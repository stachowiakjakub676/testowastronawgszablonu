"""Dane strukturalne (KONTRAKT §9, jsonld.py): godziny jako OpeningHoursSpecification na przedział, wyjątki,
Organization z osobnym LocalBusiness, bez aggregateRating/review, bezpieczny <script>."""
from __future__ import annotations

import json
import unittest

from _wspolne import BIMEX, DZIS_DATA, KORZEN

from silnik import dane, jsonld
from silnik.komunikaty import Raport


def tydzien(**dni) -> dict:
    t = {d: [] for d in dane.DNI}
    t.update(dni)
    return t


GODZINY = {
    "nazwa": "Sala",
    "tydzien": tydzien(wt=[["12:00", "15:00"], ["17:00", "22:00"]], sr=[["12:00", "15:00"], ["17:00", "22:00"]],
                       pt=[["12:00", "15:00"], ["17:00", "02:00"]], sb=[["12:00", "24:00"]], nd=[["12:00", "00:00"]]),
    "dodatkowe": [{"nazwa": "Kuchnia", "tydzien": tydzien(wt=[["12:00", "21:00"]])}],
    "wyjatki": [
        {"data": "2026-09-01", "godziny": [], "opis": "przeszłość"},
        {"data": "2026-11-01", "godziny": [], "opis": "Wszystkich Świętych"},
        {"data": "2026-12-24", "godziny": [["10:00", "14:00"], ["16:00", "24:00"]], "opis": "Wigilia"},
        {"data": "2028-01-01", "godziny": [], "opis": "za ponad rok"},
    ],
    "uwagi": None, "pokazuj_status": True,
}


def przygotuj(godziny=GODZINY, typ=None, opinie=True):
    d = dane.wczytaj(BIMEX, KORZEN, Raport())
    d.firma["godziny"] = json.loads(json.dumps(godziny))
    if typ:
        d.preset["typ_schema"] = typ
    if opinie:
        d.firma["opinie_zbiorczo"] = {"zrodlo": "Google", "ocena": 4.8, "liczba": 212, "data": "2026-09-20",
                                      "url": "https://maps.example/opinie"}
        d.tresc["opinie"] = {"naglowek": None, "weryfikacja": "Cytujemy opinie z Google.", "pozycje": [
            {"tekst": "Dobra robota.", "autor": "Anna", "miejscowosc": None, "data": "2026-09-01",
             "url": "https://maps.example/o/1"}]}
    return d


def graf(d, sciezka="/"):
    auto = dane.auto(d, DZIS_DATA, set(), ["hero", "oferta", "kontakt"])
    strona = {"sciezka": sciezka, "okruszki": [], "kanoniczny": d.firma["firma"]["domena"] + sciezka,
              "og_obraz": "https://www.bimex-rogozno.pl/assets/img/og.jpg"}
    abs_url = lambda s: d.firma["firma"]["domena"] + "/" + s.lstrip("/")
    return jsonld.graf(d, auto, strona, abs_url, {"plik": "assets/img/logo.png", "szer": 112, "wys": 56}, DZIS_DATA)


def _dni(spec: dict) -> list[str]:
    return spec["dayOfWeek"] if isinstance(spec["dayOfWeek"], list) else [spec["dayOfWeek"]]


def wezel(g: dict, typ: str) -> dict:
    return next(w for w in g["@graph"] if w["@type"] == typ)


class Godziny(unittest.TestCase):
    def setUp(self):
        self.firma = wezel(graf(przygotuj()), "GeneralContractor")
        self.spec = self.firma["openingHoursSpecification"]

    def test_jedna_specyfikacja_na_przedzial(self):
        pary = {(s["opens"], s["closes"]) for s in self.spec}
        self.assertEqual(pary, {("12:00", "15:00"), ("12:00", "23:59"), ("17:00", "02:00"), ("17:00", "22:00")})
        # każdy przedział dnia jest w dokładnie jednej specyfikacji
        for dzien, liczba in (("Tuesday", 2), ("Friday", 2), ("Saturday", 1), ("Sunday", 1)):
            self.assertEqual(sum(dzien in _dni(s) for s in self.spec), liczba, dzien)

    def test_dni_o_tych_samych_godzinach_razem(self):
        po = {(s["opens"], s["closes"]): s["dayOfWeek"] for s in self.spec}
        self.assertEqual(po[("12:00", "15:00")], ["Tuesday", "Wednesday", "Friday"])
        self.assertEqual(po[("17:00", "22:00")], ["Tuesday", "Wednesday"])
        self.assertEqual(po[("17:00", "02:00")], "Friday")           # jeden dzień = napis, nie lista

    def test_polnoc_jako_2359(self):
        # „24:00” (sobota) i „00:00” (niedziela) = zamknięcie o północy → „23:59”
        for dzien in ("Saturday", "Sunday"):
            self.assertEqual([(s["opens"], s["closes"]) for s in self.spec if dzien in _dni(s)], [("12:00", "23:59")])

    def test_po_polnocy_zostaje_przy_dniu_otwarcia(self):
        piatek = [s for s in self.spec if "Friday" in _dni(s)]
        self.assertIn(("17:00", "02:00"), [(s["opens"], s["closes"]) for s in piatek])
        self.assertFalse(any("Saturday" == s["dayOfWeek"] and s["opens"] == "00:00" for s in self.spec))

    def test_dni_zamkniete_pominiete(self):
        dni = {d for s in self.spec for d in _dni(s)}
        self.assertNotIn("Monday", dni)
        self.assertNotIn("Thursday", dni)

    def test_wyjatki(self):
        spec = self.firma["specialOpeningHoursSpecification"]
        daty = [s["validFrom"] for s in spec]
        self.assertNotIn("2026-09-01", daty)                  # przeszłość
        self.assertNotIn("2028-01-01", daty)                  # dalej niż rok
        zamkniete = [s for s in spec if s["validFrom"] == "2026-11-01"]
        self.assertEqual(zamkniete, [{"@type": "OpeningHoursSpecification", "validFrom": "2026-11-01",
                                      "validThrough": "2026-11-01", "opens": "00:00", "closes": "00:00"}])
        wigilia = sorted((s["opens"], s["closes"]) for s in spec if s["validFrom"] == "2026-12-24")
        self.assertEqual(wigilia, [("10:00", "14:00"), ("16:00", "23:59")])

    def test_bez_godzin_bez_specyfikacji(self):
        f = wezel(graf(przygotuj(godziny=None)), "GeneralContractor")
        self.assertNotIn("openingHoursSpecification", f)
        self.assertNotIn("specialOpeningHoursSpecification", f)

    def test_bez_wyjatkow_bez_special(self):
        g = dict(GODZINY, wyjatki=[])
        self.assertNotIn("specialOpeningHoursSpecification", wezel(graf(przygotuj(godziny=g)), "GeneralContractor"))


class Firma(unittest.TestCase):
    def test_dane_firmy(self):
        f = wezel(graf(przygotuj()), "GeneralContractor")
        self.assertEqual(f["telephone"], "+48672683408")
        self.assertEqual(f["taxID"], "6060092256")
        self.assertEqual(f["address"]["postalCode"], "64-610")
        self.assertEqual(f["geo"]["latitude"], 52.7536)
        self.assertIn("https://www.facebook.com/profile.php?id=100064015176507", f["sameAs"])
        self.assertEqual({i["propertyID"] for i in f["identifier"]}, {"KRS", "REGON"})
        self.assertTrue(f["logo"]["url"].startswith("https://"))
        self.assertEqual(len(f["contactPoint"]), 3)

    def test_organization_ma_osobny_lokal_z_godzinami(self):
        g = graf(przygotuj(typ="Organization"))
        org = wezel(g, "Organization")
        lokal = wezel(g, "LocalBusiness")
        self.assertNotIn("openingHoursSpecification", org)
        self.assertNotIn("geo", org)
        self.assertTrue(lokal["@id"].endswith("/#lokal"))
        self.assertEqual(lokal["parentOrganization"], {"@id": org["@id"]})
        self.assertIn("openingHoursSpecification", lokal)
        self.assertIn("geo", lokal)
        self.assertTrue(lokal["name"].endswith("– Sala"))

    def test_nigdy_ocen_ani_opinii(self):
        for typ in (None, "Organization", "Restaurant"):
            with self.subTest(typ=typ):
                tekst = json.dumps(graf(przygotuj(typ=typ, opinie=True)))
                self.assertNotIn("aggregateRating", tekst)
                self.assertNotIn('"review"', tekst)
                self.assertNotIn('"Review"', tekst)

    def test_website_i_wydawca(self):
        g = graf(przygotuj())
        www = wezel(g, "WebSite")
        self.assertEqual(www["inLanguage"], "pl-PL")
        self.assertEqual(www["publisher"]["@id"], wezel(g, "GeneralContractor")["@id"])

    def test_faq_tylko_gdy_wlaczone(self):
        d = przygotuj()
        d.tresc["faq"] = {"naglowek": None, "pozycje": [{"pytanie": "Czy?", "odpowiedz": "**Tak**, [zob.](/kontakt)."}]}
        auto = dane.auto(d, DZIS_DATA, set(), ["hero", "faq"])
        strona = {"sciezka": "/", "okruszki": [], "kanoniczny": "https://x.example/"}
        typy = lambda: [w["@type"] for w in jsonld.graf(d, auto, strona, lambda s: s, None, DZIS_DATA)["@graph"]]
        self.assertNotIn("FAQPage", typy())
        d.firma["funkcje"]["faq_schema"] = True
        self.assertIn("FAQPage", typy())
        faq = next(w for w in jsonld.graf(d, auto, strona, lambda s: s, None, DZIS_DATA)["@graph"] if w["@type"] == "FAQPage")
        self.assertEqual(faq["mainEntity"][0]["acceptedAnswer"]["text"], "Tak, zob..")

    def test_okruszki(self):
        d = przygotuj()
        auto = dane.auto(d, DZIS_DATA, set(), [])
        strona = {"sciezka": "/kontakt", "kanoniczny": "https://www.bimex-rogozno.pl/kontakt",
                  "okruszki": [{"nazwa": "Strona główna", "url": "/"}, {"nazwa": "Kontakt", "url": None}]}
        g = jsonld.graf(d, auto, strona, lambda s: s, None, DZIS_DATA)
        lista = wezel(g, "BreadcrumbList")["itemListElement"]
        self.assertEqual([x["position"] for x in lista], [1, 2])
        self.assertEqual(lista[1]["item"], "https://www.bimex-rogozno.pl/kontakt")


class Skrypt(unittest.TestCase):
    def test_jako_skrypt_escapuje(self):
        tekst = jsonld.jako_skrypt({"a": "</script><script>alert(1)</script><!--"})
        self.assertNotIn("<", tekst)
        self.assertEqual(json.loads(tekst)["a"], "</script><script>alert(1)</script><!--")

    def test_polskie_znaki_bez_escape(self):
        self.assertIn("Rogoźno", jsonld.jako_skrypt({"m": "Rogoźno"}))


if __name__ == "__main__":
    unittest.main()
