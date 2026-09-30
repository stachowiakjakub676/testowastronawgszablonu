#!/usr/bin/env python3
"""Polskie święta i dni o nietypowych godzinach — do przypominania o godzinach świątecznych (KONTRAKT §10).

Dni wolne od pracy (ustawa z 18 stycznia 1951 r. o dniach wolnych od pracy, z późniejszymi zmianami):
  1.01 Nowy Rok · 6.01 Trzech Króli (od 2011 r.) · Wielkanoc i Poniedziałek Wielkanocny · 1.05 Święto Pracy ·
  3.05 Święto Konstytucji 3 Maja · Zielone Świątki (niedziela, Wielkanoc + 49 dni) · Boże Ciało (Wielkanoc + 60 dni) ·
  15.08 Wniebowzięcie NMP · 1.11 Wszystkich Świętych · 11.11 Święto Niepodległości ·
  24.12 Wigilia (dzień wolny od 2025 r.) · 25.12 i 26.12 Boże Narodzenie.
Dni zwyczajowo krótsze (nie są ustawowo wolne): Wielka Sobota (sklepy do 14:00), Sylwester, Wigilia przed 2025 r.
Niedziele handlowe (ustawa z 10 stycznia 2018 r. o ograniczeniu handlu w niedziele, zmiana od 2025 r.) — wyliczane
„na najlepszą wiedzę” i zawsze oznaczone „do potwierdzenia”: ostatnia niedziela stycznia, kwietnia, czerwca i sierpnia,
niedziela przed Wielkanocą i niedziele przed Bożym Narodzeniem (od 2025 r. trzy, w latach 2020–2024 dwie).

Użycie:
  python3 tools/swieta.py                 lista na bieżący rok
  python3 tools/swieta.py 2027            lista na rok 2027
  python3 tools/swieta.py 2026 --json     jako JSON
  python3 tools/swieta.py --od 2026-12-01 [--dni 45]   co wypada w najbliższych dniach

Build (tools/silnik/dane.py): dla branż z godzinami dla klientów (preset „pokazuj_status_w_hero”) — gdy do święta
zostało ≤ 45 dni, dzień jest zwykle otwarty, a w godziny.wyjatki nie ma tej daty — ostrzeżenie
„POTWIERDŹ: godziny na 24.12 (Wigilia)”. Tylko biblioteka standardowa Pythona.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from dataclasses import dataclass

USTAWOWE = "ustawowe"          # dzień wolny od pracy
ZWYCZAJOWE = "zwyczajowe"      # zwykle krótsze godziny (Wielka Sobota, Sylwester)
HANDLOWA = "niedziela_handlowa"

DNI_KODY = ["pn", "wt", "sr", "cz", "pt", "sb", "nd"]     # jak w data/firma.json → godziny.tydzien


@dataclass(frozen=True, order=True)
class Swieto:
    data: dt.date
    nazwa: str
    typ: str
    do_potwierdzenia: bool = False

    def slownik(self) -> dict:
        return {"data": self.data.isoformat(), "nazwa": self.nazwa, "typ": self.typ,
                "do_potwierdzenia": self.do_potwierdzenia}


def wielkanoc(rok: int) -> dt.date:
    """Niedziela Wielkanocna (kalendarz gregoriański) — algorytm Meeusa/Jonesa/Butchera."""
    a = rok % 19
    b, c = divmod(rok, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    miesiac, dzien = divmod(h + l_ - 7 * m + 114, 31)
    return dt.date(rok, miesiac, dzien + 1)


def _ostatnia_niedziela(rok: int, miesiac: int) -> dt.date:
    nastepny = dt.date(rok + (miesiac == 12), miesiac % 12 + 1, 1)
    d = nastepny - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - 6) % 7)


def dni_wolne(rok: int) -> list[Swieto]:
    w = wielkanoc(rok)
    lista = [
        (dt.date(rok, 1, 1), "Nowy Rok"),
        (w, "Wielkanoc"),
        (w + dt.timedelta(days=1), "Poniedziałek Wielkanocny"),
        (dt.date(rok, 5, 1), "Święto Pracy"),
        (dt.date(rok, 5, 3), "Święto Konstytucji 3 Maja"),
        (w + dt.timedelta(days=49), "Zielone Świątki"),
        (w + dt.timedelta(days=60), "Boże Ciało"),
        (dt.date(rok, 8, 15), "Wniebowzięcie NMP"),
        (dt.date(rok, 11, 1), "Wszystkich Świętych"),
        (dt.date(rok, 11, 11), "Święto Niepodległości"),
        (dt.date(rok, 12, 25), "Boże Narodzenie"),
        (dt.date(rok, 12, 26), "Drugi dzień Bożego Narodzenia"),
    ]
    if rok >= 2011:
        lista.append((dt.date(rok, 1, 6), "Trzech Króli"))
    if rok >= 2025:
        lista.append((dt.date(rok, 12, 24), "Wigilia"))
    return sorted(Swieto(d, n, USTAWOWE) for d, n in lista)


def dni_zwyczajowe(rok: int) -> list[Swieto]:
    lista = [Swieto(wielkanoc(rok) - dt.timedelta(days=1), "Wielka Sobota", ZWYCZAJOWE),
             Swieto(dt.date(rok, 12, 31), "Sylwester", ZWYCZAJOWE)]
    if rok < 2025:
        lista.append(Swieto(dt.date(rok, 12, 24), "Wigilia", ZWYCZAJOWE))
    return sorted(lista)


def niedziele_handlowe(rok: int) -> list[Swieto]:
    """Niedziele handlowe „na najlepszą wiedzę” (przed 2020 r. inne zasady — lista pusta). Zawsze do potwierdzenia."""
    if rok < 2020:
        return []
    wolne = {s.data for s in dni_wolne(rok)}
    kandydaci = [_ostatnia_niedziela(rok, m) for m in (1, 4, 6, 8)]
    kandydaci.append(wielkanoc(rok) - dt.timedelta(days=7))
    ile = 3 if rok >= 2025 else 2
    d = dt.date(rok, 12, 24)
    d -= dt.timedelta(days=(d.weekday() - 6) % 7)        # ostatnia niedziela przed 25.12 (może być 24.12)
    przed_bn = []
    while len(przed_bn) < ile:
        if d not in wolne:
            przed_bn.append(d)
        d -= dt.timedelta(days=7)
    kandydaci += przed_bn
    return sorted(Swieto(x, "niedziela handlowa", HANDLOWA, True) for x in set(kandydaci) if x not in wolne)


def wszystkie(rok: int, handlowe: bool = True) -> list[Swieto]:
    return sorted(dni_wolne(rok) + dni_zwyczajowe(rok) + (niedziele_handlowe(rok) if handlowe else []))


def najblizsze(dzis: dt.date, dni: int = 45, handlowe: bool = False) -> list[Swieto]:
    """Święta od dziś (włącznie) do dziś + dni."""
    koniec = dzis + dt.timedelta(days=dni)
    lista = []
    for rok in range(dzis.year, koniec.year + 1):
        lista += [s for s in wszystkie(rok, handlowe) if dzis <= s.data <= koniec]
    return sorted(lista)


def do_potwierdzenia(tydzien: dict | None, wyjatki: list | None, dzis: dt.date, dni: int = 45) -> list[Swieto]:
    """Święta w ciągu `dni`, które wypadają w dzień zwykle otwarty i nie mają wpisu w godziny.wyjatki."""
    wpisane = {str(w.get("data")) for w in (wyjatki or []) if isinstance(w, dict)}
    wynik = []
    for s in najblizsze(dzis, dni):
        if s.data.isoformat() in wpisane:
            continue
        if tydzien is not None and not tydzien.get(DNI_KODY[s.data.weekday()]):
            continue                      # i tak zamknięte w ten dzień tygodnia — nie ma czego potwierdzać
        wynik.append(s)
    return wynik


def komunikat(s: Swieto) -> str:
    return f"POTWIERDŹ: godziny na {s.data.day:02d}.{s.data.month:02d} ({s.nazwa})"


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    jako_json = "--json" in argv
    try:
        if "--od" in argv:
            od = dt.date.fromisoformat(argv[argv.index("--od") + 1])
            dni = int(argv[argv.index("--dni") + 1]) if "--dni" in argv else 45
            lista = najblizsze(od, dni, handlowe=True)
            tytul = f"Od {od.strftime('%d.%m.%Y')} przez {dni} dni"
        else:
            liczby = [a for a in argv if a.isdigit()]
            rok = int(liczby[0]) if liczby else dt.date.today().year
            lista = wszystkie(rok)
            tytul = f"Święta i dni o nietypowych godzinach — {rok}"
    except (ValueError, IndexError):
        print("swieta.py: podaj rok (np. 2027) albo --od RRRR-MM-DD [--dni 45]", file=sys.stderr)
        return 2
    if jako_json:
        print(json.dumps([s.slownik() for s in lista], ensure_ascii=False, indent=1))
        return 0
    dni_tyg = ["pn.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."]
    opis = {USTAWOWE: "dzień wolny", ZWYCZAJOWE: "zwykle krótsze godziny", HANDLOWA: "do potwierdzenia"}
    print(tytul)
    for s in lista:
        print(f"  {s.data.strftime('%d.%m.%Y')}  {dni_tyg[s.data.weekday()]:7} {s.nazwa:32} {opis[s.typ]}")
    if any(s.do_potwierdzenia for s in lista):
        print("\nNiedziele handlowe policzone według ustawy (stan 2025); sprawdź aktualny kalendarz przed publikacją.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
