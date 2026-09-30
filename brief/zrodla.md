# Źródła faktów

Każdy fakt na stronie ma tu wiersz: skąd go wzięliśmy i kiedy. To samo źródło (krócej) trafia do
`data/firma.json → zrodla`. Fakt bez źródła nie trafia na stronę — zostaje `null` albo idzie do „Braki”.

Data w formacie RRRR-MM-DD (dzień odczytu). Zrzut ekranu źródła, które może zniknąć (Facebook, Google), warto
zapisać w `brief/zrzuty/` (poza gitem, jak zdjęcia).

## Fakty

| Fakt (pole w danych) | Wartość | Źródło (adres URL albo „właściciel, e-mail z …”) | Data |
|---|---|---|---|
| firma.nazwa_prawna | | https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/…?rejestr=P&format=json | |
| rejestr.nip / regon / krs | | https://wl-api.mf.gov.pl/api/search/nip/…?date=… | |
| kontakt.adres | | | |
| kontakt.telefon | | | |
| kontakt.geo | | https://nominatim.openstreetmap.org/… (punkt wejścia sprawdzony na mapie) | |
| godziny | | | |
| marka.kolor | | (plik logo / zdjęcie szyldu) | |

## Zdjęcia

| id | Plik w brief/zdjecia/ | Skąd (strona, Facebook, właściciel) | Autor | Osoby / zgoda |
|---|---|---|---|---|
| | | | | |

## Braki (pytania do właściciela)

Według liter z `brief/BRIEF.md`:

- A:
- B:
- C:
- D:
- E:
