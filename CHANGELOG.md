# Zmiany w SZABLONIE

Numer wersji jest w pliku `SZABLON_WERSJA` (semver: zmiana danych wymagająca poprawek u klienta = nowa wersja
główna do 1.0 — druga liczba). Każde wydanie ma tag `v<wersja>`; strony klientów aktualizuje `tools/aktualizuj.py`.
Przy każdej pozycji piszemy, **dlaczego** — to czyta osoba, która decyduje, czy aktualizować stronę klienta.

## Niewydane (następna: 0.2.0)

Po próbnej personalizacji pizzerii z samego briefu, przeglądzie wyglądu i przeglądzie bezpieczeństwa/prawa.
**Wymaga uwagi u klienta:** cytat opinii bez linku, brak `kontakt.email` i (przy formularzu przez Workera)
`namespace_id` „1101” zatrzymują teraz `--produkcja`; `pattern` w schemacie sprawdza cały tekst, a `hero.cta_*.href`
ma listę dozwolonych adresów.

- **Brak danych bez zastępników (D13):** `firma.domena: null` + `adres_roboczy` (noindex), `kontakt.geo: null`
  (trasa do adresu), `rejestr.forma_prawna: "nieznana"`, `menu.ceny: "w_lokalu"`. Dlaczego: AI z samym briefem
  wpisywało adres roboczy jako domenę, „inna” zamiast „nie wiem” i ceny/współrzędne z domysłu.
- **Formularz:** czas wypełnienia liczony w przeglądarce (`performance.now()`), nie zegarem odwiedzającego — wiadomości
  z telefonów z przestawionym zegarem przepadały po cichu. Origin z/bez www, `Sec-Fetch-Site`, limit 16 KB, ścisły
  Reply-To, temat bez separatorów Unicode, strony `/blad-formularz` i `/blad-konfiguracja` bez JS; pole „zgoda”
  nieobowiązkowe (art. 7 ust. 4 RODO).
- **Bezpieczeństwo danych:** `re.fullmatch` w schemacie (adres roboczy z „\n” dawał noindex całej domeny), znaki
  sterujące = błąd, bezpieczne adresy przycisków, CSP bez `data:`, dziennik wywołań Workera wyłączony.
- **Polityka prywatności i stopka:** jedna rola Cloudflare, okresy i podstawy przekazania do USA wg odbiorcy;
  `psa`, `kapital_wplacony` (S.A.), `adres_siedziby`; JDG bez powtórzonego właściciela.
- **Narzędzia:** `sprawdz.sh` bez zawieszenia na zrzutach bez JS, z limitami czasu, sprzątaniem po przerwaniu
  i `SZABLON_NODE_PREFIX`; `start.py` zastępuje nietknięty szkielet, pisze README klienta i losuje `namespace_id`;
  `tools/zrodla.py` (koniec faz 0–1), `tools/skill.py` (SKILL = PROCEDURA); przezroczyste logo w ikonach, `og.jpg`
  z logo bez zdjęcia hero; `assets/css/wlasne.css` w szablonie; twarda spacja także w tekstach szablonów.
- **Wygląd:** sekcje w różnym rytmie (jedna z tłem, sekcje użytkowe ciaśniej, nagłówek z boku w krótkich sekcjach),
  bez dwóch czarnych linii nad h2, tekst ≥ 16 px, nagłówek bez drugiego „Zadzwoń” w pierwszym ekranie, stopka bez
  powtórzonego kontaktu, równe wiersze oferty i siatka produktów, jedna nazwa sekcji przetargów, proces bez stylu
  „1-2-3”, mapa bez pudełka. Dlaczego: strony wyglądały jak jeden powtarzany blok (producent: 10 800 px).

## 0.1.0 — 2026-09-30

Pierwsza wersja. Zasady z trzech wcześniejszych stron (Sofastyl, Kociak, Dom Smaków) i z badania najlepszych stron
MŚP zamienione na kod, który ich pilnuje.

- **Silnik:** `tools/build.py` (tylko biblioteka standardowa) — dane `data/*.json` sprawdzane schematem z polskimi
  komunikatami, render szablonów, kontrole wyniku (nagłówki, obrazy, linki, kontrast, pozostałości szablonu),
  `_headers` z CSP na skrótach sha256, sitemap, robots, JSON-LD. Dlaczego: jedna informacja w jednym miejscu
  i błąd zamiast cichej usterki — w Sofastyl kilka commitów tylko usuwało duplikaty.
- **Presety branż:** restauracja, budowlana, producent, usługi, gabinet — kolejność sekcji, przycisk główny,
  pasek na telefonie, typ firmy dla Google. Dlaczego: skala i pierwsze pytanie klienta różnią się między branżami.
- **Sekcje:** hero, ogłoszenie, oferta, cennik, karta, produkty, realizacje, przetargi, galeria, proces, zasady,
  o firmie, zespół, liczby, opinie, certyfikaty, pytania, godziny, aktualności, praca, do pobrania, współpraca,
  gdzie kupić, kontakt; każda znika bez danych. Dlaczego: szablon nie może zachęcać do zmyślania treści.
- **Worker i prawo:** formularz przez Cloudflare Worker (limit, pułapka, czas), polityka prywatności z tego, co strona
  robi, strona dostępności, dane rejestrowe w stopce według formy prawnej.
- **Kontrola jakości treści:** `tools/lint_slop.py` (frazesy, szablonowe wzorce), `tools/swieta.py` (godziny w święta).
- **Narzędzia AI:** `AGENTS.md`, `CLAUDE.md` z hookami, skill `/personalizuj` = `docs/PROCEDURA.md`, kwestionariusz
  `brief/BRIEF.md`, `tools/kolory.py` (kolor z logo i raport kontrastu), `tools/sprawdz.sh` (zrzuty, bez JS,
  wymuszone kolory, html-validate, axe, Lighthouse, skan wstrzyknięć Cloudflare), `tools/raport.py` (karta jakości),
  `tools/co_zawiera.py` (spis funkcji dla klienta), `tools/aktualizuj.py` (aktualizacja silnika u klienta).
  Dlaczego: AI dostaje polecenia, które sprawdzają jej pracę, zamiast samych zasad do zapamiętania.
- **Po połączeniu modułów:** CSS strony zawiera tylko reguły sekcji, które strona ma, i nie ma komentarzy źródeł
  (79 KB → 44–52 KB; limit 60 KB). Dlaczego: z CSS wszystkich sekcji `--produkcja` stawał u każdego klienta.
  Godziny świąteczne są ostrzeżeniem klasy A (D12), bo w 45 dniach prawie zawsze wypada święto i nocny build
  restauracji stawałby co tydzień. Linter nie traktuje imion, nazw punktów sprzedaży i zamawiających jako „Title
  Case”. `tools/zrzuty.cjs` przewija stronę przed zrzutem, żeby leniwe zdjęcia nie wychodziły puste.
