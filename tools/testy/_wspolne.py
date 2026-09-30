"""Wspólne dla testów silnika (tools/testy/test_*.py) i generatora fikstur (tools/testy/klienci/generuj.py).

- KORZEN i ścieżka do modułów silnika (tools/silnik) — tak samo jak w tools/build.py;
- DZIS: jeden, stały „dziś” dla testów, fikstur i CI (SZABLON_DZIS), żeby daty w fiksturach się nie starzały;
- zbuduj(): build.py w osobnym procesie, do katalogu tymczasowego, z komunikatami jako JSON.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent.parent
if str(KORZEN / "tools") not in sys.path:
    sys.path.insert(0, str(KORZEN / "tools"))

# Zmieniasz datę? Przelicz fikstury: python3 tools/testy/klienci/generuj.py --tylko-dane (daty są względne do DZIS)
# i zmień SZABLON_DZIS w .github/workflows/sprawdz.yml.
DZIS = "2026-10-01"
DZIS_DATA = dt.date.fromisoformat(DZIS)

BIMEX = KORZEN / "przyklady" / "bimex"
KLIENCI = KORZEN / "tools" / "testy" / "klienci"
FIKSTURY = ["restauracja", "producent", "uslugi", "gabinet"]


class Wynik:
    """Wynik jednego buildu: kod wyjścia, komunikaty (lista słowników z --json) i katalog wyniku."""

    def __init__(self, kod: int, stdout: str, stderr: str, dist: Path):
        self.kod, self.stdout, self.stderr, self.dist = kod, stdout, stderr, dist
        try:
            dane = json.loads(stdout)
        except ValueError:
            dane = {"wynik": {}, "komunikaty": []}
        self.wynik = dane.get("wynik", {})
        self.komunikaty = dane.get("komunikaty", [])

    def poziom(self, poziom: str) -> list[dict]:
        return [k for k in self.komunikaty if k["poziom"] == poziom]

    @property
    def bledy(self) -> list[dict]:
        return self.poziom("BŁĄD")

    def teksty(self, poziom: str | None = None) -> list[str]:
        return [k["tresc"] for k in self.komunikaty if poziom is None or k["poziom"] == poziom]

    def opis_bledow(self) -> str:
        return "\n".join(f"  {k.get('plik') or ''} [{k.get('pole') or ''}] {k['tresc']}" for k in self.bledy) \
            or self.stderr[-3000:]


def zbuduj(klient: Path, *argumenty: str, dzis: str | None = DZIS, wyjscie: Path | None = None,
           sprzataj=None) -> Wynik:
    """python3 tools/build.py --klient <klient> --wyjscie <tmp> --json [argumenty]. `sprzataj` — np. TestCase.addCleanup."""
    if wyjscie is None:
        wyjscie = Path(tempfile.mkdtemp(prefix="szablon-test-")) / "dist"
        if sprzataj:
            sprzataj(shutil.rmtree, wyjscie.parent, True)
    env = dict(os.environ)
    env.pop("SZABLON_DZIS", None)
    if dzis:
        env["SZABLON_DZIS"] = dzis
    p = subprocess.run([sys.executable, str(KORZEN / "tools" / "build.py"), "--klient", str(klient),
                        "--wyjscie", str(wyjscie), "--json", *argumenty],
                       capture_output=True, text=True, env=env, cwd=KORZEN, timeout=300)
    return Wynik(p.returncode, p.stdout, p.stderr, wyjscie)


def kopia_klienta(zrodlo: Path, sprzataj=None) -> Path:
    """Kopia katalogu klienta w katalogu tymczasowym (do mutowania danych w teście)."""
    tmp = Path(tempfile.mkdtemp(prefix="szablon-klient-"))
    if sprzataj:
        sprzataj(shutil.rmtree, tmp, True)
    cel = tmp / zrodlo.name
    shutil.copytree(zrodlo, cel, ignore=shutil.ignore_patterns("brief"))
    return cel


def czytaj_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def zapisz_json(p: Path, obiekt) -> None:
    p.write_text(json.dumps(obiekt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
