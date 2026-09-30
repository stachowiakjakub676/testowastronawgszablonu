# Strona internetowa firmy

<!-- Wpisz w tytule nazwę firmy, a niżej jedno zdanie: co to za strona i pod jakim adresem działa. -->
Strona zbudowana z szablonu SZABLON (branża „producent”, wersja w pliku `SZABLON_WERSJA`). Treść jest w `data/`,
zdjęcia w `assets/img/`, wygląd tej strony w `assets/css/wlasne.css`. Silnik (`src/`, `tools/`, `assets/css/czesci/`)
zmienia się tylko przez aktualizację szablonu (`tools/aktualizuj.py`). Instrukcje dla AI: `AGENTS.md`, `docs/PROCEDURA.md`.

## Podgląd lokalny

```
python3 tools/build.py          # build z kontrolami → dist/
python3 tools/podglad.py        # http://localhost:8765
bash tools/sprawdz.sh           # pełna kontrola: zrzuty, dostępność, Lighthouse → raport/
```

## Publikacja

Cloudflare Workers Builds: każdy push do gałęzi produkcyjnej uruchamia `python3 tools/build.py --produkcja`
i wdraża `dist/`. Krok po kroku: `docs/CLOUDFLARE.md`; formularz: `docs/FORMULARZ.md`; przekazanie: `docs/PRZEKAZANIE.md`.

## Co i gdzie zmienić

| Co | Gdzie |
|---|---|
| Telefon, e-mail, adres | `data/firma.json` → `kontakt` |
| Godziny otwarcia, święta i wyjątki | `data/firma.json` → `godziny` (`wyjatki`: data, godziny, opis) |
| Nagłówek i zdanie na pierwszym ekranie, zdjęcie | `data/tresc.json` → `hero` |
| Ogłoszenie („24–26.12 nieczynne”) | `data/tresc.json` → `ogloszenie` (`tekst`, `od`, `do`) |
| Produkty | `data/tresc.json` → `produkty` |
| Cennik | `data/tresc.json` → `cennik` |
| Tekst „O firmie” | `data/tresc/o-firmie.md` (Markdown) i `data/tresc.json` → `o_firmie` |
| Przebieg zlecenia | `data/tresc.json` → `proces` |
| Firma w liczbach | `data/tresc.json` → `liczby` (każda liczba z datą) |
| Zasady (gwarancja, zadatek, rezerwacje) | `data/tresc.json` → `zasady` |
| Współpraca | `data/tresc.json` → `wspolpraca` |
| Punkty sprzedaży | `data/tresc.json` → `gdzie_kupic` |
| Pliki do pobrania | `data/tresc.json` → `do_pobrania` (pliki w `assets/img/pliki/`) |
| Pytania i odpowiedzi | `data/tresc.json` → `faq` |
| Aktualność | nowy plik `data/aktualnosci/RRRR-MM-tytul.md` |
| Nowe zdjęcie | plik do `brief/zdjecia/`, wpis w `data/zdjecia.json`, potem `python3 tools/zdjecia.py` |
| Logo, kolor, kroje, tło | `data/firma.json` → `marka` (logo w `assets/img/`) |
| Element-podpis, drobne różnice wyglądu | `assets/css/wlasne.css` |
| Dane rejestrowe w stopce | `data/firma.json` → `rejestr` |
| Formularz, mapa, statystyki | `data/firma.json` → `funkcje` (opis przełączników: `docs/DECYZJE.md`) |
| Tytuł karty i opis w Google | `data/firma.json` → `seo` |

Po każdej zmianie: `python3 tools/build.py` — komunikaty mówią, który plik i pole poprawić.

## Do potwierdzenia z właścicielem

<!-- do-potwierdzenia:poczatek -->
- (lista powstaje z `data/firma.json` → `do_potwierdzenia`: `python3 tools/raport.py --readme`)
<!-- do-potwierdzenia:koniec -->
