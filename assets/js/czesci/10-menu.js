// Menu na telefonie (< 960 px): przycisk „Menu” rozwija nawigację pod nagłówkiem.
// Esc zamyka i wraca fokusem na przycisk, klik w link albo poza nagłówek zamyka. Bez JS menu jest widoczne zawsze.
(() => {
  const naglowek = document.querySelector('.site-header');
  const przycisk = naglowek && naglowek.querySelector('.nav-toggle');
  const nav = document.getElementById('nav');
  if (!przycisk || !nav) return;
  const otwarte = () => przycisk.getAttribute('aria-expanded') === 'true';
  const ustaw = (stan) => {
    naglowek.classList.toggle('is-open', stan);
    przycisk.setAttribute('aria-expanded', String(stan));
  };
  przycisk.addEventListener('click', () => ustaw(!otwarte()));
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) ustaw(false); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && otwarte()) { ustaw(false); przycisk.focus(); }
  });
  document.addEventListener('click', (e) => { if (otwarte() && !naglowek.contains(e.target)) ustaw(false); });
  const szeroki = window.matchMedia('(min-width: 960px)');
  szeroki.addEventListener('change', () => { if (szeroki.matches) ustaw(false); });
})();
