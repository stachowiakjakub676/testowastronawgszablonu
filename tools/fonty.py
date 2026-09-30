#!/usr/bin/env python3
"""Biblioteka krojów pisma: przygotowanie plików woff2 (łacina + polskie znaki) i metryk zamiennika.

Uruchamiane tylko lokalnie, przy dodawaniu kroju — wynik (woff2 + fonty.json) trafia do repozytorium.
Wymaga fontTools (i brotli do woff2):  python3 -m pip install fonttools brotli

Polecenia:
  python3 tools/fonty.py dodaj <id> --nazwa "Barlow" --styl sans --plik Barlow-Regular.ttf --plik Barlow-SemiBold.ttf \
          --licencja OFL.txt --waga-naglowkow 600 --pochodzenie "google/fonts ofl/barlow"
      Krój zmienny (wght): zostaje oś wght 400–700, pozostałe osie przypięte do wartości domyślnej → <id>/<id>-pl.woff2.
      Krój statyczny: jeden plik na wagę → <id>/<id>-<waga>-pl.woff2.
  python3 tools/fonty.py metryki [<id> …]     przelicza zamiennik (size-adjust, ascent/descent/line-gap-override)
  python3 tools/fonty.py sprawdz               sprawdza, czy każdy plik ma wszystkie polskie znaki

Zamiennik metryczny: średnia szerokość znaków (ważona częstością liter w polskim tekście) porównana
z Arial (kroje bezszeryfowe) albo Times New Roman (szeryfowe). Dzięki temu tekst w kroju systemowym zajmuje
tyle samo miejsca co docelowy krój, więc po doczytaniu fontu strona nie „skacze” (CLS).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
FONTY = KORZEN / "assets" / "fonts"
KATALOG = FONTY / "fonty.json"

# zakres znaków: łacina podstawowa + Latin-1, polskie litery, cudzysłowy, półpauza/pauza, wielokropek, €, ™
ZAKRES = ("U+0000-00FF, U+0104-0107, U+0118-0119, U+0141-0144, U+015A-015B, U+0179-017C, "
          "U+2013-2014, U+2018-201A, U+201C-201E, U+2022, U+2026, U+20AC, U+2122, U+2212")
POLSKIE = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ„”–…"

# częstość liter w polskim tekście (%), spacja ≈ 15 %
CZESTOSC = {"a": 8.91, "i": 8.21, "o": 7.75, "e": 7.66, "z": 5.64, "n": 5.52, "r": 4.69, "w": 4.65, "s": 4.32,
            "t": 3.98, "c": 3.96, "y": 3.76, "k": 3.51, "d": 3.25, "p": 3.13, "m": 2.80, "u": 2.50, "j": 2.28,
            "l": 2.10, "ł": 1.82, "b": 1.47, "g": 1.42, "ę": 1.11, "h": 1.08, "ą": 0.99, "ó": 0.85, "ż": 0.83,
            "ś": 0.66, "ć": 0.40, "f": 0.30, "ń": 0.20, "ź": 0.06, " ": 15.0}
BAZA = str.maketrans("ąćęłńóśźż", "acelnoszz")
# szerokości znaków (na 1000 jednostek) — Arial = metryki Helvetiki, Times New Roman = metryki Times
ARIAL = dict(zip("abcdefghijklmnopqrstuvwxyz ", [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556,
                                                 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 278]))
TIMES = dict(zip("abcdefghijklmnopqrstuvwxyz ", [444, 500, 444, 500, 444, 333, 500, 500, 278, 278, 500, 278, 778, 500,
                                                 500, 500, 500, 333, 389, 278, 500, 500, 722, 500, 500, 444, 250]))
ZAMIENNIKI = {"sans": (["Arial", "Helvetica", "Liberation Sans"], ARIAL),
              "serif": (["Times New Roman", "Times", "Liberation Serif"], TIMES)}


def _fonttools():
    try:
        from fontTools.ttLib import TTFont  # noqa: F401
        return True
    except ImportError:
        sys.exit("Zainstaluj fontTools: python3 -m pip install fonttools brotli")


def _unicodes():
    wynik = set()
    for czesc in ZAKRES.split(","):
        czesc = czesc.strip()[2:]
        if "-" in czesc:
            a, b = czesc.split("-")
            wynik.update(range(int(a, 16), int(b, 16) + 1))
        else:
            wynik.add(int(czesc, 16))
    return sorted(wynik)


def _srednia(szerokosci: dict) -> float:
    suma = sum(CZESTOSC.values())
    return sum(szerokosci[z.translate(BAZA)] * c for z, c in CZESTOSC.items()) / suma / 1000


def metryki(plik: Path, styl: str) -> dict:
    """Wartości @font-face zamiennika dla pliku kroju (dla krojów zmiennych: instancja wght 400)."""
    from fontTools.ttLib import TTFont
    f = TTFont(str(plik))
    if "fvar" in f:
        from fontTools.varLib import instancer
        osie = {a.axisTag: (400 if a.axisTag == "wght" and a.minValue <= 400 <= a.maxValue else a.defaultValue)
                for a in f["fvar"].axes}
        f = instancer.instantiateVariableFont(f, osie)
    upm = f["head"].unitsPerEm
    hhea = f["hhea"]
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    suma = sum(CZESTOSC.values())
    srednia = sum(hmtx[cmap[ord(z)]][0] * c for z, c in CZESTOSC.items() if ord(z) in cmap) / suma / upm
    lokalne, wzor = ZAMIENNIKI[styl]
    size_adjust = srednia / _srednia(wzor)
    proc = lambda x: f"{x * 100:.2f}%"
    return {"lokalny": lokalne,
            "size_adjust": proc(size_adjust),
            "ascent": proc(hhea.ascent / upm / size_adjust),
            "descent": proc(abs(hhea.descent) / upm / size_adjust),
            "line_gap": proc(hhea.lineGap / upm / size_adjust)}


def podzbior(zrodlo: Path, cel: Path) -> str:
    """Tworzy woff2 łacina+PL. Zwraca opis wagi: „400 700” (zmienny) albo „600” (statyczny)."""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    f = TTFont(str(zrodlo))
    if "fvar" in f:
        from fontTools.varLib import instancer
        osie = {}
        for a in f["fvar"].axes:
            if a.axisTag == "wght":
                osie["wght"] = (max(400, a.minValue), min(700, a.maxValue))
            elif a.axisTag == "wdth" and a.minValue <= 100 <= a.maxValue:
                osie["wdth"] = 100
            else:
                osie[a.axisTag] = a.defaultValue
        f = instancer.instantiateVariableFont(f, osie)
        waga = f"{int(osie['wght'][0])} {int(osie['wght'][1])}" if "wght" in osie else "400"
    else:
        waga = str(f["OS/2"].usWeightClass)
    opcje = subset.Options()
    opcje.flavor = "woff2"
    opcje.layout_features = ["*"]
    opcje.name_IDs = ["*"]
    opcje.notdef_outline = True
    s = subset.Subsetter(opcje)
    s.populate(unicodes=_unicodes())
    s.subset(f)
    f.flavor = "woff2"
    cel.parent.mkdir(parents=True, exist_ok=True)
    f.save(str(cel))
    return waga


def wczytaj_katalog() -> dict:
    return json.loads(KATALOG.read_text(encoding="utf-8")) if KATALOG.exists() else {}


def zapisz_katalog(k: dict) -> None:
    KATALOG.write_text(json.dumps(k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dodaj(a) -> None:
    _fonttools()
    katalog = wczytaj_katalog()
    pliki = []
    for zrodlo in a.plik:
        zrodlo = Path(zrodlo)
        from fontTools.ttLib import TTFont
        zmienny = "fvar" in TTFont(str(zrodlo))
        if zmienny:
            cel = FONTY / a.id / f"{a.id}-pl.woff2"
        else:
            cel = FONTY / a.id / f"{a.id}-{TTFont(str(zrodlo))['OS/2'].usWeightClass}-pl.woff2"
        waga = podzbior(zrodlo, cel)
        pliki.append({"plik": str(cel.relative_to(FONTY)), "waga": waga, "styl_kroju": "normal"})
        print(f"  {cel.relative_to(KORZEN)}: {cel.stat().st_size / 1024:.1f} KB, waga {waga}")
    if a.licencja:
        shutil.copy(a.licencja, FONTY / a.id / "OFL.txt")
    wpis = katalog.get(a.id, {})
    wpis.update({
        "nazwa": a.nazwa, "styl": a.styl, "pochodzenie": a.pochodzenie or wpis.get("pochodzenie"),
        "pliki": pliki,
        "waga_tekstu": 400, "waga_mocna": a.waga_mocna, "waga_naglowkow": a.waga_naglowkow,
        "licencja": f"{a.id}/OFL.txt",
    })
    wpis["zamiennik"] = metryki(FONTY / pliki[0]["plik"], a.styl)
    katalog[a.id] = wpis
    zapisz_katalog(katalog)
    print(f"Dodano „{a.id}” do assets/fonts/fonty.json")


def przelicz(a) -> None:
    _fonttools()
    katalog = wczytaj_katalog()
    for kid, wpis in katalog.items():
        if kid.startswith("$") or (a.id and kid not in a.id):
            continue
        pliki = sorted(wpis["pliki"], key=lambda p: abs(int(p["waga"].split()[0]) - 400))
        wpis["zamiennik"] = metryki(FONTY / pliki[0]["plik"], wpis["styl"])
        print(f"  {kid}: {wpis['zamiennik']}")
    zapisz_katalog(katalog)


def sprawdz(a) -> None:
    _fonttools()
    from fontTools.ttLib import TTFont
    katalog = wczytaj_katalog()
    ok = True
    for kid, wpis in katalog.items():
        if kid.startswith("$"):
            continue
        for p in wpis["pliki"]:
            sciezka = FONTY / p["plik"]
            if not sciezka.exists():
                print(f"BŁĄD: {kid}: brak pliku {p['plik']}")
                ok = False
                continue
            cmap = TTFont(str(sciezka)).getBestCmap()
            brak = [z for z in POLSKIE if ord(z) not in cmap]
            rozmiar = sciezka.stat().st_size / 1024
            stan = "OK" if not brak and rozmiar <= 60 else "BŁĄD"
            ok &= stan == "OK"
            print(f"{stan}: {p['plik']} {rozmiar:.1f} KB" + (f", brak znaków: {''.join(brak)}" if brak else "")
                  + (" (limit 60 KB)" if rozmiar > 60 else ""))
        if not (FONTY / wpis.get("licencja", "-")).exists():
            print(f"BŁĄD: {kid}: brak pliku licencji {wpis.get('licencja')}")
            ok = False
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description="Krój pisma → woff2 łacina+PL i metryki zamiennika (wymaga fontTools).")
    sub = p.add_subparsers(dest="polecenie", required=True)
    d = sub.add_parser("dodaj", help="dodaj krój do assets/fonts/")
    d.add_argument("id")
    d.add_argument("--nazwa", required=True, help="nazwa rodziny w CSS, np. „Barlow Condensed”")
    d.add_argument("--styl", choices=["sans", "serif"], required=True)
    d.add_argument("--plik", action="append", required=True, help="plik TTF/OTF (zmienny albo po jednym na wagę)")
    d.add_argument("--licencja", help="plik OFL.txt")
    d.add_argument("--waga-naglowkow", type=int, default=600)
    d.add_argument("--waga-mocna", type=int, default=600)
    d.add_argument("--pochodzenie", help="skąd są pliki, np. „google/fonts ofl/barlow”")
    d.set_defaults(f=dodaj)
    m = sub.add_parser("metryki", help="przelicz metryki zamiennika")
    m.add_argument("id", nargs="*")
    m.set_defaults(f=przelicz)
    s = sub.add_parser("sprawdz", help="sprawdź polskie znaki, rozmiary i licencje")
    s.set_defaults(f=sprawdz)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
