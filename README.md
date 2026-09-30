# SZABLON — strona firmowa z danych, gotowa do personalizacji przez AI

SZABLON to repozytorium, z którego powstają strony małych i średnich firm: restauracji, firm budowlanych,
producentów, warsztatów, gabinetów. Strona to statyczny HTML budowany z kilku plików danych (`data/`) skryptem
w Pythonie (tylko biblioteka standardowa), publikowany na Cloudflare. Bez WordPressa, bez bibliotek JS, bez ciasteczek.

Szablon jest zrobiony tak, żeby można było **wysłać repozytorium do AI razem z danymi firmy i zdjęciami** i dostać
spersonalizowaną stronę: AI ma instrukcje (`AGENTS.md`, `CLAUDE.md`), procedurę krok po kroku (`docs/PROCEDURA.md`,
w Claude Code skill `/personalizuj`) i polecenia, które sprawdzają jej pracę (build, linter frazesów, zrzuty, axe,
Lighthouse). Sekcja bez prawdziwych danych nie powstaje — szablon nie ma tekstów zastępczych do „wypełnienia”.

Co dostaje klient (lista funkcji w prostym języku, do oferty): [`docs/CO-ZAWIERA-STRONA.md`](docs/CO-ZAWIERA-STRONA.md).
Wzór na prawdziwej firmie: `przyklady/bimex/` (`python3 tools/build.py --klient przyklady/bimex`).

## Nowy klient

1. Nowe repozytorium z szablonu (SZABLON oznaczony na GitHubie jako *Template repository*:
   `gh repo edit <konto>/SZABLON --template`):
   ```
   gh repo create <konto>/strona-<firma> --private --template <konto>/SZABLON --clone
   cd strona-<firma>
   ```
   Bez GitHuba: `git clone --depth 1 <adres SZABLONU> strona-<firma> && cd strona-<firma> && rm -rf .git && git init`
   (klon ma tylko pliki z repozytorium — bez `dist/`, `raport/` i roboczych katalogów agentów; `cp -r` przeniósłby je).
2. Wrzuć materiały do `brief/`: wypełniony `brief/BRIEF.md` (kwestionariusz dla właściciela), zdjęcia i logo do
   `brief/zdjecia/` (poza gitem), notatki, adresy strony / Facebooka.
3. Uruchom AI w katalogu repozytorium i poproś: „Spersonalizuj stronę dla tej firmy według docs/PROCEDURA.md”
   (Claude Code: `/personalizuj`).

## Jak pracuje AI (w pięciu zdaniach)

1. Czyta `brief/`, szuka faktów w źródłach publicznych (strona, Facebook, Google, KRS, BZP) i zapisuje każde źródło
   w `brief/zrodla.md`; o resztę pyta właściciela raz.
2. `python3 tools/start.py --branza …` tworzy puste dane (i README strony klienta w miejsce tego), AI wypełnia `data/firma.json` (fakty ze źródłem, kolor
   z logo przez `tools/kolory.py`), ogląda każde zdjęcie i opisuje je w `data/zdjecia.json`, potem `tools/zdjecia.py`.
3. Pisze `data/tresc.json` krótko i konkretnie; czego nie wie — zostawia `null` (sekcja znika) albo wpisuje
   do „Do potwierdzenia z właścicielem”.
4. Dobiera kroje, tło i jeden element-podpis w `assets/css/wlasne.css`, poprawia wszystko, co zgłasza
   `python3 tools/build.py --produkcja`.
5. `bash tools/sprawdz.sh` — zrzuty, dostępność, Lighthouse, karta jakości w `raport/`; AI ogląda zrzuty
   i kończy dopiero, gdy wszystko przechodzi (w Claude Code pilnują tego hooki).

## Struktura

```
AGENTS.md, CLAUDE.md      instrukcje dla AI (Claude Code: CLAUDE.md importuje AGENTS.md; Gemini: .gemini/settings.json)
brief/                    materiały od klienta: BRIEF.md, zrodla.md, zdjecia/ (oryginały poza gitem)       [klient]
data/                     firma.json, tresc.json, zdjecia.json, tresc/*.md, aktualnosci/*.md             [klient]
assets/img/               logo, zdjęcia po tools/zdjecia.py, ikony, pliki PDF                            [klient]
assets/css/wlasne.css     style tylko tego klienta (element-podpis)                                      [klient]
assets/css/czesci/, assets/js/czesci/, assets/fonts/   style, skrypty i kroje silnika                    [silnik]
src/                      szablony: układ, części, sekcje, podstrony                                    [silnik]
tools/                    build.py i silnik/, schematy danych, presety branż, narzędzia                 [silnik]
worker/, wrangler.jsonc   formularz (/api/*) i nocna przebudowa na Cloudflare                           [silnik]
docs/                     KONTRAKT (umowa silnika), PROCEDURA, DECYZJE, CLOUDFLARE, FORMULARZ, PRZEKAZANIE… [silnik]
przyklady/bimex/          pełny katalog klienta na prawdziwej firmie — do testów silnika                [silnik]
tools/testy/              testy silnika i klienci testowi czterech branż; CI: .github/workflows/sprawdz.yml [silnik]
dist/, raport/            wynik buildu i kontroli (generowane, poza gitem)
```

Pliki **[klient]** zmienia się przy każdej stronie. Pliki **[silnik]** zmienia się tylko w repozytorium SZABLON —
wtedy poprawka trafia do wszystkich stron (patrz „Aktualizacja”). Szczegóły: `docs/KONTRAKT.md` §2.

## Podgląd lokalny

```
python3 tools/build.py              # build z kontrolami → dist/
python3 tools/podglad.py            # http://localhost:8765 — adresy bez .html, strona 404, nagłówki z _headers
python3 tools/build.py --plik       # linki z .html — do otwarcia dist/index.html prosto z dysku (np. na iPadzie)
bash tools/sprawdz.sh               # pełna kontrola przed oddaniem → raport/ (wymaga Node: playwright, pa11y, lighthouse, html-validate)
python3 tools/testy/uruchom.py      # testy silnika + build przykładu i klientów testowych (tools/testy/klienci/)
```

Brakujące narzędzia `sprawdz.sh` wypisuje na początku i pomija (POMINIĘTO). Instalacja bez uprawnień do systemowego
Node: `npm i -g --prefix ~/.szablon-node playwright html-validate pa11y lighthouse linkinator && npx playwright install
chromium`, potem `SZABLON_NODE_PREFIX=~/.szablon-node bash tools/sprawdz.sh` (Chromium spoza Playwright: `CHROMIUM=…`). Build (`tools/build.py`) nie potrzebuje niczego poza Pythonem ≥ 3.10.
Do przygotowania zdjęć i krojów lokalnie: Pillow (`tools/zdjecia.py`, `tools/kolory.py logo`), fontTools (`tools/fonty.py`).

## Publikacja

Cloudflare Workers Builds: każdy push do gałęzi produkcyjnej uruchamia `python3 tools/build.py --produkcja`
i wdraża `dist/` (+ Worker dla formularza). Krok po kroku (konto, domena, przekierowanie www, ustawienia strefy,
sekrety, nocna przebudowa): `docs/CLOUDFLARE.md`. Formularz przez Resend: `docs/FORMULARZ.md`.
Przekazanie strony i kont klientowi: `docs/PRZEKAZANIE.md`.
Po publikacji: `bash tools/sprawdz.sh --url https://domena.pl` (czy Cloudflare nie wstrzykuje skryptów).

## Co i gdzie zmienić

| Co | Gdzie |
|---|---|
| Telefon, e-mail, adres, telefony działów | `data/firma.json` → `kontakt` |
| Godziny otwarcia, święta i wyjątki | `data/firma.json` → `godziny` (`wyjatki`: data, godziny, opis) |
| Ogłoszenie („24–26.12 nieczynne”) | `data/tresc.json` → `ogloszenie` (`tekst`, `od`, `do`) |
| Nagłówek i zdanie na pierwszym ekranie, zdjęcie | `data/tresc.json` → `hero` |
| Usługi, ceny, cennik, karta dań, produkty | `data/tresc.json` → `oferta`, `cennik`, `menu` (bez cen na stronie: `"ceny": "w_lokalu"`), `produkty` |
| Realizacje, przetargi, galeria | `data/tresc.json` → `realizacje`, `przetargi`, `galeria` |
| Tekst „O firmie” | `data/tresc/o-firmie.md` (Markdown) |
| Jak pracujemy, zasady (gwarancja, zadatek), pytania | `data/tresc.json` → `proces`, `zasady`, `faq` |
| Zespół, liczby, opinie, certyfikaty | `data/tresc.json` → `zespol` (zdjęcie tylko z `zgoda: true`), `liczby`, `opinie`, `certyfikaty` |
| Oferty pracy (`/kariera`) | `data/tresc.json` → `kariera` (`opublikowano`, `wazne_do` — po terminie oferta znika) |
| Pliki do pobrania, współpraca, punkty sprzedaży | `data/tresc.json` → `do_pobrania` (pliki w `assets/img/pliki/`), `wspolpraca`, `gdzie_kupic` |
| Aktualność | nowy plik `data/aktualnosci/RRRR-MM-tytul.md` |
| Nowe zdjęcie | plik do `brief/zdjecia/`, wpis w `data/zdjecia.json`, potem `python3 tools/zdjecia.py` |
| Logo, kolor, kroje, tło | `data/firma.json` → `marka` (logo w `assets/img/`; kontrast: `python3 tools/kolory.py raport --klient .`) |
| Element-podpis, drobne różnice wyglądu | `assets/css/wlasne.css` |
| Dane rejestrowe w stopce | `data/firma.json` → `rejestr` |
| Formularz, mapa, statystyki, animacja | `data/firma.json` → `funkcje` (opis przełączników: `docs/DECYZJE.md`) |
| Tytuł karty i opis w Google | `data/firma.json` → `seo` |
| Stare adresy poprzedniej strony (przekierowania 301) | `data/firma.json` → `przekierowania` (`z`, `do`) |
| Informacja o dostępności (`/dostepnosc`) | `data/firma.json` → `dostepnosc` i `funkcje.strona_dostepnosci` |
| Zmiana wyglądu wszystkich stron | repozytorium SZABLON: `src/`, `assets/css/czesci/` (`docs/JAK-DODAC-SEKCJE.md`) |

Po każdej zmianie: `python3 tools/build.py` — komunikaty po polsku mówią, który plik i pole poprawić.

## Aktualizacja strony klienta do nowszej wersji SZABLONU

Wersja szablonu jest w pliku `SZABLON_WERSJA`, zmiany i powody — w `CHANGELOG.md`. Każde wydanie SZABLONU ma tag
`v<wersja>` (`git tag v0.1.0 && git push --tags`). Strona klienta nie zmienia plików silnika, więc aktualizacja to
skopiowanie nowych plików silnika:

```
git remote add szablon https://github.com/<konto>/SZABLON.git     # raz
git fetch szablon --tags
python3 tools/aktualizuj.py --wersja v0.2.0 --proba                # co się zmieni
python3 tools/aktualizuj.py --wersja v0.2.0                        # kopiuje silnik i uruchamia build --sprawdz
git commit -am "Aktualizacja SZABLONU do 0.2.0"
```

`tools/aktualizuj.py` odmawia, jeśli w stronie klienta zmieniono plik silnika (wypisuje listę) — taką zmianę
przenieś do `assets/css/wlasne.css` albo do SZABLONU. `wrangler.jsonc` (nazwa Workera klienta) nie jest nadpisywany;
nowa wersja trafia obok jako `wrangler.jsonc.szablon`. Zamiast zdalnego repozytorium można podać katalog:
`--szablon ../SZABLON`.

## Decyzje

Domyślne ustawienia, które różnią się od wcześniejszych stron (etykiety nad nagłówkami, myślnik, telefon w nagłówku,
tytuł karty, kroje, animacje, checkbox zgody, REGON, przykład na prawdziwej firmie, niepotwierdzone dane) — każde
jako przełącznik w danych, z uzasadnieniem: [`docs/DECYZJE.md`](docs/DECYZJE.md).

## Dokumentacja

- `AGENTS.md` — zasady dla AI (polecenia, Zawsze / Zapytaj najpierw / Nigdy)
- `docs/PROCEDURA.md` — personalizacja krok po kroku (fazy 0–9)
- `docs/KONTRAKT.md` — umowa silnika: model danych, szablony, CSS, JS, build, kontrole
- `docs/JAK-DODAC-SEKCJE.md` — dla osoby rozwijającej silnik: nowa sekcja, podstrona, CSS, JS, schemat
- `docs/CO-ZAWIERA-STRONA.md` — co ma strona i po co (generuje `python3 tools/co_zawiera.py`)
- `docs/CLOUDFLARE.md`, `docs/FORMULARZ.md`, `docs/PRZEKAZANIE.md` — publikacja, formularz, przekazanie klientowi

## Do potwierdzenia z właścicielem

W stronie klienta tę sekcję generuje `python3 tools/raport.py --readme` z `data/firma.json → do_potwierdzenia`.

<!-- do-potwierdzenia:poczatek -->
- (repozytorium SZABLON — lista powstaje w stronie klienta)
<!-- do-potwierdzenia:koniec -->
