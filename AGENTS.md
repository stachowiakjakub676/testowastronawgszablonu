# SZABLON — instrukcje dla agentów AI

Szablon strony firmowej (statyczny HTML, build w Pythonie bez zależności, publikacja na Cloudflare).
Dostajesz dane firmy i zdjęcia (`brief/`), a zwracasz stronę z prawdziwą treścią tej firmy.
Wszystko po polsku: treść strony, komentarze w kodzie, komunikaty, dokumentacja, opisy commitów.
Procedura krok po kroku: `docs/PROCEDURA.md` (w Claude Code: `/personalizuj`). Umowa silnika: `docs/KONTRAKT.md`.

## Polecenia

| Polecenie | Kiedy |
|---|---|
| `python3 tools/start.py --branza restauracja\|budowlana\|producent\|uslugi\|gabinet` | nowy klient: szkielet `data/*.json` z samymi `null` (nietknięty szkielet zastępuje sam, zmienione pliki — tylko z `--nadpisz`), README klienta, własne `namespace_id` w `wrangler.jsonc` |
| `python3 tools/zrodla.py --faza 0\|1` | koniec faz 0–1: `brief/zrodla.md` ma braki i fakty z wartością, źródłem i datą (nie wzór) |
| `python3 tools/build.py --szybko` | po każdej zmianie w `data/` — walidacja i render |
| `python3 tools/build.py` (= `--sprawdz`) | wszystkie kontrole wyniku; ostrzeżenia nie przerywają |
| `python3 tools/build.py --produkcja` | jak na Cloudflare: ostrzeżenia = błędy |
| `python3 tools/build.py --json` | komunikaty jako JSON (plik, pole, jak naprawić) — do pętli poprawek |
| `python3 tools/build.py --klient przyklady/bimex --wyjscie dist-test` | inny katalog klienta / wyniku |
| `python3 tools/kolory.py logo brief/zdjecia/logo.png` | kandydaci na kolor marki z logo |
| `python3 tools/kolory.py raport "#RRGGBB"` | tokeny kolorów i kontrast każdej pary |
| `python3 tools/zdjecia.py` | zdjęcia z `brief/zdjecia/` → AVIF/WebP/JPEG, `og.jpg`, ikony (wymaga Pillow) |
| `python3 tools/lint_slop.py dist/ data/ --json` | frazesy i szablonowe wzorce (build uruchamia go sam) |
| `python3 tools/podglad.py` | podgląd `dist/` pod http://localhost:8765 (adresy bez `.html`, 404, nagłówki) |
| `bash tools/sprawdz.sh` | pełna kontrola: build, zrzuty 375/768/1440, bez JS, html-validate, pa11y, Lighthouse → `raport/`; narzędzia Node spoza systemu: `SZABLON_NODE_PREFIX=~/.szablon-node` (instalacja: `npm i -g --prefix ~/.szablon-node playwright html-validate pa11y lighthouse linkinator`), zajęty port: `--port 8791` |
| `python3 tools/raport.py --readme` | karta jakości `raport/KARTA-JAKOSCI.md` + sekcja „Do potwierdzenia” w README |
| `python3 tools/co_zawiera.py --klient .` | spis funkcji strony dla klienta → `raport/CO-ZAWIERA-STRONA.md` |
| `python3 tools/swieta.py 2027` | święta i niedziele handlowe roku (build przypomina o godzinach na 45 dni wcześniej) |
| `python3 tools/testy/uruchom.py` | po zmianie silnika: testy jednostkowe, build przykładu i klientów testowych (ok. 6 s) |
| `node tools/test_worker.mjs` | po zmianie `worker/index.js` (formularz przez Workera) |
| `python3 tools/skill.py` | po zmianie `docs/PROCEDURA.md` (w repozytorium SZABLON) — odświeża skill `/personalizuj` |

Kod wyjścia buildu: 0 = OK, 1 = błędy danych albo kontroli, 2 = błąd wewnętrzny. Pola danych opisują
`tools/schemat/*.schema.json` i `docs/KONTRAKT.md` §4. Reguły branży: `tools/presety/<branza>.json`.

## Pliki klienta i pliki silnika

- **Klient (tu pracujesz):** `data/firma.json`, `data/tresc.json`, `data/zdjecia.json`, `data/tresc/*.md`,
  `data/aktualnosci/*.md`, `brief/`, `assets/img/`, `assets/css/wlasne.css`, `README.md`.
- **Silnik (nie ruszasz w repozytorium klienta):** `src/`, `tools/`, `assets/css/czesci/`, `assets/js/czesci/`,
  `assets/fonts/`, `worker/`, `docs/`, `przyklady/`, `AGENTS.md`, `CLAUDE.md`, `.claude/`. Zmiana silnika w stronie
  klienta blokuje `tools/aktualizuj.py` (aktualizacje z nowszych wersji szablonu).
- `dist/` i `raport/` są generowane — nie edytuj ich i nie commituj.
- `przyklady/bimex/` to wzór pełnego katalogu klienta na prawdziwej firmie. Nie kopiuj z niego treści:
  `--produkcja` zatrzymuje build, gdy na stronie są zdania, telefony albo NIP z przykładu.

## Zawsze

- Każda liczba, cena, godzina, rok, nazwa klienta i certyfikat ma źródło: `data/firma.json → zrodla`
  (pole → „skąd, data”) i wiersz w `brief/zrodla.md` (adres URL + data odczytu).
- Czego nie wiesz — `null`. Sekcja bez danych sama się ukrywa (build wypisuje `UKRYTO`). Fakt niepewny: `null`
  albo wartość + wpis w `firma.do_potwierdzenia` (trafia do README „Do potwierdzenia z właścicielem”).
  Bez domeny: `firma.domena: null` + `adres_roboczy` (noindex); bez współrzędnych: `kontakt.geo: null`; bez formy
  prawnej: `rejestr.forma_prawna: "nieznana"`; karta bez cen: `menu.ceny: "w_lokalu"` — nie wpisuj zastępników.
- Logo kopiujesz do `assets/img/` (`marka.logo: "assets/img/logo.png"`); `brief/` nie trafia do gita ani na serwer.
- Obejrzyj każde zdjęcie (otwórz plik), zanim napiszesz `alt` i `podpis`. `alt` opisuje to, co widać, 5–150 znaków,
  bez „Zdjęcie…”, „Obraz…”, nazwy pliku.
- Przy zdjęciu z rozpoznawalną twarzą: `osoby: true` i `zgoda: true` tylko wtedy, gdy właściciel potwierdził zgodę.
- Kolor marki bierz z logo albo szyldu (`tools/kolory.py`), a skąd jest — wpisz w `marka.kolor_zrodlo`.
- Pisz rzeczowo, krótkimi zdaniami, konkretem: co, gdzie, od kiedy, za ile, ile km / m² / dni.
- Jedna informacja w jednym miejscu (plus stopka). Nie powtarzaj telefonu, adresu ani oferty w kilku sekcjach.
- Po każdej zmianie danych: `python3 tools/build.py --szybko`; przed commitem: `python3 tools/build.py`.
- Małe commity z opisem *dlaczego* (np. „Godziny wytwórni z baneru na Facebooku — biuro ma inne”).

## Zapytaj najpierw

- Zmiana czegokolwiek w plikach silnika (`src/`, `tools/`, `assets/css/czesci/`, `assets/js/czesci/`, `worker/`).
  Zwykle wystarczą dane albo `assets/css/wlasne.css`. Poprawka dla wszystkich stron należy do repozytorium SZABLON.
- Pokazanie cen, nazw klientów prywatnych, zdjęć osób, cytatów opinii.
- Adres e-mail formularza, tryb formularza (`mailto` / `worker`), domena, wybór hostingu.
- Zmiana branży (`branza`) albo kolejności sekcji, wyłączenie kontroli przez `data/slop-ok.json`.
- Usunięcie treści, którą dostarczył właściciel.

## Nigdy

- Nie wymyślaj: liczb, cen, lat, godzin, realizacji, klientów, certyfikatów, opinii, członków zespołu, działów,
  sprzętu, „10 lat doświadczenia”. Brak źródła = `null`.
- Nie używaj zdjęć stockowych, obrazów z AI ani zdjęć klientów z Google udających zdjęcia firmy.
  Tylko prawdziwe zdjęcia firmy z zapisanym `zrodlo` (i `autor`, jeśli to nie firma).
- Nie dodawaj Google Fonts, iframe Google Maps, trackerów, pikseli, bibliotek JS, CDN, obrazków `data:`,
  atrybutów `style=""` ani bloków `<style>` — CSP i kontrole buildu to odrzucą.
- Nie osłabiaj kontroli w `tools/` ani hooków, żeby build przeszedł. Napraw dane albo zapytaj.
- Nie commituj sekretów (klucz Resend, tokeny, adres Deploy Hook) ani oryginałów z `brief/zdjecia/`.
- Nie pisz frazesów: „kompleksowe usługi”, „najwyższa jakość”, „indywidualne podejście”, „z pasją”,
  „Dlaczego my?”, „zespół doświadczonych specjalistów”; bez emoji, liczników „500+”, etykiet nad każdym
  nagłówkiem (pełna lista: `python3 tools/lint_slop.py --reguly`).
- Nie ustawiaj `"przyklad": true` w danych klienta i nie kopiuj danych z `przyklady/`.

## Kiedy praca jest skończona

1. `python3 tools/build.py --produkcja` kończy się kodem 0 (dla katalogu z `przyklady/`: `--sprawdz`).
2. `bash tools/sprawdz.sh` — wszystkie wykonane kroki OK (Lighthouse: dostępność, dobre praktyki, SEO = 100;
   pa11y 0 problemów; 0 px przewijania w poziomie; pusta konsola; 0 obcych domen i ciasteczek).
3. Obejrzałeś zrzuty `raport/zrzuty/*-375.png`, `*-375-ekran.png` i `*-1440.png` i poprawiłeś to, co odstaje
   (lista kontrolna: `docs/PROCEDURA.md`, faza 8).
4. `python3 tools/raport.py --readme` — README ma aktualną sekcję „Do potwierdzenia z właścicielem”.
5. Ostatnia wiadomość do użytkownika podaje liczby i ścieżki (wyniki, zrzuty, ukryte sekcje, pytania do
   właściciela) — nie zapewnienia.
