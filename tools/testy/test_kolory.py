"""Tokeny kolorów z koloru marki (KONTRAKT §7.2): każda para tekst/tło musi przejść kontrast WCAG dla każdego koloru."""
from __future__ import annotations

import unittest

import _wspolne  # noqa: F401  (ścieżka do tools/silnik)

from silnik import kolory

# kolory z logo i szyldów, także „trudne”: żółty, biel, czerń, neon, pastele, średni niebieski, szarości
MARKI = {
    "rdza (Sofastyl)": "#C8471F",
    "żółty (BIMEX)": "#FFD100",
    "jasnożółty": "#FFF3B0",
    "biały": "#FFFFFF",
    "jasnoszary": "#F2F2F2",
    "średni szary": "#6B6B6B",
    "czarny": "#000000",
    "prawie czarny": "#111111",
    "średni niebieski": "#1E6FD9",
    "błękit": "#3B9EDB",
    "granat": "#1B2A4A",
    "zieleń butelkowa": "#1F7A4D",
    "neonowa zieleń": "#39FF14",
    "czerwień": "#E30613",
    "róż": "#FF69B4",
    "turkus pastelowy": "#7FC8C2",
    "fiolet": "#6A1B9A",
    "pomarańcz": "#FF8C00",
}
TLA = ["biale", "cieple", "chlodne", "#FCFCFA", "#EEF2F0"]


def marka(kolor: str, tlo: str = "biale", dodatkowy: str | None = None) -> dict:
    return {"kolor": kolor, "tlo": tlo, "kolor_dodatkowy": dodatkowy}


class KontrastKazdejPary(unittest.TestCase):
    def test_wszystkie_marki_i_tla(self):
        for nazwa, kolor in MARKI.items():
            for tlo in TLA:
                for dodatkowy in (None, "#D12A1E", "#FFE600"):
                    with self.subTest(marka=nazwa, tlo=tlo, dodatkowy=dodatkowy):
                        tok, pary = kolory.tokeny(marka(kolor, tlo, dodatkowy))
                        zle = [f"{a} na {b}: {w:.2f} < {m} ({opis})" for a, b, w, m, opis in pary if w < m]
                        self.assertEqual(zle, [])

    def test_lista_par_jest_pelna(self):
        _, pary = kolory.tokeny(marka("#C8471F"))
        sprawdzane = {(a, b) for a, b, *_ in pary}
        for para in [("--tekst", "--tlo"), ("--tekst-2", "--tlo-2"), ("--marka-tekst", "--tlo"),
                     ("--na-przycisku", "--przycisk"), ("--na-przycisku", "--przycisk-hover"),
                     ("--przycisk-ramka", "--tlo"), ("--na-ciemnym", "--ciemne"), ("--akcent-na-ciemnym", "--ciemne"),
                     ("--focus", "--tlo"), ("--focus-na-ciemnym", "--ciemne"), ("--blad", "--tlo"), ("--ok", "--tlo")]:
            self.assertIn(para, sprawdzane)

    def test_progi(self):
        tok, pary = kolory.tokeny(marka("#1E6FD9"))
        progi = {(a, b): m for a, b, _, m, _ in pary}
        self.assertEqual(progi[("--tekst", "--tlo")], 7.0)
        self.assertEqual(progi[("--tekst-2", "--tlo")], 5.5)
        self.assertEqual(progi[("--marka-tekst", "--tlo")], 4.5)
        self.assertEqual(progi[("--linia-mocna", "--tlo")], 3.0)
        self.assertEqual(progi[("--focus", "--tlo")], 3.0)

    def test_tokeny_sa_hex(self):
        tok, _ = kolory.tokeny(marka("#39FF14", "cieple"))
        for k, v in tok.items():
            self.assertRegex(v, r"^#[0-9A-F]{6}$", k)


class PrzypadkiSzczegolne(unittest.TestCase):
    def test_zolty_nie_jest_kolorem_tekstu(self):
        tok, _ = kolory.tokeny(marka("#FFD100"))
        self.assertEqual(tok["--marka-tekst"], tok["--tekst"])      # żółty tekst na białym byłby nieczytelny
        self.assertEqual(tok["--marka"], "#FFD100")                  # marka zostaje w wypełnieniach
        self.assertEqual(tok["--przycisk"], "#FFD100")               # żółty przycisk z ciemnym napisem
        self.assertEqual(tok["--na-przycisku"], tok["--tekst"])
        self.assertEqual(tok["--przycisk-ramka"], tok["--tekst"])    # obrys 3:1 zamiast żółtego

    def test_bialy_przycisk_ma_ciemne_wypelnienie(self):
        for kolor in ("#FFFFFF", "#F2F2F2"):
            with self.subTest(kolor=kolor):
                tok, _ = kolory.tokeny(marka(kolor))
                self.assertEqual(tok["--przycisk"], tok["--tekst"])
                self.assertEqual(tok["--na-przycisku"], tok["--tlo"])

    def test_czarny_przycisk_po_najechaniu_jasnieje(self):
        tok, _ = kolory.tokeny(marka("#000000"))
        self.assertGreater(kolory.luminancja(tok["--przycisk-hover"]), kolory.luminancja(tok["--przycisk"]))

    def test_zwykly_przycisk_po_najechaniu_ciemnieje(self):
        tok, _ = kolory.tokeny(marka("#1E6FD9"))
        self.assertLess(kolory.luminancja(tok["--przycisk-hover"]), kolory.luminancja(tok["--przycisk"]))
        self.assertEqual(tok["--na-przycisku"], "#FFFFFF")

    def test_marka_tekst_zachowuje_odcien(self):
        for kolor in ("#C8471F", "#1E6FD9", "#1F7A4D", "#E30613"):
            with self.subTest(kolor=kolor):
                tok, _ = kolory.tokeny(marka(kolor))
                h1 = kolory.oklch(kolor)[2]
                h2 = kolory.oklch(tok["--marka-tekst"])[2]
                self.assertLess(min(abs(h1 - h2), 360 - abs(h1 - h2)), 12)

    def test_kolor_dodatkowy_steruje_fokusem(self):
        tok, _ = kolory.tokeny(marka("#FFD100", dodatkowy="#D12A1E"))
        L, C, H = kolory.oklch(tok["--focus"])
        self.assertLess(min(abs(H - kolory.oklch("#D12A1E")[2]), 360 - abs(H - kolory.oklch("#D12A1E")[2])), 12)

    def test_ciemne_tlo_strony_to_blad(self):
        with self.assertRaises(ValueError):
            kolory.tokeny(marka("#C8471F", "#333333"))

    def test_kontrast_wzorcowy(self):
        self.assertAlmostEqual(kolory.kontrast("#000000", "#FFFFFF"), 21.0, places=2)
        self.assertAlmostEqual(kolory.kontrast("#777777", "#FFFFFF"), 4.48, places=2)
        self.assertEqual(kolory.kontrast("#123456", "#123456"), 1.0)

    def test_oklch_w_obie_strony(self):
        for kolor in MARKI.values():
            with self.subTest(kolor=kolor):
                self.assertEqual(kolory.oklch_na_hex(*kolory.oklch(kolor)), kolor.upper())

    def test_css_root(self):
        tok, _ = kolory.tokeny(marka("#C8471F"))
        css = kolory.css_root(tok)
        self.assertTrue(css.startswith(":root{--tlo:#FFFFFF;"))
        self.assertTrue(css.endswith("}"))


if __name__ == "__main__":
    unittest.main()
