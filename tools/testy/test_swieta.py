"""Testy tools/swieta.py: Wielkanoc, dni wolne, niedziele handlowe i przypomnienie o godzinach świątecznych.

Uruchom:  python3 -m unittest discover -s tools/testy -v
"""
import contextlib
import datetime as dt
import io
import json
import sys
import unittest
from pathlib import Path

NARZEDZIA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(NARZEDZIA))

import swieta  # noqa: E402
from silnik import dane as dane_mod  # noqa: E402
from silnik.komunikaty import Raport  # noqa: E402

D = dt.date
OTWARTE_PN_SB = {"pn": [["08:00", "16:00"]], "wt": [["08:00", "16:00"]], "sr": [["08:00", "16:00"]],
                 "cz": [["08:00", "16:00"]], "pt": [["08:00", "16:00"]], "sb": [["09:00", "13:00"]], "nd": []}


class Wielkanoc(unittest.TestCase):
    def test_znane_daty(self):
        for rok, data in [(2019, D(2019, 4, 21)), (2024, D(2024, 3, 31)), (2025, D(2025, 4, 20)), (2026, D(2026, 4, 5)),
                          (2027, D(2027, 3, 28)), (2038, D(2038, 4, 25)), (2285, D(2285, 3, 22)), (1943, D(1943, 4, 25))]:
            with self.subTest(rok=rok):
                self.assertEqual(swieta.wielkanoc(rok), data)

    def test_zawsze_niedziela(self):
        for rok in range(1900, 2201):
            self.assertEqual(swieta.wielkanoc(rok).weekday(), 6, rok)


class DniWolne(unittest.TestCase):
    def daty(self, rok):
        return {s.data: s.nazwa for s in swieta.dni_wolne(rok)}

    def test_2026(self):
        d = self.daty(2026)
        self.assertEqual(len(d), 14)
        self.assertEqual(d[D(2026, 6, 4)], "Boże Ciało")
        self.assertEqual(d[D(2026, 5, 24)], "Zielone Świątki")
        self.assertEqual(d[D(2026, 4, 6)], "Poniedziałek Wielkanocny")
        self.assertIn(D(2026, 12, 24), d)

    def test_wigilia_od_2025(self):
        self.assertIn(D(2025, 12, 24), self.daty(2025))
        self.assertNotIn(D(2024, 12, 24), self.daty(2024))
        zwycz = {s.data for s in swieta.dni_zwyczajowe(2024)}
        self.assertIn(D(2024, 12, 24), zwycz)                 # przed 2025 r. — dzień o krótszych godzinach
        self.assertNotIn(D(2025, 12, 24), {s.data for s in swieta.dni_zwyczajowe(2025)})

    def test_trzech_kroli_od_2011(self):
        self.assertNotIn(D(2010, 1, 6), self.daty(2010))
        self.assertIn(D(2011, 1, 6), self.daty(2011))

    def test_wielka_sobota_i_sylwester(self):
        zw = {s.data: s.nazwa for s in swieta.dni_zwyczajowe(2026)}
        self.assertEqual(zw[D(2026, 4, 4)], "Wielka Sobota")
        self.assertEqual(zw[D(2026, 12, 31)], "Sylwester")


class NiedzieleHandlowe(unittest.TestCase):
    def test_2025(self):
        self.assertEqual([s.data for s in swieta.niedziele_handlowe(2025)],
                         [D(2025, 1, 26), D(2025, 4, 13), D(2025, 4, 27), D(2025, 6, 29), D(2025, 8, 31),
                          D(2025, 12, 7), D(2025, 12, 14), D(2025, 12, 21)])

    def test_2026_i_oznaczenie(self):
        lista = swieta.niedziele_handlowe(2026)
        self.assertEqual([s.data for s in lista],
                         [D(2026, 1, 25), D(2026, 3, 29), D(2026, 4, 26), D(2026, 6, 28), D(2026, 8, 30),
                          D(2026, 12, 6), D(2026, 12, 13), D(2026, 12, 20)])
        self.assertTrue(all(s.do_potwierdzenia and s.typ == swieta.HANDLOWA for s in lista))

    def test_dwie_przed_bozym_narodzeniem_do_2024(self):
        grudzien = [s.data for s in swieta.niedziele_handlowe(2024) if s.data.month == 12]
        self.assertEqual(grudzien, [D(2024, 12, 15), D(2024, 12, 22)])

    def test_nigdy_w_swieto_i_zawsze_niedziela(self):
        for rok in range(2020, 2040):
            wolne = {s.data for s in swieta.dni_wolne(rok)}
            for s in swieta.niedziele_handlowe(rok):
                self.assertEqual(s.data.weekday(), 6)
                self.assertNotIn(s.data, wolne)

    def test_przed_2020_puste(self):
        self.assertEqual(swieta.niedziele_handlowe(2019), [])


class DoPotwierdzenia(unittest.TestCase):
    def test_okno_45_dni(self):
        lista = swieta.do_potwierdzenia(None, [], D(2026, 11, 10), 45)
        self.assertEqual([s.data for s in lista][0], D(2026, 11, 11))
        self.assertTrue(all(D(2026, 11, 10) <= s.data <= D(2026, 12, 25) for s in lista))
        self.assertIn(D(2026, 12, 24), [s.data for s in lista])
        self.assertNotIn(D(2026, 12, 26), [s.data for s in lista])    # 46. dzień

    def test_wpis_w_wyjatkach_i_zamkniety_dzien(self):
        lista = swieta.do_potwierdzenia(OTWARTE_PN_SB, [{"data": "2026-12-24", "godziny": [], "opis": "Wigilia"}],
                                        D(2026, 12, 1), 45)
        daty = [s.data for s in lista]
        self.assertNotIn(D(2026, 12, 24), daty)          # wpisane
        self.assertIn(D(2026, 12, 26), daty)             # sobota, zwykle otwarte
        self.assertIn(D(2026, 12, 31), daty)             # Sylwester
        self.assertFalse(any(d.weekday() == 6 for d in daty))   # w niedziele i tak zamknięte
        self.assertFalse(any(s.typ == swieta.HANDLOWA for s in lista))

    def test_komunikat(self):
        s = swieta.Swieto(D(2026, 12, 24), "Wigilia", swieta.USTAWOWE)
        self.assertEqual(swieta.komunikat(s), "POTWIERDŹ: godziny na 24.12 (Wigilia)")

    def test_cli(self):
        wyj, bl = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(wyj), contextlib.redirect_stderr(bl):
            self.assertEqual(swieta.main(["2026", "--json"]), 0)
            self.assertEqual(swieta.main(["--od", "zla-data"]), 2)
        self.assertEqual(len(json.loads(wyj.getvalue())), 24)


class KontroleWBuildzie(unittest.TestCase):
    """dane.kontrole_swiat: tylko branże z godzinami dla klientów, ostrzeżenie klasy A (D12: --produkcja przechodzi)."""

    class Dane:
        def __init__(self, godziny, status_w_hero):
            self.firma = {"godziny": godziny}
            self.preset = {"pokazuj_status_w_hero": status_w_hero}

    def godziny(self, wyjatki):
        return {"tydzien": OTWARTE_PN_SB, "wyjatki": wyjatki}

    def test_ostrzega_przed_wigilia(self):
        r = Raport()
        dane_mod.kontrole_swiat(self.Dane(self.godziny([]), True), r, D(2026, 12, 1))
        teksty = [k.tresc for k in r.komunikaty]
        self.assertIn("POTWIERDŹ: godziny na 24.12 (Wigilia)", teksty)
        self.assertTrue(all(k.pole == "godziny.wyjatki" for k in r.komunikaty))

    def test_produkcja_nie_blokuje(self):
        r = Raport(produkcja=True)
        dane_mod.kontrole_swiat(self.Dane(self.godziny([]), True), r, D(2026, 12, 1))
        self.assertFalse(r.bledy)
        self.assertTrue(r.komunikaty)

    def test_bez_ostrzezenia(self):
        for dane, dzis in [(self.Dane(self.godziny([]), False), D(2026, 12, 1)),     # budowlana/producent
                           (self.Dane(None, True), D(2026, 12, 1)),                  # brak godzin
                           (self.Dane(self.godziny([]), True), D(2026, 9, 1))]:      # daleko do święta
            r = Raport()
            dane_mod.kontrole_swiat(dane, r, dzis)
            self.assertEqual(r.komunikaty, [], dzis)


if __name__ == "__main__":
    unittest.main()
