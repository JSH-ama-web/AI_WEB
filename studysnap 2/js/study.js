// 노트 정리하기 페이지: 입력 → fetch('/api/study') → 결과 표시
const MIN_LEN = 30;
const MAX_LEN = 6000;
const SLOW_MS = 8000;     // 8초 넘으면 "조금 걸려요" 안내
const TIMEOUT_MS = 30000; // 30초 넘으면 요청 중단

const form = document.getElementById('study-form');
const note = document.getElementById('note');
const quizCount = document.getElementById('quiz-count');
const charCount = document.getElementById('char-count');
const submitBtn = document.getElementById('submit-btn');
const statusBox = document.getElementById('status');
const resultBox = document.getElementById('result');

const SAMPLE = `연속방정식은 유체의 질량 보존 법칙을 수식으로 나타낸 것이다. 비압축성 유체가 관을 흐를 때 단면적 A와 평균 유속 V의 곱인 유량 Q는 어느 단면에서나 같다(Q = A1V1 = A2V2). 따라서 관이 좁아지면 유속이 빨라진다.
베르누이 방정식은 에너지 보존을 나타내며, 압력 수두 + 속도 수두 + 위치 수두의 합이 하나의 유선을 따라 일정하다. 이 식은 마찰이 없고 정상류이며 비압축성인 흐름이라는 가정에서 성립한다. 실제 관로에서는 마찰에 의한 손실 수두를 추가로 고려해야 한다.`;

// ---- 상태 메시지 ----
function showStatus(type, message) {
  statusBox.hidden = false;
  statusBox.className = `status ${type}`;
  statusBox.innerHTML = type === 'loading' || type === 'slow'
    ? `<span class="spinner"></span>${message}` : message;
}
function hideStatus() { statusBox.hidden = true; }

// ---- 글자 수 ----
function updateCount() {
  const len = note.value.length;
  charCount.textContent = `${len.toLocaleString()} / ${MAX_LEN.toLocaleString()}자`;
  charCount.style.color = len > MAX_LEN ? 'var(--danger)' : '';
  note.classList.remove('invalid');
}
note.addEventListener('input', updateCount);

document.getElementById('sample-btn').addEventListener('click', () => {
  note.value = SAMPLE;
  updateCount();
  note.focus();
});

// ---- 결과 렌더링 (textContent 사용 → AI 응답에 HTML이 섞여도 안전) ----
function el(tag, text) { const e = document.createElement(tag); if (text) e.textContent = text; return e; }

function renderResult(data) {
  document.getElementById('summary').textContent = data.summary || '요약 결과가 비어 있어요.';

  const kw = document.getElementById('keywords');
  kw.replaceChildren();
  (data.keywords || []).forEach(k => {
    const li = el('li');
    li.append(el('strong', k.term || ''), el('span', k.desc || ''));
    kw.append(li);
  });
  if (!kw.children.length) kw.append(el('li', '추출된 키워드가 없어요.'));

  const qz = document.getElementById('quiz');
  qz.replaceChildren();
  (data.quiz || []).forEach(q => {
    const li = el('li');
    const d = el('details');
    d.append(el('summary', q.q || ''), el('p', `정답: ${q.a || ''}`));
    li.append(d);
    qz.append(li);
  });
  if (!qz.children.length) qz.append(el('li', '생성된 문제가 없어요.'));

  resultBox.hidden = false;
  resultBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ---- 제출 ----
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = note.value.trim();

  // 실패 처리 1: 빈 입력 / 길이 검사
  if (!text) {
    note.classList.add('invalid');
    return showStatus('error', '⚠️ 강의 노트를 입력해 주세요.');
  }
  if (text.length < MIN_LEN) {
    note.classList.add('invalid');
    return showStatus('error', `⚠️ 내용이 너무 짧아요. ${MIN_LEN}자 이상 입력해 주세요.`);
  }
  if (text.length > MAX_LEN) {
    note.classList.add('invalid');
    return showStatus('error', `⚠️ 내용이 너무 길어요. ${MAX_LEN.toLocaleString()}자 이하로 줄여 주세요.`);
  }

  submitBtn.disabled = true;   // 중복 호출 방지(과금 보호)
  submitBtn.textContent = '정리하는 중...';
  resultBox.hidden = true;
  showStatus('loading', 'AI가 노트를 읽고 있어요...');

  // 실패 처리 3: 지연 / 타임아웃
  const controller = new AbortController();
  const slowTimer = setTimeout(() => showStatus('slow', '평소보다 오래 걸리고 있어요. 조금만 기다려 주세요...'), SLOW_MS);
  const abortTimer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch('/api/study', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, quizCount: Number(quizCount.value) }),
      signal: controller.signal,
    });

    let data = {};
    try { data = await res.json(); } catch (_) { /* JSON이 아닌 응답 */ }

    // 실패 처리 2: API 오류(4xx/5xx)
    if (!res.ok) {
      const fallback = res.status >= 500
        ? `서버 오류가 발생했어요. (${res.status}) 잠시 후 다시 시도해 주세요.`
        : `요청을 처리할 수 없어요. (${res.status})`;
      throw new Error(data.error || fallback);
    }

    hideStatus();
    renderResult(data);
  } catch (err) {
    if (err.name === 'AbortError') {
      showStatus('error', '⏱️ 응답 시간이 초과됐어요. 노트를 조금 줄여서 다시 시도해 주세요.');
    } else if (err instanceof TypeError) {
      showStatus('error', '📡 네트워크 연결을 확인해 주세요.');
    } else {
      showStatus('error', `❌ ${err.message}`);
    }
  } finally {
    clearTimeout(slowTimer);
    clearTimeout(abortTimer);
    submitBtn.disabled = false;
    submitBtn.textContent = 'AI로 정리하기';
  }
});

// ---- 결과 복사 ----
document.getElementById('copy-btn').addEventListener('click', async () => {
  const txt = resultBox.innerText;
  try {
    await navigator.clipboard.writeText(txt);
    showStatus('loading', '📋 결과를 복사했어요.');
    setTimeout(hideStatus, 1500);
  } catch (_) {
    showStatus('error', '복사에 실패했어요. 직접 드래그해서 복사해 주세요.');
  }
});
