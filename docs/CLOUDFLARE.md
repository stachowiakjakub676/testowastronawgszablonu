# Publikacja na Cloudflare — krok po kroku

Stan na: wrzesień 2026 (nazwy przycisków w panelu Cloudflare zmieniają się co kilka miesięcy — jeśli czegoś nie ma
pod podaną nazwą, szukaj w tym samym dziale).

Jak to działa:

```
push do GitHuba → Cloudflare Workers Builds: python3 tools/build.py --produkcja → dist/
               → wdrożenie: pliki z dist/ (z _headers i _redirects) + Worker tylko dla /api/* (worker/index.js)
co noc 2:17 UTC → Worker wywołuje Deploy Hook → ten sam build od nowa (aktualne daty na stronie)
```

Na serwer trafia wyłącznie `dist/`. `src/`, `tools/`, `data/`, `docs/` zostają w repozytorium.
Konfiguracja wdrożenia jest w `wrangler.jsonc` — w panelu nie trzeba jej powtarzać.

---

## 1. Przed pierwszym wdrożeniem (w repozytorium)

1. W `wrangler.jsonc` zmień `"name": "strona-firmy"` na krótką nazwę strony (małe litery, cyfry, myślniki,
   np. `bimex`). To będzie nazwa Workera i część adresu roboczego `bimex.<konto>.workers.dev`.
2. `ratelimits` → `namespace_id`: każda strona na koncie Cloudflare musi mieć inną liczbę, inaczej strony dzielą limit
   5 wiadomości na minutę. `python3 tools/start.py` losuje ją przy nowym kliencie; przy formularzu przez Workera
   `--produkcja` nie przejdzie, dopóki zostaje wartość z szablonu `"1101"`.
3. `python3 tools/build.py --produkcja` musi przejść lokalnie bez błędów — ten sam build uruchomi Cloudflare.

## 2. Worker z repozytorium GitHub (Workers Builds)

1. <https://dash.cloudflare.com> → **Workers & Pages** → **Create** → **Import a repository** (zakładka Workers).
2. Połącz konto GitHub (**Connect GitHub**) i wybierz repozytorium strony.
3. Ustawienia builda:
   | Pole | Wartość |
   |---|---|
   | Project name | ta sama nazwa co `name` w `wrangler.jsonc` |
   | Build command | *(puste — bierze się z `wrangler.jsonc`: `python3 tools/build.py --produkcja`)* |
   | Deploy command | `npx wrangler deploy` (domyślne) |
   | Root directory | `/` |
   | Production branch | gałąź, z której publikujemy (np. `main`) |
4. **Deploy**. Po 1–2 minutach strona działa pod `https://<nazwa>.<konto>.workers.dev`.
   Ten adres ma nagłówek `X-Robots-Tag: noindex` (plik `_headers`) — wyszukiwarki go nie pokażą.
5. Build nie przeszedł? **Workers & Pages → <nazwa> → Deployments → View build log**. Komunikaty buildu są po polsku,
   z plikiem, polem i sposobem naprawy. Najczęściej: ostrzeżenie, które w `--produkcja` jest błędem (np. za duży CSS,
   za długi tytuł) albo `"przyklad": true` w `data/firma.json`.

Każdy kolejny push do gałęzi produkcyjnej wdraża stronę sam. Pushe do innych gałęzi tworzą wersje podglądu
(adres `<wersja>-<nazwa>.<konto>.workers.dev`, też z `noindex`).

## 3. Własna domena i przekierowanie www

Domena musi mieć DNS w Cloudflare (**Add a domain** → plan Free → zmiana serwerów nazw u rejestratora domeny,
np. w home.pl / OVH / nazwa.pl; propagacja do 24 godzin).

1. **Workers & Pages → <nazwa> → Settings → Domains & Routes → Add → Custom domain**: wpisz domenę główną z `firma.domena`
   (np. `www.bimex-rogozno.pl` albo `bimex-rogozno.pl` — dokładnie tę, która jest w `data/firma.json`). Cloudflare sam
   doda rekord DNS i certyfikat.
2. Drugi wariant adresu (z `www` albo bez) **musi** przekierowywać na główny (jeden adres w Google, jeden Origin
   formularza; Worker przyjmuje oba warianty tylko po to, żeby formularz nie kończył się błędem 403):
   - **DNS → Records → Add record**: typ `A`, nazwa `www` (albo `@`), adres `192.0.2.1`, **Proxy status: Proxied**
     (pomarańczowa chmurka). Adres jest umowny — ruch i tak zatrzyma reguła poniżej, ale rekord musi istnieć.
   - **Rules → Redirect Rules → Create rule** → szablon **Redirect from WWW to root** (albo odwrotnie):
     *If* hostname equals `www.domena.pl` → *Then* Dynamic, `concat("https://domena.pl", http.request.uri.path)`,
     kod **301**, **Preserve query string** zaznaczone.
   - Reguła działa przed Workerem, więc formularz (sprawdzenie nagłówka Origin) widzi zawsze główny adres.
3. Przekierowania starych podstron (np. `/oferta.php` z poprzedniej strony) wpisz w `data/firma.json` →
   `przekierowania` (`[{"z": "/oferta.php", "do": "/oferta"}]`). Build zapisze je w `dist/_redirects` (kod 301).
   Tam działają tylko ścieżki na tej samej domenie — przekierowania całych domen robi się regułami jak wyżej.
4. Jeśli strona była wcześniej pod adresem roboczym i ktoś go podlinkował, nic nie trzeba robić — `noindex` zostaje.

## 4. Ustawienia strefy (domeny) — lista kontrolna

Plik `_headers` ustawia ścisłą politykę CSP: skrypty tylko z własnego serwera. Funkcje Cloudflare, które same
wstrzykują skrypty do strony, łamią ją (błędy w konsoli, zepsute elementy) — dlatego muszą być wyłączone.

| Gdzie w panelu (strefa domeny) | Ustawienie | Dlaczego |
|---|---|---|
| Security → Bots → **Bot Fight Mode** | **wyłączone** | wstrzykuje skrypt JS na strony (CSP go blokuje), ustawia ciasteczko `__cf_bm` i potrafi zablokować formularz; ochronę formularza robi Worker (pułapka, czas, limit z IP) |
| Security → WAF / Security Settings → **Under Attack Mode**, reguły z akcją **Managed Challenge / JS Challenge**, **Security Level: I'm Under Attack** | **nie włączaj** | wyzwanie ustawia ciasteczko `cf_clearance` (i `__cf_bm`), a polityka prywatności mówi, że strona nie używa cookies. Jeśli atak wymusi włączenie, dopisz w polityce zdanie o niezbędnym ciasteczku bezpieczeństwa (wyjątek dla plików niezbędnych z art. 399 Prawa komunikacji elektronicznej — bez banera) i wyłącz po ataku |
| Scrape Shield → **Email Address Obfuscation** | **wyłączone** | podmienia adresy e-mail na skrypt `email-decode.min.js` — link `mailto:` przestaje działać bez JS i łamie CSP |
| Speed → Optimization → **Rocket Loader** | **wyłączone** | przepisuje znaczniki `<script>`; łamie CSP i kolejność skryptów |
| Web Analytics → strona → **Manage site** | **Enable with JS Snippet installation** albo **Disable** — nigdy automatyczne | automatyczne wstrzykiwanie dodaje skrypt, którego CSP nie zna. Statystyki włączamy w danych: `funkcje.statystyki_cf_token` (build sam doda skrypt i wpisze go do CSP i polityki prywatności) |
| SSL/TLS → Overview | **Full (strict)** | szyfrowanie do końca |
| SSL/TLS → Edge Certificates → **Always Use HTTPS** | **włączone** | wejście przez `http://` przechodzi na `https://` |
| SSL/TLS → Edge Certificates → **HSTS** | **nie włączaj tutaj** | nagłówek HSTS ustawia już `_headers` (`funkcje.hsts_subdomeny`, `hsts_preload`) — dwa źródła = dwie różne wartości |
| SSL/TLS → Edge Certificates → Minimum TLS Version | **TLS 1.2** | starsze wersje są niebezpieczne |
| DNS → Settings → **DNSSEC** | **Enable DNSSEC**, potem rekord DS u rejestratora | chroni przed podszyciem się pod domenę |
| DNS → Records → **CAA** | jeden rekord `0 iodef "mailto:<e-mail firmy>"` (typ CAA, nazwa `@`) | gdy w strefie jest choć jeden rekord CAA, Cloudflare sam dopisuje urzędy, z których wystawia certyfikaty (Let's Encrypt, Google Trust Services, SSL.com, Sectigo) — inne urzędy nie wystawią certyfikatu dla domeny. Nie dopisuj ręcznie `issue` dla jednego urzędu: zablokujesz odnowienie. Dodatkowo: SSL/TLS → Edge Certificates → **Certificate Transparency Monitoring** włączone |
| Caching → Configuration → Browser Cache TTL | **Respect Existing Headers** | pamięć podręczną ustawia `_headers` (`/assets/*` na rok, strony zawsze świeże) |
| Speed → Optimization → Auto Minify / Early Hints | bez zmian (Minify zostało wycofane) | — |

Poczta firmy (MX) i rekordy dla formularza (SPF, DKIM, DMARC) — zob. `docs/FORMULARZ.md`, rozdział 3.
Rekordy poczty zawsze **DNS only** (szara chmurka).

## 5. Sekrety i zmienne

**Workers & Pages → <nazwa> → Settings → Variables and Secrets → Add**. Sekretów nie ma w repozytorium;
`keep_vars: true` w `wrangler.jsonc` sprawia, że wdrożenie ich nie kasuje.

| Nazwa | Typ | Po co | Bez niej |
|---|---|---|---|
| `RESEND_API_KEY` | Secret | wysyłka formularza przez Resend | formularz odpowiada 503, strona otwiera program pocztowy z gotową wiadomością |
| `ADRESAT` | Text | adres, na który przychodzą zapytania (kilka: po przecinku) | jak wyżej |
| `NADAWCA` | Text | nadawca, np. `Bimex – formularz <formularz@send.domena.pl>` (domena zweryfikowana w Resend) | wysyłka z adresu testowego Resend — dochodzi tylko na adres właściciela konta Resend |
| `DEPLOY_HOOK_URL` | Secret | nocny build (rozdział 6) | daty na stronie odświeżają się tylko przy pushu |

Zmienne działają od razu po **Deploy** w tym oknie — bez ponownego budowania strony.

## 6. Nocny build (Deploy Hook + cron)

Strona jest statyczna, a część treści zależy od dnia: ogłoszenia z datą „do”, godziny w święta, rok w stopce,
data ważności w `security.txt`. Dlatego raz na dobę budujemy ją od nowa.

1. **Workers & Pages → <nazwa> → Settings → Builds → Deploy Hooks → Create**: nazwa `nocny build`,
   gałąź produkcyjna → **Create**. Skopiuj adres (`https://api.cloudflare.com/client/v4/workers/builds/deploy_hooks/…`).
2. Dodaj go jako sekret `DEPLOY_HOOK_URL` (rozdział 5). Adres działa bez hasła — kto go zna, może uruchomić build,
   dlatego tylko jako sekret.
3. Harmonogram jest w `wrangler.jsonc` → `triggers.crons`: `"17 2 * * *"` — codziennie o 2:17 **UTC**
   (4:17 latem, 3:17 zimą w Polsce). Widać go w **Settings → Trigger Events**.
4. Sprawdzenie: **Settings → Trigger Events → cron → Test** (albo poczekaj do rana) → w **Deployments** pojawia się
   nowy build. Błędy wywołania są w **Observability → Logs** (wpis „Nocny build: …”).

Dziennik Workera (`observability` w `wrangler.jsonc`): tylko wiersze, które Worker sam wypisuje (kody błędów wysyłki
i nocnego buildu, bez treści wiadomości i adresów IP), przechowywane 3 dni (7 dni w planie płatnym). Dziennik wywołań
(`invocation_logs` — adres, metoda i nagłówki każdego zapytania) jest wyłączony, bo polityka prywatności mówi, że
nie prowadzimy dzienników odwiedzin. Nie włączaj go w panelu (**Settings → Observability**).

Nieudany nocny build nie psuje strony — zostaje poprzednia wersja, a log pokazuje, co poprawić.

## 7. Po wdrożeniu — sprawdź

- `https://domena.pl`, `https://www.domena.pl` i `http://domena.pl` kończą się na jednym adresie `https://…` (301).
- Konsola przeglądarki (F12) na stronie głównej i kontakcie: **zero** błędów CSP.
- <https://securityheaders.com> — ocena A albo A+.
- Formularz: wyślij próbną wiadomość (`docs/FORMULARZ.md`, rozdział 5).
- Google Search Console: dodaj domenę (rekord TXT w DNS), wyślij `https://domena.pl/sitemap.xml`.

## 8. Panel do samodzielnej edycji (opcjonalnie)

Szablon nie ma panelu CMS — dane są w `data/*.json` i zmienia je programista albo AI. Jeśli klient ma sam dodawać
np. aktualności, gotowe i sprawdzone rozwiązanie jest w repozytorium **Sofastyl**: Decap CMS pod `/admin`
(`admin/index.html`, `admin/config.yml`), logowanie login + hasło przez Workera (`worker/admin-auth.js`: PBKDF2,
podpisana sesja, limit 10 prób na minutę) i instrukcja `docs/PANEL.md`. Żeby to przenieść:

1. skopiuj `admin/` i `worker/admin-auth.js`, w `worker/index.js` dodaj trasy `/api/auth*` i `/api/github/*`
   (wzór: `sofastyl/worker/index.js`);
2. w `wrangler.jsonc` dodaj limit `LOGIN_LIMIT` (`ratelimits`, 10 na 60 s);
3. w `admin/config.yml` ustaw repozytorium i gałąź produkcyjną; kolekcje wskaż na pliki `data/`;
4. sekrety `GITHUB_TOKEN` i `ADMIN_USERS` jak w `sofastyl/docs/PANEL.md`;
5. CSP dla `/admin/*` musi dopuścić skrypty panelu — w `tools/silnik/naglowki.py` dodaj osobny blok `/admin/*`
   (reguła `noindex` dla `/admin/*` już jest).
