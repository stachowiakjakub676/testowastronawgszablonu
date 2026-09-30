"""Silnik szablonów (KONTRAKT §3): składnia, filtry, escapowanie, polska typografia, wykrywanie pozostałości."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _wspolne import BIMEX, DZIS_DATA, KORZEN

from silnik import dane, kontrole, typografia as typo
from silnik.zasoby import INLINE_JS
from silnik.komunikaty import Raport
from silnik.szablony import BladSzablonu, Markup, Silnik

NBSP = "\u00a0"


class Srodowisko:
    """Minimalne środowisko buildu — to, czego filtry potrzebują (url, zasob, abs, obraz, md_plik)."""
    myslnik = "polpauza"
    domena = "https://firma.example"

    def url(self, s):
        return s

    def zasob(self, s):
        return "/" + s.lstrip("/") + "?v=abc123"

    def abs(self, s):
        return s if s.startswith("http") else self.domena + "/" + s.lstrip("/")

    def obraz(self, zid, wariant):
        return f'<picture class="foto foto--{zid}" data-wariant="{wariant}"></picture>'

    def czytaj_md(self, sciezka):
        return "Pierwszy akapit z pliku.\n\n## Nagłówek\n\nDrugi akapit."

    def link_md(self, adres):
        return adres


class Baza(unittest.TestCase):
    def setUp(self):
        self.raport = Raport()
        self.silnik = Silnik(KORZEN / "src", self.raport, Srodowisko())

    def r(self, zrodlo: str, **kontekst) -> str:
        return self.silnik.renderuj_tekst(zrodlo, kontekst, "test.html")


class Skladnia(Baza):
    def test_wartosc_i_sciezki(self):
        self.assertEqual(self.r("{{ a.b.0.c }}", a={"b": [{"c": "x"}]}), "x")

    def test_if_elif_else(self):
        wz = "{% if n > 5 %}duzo{% elif n > 1 %}kilka{% else %}jeden{% endif %}"
        self.assertEqual([self.r(wz, n=n) for n in (9, 3, 1)], ["duzo", "kilka", "jeden"])

    def test_wyrazenia(self):
        self.assertEqual(self.r('{% if "a" in lista and not pusto %}tak{% endif %}', lista=["a"], pusto=[]), "tak")
        self.assertEqual(self.r('{% if x not in lista or (y == null) %}tak{% endif %}', x=1, lista=[1], y=None), "tak")
        self.assertEqual(self.r('{% if 0 %}a{% elif "" %}b{% elif {} %}c{% else %}d{% endif %}'
                                .replace("{}", "pusty"), pusty={}), "d")

    def test_petla_i_zmienne_petli(self):
        wz = "{% for x in l %}{{ petla.indeks }}/{{ petla.dlugosc }}:{{ x }}{% if not petla.ostatni %},{% endif %}{% endfor %}"
        self.assertEqual(self.r(wz, l=["a", "b", "c"]), "1/3:a,2/3:b,3/3:c")

    def test_petla_else_gdy_pusto(self):
        self.assertEqual(self.r("{% for x in l %}{{ x }}{% else %}brak{% endfor %}", l=[]), "brak")
        self.assertEqual(self.r("{% for x in l %}{{ x }}{% else %}brak{% endfor %}"), "brak")   # brak klucza = pusto

    def test_petla_po_slowniku(self):
        self.assertEqual(self.r("{% for p in d %}{{ p.klucz }}={{ p.wartosc }};{% endfor %}", d={"a": 1, "b": 2}), "a=1;b=2;")

    def test_set(self):
        self.assertEqual(self.r('{% set x = "abc" | wersaliki_pierwsza %}{{ x }}'), "Abc")

    def test_literal_z_zamknieciem_w_srodku(self):
        self.assertEqual(self.r('{{ "a}}b" }}{{ "c%}d" }}'), "a}}bc%}d")

    def test_komentarz_znika(self):
        self.assertEqual(self.r("a{# komentarz z {{ x }} #}b"), "ab")

    def test_wiersz_z_samym_znacznikiem_znika(self):
        wynik = self.r("<ul>\n  {% for x in l %}\n  <li>{{ x }}</li>\n  {% endfor %}\n</ul>\n", l=[1, 2])
        self.assertEqual(wynik, "<ul>\n  <li>1</li>\n  <li>2</li>\n</ul>\n")

    def test_include_ze_zmiennymi(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "czesci").mkdir()
            (Path(tmp) / "czesci" / "x.html").write_text("[{{ a }}|{{ b }}]", encoding="utf-8")
            s = Silnik(Path(tmp), self.raport, Srodowisko())
            self.assertEqual(s.renderuj_tekst('{% include "czesci/x.html" a="1" b=n %}', {"n": 2}), "[1|2]")

    def test_include_ukrywa_przy_niespelnionym_wymaga(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "czesci").mkdir()
            (Path(tmp) / "czesci" / "x.html").write_text("{# wymaga: dane.lista #}\nwidać", encoding="utf-8")
            s = Silnik(Path(tmp), self.raport, Srodowisko())
            self.assertEqual(s.renderuj_tekst('{% include "czesci/x.html" %}', {"dane": {"lista": []}}), "")
            self.assertTrue(any("brak danych: dane.lista" in k.tresc for k in self.raport.lista("UKRYTO")))
            self.assertEqual(s.renderuj_tekst('{% include "czesci/x.html" %}', {"dane": {"lista": [1]}}), "widać")

    def test_naglowek_strony(self):
        from silnik.szablony import parsuj
        sz = parsuj('{# strona: sciezka="/kontakt" nav="Kontakt" tytul="Kontakt i dojazd" #}\n<p></p>', "strony/k.html")
        self.assertEqual(sz.strona["sciezka"], "/kontakt")
        self.assertEqual(sz.strona["tytul"], "Kontakt i dojazd")


class BledySkladni(Baza):
    def zly(self, zrodlo: str, fragment: str, linia: int | None = None, **kontekst):
        with self.assertRaises(BladSzablonu) as cm:
            self.r(zrodlo, **kontekst)
        self.assertIn(fragment, str(cm.exception))
        if linia is not None:
            self.assertEqual(cm.exception.linia, linia)

    def test_niezamkniete_znaczniki_z_numerem_wiersza(self):
        self.zly("a\nb {{ x", "„{{” bez zamknięcia „}}”", 2)
        self.zly("a\n\n{% if x", "„{%” bez zamknięcia „%}”", 3)
        self.zly("{# komentarz", "„{#” bez zamknięcia „#}”", 1)

    def test_nieznany_filtr(self):
        self.zly("{{ x | nie_ma_takiego }}", "nieznany filtr „nie_ma_takiego”", x=1)

    def test_nieznany_znacznik_i_brak_zamkniecia_bloku(self):
        for zrodlo in ("{% petla x %}", "{% if x %}bez końca", "{% endif %}", "{% for x %}{% endfor %}"):
            with self.subTest(zrodlo=zrodlo), self.assertRaises(BladSzablonu):
                self.r(zrodlo, x=1)

    def test_niezrozumiale_wyrazenie(self):
        self.zly("{{ x + 1 }}", "nie rozumiem wyrażenia", x=1)

    def test_lista_w_wartosci(self):
        self.zly("{{ l }}", "nie można wypisać listy", l=[1])

    def test_blad_filtra_ma_miejsce(self):
        self.zly('{{ n | liczba_mnoga:"jedna,dwie" }}', "filtr „liczba_mnoga”", n=2)


class Escapowanie(Baza):
    def test_html_z_danych_jest_escapowany(self):
        self.assertEqual(self.r("{{ x }}", x='<script>alert("x")</script>'),
                         "&lt;script&gt;alert(„x”)&lt;/script&gt;")

    def test_atrybut_nie_ucieka(self):
        # para cudzysłowów staje się „…”, pojedynczy — encją; w obu razach atrybut się nie kończy
        for x in ('" onmouseover="zle', '" onmouseover=zle', "' onmouseover='zle"):
            with self.subTest(x=x):
                wynik = self.r('<a title="{{ x }}">', x=x)
                self.assertEqual(wynik.count('"'), 2, wynik)
                self.assertNotIn("'", wynik)

    def test_surowe_i_markup(self):
        self.assertEqual(self.r("{{ x | surowe }}", x="<b>tak</b>"), "<b>tak</b>")
        self.assertEqual(self.r("{{ x }}", x=Markup("<b>tak</b>")), "<b>tak</b>")

    def test_json_bezpieczny_w_script(self):
        wynik = self.r("{{ x | json }}", x={"a": "</script><!--"})
        self.assertNotIn("<", wynik)
        self.assertIn("\\u003c/script>", wynik)

    def test_md_escapuje_html_i_odrzuca_niebezpieczne_linki(self):
        wynik = self.r("{{ t | md }}", t="<img src=x onerror=alert(1)> [a](javascript:alert(1)) [b](//zly.example) "
                                         "[c](https://ok.example) [d](/kontakt) [e](mailto:a@b.pl)")
        self.assertNotIn("<img", wynik)
        self.assertIn("&lt;img", wynik)
        self.assertNotIn("javascript:", wynik.replace("&", ""))
        self.assertNotIn('href="//zly.example"', wynik)
        for href in ("https://ok.example", "/kontakt", "mailto:a@b.pl"):
            self.assertIn(f'href="{href}"', wynik)


class Filtry(Baza):
    def test_tel(self):
        self.assertEqual(self.r("{{ t | tel }}", t="+48672683408"), f"+48{NBSP}67{NBSP}268{NBSP}34{NBSP}08")
        self.assertEqual(self.r('{{ t | tel:"krajowy" }}', t="+48500000001"), f"500{NBSP}000{NBSP}001")
        self.assertEqual(self.r("{{ t | tel_href }}", t="+48 500 000 001"), "tel:+48500000001")

    def test_cena(self):
        przypadki = [(1250, f"1{NBSP}250{NBSP}zł"), (12.5, f"12,50{NBSP}zł"), (0, f"0{NBSP}zł"),
                     ({"od": 32, "do": 46}, f"32–46{NBSP}zł"), ({"od": 300}, f"od{NBSP}300{NBSP}zł"),
                     ({"do": 50}, f"do{NBSP}50{NBSP}zł"), (4.5, f"4,50{NBSP}zł")]
        for v, oczekiwane in przypadki:
            with self.subTest(v=v):
                self.assertEqual(self.r("{{ c | cena }}", c=v), oczekiwane)

    def test_daty(self):
        self.assertEqual(self.r("{{ d | data }}", d="2026-09-29"), f"29{NBSP}września 2026")
        self.assertEqual(self.r("{{ d | data_krotka }}", d="2026-09-05"), "05.09.2026")
        self.assertEqual(self.r("{{ d | data_iso }}", d="2026-09-05"), "2026-09-05")

    def test_liczba(self):
        self.assertEqual(self.r("{{ n | liczba }}", n=1250), f"1{NBSP}250")
        self.assertEqual(self.r("{{ n | liczba }}", n=4.8), "4,8")
        self.assertEqual(self.r("{{ n }}", n=4.8), "4,8")          # float w {{ }} bez „4,80”

    def test_liczba_mnoga(self):
        f = "realizacja,realizacje,realizacji"
        for n, forma in ((1, "realizacja"), (2, "realizacje"), (5, "realizacji"), (12, "realizacji"), (22, "realizacje"),
                         (0, "realizacji"), (104, "realizacje"), (112, "realizacji")):
            with self.subTest(n=n):
                self.assertEqual(self.r('{{ n | liczba_mnoga:"' + f + '" }}', n=n), forma)

    def test_pomocnicze(self):
        self.assertEqual(self.r("{{ t | slug }}", t="Żółta Łódź – 2026!"), "zolta-lodz-2026")
        self.assertEqual(self.r("{{ l | dlugosc }}", l=[1, 2, 3]), "3")
        self.assertEqual(self.r('{% for x in l | pierwsze:2 %}{{ x }}{% endfor %}', l=[1, 2, 3]), "12")
        self.assertEqual(self.r('{% for x in l | reszta:2 %}{{ x }}{% endfor %}', l=[1, 2, 3]), "3")
        self.assertEqual(self.r('{{ l | polacz:", " }}', l=["a", "b"]), "a, b")
        self.assertEqual(self.r('{{ x | domyslnie:"brak" }}'), "brak")
        self.assertEqual(self.r('{{ x | domyslnie:y }}', y="z ścieżki"), f"z{NBSP}ścieżki")

    def test_zasob_obraz_abs(self):
        self.assertEqual(self.r('{{ "assets/css/strona.css" | zasob }}'), "/assets/css/strona.css?v=abc123")
        self.assertIn('class="foto foto--sala"', self.r('{{ "sala" | obraz:"hero" }}'))
        self.assertEqual(self.r('{{ "/kontakt" | abs }}'), "https://firma.example/kontakt")

    def test_mailto(self):
        self.assertEqual(self.r("{{ e | mailto }}", e=" biuro@firma.example "), "mailto:biuro@firma.example")

    def test_md_poziomy_naglowkow(self):
        t = "## Duży\n\n### Mniejszy\n\n- a\n- b\n\n1. jeden\n2. dwa\n\n**mocno** i *lekko*"
        wynik = self.r('{{ t | md:3 }}', t=t)
        self.assertIn("<h3>Duży</h3>", wynik)
        self.assertIn("<h4>Mniejszy</h4>", wynik)
        self.assertIn("<ul><li>a</li><li>b</li></ul>", wynik)
        self.assertIn("<ol><li>jeden</li><li>dwa</li></ol>", wynik)
        self.assertIn("<strong>mocno</strong>", wynik)
        self.assertIn("<em>lekko</em>", wynik)

    def test_md_plik_poczatek(self):
        self.assertEqual(self.r('{{ "tresc/x.md" | md_plik_poczatek }}'), f"<p>Pierwszy akapit z{NBSP}pliku.</p>")


class Typografia(Baza):
    def test_twarde_spacje(self):
        wynik = self.r("{{ t }}", t="Dom z ogrodem i garażem, ul. Testowa 1, nr 5, ok. 30 min w 2019 r.")
        for fragment in (f"z{NBSP}ogrodem", f"i{NBSP}garażem", f"ul.{NBSP}Testowa", f"nr{NBSP}5", f"ok.{NBSP}30",
                         f"30{NBSP}min", f"w{NBSP}2019", f"2019{NBSP}r."):
            self.assertIn(fragment, wynik)

    def test_liczby_jednostki_grupy(self):
        wynik = self.r("{{ t }}", t="Hala 1 200 m², 5 km dalej, 1 250 zł, 12 kg")
        for fragment in (f"1{NBSP}200{NBSP}m²", f"5{NBSP}km", f"1{NBSP}250{NBSP}zł", f"12{NBSP}kg"):
            self.assertIn(fragment, wynik)

    def test_zakresy_i_myslniki(self):
        self.assertEqual(typo.typografia("7:00 - 15:00"), "7:00–15:00")
        self.assertEqual(typo.typografia("32-46 zł"), f"32–46{NBSP}zł")
        self.assertEqual(typo.typografia("2019-2020"), "2019–2020")
        self.assertEqual(typo.typografia("Dom - ogród"), f"Dom{NBSP}– ogród")
        self.assertEqual(typo.typografia("Dom - ogród", "pauza"), f"Dom{NBSP}— ogród")
        self.assertEqual(typo.typografia('Firma "Test"'), "Firma „Test”")

    def test_slowa_z_dywizem_bez_zmian(self):
        # „pieszo-rowerowe”, „Nowe Miasto-Wilda” — dywiz w słowie nie jest myślnikiem ani zakresem
        self.assertEqual(typo.typografia("ścieżki pieszo-rowerowe"), "ścieżki pieszo-rowerowe")
        self.assertEqual(typo.typografia("kod 64-610"), "kod 64-610")

    def test_adres_bez_typografii_nawet_bez_filtra_url(self):
        for adres in ("https://firma.example/realizacje-2019-2020?a=1-2&w=z", "mailto:a@b.pl", "tel:+48500000001",
                      "https://firma.example/w/z/a"):
            with self.subTest(adres=adres):
                wynik = self.r("{{ a }}", a=adres)
                self.assertNotIn(NBSP, wynik)
                self.assertNotIn("–", wynik)

    def test_filtr_url_bez_typografii(self):
        wynik = self.r('<a href="{{ a | url }}">', a="https://mapy.example/dir/?api=1&destination=52.1,16.9 - w z")
        self.assertNotIn(NBSP, wynik)
        self.assertNotIn("–", wynik)
        self.assertIn("&amp;destination", wynik)

    def test_link_w_md_bez_typografii_w_adresie(self):
        wynik = self.r("{{ t | md }}", t="Zobacz [realizacje z lat 2019-2020](https://firma.example/r-2019-2020) i w z")
        self.assertIn('href="https://firma.example/r-2019-2020"', wynik)
        self.assertIn("2019–2020</a>", wynik)          # w tekście linku półpauza jest poprawna

    def test_typografia_nie_psuje_encji(self):
        self.assertEqual(self.r("{{ t }}", t="Kot & pies <b>"), "Kot &amp; pies &lt;b&gt;")


class PusteWartosci(Baza):
    def test_brak_wartosci_to_ostrzezenie(self):
        self.assertEqual(self.r("[{{ literowka }}]"), "[]")
        self.assertTrue(any("pusta wartość w {{ literowka }}" in k.tresc for k in self.raport.komunikaty))

    def test_domyslnie_wycisza(self):
        self.r('{{ x | domyslnie:"" }}')
        self.assertEqual(self.raport.komunikaty, [])

    def test_produkcja_zamienia_na_blad(self):
        raport = Raport(produkcja=True)
        Silnik(KORZEN / "src", raport, Srodowisko()).renderuj_tekst("{{ nie_ma }}", {}, "t.html")
        self.assertTrue(raport.bledy)


class Pozostalosci(unittest.TestCase):
    """Trzy warstwy: tokenizer (niezamknięte znaczniki — BledySkladni), dane (dane.kontrole) i wynik (kontrole.sprawdz)."""

    def test_pozostalosci_w_danych(self):
        raport = Raport()
        d = dane.wczytaj(BIMEX, KORZEN, raport)
        d.tresc["hero"]["lead"] = "Tekst z {{ zmienna }} w środku."
        d.tresc["oferta"]["pozycje"][0]["opis"] = "TODO: dopisać opis"
        d.firma["zrodla"]["firma.opis"] = "notatka TODO — pola notatek nie trafiają na stronę"
        dane.kontrole(d, raport, False, DZIS_DATA)
        bledy = {(k.pole, k.tresc.split("”")[0]) for k in raport.bledy}
        self.assertIn(("hero.lead", "w tekście jest „{{"), bledy)
        self.assertIn(("oferta.pozycje[0].opis", "w tekście jest „TODO"), bledy)
        self.assertFalse(any((k.pole or "").startswith("zrodla") for k in raport.bledy))

    def _strona(self, tresc: str, glowa: str = "") -> Raport:
        with tempfile.TemporaryDirectory() as tmp:
            html = ('<!doctype html><html lang="pl"><head><title>T</title>'
                    '<meta property="og:image" content="https://firma.example/og.jpg">' + glowa +
                    f'</head><body><h1>Test</h1>{tresc}</body></html>')
            (Path(tmp) / "index.html").write_text(html, encoding="utf-8")
            raport = Raport()
            kontrole.sprawdz(Path(tmp), raport, "https://firma.example", INLINE_JS)
            return raport

    def test_czysta_strona_bez_bledow(self):
        self.assertEqual([k.tresc for k in self._strona("<p>Treść</p>").bledy], [])
        self.assertEqual([k.tresc for k in self._strona("", f"<script>{INLINE_JS}</script>").bledy], [])

    def test_pozostalosci_w_wyniku(self):
        for znacznik in ("{{ x }}", "{% if %}", "{# k #}", "[UZUPEŁNIJ]", "TODO", "Lorem ipsum", "XXX"):
            with self.subTest(znacznik=znacznik):
                bledy = [k.tresc for k in self._strona(f"<p>{znacznik}</p>").bledy]
                self.assertTrue(any("pozostałość szablonu" in b for b in bledy), bledy)

    def test_twarda_spacja_i_polpauza_w_adresie(self):
        for adres in ("/kontakt&nbsp;x", "/realizacje-2019–2020", "https://firma.example/„a”"):
            with self.subTest(adres=adres):
                bledy = [k.tresc for k in self._strona(f'<p><a href="{adres}">link</a></p>').bledy]
                self.assertTrue(any("typografia zepsuła link" in b for b in bledy), bledy)

    def test_inne_kontrole_wyniku(self):
        przypadki = {
            '<h1>Drugi</h1>': "nagłówków h1",
            '<h3>Za głęboko</h3>': "przeskok poziomu nagłówka",
            '<img src="/a.jpg">': "<img> bez atrybutów",
            '<p id="a"></p><p id="a"></p>': "powtórzone id",
            '<p style="color:red">x</p>': "atrybut style",
            '<script>alert(1)</script>': "skrypt wbudowany",
            '<a href="tel:500 000 001">x</a>': "E.164",
            '<img src="https://obcy.example/a.jpg" alt="a" width="1" height="1">': "obcej domeny",
            '<a href="/nie-ma">x</a>': "nieistniejącej strony",
            '<a href="#nie-ma">x</a>': "kotwica #nie-ma",
            '<a href="/"></a>': "bez nazwy",
        }
        for html, fragment in przypadki.items():
            with self.subTest(html=html):
                bledy = [k.tresc for k in self._strona(html).bledy]
                self.assertTrue(any(fragment in b for b in bledy), bledy)

    def test_json_ld_z_komentarzem(self):
        bledy = [k.tresc for k in self._strona("", '<script type="application/ld+json">{"a":"<!--"}</script>').bledy]
        self.assertTrue(any("JSON-LD zawiera" in b for b in bledy), bledy)


if __name__ == "__main__":
    unittest.main()
