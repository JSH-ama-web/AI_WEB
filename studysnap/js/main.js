// 모든 페이지 공통: 모바일 메뉴 토글 + 다크 모드
(function () {
  const root = document.documentElement;

  // 저장된 테마 적용 (localStorage가 막힌 환경 대비 try/catch)
  let saved = null;
  try { saved = localStorage.getItem('theme'); } catch (e) {}
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = saved || (prefersDark ? 'dark' : 'light');

  const themeBtn = document.querySelector('.theme-toggle');
  const syncIcon = () => { if (themeBtn) themeBtn.textContent = root.dataset.theme === 'dark' ? '☀️' : '🌙'; };
  syncIcon();
  themeBtn?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('theme', root.dataset.theme); } catch (e) {}
    syncIcon();
  });

  // 모바일 햄버거 메뉴
  const menuBtn = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav');
  menuBtn?.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    menuBtn.setAttribute('aria-expanded', String(open));
    menuBtn.textContent = open ? '✕' : '☰';
  });
})();
