# Jak rozwijać silnik: sekcje, podstrony, CSS, JS, dane

Dla osoby (albo agenta), która zmienia **silnik** w repozytorium SZABLON — nie dla personalizacji strony klienta
(ta jest w `docs/PROCEDURA.md`). Pełna umowa: `docs/KONTRAKT.md`; ten plik to praktyczny skrót i konwencje.

## Plik sekcji (`src/sekcje/<id>.html`)

- Wiersz 1: `{# wymaga: tresc.<id>.pozycje #}`. Ścieżki to ścieżki kontekstu szablonu (`tresc.*`, `firma.*`, `auto.*`);
  przecinek = wszystkie, `a|b` = jedna z nich. Wiersz 2: komentarz, co sekcja robi.
- Element główny:
  ```
  <section class="section{% if sekcja.klasa %} {{ sekcja.klasa }}{% endif %} <id>" id="{{ sekcja.html_id }}"
           aria-labelledby="{% if bez_naglowka %}tytul-strony{% else %}<html_id>-h{% endif %}">
    <div class="wrap">
      {% if not bez_naglowka %}<div class="section__head"><h2 id="<html_id>-h">{{ sekcja.naglowek }}</h2>…</div>{% endif %}
  ```
  Nagłówki wewnątrz sekcji: `<h{{ hn }}>`. `sekcja.klasa` to wariant z presetu (`warianty`: `section--tint` —
  tło, `section--sm` — mniejsze odstępy; tylko na głównej). Krótka sekcja (kilka wierszy) może mieć nagłówek z boku:
  `<div class="wrap{% if not bez_naglowka %} bok{% endif %}">` (01-baza.css, jak w zasadach i pytaniach).
- Zmienne: `tryb` = `"skrot"` na stronie głównej, `"pelny"` na podstronie; `limit` z presetu (`limity`), `None`
  w pełnej wersji; `bez_naglowka`; `hn` = 3 (albo 2 przy `bez_naglowka`); `sekcja` = `{id, html_id, naglowek, dane, strona, klasa}`.
  Globalne: `firma`, `tresc`, `zdjecia`, `preset`, `funkcje`, `strona`, `nav`, `aktualnosci`, `element` (strony
  kolekcji), `auto.*` (pełna lista: KONTRAKT §9.1).
- **Skrót i pełna wersja nie powtarzają się.** Skrót kończy się opisowym linkiem:
  `{% if tryb == "skrot" and sekcja.strona %}<p class="section__wiecej"><a href="{{ sekcja.strona | url }}">Wszystkie … ({{ n }})</a></p>{% endif %}`.
  Blok z tymi samymi akcjami co pasek mobilny dostaje `data-ukryj-pasek`. Wzór do skopiowania: `src/sekcje/kontakt.html`.
- Układ pod treść, nie jeden dla wszystkich: tabela dla przetargów, `<dl>` dla faktów, prawdziwe `<ol>` dla procesu,
  gęsta typografia z cenami tabelarycznymi dla karty, duże zdjęcia w rzędach dla realizacji. Linie 1 px zamiast kart.

## Zasady wyjścia HTML

- Każdy adres z danych przez `| url`, `| zasob` albo `| mailto`. Build przerywa, gdy w `href`/`src`/`srcset`/
  `data-src`/`action`/`og:*` jest półpauza, twarda spacja albo polski cudzysłów (typografia zepsuła link).
- Do `<script>` tylko przez `| json` albo `jsonld.jako_skrypt`. Bez `style=""` i bez skryptów inline.
- Zdjęcia tylko `{{ id | obraz:"pol|tercja|miniatura|pelny|hero" }}`.
- Adres: `auto.adres_html` i `auto.adres_linia_html` — HTML z nierozdzielnym kodem pocztowym do widocznego tekstu;
  `auto.adres_linia` — zwykły tekst do atrybutów i meta. `auto.rejestr_linie` to HTML bez adresu.

## CSS

- Jeden plik na sekcję lub grupę: `assets/css/czesci/1x-<sekcja>.css` (10 = hero, 19 = kontakt, 11–18 wolne,
  89 dokument, 90 druk, 91 ruch, 92 wymuszone kolory). Pliki są sklejane w kolejności nazw.
- Klasy w stylu BEM (`.oferta__pozycja`); kolory tylko tokenami z `:root` (bez wartości hex); breakpointy mobile-first
  600 / 960 / 1280 px. Klasy bazowe: KONTRAKT §7.6 (w tym `.nowrap`).
- Wszystko z przezroczystą ramką potrzebuje reguły w `@media (forced-colors: active)`.
- Limit CSS strony: 60 KB (build ostrzega, `--produkcja` przerywa). Komentarze nie trafiają do `dist/`, a z plików
  `1x-*.css` build wycina reguły bloków, których strona nie ma — dlatego każda reguła sekcji musi zaczynać się od klasy
  jej bloku (`.cennik__grupa`, nie gołe `table td`), a klasy dodawane skryptem muszą stać w JS jako napis.

## JS

- Jeden plik na funkcję: `assets/js/czesci/NN-nazwa.js`, samodzielny `(() => { … })();` bez zależności.
- Haki przez atrybuty `data-*`; bez haka skrypt nic nie robi; strona działa bez JS.
- Bez localStorage i bez zapytań do obcych serwerów. Numery `10-menu` … `70-ogloszenie` są zajęte (KONTRAKT §11);
  wejście hero nie ma JS — jest w `91-ruch.css`.

## Schemat i dane

- `tools/schemat/*.schema.json` zmieniaj przez wczytanie i zapis: `json.dumps(indent=2, ensure_ascii=False) + "\n"` —
  pliki zostają w tym samym stylu (mniej konfliktów przy łączeniu gałęzi).
- `additionalProperties: false`; bloki najwyższego poziomu są wymagane i mogą być `null`. Daty przez
  `{"$ref": "#/$defs/data"}` (sprawdzane z kalendarzem); zdjęcia przez klucze `zdjecie`/`zdjecia` (istnienie sprawdza build).
- Kontrole znaczeniowe w `dane.kontrole`: `raport.blad(tresc, plik=, pole=, naprawa=)`. `raport.ostrzezenie(..., klasa="A")`
  tylko dla ostrzeżeń, które nie mogą blokować `--produkcja`.
- W tej samej zmianie: KONTRAKT §4.2, `tools/start.py` (nowe pola firmy) i `przyklady/bimex/data` — tylko prawdziwe
  dane ze źródłem. `funkcje.hosting` jest wymagane.

## Presety i podstrony

- Zmiana w presetach: wszystkie pięć plików `tools/presety/` — `sekcje_glowna`, `naglowki` (neutralne, bez zakładania
  treści), `nav`, `nav_etykiety`, `limity`.
- Szablon podstrony `src/strony/<nazwa>.html`: nagłówek `{# strona: sciezka="/…" sekcja="<id>" nav="…" tytul="…" #}`,
  potem `{% include "czesci/naglowek-strony.html" %}` i `{% include "sekcje/<id>.html" tryb="pelny" bez_naglowka=true %}`.
  Strona musi być w `strony` presetu; próg jej powstania — w `strony.progi()`.

## Testowanie zmiany

- Własny katalog wyniku i port (równoległa praca nie nadpisuje się; `dist-*` jest w `.gitignore` i chroniony znacznikiem):
  ```
  python3 tools/build.py --klient przyklady/bimex --wyjscie dist-<sekcja>      # kod 0; --szybko do szybkich iteracji
  npx --no-install html-validate dist-<sekcja>/*.html
  PODGLAD_CICHO=1 python3 tools/podglad.py --katalog dist-<sekcja> --port 87xx &
  node tools/zrzuty.cjs http://localhost:87xx <katalog-zrzutów> <prefiks>
  npx --no-install pa11y --config <plik-konfiguracji.json> http://localhost:87xx/
  ```
  Albo wszystko naraz: `bash tools/sprawdz.sh --klient przyklady/bimex --wyjscie dist-<sekcja> --port 87xx --raport raport-<sekcja>`.
- `SZABLON_DZIS=RRRR-MM-DD` — sekcje zależne od daty (ogłoszenia, święta, oferty pracy).
- Gdy `przyklady/bimex` ma `null` w Twojej sekcji: skopiuj go **poza repozytorium**, dopisz dane testowe i podaj
  katalog przez `--klient /pełna/ścieżka`. Nigdy nie dopisuj zmyślonych faktów do `przyklady/bimex`. Nie wklejaj zdań
  z bimex do klienta testowego budowanego z `--produkcja` — kontrola przecieku łapie zdania od 30 znaków i identyfikatory.
- Testy narzędzi: `python3 -m unittest discover -s tools/testy`.

## Po zmianie silnika

- Wpis w `CHANGELOG.md` (co i **dlaczego**), podniesienie `SZABLON_WERSJA`, tag `v<wersja>` po połączeniu.
- Nowa funkcja widoczna dla klienta → pozycja w `LISTA` w `tools/co_zawiera.py`, potem `python3 tools/co_zawiera.py`.
- Zmiana procedury → `docs/PROCEDURA.md` i ta sama treść w `.claude/skills/personalizuj/SKILL.md` (pod nagłówkiem YAML).
- Nowe polecenie → `AGENTS.md` (tabela „Polecenia”) i `README.md`.
