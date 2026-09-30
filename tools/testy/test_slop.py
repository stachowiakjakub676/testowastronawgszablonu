"""Testy tools/lint_slop.py: reguły treści i wyglądu, dane klienta, zwolnienia (data/slop-ok.json), kody wyjścia.

Uruchom:  python3 -m unittest discover -s tools/testy -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

NARZEDZIA = Path(__file__).resolve().parent.parent
KORZEN = NARZEDZIA.parent
sys.path.insert(0, str(NARZEDZIA))

import lint_slop  # noqa: E402

NBSP = " "

STRONA_SLOP = """<!doctype html><html lang="pl"><head><title>Kompleksowe Rozwiązania Dla Twojego Biznesu</title>
<style>
.hero{background:linear-gradient(135deg,#6366f1,#8b5cf6)}
.t{background:linear-gradient(90deg,#6366f1,#ec4899);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.a{border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.1)}.b{border-radius:20px;box-shadow:0 4px 6px rgba(0,0,0,.1)}
.c{border-radius:1rem;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.btn{border-radius:999px}
.k1{text-transform:uppercase;letter-spacing:.2em}.k2{text-transform:uppercase;letter-spacing:.1em}
.k3{text-transform:uppercase;letter-spacing:2px}.k4{text-transform:uppercase;letter-spacing:.3em}
.pasek{border-left:4px solid #e11d48}
a:focus-visible{outline:2px solid}
</style></head><body>
<main>
<section id="s1"><h1>Przenieś Swój Biznes Na Wyższy Poziom</h1>
<p>W dzisiejszych czasach każda firma potrzebuje wsparcia. Jesteśmy zespołem z pasją i wieloletnim doświadczeniem.</p>
<a class="btn" href="/o">Dowiedz się więcej</a></section>
<section id="s2"><h2>Dlaczego my?</h2>
<div class="cechy">
 <div class="cecha"><svg></svg><h3>Jakość</h3><p>Opis cechy numer jeden.</p></div>
 <div class="cecha"><svg></svg><h3>Terminowość</h3><p>Opis cechy numer dwa.</p></div>
 <div class="cecha"><svg></svg><h3>Cena</h3><p>Opis cechy numer trzy.</p></div>
</div>
<p>To nie tylko usługa, to styl życia. 🚀 Seamless obsługa.</p>
<div><span>01</span><span>02</span><span>03</span></div>
<div><b data-countup="500">500+</b> zadowolonych klientów <b>15+</b> lat <b>98%</b> poleceń</div>
<img src="https://images.unsplash.com/photo-1" alt="zespół" width="10" height="10">
</section></main></body></html>"""

STRONA_CZYSTA = f"""<!doctype html><html lang="pl"><head><title>Roboty drogowe Rogoźno – BIMEX</title>
<link rel="stylesheet" href="/assets/css/strona.css?v=1"></head><body>
<header class="site-header"><nav><ul><li><a href="/">Start</a></li></ul></nav></header>
<main>
<section id="hero"><h1>Roboty drogowe i{NBSP}beton towarowy w{NBSP}Rogoźnie</h1>
<p>Rodzinna firma z{NBSP}Rogoźna, działamy od 1993 roku. Budujemy i{NBSP}remontujemy drogi, a{NBSP}w{NBSP}wytwórni przy
ul.{NBSP}Fabrycznej produkujemy beton i{NBSP}prefabrykaty.</p>
<a class="btn btn--primary" href="tel:+48672683408">Zadzwoń: 67 268 34 08</a></section>
<section id="proces"><h2>Jak zamówić beton</h2>
<ol><li><span>01</span> Zadzwoń</li><li><span>02</span> Podaj adres</li><li><span>03</span> Ustal termin</li></ol>
<p>Pianka wysokiej jakości T35, stelaż z{NBSP}drewna bukowego.</p>
<p>Każdy mebel w{NBSP}sercu każdego salonu wygląda inaczej.</p>
</section></main>
<footer class="site-footer"><p>Rodzinna firma z{NBSP}Rogoźna, działamy od 1993 roku.</p></footer>
</body></html>"""

CSS_CZYSTY = """/* 01-baza.css */
:root { --tlo: #FFFFFF; --tekst: #1A1A1A; --marka: #FFD100; }
body { background: var(--tlo); color: var(--tekst); font-family: "Barlow", Arial, sans-serif; }
@font-face { font-family: "Barlow"; src: url(x.woff2); }
a:focus-visible { outline: 2px solid var(--tekst); }
.site-header { backdrop-filter: blur(6px); }
.btn { border-radius: 2px; }
.hero__foto::after { background: linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,.5)); }
"""


def uruchom_na(pliki: dict, *arg, produkcja=False):
    """Zapisuje pliki do katalogu tymczasowego i uruchamia linter; zwraca (wynik, katalog)."""
    kat = Path(tempfile.mkdtemp(prefix="slop-"))
    for nazwa, tresc in pliki.items():
        p = kat / nazwa
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(tresc if isinstance(tresc, str) else json.dumps(tresc, ensure_ascii=False, indent=1), encoding="utf-8")
    sciezki = [str(kat / a) for a in arg] if arg else [str(kat)]
    return lint_slop.uruchom(sciezki, produkcja), kat


def ids(wynik, poziom=None):
    return {w.id for w in wynik["wyniki"] if poziom is None or w.poziom == poziom}


class RegulyStrony(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slop, cls.k1 = uruchom_na({"index.html": STRONA_SLOP})
        cls.czysta, cls.k2 = uruchom_na({"dist/index.html": STRONA_CZYSTA, "dist/assets/css/strona.css": CSS_CZYSTY})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.k1)
        shutil.rmtree(cls.k2)

    def test_slop_odpala_wiele_regul(self):
        oczekiwane = {"PL-OPENER", "PL-FRAZES", "PL-ANTYTEZA", "PL-DLACZEGO-MY", "PL-HYPE", "PL-TITLE-CASE", "PL-CTA-OGOLNE",
                      "PL-LICZNIK", "EN-BUZZ", "V-EMOJI", "TRESC-STOCK", "V-GRAD-FIOLET", "V-TEKST-GRADIENT",
                      "V-KARTY-ZAOKR-CIEN", "V-PIGULKA", "V-WERSALIKI", "V-NUMERY-01", "V-TRZY-KARTY", "V-LICZNIK-ANIM",
                      "V-PASEK-STATYSTYK", "V-PASEK-BOCZNY"}
        self.assertEqual(oczekiwane - ids(self.slop), set())
        self.assertEqual(self.slop["kod"], 2)

    def test_poziomy(self):
        p0 = ids(self.slop, "P0")
        self.assertTrue({"PL-FRAZES", "PL-OPENER", "PL-ANTYTEZA", "V-EMOJI", "TRESC-STOCK", "V-GRAD-FIOLET"} <= p0)
        self.assertIn("V-WERSALIKI", ids(self.slop, "P1"))

    def test_czysta_strona_bez_p0_p1(self):
        zle = [(w.id, w.komunikat) for w in self.czysta["wyniki"] if w.poziom in ("P0", "P1")]
        self.assertEqual(zle, [])
        self.assertEqual(self.czysta["kod"], 0)

    def test_twarde_spacje_to_nie_sierotki(self):
        self.assertNotIn("PL-SIEROTKI", ids(self.czysta))
        wynik, kat = uruchom_na({"a.html": "<html><body><main><p>Budujemy drogi w Rogoźnie i okolicy od lat.</p></main></body></html>"})
        shutil.rmtree(kat)
        self.assertIn("PL-SIEROTKI", ids(wynik))

    def test_numery_w_ol_i_serce_bez_miasta(self):
        self.assertNotIn("V-NUMERY-01", ids(self.czysta))
        self.assertNotIn("PL-HYPE", ids(self.czysta))
        wynik, kat = uruchom_na({"a.html": "<p>Restauracja w sercu Poznania, 40 miejsc.</p>"})
        shutil.rmtree(kat)
        self.assertIn("PL-HYPE", ids(wynik))

    def test_konkret_obniza_poziom(self):
        wysokiej = [w for w in self.czysta["wyniki"] if w.id == "PL-FRAZES-LEKKIE"]
        self.assertTrue(wysokiej and all(w.poziom == "P2" for w in wysokiej))
        wynik, kat = uruchom_na({"a.html": "<p>Oferujemy profesjonalną obsługę i konkurencyjne ceny.</p>"})
        shutil.rmtree(kat)
        self.assertIn("PL-FRAZES-LEKKIE", ids(wynik, "P1"))

    def test_tytul_bez_marki_i_nazwy_stale(self):
        self.assertNotIn("PL-TITLE-CASE", ids(self.czysta))
        self.assertFalse(lint_slop.czy_title_case("Przekazanie danych poza Europejski Obszar Gospodarczy", set()))
        self.assertTrue(lint_slop.czy_title_case("Skontaktuj Się Z Nami Dzisiaj", set()))

    def test_nazwy_osob_i_punktow_to_nie_title_case(self):
        tresc = {"zespol": {"osoby": [{"imie": "lek. Jan Próbny"}]},
                 "gdzie_kupic": {"punkty": [{"nazwa": "Sklep Meblowy Próba", "miasto": "Poznań"}]}}
        nazwy = lint_slop.nazwy_z_tresci(tresc)
        self.assertFalse(lint_slop.czy_title_case("lek. Jan Próbny", nazwy))
        self.assertFalse(lint_slop.czy_title_case("Sklep Meblowy Próba", nazwy))
        self.assertTrue(lint_slop.czy_title_case("Skontaktuj Się Z Nami Dzisiaj", nazwy))

    def test_powtorka_w_dwoch_sekcjach(self):
        zdanie = "Beton dowozimy własnymi betonomieszarkami na budowy w całym powiecie obornickim."
        html = f"<main><section id='a'><p>{zdanie}</p></section><section id='b'><p>{zdanie}</p></section></main>" \
               f"<footer><p>{zdanie}</p></footer>"
        wynik, kat = uruchom_na({"a.html": html})
        shutil.rmtree(kat)
        powt = [w for w in wynik["wyniki"] if w.id == "TRESC-POWTORKA"]
        self.assertEqual(len(powt), 1)
        # stopka może powtarzać informację (CLAUDE.md §2: „plus stopka”)
        wynik, kat = uruchom_na({"a.html": f"<main><section id='a'><p>{zdanie}</p></section></main><footer><p>{zdanie}</p></footer>"})
        shutil.rmtree(kat)
        self.assertNotIn("TRESC-POWTORKA", ids(wynik))

    def test_myslniki(self):
        zdania = " ".join(f"Zdanie numer {i} ma kilka słów – i jeszcze kilka po myślniku." for i in range(40))
        wynik, kat = uruchom_na({"a.html": f"<main><p>{zdania}</p></main>"})
        shutil.rmtree(kat)
        self.assertIn("PL-MYSLNIK-GESTOSC", ids(wynik, "P1"))
        wynik, kat = uruchom_na({"a.html": "<p>Czynne pn.–pt. 7:00–15:00, sob. 8:00–12:00 — tylko wytwórnia – bez biura.</p>"})
        shutil.rmtree(kat)
        self.assertIn("PL-MYSLNIK-MIX", ids(wynik))
        self.assertNotIn("PL-ZAKRES-SPACJE", ids(wynik))

    def test_emoji_dozwolone_znaki(self):
        wynik, kat = uruchom_na({"a.html": "<p>Ocena ★ 4,8 (Google) ✓ zweryfikowane</p>"})
        shutil.rmtree(kat)
        self.assertNotIn("V-EMOJI", ids(wynik))

    def test_stock_w_nazwie_pliku_i_alt(self):
        wynik, kat = uruchom_na({"a.html": '<img src="/img/shutterstock_123.jpg" alt="x" width="1" height="1">'
                                           '<img src="/img/a.jpg" alt="Obraz wygenerowany przez AI" width="1" height="1">'})
        shutil.rmtree(kat)
        self.assertEqual(len([w for w in wynik["wyniki"] if w.id == "TRESC-STOCK"]), 2)


class Dane(unittest.TestCase):
    def firma(self, **zm):
        f = {"przyklad": False, "firma": {"nazwa": "Testowo", "nazwa_prawna": "Testowo Jan Testowy"},
             "kontakt": {"adres": {"ulica": "ul. Polna 1", "miasto": "Rogoźno"}},
             "marka": {"kolor": "#2A6F97", "font_naglowki": "literata", "font_tekst": "public-sans"},
             "zrodla": {"x": "kompleksowe usługi z pasją — notatka, nie trafia na stronę"}}
        f.update(zm)
        return f

    def test_pole_danych_i_notatki(self):
        tresc = {"hero": {"naglowek": "Serwis rowerów", "lead": "Oferujemy kompleksowe usługi i indywidualne podejście."}}
        wynik, kat = uruchom_na({"data/firma.json": self.firma(), "data/tresc.json": tresc}, "data")
        shutil.rmtree(kat)
        fr = [w for w in wynik["wyniki"] if w.id == "PL-FRAZES"]
        self.assertEqual(len(fr), 1)
        self.assertEqual(fr[0].pole, "hero.lead")
        self.assertTrue(fr[0].plik.endswith("tresc.json"))

    def test_pole_przy_wyniku_ze_strony(self):
        tresc = {"hero": {"lead": "Oferujemy kompleksowe usługi i indywidualne podejście."}}
        html = "<main><p>Oferujemy kompleksowe usługi i indywidualne podejście.</p></main>"
        wynik, kat = uruchom_na({"data/firma.json": self.firma(), "data/tresc.json": tresc, "dist/index.html": html},
                                "dist", "data")
        shutil.rmtree(kat)
        fr = [w for w in wynik["wyniki"] if w.id == "PL-FRAZES"]
        self.assertEqual(len(fr), 1)
        self.assertTrue(fr[0].plik.endswith("index.html"))
        self.assertIn("hero.lead", fr[0].pole)

    def test_tekst_niewidoczny_na_stronie_to_p2(self):
        tresc = {"faq": {"wstep": "Oferujemy kompleksowe usługi."}}
        wynik, kat = uruchom_na({"data/firma.json": self.firma(), "data/tresc.json": tresc,
                                 "dist/index.html": "<p>Budujemy drogi od 1993 r.</p>"}, "dist", "data")
        shutil.rmtree(kat)
        self.assertEqual({w.poziom for w in wynik["wyniki"] if w.id == "PL-FRAZES"}, {"P2"})

    def test_markdown(self):
        md = "---\ntytul: x\n---\n# Nasze Wartości I Misja Firmy\n\nW dzisiejszych czasach robimy drogi.\n"
        wynik, kat = uruchom_na({"data/firma.json": self.firma(), "data/tresc/o-firmie.md": md}, "data")
        shutil.rmtree(kat)
        self.assertIn("PL-OPENER", ids(wynik))
        self.assertIn("PL-TITLE-CASE", ids(wynik))

    def test_marka_domyslna(self):
        f = self.firma(marka={"kolor": None, "font_naglowki": "archivo", "font_tekst": "public-sans"})
        wynik, kat = uruchom_na({"data/firma.json": f}, "data")
        shutil.rmtree(kat)
        self.assertIn("MARKA-DOMYSLNA", ids(wynik, "P0"))
        bimex = json.loads((KORZEN / "przyklady/bimex/data/firma.json").read_text(encoding="utf-8"))["marka"]
        wynik, kat = uruchom_na({"data/firma.json": self.firma(marka=bimex)}, "data")
        shutil.rmtree(kat)
        self.assertIn("MARKA-DOMYSLNA", ids(wynik, "P0"))
        wynik, kat = uruchom_na({"data/firma.json": self.firma(przyklad=True, marka={"kolor": None})}, "data")
        shutil.rmtree(kat)
        self.assertNotIn("MARKA-DOMYSLNA", ids(wynik))
        wynik, kat = uruchom_na({"data/firma.json": self.firma()}, "data")
        shutil.rmtree(kat)
        self.assertNotIn("MARKA-DOMYSLNA", ids(wynik))


class Zwolnienia(unittest.TestCase):
    HTML = "<main><section id='a'><h2>Zaufali nam</h2><p>Robimy drogi od 1993 r.</p></section></main>"

    def test_zwolnienie_p1_i_kody(self):
        wynik, kat = uruchom_na({"dist/index.html": self.HTML, "data/firma.json": {"przyklad": True}}, "dist", "data")
        shutil.rmtree(kat)
        self.assertIn("PL-SEKCJA", ids(wynik, "P1"))
        self.assertEqual(wynik["kod"], 0)
        wynik, kat = uruchom_na({"dist/index.html": self.HTML, "data/firma.json": {"przyklad": True}}, "dist", "data",
                                produkcja=True)
        shutil.rmtree(kat)
        self.assertEqual(wynik["kod"], 1)
        zw = [{"id": "PL-SEKCJA", "powod": "lista referencji z BZP, nagłówek ustalony z klientem", "gdzie": "index.html"}]
        wynik, kat = uruchom_na({"dist/index.html": self.HTML, "data/firma.json": {"przyklad": True},
                                 "data/slop-ok.json": zw}, "dist", "data", produkcja=True)
        shutil.rmtree(kat)
        self.assertNotIn("PL-SEKCJA", ids(wynik))
        self.assertEqual([w.id for w, _ in wynik["zwolnione"]], ["PL-SEKCJA"])
        self.assertEqual(wynik["kod"], 0)

    def test_zwolnienie_bez_powodu_p0_i_nieuzywane(self):
        html = self.HTML + "<p>Działamy z pasją.</p>"
        zw = [{"id": "PL-SEKCJA", "powod": ""}, {"id": "PL-FRAZES", "powod": "próba zwolnienia frazesu"},
              {"id": "V-SZKLO", "powod": "nagłówek nad zdjęciem hero"}]
        wynik, kat = uruchom_na({"dist/index.html": html, "data/firma.json": {"przyklad": True}, "data/slop-ok.json": zw},
                                "dist", "data")
        shutil.rmtree(kat)
        self.assertTrue({"SLOP-OK-BEZ-POWODU", "SLOP-OK-P0", "PL-SEKCJA", "PL-FRAZES"} <= ids(wynik))
        self.assertIn("SLOP-OK-NIEUZYWANE", ids(wynik, "P2"))
        self.assertEqual(wynik["kod"], 2)

    def test_komentarz_w_css(self):
        css = ".karta { backdrop-filter: blur(8px); } /* slop-ok: V-SZKLO podpis na zdjęciu */\na:focus-visible{outline:1px solid}"
        wynik, kat = uruchom_na({"a.css": css})
        shutil.rmtree(kat)
        self.assertNotIn("V-SZKLO", ids(wynik))
        self.assertEqual(len(wynik["zwolnione"]), 1)


class Wiersz(unittest.TestCase):
    def test_json_i_kod_wyjscia(self):
        kat = Path(tempfile.mkdtemp(prefix="slop-"))
        (kat / "a.html").write_text("<p>W dzisiejszych czasach robimy drogi.</p>", encoding="utf-8")
        w = subprocess.run([sys.executable, str(NARZEDZIA / "lint_slop.py"), str(kat), "--json"], capture_output=True, text=True)
        shutil.rmtree(kat)
        self.assertEqual(w.returncode, 2)
        dane = json.loads(w.stdout)
        self.assertEqual(dane["liczby"]["P0"], 1)
        self.assertEqual(dane["wyniki"][0]["id"], "PL-OPENER")
        self.assertTrue(dane["wyniki"][0]["naprawa"])

    def test_reguly(self):
        w = subprocess.run([sys.executable, str(NARZEDZIA / "lint_slop.py"), "--reguly"], capture_output=True, text=True)
        self.assertEqual(w.returncode, 0)
        self.assertIn("PL-FRAZES", w.stdout)


@unittest.skipUnless((KORZEN / "przyklady/bimex/data/firma.json").is_file(), "brak przyklady/bimex")
class Bimex(unittest.TestCase):
    """Kalibracja: prawdziwa treść BIMEX nie ma P0 ani P1 (tylko uwagi P2)."""

    def test_build_bimex_czysty(self):
        wyjscie = Path(tempfile.mkdtemp(prefix="dist-slop-"))
        try:
            b = subprocess.run([sys.executable, str(NARZEDZIA / "build.py"), "--klient", str(KORZEN / "przyklady/bimex"),
                                "--wyjscie", str(wyjscie), "--szybko"], capture_output=True, text=True, cwd=KORZEN)
            self.assertEqual(b.returncode, 0, b.stdout + b.stderr)
            wynik = lint_slop.uruchom([str(wyjscie), str(KORZEN / "przyklady/bimex/data")])
            zle = [(w.id, w.plik, w.komunikat) for w in wynik["wyniki"] if w.poziom in ("P0", "P1")]
            self.assertEqual(zle, [])
        finally:
            shutil.rmtree(wyjscie, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
