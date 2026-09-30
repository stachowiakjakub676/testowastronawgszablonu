/**
 * Worker strony (Cloudflare Workers + pliki statyczne z dist/) — KONTRAKT §12, §13.
 *
 * Pliki strony serwuje Cloudflare bezpośrednio; Worker uruchamia się tylko dla /api/* (run_worker_first
 * w wrangler.jsonc). Kod przeniesiony z worker/contact.js stron Sofastyl i JSoft (działa tam produkcyjnie),
 * z polami formularza szablonu: imie, kontakt, wiadomosc, strona_www (pułapka), t (ile ms formularz był otwarty).
 *
 *   POST /api/kontakt  — wiadomość z formularza → e-mail do firmy przez Resend (https://resend.com)
 *   scheduled()        — nocny build przez Deploy Hook Workers Builds (aktualne daty: ogłoszenia, święta, © rok)
 *
 * Ustawienia (Workers & Pages → <worker> → Settings → Variables and Secrets), opis: docs/FORMULARZ.md:
 *   RESEND_API_KEY   (sekret)  — klucz API z Resend; bez niego 503 {"blad":"nie_skonfigurowano"} → strona otwiera mailto:
 *   ADRESAT          (zmienna) — adres, na który przychodzą wiadomości (kilka: po przecinku)
 *   NADAWCA          (zmienna, opcjonalnie) — np. „Bimex – formularz <formularz@send.bimex-rogozno.pl>”;
 *                    domena zweryfikowana w Resend. Bez niej adres testowy Resend (dostarcza tylko do właściciela konta).
 *   DEPLOY_HOOK_URL  (sekret, opcjonalnie) — adres Deploy Hook z Settings → Builds → Deploy Hooks (docs/CLOUDFLARE.md)
 *   LIMIT_KONTAKT    (wiązanie ratelimits w wrangler.jsonc) — 5 wiadomości na minutę z jednego adresu IP
 *
 * Odpowiedź: JSON, gdy nagłówek Accept zawiera application/json (wysyłka przez JS, assets/js/czesci/60-formularz.js);
 * inaczej 303 → /dziekujemy albo strona błędu z opisem, co zrobić (formularz bez JavaScriptu): /blad-formularz
 * (brakujące albo za długie pola), /blad-konfiguracja (wysyłka niewłączona — e-mail i telefon firmy), /blad (reszta);
 * zawsze z ?powod=<kod>.
 * JSON: sukces {"ok":true}; błąd {"ok":false,"blad":"<kod>","komunikat":"<zdanie dla odwiedzającego>"}.
 * Worker nie zapisuje treści wiadomości ani adresów IP — w dzienniku są tylko kody błędów wysyłki.
 */

const RESEND_URL = 'https://api.resend.com/emails';
const LIMITY = { imie: 120, kontakt: 160, wiadomosc: 3000 };
const MIN_CZAS_MS = 3000;
const MAX_LINKOW = 5;
// Content-Length większy niż to = nie nasz formularz (3 pola po ≤ 3000 zn. w UTF-8 mieszczą się z zapasem)
const MAX_BAJTOW = 16384;
// tylko zwykłe znaki w adresie: przecinek, średnik czy nawias w części przed @ zamieniłyby Reply-To w dwa adresy
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

const KOMUNIKATY = {
  origin: 'Formularz można wysłać tylko ze strony firmy.',
  nie_skonfigurowano: 'Wysyłka z formularza nie jest jeszcze włączona. Napisz e-mail albo zadzwoń.',
  limit: 'Wysłano kilka wiadomości w krótkim czasie. Spróbuj ponownie za minutę.',
  zle_dane: 'Nie udało się odczytać formularza. Odśwież stronę i spróbuj ponownie.',
  brak_pol: 'Uzupełnij imię, telefon lub e-mail i treść zapytania.',
  kontakt: 'Podaj telefon albo adres e-mail, żebyśmy mogli odpowiedzieć.',
  za_dlugie: 'Wiadomość jest za długa — skróć ją do 3000 znaków.',
  za_duze: 'Wiadomość jest za długa — skróć ją do 3000 znaków.',
  wysylka: 'Nie udało się wysłać wiadomości. Spróbuj ponownie za chwilę albo zadzwoń.',
  metoda: 'Formularz wysyła się metodą POST.',
  nie_ma: 'Nie ma takiego adresu.',
};
const STATUSY = { origin: 403, nie_skonfigurowano: 503, limit: 429, zle_dane: 400, brak_pol: 422, kontakt: 422,
  za_dlugie: 422, za_duze: 413, wysylka: 502, metoda: 405, nie_ma: 404 };

// strony błędów bez JS (src/strony/blad*.html) — odwiedzający od razu wie, co poprawić albo gdzie napisać
const STRONY_BLEDU = { brak_pol: '/blad-formularz', kontakt: '/blad-formularz', za_dlugie: '/blad-formularz',
  za_duze: '/blad-formularz', zle_dane: '/blad-formularz', nie_skonfigurowano: '/blad-konfiguracja' };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/api/kontakt' || url.pathname === '/api/kontakt/') {
      if (request.method !== 'POST') return blad(request, 'metoda', { Allow: 'POST' });
      return kontakt(request, env, url);
    }
    if (url.pathname.startsWith('/api/')) return blad(request, 'nie_ma');
    // tu trafia tylko wtedy, gdy run_worker_first obejmie coś więcej niż /api/* — oddajemy pliki strony
    return env.ASSETS ? env.ASSETS.fetch(request) : new Response('Nie ma takiego adresu.', { status: 404 });
  },

  // Cron z wrangler.jsonc ("17 2 * * *", czas UTC). Nowy build tej samej gałęzi — bez zmian w repozytorium.
  async scheduled(controller, env, ctx) {
    const hook = env.DEPLOY_HOOK_URL;
    if (!hook) {
      console.log('Nocny build: brak DEPLOY_HOOK_URL — pomijam (docs/CLOUDFLARE.md, „Nocny build”)');
      return { ok: false, powod: 'brak_hooka' };
    }
    if (!/^https:\/\//.test(hook)) {
      console.log('Nocny build: DEPLOY_HOOK_URL musi zaczynać się od https://');
      return { ok: false, powod: 'zly_adres' };
    }
    const zadanie = fetch(hook, { method: 'POST' })
      .then(async (odp) => {
        if (!odp.ok) console.log('Nocny build: Deploy Hook odpowiedział', odp.status, (await odp.text()).slice(0, 300));
        return { ok: odp.ok, status: odp.status };
      })
      .catch((e) => {
        console.log('Nocny build: brak połączenia z Deploy Hook', String(e && e.message));
        return { ok: false, powod: 'polaczenie' };
      });
    if (ctx && ctx.waitUntil) ctx.waitUntil(zadanie);
    return zadanie;
  },
};

// Adres strony i jego wariant z www / bez www — Redirect Rule (docs/CLOUDFLARE.md) kieruje ruch na jeden z nich,
// ale formularz otwarty tuż przed zmianą reguły albo z drugiego wariantu nie może kończyć się błędem 403.
function wlasneAdresy(url) {
  const host = url.host.startsWith('www.') ? url.host.slice(4) : url.host;
  return new Set([`${url.protocol}//${host}`, `${url.protocol}//www.${host}`]);
}

async function kontakt(request, env, url) {
  // tylko z własnej strony: przeglądarka wysyła Origin przy POST formularza; gdy go nie ma, wystarczy
  // Sec-Fetch-Site: same-origin. Bez obu nagłówków to nie jest przeglądarka na naszej stronie.
  const origin = request.headers.get('Origin');
  const fetchSite = request.headers.get('Sec-Fetch-Site');
  if (origin ? !wlasneAdresy(url).has(origin) : fetchSite !== 'same-origin') return blad(request, 'origin');

  // nazwy brakujących ustawień (bez wartości) — strona otwiera wtedy program pocztowy
  const brakuje = ['RESEND_API_KEY', 'ADRESAT'].filter((k) => !env[k]);
  if (brakuje.length) return blad(request, 'nie_skonfigurowano', {}, { brakuje });

  // za duże ciało odrzucamy, zanim Worker zacznie je czytać
  const dlugosc = Number(request.headers.get('Content-Length'));
  if (Number.isFinite(dlugosc) && dlugosc > MAX_BAJTOW) return blad(request, 'za_duze');

  if (env.LIMIT_KONTAKT) {
    const ip = request.headers.get('CF-Connecting-IP') || 'nieznany';
    const { success } = await env.LIMIT_KONTAKT.limit({ key: ip });
    if (!success) return blad(request, 'limit');
  }

  let form;
  try {
    form = await request.formData();
  } catch (e) {
    return blad(request, 'zle_dane');
  }
  const pole = (k) => String(form.get(k) ?? '').trim();

  // pułapki na boty: udajemy sukces, żeby bot nie próbował dalej
  if (pole('strona_www')) return sukces(request);
  // t = ile milisekund formularz był otwarty (performance.now() w przeglądarce, 60-formularz.js) — nie porównujemy
  // zegara odwiedzającego z zegarem serwera: przestawiony zegar w telefonie nie może zgubić wiadomości.
  // Bez JS pole jest puste — wtedy nie odrzucamy za czas; wartość ujemna (dziwna przeglądarka) też przechodzi.
  if (pole('t')) {
    const t = Number(pole('t'));
    if (!Number.isFinite(t) || (t >= 0 && t < MIN_CZAS_MS)) return sukces(request);   // „abc” wpisuje tylko bot
  }

  const d = { imie: pole('imie'), kontakt: pole('kontakt'), wiadomosc: pole('wiadomosc') };
  if (!d.imie || !d.kontakt || !d.wiadomosc) {
    return blad(request, 'brak_pol', {}, { pola: Object.keys(d).filter((k) => !d[k]) });
  }
  if (Object.keys(LIMITY).some((k) => d[k].length > LIMITY[k])) return blad(request, 'za_dlugie');
  const email = EMAIL_RE.test(d.kontakt) ? d.kontakt : null;
  if (!email && !/\d{3}/.test(d.kontakt)) return blad(request, 'kontakt');
  // typowy spam: sama lista linków
  if ((d.wiadomosc.match(/https?:\/\//gi) || []).length > MAX_LINKOW) return sukces(request);

  const wiersze = [
    ['Imię i nazwisko', d.imie],
    [email ? 'E-mail' : 'Telefon lub e-mail', d.kontakt],
    ['Zapoznanie z informacją o danych', form.get('zgoda') ? 'potwierdzone' : ''],
  ].filter(([, v]) => v);
  // temat w jednej linii: także separatory Unicode (U+2028/2029, U+0085) i znaki sterujące
  const jedenWiersz = (s) => s.replace(/[\r\n\u0085\u2028\u2029\x00-\x1f\x7f]+/g, ' ');
  const temat = jedenWiersz(`Zapytanie ze strony ${url.host} – ${d.imie}`).slice(0, 200);
  const stopka = email
    ? `Wysłano z formularza na stronie ${url.host}. Odpowiedz na tę wiadomość, aby napisać do nadawcy.`
    : `Wysłano z formularza na stronie ${url.host}. Nadawca podał telefon — oddzwoń na podany numer.`;
  const text = wiersze.map(([k, v]) => `${k}: ${v}`).join('\n') + '\n\nWiadomość:\n' + d.wiadomosc + '\n\n--\n' + stopka;
  const html = `<div style="font-family:Arial,sans-serif;font-size:15px;color:#1a1a1a;line-height:1.5">
<table cellpadding="6" style="border-collapse:collapse">${wiersze.map(([k, v]) =>
    `<tr><td style="color:#555;padding-right:16px;vertical-align:top">${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</table>
<p style="margin:20px 0 6px;color:#555">Wiadomość:</p>
<div style="white-space:pre-wrap;border-left:3px solid #999;padding-left:12px">${esc(d.wiadomosc)}</div>
<p style="margin-top:24px;font-size:13px;color:#666">${esc(stopka)}</p>
</div>`;

  const list = {
    from: env.NADAWCA || `Formularz ${url.host} <onboarding@resend.dev>`,
    to: env.ADRESAT.split(',').map((s) => s.trim()).filter(Boolean),
    subject: temat,
    text,
    html,
  };
  if (email) list.reply_to = email;

  let odp;
  try {
    odp = await fetch(env.RESEND_API_URL || RESEND_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(list),
    });
  } catch (e) {
    console.log('Resend: brak połączenia', String(e && e.message));
    return blad(request, 'wysylka');
  }
  if (!odp.ok) {
    // tylko status i początek odpowiedzi Resend — bez treści wiadomości i danych nadawcy
    console.log('Resend: błąd', odp.status, (await odp.text()).slice(0, 300));
    return blad(request, 'wysylka');
  }
  return sukces(request);
}

function chceJson(request) {
  return (request.headers.get('Accept') || '').includes('application/json');
}

function sukces(request) {
  if (chceJson(request)) return json({ ok: true }, 200);
  return przekieruj(request, '/dziekujemy');
}

function blad(request, kod, naglowki = {}, dodatkowe = {}) {
  if (chceJson(request)) {
    return json({ ok: false, blad: kod, komunikat: KOMUNIKATY[kod], ...dodatkowe }, STATUSY[kod], naglowki);
  }
  return przekieruj(request, `${STRONY_BLEDU[kod] || '/blad'}?powod=${encodeURIComponent(kod)}`);
}

function przekieruj(request, sciezka) {
  const cel = new URL(sciezka, new URL(request.url).origin);
  return new Response(null, { status: 303, headers: { Location: cel.toString(), ...NAGLOWKI } });
}

// _headers nie działa dla odpowiedzi Workera — nagłówki bezpieczeństwa ustawiamy tutaj
const NAGLOWKI = {
  'Cache-Control': 'no-store',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Robots-Tag': 'noindex',
};

function json(body, status = 200, naglowki = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...NAGLOWKI, ...naglowki },
  });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
