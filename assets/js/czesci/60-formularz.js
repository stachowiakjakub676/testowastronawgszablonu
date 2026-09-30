// Formularz zapytania (tryb worker): wysyłka fetch → JSON. Błędy przy polach (aria-invalid + aria-describedby),
// fokus na pierwszy błąd. Gdy wysyłka nie jest skonfigurowana (503) albo Worker nie odpowiada — otwieramy mailto:
// z treścią z formularza. Pola: imie, kontakt, wiadomosc, strona_www (pułapka), t — KONTRAKT §13.
// t = ile milisekund formularz był otwarty (performance.now(), liczone od otwarcia strony albo od ostatniej wysyłki);
// zegar odwiedzającego nie ma tu znaczenia, więc przestawiona godzina w telefonie nie zgubi wiadomości.
(() => {
  const KOMUNIKATY = {
    imie: 'Wpisz imię i nazwisko.',
    kontakt: 'Podaj telefon albo adres e-mail, żebyśmy mogli odpowiedzieć.',
    wiadomosc: 'Napisz, czego dotyczy zapytanie.',
  };
  document.querySelectorAll('form[data-formularz]').forEach((form) => {
    const czas = form.querySelector('input[name="t"]');
    let start = performance.now();
    form.noValidate = true; // własne komunikaty po polsku zamiast dymków przeglądarki
    const status = form.querySelector('.formularz__status');
    const przycisk = form.querySelector('[type="submit"]');

    const wyczysc = () => {
      form.querySelectorAll('.pole__blad').forEach((b) => b.remove());
      form.querySelectorAll('[aria-invalid]').forEach((p) => { p.removeAttribute('aria-invalid'); p.removeAttribute('aria-describedby'); });
    };
    const blad = (pole, tekst) => {
      const id = `${pole.id}-blad`;
      const p = document.createElement('p');
      p.className = 'pole__blad';
      p.id = id;
      p.textContent = tekst;
      pole.insertAdjacentElement('afterend', p);
      pole.setAttribute('aria-invalid', 'true');
      pole.setAttribute('aria-describedby', id);
    };
    const mailto = () => {
      const baza = form.dataset.mailto;
      if (!baza) return null;
      const w = (n) => (form.elements[n] ? form.elements[n].value.trim() : '');
      const tresc = `Imię i nazwisko: ${w('imie')}\nTelefon lub e-mail: ${w('kontakt')}\n\n${w('wiadomosc')}\n`;
      return `${baza.split('&body=')[0]}&body=${encodeURIComponent(tresc)}`;
    };

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      wyczysc();
      const bledy = [];
      Object.keys(KOMUNIKATY).forEach((nazwa) => {
        const pole = form.elements[nazwa];
        if (pole && !pole.value.trim()) { blad(pole, KOMUNIKATY[nazwa]); bledy.push(pole); }
      });
      const kontakt = form.elements.kontakt;
      if (kontakt && kontakt.value.trim() && !/@|\d{3}/.test(kontakt.value)) {
        blad(kontakt, 'To nie wygląda na telefon ani e-mail.');
        bledy.push(kontakt);
      }
      if (bledy.length) { bledy[0].focus(); return; }
      przycisk.disabled = true;
      status.textContent = 'Wysyłanie…';
      if (czas) czas.value = String(Math.round(performance.now() - start));
      try {
        const odp = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } });
        const json = (odp.headers.get('Content-Type') || '').includes('application/json');
        // brak Workera (404/405/501), wysyłka nieskonfigurowana (503) albo odpowiedź nie-JSON → mailto
        if ([404, 405, 501, 503].includes(odp.status) || !json) throw new Error('nie_skonfigurowano');
        const dane = await odp.json().catch(() => ({}));
        if (odp.ok && dane.ok !== false) {
          form.reset();
          start = performance.now();
          status.textContent = form.dataset.sukces || 'Dziękujemy, wiadomość wysłana.';
          return;
        }
        status.textContent = dane.komunikat || 'Nie udało się wysłać wiadomości. Spróbuj ponownie albo zadzwoń.';
      } catch (err) {
        const link = mailto();
        if (link) {
          status.textContent = 'Formularz chwilowo nie działa. Otwieramy program pocztowy z gotową wiadomością.';
          window.location.href = link;
        } else {
          status.textContent = 'Nie udało się wysłać wiadomości. Zadzwoń albo napisz e-mail.';
        }
      } finally {
        przycisk.disabled = false;
      }
    });
  });
})();
