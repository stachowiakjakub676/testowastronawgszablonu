"""Narzędzia personalizacji: tools/zrodla.py (koniec faz 0 i 1), tools/skill.py (SKILL.md = PROCEDURA)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _wspolne import KORZEN


def zrodla(klient: Path, faza: int) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(KORZEN / "tools" / "zrodla.py"), "--klient", str(klient), "--faza", str(faza)],
                          capture_output=True, text=True)


class Zrodla(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="szablon-zrodla-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "brief").mkdir()
        self.plik = self.tmp / "brief" / "zrodla.md"
        self.wzor = (KORZEN / "brief" / "zrodla.md").read_text(encoding="utf-8")

    def test_wzor_z_szablonu_nie_przechodzi(self):
        """Wzór ma adresy URL z „…” — grep -c https przechodził na nietkniętym pliku."""
        self.plik.write_text(self.wzor, encoding="utf-8")
        self.assertEqual(zrodla(self.tmp, 0).returncode, 1)
        self.assertEqual(zrodla(self.tmp, 1).returncode, 1)

    def test_wypelniony_przechodzi(self):
        tekst = self.wzor.replace("| kontakt.adres | | | |", "| kontakt.adres | ul. Testowa 1, 00-001 Testowo | "
                                  "https://www.facebook.com/przyklad | 2026-09-30 |")
        tekst = tekst.replace("| kontakt.telefon | | | |", "| kontakt.telefon | +48500000001 | baner na Facebooku | 2026-09-30 |")
        tekst = tekst.replace("## Fakty\n", "## Fakty\n")
        tekst = tekst.replace("| firma.nazwa_prawna | |", "| firma.nazwa, firma.nazwa_prawna | Test sp. z o.o. |")
        tekst = tekst.replace("https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/…?rejestr=P&format=json | |",
                              "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/0000000001?rejestr=P&format=json | 2026-09-30 |")
        tekst = tekst.replace("- A:\n", "- A: godziny w sobotę\n")
        self.plik.write_text(tekst, encoding="utf-8")
        w = zrodla(self.tmp, 1)
        self.assertEqual(w.returncode, 0, w.stdout)


class Skill(unittest.TestCase):
    def test_skill_zgodny_z_procedura(self):
        w = subprocess.run([sys.executable, str(KORZEN / "tools" / "skill.py"), "--sprawdz"], capture_output=True, text=True)
        self.assertEqual(w.returncode, 0, w.stdout)
