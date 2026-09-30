#!/usr/bin/env python3
"""Wszystkie testy silnika: python3 tools/testy/uruchom.py  (tylko biblioteka standardowa Pythona ≥ 3.10).

  python3 tools/testy/uruchom.py              wszystkie testy
  python3 tools/testy/uruchom.py -k godziny   tylko testy, których nazwa zawiera „godziny”
  python3 tools/testy/uruchom.py test_kolory  jeden plik
  python3 tools/testy/uruchom.py -q           mniej wypisywania

To samo co: cd tools/testy && python3 -m unittest discover -p "test_*.py".
Kod wyjścia: 0 = wszystko przeszło, 1 = któryś test nie przeszedł.
"""
from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

TUTAJ = Path(__file__).resolve().parent


def main() -> int:
    p = argparse.ArgumentParser(description="Testy silnika SZABLON (unittest).")
    p.add_argument("pliki", nargs="*", help="moduły testów, np. test_dane (domyślnie wszystkie)")
    p.add_argument("-k", dest="wzorce", action="append", help="tylko testy pasujące do wzorca (można powtórzyć)")
    p.add_argument("-q", action="store_true", help="mniej wypisywania")
    a = p.parse_args()
    sys.path.insert(0, str(TUTAJ))
    ladowacz = unittest.TestLoader()
    if a.wzorce:
        ladowacz.testNamePatterns = [f"*{w}*" for w in a.wzorce]
    if a.pliki:
        zestaw = ladowacz.loadTestsFromNames([Path(x).stem for x in a.pliki])
    else:
        zestaw = ladowacz.discover(str(TUTAJ), pattern="test_*.py", top_level_dir=str(TUTAJ))
    wynik = unittest.TextTestRunner(verbosity=1 if a.q else 2).run(zestaw)
    if wynik.wasSuccessful():
        print(f"\nTesty: OK ({wynik.testsRun})")
        return 0
    print(f"\nTesty: {len(wynik.failures)} nieudanych, {len(wynik.errors)} błędów (z {wynik.testsRun})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
