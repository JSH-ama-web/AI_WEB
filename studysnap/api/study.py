"""
StudySnap - Vercel Serverless Function (Python)
POST /api/study  { "text": "강의 노트...", "quizCount": 3 }
-> { "summary": "...", "keywords": [{"term","desc"}], "quiz": [{"q","a"}] }

AI: 코디세이 AI Gateway를 통해 Claude 호출
 - 기본: Anthropic Messages 형식  -> {AI_BASE_URL}/v1/messages
 - 선택: OpenAI 호환 형식(AI_API_FORMAT=openai) -> {AI_BASE_URL}/v1/chat/completions
API 키/주소/모델은 코드에 쓰지 않고 Vercel 환경 변수에서 읽는다.
  AI_API_KEY   (필수) 코디세이 콘솔에서 발급한 키
  AI_BASE_URL  (필수) 코디세이 콘솔에 안내된 Gateway 기본 주소 (끝의 /v1 은 있어도 없어도 됨)
  AI_MODEL     (선택) 모델 이름. 기본값 claude-haiku-4 (예: claude-sonnet-4)
  AI_API_FORMAT(선택) anthropic(기본) 또는 openai
외부 패키지 없이 표준 라이브러리(urllib)만 사용한다.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import socket
import urllib.request
import urllib.error

DEFAULT_MODEL = "claude-haiku-4"  # 코디세이 콘솔의 사용 가능 모델 이름
MIN_LEN = 30          # 너무 짧은 입력 차단
MAX_LEN = 6000        # 과금/쿼터 보호용 입력 상한
UPSTREAM_TIMEOUT = 25 # 초

SYSTEM_PROMPT = """너는 대학생의 복습을 돕는 학습 도우미다.
사용자가 준 강의 노트만 근거로 아래 JSON 형식으로만 답한다. 다른 문장은 쓰지 않는다.
{
  "summary": "핵심 내용을 3~5문장으로 요약",
  "keywords": [{"term": "핵심 용어", "desc": "한 줄 설명"}],
  "quiz": [{"q": "확인 문제", "a": "정답과 짧은 해설"}]
}
keywords는 4~6개, quiz는 요청된 개수만큼 만든다. 노트에 없는 내용은 지어내지 않는다."""


def build_url(base: str, path: str) -> str:
    """AI_BASE_URL 끝에 /v1 이 붙어 있든 없든 올바른 주소를 만든다."""
    base = base.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return f"{base}/v1/{path}"


class UpstreamError(Exception):
    """Gateway가 오류를 돌려준 경우: 상태 코드, 호출한 경로, Gateway 메시지를 함께 담는다."""
    def __init__(self, code: int, path: str, model: str, detail: str):
        super().__init__(detail)
        self.code, self.path, self.model, self.detail = code, path, model, detail


def get_config():
    return {
        "api_key": os.environ.get("AI_API_KEY", "").strip(),
        "base_url": os.environ.get("AI_BASE_URL", "").strip(),
        "model": os.environ.get("AI_MODEL", "").strip() or DEFAULT_MODEL,
        "format": os.environ.get("AI_API_FORMAT", "").strip().lower() or "anthropic",
    }


def post_json(url: str, body: dict, headers: dict, model: str) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            detail = ""
        path = "/" + url.split("://", 1)[-1].split("/", 1)[-1]
        raise UpstreamError(e.code, path, model, detail)


def request_anthropic(cfg: dict, user_msg: str) -> str:
    """Anthropic Messages 형식: POST {base}/v1/messages, 헤더 x-api-key"""
    data = post_json(
        build_url(cfg["base_url"], "messages"),
        {
            "model": cfg["model"],
            "max_tokens": 1500,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
        },
        {
            "Content-Type": "application/json",
            "x-api-key": cfg["api_key"],
            "anthropic-version": "2023-06-01",
        },
        cfg["model"],
    )
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def request_openai(cfg: dict, user_msg: str) -> str:
    """OpenAI 호환 형식: POST {base}/v1/chat/completions, 헤더 Authorization: Bearer"""
    data = post_json(
        build_url(cfg["base_url"], "chat/completions"),
        {
            "model": cfg["model"],
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        },
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        cfg["model"],
    )
    choices = data.get("choices") or []
    return (choices[0].get("message", {}).get("content") or "") if choices else ""


def call_ai(text: str, quiz_count: int) -> dict:
    cfg = get_config()
    if not cfg["api_key"] or not cfg["base_url"]:
        raise RuntimeError("SERVER_KEY_MISSING")

    user_msg = f"확인 문제 개수: {quiz_count}\n\n[강의 노트]\n{text}"
    first, second = (request_openai, request_anthropic) if cfg["format"] == "openai" \
        else (request_anthropic, request_openai)

    try:
        raw = first(cfg, user_msg)
    except UpstreamError as e:
        # 경로/형식이 안 맞을 때(404, 405)만 다른 형식으로 한 번 더 시도
        if e.code not in (404, 405):
            raise
        raw = second(cfg, user_msg)

    if not raw.strip():
        raise ValueError("EMPTY_RESPONSE")
    return parse_result(raw)


def parse_result(raw: str) -> dict:
    """모델 응답에서 JSON만 꺼낸다. 실패하면 요약 칸에 원문을 넣어 준다."""
    start, end = raw.find("{"), raw.rfind("}")
    try:
        result = json.loads(raw[start:end + 1])
    except (ValueError, json.JSONDecodeError):
        return {"summary": raw.strip(), "keywords": [], "quiz": []}
    return {
        "summary": str(result.get("summary", "")),
        "keywords": result.get("keywords", []) or [],
        "quiz": result.get("quiz", []) or [],
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict):
        out = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        # 배포 후 설정 확인용 (키 값은 절대 보여 주지 않고, 설정 여부만 표시)
        cfg = get_config()
        self._send(200, {
            "ok": True,
            "api_key_set": bool(cfg["api_key"]),
            "base_url": cfg["base_url"] or "(설정 안 됨)",
            "model": cfg["model"],
            "format": cfg["format"],
        })

    def do_POST(self):
        # 1) 요청 파싱
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "잘못된 요청 형식입니다."})

        text = str(payload.get("text", "")).strip()
        try:
            quiz_count = max(1, min(5, int(payload.get("quizCount", 3))))
        except (TypeError, ValueError):
            quiz_count = 3

        # 2) 입력 검증 (프론트에서도 검사하지만 서버에서 한 번 더)
        if not text:
            return self._send(400, {"error": "강의 노트를 입력해 주세요."})
        if len(text) < MIN_LEN:
            return self._send(400, {"error": f"내용이 너무 짧아요. {MIN_LEN}자 이상 입력해 주세요."})
        if len(text) > MAX_LEN:
            return self._send(413, {"error": f"내용이 너무 길어요. {MAX_LEN}자 이하로 줄여 주세요."})

        # 3) AI 호출 + 실패 처리
        try:
            result = call_ai(text, quiz_count)
            return self._send(200, result)
        except RuntimeError:
            return self._send(500, {"error": "서버에 API 키 또는 주소가 설정되지 않았습니다. 관리자에게 문의하세요."})
        except UpstreamError as e:
            info = f"[{e.code}] {e.path} · 모델 {e.model} · {e.detail}"
            if e.code == 429:
                return self._send(429, {"error": "요청이 많아요. 잠시 후 다시 시도해 주세요."})
            if e.code in (401, 403):
                return self._send(502, {"error": f"AI 서비스 인증에 실패했습니다. 키를 확인하세요. {info}"})
            if e.code == 404:
                return self._send(502, {"error": f"AI 서버 주소나 모델 이름이 올바르지 않습니다. {info}"})
            return self._send(502, {"error": f"AI 서비스 오류가 발생했습니다. {info}"})
        except ValueError:
            return self._send(502, {"error": "AI가 결과를 만들지 못했어요. 노트 내용을 바꿔서 다시 시도해 주세요."})
        except (socket.timeout, TimeoutError):
            return self._send(504, {"error": "AI 응답이 너무 늦어요. 내용을 줄여서 다시 시도해 주세요."})
        except urllib.error.URLError:
            return self._send(502, {"error": "AI 서비스에 연결하지 못했습니다."})
        except Exception:
            return self._send(500, {"error": "알 수 없는 오류가 발생했습니다."})
