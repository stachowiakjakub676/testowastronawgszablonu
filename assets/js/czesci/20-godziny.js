// Status „Otwarte do 15:00 / Zamknięte. Otwieramy jutro o 7:00” liczony w strefie Europe/Warsaw
// (niezależnie od strefy odwiedzającego) z JSON-LD strony: openingHoursSpecification + specialOpeningHoursSpecification.
// Kilka przedziałów dziennie, przedziały po północy, wyjątki (święta). Odświeżanie co 60 s, podświetlenie dzisiejszego wiersza.
// Haki: [data-status] (opcjonalnie data-nazwa="Biuro"), tr[data-dzien="pn|wt|sr|cz|pt|sb|nd"].
(() => {
  const statusy = document.querySelectorAll('[data-status]');
  const wiersze = document.querySelectorAll('tr[data-dzien]');
  if (!statusy.length && !wiersze.length) return;

  const DNI = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const KODY = ['pn', 'wt', 'sr', 'cz', 'pt', 'sb', 'nd'];
  const KIEDY = ['w poniedziałek', 'we wtorek', 'w środę', 'w czwartek', 'w piątek', 'w sobotę', 'w niedzielę'];
  const minuty = (t) => +t.slice(0, 2) * 60 + +t.slice(3, 5);
  // 1440 = zamknięcie o północy → „24:00” (jak w tabeli godzin); 1560 = 2:00 następnego dnia
  const godzina = (m) => { if (m === 1440) return '24:00'; m %= 1440; return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`; };

  let wezel = null;
  document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
    if (wezel) return;
    try {
      const d = JSON.parse(s.textContent);
      wezel = (d['@graph'] || [d]).find((w) => w.openingHoursSpecification) || null;
    } catch (e) { /* uszkodzony JSON-LD — build to wyłapuje */ }
  });

  const zakres = (s) => {
    const od = minuty(s.opens);
    let doo = s.closes === '23:59' ? 1440 : minuty(s.closes);
    if (doo <= od) doo += 1440; // zamknięcie po północy
    return [od, doo];
  };
  const tydzien = [[], [], [], [], [], [], []];
  const wyjatki = {}; // 'RRRR-MM-DD' → [[od, do], …]; [] = zamknięte cały dzień
  if (wezel) {
    wezel.openingHoursSpecification.forEach((s) => {
      [].concat(s.dayOfWeek || []).forEach((d) => {
        const i = DNI.indexOf(String(d).replace(/^https?:\/\/schema\.org\//, ''));
        if (i >= 0) tydzien[i].push(zakres(s));
      });
    });
    (wezel.specialOpeningHoursSpecification || []).forEach((s) => {
      if (!s.validFrom) return;
      const lista = (wyjatki[s.validFrom] = wyjatki[s.validFrom] || []);
      if (!(s.opens === '00:00' && s.closes === '00:00')) lista.push(zakres(s));
    });
  }

  const teraz = () => {
    const p = {};
    new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit', day: '2-digit',
      weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date()).forEach((x) => { p[x.type] = x.value; });
    return {
      dzien: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(p.weekday),
      min: +p.hour * 60 + +p.minute,
      data: `${p.year}-${p.month}-${p.day}`,
    };
  };
  const przesun = (data, n) => {
    const d = new Date(`${data}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  const przedzialy = (data, dzien) => (wyjatki[data] !== undefined ? wyjatki[data] : tydzien[dzien]);

  const status = (t) => {
    // otwarte teraz — także przedział z wczoraj, który trwa po północy
    for (const [, doo] of przedzialy(przesun(t.data, -1), (t.dzien + 6) % 7)) {
      if (doo > 1440 && t.min < doo - 1440) return { otwarte: true, tekst: `Otwarte do ${godzina(doo)}` };
    }
    for (const [od, doo] of przedzialy(t.data, t.dzien)) {
      if (t.min >= od && t.min < doo) return { otwarte: true, tekst: `Otwarte do ${godzina(doo)}` };
    }
    for (let n = 0; n < 8; n += 1) {
      const dzien = (t.dzien + n) % 7;
      const lista = przedzialy(przesun(t.data, n), dzien).filter(([od]) => n > 0 || od > t.min).sort((a, b) => a[0] - b[0]);
      if (lista.length) {
        const kiedy = n === 0 ? 'dziś' : n === 1 ? 'jutro' : KIEDY[dzien];
        return { otwarte: false, tekst: `Zamknięte. Otwieramy ${kiedy} o ${godzina(lista[0][0])}` };
      }
    }
    return { otwarte: false, tekst: 'Zamknięte' };
  };

  const odswiez = () => {
    const t = teraz();
    if (wezel) {
      const s = status(t);
      statusy.forEach((el) => {
        const nazwa = el.dataset.nazwa;
        const tekst = nazwa ? `${nazwa}: ${s.tekst.charAt(0).toLowerCase()}${s.tekst.slice(1)}` : s.tekst;
        if (el.textContent !== tekst) el.textContent = tekst; // bez zmian = bez ponownego odczytu przez czytnik
        el.classList.toggle('is-otwarte', s.otwarte);
        el.classList.toggle('is-zamkniete', !s.otwarte);
        el.hidden = false;
      });
    }
    wiersze.forEach((w) => {
      const dzis = w.dataset.dzien === KODY[t.dzien];
      w.classList.toggle('is-dzis', dzis);
      if (dzis) w.setAttribute('aria-current', 'date'); else w.removeAttribute('aria-current');
    });
  };
  odswiez();
  setInterval(odswiez, 60000);
})();
