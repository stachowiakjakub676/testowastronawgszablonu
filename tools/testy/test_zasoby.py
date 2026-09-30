"""Przycinanie CSS sekcji (tools/silnik/zasoby.py): reguły bloków, których strona nie ma, znikają; reszta zostaje."""
from __future__ import annotations

import unittest

import _wspolne  # noqa: F401  (ścieżka do tools/)
from silnik import zasoby


class PrzycinanieCss(unittest.TestCase):
    CSS = """.cennik { color: red; }
.cennik__poz, .oferta__poz { margin: 0; }
.oferta__poz:not(.cennik--x) { padding: 0; }
.mapa:has(.nieznany__el) { padding: 0; }
@media (min-width: 60em) { .cennik__grupa { gap: 1rem; } .oferta { gap: 2rem; } }
@media print { .cennik { display: none; } }
@keyframes wjazd { from { opacity: 0; } }
/* slop-ok: V-GRADIENT powód */
.is-open { display: block; }
.oferta a[href$=".pdf"] { font-weight: 700; }
"""

    def test_przycina_nieuzyte_bloki(self):
        wynik = zasoby.przytnij_css(self.CSS, {"oferta", "mapa", "is-open"})
        self.assertNotIn(".cennik {", wynik)
        self.assertIn(".cennik__poz, .oferta__poz", wynik)          # jeden żywy selektor ratuje regułę
        self.assertIn(".oferta__poz:not(.cennik--x)", wynik)        # klasa w :not() nie przesądza
        self.assertIn(".mapa:has(.nieznany__el)", wynik)            # ani w :has()
        self.assertIn(".oferta { gap: 2rem; }", wynik)
        self.assertNotIn("cennik__grupa", wynik)
        self.assertNotIn("@media print", wynik)                     # pusta @media znika
        self.assertIn("@keyframes wjazd", wynik)
        self.assertIn("slop-ok", wynik)
        self.assertIn(".is-open", wynik)
        self.assertIn('a[href$=".pdf"]', wynik)                   # „.pdf” w atrybucie to nie klasa

    def test_bloki_z_html_i_js(self):
        bloki = zasoby.uzyte_bloki(['<div class="oferta__poz oferta__poz--duza">'], ["el.className = 'mapa__ramka'"])
        self.assertTrue({"oferta", "mapa"} <= bloki)
        self.assertNotIn("cennik", bloki)

    def test_komentarze_bez_zwolnien_znikaja(self):
        wynik = zasoby.bez_komentarzy("/* opis */\n.a { b: c; } /* slop-ok: X powód */\n")
        self.assertNotIn("opis", wynik)
        self.assertIn("slop-ok: X powód", wynik)


if __name__ == "__main__":
    unittest.main()
