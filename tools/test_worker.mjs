// Testy Workera (worker/index.js) bez zależności: node tools/test_worker.mjs
// Sprawdza każdą gałąź POST /api/kontakt i scheduled() z podmienionym fetch i env (KONTRAKT §12, §13).
// Wynik: lista „ok / BŁĄD”, kod wyjścia 1 przy pierwszym niepowodzeniu w podsumowaniu.
import worker from '../worker/index.js';

const ORIGIN = 'https://www.firma-testowa.pl';
const URL_KONTAKT = `${ORIGIN}/api/kontakt`;
let wynik = 0;
let wyslane = [];      // zapytania do Resend przechwycone przez podmieniony fetch
let odpowiedzResend = () => new Response('{"id":"x"}', { status: 200 });

globalThis.fetch = async (url, opcje = {}) => {
  wyslane.push({ url: String(url), opcje });
  return odpowiedzResend(url, opcje);
};
const cicho = console.log;
console.log = () => {};   // Worker loguje błędy wysyłki — w testach niepotrzebne

const env = (zmiany = {}) => ({
  RESEND_API_KEY: 're_test', ADRESAT: 'biuro@firma-testowa.pl, szef@firma-testowa.pl', NADAWCA: 'Formularz <f@send.firma-testowa.pl>',
  LIMIT_KONTAKT: { limit: async () => ({ success: true }) },
  ASSETS: { fetch: async () => new Response('plik', { status: 200 }) },
  ...zmiany,
});

function formularz(pola = {}) {
  const f = new FormData();
  const dane = { imie: 'Jan Testowy', kontakt: 'jan@example.com', wiadomosc: 'Proszę o wycenę 120 m² kostki.', strona_www: '',
    t: '10000', ...pola };
  for (const [k, v] of Object.entries(dane)) if (v !== undefined) f.append(k, v);
  return f;
}

function zadanie(pola, { json = true, origin = ORIGIN, metoda = 'POST', url = URL_KONTAKT, body, fetchSite, naglowki = {} } = {}) {
  const headers = { 'CF-Connecting-IP': '203.0.113.7' };
  if (origin) headers.Origin = origin;
  if (fetchSite) headers['Sec-Fetch-Site'] = fetchSite;
  if (json) headers.Accept = 'application/json';
  Object.assign(headers, naglowki);
  const init = { method: metoda, headers };
  if (metoda === 'POST') init.body = body !== undefined ? body : formularz(pola);
  return new Request(url, init);
}

async function sprawdz(nazwa, fn) {
  wyslane = [];
  odpowiedzResend = () => new Response('{"id":"x"}', { status: 200 });
  try {
    await fn();
    cicho(`ok     ${nazwa}`);
  } catch (e) {
    wynik = 1;
    cicho(`BŁĄD   ${nazwa}\n       ${e.message}`);
  }
}

function rowne(a, b, opis) {
  if (a !== b) throw new Error(`${opis}: jest ${JSON.stringify(a)}, oczekiwano ${JSON.stringify(b)}`);
}

async function json(odp) {
  rowne((odp.headers.get('Content-Type') || '').startsWith('application/json'), true, 'Content-Type JSON');
  return odp.json();
}

await sprawdz('sukces (JSON): wysyłka do Resend z Reply-To, dwoma adresatami i nagłówkami bezpieczeństwa', async () => {
  const odp = await worker.fetch(zadanie(), env());
  rowne(odp.status, 200, 'status');
  rowne((await json(odp)).ok, true, 'ok');
  rowne(odp.headers.get('X-Content-Type-Options'), 'nosniff', 'nosniff');
  rowne(wyslane.length, 1, 'liczba wysyłek');
  rowne(wyslane[0].url, 'https://api.resend.com/emails', 'adres Resend');
  rowne(wyslane[0].opcje.headers.Authorization, 'Bearer re_test', 'klucz');
  const list = JSON.parse(wyslane[0].opcje.body);
  rowne(list.reply_to, 'jan@example.com', 'reply_to');
  rowne(list.to.join('|'), 'biuro@firma-testowa.pl|szef@firma-testowa.pl', 'adresaci');
  rowne(list.from, 'Formularz <f@send.firma-testowa.pl>', 'nadawca');
  rowne(list.text.includes('120 m² kostki'), true, 'treść w wiadomości');
});

await sprawdz('sukces bez JS: 303 → /dziekujemy', async () => {
  const odp = await worker.fetch(zadanie({}, { json: false }), env());
  rowne(odp.status, 303, 'status');
  rowne(odp.headers.get('Location'), `${ORIGIN}/dziekujemy`, 'Location');
});

await sprawdz('formularz bez JS (application/x-www-form-urlencoded, puste t): 303 → /dziekujemy', async () => {
  const body = new URLSearchParams({ imie: 'Anna', kontakt: '600100200', wiadomosc: 'Zapytanie', strona_www: '', t: '' });
  const req = new Request(URL_KONTAKT, { method: 'POST', headers: { Origin: ORIGIN,
    'Content-Type': 'application/x-www-form-urlencoded', Accept: 'text/html' }, body });
  const odp = await worker.fetch(req, env());
  rowne(odp.status, 303, 'status');
  rowne(odp.headers.get('Location'), `${ORIGIN}/dziekujemy`, 'Location');
  rowne(wyslane.length, 1, 'wysłano');
});

await sprawdz('telefon zamiast e-maila: bez Reply-To, numer w treści', async () => {
  const odp = await worker.fetch(zadanie({ kontakt: '600 100 200' }), env());
  rowne(odp.status, 200, 'status');
  const list = JSON.parse(wyslane[0].opcje.body);
  rowne('reply_to' in list, false, 'brak reply_to');
  rowne(list.text.includes('600 100 200'), true, 'telefon w treści');
});

await sprawdz('HTML w treści jest escapowany w wersji HTML wiadomości', async () => {
  await worker.fetch(zadanie({ wiadomosc: '<script>alert(1)</script>' }), env());
  const list = JSON.parse(wyslane[0].opcje.body);
  rowne(list.html.includes('<script>'), false, 'brak surowego <script>');
  rowne(list.html.includes('&lt;script&gt;'), true, 'escapowane');
});

await sprawdz('nowa linia w imieniu nie psuje tematu', async () => {
  await worker.fetch(zadanie({ imie: 'Jan\r\nBcc: x@y.pl' }), env());
  const list = JSON.parse(wyslane[0].opcje.body);
  rowne(/[\r\n]/.test(list.subject), false, 'temat w jednej linii');
});

await sprawdz('bez NADAWCA: adres testowy Resend', async () => {
  await worker.fetch(zadanie(), env({ NADAWCA: undefined }));
  rowne(JSON.parse(wyslane[0].opcje.body).from, 'Formularz www.firma-testowa.pl <onboarding@resend.dev>', 'nadawca');
});

await sprawdz('obcy Origin: 403', async () => {
  const odp = await worker.fetch(zadanie({}, { origin: 'https://obca.pl' }), env());
  rowne(odp.status, 403, 'status');
  rowne((await json(odp)).blad, 'origin', 'kod');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('brak Origin, ale Sec-Fetch-Site: same-origin — przechodzi', async () => {
  const odp = await worker.fetch(zadanie({}, { origin: null, fetchSite: 'same-origin' }), env());
  rowne(odp.status, 200, 'status');
});

await sprawdz('brak Origin i Sec-Fetch-Site (nie przeglądarka na naszej stronie): 403', async () => {
  const odp = await worker.fetch(zadanie({}, { origin: null }), env());
  rowne(odp.status, 403, 'status');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('brak Origin, Sec-Fetch-Site: cross-site: 403', async () => {
  const odp = await worker.fetch(zadanie({}, { origin: null, fetchSite: 'cross-site' }), env());
  rowne(odp.status, 403, 'status');
});

await sprawdz('Origin bez www przy adresie z www (i odwrotnie) — przechodzi', async () => {
  rowne((await worker.fetch(zadanie({}, { origin: 'https://firma-testowa.pl' }), env())).status, 200, 'bez www → www');
  const req = zadanie({}, { origin: ORIGIN, url: 'https://firma-testowa.pl/api/kontakt' });
  rowne((await worker.fetch(req, env())).status, 200, 'www → bez www');
  rowne((await worker.fetch(zadanie({}, { origin: 'https://www.firma-testowa.pl.obca.pl' }), env())).status, 403, 'podszycie');
});

await sprawdz('Content-Length > 16 KB: 413 za_duze, bez czytania treści', async () => {
  const odp = await worker.fetch(zadanie({}, { naglowki: { 'Content-Length': '20000' } }), env());
  rowne(odp.status, 413, 'status');
  rowne((await json(odp)).blad, 'za_duze', 'kod');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('e-mail z przecinkiem w części lokalnej nie jest adresem (nie trafi do Reply-To): 422', async () => {
  const odp = await worker.fetch(zadanie({ kontakt: 'a,evil@x.pl' }), env());
  rowne(odp.status, 422, 'status');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('separator U+2028 i znaki sterujące w imieniu nie psują tematu', async () => {
  await worker.fetch(zadanie({ imie: 'Jan\u2028Bcc: x@y.pl\u0085\x07' }), env());
  const list = JSON.parse(wyslane[0].opcje.body);
  rowne(/[\r\n\u0085\u2028\u2029\x00-\x1f]/.test(list.subject), false, 'temat w jednej linii');
});

await sprawdz('brak klucza Resend: 503 {"blad":"nie_skonfigurowano"} z nazwami braków', async () => {
  const odp = await worker.fetch(zadanie(), env({ RESEND_API_KEY: '' }));
  rowne(odp.status, 503, 'status');
  const d = await json(odp);
  rowne(d.blad, 'nie_skonfigurowano', 'kod');
  rowne(d.brakuje.join(','), 'RESEND_API_KEY', 'brakuje');
});

await sprawdz('brak ADRESAT: 503', async () => {
  const odp = await worker.fetch(zadanie(), env({ ADRESAT: undefined }));
  rowne(odp.status, 503, 'status');
});

await sprawdz('brak klucza bez JS: 303 → /blad-konfiguracja?powod=nie_skonfigurowano', async () => {
  const odp = await worker.fetch(zadanie({}, { json: false }), env({ RESEND_API_KEY: '' }));
  rowne(odp.status, 303, 'status');
  rowne(odp.headers.get('Location'), `${ORIGIN}/blad-konfiguracja?powod=nie_skonfigurowano`, 'Location');
});

await sprawdz('limit z IP: 429 z komunikatem, klucz = adres IP', async () => {
  let klucz;
  const odp = await worker.fetch(zadanie(), env({ LIMIT_KONTAKT: { limit: async (o) => { klucz = o.key; return { success: false }; } } }));
  rowne(odp.status, 429, 'status');
  rowne(klucz, '203.0.113.7', 'klucz limitu');
  rowne(typeof (await json(odp)).komunikat, 'string', 'komunikat');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('pole-pułapka wypełnione: udawany sukces, bez wysyłki', async () => {
  const odp = await worker.fetch(zadanie({ strona_www: 'http://spam.example' }), env());
  rowne(odp.status, 200, 'status');
  rowne((await json(odp)).ok, true, 'ok');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('wysłane po < 3 s: udawany sukces, bez wysyłki', async () => {
  const odp = await worker.fetch(zadanie({ t: '1000' }), env());
  rowne(odp.status, 200, 'status');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('ujemny czas (dziwna przeglądarka) albo znacznik czasu ze starego skryptu: wysyłamy', async () => {
  await worker.fetch(zadanie({ t: '-5000' }), env());
  rowne(wyslane.length, 1, 'ujemny — wysłano');
  wyslane = [];
  await worker.fetch(zadanie({ t: String(Date.now() + 3_600_000) }), env());
  rowne(wyslane.length, 1, 'zegar z przyszłości — wysłano');
});

await sprawdz('t nie jest liczbą: udawany sukces', async () => {
  await worker.fetch(zadanie({ t: 'abc' }), env());
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('puste t (bez JS): nie odrzucamy za czas', async () => {
  const odp = await worker.fetch(zadanie({ t: '' }, { json: false }), env());
  rowne(odp.status, 303, 'status');
  rowne(odp.headers.get('Location'), `${ORIGIN}/dziekujemy`, 'Location');
  rowne(wyslane.length, 1, 'wysłano');
});

await sprawdz('więcej niż 5 linków: udawany sukces, bez wysyłki', async () => {
  const linki = Array.from({ length: 6 }, (_, i) => `https://spam${i}.example`).join(' ');
  const odp = await worker.fetch(zadanie({ wiadomosc: linki }), env());
  rowne(odp.status, 200, 'status');
  rowne(wyslane.length, 0, 'bez wysyłki');
});

await sprawdz('5 linków: wysyłamy', async () => {
  const linki = Array.from({ length: 5 }, (_, i) => `https://strona${i}.example`).join(' ');
  await worker.fetch(zadanie({ wiadomosc: linki }), env());
  rowne(wyslane.length, 1, 'wysłano');
});

await sprawdz('brak pola: 422 z listą pól', async () => {
  const odp = await worker.fetch(zadanie({ imie: '  ' }), env());
  rowne(odp.status, 422, 'status');
  const d = await json(odp);
  rowne(d.blad, 'brak_pol', 'kod');
  rowne(d.pola.join(','), 'imie', 'pola');
});

await sprawdz('brak pola bez JS: 303 → /blad-formularz?powod=brak_pol', async () => {
  const odp = await worker.fetch(zadanie({ wiadomosc: undefined }, { json: false }), env());
  rowne(odp.headers.get('Location'), `${ORIGIN}/blad-formularz?powod=brak_pol`, 'Location');
});

await sprawdz('kontakt bez telefonu i e-maila: 422', async () => {
  const odp = await worker.fetch(zadanie({ kontakt: 'nie podam' }), env());
  rowne(odp.status, 422, 'status');
  rowne((await json(odp)).blad, 'kontakt', 'kod');
});

await sprawdz('wiadomość > 3000 znaków: 422 za_dlugie', async () => {
  const odp = await worker.fetch(zadanie({ wiadomosc: 'a'.repeat(3001) }), env());
  rowne(odp.status, 422, 'status');
  rowne((await json(odp)).blad, 'za_dlugie', 'kod');
});

await sprawdz('imię > 120 znaków: 422 za_dlugie', async () => {
  const odp = await worker.fetch(zadanie({ imie: 'J'.repeat(121) }), env());
  rowne(odp.status, 422, 'status');
});

await sprawdz('treść, której nie da się odczytać: 400 zle_dane', async () => {
  const req = new Request(URL_KONTAKT, { method: 'POST', headers: { Origin: ORIGIN, Accept: 'application/json',
    'Content-Type': 'multipart/form-data; boundary=zly' }, body: 'to nie jest multipart' });
  const odp = await worker.fetch(req, env());
  rowne(odp.status, 400, 'status');
});

await sprawdz('Resend odpowiada 422: 502 wysylka', async () => {
  odpowiedzResend = () => new Response('{"message":"invalid from"}', { status: 422 });
  const odp = await worker.fetch(zadanie(), env());
  rowne(odp.status, 502, 'status');
  rowne((await json(odp)).blad, 'wysylka', 'kod');
});

await sprawdz('brak połączenia z Resend: 502, bez JS 303 → /blad?powod=wysylka', async () => {
  odpowiedzResend = () => { throw new Error('sieć'); };
  const odp = await worker.fetch(zadanie({}, { json: false }), env());
  rowne(odp.status, 303, 'status');
  rowne(odp.headers.get('Location'), `${ORIGIN}/blad?powod=wysylka`, 'Location');
});

await sprawdz('GET /api/kontakt: 405 z Allow: POST', async () => {
  const odp = await worker.fetch(zadanie({}, { metoda: 'GET' }), env());
  rowne(odp.status, 405, 'status');
  rowne(odp.headers.get('Allow'), 'POST', 'Allow');
});

await sprawdz('inny adres /api/*: 404', async () => {
  const odp = await worker.fetch(zadanie({}, { url: `${ORIGIN}/api/nic` }), env());
  rowne(odp.status, 404, 'status');
});

await sprawdz('adres spoza /api/: pliki strony (ASSETS)', async () => {
  const odp = await worker.fetch(new Request(`${ORIGIN}/kontakt`), env());
  rowne(await odp.text(), 'plik', 'treść z ASSETS');
});

await sprawdz('bez wiązania limitu (lokalnie): wysyłamy', async () => {
  const odp = await worker.fetch(zadanie(), env({ LIMIT_KONTAKT: undefined }));
  rowne(odp.status, 200, 'status');
  rowne(wyslane.length, 1, 'wysłano');
});

await sprawdz('scheduled bez DEPLOY_HOOK_URL: nic nie wysyła', async () => {
  const w = await worker.scheduled({ cron: '17 2 * * *' }, env(), { waitUntil() {} });
  rowne(w.powod, 'brak_hooka', 'powód');
  rowne(wyslane.length, 0, 'bez zapytań');
});

await sprawdz('scheduled z DEPLOY_HOOK_URL: POST na hook, waitUntil', async () => {
  const hook = 'https://api.cloudflare.com/client/v4/workers/builds/deploy_hooks/abc';
  let czekano = false;
  const w = await worker.scheduled({ cron: '17 2 * * *' }, env({ DEPLOY_HOOK_URL: hook }), { waitUntil() { czekano = true; } });
  rowne(w.ok, true, 'ok');
  rowne(czekano, true, 'waitUntil');
  rowne(wyslane[0].url, hook, 'adres');
  rowne(wyslane[0].opcje.method, 'POST', 'metoda');
});

await sprawdz('scheduled: hook odpowiada błędem albo nie odpowiada — bez wyjątku', async () => {
  const hook = 'https://api.cloudflare.com/client/v4/workers/builds/deploy_hooks/abc';
  odpowiedzResend = () => new Response('nie', { status: 500 });
  rowne((await worker.scheduled({}, env({ DEPLOY_HOOK_URL: hook }), {})).ok, false, 'ok przy 500');
  odpowiedzResend = () => { throw new Error('sieć'); };
  rowne((await worker.scheduled({}, env({ DEPLOY_HOOK_URL: hook }), {})).powod, 'polaczenie', 'brak połączenia');
});

await sprawdz('scheduled: adres http:// odrzucony', async () => {
  const w = await worker.scheduled({}, env({ DEPLOY_HOOK_URL: 'http://przyklad.pl/hook' }), {});
  rowne(w.powod, 'zly_adres', 'powód');
  rowne(wyslane.length, 0, 'bez zapytań');
});

console.log = cicho;
console.log(wynik ? '\nSą błędy.' : '\nWszystkie testy Workera przeszły.');
process.exit(wynik);
