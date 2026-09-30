# Kontrakt silnika SZABLON

Ten plik ustala umowę między wszystkimi częściami szablonu: modelem danych, silnikiem szablonów, szablonami HTML,
CSS, JS, Workerem i narzędziami. Kto zmienia jedną część, sprawdza tutaj, czego oczekują pozostałe.
Jeśli kod i ten plik się rozjadą, poprawia się jedno albo drugie w tym samym commicie.

Źródła decyzji: `bimex/CLAUDE.md` (zasady domu), raporty z badania (strony flagowe, najlepsze strony MŚP,
czynniki wartości rynkowej, „AI slop”, repozytoria `sofastyl`, `jsoft`, `bimex`). Najważniejsze wartości są wpisane niżej —
nie trzeba sięgać do raportów.

---

## 1. Zasady nadrzędne

1. **Jedno źródło prawdy.** Wszystko, co zależy od firmy, pochodzi z `data/`. Szablony HTML nie zawierają żadnych
   danych firmy, tekstów marketingowych ani numerów telefonów.
2. **`null` ukrywa.** Pole `null` (albo pusta lista) = element lub sekcja nie powstaje. Build wypisuje
   `UKRYTO: sekcja „opinie” (brak danych: tresc.opinie)`. Nigdy nie wstawiamy tekstu zastępczego.
3. **Nie zgadujemy.** Ceny, godziny, lata, liczby, nazwy klientów, certyfikaty i opinie są albo ze źródła
   (`firma.zrodla`), albo `null`. Niepewne trafiają do `firma.do_potwierdzenia`.
4. **Twarde błędy zamiast cichych usterek.** Pozostałości `{{`, `{%`, `{#`, `[UZUPEŁNIJ`, `TODO`, `Lorem`, `XXX`
   w `dist/` przerywają build. Komunikaty po polsku, z plikiem, polem i sposobem naprawy.
5. **Silnik osobno, klient osobno.** Klient (i AI, która personalizuje) zmienia pliki klienta. Pliki silnika zmienia się
   tylko w repozytorium SZABLON (wtedy trafiają do wszystkich przyszłych stron).
6. **Bez zależności w buildzie.** `tools/build.py` i `tools/silnik/*` — tylko biblioteka standardowa Pythona ≥ 3.10.
   Pillow (`tools/zdjecia.py`) i fontTools (`tools/fonty.py`) są potrzebne tylko lokalnie, przy przygotowaniu plików,
   które się commituje.
7. **Po polsku:** treść, komentarze w kodzie, komunikaty, dokumentacja, commity. Nazwy klas CSS i identyfikatory w JS
   mogą być angielskie (krótkie, jak w `sofastyl`/`bimex`); klucze danych i zmienne szablonów — po polsku.

---

## 2. Struktura repozytorium i właściciel plików

```
SZABLON/
├── AGENTS.md  CLAUDE.md  README.md  CHANGELOG.md  SZABLON_WERSJA         [silnik]
├── .htmlvalidate.json   konfiguracja html-validate dla tools/sprawdz.sh      [silnik]
├── .claude/settings.json, .claude/hooks/*.py, .claude/skills/personalizuj/SKILL.md, .gemini/settings.json [silnik]
├── brief/            BRIEF.md (kwestionariusz), zrodla.md, zdjecia/ (oryginały, poza gitem) [klient]
├── data/             firma.json, tresc.json, zdjecia.json, tresc/*.md, aktualnosci/*.md    [klient]
├── assets/
│   ├── css/czesci/*.css      style silnika, sklejane przez build w jeden plik          [silnik]
│   ├── css/wlasne.css        style tylko tego klienta (element-podpis, drobne różnice)   [klient]
│   ├── js/czesci/*.js        skrypty silnika, sklejane w jeden plik                    [silnik]
│   ├── fonts/<krój>/         woff2 łacina+PL, OFL.txt; fonts/fonty.json = katalog krojów [silnik]
│   └── img/                  logo, ikony/, foto/ (wyjście tools/zdjecia.py), pliki/ (PDF) [klient]
├── src/
│   ├── uklad.html            szkielet każdej strony (head, nagłówek, main, stopka)     [silnik]
│   ├── czesci/*.html         nagłówek, stopka, pasek-mobilny, okruszki, formularz…     [silnik]
│   ├── sekcje/*.html         jedna sekcja = jeden plik                                  [silnik]
│   └── strony/*.html         szablony podstron                                           [silnik]
├── tools/
│   ├── build.py              wejście: walidacja → render → kontrole → dist/            [silnik]
│   ├── silnik/*.py           moduły buildu (patrz §9)                                    [silnik]
│   ├── schemat/*.schema.json JSON Schema dla data/*.json                                 [silnik]
│   ├── presety/*.json        reguły branż                                                [silnik]
│   ├── start.py  zdjecia.py  fonty.py  kolory.py  lint_slop.py  swieta.py
│   ├── podglad.py  sprawdz.sh  zrzuty.cjs  raport.py  co_zawiera.py  aktualizuj.py       [silnik]
├── worker/index.js, wrangler.jsonc, tools/test_worker.mjs (test Workera, node)           [silnik]
├── docs/                     KONTRAKT.md, CLOUDFLARE.md, FORMULARZ.md, PROCEDURA.md, CO-ZAWIERA-STRONA.md, … [silnik]
└── przyklady/<nazwa>/        pełny „katalog klienta” (data/, assets/img/, brief/) do testów [silnik]
```

`dist/` i `raport/` są w `.gitignore` — build uruchamia Cloudflare (`python3 tools/build.py --produkcja`).
Na serwer trafia wyłącznie `dist/` (bez pliku-znacznika `.szablon-wynik`, który wyklucza `dist/.assetsignore`).

**Katalog klienta.** Build czyta dane klienta z katalogu podanego w `--klient` (domyślnie `.`, czyli korzeń repozytorium):
`<klient>/data/`, `<klient>/assets/img/`, `<klient>/assets/css/wlasne.css`, `<klient>/brief/`.
Pliki silnika zawsze z korzenia repozytorium. Dzięki temu `przyklady/bimex` buduje się tym samym silnikiem:
`python3 tools/build.py --klient przyklady/bimex`.

---

## 3. Silnik szablonów (`tools/silnik/szablony.py`)

Składnia jest mała i zamknięta. Wszystko, czego nie rozpoznaje, jest błędem.

| Składnia | Znaczenie |
|---|---|
| `{{ sciezka }}` | wartość z kontekstu, **escapowana HTML + polska typografia** (§3.2) |
| `{{ sciezka \| filtr }}`, `{{ x \| filtr:"arg" }}`, łańcuch `{{ x \| a \| b }}` | filtry (§3.1) |
| `{% if wyr %} … {% elif wyr %} … {% else %} … {% endif %}` | warunek |
| `{% for x in wyr %} … {% else %} … {% endfor %}` | pętla; `{% else %}` gdy pusto; zmienne `petla.indeks` (od 1), `petla.indeks0`, `petla.pierwszy`, `petla.ostatni`, `petla.dlugosc` |
| `{% set nazwa = wyr %}` | zmienna lokalna (do końca bieżącego pliku/bloku) |
| `{% include "czesci/x.html" %}`, `{% include "sekcje/x.html" tryb="skrot" limit=6 %}` | wstawienie pliku z `src/`, z dodatkowymi zmiennymi |
| `{% sekcje %}` | (tylko w `strony/index.html`) wstawia sekcje strony głównej w kolejności z presetu (§6) |
| `{# komentarz #}` | usuwany z wyniku |

**Ścieżki:** `firma.kontakt.telefon`, `tresc.oferta.pozycje`, indeksy `lista.0.nazwa`. Brak klucza albo `null` → wartość
pusta (fałsz w `if`, pusty ciąg w `{{ }}`), **ale** w `{{ }}` brak wartości w trybie `--produkcja` jest błędem, chyba że
użyto filtra `domyslnie`. Dzięki temu literówka w nazwie pola nie przechodzi po cichu.

**Wyrażenia** (`if`, `for`, `set`): ścieżka, literał (`"tekst"`, `12`, `true`, `false`, `null`), filtry, porównania
`== != < > <= >=`, `in`, `not in`, `and`, `or`, `not`, nawiasy. Prawda = nie `null`, nie `false`, nie `0`, nie `""`, nie pusta lista/słownik.
Argument filtra może być literałem albo ścieżką (`{{ x | domyslnie:firma.firma.nazwa }}`).

**Literały i zamknięcia:** literał w cudzysłowie może zawierać `}}` i `%}` (`{{ "a}}b" }}`). `{{`, `{%` albo `{#` bez
zamknięcia jest błędem już przy renderze (także w `--szybko`), z numerem wiersza.

**Białe znaki:** wiersz, w którym stoi tylko znacznik `{% … %}` albo `{# … #}`, znika w całości (z wcięciem i końcem
wiersza) — w wyniku nie ma pustych linii po warunkach i pętlach.

**Nagłówki plików** (pierwszy znacznik pliku): `{# wymaga: … #}` w sekcjach i częściach, `{# strona: klucz="wartość" … #}`
w stronach (§6.1). Ścieżki w `wymaga:` są ścieżkami kontekstu szablonu (`tresc.oferta.pozycje`, `firma.godziny`,
`firma.kontakt.adres`); `a|b` = jedna z, przecinek = wszystkie. Wartości w nagłówku strony mogą zawierać `{{ }}` i `{% if %}`.

**Zmienne sekcji** (ustawiane przy `{% sekcje %}` i przy `{% include "sekcje/…" %}`): `tryb` (`"skrot"` / `"pelny"`),
`limit` (z presetu `limity`), `bez_naglowka`, `hn` — poziom nagłówków wewnątrz sekcji (3 pod h2 sekcji, 2 gdy
`bez_naglowka=true`, bo wtedy tytułem jest h1 podstrony) oraz `sekcja` = `{id, html_id, naglowek, dane, strona}`
(`naglowek`: z `tresc.<id>.naglowek` albo domyślny z presetu; `strona`: ścieżka podstrony z pełną wersją albo `null`).

### 3.1 Filtry

| Filtr | Wynik |
|---|---|
| `surowe` | bez escapowania i bez typografii (tylko dla HTML wygenerowanego przez silnik) |
| `tel` | `+48672683408` → `+48 67 268 34 08` (twarde spacje); `tel:"krajowy"` → `67 268 34 08` (przyciski, tabele) |
| `tel_href` | `tel:+48672683408` |
| `cena` | `1250` → `1 250 zł`; `{"od":32,"do":46}` → `32–46 zł`; `12.5` → `12,50 zł` (grosze zawsze dwiema cyframi) |
| `data` / `data_krotka` / `data_iso` | `29 września 2026` / `29.09.2026` / `2026-09-29` |
| `md` | podzbiór Markdown → HTML (akapity, `##`/`###` → h2/h3 **o poziom niżej niż kontekst ustawi `md:3`**, listy, **pogrubienie**, *kursywa*, linki http(s)/mailto/tel/względne); HTML w źródle jest escapowany |
| `md_plik` | jak `md`, ale argumentem jest ścieżka `data/tresc/x.md` |
| `md_plik_poczatek` | pierwszy akapit pliku `.md` (bez nagłówków i list) — skrót na głównej, gdy cały tekst jest na podstronie |
| `json` | JSON bezpieczny do `<script>`: każde `<` jako `\u003c` (ani `</script>`, ani `<!--` z danych nie zmienią parsowania strony) |
| `url` | ścieżka strony → link (`/kontakt`; w trybie `--plik` → względny `kontakt.html`); adres pełny (`https://…`, `mailto:`, `tel:`) bez zmian i **bez typografii**. Każdy adres z danych w `href`/`src`/`content` wypisujemy przez `url` |
| `mailto` | `biuro@firma.pl` → `mailto:biuro@firma.pl` (do `href`) |
| `zasob` | ścieżka pliku z `assets/` → URL z `?v=<skrót zawartości>` (w `--plik` względny) |
| `abs` | ścieżka → pełny adres `https://domena/…` |
| `obraz:"wariant"` | id zdjęcia → gotowy `<picture class="foto foto--<id>">` (§8) |
| `slug`, `dlugosc`, `pierwsze:n`, `reszta:n`, `domyslnie:"x"`, `polacz:", "`, `wersaliki_pierwsza`, `liczba` (`1250` → `1 250`, `4.8` → `4,8` — tyle miejsc po przecinku, ile w danych) | pomocnicze |
| `liczba_mnoga:"zlecenie,zlecenia,zleceń"` | polska odmiana przy liczbie — zwraca samo słowo: `{{ n }} {{ n \| liczba_mnoga:"…" }}` |

### 3.2 Polska typografia (automatycznie w `{{ }}` bez `surowe`, oraz w `md`)

- twarda spacja po jednoliterowych słowach `a i o u w z A I O U W Z` i po „ul.”, „nr”, „tel.”, „r.”, „ok.”;
- twarda spacja między liczbą a jednostką (`12 m²`, `1 250 zł`, `30 min`, `5 km`) i w grupach cyfr;
- zakresy bez spacji z półpauzą: `7:00 - 15:00` / `7:00–15:00` → `7:00–15:00`, `32-46 zł` → `32–46 zł`;
- myślnik w zdaniu: ` - ` i ` — ` → ` – ` (półpauza ze spacjami; `funkcje.myslnik: "pauza"` → ` — `; decyzja D2 w `docs/DECYZJE.md`);
- cudzysłów `"tekst"` → `„tekst”`.

Wartość, która w całości jest adresem (`https://…`, `http://…`, `mailto:…`, `tel:…`), nie dostaje typografii nawet bez
filtra `url` (zakres lat `2019-2020` w adresie zostaje dywizem). Kod pocztowy w `auto.adres_html`, `auto.adres_linia_html`
i `auto.rejestr_linie` jest w `<span class="nowrap">` (nie łamie się na dywizie; U+2011 nie ma w podzbiorach fontów).

---

## 4. Model danych

Schematy: `tools/schemat/firma.schema.json`, `tresc.schema.json`, `zdjecia.schema.json` (JSON Schema 2020-12,
walidowane przez `tools/silnik/schemat.py` — podzbiór: `type`, `properties`, `required`, `additionalProperties:false`,
`enum`, `pattern`, `minLength/maxLength`, `minimum/maximum`, `items`, `minItems`, `oneOf` z `null`).
Nieznane pole = błąd (łapie literówki). Każdy plik danych zaczyna się od `"$schema"` i `"wersja_danych": 1`.

### 4.1 `data/firma.json` — kim jest firma (fakty, ustawienia)

```jsonc
{
  "$schema": "../tools/schemat/firma.schema.json",
  "wersja_danych": 1,
  "przyklad": false,                 // true tylko w przyklady/ — --produkcja przerywa
  "branza": "budowlana",             // restauracja | budowlana | producent | uslugi | gabinet  (→ tools/presety/)
  "typ_schema": null,                // nadpisanie @type, np. "RoofingContractor"; null = z presetu
  "firma": {
    "nazwa": "Bimex",                // krótka nazwa (logo-tekst, og:site_name, tytuł)
    "nazwa_prawna": "BIMEX Sp. z o.o.",
    "opis": "Roboty drogowe, wodno-kanalizacyjne i beton towarowy z własnej wytwórni w Rogoźnie.", // 1 zdanie ≤160 zn.
    "rok_zalozenia": 1993,           // albo null
    "domena": "https://bimex-rogozno.pl",   // bez „/” na końcu; null = jeszcze nie wiadomo (D13) — wtedy wymagany
                                     // adres_roboczy: canonical, sitemap i og:image z adresu roboczego, noindex na
                                     // każdej stronie, ostrzeżenie klasy A
    "adres_roboczy": null            // np. "https://bimex.konto.workers.dev" → noindex
  },
  "kontakt": {
    "telefon": "+48672683408",       // E.164; główny numer (przycisk „Zadzwoń”)
    "email": "biuro@firma.pl",       // null = ostrzeżenie B (--produkcja nie przejdzie): art. 5 ust. 2 u.ś.u.d.e.
    "adres": { "ulica": "ul. Fabryczna 7", "kod": "64-610", "miasto": "Rogoźno",
               "wojewodztwo": "wielkopolskie", "kraj": "PL" },
    "geo": { "lat": 52.75213, "lng": 16.99402 },   // zalecane 5 miejsc po przecinku; < 4 = błąd (json.dump, jq, Decap
                                                    // obcinają końcowe zera: 52.75360 → 52.7536, dlatego próg to 4);
                                                    // null = ostrzeżenie A: „Wyznacz trasę” do adresu, bez mapy OSM
    "obszar_dzialania": ["powiat obornicki", "Poznań"],  // albo null
    "dzialy": [ { "nazwa": "Dział sprzedaży betonu", "do_czego": "zamówienia betonu i transport",
                  "telefon": "+48602574218", "email": null, "osoba": null } ],   // albo null
    "dojazd": null,                  // zdanie: skąd wjazd, parking
    "dostepnosc_lokalu": null,       // zdanie: próg, winda, toaleta
    "czas_odpowiedzi": null          // np. "oddzwaniamy w ciągu 1 dnia roboczego"; null = bez obietnicy
  },
  "godziny": {                       // null = nie pokazujemy godzin w ogóle
    "nazwa": "Biuro",                // albo null; nagłówek tabeli
    "tydzien": { "pn": [["07:00","15:00"]], "wt": [["07:00","15:00"]], "sr": [["07:00","15:00"]],
                 "cz": [["07:00","15:00"]], "pt": [["07:00","15:00"]], "sb": [], "nd": [] },
                 // [] = zamknięte; kilka przedziałów: [["12:00","15:00"],["18:00","22:00"]]; "02:00" po północy OK
    "dodatkowe": [ { "nazwa": "Kuchnia", "tydzien": { … } } ],   // albo null (kuchnia, telefon, wytwórnia)
    "wyjatki": [ { "data": "2026-12-24", "godziny": [], "opis": "Wigilia" } ],  // albo []
    "uwagi": null,                   // zdanie pod tabelą
    "pokazuj_status": true           // „Otwarte do 15:00” w Europe/Warsaw
  },
  "rejestr": {
    "forma_prawna": "sp_z_oo",       // jdg | spolka_cywilna | sp_j | sp_k | sp_z_oo | sa | psa | inna | nieznana
                                     // (nieznana = jeszcze nie sprawdzona: ostrzeżenie A, w stopce sama nazwa;
                                     //  „inna” to naprawdę inna forma — fundacja, spółdzielnia)
    "nip": "6060001234", "regon": null, "krs": "0000123456",
    "sad_rejestrowy": "Sąd Rejonowy Poznań – Nowe Miasto i Wilda w Poznaniu, IX Wydział Gospodarczy KRS",
    "kapital_zakladowy": 50000,      // liczba w zł (sp_z_oo, sa)
    "kapital_wplacony": null,        // opcjonalne; S.A. (art. 374 § 1 KSH): kapitał wpłacony — wymagany dla "sa"
    "adres_siedziby": null,          // opcjonalne: {"ulica","kod","miasto"} z KRS, gdy siedziba ≠ kontakt.adres (stopka)
    "wlasciciel": null,              // JDG: imię i nazwisko
    "wspolnicy": null,               // s.c.: lista imion i nazwisk
    "samorzad_zawodowy": null        // zawody regulowane: izba, numer wpisu
  },
  "marka": {
    "logo": "assets/img/logo.png",   // plik w assets/img/ (skopiuj z brief/zdjecia/ — brief/ nie trafia do gita ani na
                                     // serwer, więc logo z brief/ = błąd); SVG albo PNG ≥ 512 px, przezroczystość zostaje
    "logo_na_ciemnym": null,
    "logo_szerokosc": 140,           // px w nagłówku (wysokość wynika z proporcji)
    "kolor": "#C8471F",              // kolor z logo/szyldu
    "kolor_zrodlo": "logo (plik od klienta)",
    "kolor_dodatkowy": null,         // drugi kolor z logo — tylko do jednej roli (np. focus)
    "tlo": "biale",                  // biale | cieple | chlodne | "#hex"
    "font_naglowki": "archivo",      // id z assets/fonts/fonty.json
    "font_tekst": "public-sans",
    "promien": 2,                    // 0 | 2 | 4  (px, przyciski i pola)
    "sekcja_ciemna": "stopka"        // gdzie ciemne tło: brak | stopka | kontakt
  },
  "seo": {
    "fraza": "Roboty drogowe i beton towarowy",  // co (usługa/produkt) — do tytułów stron
    "miasto": "Rogoźno",
    "opis": null                     // meta description strony głównej ≤ 160 zn. (> 160 = ostrzeżenie; < 70 = tylko
                                     // podpowiedź klasy A — nie dopisuj ogólników); null = z firma.opis
  },
  "social": { "facebook": null, "instagram": null, "google_maps": null, "linkedin": null,
              "youtube": null, "tiktok": null },
  "opinie_zbiorczo": null,           // {"zrodlo":"Google","ocena":4.8,"liczba":212,"data":"2026-09-29","url":"…"}
  "przekierowania": null,            // [{"z":"/oferta.php","do":"/oferta"}] → dist/_redirects (301); z = ścieżka, do = ścieżka lub https://
                                     // „z” pasuje dokładnie: /galeria/ nie łapie /galeria — wpisz adres tak, jak był linkowany
  "dostepnosc": null,                // {"data_oceny":"2026-09-15","metoda":"samoocena|audyt","wykonawca":null,
                                     //  "zgodnosc":"pelna|czesciowa","niedostepne":["…"]} → /dostepnosc; null = bez deklaracji zgodności
  "funkcje": {
    "hosting": "cloudflare",         // cloudflare | github_pages — polityka prywatności; github_pages: bez _headers i Workera
    "formularz": { "tryb": "mailto", "adresat": "biuro@firma.pl", "zgoda_checkbox": false },  // tryb: mailto | worker; null = brak formularza (D7)
    "mapa": "link",                  // link (tylko „Wyznacz trasę”) | po_kliknieciu (OSM po kliknięciu)
    "statystyki_cf_token": null,     // Cloudflare Web Analytics (bez cookies)
    "tytul_tryb": "fraza",           // fraza: „Fraza Miasto – Marka” | marka: „Marka” (D4)
    "telefon_w_naglowku": null,      // null = z presetu (D3)
    "etykiety_sekcji": false,        // małe etykiety nad nagłówkami (D1)
    "animacje": "brak",              // brak | wejscie (jedno subtelne wejście hero, nigdy h1/LCP) (D6)
    "myslnik": "polpauza",           // polpauza („ – ”) | pauza („ — ”) w tekstach strony (D2)
    "boty_ai": "zezwol",             // zezwol | blokuj_trening (robots.txt)
    "hsts_subdomeny": false, "hsts_preload": false,
    "faq_schema": false,
    "strona_dostepnosci": false,
    "rss": false
  },
  "zrodla": { "kontakt.telefon": "baner firmy na Facebooku, 2026-09-29" },
  "do_potwierdzenia": [ "godziny.tydzien.sb" ]   // → README „Do potwierdzenia z właścicielem”; ostrzeżenie klasy A (D10)
}
```
Daty (`RRRR-MM-DD`) są sprawdzane z kalendarzem: `2026-02-30` = błąd danych „nie ma takiego dnia: 30.02.2026”.
Godziny: przedział po północy (`["20:00","02:00"]`) należy do dnia otwarcia; nakładanie się przedziałów jest sprawdzane
także między dniami (piątek 20:00–04:00 i sobota 02:00–10:00 = błąd) i z niedzieli na poniedziałek. Zamknięcie o północy
zapisujemy `"24:00"` (albo `"00:00"`) — na stronie zawsze „24:00”, w JSON-LD `"23:59"`.

### 4.2 `data/tresc.json` — co firma robi (treść sekcji)

Każdy blok najwyższego poziomu jest `null` albo obiektem. `naglowek` każdej sekcji jest opcjonalny —
`null` = nagłówek domyślny z presetu (np. „Zakres prac”, „Karta”, „Realizacje”). Pola `zdjecie` to id z `zdjecia.json`.

```jsonc
{
  "$schema": "../tools/schemat/tresc.schema.json",
  "wersja_danych": 1,
  "hero": {
    "naglowek": "Drogi, kanalizacja i beton z Rogoźna",   // h1, ≤ 70 zn., konkret: co + gdzie
    "lead": "Od 1993 r. budujemy drogi gminne i powiatowe w północnej Wielkopolsce. Beton wozimy z własnej wytwórni.",
    "zdjecie": "droga",              // albo null (hero bez zdjęcia — typograficzne)
    "podpis": "Droga w Parkowie, 2024",  // nie pokazuje się pod zdjęciem hero (h1 obok mówi, co to) — opis w alt
    "cta_glowne": null,              // null = z presetu (np. Zadzwoń); albo {"tekst":"…","href":"/kontakt"}
    "cta_drugie": null
  },
  "ogloszenie": null,                // {"tekst":"24–26.12 nieczynne","od":"2026-12-10","do":"2026-12-27"}
  "oferta": {
    "naglowek": null, "wstep": null,
    "pozycje": [ { "slug": "roboty-drogowe", "nazwa": "Roboty drogowe", "opis": "Jedno–dwa zdania konkretu.",
                   "zakres": ["nawierzchnie bitumiczne", "chodniki z kostki"],   // albo null
                   "cena": null,             // liczba | {"od":…, "do":…} | null
                   "jednostka": null,        // "m²", "szt.", "h"
                   "czas": null,             // "2–3 dni"
                   "zdjecie": "walec",       // albo null
                   "tresc": null } ]         // "tresc/uslugi/roboty-drogowe.md" → podstrona (próg §6.3)
  },
  "cennik": null,        // {"naglowek","dla":"konsumenci|firmy","data":"2026-09-01","grupy":[{"nazwa","pozycje":[{"nazwa","opis","cena","jednostka"}]}],"uwagi","pdf"}
  "menu": null,          // {"naglowek","data","ceny","kategorie":[{"nazwa","pozycje":[{"nazwa","opis","cena","wege":bool,"ostre":bool,"alergeny":[]}]}],"uwagi","pdf"}
                         // ceny (opcjonalne): "w_lokalu" = karta bez cen na stronie (każda cena null)
  "produkty": null,      // {"naglowek","wstep","kategorie":[{"slug","nazwa"}],"pozycje":[{"slug","nazwa","kategoria","opis","parametry":[{"nazwa","wartosc"}],"zdjecie","cena"}]}
  "realizacje": null,    // {"naglowek","wstep","kategorie":[{"slug","nazwa"}],"pozycje":[{"tytul","miejsce","rok","kategoria","parametr","opis","klient","zdjecia":[],"zrodlo","prywatna":bool}]}
  "przetargi": null,     // {"naglowek","wstep","zrodlo_opis","pozycje":[{"zadanie","zamawiajacy","rok","wartosc","zrodlo"}]}
  "proces": null,        // {"naglowek","wstep","kroki":[{"nazwa","opis","czas"}]}  ≥ 2 kroki; opis = Markdown; czas = termin albo rezultat
  "zasady": null,        // {"naglowek","wstep","pozycje":[{"nazwa","opis"}]}  gwarancja, płatności, zadatek, ważność wyceny, rezerwacje, dostawa
  "o_firmie": null,      // {"naglowek","wstep","tresc":"tresc/o-firmie.md","zdjecie","fakty":[{"nazwa","wartosc"}]}  podpis zdjęcia z zdjecia.json
  "zespol": null,        // {"naglowek","wstep","osoby":[{"imie","rola","fakt","zdjecie","zgoda":true}]}  właściciel pierwszy; zdjęcie tylko przy zgoda: true
  "liczby": null,        // {"naglowek","pozycje":[{"wartosc","jednostka","opis","zrodlo","data"}]}  (≥ 2, inaczej ukryte); rok jako tekst ("1993"), bo liczba dostaje grupy cyfr
  "opinie": null,        // {"naglowek","weryfikacja":"zdanie Omnibus","pozycje":[{"tekst","autor","miejscowosc","data","url"}]} (≤ 3; [] = sama ocena z firma.opinie_zbiorczo)
  "certyfikaty": null,   // {"naglowek","wstep","pozycje":[{"nazwa","wydawca","numer","rok","waznosc","plik"}]}  plik w assets/img/ (np. pliki/iso.pdf); wygasłe pomijane
  "faq": null,           // {"naglowek","pozycje":[{"pytanie","odpowiedz"}]}  odpowiedź = Markdown; prawdziwe pytania klientów
  "galeria": null,       // {"naglowek","zdjecia":["id",…]}
  "do_pobrania": null,   // {"naglowek","pozycje":[{"plik":"assets/img/pliki/katalog.pdf","opis"}]}  plik tylko w assets/img/
                         //   (inaczej nie trafi na serwer); brak pliku = błąd; typ, rozmiar i liczbę stron PDF liczy build
  "kariera": null,       // {"naglowek","wstep","kontakt":{"osoba","telefon","email"}|null,"pozycje":[{"stanowisko","miejsce",
                         //   "wymiar","wynagrodzenie","opis","wazne_do","opublikowano"}]}  kontakt null = główny telefon i e-mail;
                         //   po wazne_do oferta znika; JobPosting tylko z opublikowano + wazne_do + opis (Google wymaga datePosted)
  "wspolpraca": null,    // producent B2B: {"naglowek","wstep","tresc":"tresc/wspolpraca.md","warunki":[…]}  (tresc albo warunki)
  "gdzie_kupic": null,   // {"naglowek","wstep","punkty":[{"nazwa","miasto","wojewodztwo","adres","www"}]}  województwo małymi
                         //   literami („wielkopolskie”; literówka „…kie” = błąd), za granicą nazwa kraju, null → „Pozostałe”
  "kontakt": { "naglowek": null, "wstep": null }
}
```

#### 4.2.1 Oferta, cennik, karta, produkty (`tools/silnik/oferta.py`)

- **Ceny** zawsze przez filtr `cena` (część `czesci/cena.html`: `0` → „bezpłatnie”, `jednostka` → „45 zł/m²”).
  Obiekt `{}` bez `od` i `do` albo `od > do` = błąd danych.
- **Brutto domyślnie** (art. 3 ust. 2 ustawy o informowaniu o cenach): oferta, karta i produkty są zawsze brutto.
  `cennik.dla: "firmy"` = ceny netto — dozwolone tylko w branży z `cennik_netto: true` w presecie (budowlana, producent,
  usługi), inaczej błąd; strona pokazuje wtedy „**Ceny netto** (bez VAT), dla firm” i „Cena netto” w nagłówku kolumny.
- **Pola opcjonalne** (nie trzeba ich wpisywać; brak = `null`): `cennik.grupy[].pozycje[].czas` („45 min” — kolumna
  „Czas” tylko w grupie, która go ma; na telefonie pod nazwą), `menu.kategorie[].pozycje[].porcja` („300 g”, „10 szt.”),
  `produkty.pozycje[].jednostka` („m²”, „szt.”).
- **Karta:** oznaczenia `wege`/`ostre` jako „W”/„O” w ramce 1 px z legendą (tylko użyte znaki; czytnik ekranu dostaje
  pełne słowa), alergeny nazwami 14 grup (rozporządzenie UE 1169/2011, zał. II — inna nazwa = ostrzeżenie),
  „Karta z dnia …” z `menu.data`. Cennik z kilkoma grupami — każda grupa musi mieć `nazwa`.
  Karta bez cen (właściciel podaje je tylko w lokalu): `menu.ceny: "w_lokalu"` — pod kartą, na głównej i na `/menu`,
  stoi `menu.uwagi` albo „Ceny podajemy w lokalu.”; cena przy `"w_lokalu"` = błąd, karta bez żadnej ceny bez tego
  pola = ostrzeżenie klasy A. `menu.uwagi` jest w obu wersjach sekcji. `/menu` powstaje tylko wtedy, gdy pełna
  karta pokazuje coś więcej niż skrót: alergeny, PDF albo więcej pozycji niż `limity.menu` + 6 — inaczej cała karta
  stoi na głównej.
- **PDF** (`menu.pdf`, `cennik.pdf`): ścieżka `assets/img/pliki/…pdf`, plik musi istnieć (inaczej błąd); typ, rozmiar
  i liczbę stron liczy build (`tools/silnik/pliki.py`): „Karta do pobrania (PDF, 240 kB, 2 strony)”. PDF tylko jako
  dodatek do HTML, w pełnej wersji sekcji.
- **Produkty:** `kategoria` musi być slugiem z `produkty.kategorie` (inaczej błąd); produkty bez kategorii przy
  istniejących kategoriach trafiają do grupy „Pozostałe”. Bez żadnego zdjęcia — lista wierszy zamiast siatki.
- **Skrót na głównej** (`tryb="skrot"`, gdy jest podstrona): oferta i produkty — pierwsze pozycje do `limity`; karta
  i cennik — po kolei po jednej pozycji z każdej grupy do limitu (widać przekrój). Link do pełnej wersji tylko wtedy,
  gdy pokazuje ona coś więcej (`auto.<sekcja>.wiecej`, np. „Szczegółowy zakres i cennik”, „Pełny cennik (24 pozycje)”).
  Bez podstrony sekcja na głównej jest pełna.

**Realizacje, przetargi, galeria — znaczenie pól.**
- `realizacje.pozycje[].tytul` to rodzaj prac, najlepiej małą literą („przebudowa drogi gminnej”); na stronie tytuł to
  „{miejsce} – {tytul}” z wielką literą na początku (gdy `miejsce` już jest w tytule — sam tytuł). `parametr` — jedna
  liczba z jednostką („1,8 km”, „2 400 m²”). `zdjecia[0]` jest zdjęciem głównym. `prywatna: true` → zamiast klienta
  „Klient prywatny”, a `miejsce` może mieć tylko miejscowość albo gminę (ulica albo cyfra = błąd danych).
  `zrodlo` z adresem `https://…` staje się linkiem „Źródło: domena” (w pełnej wersji), inny tekst jest notatką i się nie pokazuje.
  `kategoria` musi być slugiem z `kategorie` (błąd danych); filtr powstaje przy ≥ 2 kategoriach z pozycjami.
- `przetargi.pozycje` są na stronie od najnowszych (sortowanie po `rok`, w roku kolejność z danych) i pogrupowane latami.
  `zrodlo`: `"BZP"` (pod tabelą link do wyszukiwarki ogłoszeń BZP), adres `https://…` (kolumna „Źródło” z linkiem)
  albo `null`. Kolumny „Wartość” i „Źródło” są tylko wtedy, gdy ma je choć jeden wiersz. `zrodlo_opis` → „Źródło: …” pod tabelą.
  `rok` w przyszłości (także w realizacjach) i powtórzony wiersz = ostrzeżenie (w `--produkcja` błąd).
- `galeria.zdjecia` — kolejność z danych, podpis z `zdjecia.json` → `podpis`.

### 4.3 `data/zdjecia.json` — manifest zdjęć

```jsonc
{ "$schema": "../tools/schemat/zdjecia.schema.json", "wersja_danych": 1,
  "zdjecia": [
    { "id": "droga",                          // [a-z0-9-]
      "zrodlo_plik": "brief/zdjecia/droga.jpg",   // oryginał (dla tools/zdjecia.py)
      "alt": "Świeżo położony asfalt na drodze gminnej między polami", // po polsku, 5–150 zn.; "" tylko gdy ozdobne
      "podpis": null,                         // widoczny podpis albo null
      "zrodlo": "ulotka firmy na bimex-rogozno.pl, 2026-09-29",
      "autor": null,                          // fotograf, jeśli nie firma
      "zgoda": null,                          // true wymagane, gdy widać rozpoznawalną twarz
      "osoby": false,                         // czy na zdjęciu są rozpoznawalne osoby
      "punkt": [0.5, 0.5],                    // punkt ostrości do kadrowania (OG, kadr mobilny)
      "kadr_mobilny": null } ] }             // id innego zdjęcia (portret) dla < 600 px albo null
```

`tools/zdjecia.py` zapisuje `assets/img/foto/<id>-<szer>.{avif,webp,jpg}` (szerokości 480/960/1440/1920, nie większe
niż oryginał) oraz `assets/img/foto/manifest.json`: `{ "<id>": {"szer": 1920, "wys": 1280, "szerokosci": [...],
"formaty": ["avif","webp","jpg"]} }`, a także `assets/img/og.jpg` (1200×630) i `assets/img/ikony/*` z logo
(`logo-naglowek.png` = 3× szerokości, w jakiej logo stoi w nagłówku: `min(logo_szerokosc, 56 px × proporcja)`).
`build.py` czyta tylko `manifest.json` i `zdjecia.json` — sam nie przetwarza obrazów.
Dla pozycji oferty z plikiem `.md` (kandydatki na podstronę usługi) `tools/zdjecia.py` zapisuje też
`assets/img/og/<id-zdjęcia>.jpg` (1200×630, kadr wg `punkt`) — `og:image` podstrony; bez pliku build bierze `og.jpg`.

### 4.4 `data/tresc/*.md`, `data/aktualnosci/*.md`

Markdown (podzbiór z §3.1). Aktualności mają nagłówek:
```
---
tytul: Nowa wytwórnia betonu
data: 2026-05-14
zdjecie: wytwornia        # id albo brak
opis: Jedno zdanie do listy i meta description.
---
Treść…
```
Nazwa pliku = slug (`2026-05-nowa-wytwornia.md` → `/aktualnosci/2026-05-nowa-wytwornia`).
Nagłówek ma tylko te cztery pola (`tytul`, `data`, `opis` — wymagane; `zdjecie` — id z `zdjecia.json`); nieznane pole
(np. „zdjęcie”) i nieistniejące zdjęcie to błąd. Tytuł idzie do `<title>` („Tytuł Miasto – Marka”, a gdy się nie mieści —
„Tytuł – Marka”): powyżej ok. 50 znaków build ostrzega o tytule > 60 zn. `opis` trafia do listy, meta description i RSS —
na stronie wpisu nie stoi nad treścią. Najnowszy wpis starszy niż 12 miesięcy: zapowiedź na głównej znika
(`UKRYTO` + ostrzeżenie klasy A), `/aktualnosci` i wpisy zostają.

---

## 5. Presety branżowe (`tools/presety/<branza>.json`)

Preset to **reguły, nie wygląd** (nie zawiera CSS).

```jsonc
{
  "branza": "restauracja",
  "typ_schema": "Restaurant",
  "wymagane": ["godziny", "tresc.menu|tresc.cennik"],      // „a|b” = jedno z dwóch
  "zalecane": ["tresc.galeria", "social.facebook"],        // ostrzeżenie, nie błąd
  "sekcje_glowna": ["hero", "menu", "galeria", "o_firmie", "opinie", "godziny", "kontakt"],
  "warianty": { "godziny": "tint", "zasady": "sm" },      // tylko strona główna: tint = sekcja z tłem (--tlo-2; jedna
                                                         // na stronę, w środku), sm = mniejsze odstępy (sekcje użytkowe);
                                                         // szablon sekcji dostaje sekcja.klasa (section--tint | section--sm)
  "strony": ["menu", "kontakt", "polityka-prywatnosci"],   // podstrony dostępne w tej branży (i tak znikają bez danych)
  "cta_glowne": { "tekst": "Zadzwoń: {tel}", "href": "tel" },   // "tel" | "trasa" | "kontakt" | "/menu" | "katalog"
  "cta_drugie": { "tekst": "Wyznacz trasę", "href": "trasa" },
  "pasek_mobilny": ["tel", "trasa"],                      // przyciski paska na telefonie (< 960 px)
  "telefon_w_naglowku": true,
  "naglowki": { "oferta": "Co robimy", "menu": "Karta", "realizacje": "Realizacje", … },
  "pokazuj_status_w_hero": true,
  "nav": ["menu", "galeria", "o_firmie", "godziny", "kontakt"],   // kandydaci do nawigacji (§6.3), w tej kolejności
  "nav_etykiety": { "o_firmie": "O nas", … },               // krótkie etykiety w menu
  "limity": { "realizacje": 6, "przetargi": 8, … }            // zmienna `limit` sekcji w trybie „skrot”
}
```
Ścieżki w `wymagane`/`zalecane`: „tresc.…” → `data/tresc.json`, reszta → `data/firma.json` (np. „godziny”, „social.facebook”).
`cennik_netto` (bool): czy branża może mieć cennik netto (`cennik.dla: "firmy"`) — `false` dla restauracji i gabinetu
(sprzedają konsumentom), `true` dla budowlanej, producenta i usług. Restauracja i producent mają `cennik` na głównej
(zaraz po karcie / produktach), gabinet i usługi — jak w tabeli; budowlana pokazuje cennik tylko na `/oferta`.
Domyślne `naglowki` nie mogą zakładać treści, której nie znamy („Zasady”, „Zdjęcia”, „Adres i dojazd” — nie „Rezerwacje”,
„Wnętrze i dania”, „Płatności i gwarancja”); konkretny nagłówek klient wpisuje w `tresc.<sekcja>.naglowek`.
Po hero każda branża ma `ogloszenie` (sekcja znika, gdy nie ma aktualnego ogłoszenia). Przed godzinami i kontaktem każda
ma `aktualnosci` (trzy najnowsze wpisy; znika bez wpisów albo gdy najnowszy ma > 12 miesięcy). „Praca” (`kariera`) jest
w `nav` każdej branży — pozycja pojawia się tylko wtedy, gdy powstała strona `/kariera`.

| branza | `@type` | sekcje strony głównej (kolejność) | CTA / pasek |
|---|---|---|---|
| restauracja | Restaurant | hero, ogloszenie, menu (skrót), cennik (skrót), galeria, o_firmie, opinie, aktualnosci (skrót), godziny, zasady, faq, kontakt | Zadzwoń + Trasa |
| budowlana | GeneralContractor | hero, ogloszenie, oferta, realizacje (skrót), przetargi (skrót), proces, zasady, o_firmie, liczby, certyfikaty, faq, aktualnosci (skrót), kontakt | Zadzwoń + Zapytanie |
| producent | Organization (+ LocalBusiness dla salonu) | hero, ogloszenie, produkty, cennik (skrót), o_firmie, proces, liczby, zasady, wspolpraca, gdzie_kupic, do_pobrania, faq, aktualnosci (skrót), kontakt | Katalog + Kontakt (bez telefonu w nagłówku) |
| uslugi | ProfessionalService (lub podtyp) | hero, ogloszenie, oferta, cennik (skrót), proces, zasady, zespol, opinie, aktualnosci (skrót), godziny, faq, kontakt | Zadzwoń + Trasa |
| gabinet | MedicalBusiness (lub podtyp) | hero, ogloszenie, oferta, zespol, cennik (skrót), zasady, aktualnosci (skrót), godziny, faq, kontakt | Zadzwoń + Trasa |

Sekcje bez danych znikają, więc lista kandydatów może być dłuższa niż 9 — ostrzeżenie „> 9 sekcji” liczy tylko widoczne.

---

## 6. Strony, sekcje, nawigacja

### 6.1 Strony (`src/strony/*.html`)

Każdy plik strony zaczyna się nagłówkiem:
```
{# strona: sciezka="/realizacje" wymaga="tresc.realizacje.pozycje" nav="Realizacje" tytul="Realizacje" #}
```

| Plik | Adres | Powstaje, gdy |
|---|---|---|
| `index.html` | `/` | zawsze |
| `oferta.html` | `/oferta` | `oferta.pozycje` ≥ 4 **albo** jest `cennik` (inaczej wszystko mieści się na głównej) |
| `usluga.html` | `/oferta/<slug>` | pozycja ma `tresc` (plik .md ≥ 150 słów) **i** `zdjecie` **i** jedno z: `cena`, `zakres`, `czas`; inaczej `UKRYTO: podstrona…` |
| `menu.html` | `/menu` | `menu` (restauracja) z alergenami, PDF albo > `limity.menu` + 6 pozycji (inaczej cała karta na głównej) |
| `realizacje.html` | `/realizacje` | `realizacje.pozycje` > 6 albo `przetargi.pozycje` > 8 (pełne wersje obu sekcji: h1 = nagłówek realizacji, filtr kategorii, pod nimi przetargi z własnym h2; same przetargi — h1 = nagłówek przetargów, bez drugiego nagłówka, wstęp pod h1) |
| `blad-formularz.html`, `blad-konfiguracja.html` | `/blad-formularz`, `/blad-konfiguracja` | `funkcje.formularz.tryb = "worker"` (strony błędów bez JS, noindex) |
| `produkty.html` | `/produkty` | `produkty.pozycje` > 6 |
| `o-firmie.html` | `/o-firmie` | `o_firmie.tresc` ma > 250 słów albo jest `zespol` z ≥ 4 osobami; pokazuje w pełnej wersji `o_firmie`, `zespol`, `liczby`, `certyfikaty` |
| `aktualnosci.html`, `wpis.html` | `/aktualnosci`, `/aktualnosci/<slug>` | są pliki w `data/aktualnosci/` |
| `kariera.html` | `/kariera` | `kariera.pozycje` z ważnym `wazne_do` (albo bez daty); JobPosting w JSON-LD tylko tu |
| `kontakt.html` | `/kontakt` | zawsze |
| `polityka-prywatnosci.html` | `/polityka-prywatnosci` | zawsze (treść generowana z `funkcje`) |
| `dostepnosc.html` | `/dostepnosc` | `funkcje.strona_dostepnosci` |
| `404.html`, `dziekujemy.html`, `blad.html` | `/404`, `/dziekujemy`, `/blad` | zawsze (`noindex`, poza mapą strony) |

Klucze nagłówka strony: `sciezka` (wymagany; w kolekcjach z `{slug}`), `tytul` (do `<title>`, D4: główna „Fraza Miasto – Marka”,
podstrona „Tytuł Miasto – Marka”, gdy mieści się w 60 zn., inaczej „Tytuł – Marka”; bez miasta: polityka prywatności,
dostępność i strony `indeksuj="nie"`), `h1` (domyślnie = `tytul`),
`opis` (meta description; na głównej zawsze `seo.opis` albo `firma.opis`), `wstep` (akapit pod h1), `nav` (etykieta w menu),
`sekcja` (id sekcji, które strona pokazuje w pełnej wersji — spacją; nawigacja wskazuje wtedy stronę zamiast kotwicy),
`wymaga`, `kolekcja` (`oferta` | `aktualnosci` | `kariera` — strona powstaje raz na element, w szablonie `element`),
`rodzic` (ścieżka do okruszków), `indeksuj="nie"` (noindex, bez canonical, poza sitemap).
Progi z tabeli liczy `tools/silnik/strony.py` (`progi()`); strona spoza `preset.strony` i spoza „zawsze” nie powstaje.

Plik `dist/<sciezka>.html` (np. `dist/realizacje.html`, `dist/oferta/roboty-drogowe.html`, `dist/index.html`).

**Oferta, usługa, karta, produkty.** `/oferta` ma `sekcja="oferta cennik"`: h1 = nagłówek oferty (albo cennika, gdy
oferty nie ma), wstęp oferty pod h1, potem oferta (`bez_naglowka`) i cennik z własnym h2 (kotwica `/oferta#cennik`).
`/oferta/<slug>` (kolekcja `oferta`, `rodzic="/oferta"`): h1 = nazwa, wstęp = opis, zdjęcie u góry (wariant `hero`, bez
lazy), treść `.md`, obok cena brutto, czas, zakres i jedno wezwanie do działania z presetu (`auto.oferta.cta`, nie
z hero), na końcu link do listy; w JSON-LD `Service`. `/menu` jest do druku (reguły `@media print` w `12-menu.css`).
`/produkty` ma filtr kategorii (§11). Tytuł strony nadrzędnej w okruszkach może zawierać `{{ }}` — build go renderuje.
Linki wewnętrzne bez `.html` (Cloudflare `html_handling: auto-trailing-slash` je obsługuje).

### 6.2 Sekcje (`src/sekcje/<id>.html`)

Pierwsza linia: `{# wymaga: tresc.oferta.pozycje #}` (kilka ścieżek po przecinku = wszystkie; `a|b` = jedna z).
Gdy warunek niespełniony, `{% sekcje %}` i `{% include %}` pomijają sekcję i wypisują `UKRYTO`.
Sekcja dostaje zmienne `tryb` (`"skrot"` na stronie głównej, `"pelny"` na podstronie) i `limit`.
Na stronie głównej skrót kończy się linkiem do podstrony („Wszystkie realizacje (24)”), jeśli podstrona powstała.

Lista sekcji i ich identyfikatorów HTML (`<section id="…">` = kotwica):
`hero`, `ogloszenie`, `oferta`, `cennik`, `menu`, `produkty`, `realizacje`, `przetargi`, `proces`, `zasady`,
`o_firmie` (id `o-firmie`), `zespol`, `liczby`, `opinie`, `certyfikaty`, `faq`, `galeria`, `do_pobrania` (id `do-pobrania`),
`kariera`, `wspolpraca`, `gdzie_kupic` (id `gdzie-kupic`), `aktualnosci`, `godziny`, `kontakt`.
Sekcja `godziny` ma klasę korzenia `otwarcie` (nie `godziny` — tak nazywa się tabela godzin w `19-kontakt.css`): jedna
tabela, kolumna na zestaw (`godziny` + `godziny.dodatkowe`), status tylko wtedy, gdy nie ma go w hero. Gdy `godziny` stoi na
głównej, kontakt w skrócie nie powtarza tabeli (`auto.godziny_osobno`). `ogloszenie` to pasek pod hero (bez widocznego
nagłówka, `data-do` dla `70-ogloszenie.js`) i nie liczy się do limitu 9 sekcji.

Każda sekcja: `<section class="section section--<wariant>" id="{{ sekcja.html_id }}" aria-labelledby="<id>-h">` + nagłówek
`<div class="section__head"><h2 id="<id>-h">{{ sekcja.naglowek }}</h2><p class="section__lead">…</p></div>`.
Na podstronie, której h1 jest tytułem sekcji, sekcja nie wstawia własnego h2 (zmienna `bez_naglowka=true`),
a `aria-labelledby="tytul-strony"` (id h1 z `czesci/naglowek-strony.html`). Nagłówki wewnątrz: `<h{{ hn }}>`.
Brak pliku sekcji = INFO w buildzie (sekcja pominięta), niespełnione `wymaga` = `UKRYTO`.

**Skrót i pełna wersja nie powtarzają się.** `tryb="skrot"` pokazuje tylko to, co potrzebne na głównej, i kończy się
opisowym linkiem do podstrony; `tryb="pelny"` — resztę. Wzór: `sekcje/kontakt.html` (skrót: adres, trasa, główny telefon,
e-mail, godziny, gdy nie ma osobnej sekcji godzin, link `auto.kontakt_wiecej` → `/kontakt`; pełny: działy, dojazd, mapa,
zapytanie). Jedna informacja w jednej sekcji raz (plus stopka) — np. e-mail stoi w bloku telefonów, a zapytanie e-mailem
na ten sam adres pokazuje już tylko przycisk.
Blok z telefonami (i każdy inny blok z tymi samymi akcjami co pasek mobilny) ma `data-ukryj-pasek`. Pasek nie pokazuje
przycisku do strony, na której jesteśmy („Kontakt” na `/kontakt`).

**Sekcje o firmie** (`proces`, `zasady`, `faq`, `o_firmie`, `zespol`, `liczby`, `opinie`, `certyfikaty`; CSS `14-proces.css`,
`15-firma.css`). Każda ma układ pod swoją treść: proces = `<ol>` z numerem listy (`::marker`), zasady i liczby = `<dl>`
w wierszach, faq = `<details>`, o firmie = zdjęcie na całą szerokość + tekst + fakty (`<dl>`), zespół = portrety 4:5
(gdy każda osoba ma zdjęcie ze zgodą) albo wiersze, opinie = ocena zbiorcza + cytaty (`<blockquote cite>`) + zdanie
o weryfikacji, certyfikaty = wpisy z danymi i skanem („PDF, 240 kB”). `limit` tnie listę (faq, zespół, certyfikaty) tylko,
gdy istnieje podstrona z pełną wersją — inaczej pozycje byłyby nieosiągalne. Kontrole w `dane.kontrole_firma`: ocena
zbiorcza bez `tresc.opinie.weryfikacja` = błąd (Omnibus), puste zdanie o weryfikacji = błąd, ocena starsza niż pół roku,
cytat bez linku, podpis z nazwiskiem, zdjęcie osoby bez zgody, jedna liczba, liczba bez daty albo powtórzona w `o_firmie.fakty`,
plik certyfikatu spoza `assets/img/` lub nieistniejący (błąd), certyfikat wygasły (pomijany), `faq_schema` bez pytań.

### 6.3 Nawigacja

Generowana z istniejących stron (kolejność z presetu), maks. 6 pozycji; gdy podstrony nie ma — kotwica do sekcji
na głównej (`/#realizacje`). Plus jedna akcja: telefon (preset `telefon_w_naglowku`) albo CTA presetu.
`aria-current="page"` na bieżącej.
Sekcja z `null` w `tresc.json` nie daje pozycji w menu (na `/oferta` bez oferty etykietą jest „Cennik”, nie „Usługi”).

---

## 7. CSS

### 7.1 Pliki

`assets/css/czesci/` sklejane w tej kolejności (lista w `tools/silnik/zasoby.py`):
`00-reset.css`, `01-baza.css` (typografia, linki, focus, `.wrap`, `.section`, `.prose`, przyciski, formularze),
`02-uklad.css` (nagłówek, nawigacja, stopka, pasek mobilny, okruszki, nagłówek podstrony),
`10-*.css` … sekcje (jeden plik na sekcję lub grupę), `89-dokument.css` (polityka prywatności, dostępność),
`90-druk.css`, `91-ruch.css` (animacje pod `prefers-reduced-motion: no-preference`; build dołącza go tylko przy
`funkcje.animacje: "wejscie"`), `92-wymuszone-kolory.css`.
Kolejność = alfabetyczna kolejność plików w `assets/css/czesci/` (numer na początku nazwy); nowy plik sekcji
(`1x-*.css`) wystarczy dodać do katalogu. Na początek wyniku build wstawia `@font-face` wybranych krojów (+ zamienniki
metryczne; tylko pliki wag, których strona używa — `--fw-naglowki`, `--fw-tekst`, `--fw-mocna` — i tylko te trafiają do
`dist/`; `url()` ma ten sam `?v=<skrót>` co `<link rel="preload">`), `:root{…}` z tokenami marki (§7.2) i reguły `object-position` zdjęć z punktem ostrości
(`.foto--<id> img{object-position:…}` — bez atrybutów `style`), na koniec — `wlasne.css` klienta.
Wynik: `dist/assets/css/strona.css`, w HTML `strona.css?v=<skrót>`.
**Zakaz** atrybutów `style=""` i bloków `<style>` w HTML (CSP `style-src 'self'`).

### 7.2 Tokeny (`:root`, generuje `tools/silnik/kolory.py` z `marka`)

Kolory: `--tlo`, `--tlo-2` (lekko przyciemnione tło sekcji), `--tekst` (≥ 7:1), `--tekst-2` (pomocniczy ≥ 5,5:1 na obu tłach),
`--linia` (dekoracyjne linie), `--linia-mocna` (obramowania pól ≥ 3:1), `--marka` (kolor z logo),
`--marka-tekst` (wariant marki ≥ 4,5:1 na `--tlo` i `--tlo-2` — linki, akcenty tekstowe),
`--przycisk`, `--na-przycisku` (≥ 4,5:1), `--przycisk-hover`, `--przycisk-ramka` i `--przycisk-ramka-hover` (obrys
przycisku głównego ≥ 3:1 z `--tlo` i `--tlo-2`, WCAG 1.4.11: kolor przycisku, a gdy za jasny — np. żółty — `--tekst`),
`--marka-jasna` (tło z odcieniem marki),
`--ciemne`, `--na-ciemnym` (≥ 7:1), `--na-ciemnym-2` (≥ 5,5:1), `--akcent-na-ciemnym` (≥ 4,5:1),
`--focus` (≥ 3:1 na wszystkich tłach), `--blad`, `--ok`.
Build sprawdza kontrast każdej pary i przerywa z komunikatem, jeśli para nie przechodzi.

Kroje: `--font-naglowki`, `--font-tekst` (z metrycznym zamiennikiem, §7.4), wagi `--fw-naglowki`, `--fw-tekst`, `--fw-mocna`
(z `fonty.json`, dopasowane do dostępnych plików). Inne generowane: `--radius-ctl`, `--radius-img`, `--logo-szer`,
`--linia-na-ciemnym`, `--focus-na-ciemnym`. W `.section--dark` i `.site-footer--ciemna` tokeny `--tlo`, `--tekst`, `--tekst-2`,
`--linia`, `--linia-mocna`, `--marka-tekst`, `--focus` są podmienione na wersje „na ciemnym” — komponenty działają bez zmian.
Kolor marki zbyt jasny do tekstu (np. żółty): `--marka-tekst` = `--tekst`, a marka zostaje w wypełnieniach i podkreśleniach.
Marka prawie bezbarwna i jasna (biel, jasna szarość: < 3:1 z tłem i nasycenie OKLCH < 0,03): przycisk ma ciemne wypełnienie
(`--przycisk` = `--tekst`). Przycisk bardzo ciemny (jasność OKLCH < 0,3, np. czerń): `--przycisk-hover` jest jaśniejszy.

Stałe (w `01-baza.css`, nie zależą od klienta):
```
--fs-body: clamp(1.0625rem, 1rem + .25vw, 1.125rem);   /* 17→18 px */
--lh-body: 1.6;
--fs-lead: clamp(1.125rem, 1.05rem + .4vw, 1.3125rem); /* 18→21 */
--fs-h1: clamp(2.25rem, 1.2rem + 4.5vw, 4.5rem);       /* 36→72 */
--fs-h2: clamp(1.75rem, 1.2rem + 2.2vw, 3rem);         /* 28→48 */
--fs-h3: clamp(1.25rem, 1.1rem + .6vw, 1.625rem);      /* 20→26 */
--fs-maly: 1rem;      /* 16 px — najmniejszy tekst do czytania */
--fs-meta: 1rem;      /* 16 px — podpisy zdjęć i metadane; cisza przez kolor --tekst-2, nie przez rozmiar */
--s-1:4px --s-2:8px --s-3:12px --s-4:16px --s-5:24px --s-6:32px --s-7:48px --s-8:64px --s-9:96px --s-10:128px
--max: 1440px; --gutter: clamp(16px, 4vw, 56px); --prose: 65ch;
--section-y-sm: clamp(48px, 6vw, 80px); --section-y: clamp(56px, 6vw, 96px); --section-y-lg: clamp(96px, 12vw, 176px);
                      /* .section: padding --section-y (góra) / --section-y-sm (dół); pod hero --section-y-sm */
--radius-ctl: <marka.promien>px; --radius-img: 0 (zdjęcia zawsze bez zaokrągleń);
/* klasy układu: .bok (nagłówek z boku ≥ 960), .section--tint / --sm (warianty z presetu),
   .produkty__wiersze (produkty bez zdjęcia pod siatką), .site-footer__siatka--bez-kontaktu */
--header-h: 64px (≥ 960: 72px); --callbar-h: 56px;
--ease: cubic-bezier(.2,.7,.2,1); --dur: 180ms;
```
Nagłówki: `line-height 1.05–1.15`, `letter-spacing -0.01…-0.02em`, `text-wrap: balance`; akapity `text-wrap: pretty`;
`font-variant-numeric: tabular-nums` przy cenach, godzinach, telefonach, tabelach.

### 7.3 Punkty przełamania (mobile-first, `min-width`)

`600px` (1 → 2 kolumny), `960px` (menu rozwinięte, telefon w nagłówku zamiast paska mobilnego), `1280px` (szerokie układy).
Plus `@media (min-height: 800px) and (min-width: 960px)` dla wysokości hero.

### 7.4 Kroje

`assets/fonts/fonty.json`: `{ "archivo": {"nazwa":"Archivo","styl":"sans","pochodzenie":"google/fonts ofl/archivo …",
"pliki":[{"plik":"archivo/archivo-pl.woff2","waga":"400 700","styl_kroju":"normal"}],"waga_tekstu":400,"waga_mocna":600,
"waga_naglowkow":650,"licencja":"archivo/OFL.txt","zamiennik":{"lokalny":["Arial","Helvetica","Liberation Sans"],
"size_adjust":"…%","ascent":"…%","descent":"…%","line_gap":"0%"}} }`.
Krój zmienny = jeden plik (`"waga": "400 700"`); krój statyczny (Barlow) = jeden plik na wagę (`"waga": "600"`).
Każdy plik to łacina + polskie znaki w jednym woff2, `font-display: swap`, preload tylko pliku nagłówków i pliku tekstu
(maks. 2). Metryki zamiennika liczy `tools/fonty.py` (fontTools, lokalnie). Zakaz domyślnego Inter/Geist/Instrument Serif (D5).
Biblioteka: archivo, public-sans, atkinson-next, newsreader, source-serif-4, literata, barlow, barlow-condensed.

### 7.5 Zasady wyglądu (egzekwowane przez `lint_slop.py`)

Bez: gradientów tekstu i tła (poza zdjęciem z przyciemnieniem do czytelności), kart z cieniem i zaokrągleniem ≥ 12 px,
przycisków-pigułek, emoji, siatek ikon, małych etykiet nad każdym nagłówkiem, liczników „500+”, sliderów w hero,
preloaderów, strzałki „przewiń”, gigantycznego napisu w stopce, kursywnego wyróżnienia słowa w każdym nagłówku,
cyfr 01/02/03 poza prawdziwą listą `<ol>`. Linie 1 px zamiast pudełek. Tekst domyślnie do lewej.

### 7.6 Klasy bazowe dla autorów sekcji (`01-baza.css`, `02-uklad.css`)

`.wrap` (kontener 1440 z marginesem), `.section` / `--sm` / `--lg` / `--tint` / `--dark`, `.section__head` (mocna linia 1 px
na górze, h2 w kolumnach 1–7, `.section__lead` w 8–12 od 960 px), `.section__wiecej` (link „Wszystkie …”), `.siatka-12`,
`.prose` (65ch), `.lead`, `.meta`, `.num` (cyfry tabelaryczne), `.tabela`, `.btn` + `.btn--primary` / `.btn--secondary`,
`.pole` (etykieta nad polem), `.status`, `.lista-linkow`, `.wizualnie-ukryte`, `.nowrap`, `.foto` (zdjęcia z `obraz`).
Nowa sekcja dostaje własny plik `assets/css/czesci/1x-<sekcja>.css` z klasami w stylu BEM (`.oferta__pozycja`).

---

## 8. Obrazy (`obraz:"wariant"`)

| Wariant | `sizes` | Ładowanie |
|---|---|---|
| `hero` | `100vw` (lub `(min-width:960px) 58vw, 100vw` w układzie dzielonym) | `fetchpriority="high"`, bez `loading` |
| `pol` | `(min-width:960px) 50vw, 100vw` | `loading="lazy"` |
| `tercja` | `(min-width:960px) 33vw, (min-width:600px) 50vw, 100vw` | lazy |
| `miniatura` | `(min-width:600px) 240px, 50vw` | lazy |
| `pelny` | `100vw` | lazy |

Wynik: `<picture><source type="image/avif" srcset=…><source type="image/webp" srcset=…><img src=…jpg srcset=…
sizes=… width=… height=… alt=… decoding="async"></picture>`, z `<source media="(max-width:599px)">` gdy jest
`kadr_mobilny`. Brak wariantów w manifeście → w `--produkcja` błąd, poza nim ostrzeżenie i `<img>` z oryginałem.
Hero nigdy nie jest tłem CSS.

---

## 9. Build (`tools/build.py` + `tools/silnik/`)

| Moduł | Odpowiada za |
|---|---|
| `szablony.py` | parser i render składni z §3, filtry, typografia (import z `typografia.py`) |
| `typografia.py` | §3.2, formatowanie telefonu, ceny, dat po polsku, `liczba_mnoga` |
| `dane.py` | wczytanie `data/*`, walidacja schematem, kontrole semantyczne (NIP/REGON/KRS, kod pocztowy, HH:MM, geo, wymagane pola presetu i formy prawnej), wyliczenie kontekstu `auto` |
| `schemat.py` | mini-walidator JSON Schema z polskimi komunikatami |
| `kolory.py` | OKLCH → tokeny, kontrast WCAG |
| `obrazy.py` | odczyt wymiarów (stdlib), render `<picture>` |
| `jsonld.py` | `@graph`: WebSite, LocalBusiness/Organization (z godzinami, `geo`, `sameAs`, `areaServed`, `legalName`, `taxID`, `logo`), BreadcrumbList, Article, JobPosting; FAQPage tylko przy `funkcje.faq_schema` i tylko na stronie z sekcją `faq` (główna); nigdy `aggregateRating`/`review` |
| `naglowki.py` | `_headers` (CSP z sha256 skryptu inline i adresami tylko włączonych funkcji — ramka OSM przy `mapa: "po_kliknieciu"`, Cloudflare Web Analytics przy `statystyki_cf_token`; HSTS; noindex dla `adres_roboczy` i zawsze dla `https://:nazwa.:konto.workers.dev/*`), `_redirects` (z `firma.przekierowania`; zasłonięcie budowanej strony = błąd, cel bez strony = ostrzeżenie), `robots.txt`, `sitemap.xml`, `.well-known/security.txt`, `site.webmanifest`, `aktualnosci.xml` (RSS 2.0, `funkcje.rss`) |
| `zasoby.py` | sklejanie CSS/JS, `?v=`, kopiowanie `assets/` do `dist/`; CSS bez komentarzy źródeł (zostają `slop-ok`), a po renderze z plików sekcji `czesci/1*.css` znikają reguły bloków BEM, których nie ma w żadnym `class="…"` stron ani w JS (klasy w `:not()`/`:has()` nie przesądzają) — nowy skrót `?v=` trafia do stron |
| `kontrole.py` | kontrole wyniku (§10) |
| `strony.py` | lista stron do zbudowania, nawigacja, okruszki, meta (tytuł, opis, OG) |
| `komunikaty.py` | zbieranie komunikatów (BŁĄD / OSTRZEŻENIE / INFO / UKRYTO), eskalacja w `--produkcja`, wyjście JSON |
| `oferta.py` | oferta, cennik, karta, produkty: `auto.oferta/cennik/menu/produkty`, kontrole danych (§4.2.1), JSON-LD (Menu, Product z ceną, OfferCatalog, Service), `og:image` podstrony usługi |
| `pliki.py` | pliki na stronie (do pobrania, karta/cennik w PDF, skany certyfikatów): typ, rozmiar („8,4 MB”, „240 kB”), liczba stron PDF (`/Type /Pages` → `/Count`, także w strumieniach `/ObjStm`; nieczytelna = brak liczby, nie błąd) |

### 9.1 Kontekst szablonów

`firma`, `tresc`, `zdjecia` (słownik id → wpis), `preset`, `funkcje` (= `firma.funkcje`), `strona` (bieżąca: `sciezka`,
`tytul`, `opis`, `h1`, `okruszki`, `og_obraz`, `kanoniczny`, `indeksuj`), `nav`, `aktualnosci` (lista wpisów),
`auto` — wartości wyliczone:
`auto.telefon` (wyświetlanie), `auto.tel_href`, `auto.adres_linia`, `auto.adres_html`, `auto.trasa_url`
(`https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>`), `auto.osm_url`, `auto.godziny_tabela`
(lista `{dzien, dzien_krotki, kod, przedzialy_tekst, zamkniete}`), `auto.godziny_skrot` („pn.–pt. 7:00–15:00”),
`auto.status_start` (tekst statusu wyliczony w czasie buildu jako fallback bez JS: pusty — status wstawia tylko JS),
`auto.rejestr_linie` (linie danych rejestrowych do stopki wg formy prawnej — gotowy HTML, bez adresu: adres siedziby
stoi raz, w kolumnie „Dane kontaktowe” stopki), `auto.rok`, `auto.cta_glowne`, `auto.cta_drugie`,
`auto.pasek_mobilny`, `auto.telefon_w_naglowku`, `auto.jsonld` (surowy JSON), `auto.inline_js`,
`auto.logo` (`{src, szer, wys, alt}`; `szer`×`wys` = rozmiar w nagłówku ≥ 960 px, plik ma 3× tyle), `auto.naglowki` (domyślne nagłówki sekcji z presetu), `auto.podstrony` (zbiór
zbudowanych ścieżek — do linków „Wszystkie…”), `auto.formularz` (`{tryb, akcja, mailto_href, adresat, zgoda_checkbox}`).
Dodatkowo: `auto.telefon_krajowy`, `auto.telefon_e164`, `auto.email_href`, `auto.osm_embed`,
`auto.adres_linia_html` (adres w jednym wierszu jako HTML z nierozdzielnym kodem; `auto.adres_linia` = zwykły tekst do atrybutów
i meta), `auto.kontakt_wiecej` (tekst linku ze skrótu kontaktu do `/kontakt`, np. „Telefony działów i zapytanie e-mailem”;
`null`, gdy `/kontakt` nie ma nic więcej), `auto.godziny_dodatkowe`
(`[{nazwa, tabela, skrot}]`), `auto.godziny_wyjatki` (najbliższe 60 dni), `auto.pokaz_status`, `auto.status_w_hero`,
`auto.godziny_osobno` (jest osobna sekcja godzin na głównej), `auto.social` (`[{nazwa, url}]`), `auto.zdjecia_autorzy`,
`auto.ogloszenie` (aktywne dziś albo `null`), `auto.logo_na_ciemnym`, `auto.ikony` (które pliki ikon istnieją),
sekcje o firmie (`dane.auto_firma`): `auto.zespol` (`{osoby: [… + pokaz_zdjecie], portrety}` — portrety = każda osoba ma
zdjęcie ze zgodą; `null` bez osób),
`auto.polityka_prywatnosci_data`, `auto.dostepnosc_data` (data ostatniej zmiany `data/firma.json` albo szablonu strony
z historii git — „Stan na” w dokumencie; nie data buildu), `auto.liczby` (pozycje + `wartosc_tekst`; `null`, gdy < 2), `auto.opinie` (cytaty +
`serwis` z adresu: „Google”, „Facebook”…), `auto.certyfikaty` (tylko ważne, + `plik_info` `{typ, rozmiar}`; `null`, gdy brak),
`auto.o_firmie_podpis` (podpis zdjęcia sekcji z `zdjecia.json`), `auto.o_firmie_wiecej` (tekst linku ze skrótu na głównej
do `/o-firmie` — wymienia tylko to, czego na głównej nie ma; `null` bez podstrony). `dane.plik_info()` (typ i rozmiar) i
`auto.do_pobrania` liczy ten sam moduł `pliki.py`,
`auto.godziny_zestawy` (nazwy kolumn: `godziny.nazwa` albo `null`, potem nazwy `dodatkowe`), `auto.godziny_wiersze`
(`[{kod, dzien, dzien_krotki, zamkniete, komorki:[{tekst, html, zamkniete}]}]`; `html` — przedziały w `.nowrap`),
w `auto.godziny_wyjatki` dodatkowo `dzien_tygodnia` i `kiedy` („śr. 14 października”), `auto.do_pobrania`
(`[{plik, opis, typ, mime, rozmiar, strony, strony_tekst, meta}]` — `meta` = „PDF, 8,4 MB, 48 stron”, `tools/silnik/pliki.py`),
`auto.gdzie_kupic` (`[{wojewodztwo, nazwa, punkty:[… + adres_html]}]`), `auto.kariera` (aktualne oferty + `slug`,
`html_id`, `mailto` z tematem „CV – stanowisko”), `auto.kariera_kontakt` (`{osoba, email, tel_href, telefon_krajowy, mailto}`),
`auto.kariera_stanowiska`, `auto.wspolpraca_mailto`, `auto.rss` (`funkcje.rss` i jest `/aktualnosci` → `/aktualnosci.xml`
i `<link rel="alternate">`), `strona.element` (element kolekcji — do JSON-LD Article),
`auto.kolor_tla`, `auto.tokeny`, `auto.fonty_preload`, `auto.sekcje_widoczne`, `auto.dzis`.
Realizacje, przetargi i galeria (`dane.auto_realizacje`; brak danych = `null`):
`auto.realizacje` = `{pozycje, liczba, kategorie: [{slug, nazwa, liczba}] (tylko z pozycjami), filtr}` — pozycja ma pola z danych
oraz `tytul_pelny`, `klient_tekst`, `kategoria_nazwa`, `zdjecia: [{id, podpis}]`, `zrodlo_url`, `zrodlo_host`;
`auto.przetargi` = `{pozycje (od najnowszych, z nowy_rok, zrodlo_url, zrodlo_host, zrodlo_tekst), liczba, rok_od, rok_do,
zamawiajacych, z_wartoscia, z_linkami, bzp_url}`; `auto.galeria` = `[{id, podpis}]`.
`auto.cta_*` i elementy `auto.pasek_mobilny` mają postać `{tekst, href, typ, zewnetrzny, zrodlo}`; `href` w danych: `tel`, `trasa`,
`kontakt`, `katalog`, ścieżka (`/menu`; bez podstrony → kotwica `/#menu`) albo `tel:+48…`; `{tel}` w tekście = numer.
Przycisk hero, który prowadzi do nieistniejącej podstrony i sekcji, zatrzymuje build błędem danych z polem `hero.cta_*.href`.
Adresy plików w szablonach zawsze przez filtr: `{{ "assets/css/strona.css" | zasob }}` (nie ma `auto.css`/`auto.js`).

`auto.bez_domeny` (strona pod `adres_roboczy`, noindex), `sekcja.klasa` (wariant z presetu, tylko główna),
`auto.oferta` (`pozycje` z `url` podstrony usługi albo `null`, `podpis` zdjęcia i `cena_w_cenniku`, `skrot`,
`skrot_zdjecia` — każda pozycja skrótu ma zdjęcie, `wiecej`, `naglowek`, `nazwy`
— „roboty drogowe, … i prefabrykaty” do opisów stron, `cta`, `powrot`), `auto.cennik` (`grupy`/`skrot` z `ma_czas`, `liczba`,
`netto`, `pdf` = `{href, typ, rozmiar, strony, tekst}`, `wiecej`), `auto.menu` (`kategorie`/`skrot` z `znaki` przy pozycjach,
`legenda`, `legenda_skrot`, `alergeny`, `nazwy`, `pdf`, `wiecej`, `uwagi`, `ceny_w_lokalu`), `auto.produkty` (`pozycje`
z `kategoria_nazwa`, `skrot`, `skrot_listy`, `grupy` z `liczba` i `listy` — `[{zdjecia, pozycje}]`: najpierw ze zdjęciem,
potem bez, `filtr`, `ma_ceny`, `ma_zdjecia`, `brutto_we_wstepie`, `nazwy`, `wiecej`); `null`, gdy bloku nie ma. JSON-LD: pełny `Menu` tylko na stronie
z pełną kartą (firma: `hasMenu`), `Product` tylko z ceną (na stronie z pełną listą), `hasOfferCatalog` na głównej i `/oferta`.

### 9.2 Tryby

`--szybko` (render + walidacja, bez kontroli wyniku), domyślnie (`--sprawdz`: wszystko, ostrzeżenia nie przerywają),
`--produkcja` (ostrzeżenia z klas B/C → błędy; `przyklad: true` → błąd; teksty z `przyklady/` w wyniku → błąd),
`--klient <katalog>`, `--wyjscie <katalog>` (domyślnie `dist/` w repozytorium), `--plik` (linki względne z `.html` do
podglądu z dysku), `--json` (komunikaty jako JSON dla AI). Ścieżki względne w `--klient` i `--wyjscie` liczą się tak samo:
od bieżącego katalogu, a gdy tam ich nie ma — od korzenia repozytorium.

**Katalog wyniku.** Build zapisuje w nim plik `.szablon-wynik` (i `.assetsignore`, żeby znacznik nie trafił na serwer).
Przy następnym buildzie usuwa wyłącznie katalog z tym znacznikiem (albo pusty; wynik sprzed znacznika rozpoznaje po
`_headers` + `index.html` + `assets/css/strona.css`). Nigdy nie usuwa katalogu z plikami śledzonymi przez git, katalogu
repozytorium, klienta, domowego ani żadnego z ich katalogów nadrzędnych — wtedy błąd (kod 1) z poleceniem, co zrobić.

Kod wyjścia: 0 = OK, 1 = błędy danych/kontroli, 2 = błąd wewnętrzny.
Błędy danych (schemat, pola wymagane, kontrast) zatrzymują build przed renderem — wtedy wypisywana jest pełna lista braków.
Zmienna środowiska `SZABLON_DZIS=RRRR-MM-DD` ustawia „dziś” (testy ogłoszeń, wyjątków godzin, `security.txt`); zła data = kod 1.
Komunikaty zbiera `tools/silnik/komunikaty.py` (poziomy BŁĄD / OSTRZEŻENIE / INFO / UKRYTO; ostrzeżenia klasy „A”
— np. zalecane pola presetu — zostają ostrzeżeniami także w `--produkcja`).
Podgląd: `python3 tools/podglad.py` (adresy bez `.html`, 404 ze statusem 404, nagłówki z `_headers` — wczytywane ponownie
po każdym buildzie),
zrzuty i kontrola przewijania/konsoli: `node tools/zrzuty.cjs http://localhost:8765 <katalog> <prefiks>`.

---

## 10. Kontrole wyniku (`kontrole.py`)

Błąd (zawsze): pozostałości szablonu (§1.4); `<img>` bez `alt`/`width`/`height`; więcej niż jeden `h1`; przeskok
poziomu nagłówka; zduplikowane `id`; link wewnętrzny do nieistniejącej strony/kotwicy; `style=""` lub `<style>`;
inline `<script>` inny niż jeden dozwolony; JSON-LD z `<!--` albo `<script`; zasób zewnętrzny (http z innej domeny)
w `src`/`href` poza linkami; adres w `href`/`src`/`srcset`/`data-src`/`action`/`og:url`/`og:image` z twardą spacją, `–`, `—`,
`„` albo `”` (typografia zepsuła link); `tel:` nie w E.164; kontrast tokenów; brak `og:image` lub względny; HTML > 100 KB;
brak danych rejestrowych dla formy prawnej.
Już na etapie danych (z nazwą pola, przed renderem): `{{`, `{%`, `{#`, `[UZUPEŁNIJ`, `TODO`, `Lorem`, `XXX` w dowolnym
tekście `data/*.json` i `data/**/*.md` (bez `$…`, `zrodla`, `do_potwierdzenia`); nieistniejąca data; nakładające się godziny.

Ostrzeżenie (w `--produkcja` błąd): `title` > 60 zn. (sprawdza `build.py`, także w `--szybko`), `description` poza 110–160 zn.
(strona główna), zdjęcie > 250 KB (AVIF/WebP) / > 400 KB (JPEG), CSS > 60 KB, JS > 30 KB, strona główna > 9 sekcji,
`cennik.data`/`menu.data` > 12 miesięcy.
Limit 9 sekcji strony głównej nie liczy `ogloszenie` (pasek na kilka dni).

Błąd danych modułów (przed renderem): plik z `do_pobrania` nie istnieje albo leży poza `assets/img/`; nieznane pole
w nagłówku wpisu; zdjęcie wpisu spoza `zdjecia.json`; `kariera.pozycje[].opublikowano` późniejsze niż `wazne_do`;
województwo zakończone na „kie” spoza listy 16 (literówka rozbiłaby grupę w „Gdzie kupić”).

Ostrzeżenie klasy A (nie blokuje także w `--produkcja`): aktualności starsze niż 12 miesięcy (zapowiedź na głównej i tak
znika — nocny build nie może stanąć tylko dlatego, że firma rok nic nie napisała), zalecane pola presetu, `tytul_tryb: "marka"`, `hosting: "github_pages"`
(bez `_headers`), `do_potwierdzenia` niepuste (D10 — lista idzie do README „Do potwierdzenia z właścicielem”; niepewny
fakt jest `null` albo oznaczony jako poglądowy), godziny świąteczne niepotwierdzone w ciągu 45 dni (`swieta.py`, D12).

**Przeciek przykładu** (`--produkcja`, klient spoza `przyklady/`): błąd, gdy na stronie są dane z `przyklady/*/data` —
nazwa prawna, `firma.opis`, `seo.opis`, domena, e-maile, telefony, NIP/KRS/REGON, ulica z kodem pocztowym, nagłówek i lead
hero oraz zdania ≥ 30 znaków z pól opisowych (`opis`, `lead`, `wstep`, `podpis`, `alt`, `zadanie`…) i z plików `.md`.
Porównanie po widocznym tekście (plus `alt`, `title`, `aria-label`, meta description / `og:*`) bez typografii (twarde spacje,
„…”, półpauzy znormalizowane po obu stronach); nie porównujemy słów branżowych, `marka.*` (kroje, kolory), id ani wartości
wyliczeniowych. Jeden komunikat na pole przykładu z listą stron.

Informacja: lista `UKRYTO`, liczba stron, rozmiary.

Po kontrolach build uruchamia `tools/lint_slop.py dist/ data/` (P0 = błąd, P1 = ostrzeżenie/błąd w `--produkcja`
bez `slop-ok`, P2 = informacja).

**`lint_slop.py`** (tylko biblioteka standardowa): widoczny tekst, `alt`/`title`/meta i CSS z `dist/` oraz napisy z
`data/*.json` i `data/**/*.md` (bez notatek `zrodla`, `do_potwierdzenia`…). Wynik ze strony dostaje ścieżkę pola danych
(`data/tresc.json → hero.lead`), napis, którego nie ma na stronie, spada do P2. Build woła go z `--json`: P0 → błąd,
P1 → ostrzeżenie klasy B, P2 → jedna linia INFO. Katalog reguł: `python3 tools/lint_slop.py --reguly`.
Zwolnienia tylko dla P1/P2 w `data/slop-ok.json`: `[{"id": "V-NUMERY-01", "powod": "≥ 10 znaków: dlaczego to nie szablon",
"gdzie": "fragment ścieżki, pola albo cytatu (opcjonalnie)"}]`; w CSS także komentarz `/* slop-ok: ID powód */` w wierszu
reguły. Zwolnienie bez powodu i zwolnienie P0 = P1, nieużyte = P2. Kod wyjścia: 2 = P0, 1 = P1 w `--produkcja`, 0.

**`swieta.py`**: dni wolne (z Wigilią od 2025 r.), Wielka Sobota i Sylwester, niedziele handlowe (zawsze „do potwierdzenia”);
`python3 tools/swieta.py 2027`. Build (`dane.kontrole_swiat`, tylko presety z `pokazuj_status_w_hero`): święto za ≤ 45 dni,
w dzień zwykle otwarty, bez wpisu w `godziny.wyjatki` → ostrzeżenie klasy A „POTWIERDŹ: godziny na 24.12 (Wigilia)” (`--produkcja` przechodzi, D12).
Testy: `python3 -m unittest discover -s tools/testy`.

---

## 11. JS (`assets/js/czesci/*.js` → `dist/assets/js/strona.js`, `defer`)

Każdy plik to samodzielny blok `(() => { … })();` bez zależności. Strona działa bez JS.
Jedyny skrypt inline (w `<head>`): `document.documentElement.classList.add('js')` — jego sha256 build wpisuje do CSP.

| Plik | Funkcja | Haki w HTML |
|---|---|---|
| `10-menu.js` | menu na telefonie: `button.nav-toggle[aria-expanded][aria-controls=nav]`, Esc zamyka i wraca fokus, klik w link zamyka | `.site-header`, `#nav` |
| `20-godziny.js` | status „Otwarte do 15:00 / Zamknięte. Otwieramy jutro o 7:00” w Europe/Warsaw z JSON-LD `openingHoursSpecification` (+ `specialOpeningHoursSpecification`), kilka przedziałów, po północy (`closes` `23:59` = „24:00”), odświeżanie co 60 s, podświetlenie dzisiejszego wiersza (`.is-dzis`, `aria-current="date"`) | `[data-status]` (element z `aria-live="polite"`, opcjonalnie `data-nazwa="Kuchnia"`), `tr[data-dzien="pn"]` |
| `30-pasek.js` | pasek mobilny pokazuje się dopiero, gdy nie widać tych samych akcji (przyciski hero, kontakt w stopce); schowany jest `inert` | `.callbar` (`.is-widoczny`), `[data-ukryj-pasek]` |
| `40-mapa.js` | „Pokaż mapę” → iframe OSM dopiero po kliknięciu; ramka zastępuje opis i przycisk, link „Otwórz mapę w OpenStreetMap” zostaje, fokus przechodzi na ramkę | `[data-mapa]` z `data-src`, `data-tytul`, `.mapa__opis`, `button` |
| `50-filtr.js` | filtr realizacji/produktów po kategorii z `?kategoria=` w URL (klik filtruje w miejscu, `history.replaceState`, `aria-current="true"` na aktywnym linku, komunikat „Pokazano 6 z 24” w regionie `aria-live`; nieznana kategoria = wszystkie; bez JS filtra nie widać, lista jest cała); „Pokaż więcej” (zwija elementy ponad limit klasą `.is-zwiniete`, przycisk pokazuje JS, po kliknięciu fokus na pierwszy odsłonięty; bez JS i na wydruku widać wszystko); role ARIA tabel, które na telefonie układają się w stos | `[data-filtr]` z linkami `a[data-kategoria]` (`""` = wszystkie) i elementami `[data-filtr-element="slug"]`, `[data-filtr-status]`; `[data-wiecej][id]` z `[data-wiecej-reszta]` + `button[data-wiecej-przycisk][aria-controls=id][hidden]`; `table[data-stos]` |
| `60-formularz.js` | wysyłka `fetch` → JSON; 503 → otwarcie `mailto:`; błędy przy polach (`aria-invalid`, `aria-describedby`), fokus na pierwszy błąd | `form[data-formularz]` |
| `70-ogloszenie.js` | ukrywa ogłoszenie dzień po dacie `data-do` między buildami („dziś” w Europe/Warsaw, sprawdzane też co 15 min) | `[data-do="RRRR-MM-DD"]` |
| `80-ruch.js` | nie istnieje — wejście hero jest w samym CSS (`91-ruch.css`): `<html class="ruch">` wpisuje build przy `funkcje.animacje: "wejscie"`, animacja działa tylko z klasą `js` i pod `prefers-reduced-motion: no-preference` (akapit pod h1 — nie przy hero bez zdjęcia, adres/status, przyciski; nigdy h1 ani zdjęcie), plus `@view-transition` między podstronami | `html.ruch.js` |

**Filtr produktów (`/produkty`, `sekcje/produkty.html`):** `div.produkty__katalog[data-filtr]` → `nav.filtr` z linkami
`a[data-kategoria="<slug>"][href="?kategoria=<slug>#kategoria-<slug>"]` (pierwszy: „Wszystkie”, `data-kategoria=""`,
`aria-current="true"`, `href="/produkty"`), grupy `div.produkty__grupa#kategoria-<slug>[data-kategoria]` z nagłówkiem
kategorii i produkty `li.produkt[data-kategoria]`. Bez JS link przewija do grupy; skrypt filtruje w miejscu, ustawia
`aria-current` na wybranym linku i czyta `?kategoria=` przy wejściu. Filtr tylko na podstronie i tylko przy ≥ 2 grupach.

---

## 12. Worker (`worker/index.js`, `wrangler.jsonc`)

Szczegóły wdrożenia: `docs/CLOUDFLARE.md`, wysyłka: `docs/FORMULARZ.md`, test: `node tools/test_worker.mjs`.
`wrangler.jsonc`: `assets.directory ./dist`, `run_worker_first ["/api/*"]`, `html_handling auto-trailing-slash`,
`not_found_handling 404-page`, build `python3 tools/build.py --produkcja`, `ratelimits` `LIMIT_KONTAKT` (5 / 60 s),
`triggers.crons ["17 2 * * *"]` (UTC). Zmienne: `RESEND_API_KEY` (sekret), `ADRESAT`, `NADAWCA`, `DEPLOY_HOOK_URL` (sekret).
Odpowiedź JSON: sukces `{"ok":true}`, błąd `{"ok":false,"blad":"<kod>","komunikat":"<zdanie po polsku>"}`
(403 `origin`, 405 `metoda`, 400 `zle_dane`, 413 `za_duze` (Content-Length > 16 KB), 422 `brak_pol` + `pola` /
`kontakt` / `za_dlugie`, 429 `limit`, 502 `wysylka`, 503 `nie_skonfigurowano` + `brakuje`); bez `Accept: application/json`
— 303 na `/dziekujemy` albo stronę błędu z `?powod=<kod>`: `/blad-formularz` (`brak_pol`, `kontakt`, `za_dlugie`,
`za_duze`, `zle_dane`), `/blad-konfiguracja` (`nie_skonfigurowano`: przycisk mailto z gotową wiadomością i telefon),
`/blad` (reszta). Obie strony `blad-*` powstają tylko przy `funkcje.formularz.tryb = "worker"`.
Reply-To tylko, gdy `kontakt` jest zwykłym adresem e-mail (`[A-Za-z0-9._%+-]+@…`, bez przecinków i nawiasów).
Temat w jednej linii (bez `\r\n`, U+0085, U+2028/2029 i znaków sterujących).
_headers nie działa dla odpowiedzi Workera — Worker sam ustawia `no-store`, `nosniff`, `noindex`.

Tylko `/api/*` (`run_worker_first`). `POST /api/kontakt` (tę ścieżkę ma `auto.formularz.akcja`): sprawdzenie Origin (adres
strony albo jego wariant z/bez `www`; bez nagłówka Origin wystarczy `Sec-Fetch-Site: same-origin`, bez obu — 403),
limit 5/min/IP, pole-pułapka `strona_www`, czas wypełnienia ≥ 3 s (`t` = ile ms formularz był otwarty; ujemny albo pusty
nie jest odrzucany), limity długości, > 5 linków = spam, sztuczne „ok” dla botów,
Reply-To = nadawca; JSON dla `Accept: application/json`, inaczej 303 → `/dziekujemy` lub `/blad`.
Bez skonfigurowanego Resend → 503 `{"blad":"nie_skonfigurowano"}` (JS otwiera `mailto:`).
`scheduled()` — nocny build przez Deploy Hook (sekret `DEPLOY_HOOK_URL`), żeby daty (ogłoszenia, święta, © rok,
`security.txt`) były aktualne. Sekrety tylko w Cloudflare.

---

## 13. Pola formularza (stała umowa HTML ↔ JS ↔ Worker)

`imie` (text, `autocomplete="name"`, wymagane), `kontakt` (telefon lub e-mail, `autocomplete="tel"`… wymagane),
`wiadomosc` (textarea, wymagane, ≤ 3000 zn.), `strona_www` (pułapka, ukryta, `tabindex="-1"`, `autocomplete="off"`),
`t` (hidden; JS wpisuje przy wysyłce, ile milisekund formularz był otwarty — `performance.now()`, nie zegar odwiedzającego;
bez JS pusty — Worker wtedy nie odrzuca za czas).
Pod formularzem klauzula informacyjna (art. 13 RODO) i link do polityki. Pole `zgoda` (tylko przy
`zgoda_checkbox: true`) potwierdza zapoznanie się z klauzulą, nie jest zgodą i nie jest wymagane (D7).

---

## 14. Narzędzia personalizacji i kontroli (AI)

| Narzędzie | Wejście → wynik |
|---|---|
| `tools/sprawdz.sh [--klient K] [--wyjscie D] [--raport R] [--port N] [--url https://…] [--linki] [--bez-lighthouse] [--szybko]` | build (`--produkcja`; klient z `przyklady/` albo `przyklad: true` → `--sprawdz`) → `R/build.json`; podgląd; `zrzuty.cjs` na każdej stronie + `/nie-ma-takiej`, a na stronach kluczowych (`/`, pierwsza z `/oferta /menu /produkty /realizacje`, `/kontakt`) także bez JS i z wymuszonymi kolorami → `R/zrzuty/`, `R/zrzuty*.json`; html-validate; pa11y (axe, WCAG2AA) na każdej stronie → `R/pa11y/`; Lighthouse telefon + komputer na stronach kluczowych → `R/lighthouse/<strona>-<telefon\|komputer>.json` (cel: a11y/BP/SEO = 100, wydajność ≥ 90); `--url`: skan wstrzyknięć Cloudflare i nagłówków → `R/produkcja.json`; statusy kroków → `R/kroki.tsv`; na końcu `raport.py`. Brak narzędzia = POMINIĘTO z poleceniem instalacji. Kod 1 = któryś krok BŁĄD |
| `tools/zrzuty.cjs` | zmienne: `ZRZUTY_TRYBY=bezjs,wymuszone[,tylko]`, `ZRZUTY_JSON=<plik>` (przewijanie, konsola, obce domeny, ciasteczka, localStorage, żądania i bajty pierwszego widoku), `ZRZUTY_LIMIT_S` (limit na widok, 90 s). Pierwszy ekran 375 px (`*-375*-ekran.png`) z paskiem „Zadzwoń”; na zrzutach całej strony pasek ukryty. Przewijanie przez Playwright (działa bez JS) |
| `tools/sprawdz.sh` — środowisko | `SZABLON_NODE_PREFIX` (narzędzia Node z `npm i -g --prefix …`), `CHROMIUM`, `SZABLON_LIMIT_KROKU_S` (900 s); lista brakujących narzędzi na początku; `trap` zamyka podgląd i przeglądarki; podgląd z przerwanego uruchomienia na tym porcie zamyka sam |
| `tools/start.py --branza B [--klient K] [--nadpisz] [--tylko-dane]` | szkielet `data/*.json`; nietknięty szkielet zastępuje bez `--nadpisz`; README SZABLONU → README klienta (tabela „Co i gdzie zmienić” dla branży, znaczniki „Do potwierdzenia”); `namespace_id` „1101” → losowe |
| `tools/zrodla.py [--klient K] --faza 0\|1` | koniec faz 0–1: „Braki” wypełnione; wiersze „Fakty” z wartością, źródłem (bez „…” wzoru) i datą dla nazwy, adresu, telefonu, danych rejestrowych |
| `tools/skill.py [--sprawdz]` | `.claude/skills/personalizuj/SKILL.md` = nagłówek + `docs/PROCEDURA.md` |
| `tools/raport.py [--raport R] [--klient K] [--wyjscie D] [--readme] [--json]` | `R/KARTA-JAKOSCI.md` i `.html`; `--readme` podmienia w `K/README.md` blok między `<!-- do-potwierdzenia:poczatek -->` a `<!-- do-potwierdzenia:koniec -->` (albo dopisuje sekcję) |
| `tools/co_zawiera.py [--klient K] [--wyjscie P]` | bez `--klient`: `docs/CO-ZAWIERA-STRONA.md` (lista `LISTA` w skrypcie — tylko funkcje, które istnieją); z `--klient`: `raport/CO-ZAWIERA-STRONA.md` z „Jest / Do włączenia” (build `--szybko` do katalogu tymczasowego) |
| `tools/kolory.py logo <plik>` / `raport "#hex" [--tlo] [--dodatkowy] [--klient K] [--json]` | kandydaci na kolor z logo (Pillow; SVG bez Pillow) / tokeny z `silnik/kolory.py` i kontrast par (kod 1, gdy para nie przechodzi) |
| `tools/aktualizuj.py --wersja REF [--szablon DIR] [--bazowa REF] [--proba]` | kopiuje pliki silnika (lista w skrypcie) z repozytorium git SZABLONU; odmawia (kod 1) i wypisuje pliki, gdy klient zmienił silnik względem wersji bazowej (`v<SZABLON_WERSJA>`); `wrangler.jsonc` → `wrangler.jsonc.szablon`; `.gitignore` — dopisuje brakujące wiersze; potem `build.py --sprawdz` |
| `.claude/hooks/po_edycji.py` (PostToolUse `Edit\|Write\|MultiEdit`) | zmiana w `data/ src/ assets/ tools/presety\|schemat\|silnik/ przyklady/` → `build.py --szybko --json` do katalogu tymczasowego; błędy do Claude'a przez `hookSpecificOutput.additionalContext`; kod zawsze 0. W repozytorium SZABLON (szkielet w `data/`) zmiana silnika buduje pierwszy przykład |
| `.claude/hooks/przed_koncem.py` (Stop) | `build.py --sprawdz` (klient albo każdy przykład) → przy błędach `{"decision":"block","reason":…}`; `stop_hook_active` i licznik (maks. 3 blokady na sesję) chronią przed pętlą |

## 15. Testy (`tools/testy/`)

`python3 tools/testy/uruchom.py` (= `cd tools/testy && python3 -m unittest discover -p "test_*.py"`), tylko biblioteka
standardowa, ok. 5 s. „Dziś” testów, fikstur i CI to `DZIS` w `tools/testy/_wspolne.py` (`SZABLON_DZIS` w
`.github/workflows/sprawdz.yml` ma tę samą datę).

| Plik | Sprawdza |
|---|---|
| `test_szablony.py` | składnia §3 (błędy z numerem wiersza), filtry §3.1, escapowanie, typografia §3.2 (także: adres bez twardych spacji), pozostałości w danych i w `dist/` (`kontrole.sprawdz` na ręcznie zbudowanej stronie) |
| `test_dane.py` | NIP/REGON (sumy kontrolne), formaty ze schematu (KRS, kod, E.164, godzina, data z kalendarzem), nieznane pola, godziny (kilka przedziałów, po północy, nakładanie w dniu i między dniami, niedziela → poniedziałek), forma prawna §4.1 |
| `test_kolory.py` | każda para tokenów §7.2 dla 18 kolorów marki × 5 teł × 3 kolory dodatkowe; żółty, biel, czerń |
| `test_jsonld.py` | `openingHoursSpecification` na przedział, „24:00” → „23:59”, wyjątki, `Organization` + `LocalBusiness`, brak `aggregateRating`/`review`, FAQPage tylko z `faq_schema` |
| `test_build.py` | build `przyklady/bimex` i fikstur (strony, pliki, nagłówki, sitemap), tryby `--produkcja`/`--szybko`/`--plik`, szkielety `start.py` każdej branży (polskie komunikaty o brakach), nietknięty szkielet bez `--nadpisz`, README klienta, `data/` repozytorium = szkielet „uslugi” |
| `test_narzedzia.py` | `tools/zrodla.py` (wzór nie przechodzi, wypełniony tak), `tools/skill.py --sprawdz` |

**Fikstury** `tools/testy/klienci/<branza>/` (restauracja, producent, uslugi, gabinet; budowlaną sprawdza
`przyklady/bimex`): wymyślone firmy z danymi dla każdego modułu presetu, `"przyklad": true`, zdjęcia zastępcze.
Źródłem jest `tools/testy/klienci/generuj.py` (opis i lista fikcyjnych numerów: `tools/testy/klienci/README.md`).
Autor nowej sekcji dopisuje jej dane do fikstury swojej branży w `generuj.py` i uruchamia `generuj.py --tylko-dane`.
