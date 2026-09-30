#!/usr/bin/env python3
"""Szkielet danych nowego klienta: data/firma.json, data/tresc.json, data/zdjecia.json pełne null-i.

  python3 tools/start.py --branza budowlana
  python3 tools/start.py --branza restauracja --klient ../nowy-klient
  python3 tools/start.py --branza uslugi --nadpisz        (zastępuje istniejące pliki danych!)
  python3 tools/start.py --branza uslugi --tylko-dane     (bez README klienta i bez zmiany wrangler.jsonc)

Szkielet nigdy nie jest kopią przykładu z przyklady/ — każde pole jest puste (null), a build wypisze listę
brakujących danych. Wypełniaj wyłącznie prawdziwymi danymi ze źródłem (firma.zrodla), niepewne dopisuj
do firma.do_potwierdzenia. Branże: restauracja | budowlana | producent | uslugi | gabinet (tools/presety/).

Pliki danych, które są nietkniętym szkieletem (np. „uslugi” z repozytorium SZABLON), start.py zastępuje bez
--nadpisz. Plik z jakąkolwiek zmianą wymaga --nadpisz.

Oprócz danych (bez --tylko-dane):
- README.md — jeśli to wciąż README SZABLONU, powstaje README klienta: podgląd, publikacja, tabela „Co i gdzie
  zmienić” dla tej branży i znaczniki sekcji „Do potwierdzenia z właścicielem” (wypełnia tools/raport.py --readme);
- wrangler.jsonc — namespace_id limitu formularza „1101” z szablonu zmienia się na losową liczbę (dwie strony na
  jednym koncie Cloudflare nie mogą dzielić limitu).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
BRANZE = ["restauracja", "budowlana", "producent", "uslugi", "gabinet"]
BLOKI_TRESCI = ["ogloszenie", "oferta", "cennik", "menu", "produkty", "realizacje", "przetargi", "proces", "zasady",
                "o_firmie", "zespol", "liczby", "opinie", "certyfikaty", "faq", "galeria", "do_pobrania", "kariera",
                "wspolpraca", "gdzie_kupic"]


def szkielet_firmy(branza: str, schemat_wzgl: str) -> dict:
    return {
        "$schema": f"{schemat_wzgl}/firma.schema.json",
        "$komentarz": (f"Szkielet dla branży „{branza}” (tools/start.py). null = brak danych — element strony się nie pokaże. "
                       "Każdy fakt (telefon, godziny, rok, liczby) wpisz ze źródłem w „zrodla”; niepewne dopisz do "
                       "„do_potwierdzenia”. Opis pól: docs/KONTRAKT.md §4.1."),
        "wersja_danych": 1,
        "przyklad": False,
        "branza": branza,
        "typ_schema": None,
        "firma": {"nazwa": None, "nazwa_prawna": None, "opis": None, "rok_zalozenia": None, "domena": None,
                  "adres_roboczy": None},
        "kontakt": {
            "telefon": None, "email": None,
            "adres": {"ulica": None, "kod": None, "miasto": None, "wojewodztwo": None, "kraj": "PL"},
            "geo": None, "obszar_dzialania": None, "dzialy": None, "dojazd": None, "dostepnosc_lokalu": None,
            "czas_odpowiedzi": None,
        },
        "godziny": None,
        "rejestr": {"forma_prawna": None, "nip": None, "regon": None, "krs": None, "sad_rejestrowy": None,
                    "kapital_zakladowy": None, "kapital_wplacony": None, "wlasciciel": None, "wspolnicy": None,
                    "samorzad_zawodowy": None, "adres_siedziby": None},
        "marka": {"logo": None, "logo_na_ciemnym": None, "logo_szerokosc": 140, "kolor": None, "kolor_zrodlo": None,
                  "kolor_dodatkowy": None, "tlo": "biale", "font_naglowki": None, "font_tekst": None, "promien": 2,
                  "sekcja_ciemna": "stopka"},
        "seo": {"fraza": None, "miasto": None, "opis": None},
        "social": {"facebook": None, "instagram": None, "google_maps": None, "linkedin": None, "youtube": None,
                   "tiktok": None},
        "opinie_zbiorczo": None,
        "przekierowania": None,
        "dostepnosc": None,
        "funkcje": {
            "hosting": "cloudflare", "formularz": None, "mapa": "link", "statystyki_cf_token": None, "tytul_tryb": "fraza",
            "telefon_w_naglowku": None, "etykiety_sekcji": False, "animacje": "brak", "myslnik": "polpauza",
            "boty_ai": "zezwol", "hsts_subdomeny": False, "hsts_preload": False, "faq_schema": False,
            "strona_dostepnosci": False, "rss": False,
        },
        "zrodla": {},
        "do_potwierdzenia": [],
    }


def szkielet_tresci(branza: str, preset: dict, schemat_wzgl: str) -> dict:
    sekcje = ", ".join(preset.get("sekcje_glowna", []))
    t = {
        "$schema": f"{schemat_wzgl}/tresc.schema.json",
        "$komentarz": (f"Sekcje strony głównej dla branży „{branza}” (kolejność z presetu): {sekcje}. "
                       "Blok null = sekcja się nie pokazuje. Wypełniaj tylko prawdziwą treścią od firmy. "
                       "Struktura bloków: docs/KONTRAKT.md §4.2."),
        "wersja_danych": 1,
        "hero": {"naglowek": None, "lead": None, "zdjecie": None, "podpis": None, "cta_glowne": None, "cta_drugie": None},
    }
    for b in BLOKI_TRESCI:
        t[b] = None
    t["kontakt"] = {"naglowek": None, "wstep": None}
    return t


# „Co i gdzie zmienić” w README klienta: wiersze wspólne + wiersz każdej sekcji, którą branża pokazuje
WIERSZE_WSPOLNE = [
    ("Telefon, e-mail, adres", "`data/firma.json` → `kontakt`"),
    ("Godziny otwarcia, święta i wyjątki", "`data/firma.json` → `godziny` (`wyjatki`: data, godziny, opis)"),
    ("Nagłówek i zdanie na pierwszym ekranie, zdjęcie", "`data/tresc.json` → `hero`"),
]
WIERSZE_SEKCJI = {
    "ogloszenie": ("Ogłoszenie („24–26.12 nieczynne”)", "`data/tresc.json` → `ogloszenie` (`tekst`, `od`, `do`)"),
    "oferta": ("Usługi i ceny", "`data/tresc.json` → `oferta`"),
    "cennik": ("Cennik", "`data/tresc.json` → `cennik`"),
    "menu": ("Karta dań i ceny", "`data/tresc.json` → `menu` (`data` = dzień, z którego jest karta)"),
    "produkty": ("Produkty", "`data/tresc.json` → `produkty`"),
    "realizacje": ("Realizacje", "`data/tresc.json` → `realizacje`"),
    "przetargi": ("Zamówienia publiczne", "`data/tresc.json` → `przetargi`"),
    "galeria": ("Zdjęcia w galerii", "`data/tresc.json` → `galeria` (id z `data/zdjecia.json`)"),
    "o_firmie": ("Tekst „O firmie”", "`data/tresc/o-firmie.md` (Markdown) i `data/tresc.json` → `o_firmie`"),
    "proces": ("Przebieg zlecenia", "`data/tresc.json` → `proces`"),
    "zasady": ("Zasady (gwarancja, zadatek, rezerwacje)", "`data/tresc.json` → `zasady`"),
    "zespol": ("Zespół", "`data/tresc.json` → `zespol` (zdjęcie tylko z `zgoda: true`)"),
    "liczby": ("Firma w liczbach", "`data/tresc.json` → `liczby` (każda liczba z datą)"),
    "opinie": ("Opinie", "`data/tresc.json` → `opinie` (cytat z linkiem do źródła)"),
    "certyfikaty": ("Certyfikaty", "`data/tresc.json` → `certyfikaty` (skany w `assets/img/pliki/`)"),
    "faq": ("Pytania i odpowiedzi", "`data/tresc.json` → `faq`"),
    "wspolpraca": ("Współpraca", "`data/tresc.json` → `wspolpraca`"),
    "gdzie_kupic": ("Punkty sprzedaży", "`data/tresc.json` → `gdzie_kupic`"),
    "do_pobrania": ("Pliki do pobrania", "`data/tresc.json` → `do_pobrania` (pliki w `assets/img/pliki/`)"),
    "aktualnosci": ("Aktualność", "nowy plik `data/aktualnosci/RRRR-MM-tytul.md`"),
}
WIERSZE_KONCOWE = [
    ("Nowe zdjęcie", "plik do `brief/zdjecia/`, wpis w `data/zdjecia.json`, potem `python3 tools/zdjecia.py`"),
    ("Logo, kolor, kroje, tło", "`data/firma.json` → `marka` (logo w `assets/img/`)"),
    ("Element-podpis, drobne różnice wyglądu", "`assets/css/wlasne.css`"),
    ("Dane rejestrowe w stopce", "`data/firma.json` → `rejestr`"),
    ("Formularz, mapa, statystyki", "`data/firma.json` → `funkcje` (opis przełączników: `docs/DECYZJE.md`)"),
    ("Tytuł karty i opis w Google", "`data/firma.json` → `seo`"),
]


def readme_klienta(branza: str, preset: dict) -> str:
    wiersze = WIERSZE_WSPOLNE + [WIERSZE_SEKCJI[s] for s in preset.get("sekcje_glowna", []) if s in WIERSZE_SEKCJI] \
        + WIERSZE_KONCOWE
    tabela = "\n".join(f"| {co} | {gdzie} |" for co, gdzie in wiersze)
    return f"""# Strona internetowa firmy

<!-- Wpisz w tytule nazwę firmy, a niżej jedno zdanie: co to za strona i pod jakim adresem działa. -->
Strona zbudowana z szablonu SZABLON (branża „{branza}”, wersja w pliku `SZABLON_WERSJA`). Treść jest w `data/`,
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
{tabela}

Po każdej zmianie: `python3 tools/build.py` — komunikaty mówią, który plik i pole poprawić.

## Do potwierdzenia z właścicielem

<!-- do-potwierdzenia:poczatek -->
- (lista powstaje z `data/firma.json` → `do_potwierdzenia`: `python3 tools/raport.py --readme`)
<!-- do-potwierdzenia:koniec -->
"""


def nietkniety_szkielet(dane: Path, schemat_wzgl: str) -> bool:
    """Czy istniejące pliki danych to szkielet z tools/start.py bez żadnej zmiany (wtedy wolno je zastąpić)."""
    try:
        firma = json.loads((dane / "firma.json").read_text(encoding="utf-8"))
        tresc = json.loads((dane / "tresc.json").read_text(encoding="utf-8"))
        zdjecia = json.loads((dane / "zdjecia.json").read_text(encoding="utf-8"))
        branza = firma["branza"]
        preset = json.loads((KORZEN / "tools" / "presety" / f"{branza}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return (firma == szkielet_firmy(branza, schemat_wzgl) and tresc == szkielet_tresci(branza, preset, schemat_wzgl)
            and zdjecia == szkielet_zdjec(schemat_wzgl)
            and not any(p.name != ".gitkeep" for p in (dane / "tresc").glob("*"))
            and not any(p.name != ".gitkeep" for p in (dane / "aktualnosci").glob("*")))


def szkielet_zdjec(schemat_wzgl: str) -> dict:
    return {"$schema": f"{schemat_wzgl}/zdjecia.schema.json", "wersja_danych": 1, "zdjecia": []}


def main() -> int:
    p = argparse.ArgumentParser(description="Szkielet danych klienta (same null-e) dla wybranej branży.")
    p.add_argument("--branza", required=True, choices=BRANZE)
    p.add_argument("--klient", default=".", help="katalog klienta (domyślnie korzeń repozytorium)")
    p.add_argument("--nadpisz", action="store_true", help="zastąp istniejące pliki danych")
    p.add_argument("--tylko-dane", action="store_true", help="tylko data/ — bez README klienta i bez zmiany wrangler.jsonc")
    a = p.parse_args()
    klient = Path(a.klient)
    klient = klient if klient.is_absolute() else (Path.cwd() / klient)
    dane = klient / "data"
    pliki = [dane / "firma.json", dane / "tresc.json", dane / "zdjecia.json"]
    istniejace = [f for f in pliki if f.exists()]
    preset = json.loads((KORZEN / "tools" / "presety" / f"{a.branza}.json").read_text(encoding="utf-8"))
    schemat_wzgl = Path(*([".."] * len(dane.resolve().relative_to(KORZEN.resolve()).parts)), "tools", "schemat") \
        if KORZEN.resolve() in dane.resolve().parents else KORZEN / "tools" / "schemat"
    schemat_wzgl = str(schemat_wzgl).replace("\\", "/")
    if istniejace and not a.nadpisz:
        if len(istniejace) == len(pliki) and nietkniety_szkielet(dane, schemat_wzgl):
            print("Pliki danych to nietknięty szkielet z tools/start.py — zastępuję szkieletem branży "
                  f"„{a.branza}”.")
        else:
            print("Pliki danych już istnieją i ktoś je zmieniał — nic nie zmieniam:")
            for f in istniejace:
                print(f"  {f}")
            print("Użyj --nadpisz, jeśli naprawdę chcesz zacząć od pustego szkieletu (stare dane przepadną).")
            return 1
    dane.mkdir(parents=True, exist_ok=True)
    (dane / "tresc").mkdir(exist_ok=True)
    (dane / "aktualnosci").mkdir(exist_ok=True)
    (dane / "aktualnosci" / ".gitkeep").touch()
    (dane / "tresc" / ".gitkeep").touch()
    zapisz = lambda plik, obj: plik.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    zapisz(dane / "firma.json", szkielet_firmy(a.branza, schemat_wzgl))
    zapisz(dane / "tresc.json", szkielet_tresci(a.branza, preset, schemat_wzgl))
    zapisz(dane / "zdjecia.json", szkielet_zdjec(schemat_wzgl))
    zdj = klient / "brief" / "zdjecia"
    zdj.mkdir(parents=True, exist_ok=True)
    readme = zdj / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Oryginały zdjęć\n\n"
            "Tu trafiają oryginalne zdjęcia od firmy (JPG/PNG, najlepiej ≥ 1920 px). Katalog jest poza gitem —\n"
            "commituje się tylko wynik `python3 tools/zdjecia.py` w `assets/img/foto/`.\n\n"
            "Każde zdjęcie opisz w `data/zdjecia.json`: skąd jest (`zrodlo`), kto je zrobił (`autor`), czy są na nim\n"
            "rozpoznawalne osoby (`osoby`, wtedy `zgoda: true`), i `alt` napisany po obejrzeniu zdjęcia.\n"
            "Nie używaj zdjęć stockowych udających firmę ani zdjęć z Google od klientów (należą do autorów).\n",
            encoding="utf-8")
    if not a.tylko_dane:
        readme = klient / "README.md"
        if not readme.exists() or readme.read_text(encoding="utf-8").startswith("# SZABLON"):
            readme.write_text(readme_klienta(a.branza, preset), encoding="utf-8")
            print(f"README klienta: {readme} (uzupełnij tytuł; sekcję „Do potwierdzenia” wypełnia tools/raport.py --readme)")
        wrangler = klient / "wrangler.jsonc"
        if wrangler.is_file():
            tekst = wrangler.read_text(encoding="utf-8")
            if re.search(r'"namespace_id"\s*:\s*"1101"', tekst):
                nowy = str(random.SystemRandom().randint(2000, 999999))
                wrangler.write_text(re.sub(r'("namespace_id"\s*:\s*)"1101"', rf'\g<1>"{nowy}"', tekst), encoding="utf-8")
                print(f"wrangler.jsonc: namespace_id limitu formularza = {nowy} (własny dla tej strony)")
    print(f"Szkielet dla branży „{a.branza}” zapisany w {dane}.")
    print("Dalej: uzupełnij dane i uruchom python3 tools/build.py — wypisze, czego jeszcze brakuje.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
