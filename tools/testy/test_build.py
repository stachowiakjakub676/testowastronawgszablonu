"""Build od początku do końca (tools/build.py w osobnym procesie): przykład BIMEX, fikstury branż, szkielety z start.py.

Każdy build idzie do katalogu tymczasowego, „dziś” = _wspolne.DZIS (SZABLON_DZIS). Testy nie zakładają braku
ostrzeżeń (np. rozmiar CSS) — tylko braku błędów i obecności stron, które przy tych danych muszą powstać.
Sekcje, których plików jeszcze nie ma w src/sekcje/, build pomija z INFO — testy na nie nie liczą.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _wspolne import BIMEX, DZIS, FIKSTURY, KLIENCI, KORZEN, czytaj_json, kopia_klienta, zapisz_json, zbuduj

BRANZE = ["restauracja", "budowlana", "producent", "uslugi", "gabinet"]


def _tmp(test: unittest.TestCase | type) -> Path:
    p = Path(tempfile.mkdtemp(prefix="szablon-test-"))
    (test.addClassCleanup if isinstance(test, type) else test.addCleanup)(shutil.rmtree, p, True)
    return p


def ld(html: str) -> list[dict]:
    """Węzły @graph z JSON-LD strony."""
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))["@graph"] if m else []


class Bimex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = zbuduj(BIMEX, wyjscie=_tmp(cls) / "dist")

    def test_bez_bledow(self):
        self.assertEqual(self.w.kod, 0, self.w.opis_bledow())
        self.assertEqual(self.w.bledy, [])

    def test_strony_i_pliki(self):
        for plik in ("index.html", "kontakt.html", "oferta.html", "realizacje.html", "polityka-prywatnosci.html",
                     "404.html", "dziekujemy.html", "blad.html", "_headers", "robots.txt", "sitemap.xml",
                     "assets/css/strona.css", "assets/js/strona.js", ".well-known/security.txt", "site.webmanifest",
                     ".szablon-wynik", ".assetsignore"):
            with self.subTest(plik=plik):
                self.assertTrue((self.w.dist / plik).is_file())
        self.assertEqual(set(self.w.wynik["strony"]) >= {"/", "/kontakt", "/oferta", "/realizacje"}, True)

    def test_sitemap_bez_stron_technicznych(self):
        mapa = (self.w.dist / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://www.bimex-rogozno.pl/</loc>", mapa)
        self.assertIn("<loc>https://www.bimex-rogozno.pl/kontakt</loc>", mapa)
        for s in ("/404", "/blad", "/dziekujemy"):
            self.assertNotIn(f"bimex-rogozno.pl{s}<", mapa)
        self.assertIn("Sitemap: https://www.bimex-rogozno.pl/sitemap.xml",
                      (self.w.dist / "robots.txt").read_text(encoding="utf-8"))

    def test_naglowki_bezpieczenstwa(self):
        h = (self.w.dist / "_headers").read_text(encoding="utf-8")
        for fragment in ("Content-Security-Policy", "script-src 'self' 'sha256-", "X-Content-Type-Options: nosniff",
                         "Referrer-Policy", "Permissions-Policy", "Strict-Transport-Security", "/assets/*"):
            self.assertIn(fragment, h)

    def test_zasoby_z_wersja_i_bez_obcych(self):
        html = (self.w.dist / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'href="/assets/css/strona\.css\?v=[0-9a-f]+"')
        self.assertRegex(html, r'src="/assets/js/strona\.js\?v=[0-9a-f]+"')
        self.assertNotIn("fonts.googleapis", html)
        for adres in re.findall(r'(?:src|srcset)="([^"]+)"', html):
            self.assertFalse(adres.startswith(("http:", "https:", "//")), adres)

    def test_meta_i_json_ld(self):
        html = (self.w.dist / "index.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="pl"', html)
        self.assertRegex(html, r'<meta property="og:image" content="https://www\.bimex-rogozno\.pl/assets/img/og\.jpg\?v=')
        self.assertIn('<link rel="canonical" href="https://www.bimex-rogozno.pl/">', html)
        typy = [w["@type"] for w in ld(html)]
        self.assertIn("GeneralContractor", typy)
        self.assertIn("WebSite", typy)
        self.assertEqual(html.count("<h1"), 1)

    def test_strona_404_noindex(self):
        html = (self.w.dist / "404.html").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex', html)
        self.assertNotIn('rel="canonical"', html)


class TrybyBuildu(unittest.TestCase):
    def test_produkcja_odrzuca_przyklad(self):
        w = zbuduj(BIMEX, "--produkcja", sprzataj=self.addCleanup)
        self.assertEqual(w.kod, 1)
        self.assertTrue(any("dane przykładowe" in t for t in w.teksty("BŁĄD")))

    def test_szybko(self):
        w = zbuduj(BIMEX, "--szybko", sprzataj=self.addCleanup)
        self.assertEqual(w.kod, 0, w.opis_bledow())
        self.assertTrue((w.dist / "index.html").is_file())

    def test_linki_wzgledne_w_trybie_plik(self):
        w = zbuduj(BIMEX, "--plik", sprzataj=self.addCleanup)
        self.assertEqual(w.kod, 0, w.opis_bledow())
        html = (w.dist / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="kontakt.html', html)
        self.assertIn('href="assets/css/strona.css?v=', html)

    def test_zla_data_dzis(self):
        w = zbuduj(BIMEX, dzis="2026-13-01", sprzataj=self.addCleanup)
        self.assertEqual(w.kod, 1)
        self.assertIn("SZABLON_DZIS", w.stderr)

    def test_nie_usuwa_obcego_katalogu(self):
        cel = _tmp(self) / "moje-pliki"
        cel.mkdir()
        (cel / "wazny.txt").write_text("nie kasować", encoding="utf-8")
        w = zbuduj(BIMEX, wyjscie=cel)
        self.assertEqual(w.kod, 1)
        self.assertTrue((cel / "wazny.txt").is_file())
        self.assertTrue(any("nie jest wynikiem buildu" in t for t in w.teksty("BŁĄD")))

    def test_blad_danych_przed_renderem(self):
        k = kopia_klienta(BIMEX, self.addCleanup)
        f = czytaj_json(k / "data" / "firma.json")
        f["kontakt"]["telefon"] = "67 268 34 08"
        f["rejestr"]["nip"] = "6060092257"
        zapisz_json(k / "data" / "firma.json", f)
        w = zbuduj(k, sprzataj=self.addCleanup)
        self.assertEqual(w.kod, 1)
        pola = {b.get("pole") for b in w.bledy}
        self.assertIn("kontakt.telefon", pola)
        self.assertFalse((w.dist / "index.html").exists())       # schemat zatrzymał build przed renderem


class Szkielety(unittest.TestCase):
    """start.py tworzy puste dane — build ma wypisać po polsku, czego brakuje, i zakończyć się kodem 1."""

    # pola zawsze wymagane (dane.WYMAGANE) — sprawdzamy pole, nie brzmienie opisu, które może się zmienić
    WSPOLNE = ["firma.nazwa", "firma.opis", "firma.domena", "kontakt.telefon", "kontakt.adres.kod",
               "rejestr.forma_prawna", "marka.kolor", "seo.fraza", "hero.naglowek", "hero.lead"]
    PRESET = {
        "restauracja": ["branża „restauracja” wymaga: godziny", "branża „restauracja” wymaga: tresc.menu albo tresc.cennik"],
        "budowlana": ["branża „budowlana” wymaga: tresc.oferta.pozycje"],
        "producent": ["branża „producent” wymaga: tresc.produkty.pozycje"],
        "uslugi": ["branża „uslugi” wymaga: tresc.oferta.pozycje albo tresc.cennik"],
        "gabinet": ["branża „gabinet” wymaga: godziny", "branża „gabinet” wymaga: tresc.oferta.pozycje albo tresc.cennik"],
    }

    def test_szkielet_kazdej_branzy(self):
        tmp = _tmp(self)
        for branza in BRANZE:
            with self.subTest(branza=branza):
                klient = tmp / branza
                p = subprocess.run([sys.executable, str(KORZEN / "tools" / "start.py"), "--branza", branza,
                                    "--klient", str(klient)], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                f = czytaj_json(klient / "data" / "firma.json")
                self.assertEqual(f["branza"], branza)
                self.assertFalse(f["przyklad"])
                w = zbuduj(klient, wyjscie=tmp / f"dist-{branza}")
                self.assertEqual(w.kod, 1)
                bledy = w.teksty("BŁĄD")
                braki = {k.get("pole") for k in w.bledy if k["tresc"].startswith("brak danych: ")}
                for pole in self.WSPOLNE:
                    self.assertIn(pole, braki)
                for oczekiwany in self.PRESET[branza]:
                    self.assertIn(oczekiwany, bledy)
                # każdy błąd wskazuje plik i pole
                self.assertTrue(all(b.get("plik") for b in w.bledy))
                self.assertFalse((tmp / f"dist-{branza}" / "index.html").exists())

    def test_start_nie_nadpisuje(self):
        klient = _tmp(self) / "k"
        polecenie = [sys.executable, str(KORZEN / "tools" / "start.py"), "--branza", "uslugi", "--klient", str(klient)]
        self.assertEqual(subprocess.run(polecenie, capture_output=True).returncode, 0)
        (klient / "data" / "firma.json").write_text("{}", encoding="utf-8")
        p = subprocess.run(polecenie, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("nic nie zmieniam", p.stdout)
        self.assertEqual((klient / "data" / "firma.json").read_text(encoding="utf-8"), "{}")

    def test_nietkniety_szkielet_bez_nadpisz(self):
        """Szkielet bez zmian (np. kopia repozytorium SZABLON) zmienia branżę bez --nadpisz; README SZABLONU zmienia się
        w README klienta ze znacznikami „Do potwierdzenia”, a namespace_id limitu formularza przestaje być „1101”."""
        klient = _tmp(self) / "k"
        klient.mkdir()
        shutil.copy2(KORZEN / "README.md", klient / "README.md")
        shutil.copy2(KORZEN / "wrangler.jsonc", klient / "wrangler.jsonc")
        start = [sys.executable, str(KORZEN / "tools" / "start.py"), "--klient", str(klient)]
        self.assertEqual(subprocess.run(start + ["--branza", "uslugi", "--tylko-dane"], capture_output=True).returncode, 0)
        self.assertTrue((klient / "README.md").read_text(encoding="utf-8").startswith("# SZABLON"))
        p = subprocess.run(start + ["--branza", "restauracja"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(czytaj_json(klient / "data" / "firma.json")["branza"], "restauracja")
        readme = (klient / "README.md").read_text(encoding="utf-8")
        self.assertIn("<!-- do-potwierdzenia:poczatek -->", readme)
        self.assertIn("`data/tresc.json` → `menu`", readme)
        self.assertNotIn('"namespace_id": "1101"', (klient / "wrangler.jsonc").read_text(encoding="utf-8"))

    def test_szkielet_repozytorium_jest_aktualny(self):
        """data/ w repozytorium SZABLON = szkielet „uslugi” z start.py — inaczej start.py w kopii szablonu wymagałby
        --nadpisz (po zmianie schematu: python3 tools/start.py --branza uslugi --tylko-dane --nadpisz)."""
        sys.path.insert(0, str(KORZEN / "tools"))
        import start
        self.assertTrue(start.nietkniety_szkielet(KORZEN / "data", "../tools/schemat"))


class Fikstury(unittest.TestCase):
    """Klienci testowi z tools/testy/klienci/: każdy buduje się bez błędów i ma strony swojej branży."""

    STRONY = {
        "restauracja": {"/", "/kontakt", "/menu", "/o-firmie", "/polityka-prywatnosci"},
        "producent": {"/", "/kontakt", "/produkty"},
        "uslugi": {"/", "/kontakt", "/oferta", "/oferta/przeglad"},
        "gabinet": {"/", "/kontakt", "/oferta", "/o-firmie"},
    }

    @classmethod
    def setUpClass(cls):
        tmp = _tmp(cls)
        cls.w = {k: zbuduj(KLIENCI / k, wyjscie=tmp / k) for k in FIKSTURY}

    def html(self, klient: str, plik: str = "index.html") -> str:
        return (self.w[klient].dist / plik).read_text(encoding="utf-8")

    def test_buduja_sie_bez_bledow(self):
        for k in FIKSTURY:
            with self.subTest(klient=k):
                self.assertEqual(self.w[k].kod, 0, self.w[k].opis_bledow())
                self.assertEqual(self.w[k].bledy, [])

    def test_strony_branzy(self):
        for k, strony in self.STRONY.items():
            with self.subTest(klient=k):
                self.assertLessEqual(strony, set(self.w[k].wynik["strony"]))

    def test_restauracja_godziny_po_polnocy_w_json_ld(self):
        firma = next(w for w in ld(self.html("restauracja")) if w["@type"] == "Restaurant")
        pary = {(s["opens"], s["closes"]) for s in firma["openingHoursSpecification"]}
        self.assertIn(("17:00", "02:00"), pary)
        self.assertIn(("12:00", "02:00"), pary)
        wyjatki = [s["validFrom"] for s in firma["specialOpeningHoursSpecification"]]
        self.assertEqual(len(wyjatki), 3)                          # wyjątek sprzed DZIS pominięty
        self.assertTrue(all(d >= DZIS for d in wyjatki), wyjatki)

    def test_restauracja_karta(self):
        html = self.html("restauracja", "menu.html")
        self.assertIn("Żurek na zakwasie", html)
        self.assertIn("PDF", html)
        self.assertIn("Menu", [w["@type"] for w in ld(html)])

    def test_producent_organizacja_i_lokal(self):
        typy = [w["@type"] for w in ld(self.html("producent"))]
        self.assertIn("Organization", typy)
        self.assertIn("LocalBusiness", typy)
        self.assertIn("data-filtr", self.html("producent", "produkty.html"))
        self.assertIn("Pozostałe", self.html("producent", "produkty.html"))

    def test_producent_przycisk_katalogu(self):
        self.assertIn('href="/assets/img/pliki/katalog-testowy.pdf', self.html("producent"))

    def test_producent_wygasly_certyfikat_ukryty(self):
        w = self.w["producent"]
        self.assertTrue(any("wygasł" in t for t in w.teksty("OSTRZEŻENIE")))
        self.assertNotIn("Certyfikat wygasły (test)", "".join(
            p.read_text(encoding="utf-8") for p in w.dist.rglob("*.html")))

    def test_uslugi_faq_schema_i_zespol(self):
        typy = [w["@type"] for w in ld(self.html("uslugi"))]
        self.assertIn('id="faq"', self.html("uslugi"))
        self.assertIn("FAQPage", typy)                             # funkcje.faq_schema = true
        self.assertNotIn("FAQPage", [w["@type"] for w in ld(self.html("uslugi", "kontakt.html"))])
        w = self.w["uslugi"]
        self.assertTrue(any("„Tomasz” ma zdjęcie bez zgody" in t for t in w.teksty("OSTRZEŻENIE")))
        self.assertNotIn("foto--osoba-b", "".join(p.read_text(encoding="utf-8") for p in w.dist.rglob("*.html")))

    def test_uslugi_podstrona_uslugi(self):
        html = self.html("uslugi", "oferta/przeglad.html")
        self.assertIn("Service", [w["@type"] for w in ld(html)])
        self.assertRegex(html, r'property="og:image" content="https://serwis-probny\.example/assets/img/og/naprawa\.jpg')

    def test_gabinet_portrety_zespolu(self):
        html = self.html("gabinet", "o-firmie.html")
        for i in range(1, 5):
            self.assertIn(f"foto--portret-{i}", html)

    def test_produkcja_odrzuca_fikstury(self):
        w = zbuduj(KLIENCI / "uslugi", "--produkcja", sprzataj=self.addCleanup)
        self.assertEqual(w.kod, 1)
        self.assertTrue(any("dane przykładowe" in t for t in w.teksty("BŁĄD")))


class FiksturyZGeneratora(unittest.TestCase):
    """Pliki w klienci/*/data/ muszą być dokładnie wynikiem generuj.py — ręczna zmiana JSON-a zniknęłaby przy
    następnym generowaniu. Napraw: zmień generuj.py i uruchom python3 tools/testy/klienci/generuj.py --tylko-dane."""

    def test_dane_zgodne_z_generatorem(self):
        sys.path.insert(0, str(KLIENCI))
        import generuj
        for k in FIKSTURY:
            with self.subTest(klient=k):
                wzor = getattr(generuj, k)()
                katalog = KLIENCI / k / "data"
                self.assertEqual(czytaj_json(katalog / "firma.json"), wzor["firma"])
                self.assertEqual(czytaj_json(katalog / "tresc.json"), wzor["tresc"])
                zdj = [{x: y for x, y in z.items() if x != "_gen"} for z in wzor["zdjecia"]]
                self.assertEqual(czytaj_json(katalog / "zdjecia.json")["zdjecia"], zdj)
                for sciezka, tekst in wzor["md"].items():
                    self.assertEqual((katalog / sciezka).read_text(encoding="utf-8"), tekst, sciezka)
                for sciezka in wzor["pliki"]:
                    self.assertTrue((KLIENCI / k / sciezka).is_file(), sciezka)


class JednaData(unittest.TestCase):
    def test_dzis_w_ci_taki_jak_w_testach(self):
        ci = (KORZEN / ".github" / "workflows" / "sprawdz.yml").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'SZABLON_DZIS: "(\d{4}-\d{2}-\d{2})"', ci), [DZIS])
        self.assertIn(DZIS, (KLIENCI / "README.md").read_text(encoding="utf-8"))


class FiksturySaFikcyjne(unittest.TestCase):
    """Straż: dane fikstur mają zostać oczywiście testowe (nie mogą udawać prawdziwej firmy)."""

    def test_znaczniki_fikcji(self):
        from silnik import dane
        for k in FIKSTURY:
            with self.subTest(klient=k):
                f = czytaj_json(KLIENCI / k / "data" / "firma.json")
                self.assertTrue(f["przyklad"])
                self.assertTrue(f["firma"]["domena"].endswith(".example"))
                self.assertRegex(f["kontakt"]["telefon"], r"^\+4850000000\d$")
                self.assertTrue(f["rejestr"]["nip"].startswith("000") and dane.nip_ok(f["rejestr"]["nip"]))
                if f["rejestr"]["regon"]:
                    self.assertTrue(f["rejestr"]["regon"].startswith("000") and dane.regon_ok(f["rejestr"]["regon"]))
                self.assertIn("Test", f["kontakt"]["adres"]["ulica"])
                tekst = json.dumps(f, ensure_ascii=False) + (KLIENCI / k / "data" / "tresc.json").read_text(encoding="utf-8")
                for adres in re.findall(r"https://([a-z0-9.-]+)", tekst):
                    self.assertTrue(adres.endswith(".example"), adres)

    def test_zdjecia_to_zastepniki(self):
        for k in FIKSTURY:
            with self.subTest(klient=k):
                for z in czytaj_json(KLIENCI / k / "data" / "zdjecia.json")["zdjecia"]:
                    self.assertIn("zastępcze", z["alt"])
                    self.assertIn("zastępcze", z["zrodlo"])


if __name__ == "__main__":
    unittest.main()
