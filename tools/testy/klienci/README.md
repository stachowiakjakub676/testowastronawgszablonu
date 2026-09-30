# Klienci testowi (fikstury)

Cztery wymyślone firmy, po jednej na branżę, które sprawdzają każdy moduł szablonu. Branżę budowlaną sprawdza
prawdziwy przykład `przyklady/bimex`. To są **dane do testów, nie wzory treści** — nie kopiuj z nich tekstów do strony
klienta (każdy ma `"przyklad": true`, więc `--produkcja` i tak przerwie build).

| Katalog | Firma | Forma prawna | Co sprawdza |
|---|---|---|---|
| `restauracja/` | Restauracja Testowa | spółka cywilna | karta (3 kategorie, W/O, alergeny, porcje, PDF), cennik przyjęć, galeria, o lokalu (> 250 słów → `/o-firmie`), zespół ze zgodą i bez, opinie z oceną zbiorczą i weryfikacją, godziny z przerwą, po północy (pt., sob. do 2:00), kuchnia osobno, wyjątki (także przeszły), zasady, FAQ, ogłoszenie, 3 wpisy aktualności, praca (ważna i wygasła oferta), mapa po kliknięciu, formularz przez Workera, RSS |
| `producent/` | Meble Próbne | sp. z o.o. (kapitał) | 9 produktów w 3 kategoriach + „Pozostałe” (filtr, `/produkty`), ceny i produkty bez ceny, bez zdjęcia, cennik netto dla firm, liczby z datami, proces, zasady, współpraca (Markdown + warunki), gdzie kupić (3 województwa + bez województwa), do pobrania (2 PDF), certyfikaty (ważny z plikiem, wygasły), `Organization` + salon z godzinami, działy, praca bez daty ważności |
| `uslugi/` | Serwis Próbny | sp. j. | oferta z podstroną usługi (`/oferta/przeglad`, `og:image` usługi), cennik z kolumną „Czas”, cena 0 i od–do, proces, zasady, zespół (zgoda, zdjęcie bez zgody, bez zdjęcia), opinie bez oceny zbiorczej (jedna bez linku), FAQ z `FAQPage`, myślnik „pauza” |
| `gabinet/` | Gabinet Testowy | JDG + samorząd zawodowy | zespół 4 osób z portretami (→ `/o-firmie`), cennik z PDF, godziny z przerwą i godziny rejestracji, wyjątki, ogłoszenie bez daty początku, bez formularza, jasny kolor marki (turkus), własne tło `#FCFCFA`, strona `/dostepnosc` z danymi oceny, przekierowania ze starych adresów (`_redirects`) |

## Dane są fikcyjne

- Nazwy („Testowa”, „Próbna”, „Testowo”, „Próbnik”), adresy (`ul. Testowa 1–4`, kody `00-00x`) i osoby są wymyślone.
- Telefony: `+48 500 000 001` … `+48 500 000 022`. Adresy e-mail i strony: tylko w domenie `.example` (zarezerwowanej
  do przykładów, RFC 2606), także linki „opinii” i „punktów sprzedaży”.
- **NIP, REGON i KRS są fikcyjne.** Mają poprawne sumy kontrolne (build je sprawdza), ale NIP i REGON zaczynają się
  od `000` — takich numerów urzędy nie nadają. KRS (`00009000xx`) nie ma sumy kontrolnej, jest tylko w poprawnym formacie.
- Zdjęcia to zastępniki: jednolity przygaszony kolor, cienka ramka, przekątne i napis „zdjęcie testowe: …” — `alt`
  mówi wprost, że to zdjęcie zastępcze. Logo to napis z nazwą firmy. Pliki PDF mają 1–3 puste strony z jednym wierszem tekstu.

## Daty

Wszystkie daty (ogłoszenia, wyjątki w godzinach, oferty pracy, certyfikaty, oceny, aktualności) są liczone od stałego
„dziś” — `DZIS` w `tools/testy/_wspolne.py` (teraz 2026-10-01). Buduj z tą samą datą:

```
SZABLON_DZIS=2026-10-01 python3 tools/build.py --klient tools/testy/klienci/restauracja --wyjscie dist-restauracja
```

Bez `SZABLON_DZIS` build też przejdzie, ale z czasem ogłoszenia wygasną, a oferty pracy znikną.

## Zmiana danych

Źródłem prawdy jest `generuj.py` — pliki w `*/data/` i `*/assets/` są jego wynikiem (commitowanym, żeby testy i CI
nie potrzebowały Pillow). Nie edytuj JSON-ów ręcznie:

```
python3 tools/testy/klienci/generuj.py                  # wszystko: dane, zdjęcia zastępcze, logo, PDF (wymaga Pillow)
python3 tools/testy/klienci/generuj.py --tylko-dane     # tylko data/ — np. po zmianie schematu, bez Pillow
python3 tools/testy/klienci/generuj.py --branza gabinet
python3 tools/testy/uruchom.py                          # potem testy
```

Oryginały zdjęć (`*/brief/zdjecia/`) są poza gitem; `generuj.py` tworzy je od nowa i uruchamia `tools/zdjecia.py`.
Pełne generowanie może zakodować AVIF/WebP odrobinę inaczej (inne bajty, ten sam obraz) — gdy zmieniasz tylko dane,
używaj `--tylko-dane`, żeby w commicie nie było kilkudziesięciu zmienionych zdjęć.

**Oferty pracy.** Generator sam sprawdza schemat: jeśli `kariera.pozycje[]` ma pole `opublikowano` (sekcja „Praca”
z JobPosting), dopisuje `opublikowano` i `kariera.kontakt`. Po zmianie schematu wystarczy `generuj.py --tylko-dane`.
