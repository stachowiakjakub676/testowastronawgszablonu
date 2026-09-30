// Mapa OpenStreetMap dopiero po kliknięciu „Pokaż mapę” — przy wejściu na stronę nic nie łączy się z obcym serwerem.
// Hak: [data-mapa] z data-src (adres osadzenia) i data-tytul (tytuł ramki dla czytników ekranu).
// Po kliknięciu ramka zastępuje opis i przycisk, link „Otwórz mapę w OpenStreetMap” zostaje, a fokus przechodzi
// na ramkę (nie ginie na <body>, gdy znika kliknięty przycisk).
(() => {
  document.querySelectorAll('[data-mapa]').forEach((el) => {
    const przycisk = el.querySelector('button');
    if (!przycisk || !el.dataset.src) return;
    przycisk.hidden = false;
    przycisk.addEventListener('click', () => {
      const ramka = document.createElement('iframe');
      ramka.src = el.dataset.src;
      ramka.title = el.dataset.tytul || 'Mapa';
      ramka.className = 'mapa__ramka';
      const opis = el.querySelector('.mapa__opis');
      if (opis) opis.replaceWith(ramka); else el.prepend(ramka);
      przycisk.remove();
      ramka.focus();
    }, { once: true });
  });
})();
