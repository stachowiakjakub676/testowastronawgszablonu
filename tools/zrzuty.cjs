// Zrzuty ekranu i szybkie kontrole w przeglądarce (Playwright, lokalnie — nie jest częścią strony).
//   node tools/zrzuty.cjs http://localhost:8765 <katalog-wyniku> [prefiks] [ścieżka …]
// Dla każdej strony i szerokości (375, 768, 1440): zrzut całej strony, pierwszy ekran 375×667 (<plik>-ekran.png,
// także bez JS), przewijanie poziome (musi być 0), błędy w konsoli (także naruszenia CSP), żądania do obcych domen.
// Na zrzutach całej strony pasek „Zadzwoń” (.callbar, position: fixed) jest ukryty — Chromium rysuje go w wysokości
// pierwszego ekranu, na środku treści. Jak pasek leży na ekranie, pokazuje zrzut -ekran.
// Każdy widok ma limit czasu (ZRZUTY_LIMIT_S, domyślnie 90 s) — zawieszona strona to PROBLEM, nie zawieszony skrypt.
// Wymaga: NODE_PATH z pakietem playwright; ścieżka Chromium w zmiennej CHROMIUM (opcjonalnie).
//
// Zmienne dodatkowe (używa ich tools/sprawdz.sh):
//   ZRZUTY_TRYBY=bezjs,wymuszone   dodatkowo zrzut 375 i 1440 bez JavaScriptu oraz w trybie wymuszonych kolorów
//   ZRZUTY_JSON=raport/zrzuty.json wyniki jako JSON: przewijanie, konsola, obce domeny, ciasteczka, localStorage,
//                                  liczba żądań i waga pierwszego widoku (375×667, bez przewijania) — dla tools/raport.py
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [baza = 'http://localhost:8765', wyjscie = '.', prefiks = 'strona', ...sciezki] = process.argv.slice(2);
  const strony = sciezki.length ? sciezki : ['/', '/kontakt', '/polityka-prywatnosci', '/nie-ma-takiej'];
  const tryby = (process.env.ZRZUTY_TRYBY || '').split(',').map((t) => t.trim()).filter(Boolean);
  const opcje = { args: ['--no-sandbox'] };
  if (process.env.CHROMIUM) opcje.executablePath = process.env.CHROMIUM;
  const przegladarka = await chromium.launch(opcje);
  const host = new URL(baza).host;
  const wyniki = [];
  let problemy = 0;
  const limitMs = (Number(process.env.ZRZUTY_LIMIT_S) || 90) * 1000;

  // [nazwa, szerokość, wysokość, opcje kontekstu, czy pełny zestaw kontroli]
  const widoki = [['375', 375, 667, {}], ['768', 768, 1024, {}], ['1440', 1440, 900, {}]];
  if (tryby.includes('bezjs')) widoki.push(['375-bezjs', 375, 667, { javaScriptEnabled: false }], ['1440-bezjs', 1440, 900, { javaScriptEnabled: false }]);
  if (tryby.includes('wymuszone')) widoki.push(['375-wymuszone', 375, 667, { forcedColors: 'active' }], ['1440-wymuszone', 1440, 900, { forcedColors: 'active' }]);
  // „tylko” = same tryby dodatkowe, bez zwykłych szerokości (gdy zwykłe zrzuty są już zrobione)
  if (tryby.includes('tylko')) widoki.splice(0, 3);

  for (const s of strony) {
    for (const [nazwa, w, h, kontekstOpcje] of widoki) {
      const kontekst = await przegladarka.newContext({ viewport: { width: w, height: h }, ...kontekstOpcje });
      const strona = await kontekst.newPage();
      strona.setDefaultTimeout(30000);

      async function widok() {
        const bledy = [];
        const obce = new Set();
        let zadania = 0;
        let bajty = 0;
        strona.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') bledy.push(`${m.type()}: ${m.text()}`); });
        strona.on('pageerror', (e) => bledy.push(`wyjątek: ${e.message}`));
        strona.on('request', (r) => {
          const u = new URL(r.url());
          if (!u.protocol.startsWith('http')) return;
          zadania += 1;
          if (u.host !== host) obce.add(u.host);
        });
        const rozmiary = [];
        strona.on('requestfinished', (r) => {
          rozmiary.push(r.sizes().then((x) => { bajty += x.responseBodySize + x.responseHeadersSize; }).catch(() => {}));
        });
        const odp = await strona.goto(baza + s, { waitUntil: 'networkidle', timeout: 45000 });
        const przewijanie = await strona.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        const pamiec = kontekstOpcje.javaScriptEnabled === false ? 0
          : await strona.evaluate(() => { try { return localStorage.length + sessionStorage.length; } catch (e) { return 0; } });
        const ciasteczka = (await kontekst.cookies()).length;
        // waga i żądania pierwszego widoku liczymy przed przewinięciem (zrzut całej strony doczytuje leniwe obrazy)
        await Promise.all(rozmiary);
        const pierwszyWidok = { zadania, bajty };
        const plik = `${prefiks}-${s === '/' ? 'glowna' : s.replace(/^\//, '').replace(/\//g, '_')}-${nazwa}`;
        // pierwszy ekran (z paskiem „Zadzwoń”, tak jak widzi go odwiedzający) — przed przewijaniem
        if (nazwa.startsWith('375')) await strona.screenshot({ path: path.join(wyjscie, `${plik}-ekran.png`) });
        // zrzut całej strony nie przewija okna, więc leniwe obrazy poniżej pierwszego ekranu zostałyby puste —
        // przewijamy stronę krokami i czekamy na obrazy, potem wracamy na górę. Kroki robi Playwright (kółko myszy
        // i czekanie po stronie Node): bez JavaScriptu na stronie setTimeout w evaluate nigdy się nie kończy.
        const wysokosc = await strona.evaluate(() => document.documentElement.scrollHeight);
        for (let y = 0; y < wysokosc; y += h) {
          await strona.mouse.wheel(0, h);
          await strona.waitForTimeout(60);
        }
        await strona.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
        await strona.mouse.wheel(0, -wysokosc - h);
        // pasek na dole (position: fixed) na zrzucie całej strony stoi w połowie treści — tu go chowamy
        // (CSSOM, nie <style>: CSP strony blokuje style w dokumencie, a zmiana przez element.style jest dozwolona)
        await strona.evaluate(() => document.querySelectorAll('.callbar').forEach((e) => { e.style.display = 'none'; }));
        await strona.waitForTimeout(300);
        await strona.screenshot({ path: path.join(wyjscie, `${plik}.png`), fullPage: true });
        // strona 404 sama ma status 404 — ten jeden komunikat konsoli jest oczekiwany
        const bledyTekst = bledy.filter((b) => !/favicon/.test(b));
        if (odp.status() === 404) {
          const i = bledyTekst.findIndex((b) => /status of 404/.test(b));
          if (i >= 0) bledyTekst.splice(i, 1);
        }
        const zle = przewijanie > 0 || bledyTekst.length || obce.size || ciasteczka || pamiec;
        if (zle) problemy += 1;
        console.log(`${zle ? 'PROBLEM' : 'OK     '} ${s} @${nazwa}: status ${odp.status()}, przewijanie poziome ${przewijanie}px`
          + (bledyTekst.length ? `, konsola: ${bledyTekst.join(' | ')}` : '')
          + (obce.size ? `, obce domeny: ${[...obce].join(', ')}` : '')
          + (ciasteczka ? `, ciasteczka: ${ciasteczka}` : '')
          + (pamiec ? `, localStorage/sessionStorage: ${pamiec}` : ''));
        wyniki.push({ sciezka: s, widok: nazwa, szerokosc: w, status: odp.status(), przewijanie, konsola: bledyTekst,
          obce_domeny: [...obce], ciasteczka, pamiec, pierwszy_widok: pierwszyWidok, plik: `${plik}.png` });
      }

      let zegar;
      const limit = new Promise((_, odrzuc) => { zegar = setTimeout(() => odrzuc(new Error(`przekroczony limit ${limitMs / 1000} s`)), limitMs); });
      try {
        await Promise.race([widok(), limit]);
      } catch (e) {
        problemy += 1;
        console.log(`PROBLEM ${s} @${nazwa}: ${e.message.split('\n')[0]}`);
        wyniki.push({ sciezka: s, widok: nazwa, szerokosc: w, blad: e.message.split('\n')[0] });
      } finally {
        clearTimeout(zegar);
        await kontekst.close().catch(() => {});
      }
    }
  }
  await przegladarka.close();
  if (process.env.ZRZUTY_JSON) {
    fs.writeFileSync(process.env.ZRZUTY_JSON, JSON.stringify({ baza, data: new Date().toISOString(), problemy, wyniki }, null, 2) + '\n');
  }
  process.exit(problemy ? 1 : 0);
})();
