"""Model danych (KONTRAKT §4): walidacja schematem, sumy kontrolne, godziny, forma prawna, nieznane pola."""
from __future__ import annotations

import json
import unittest

from _wspolne import BIMEX, DZIS_DATA, KORZEN

from silnik import dane
from silnik.komunikaty import Raport
from silnik.schemat import waliduj

SCHEMAT_FIRMY = json.loads((KORZEN / "tools" / "schemat" / "firma.schema.json").read_text(encoding="utf-8"))
SCHEMAT_TRESCI = json.loads((KORZEN / "tools" / "schemat" / "tresc.schema.json").read_text(encoding="utf-8"))


def firma_bimex() -> dict:
    return json.loads((BIMEX / "data" / "firma.json").read_text(encoding="utf-8"))


def bledy_schematu(obiekt, schemat=SCHEMAT_FIRMY) -> list[tuple[str, str]]:
    return waliduj(obiekt, schemat)


def wczytaj_bimex(raport=None):
    """Świeże dane przykładu (Dane) — każdy test mutuje własną kopię."""
    d = dane.wczytaj(BIMEX, KORZEN, raport or Raport())
    assert d is not None
    return d


def kontrole(d) -> Raport:
    r = Raport()
    dane.kontrole(d, r, False, DZIS_DATA)
    return r


def teksty(raport: Raport, poziom: str = "BŁĄD") -> list[str]:
    return [k.tresc for k in raport.lista(poziom)]


class SumyKontrolne(unittest.TestCase):
    def test_nip(self):
        self.assertTrue(dane.nip_ok("6060092256"))          # BIMEX (KRS 0000455988)
        self.assertTrue(dane.nip_ok("0000000017"))          # fikstura restauracja (fikcyjny)
        self.assertFalse(dane.nip_ok("6060092257"))
        self.assertFalse(dane.nip_ok("6060092265"))         # przestawione cyfry

    def test_nip_z_suma_10_zawsze_zly(self):
        # 000000003: suma ważona = 21 → 21 mod 11 = 10 — taki NIP nie istnieje, żadna ostatnia cyfra nie pasuje
        self.assertFalse(any(dane.nip_ok("000000003" + str(c)) for c in range(10)))

    def test_regon_9(self):
        self.assertTrue(dane.regon_ok("302388186"))         # BIMEX
        self.assertFalse(dane.regon_ok("302388187"))
        self.assertFalse(dane.regon_ok("30238818"))         # 8 cyfr

    def test_regon_z_suma_10_ma_cyfre_0(self):
        # suma mod 11 == 10 → cyfra kontrolna 0 (inaczej niż w NIP)
        r8 = next(f"{i:08d}" for i in range(1, 10 ** 6)
                  if sum(int(c) * w for c, w in zip(f"{i:08d}", [8, 9, 2, 3, 4, 5, 6, 7])) % 11 == 10)
        self.assertTrue(dane.regon_ok(r8 + "0"))

    def test_regon_14(self):
        baza = "302388186"
        w = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
        r13 = baza + "0001"
        s = sum(int(r13[i]) * w[i] for i in range(13)) % 11
        dobry = r13 + str(0 if s == 10 else s)
        self.assertTrue(dane.regon_ok(dobry))
        self.assertFalse(dane.regon_ok(dobry[:-1] + str((int(dobry[-1]) + 1) % 10)))
        self.assertFalse(dane.regon_ok("302388187" + dobry[9:]))   # zła 9-cyfrowa część

    def test_build_zglasza_zly_nip_i_regon(self):
        d = wczytaj_bimex()
        d.firma["rejestr"]["nip"] = "6060092257"
        d.firma["rejestr"]["regon"] = "302388187"
        b = teksty(kontrole(d))
        self.assertIn("NIP 6060092257 ma złą sumę kontrolną", b)
        self.assertIn("REGON 302388187 ma złą sumę kontrolną", b)

    def test_krs_tylko_format(self):
        # KRS nie ma cyfry kontrolnej — schemat sprawdza tylko 10 cyfr
        for krs, ok in (("0000455988", True), ("455988", False), ("0000-455988", False), ("00004559881", False)):
            with self.subTest(krs=krs):
                f = firma_bimex()
                f["rejestr"]["krs"] = krs
                self.assertEqual(not any(p == "rejestr.krs" for p, _ in bledy_schematu(f)), ok)


class Formaty(unittest.TestCase):
    def sprawdz(self, pole: list[str], wartosci: dict):
        for v, ok in wartosci.items():
            with self.subTest(pole=".".join(pole), v=v):
                f = firma_bimex()
                o = f
                for k in pole[:-1]:
                    o = o[k]
                o[pole[-1]] = v
                bledy = [p for p, _ in bledy_schematu(f)]
                self.assertEqual(".".join(pole) not in bledy, ok, bledy)

    def test_kod_pocztowy(self):
        self.sprawdz(["kontakt", "adres", "kod"], {"64-610": True, "64610": False, "6-4610": False, "64-61": False,
                                                    "64 610": False, "64–610": False})

    def test_telefon_e164(self):
        self.sprawdz(["kontakt", "telefon"], {"+48672683408": True, "+48500000001": True, "672683408": False,
                                              "+48 67 268 34 08": False, "0048672683408": False, "+0672683408": False,
                                              "+4867": False})

    def test_nip_format(self):
        self.sprawdz(["rejestr", "nip"], {"6060092256": True, "606-009-22-56": False, "606009225": False})

    def test_domena(self):
        self.sprawdz(["firma", "domena"], {"https://firma.pl": True, "https://firma.pl/": False, "http://firma.pl": False,
                                           "firma.pl": False})

    def test_kolor(self):
        self.sprawdz(["marka", "kolor"], {"#C8471F": True, "#c8471f": True, "C8471F": False, "#C84": False})

    def test_godzina(self):
        for g, ok in (("07:00", True), ("24:00", True), ("23:59", True), ("7:00", False), ("24:30", False),
                      ("25:00", False), ("12:60", False)):
            with self.subTest(g=g):
                f = firma_bimex()
                f["godziny"] = {"nazwa": None, "tydzien": {d: [] for d in dane.DNI}, "dodatkowe": None, "wyjatki": [],
                                "uwagi": None, "pokazuj_status": True}
                f["godziny"]["tydzien"]["pn"] = [[g, "15:00"] if g != "24:00" else ["20:00", g]]
                self.assertEqual(not bledy_schematu(f), ok, bledy_schematu(f))

    def test_data_z_kalendarzem(self):
        t = json.loads((BIMEX / "data" / "tresc.json").read_text(encoding="utf-8"))
        t["ogloszenie"] = {"tekst": "Test", "od": "2026-02-30", "do": None}
        bledy = bledy_schematu(t, SCHEMAT_TRESCI)
        self.assertTrue(any(p == "ogloszenie.od" and "30.02.2026" in b for p, b in bledy), bledy)


class NieznanePola(unittest.TestCase):
    def test_literowka_w_polu(self):
        f = firma_bimex()
        f["kontakt"]["telefonn"] = "+48672683408"
        bledy = bledy_schematu(f)
        self.assertTrue(bledy)
        pole, tresc = bledy[0]
        self.assertIn("telefonn", pole + tresc)
        self.assertIn("telefon", tresc)                    # podpowiedź podobnej nazwy

    def test_nieznany_blok_tresci(self):
        t = json.loads((BIMEX / "data" / "tresc.json").read_text(encoding="utf-8"))
        t["cenik"] = None
        self.assertTrue(bledy_schematu(t, SCHEMAT_TRESCI))

    def test_brak_wymaganego_klucza(self):
        f = firma_bimex()
        del f["kontakt"]["email"]
        self.assertTrue(any("email" in p + b for p, b in bledy_schematu(f)))

    def test_zly_typ(self):
        f = firma_bimex()
        f["firma"]["rok_zalozenia"] = "1993"
        self.assertTrue(any(p == "firma.rok_zalozenia" for p, _ in bledy_schematu(f)))

    def test_bimex_przechodzi(self):
        self.assertEqual(bledy_schematu(firma_bimex()), [])
        t = json.loads((BIMEX / "data" / "tresc.json").read_text(encoding="utf-8"))
        self.assertEqual(bledy_schematu(t, SCHEMAT_TRESCI), [])


def tydzien(**dni) -> dict:
    t = {d: [] for d in dane.DNI}
    t.update(dni)
    return t


class Godziny(unittest.TestCase):
    def raport(self, t: dict) -> Raport:
        r = Raport()
        dane._sprawdz_tydzien(t, r, "godziny.tydzien")
        return r

    def test_kilka_przedzialow_ok(self):
        r = self.raport(tydzien(wt=[["12:00", "15:00"], ["17:00", "22:00"]], sr=[["08:00", "10:00"], ["10:00", "12:00"]]))
        self.assertEqual(r.komunikaty, [])

    def test_po_polnocy_ok(self):
        r = self.raport(tydzien(pt=[["17:00", "02:00"]], sb=[["12:00", "02:00"]], nd=[["12:00", "21:00"]]))
        self.assertEqual(r.komunikaty, [])

    def test_do_polnocy_24_i_00(self):
        self.assertEqual(self.raport(tydzien(pn=[["18:00", "24:00"]], wt=[["18:00", "00:00"]])).komunikaty, [])

    def test_calodobowo(self):
        self.assertEqual(self.raport(tydzien(**{d: [["00:00", "24:00"]] for d in dane.DNI})).komunikaty, [])

    def test_nakladanie_w_jednym_dniu(self):
        b = teksty(self.raport(tydzien(pn=[["08:00", "14:00"], ["13:00", "18:00"]])))
        self.assertIn("przedziały godzin nachodzą na siebie: poniedziałek", b)

    def test_nakladanie_miedzy_dniami(self):
        b = teksty(self.raport(tydzien(pt=[["20:00", "04:00"]], sb=[["02:00", "10:00"]])))
        self.assertIn("przedziały godzin nachodzą na siebie: piątek i sobota", b)

    def test_z_niedzieli_na_poniedzialek(self):
        b = teksty(self.raport(tydzien(nd=[["20:00", "03:00"]], pn=[["01:00", "05:00"]])))
        self.assertIn("przedziały godzin nachodzą na siebie: niedziela i poniedziałek", b)

    def test_zerowy_przedzial(self):
        b = teksty(self.raport(tydzien(pn=[["08:00", "08:00"]])))
        self.assertTrue(any("zerową długość" in x for x in b), b)

    def test_zamkniecie_pozno_po_polnocy_to_ostrzezenie(self):
        r = self.raport(tydzien(pn=[["20:00", "07:00"]]))
        self.assertEqual(r.bledy, [])
        self.assertTrue(any("po północy później niż o 6:00" in x for x in teksty(r, "OSTRZEŻENIE")))

    def test_wszystkie_dni_zamkniete(self):
        d = wczytaj_bimex()
        d.firma["godziny"] = {"nazwa": None, "tydzien": tydzien(), "dodatkowe": None, "wyjatki": [], "uwagi": None,
                              "pokazuj_status": True}
        self.assertTrue(any("wszystkie dni zamknięte" in x for x in teksty(kontrole(d))))

    def test_nakladanie_w_godzinach_dodatkowych(self):
        d = wczytaj_bimex()
        d.firma["godziny"] = {"nazwa": None, "tydzien": tydzien(pn=[["08:00", "16:00"]]),
                              "dodatkowe": [{"nazwa": "Kuchnia", "tydzien": tydzien(pn=[["08:00", "12:00"], ["11:00", "15:00"]])}],
                              "wyjatki": [], "uwagi": None, "pokazuj_status": True}
        r = kontrole(d)
        self.assertTrue(any(k.pole == "godziny.dodatkowe[0].tydzien.pn" for k in r.bledy), teksty(r))

    def test_tekst_godzin(self):
        t = tydzien(pn=[["07:00", "15:00"]], wt=[["07:00", "15:00"]], sr=[["07:00", "15:00"]],
                    cz=[["07:00", "15:00"]], pt=[["12:00", "15:00"], ["18:00", "02:00"]], sb=[["10:00", "24:00"]])
        self.assertEqual(dane.godziny_skrot(t), "pn.–czw. 7:00–15:00; pt. 12:00–15:00, 18:00–2:00; sob. 10:00–24:00")
        tabela = {w["kod"]: w for w in dane.godziny_tabela(t)}
        self.assertEqual(tabela["nd"]["przedzialy_tekst"], "zamknięte")
        self.assertTrue(tabela["nd"]["zamkniete"])
        self.assertEqual(tabela["sb"]["przedzialy_tekst"], "10:00–24:00")
        self.assertEqual(dane._przedzialy_tekst([["18:00", "00:00"]]), "18:00–24:00")


class FormaPrawna(unittest.TestCase):
    def bledy_formy(self, forma: str, **pola) -> list[str]:
        d = wczytaj_bimex()
        r = d.firma["rejestr"]
        r.update({"forma_prawna": forma, "krs": None, "sad_rejestrowy": None, "kapital_zakladowy": None,
                  "wlasciciel": None, "wspolnicy": None})
        r.update(pola)
        return [k.pole for k in kontrole(d).bledy if "w stopce musi być" in k.tresc]

    def test_sp_z_oo_wymaga_krs_sadu_nip_kapitalu(self):
        self.assertEqual(sorted(self.bledy_formy("sp_z_oo")),
                         ["rejestr.kapital_zakladowy", "rejestr.krs", "rejestr.sad_rejestrowy"])
        self.assertEqual(self.bledy_formy("sp_z_oo", krs="0000455988", sad_rejestrowy="SR", kapital_zakladowy=5000), [])

    def test_sa(self):
        self.assertIn("rejestr.kapital_zakladowy", self.bledy_formy("sa", krs="0000455988", sad_rejestrowy="SR"))

    def test_sp_k_bez_kapitalu(self):
        self.assertEqual(self.bledy_formy("sp_k", krs="0000455988", sad_rejestrowy="SR"), [])

    def test_jdg_wymaga_wlasciciela(self):
        self.assertEqual(self.bledy_formy("jdg"), ["rejestr.wlasciciel"])
        self.assertEqual(self.bledy_formy("jdg", wlasciciel="Jan Testowy"), [])

    def test_spolka_cywilna_wymaga_wspolnikow(self):
        self.assertEqual(self.bledy_formy("spolka_cywilna"), ["rejestr.wspolnicy"])

    def test_nip_i_nazwa_prawna(self):
        d = wczytaj_bimex()
        d.firma["rejestr"]["nip"] = None
        d.firma["firma"]["nazwa_prawna"] = None
        pola = {k.pole for k in kontrole(d).bledy}
        self.assertIn("rejestr.nip", pola)
        self.assertIn("firma.nazwa_prawna", pola)

    def test_linie_stopki(self):
        f = firma_bimex()
        f["rejestr"].update({"forma_prawna": "sp_z_oo", "kapital_zakladowy": 50000})
        linie = " ".join(dane.rejestr_linie(f))
        self.assertIn("KRS\u00a00000455988", linie)
        self.assertIn("NIP\u00a06060092256", linie)
        self.assertIn("Kapitał zakładowy 50\u00a0000\u00a0zł (wpłacony w\u00a0całości)", linie)
        self.assertNotIn("Fabryczna", linie)            # adres stoi raz, w kolumnie kontaktu


class InneKontrole(unittest.TestCase):
    def test_geo_za_malo_miejsc(self):
        d = wczytaj_bimex()
        d.firma["kontakt"]["geo"] = {"lat": dane._float("52.75"), "lng": dane._float("16.98759")}
        self.assertTrue(any(k.pole == "kontakt.geo.lat" for k in kontrole(d).bledy))

    def test_geo_zamienione(self):
        d = wczytaj_bimex()
        d.firma["kontakt"]["geo"] = {"lat": dane._float("16.98759"), "lng": dane._float("52.75360")}
        self.assertTrue(any("poza Polską" in x for x in teksty(kontrole(d), "OSTRZEŻENIE")))

    def test_pola_wymagane_zawsze(self):
        d = wczytaj_bimex()
        d.firma["firma"]["nazwa"] = None
        d.tresc["hero"]["naglowek"] = None
        pola = {k.pole for k in kontrole(d).bledy}
        self.assertIn("firma.nazwa", pola)
        self.assertIn("hero.naglowek", pola)

    def test_nieznany_kroj_i_brak_logo(self):
        d = wczytaj_bimex()
        d.firma["marka"]["font_naglowki"] = "inter"
        d.firma["marka"]["logo"] = "assets/img/nie-ma.png"
        b = teksty(kontrole(d))
        self.assertTrue(any("nie ma kroju „inter”" in x for x in b))
        self.assertIn("nie ma pliku assets/img/nie-ma.png", b)

    def test_zdjecie_spoza_manifestu(self):
        d = wczytaj_bimex()
        d.tresc["hero"]["zdjecie"] = "nie-ma"
        self.assertTrue(any(k.pole == "hero.zdjecie" for k in kontrole(d).bledy))

    def test_osoba_na_zdjeciu_bez_zgody(self):
        d = wczytaj_bimex()
        d.zdjecia_lista[0]["osoby"] = True
        d.zdjecia_lista[0]["zgoda"] = None
        self.assertTrue(any("potrzebna zgoda" in x for x in teksty(kontrole(d))))

    def test_powtorzony_slug(self):
        d = wczytaj_bimex()
        poz = d.tresc["oferta"]["pozycje"]
        poz[1]["slug"] = poz[0]["slug"]
        self.assertTrue(any("powtórzony slug" in x for x in teksty(kontrole(d))))

    def test_ogloszenie_od_po_do(self):
        d = wczytaj_bimex()
        d.tresc["ogloszenie"] = {"tekst": "x", "od": "2026-10-10", "do": "2026-10-01"}
        self.assertTrue(any("„od” jest późniejsza" in x for x in teksty(kontrole(d))))

    def test_przyklad_w_produkcji(self):
        d = wczytaj_bimex()
        r = Raport(produkcja=True)
        dane.kontrole(d, r, True, DZIS_DATA)
        self.assertTrue(any("dane przykładowe" in k.tresc for k in r.bledy))

    def test_bimex_bez_bledow(self):
        self.assertEqual(teksty(kontrole(wczytaj_bimex())), [])


if __name__ == "__main__":
    unittest.main()


class Zabezpieczenia(unittest.TestCase):
    """Wartości trafiające do _headers, _redirects i href: bez nowej linii na końcu i bez javascript:."""

    def test_pattern_nie_przepuszcza_nowej_linii_na_koncu(self):
        f = firma_bimex()
        f["firma"]["adres_roboczy"] = "https://serwis.konto.workers.dev\n"
        self.assertTrue(any(p == "firma.adres_roboczy" for p, _ in bledy_schematu(f)))
        f = firma_bimex()
        f["przekierowania"] = [{"z": "/stara\n/*", "do": "/"}]
        self.assertTrue(any(p.startswith("przekierowania[0]") for p, _ in bledy_schematu(f)))

    def test_znaki_sterujace_w_tekscie(self):
        f = firma_bimex()
        f["firma"]["opis"] = "Beton towarowy"
        self.assertTrue(any("U+2028" in b for _, b in bledy_schematu(f)))
        t = json.loads((BIMEX / "data" / "tresc.json").read_text(encoding="utf-8"))
        t["hero"]["lead"] = "Dwa akapity:\n\nzwykła nowa linia w Markdownie jest w porządku."
        self.assertEqual(bledy_schematu(t, SCHEMAT_TRESCI), [])

    def test_naglowki_odrzucaja_nowa_linie(self):
        from silnik import naglowki
        f = firma_bimex()
        f["firma"]["adres_roboczy"] = "https://x.workers.dev\n/*"
        with self.assertRaises(ValueError):
            naglowki.headers(f, "x")

    def test_przycisk_bez_javascript(self):
        t = json.loads((BIMEX / "data" / "tresc.json").read_text(encoding="utf-8"))
        for href, ok in (("javascript:alert(1)", False), ("JavaScript:x", False), ("//obca.pl", False),
                         ("data:text/html,x", False), ("tel", True), ("/kontakt", True), ("#oferta", True),
                         ("https://firma.pl/a", True), ("mailto:biuro@firma.pl", True), ("tel:+48612345678", True)):
            with self.subTest(href=href):
                t["hero"]["cta_drugie"] = {"tekst": "Test", "href": href}
                bledy = [p for p, _ in bledy_schematu(t, SCHEMAT_TRESCI)]
                self.assertEqual("hero.cta_drugie.href" not in bledy, ok, bledy)
        with self.assertRaises(ValueError):          # druga zapora: przycisk z presetu też nie dostanie javascript:
            dane._cta({"tekst": "x", "href": "javascript:alert(1)"}, {}, set(), [])


class DaneNiepewne(unittest.TestCase):
    """Brief bez domeny, współrzędnych i formy prawnej przechodzi (ostrzeżenia klasy A), zamiast wymuszać zastępniki."""

    def test_bez_geo_trasa_do_adresu(self):
        d = wczytaj_bimex()
        d.firma["kontakt"]["geo"] = None
        r = kontrole(d)
        self.assertNotIn("kontakt.geo", {k.pole for k in r.bledy})
        self.assertTrue(any(k.pole == "kontakt.geo" and k.klasa == "A" for k in r.lista("OSTRZEŻENIE")))
        a = dane.auto(d, DZIS_DATA, set(), [])
        self.assertTrue(a["trasa_url"].startswith("https://www.google.com/maps/dir/?api=1&destination=ul."))
        self.assertIsNone(a["osm_embed"])

    def test_bez_domeny_z_adresem_roboczym(self):
        d = wczytaj_bimex()
        d.firma["firma"]["domena"] = None
        d.firma["firma"]["adres_roboczy"] = "https://bimex.konto.workers.dev"
        r = kontrole(d)
        self.assertNotIn("firma.domena", {k.pole for k in r.bledy})
        self.assertTrue(any(k.pole == "firma.domena" and k.klasa == "A" for k in r.lista("OSTRZEŻENIE")))
        d.firma["firma"]["adres_roboczy"] = None
        self.assertIn("firma.domena", {k.pole for k in kontrole(d).bledy})

    def test_forma_nieznana(self):
        d = wczytaj_bimex()
        d.firma["rejestr"]["forma_prawna"] = "nieznana"
        r = kontrole(d)
        self.assertFalse([k for k in r.bledy if k.pole and k.pole.startswith("rejestr")])
        self.assertTrue(any(k.pole == "rejestr.forma_prawna" and k.klasa == "A" for k in r.lista("OSTRZEŻENIE")))

    def test_brak_emaila_blokuje_tylko_produkcje(self):
        d = wczytaj_bimex()
        d.firma["kontakt"]["email"] = None
        r = kontrole(d)
        self.assertTrue(any(k.pole == "kontakt.email" and k.klasa == "B" for k in r.lista("OSTRZEŻENIE")))

    def test_logo_w_brief(self):
        d = wczytaj_bimex()
        d.firma["marka"]["logo"] = "brief/zdjecia/logo.png"
        self.assertTrue(any(k.pole == "marka.logo" and "assets/img/" in k.tresc for k in kontrole(d).bledy))


class Rejestr(unittest.TestCase):
    def test_psa_i_sa_z_kapitalem_wplaconym(self):
        f = firma_bimex()
        f["rejestr"]["forma_prawna"] = "psa"
        self.assertEqual(bledy_schematu(f), [])
        f["rejestr"].update({"forma_prawna": "sa", "kapital_zakladowy": 100000, "kapital_wplacony": 25000})
        self.assertIn("wpłacony 25 000 zł", " ".join(dane.rejestr_linie(f)))

    def test_jdg_bez_powtorzenia_wlasciciela(self):
        f = firma_bimex()
        f["firma"]["nazwa_prawna"] = "Gabinet Testowy Anna Testowa"
        f["rejestr"].update({"forma_prawna": "jdg", "wlasciciel": "Anna Testowa"})
        self.assertEqual(dane.rejestr_linie(f)[0], "Gabinet Testowy Anna Testowa")

    def test_nazwa_prawna_rowna_nazwie_nie_powtarza_sie(self):
        f = firma_bimex()
        f["firma"]["nazwa_prawna"] = f["firma"]["nazwa"]
        f["rejestr"]["forma_prawna"] = "inna"
        self.assertNotIn(f["firma"]["nazwa"], " ".join(dane.rejestr_linie(f)))

    def test_siedziba_inna_niz_lokal(self):
        f = firma_bimex()
        f["rejestr"]["adres_siedziby"] = {"ulica": "ul. Długa 1", "kod": "60-101", "miasto": "Poznań"}
        self.assertEqual(bledy_schematu(f), [])
        self.assertIn("Siedziba: ul. Długa 1, 60-101 Poznań", " ".join(dane.rejestr_linie(f)))
        f["rejestr"]["adres_siedziby"] = {k: f["kontakt"]["adres"][k] for k in ("ulica", "kod", "miasto")}
        self.assertNotIn("Siedziba", " ".join(dane.rejestr_linie(f)))


class KartaBezCen(unittest.TestCase):
    """Karta z samymi nazwami (ceny tylko w lokalu): jawny stan menu.ceny = "w_lokalu" i bez /menu dla kilku nazw."""

    def restauracja(self):
        from _wspolne import KLIENCI
        d = dane.wczytaj(KLIENCI / "restauracja", KORZEN, Raport())
        for k in d.tresc["menu"]["kategorie"]:
            for p in k["pozycje"]:
                p.update(cena=None, opis=None, alergeny=None)
        d.tresc["menu"].update(pdf=None, uwagi=None)
        return d

    def test_w_lokalu(self):
        from silnik import oferta
        d = self.restauracja()
        r = Raport()
        oferta.kontrole(d, r)
        self.assertTrue(any(k.pole == "menu.ceny" and k.klasa == "A" for k in r.lista("OSTRZEŻENIE")))
        d.tresc["menu"]["ceny"] = "w_lokalu"
        r = Raport()
        oferta.kontrole(d, r)
        self.assertFalse([k for k in r.komunikaty if k.pole == "menu.ceny"])
        self.assertEqual(oferta.auto(d, set(), ["menu"], {})["menu"]["uwagi"], "Ceny podajemy w lokalu.")
        d.tresc["menu"]["kategorie"][0]["pozycje"][0]["cena"] = 12
        r = Raport()
        oferta.kontrole(d, r)
        self.assertTrue(any(k.pole == "menu.ceny" for k in r.bledy))

    def test_menu_bez_podstrony_dla_kilku_nazw(self):
        from silnik import strony
        d = self.restauracja()
        self.assertFalse(strony._menu_podstrona(d))
        d.tresc["menu"]["pdf"] = "assets/img/pliki/karta.pdf"
        self.assertTrue(strony._menu_podstrona(d))
