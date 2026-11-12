# StudySnap 📝

> 강의 노트를 붙여 넣으면 AI가 **요약 · 핵심 키워드 · 확인 문제**를 만들어 주는 복습 도우미 웹 서비스

- **배포 URL:** https://(배포 후 여기에 Vercel 주소 입력).vercel.app
- **GitHub:** https://github.com/(본인 계정)/studysnap

## 1. 서비스 소개
시험 기간, 길고 흩어진 강의 노트를 다시 읽기 어려운 대학생을 위한 서비스입니다.
노트 텍스트를 입력하면 Claude API (코디세이 AI Gateway)가 내용을 분석해 복습용 한 장으로 정리합니다.

| 페이지 | 내용 |
|---|---|
| `index.html` 홈 | 서비스 소개, 주요 기능, 시작 버튼 |
| `study.html` 노트 정리하기 | 노트 입력 → AI 요약/키워드/확인 문제 출력 (**AI 기능**) |
| `about.html` 사용법 · 소개 | 사용 방법, 추천 대상, 안내 사항, 기술 스택 |

상단 메뉴로 페이지를 이동하며, 모바일에서는 햄버거 메뉴(☰)로 바뀝니다. 다크 모드를 지원합니다.

## 2. 기술 스택
- **Frontend:** HTML, CSS, JavaScript (Vanilla, 프레임워크 미사용)
- **Backend:** Python — Vercel Serverless Functions (`api/` 폴더)
- **AI:** Google Claude API (코디세이 AI Gateway) (generateContent)
- **배포:** GitHub + Vercel

## 3. 폴더 구조
```
studysnap/
├── index.html          # 홈
├── study.html          # AI 노트 정리
├── about.html          # 사용법 · 소개
├── css/style.css       # 공통 스타일 + 반응형 + 다크 모드
├── js/main.js          # 메뉴 토글, 다크 모드
├── js/study.js         # 입력 검증, fetch('/api/study'), 결과 표시, 실패 처리
├── api/study.py        # 서버리스 함수: Claude API (코디세이 AI Gateway) 호출
├── images/             # 이미지/스크린샷
├── docs/service-plan.md# 서비스 기획서
├── requirements.txt    # Python 패키지 목록 (표준 라이브러리만 사용)
├── vercel.json         # 함수 최대 실행 시간 설정
└── .env.example        # 환경 변수 예시 (실제 키 X)
```

## 4. 동작 흐름
1. 사용자가 `study.html`에서 노트를 입력하고 버튼 클릭
2. `js/study.js`가 입력값을 검사한 뒤 `fetch('/api/study', { method: 'POST' })`로 전송
3. `api/study.py`가 환경 변수의 API 키로 Claude API (코디세이 AI Gateway)를 호출
4. 결과(JSON)를 받아 프론트로 반환 → 화면에 요약/키워드/문제 표시

## 5. 환경 변수 설정
API 키는 코드·README·스크린샷에 절대 넣지 않습니다.

| 이름 | 필수 | 설명 |
|---|---|---|
| `AI_API_KEY` | ✅ | 코디세이 콘솔(copa.codyssey.kr)에서 발급한 API 키 |
| `AI_BASE_URL` | ✅ | 콘솔에 안내된 AI Gateway 기본 주소 |
| `AI_MODEL` | 선택 | 모델 이름 (기본값 `claude-haiku-5-5`) |
| `AI_API_FORMAT` | 선택 | `anthropic`(기본, `/v1/messages`) 또는 `openai`(`/v1/chat/completions`) |

- **Vercel:** 프로젝트 → Settings → Environment Variables 에 추가 → **Redeploy** 해야 적용됩니다.
- **로컬:** `.env.example`을 복사해 `.env.local`로 만들고 키 입력 (`.gitignore`에 포함되어 커밋되지 않음).

## 6. 실행 방법
### 로컬 실행
```bash
npm i -g vercel        # 최초 1회
vercel login
vercel link            # Vercel 프로젝트와 연결
vercel env pull .env.local   # 또는 .env.example 복사 후 직접 입력
vercel dev             # http://localhost:3000
```
> HTML만 더블클릭해서 열면 `/api/study`가 없어서 AI 기능이 동작하지 않습니다. 반드시 `vercel dev`로 실행하세요.

### 배포
1. GitHub에 저장소 push
2. vercel.com → Add New Project → 저장소 Import (Framework Preset: **Other**)
3. Environment Variables에 `AI_API_KEY`, `AI_BASE_URL` 입력 → Deploy
4. 이후 `git push`할 때마다 자동 재배포

## 7. 실패 처리
| 상황 | 처리 |
|---|---|
| 빈 입력 / 30자 미만 / 6,000자 초과 | 프론트와 서버 양쪽에서 검사, 안내 메시지 표시 |
| API 오류 (4xx/5xx, 429 요청 과다, 키 누락) | 상태 코드별 안내 메시지 표시 |
| 지연 / 타임아웃 | 8초 경과 시 "오래 걸려요" 안내, 30초 경과 시 요청 중단 후 안내 |
| 중복 클릭 | 요청 중 버튼 비활성화 (불필요한 과금 방지) |

## 8. 보안 메모
- 키가 노출되면 즉시 코디세이 콘솔에서 **폐기 후 재발급**하고 Vercel 환경 변수를 교체합니다.
- 실수로 커밋된 경우 키 폐기가 최우선이며, 이후 `git filter-repo` 등으로 이력에서 제거합니다.
