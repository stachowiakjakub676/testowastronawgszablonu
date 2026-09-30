// Filtr kategorii i „Pokaż więcej” (KONTRAKT §11) oraz role ARIA tabel układanych w stos. Bez JS widać wszystko.
//
// 1. Filtr: [data-filtr] zawiera linki a[data-kategoria="slug"] (prawdziwe <a href="?kategoria=slug">, „Wszystkie” ma
//    data-kategoria="") i elementy [data-filtr-element="slug"]. Kategoria z adresu (?kategoria=) działa od razu po
//    wejściu — link można wysłać klientowi. Klik filtruje w miejscu, poprawia adres (history.replaceState), ustawia
//    aria-current="true" na aktywnym linku i ogłasza wynik w [data-filtr-status] („Pokazano 6 z 24”). Nieznana
//    kategoria = wszystkie. Klik z Ctrl/Cmd/Shift albo środkowym przyciskiem otwiera zwykły link.
// 2. „Pokaż więcej”: kontener [data-wiecej] (lista albo <tbody>) z elementami [data-wiecej-reszta] i przycisk
//    [data-wiecej-przycisk][aria-controls=<id kontenera>] (w HTML ukryty). Skrypt zwija resztę (.is-zwiniete — reguła
//    w 13-realizacje.css, tylko na ekranie) i pokazuje przycisk; po kliknięciu fokus przechodzi na pierwszy odsłonięty element.
// 3. table[data-stos]: na telefonie wiersze tabeli mają display: grid, a Safari gubi wtedy semantykę tabeli —
//    jawne role (table/rowgroup/row/columnheader/rowheader/cell) ją przywracają. W HTML ich nie ma (są zbędne dla walidatora).
(() => {
  document.querySelectorAll('[data-filtr]').forEach((kontener) => {
    const linki = [...kontener.querySelectorAll('a[data-kategoria]')];
    const elementy = [...kontener.querySelectorAll('[data-filtr-element]')];
    const status = kontener.querySelector('[data-filtr-status]');
    if (!linki.length || !elementy.length) return;
    const znane = new Set(linki.map((a) => a.dataset.kategoria));
    const pokaz = (kategoria, oglos) => {
      const kat = znane.has(kategoria) ? kategoria : '';
      let n = 0;
      elementy.forEach((el) => {
        const tak = !kat || el.dataset.filtrElement.split(' ').includes(kat);
        el.hidden = !tak;
        if (tak) n += 1;
      });
      linki.forEach((a) => {
        if (a.dataset.kategoria === kat) a.setAttribute('aria-current', 'true');
        else a.removeAttribute('aria-current');
      });
      if (status && (oglos || kat)) {
        status.textContent = kat ? `Pokazano ${n} z ${elementy.length}` : `Pokazano wszystkie: ${elementy.length}`;
      }
      return kat;
    };
    linki.forEach((a) => a.addEventListener('click', (e) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      const kat = pokaz(a.dataset.kategoria, true);
      const adres = new URL(window.location.href);
      if (kat) adres.searchParams.set('kategoria', kat);
      else adres.searchParams.delete('kategoria');
      window.history.replaceState(null, '', adres.pathname + adres.search + adres.hash);
    }));
    pokaz(new URLSearchParams(window.location.search).get('kategoria') || '', false);
  });

  document.querySelectorAll('[data-wiecej]').forEach((kontener) => {
    const reszta = kontener.querySelectorAll('[data-wiecej-reszta]');
    const przycisk = kontener.id && document.querySelector(`[data-wiecej-przycisk][aria-controls="${kontener.id}"]`);
    if (!reszta.length || !przycisk) return;
    kontener.classList.add('is-zwiniete');
    przycisk.setAttribute('aria-expanded', 'false');
    przycisk.hidden = false;
    przycisk.addEventListener('click', () => {
      kontener.classList.remove('is-zwiniete');
      przycisk.setAttribute('aria-expanded', 'true');
      const pierwszy = reszta[0];
      pierwszy.tabIndex = -1;
      pierwszy.focus();
      (przycisk.closest('.wiecej') || przycisk).hidden = true;
    });
  });

  document.querySelectorAll('table[data-stos]').forEach((t) => {
    t.setAttribute('role', 'table');
    t.querySelectorAll('thead, tbody, tfoot').forEach((el) => el.setAttribute('role', 'rowgroup'));
    t.querySelectorAll('tr').forEach((el) => el.setAttribute('role', 'row'));
    t.querySelectorAll('th').forEach((el) => el.setAttribute('role', el.scope === 'row' ? 'rowheader' : 'columnheader'));
    t.querySelectorAll('td').forEach((el) => el.setAttribute('role', 'cell'));
  });
})();
