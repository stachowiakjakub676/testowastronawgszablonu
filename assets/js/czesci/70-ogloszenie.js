// Ogłoszenie z datą końca: build wstawia je tylko między „od” a „do”, a nocny build odświeża stronę. Gdyby nocny build
// nie przeszedł, ten skrypt chowa ogłoszenie dzień po dacie data-do — „dziś” liczone w strefie Europe/Warsaw
// (niezależnie od strefy odwiedzającego), porównanie dat RRRR-MM-DD jako tekstu. Hak: [data-do="RRRR-MM-DD"].
(() => {
  const ogloszenia = document.querySelectorAll('[data-do]');
  if (!ogloszenia.length) return;
  const dzis = () => {
    const p = {};
    new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit', day: '2-digit' })
      .formatToParts(new Date()).forEach((x) => { p[x.type] = x.value; });
    return `${p.year}-${p.month}-${p.day}`;
  };
  const sprawdz = () => {
    const d = dzis();
    ogloszenia.forEach((el) => {
      if (/^\d{4}-\d{2}-\d{2}$/.test(el.dataset.do) && d > el.dataset.do) el.hidden = true;
    });
  };
  sprawdz();
  // strona otwarta przez północ (kiosk, karta w tle) też traci nieaktualne ogłoszenie
  setInterval(sprawdz, 15 * 60 * 1000);
})();
