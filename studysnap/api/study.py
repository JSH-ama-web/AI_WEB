"""
StudySnap - Vercel Serverless Function (Python)
POST /api/study  { "text": "강의 노트...", "quizCount": 3 }
-> { "summary": "...", "keywords": [{"term","desc"}], "quiz": [{"q","a"}] }

API 키는 코드에 쓰지 않고 Vercel 환경 변수 ANTHROPIC_API_KEY 에서 읽는다.
외부 패키지 없이 표준 라이브러리(urllib)만 사용한다.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import socket
import urllib.request
import urllib.error

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-5-5"
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


def call_claude(text: str, quiz_count: int) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("SERVER_KEY_MISSING")

    body = {
        "model": os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": f"확인 문제 개수: {quiz_count}\n\n[강의 노트]\n{text}",
        }],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT) as res:
        data = json.loads(res.read().decode("utf-8"))

    raw = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
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
        # 배포 후 함수가 살아 있는지 확인용
        self._send(200, {"ok": True, "message": "POST로 강의 노트를 보내 주세요."})

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
            result = call_claude(text, quiz_count)
            return self._send(200, result)
        except RuntimeError:
            return self._send(500, {"error": "서버에 API 키가 설정되지 않았습니다. 관리자에게 문의하세요."})
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return self._send(429, {"error": "요청이 많아요. 잠시 후 다시 시도해 주세요."})
            if e.code in (401, 403):
                return self._send(502, {"error": "AI 서비스 인증에 실패했습니다. (서버 키 확인 필요)"})
            return self._send(502, {"error": f"AI 서비스 오류가 발생했습니다. (코드 {e.code})"})
        except (socket.timeout, TimeoutError):
            return self._send(504, {"error": "AI 응답이 너무 늦어요. 내용을 줄여서 다시 시도해 주세요."})
        except urllib.error.URLError:
            return self._send(502, {"error": "AI 서비스에 연결하지 못했습니다."})
        except Exception:
            return self._send(500, {"error": "알 수 없는 오류가 발생했습니다."})
