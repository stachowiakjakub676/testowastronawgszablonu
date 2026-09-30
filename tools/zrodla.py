#!/usr/bin/env python3
"""Kontrola brief/zrodla.md na końcu faz 0 i 1 (docs/PROCEDURA.md) — czy plik ma prawdziwe wpisy, a nie wzór.

  python3 tools/zrodla.py --faza 0        sekcja „Braki” wypełniona (albo „- brak braków”)
  python3 tools/zrodla.py --faza 1        + w tabeli „Fakty” wiersze z wartością, źródłem i datą dla nazwy, adresu,
                                          telefonu i danych rejestrowych
  python3 tools/zrodla.py --klient ../strona-firmy --faza 1

Wiersz faktu liczy się, gdy ma wartość, źródło bez „…” (wzór z szablonu ma „…” w adresach) i datę RRRR-MM-DD.
Kod wyjścia: 0 = OK, 1 = czegoś brakuje (lista wyżej). Tylko biblioteka standardowa.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

WYMAGANE_FAZA_1 = {
    "nazwa": r"nazwa",
    "adres": r"adres",
    "telefon": r"telefon",
    "dane rejestrowe": r"rejestr|nip|regon|krs|nazwa_prawna|forma_prawna",
}
RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sekcja(tekst: str, tytul: str) -> str:
    m = re.search(rf"^## {re.escape(tytul)}.*?$(.*?)(?=^## |\Z)", tekst, re.M | re.S)
    return m.group(1) if m else ""


def fakty(tekst: str) -> list[dict]:
    """Wiersze tabeli „Fakty”: {fakt, wartosc, zrodlo, data, ok, powod}."""
    wynik = []
    for linia in sekcja(tekst, "Fakty").splitlines():
        if not linia.startswith("|") or re.match(r"^\|\s*-", linia) or "Fakt (pole" in linia:
            continue
        kom = [k.strip() for k in linia.strip().strip("|").split("|")]
        if len(kom) < 4:
            continue
        fakt, wartosc, zrodlo, data = kom[:4]
        powod = None
        if not wartosc:
            powod = "brak wartości"
        elif not zrodlo or "…" in zrodlo or "..." in zrodlo:
            powod = "źródło puste albo ze wzoru („…”)"
        elif not RE_DATA.match(data):
            powod = "brak daty RRRR-MM-DD"
        wynik.append({"fakt": fakt, "wartosc": wartosc, "zrodlo": zrodlo, "data": data, "ok": powod is None,
                      "powod": powod})
    return wynik


def braki_wypelnione(tekst: str) -> bool:
    """Choć jedna pozycja w „Braki” z treścią po literze („- A: godziny sobotnie”) albo „- brak braków”."""
    for linia in sekcja(tekst, "Braki").splitlines():
        m = re.match(r"^\s*-\s*(?:[A-E]\s*:)?\s*(.*)$", linia)
        if m and m.group(1).strip():
            return True
    return False


def main() -> int:
    p = argparse.ArgumentParser(description="Czy brief/zrodla.md ma prawdziwe wpisy (koniec faz 0 i 1).")
    p.add_argument("--klient", default=".")
    p.add_argument("--faza", type=int, choices=[0, 1], default=1)
    a = p.parse_args()
    plik = Path(a.klient) / "brief" / "zrodla.md"
    if not plik.is_file():
        print(f"BŁĄD: nie ma pliku {plik}")
        return 1
    tekst = plik.read_text(encoding="utf-8")
    problemy = []
    if not braki_wypelnione(tekst):
        problemy.append("sekcja „Braki” jest pusta — wypisz, czego brakuje (litery A–E z BRIEF.md) albo „- brak braków”")
    if a.faza >= 1:
        wiersze = fakty(tekst)
        dobre = [w for w in wiersze if w["ok"]]
        for nazwa, wzor in WYMAGANE_FAZA_1.items():
            if not any(re.search(wzor, w["fakt"], re.I) for w in dobre):
                problemy.append(f"brak wiersza faktu „{nazwa}” z wartością, źródłem i datą")
        for w in wiersze:
            if not w["ok"] and w["wartosc"]:
                problemy.append(f"wiersz „{w['fakt']}”: {w['powod']}")
        print(f"brief/zrodla.md: {len(dobre)} wierszy faktów z wartością, źródłem i datą")
    for x in problemy:
        print(f"  - {x}")
    print("Wynik: OK" if not problemy else f"Wynik: {len(problemy)} do poprawienia")
    return 1 if problemy else 0


if __name__ == "__main__":
    sys.exit(main())
