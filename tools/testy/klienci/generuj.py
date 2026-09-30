#!/usr/bin/env python3
"""Generator klientów testowych (fikstur) w tools/testy/klienci/<branza>/.

To jest źródło prawdy dla fikstur: dane (data/*.json, data/tresc/*.md, data/aktualnosci/*.md), zdjęcia zastępcze,
logo, małe pliki PDF i — przez tools/zdjecia.py — warianty zdjęć, og.jpg i ikony. Wynik się commituje, więc testy
i CI nie potrzebują Pillow. Oryginały zdjęć (brief/zdjecia/) są poza gitem — generator tworzy je od nowa.

  python3 tools/testy/klienci/generuj.py                 wszystko (wymaga Pillow)
  python3 tools/testy/klienci/generuj.py --tylko-dane    tylko JSON i .md (bez Pillow) — np. po zmianie schematu
  python3 tools/testy/klienci/generuj.py --branza gabinet

Wszystkie dane są WYMYŚLONE i wyraźnie testowe („Restauracja Testowa”, „ul. Testowa 1”, domeny .example,
telefony +48 500 000 00x). NIP, REGON i KRS mają poprawne sumy kontrolne, ale nie należą do żadnej firmy
(NIP i REGON zaczynają się od zer — takich numerów urzędy nie nadają). Każdy klient ma "przyklad": true.
Daty są liczone względem DZIS (ten sam dzień ustawia SZABLON_DZIS w testach i w CI), żeby fikstury się nie starzały.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

TUTAJ = Path(__file__).resolve().parent
KORZEN = TUTAJ.parent.parent.parent
sys.path.insert(0, str(KORZEN / "tools"))
sys.path.insert(0, str(TUTAJ.parent))

from _wspolne import DZIS  # noqa: E402  (tools/testy/_wspolne.py — jedna data dla testów, CI i fikstur)

SCHEMAT = "../../../../../tools/schemat"      # z tools/testy/klienci/<branza>/data/
BRANZE = ["restauracja", "producent", "uslugi", "gabinet"]
ZRODLO = "fikstura testowa (tools/testy/klienci/generuj.py) — dane wymyślone"


# ----------------------------------------------------------------------------- numery z sumą kontrolną

def nip(pierwsze9: str) -> str:
    w = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    s = sum(int(pierwsze9[i]) * w[i] for i in range(9)) % 11
    if s == 10:
        raise ValueError(f"NIP {pierwsze9}…: suma 10 — wybierz inne cyfry")
    return pierwsze9 + str(s)


def regon(pierwsze8: str) -> str:
    w = [8, 9, 2, 3, 4, 5, 6, 7]
    s = sum(int(pierwsze8[i]) * w[i] for i in range(8)) % 11
    return pierwsze8 + str(0 if s == 10 else s)


# ----------------------------------------------------------------------------- wspólne bloki

def funkcje(**zmiany) -> dict:
    f = {"hosting": "cloudflare", "formularz": {"tryb": "mailto", "adresat": None, "zgoda_checkbox": False},
         "mapa": "link", "statystyki_cf_token": None, "tytul_tryb": "fraza", "telefon_w_naglowku": None,
         "etykiety_sekcji": False, "animacje": "brak", "myslnik": "polpauza", "boty_ai": "zezwol",
         "hsts_subdomeny": False, "hsts_preload": False, "faq_schema": False, "strona_dostepnosci": False, "rss": False}
    f.update(zmiany)
    return f


def rejestr(**pola) -> dict:
    r = {"forma_prawna": None, "nip": None, "regon": None, "krs": None, "sad_rejestrowy": None,
         "kapital_zakladowy": None, "wlasciciel": None, "wspolnicy": None, "samorzad_zawodowy": None}
    r.update(pola)
    return r


def social(**pola) -> dict:
    s = {"facebook": None, "instagram": None, "google_maps": None, "linkedin": None, "youtube": None, "tiktok": None}
    s.update(pola)
    return s


def tydzien(**dni) -> dict:
    t = {d: [] for d in ("pn", "wt", "sr", "cz", "pt", "sb", "nd")}
    t.update(dni)
    return t


def firma(branza: str, **pola) -> dict:
    f = {
        "$schema": f"{SCHEMAT}/firma.schema.json",
        "$komentarz": ("FIKSTURA TESTOWA — dane wymyślone (tools/testy/klienci/README.md). Nie kopiuj ich do strony "
                       "klienta. Plik generuje tools/testy/klienci/generuj.py — zmiany wprowadzaj tam."),
        "wersja_danych": 1,
        "przyklad": True,
        "branza": branza,
        "typ_schema": None,
    }
    f.update(pola)
    f.setdefault("opinie_zbiorczo", None)
    f.setdefault("zrodla", {"firma": ZRODLO})
    f.setdefault("do_potwierdzenia", [])
    f.setdefault("przekierowania", None)     # moduł publikacji: stare adresy → nowe (_redirects)
    f.setdefault("dostepnosc", None)         # moduł publikacji: dane strony /dostepnosc
    return f


BLOKI = ["ogloszenie", "oferta", "cennik", "menu", "produkty", "realizacje", "przetargi", "proces", "zasady", "o_firmie",
         "zespol", "liczby", "opinie", "certyfikaty", "faq", "galeria", "do_pobrania", "kariera", "wspolpraca",
         "gdzie_kupic"]


def tresc(hero: dict, **bloki) -> dict:
    t = {"$schema": f"{SCHEMAT}/tresc.schema.json",
         "$komentarz": "FIKSTURA TESTOWA — treść wymyślona do sprawdzenia modułów szablonu (generuj.py).",
         "wersja_danych": 1, "hero": hero}
    for b in BLOKI:
        t[b] = bloki.pop(b, None)
    t["kontakt"] = bloki.pop("kontakt", {"naglowek": None, "wstep": None})
    if bloki:
        raise KeyError(f"nieznane bloki: {', '.join(bloki)}")
    return t


def zdjecie(zid: str, co: str, alt: str, podpis=None, osoby=False, punkt=(0.5, 0.5), rozmiar=(1440, 960)) -> dict:
    """Wpis zdjecia.json + parametry generowania (klucz „_gen” usuwany przed zapisem)."""
    return {"id": zid, "zrodlo_plik": f"brief/zdjecia/{zid}.jpg", "alt": alt, "podpis": podpis,
            "zrodlo": "zdjęcie zastępcze wygenerowane przez tools/testy/klienci/generuj.py", "autor": None,
            "zgoda": True if osoby else None, "osoby": osoby, "punkt": list(punkt), "kadr_mobilny": None,
            "_gen": {"co": co, "rozmiar": rozmiar}}


def alt_zastepczy(co: str) -> str:
    return f"Zdjęcie zastępcze: jednolite tło z napisem „zdjęcie testowe: {co}”"


def kariera_pozycja(**p) -> dict:
    """Oferta pracy. Gdy schemat zna pola z gałęzi sekcji „więcej” (opublikowano), generator je dopisuje."""
    if KARIERA_ROZSZERZONA:
        p.setdefault("opublikowano", None)
    else:
        p.pop("opublikowano", None)
    return p


def kariera(**blok) -> dict:
    if KARIERA_ROZSZERZONA:
        blok.setdefault("kontakt", None)
    else:
        blok.pop("kontakt", None)
    return blok


def _schemat_kariery() -> bool:
    s = json.loads((KORZEN / "tools" / "schemat" / "tresc.schema.json").read_text(encoding="utf-8"))
    obiekt = next(o for o in s["properties"]["kariera"]["oneOf"] if o.get("type") == "object")
    return "opublikowano" in obiekt["properties"]["pozycje"]["items"]["properties"]


KARIERA_ROZSZERZONA = _schemat_kariery()


def dni(n: int) -> str:
    """Data DZIS + n dni (RRRR-MM-DD)."""
    import datetime as dt
    return (dt.date.fromisoformat(DZIS) + dt.timedelta(days=n)).isoformat()


# ----------------------------------------------------------------------------- restauracja

def restauracja() -> dict:
    zdj = [
        zdjecie("sala", "sala restauracji", alt_zastepczy("sala restauracji"), punkt=(0.5, 0.45), rozmiar=(1920, 1280)),
        zdjecie("zupa", "zupa dnia", alt_zastepczy("zupa dnia"), podpis="Zupa dnia (zdjęcie testowe)", rozmiar=(1200, 1200)),
        zdjecie("pierogi", "pierogi", alt_zastepczy("pierogi"), podpis="Pierogi ruskie (zdjęcie testowe)"),
        zdjecie("ogrod", "ogródek", alt_zastepczy("ogródek"), podpis="Ogródek latem (zdjęcie testowe)", rozmiar=(1440, 810)),
        zdjecie("bar", "bar", alt_zastepczy("bar"), rozmiar=(960, 1200)),
        zdjecie("kuchnia", "kuchnia", alt_zastepczy("kuchnia"), podpis="Kuchnia (zdjęcie testowe)"),
        zdjecie("deser", "deser", alt_zastepczy("deser"), rozmiar=(1200, 1500)),
        zdjecie("wejscie", "wejście od ulicy", alt_zastepczy("wejście od ulicy"), rozmiar=(1440, 960)),
        zdjecie("szef", "szef kuchni", alt_zastepczy("szef kuchni"), osoby=True, rozmiar=(960, 1200)),
    ]
    f = firma(
        "restauracja",
        firma={"nazwa": "Restauracja Testowa", "nazwa_prawna": "Restauracja Testowa",
               "opis": "Fikcyjna restauracja do testów szablonu: kuchnia polska, obiady w tygodniu i kolacje do późna.",
               "rok_zalozenia": 2015, "domena": "https://restauracja-testowa.example", "adres_roboczy": None},
        kontakt={"telefon": "+48500000001", "email": "stolik@restauracja-testowa.example",
                 "adres": {"ulica": "ul. Testowa 1", "kod": "00-001", "miasto": "Testowo", "wojewodztwo": "mazowieckie",
                           "kraj": "PL"},
                 "geo": {"lat": 52.23014, "lng": 21.01127}, "obszar_dzialania": None,
                 "dzialy": [{"nazwa": "Rezerwacje i przyjęcia", "do_czego": "stoliki powyżej 8 osób, przyjęcia",
                             "telefon": "+48500000011", "email": None, "osoba": None}],
                 "dojazd": "Wejście od ulicy Testowej, parking dla gości na podwórzu (4 miejsca).",
                 "dostepnosc_lokalu": "Wejście bez progu, toaleta dostosowana dla osób na wózku.",
                 "czas_odpowiedzi": None},
        godziny={"nazwa": "Sala",
                 "tydzien": tydzien(wt=[["12:00", "15:00"], ["17:00", "22:00"]],
                                    sr=[["12:00", "15:00"], ["17:00", "22:00"]],
                                    cz=[["12:00", "15:00"], ["17:00", "22:00"]],
                                    pt=[["12:00", "15:00"], ["17:00", "02:00"]],
                                    sb=[["12:00", "02:00"]], nd=[["12:00", "21:00"]]),
                 "dodatkowe": [{"nazwa": "Kuchnia",
                                "tydzien": tydzien(wt=[["12:00", "14:30"], ["17:00", "21:30"]],
                                                   sr=[["12:00", "14:30"], ["17:00", "21:30"]],
                                                   cz=[["12:00", "14:30"], ["17:00", "21:30"]],
                                                   pt=[["12:00", "14:30"], ["17:00", "23:00"]],
                                                   sb=[["12:00", "23:00"]], nd=[["12:00", "20:00"]])}],
                 "wyjatki": [{"data": dni(-47), "godziny": [], "opis": "Wyjątek z przeszłości (test)"},
                             {"data": dni(31), "godziny": [], "opis": "Wszystkich Świętych"},
                             {"data": dni(41), "godziny": [["12:00", "18:00"]], "opis": "Święto Niepodległości"},
                             {"data": dni(84), "godziny": [], "opis": "Wigilia"}],
                 "uwagi": "Ostatnie zamówienia z kuchni przyjmujemy pół godziny przed jej zamknięciem.",
                 "pokazuj_status": True},
        rejestr=rejestr(forma_prawna="spolka_cywilna", nip=nip("000000001"), regon=regon("00000001"),
                        wspolnicy=["Jan Testowy", "Anna Próbna"]),
        marka={"logo": "assets/img/logo.png", "logo_na_ciemnym": None, "logo_szerokosc": 150, "kolor": "#8A2E1F",
               "kolor_zrodlo": ZRODLO, "kolor_dodatkowy": None, "tlo": "cieple", "font_naglowki": "newsreader",
               "font_tekst": "source-serif-4", "promien": 2, "sekcja_ciemna": "stopka"},
        seo={"fraza": "Restauracja testowa", "miasto": "Testowo",
             "opis": "Restauracja Testowa w Testowie (dane fikcyjne): obiady od wtorku do niedzieli, kolacje w piątek "
                     "i sobotę do 2:00, karta i rezerwacje."},
        social=social(facebook="https://www.facebook.example/restauracja-testowa",
                      google_maps="https://mapy.example/restauracja-testowa"),
        opinie_zbiorczo={"zrodlo": "Mapy (test)", "ocena": 4.6, "liczba": 128, "data": dni(-16),
                         "url": "https://mapy.example/restauracja-testowa/opinie"},
        funkcje=funkcje(mapa="po_kliknieciu", formularz={"tryb": "worker", "adresat": None, "zgoda_checkbox": False},
                        rss=True, faq_schema=False),
    )
    t = tresc(
        {"naglowek": "Kuchnia polska w Testowie, kolacje do późna", "lead":
         "Obiady od wtorku do niedzieli, w piątek i sobotę kuchnia do 23:00, bar do 2:00. Dane i zdjęcia są testowe.",
         "zdjecie": "sala", "podpis": "Sala główna (zdjęcie testowe)", "cta_glowne": None, "cta_drugie": None},
        ogloszenie={"tekst": f"Test ogłoszenia: {dni(31)[8:10]}.{dni(31)[5:7]} lokal nieczynny", "od": dni(-6),
                    "do": dni(31)},
        menu={"naglowek": None, "data": dni(-30), "uwagi": "Ceny brutto. Porcje dziecięce za pół ceny (dane testowe).",
              "pdf": "assets/img/pliki/karta-testowa.pdf",
              "kategorie": [
                  {"nazwa": "Zupy", "pozycje": [
                      {"nazwa": "Żurek na zakwasie", "opis": "z jajkiem i białą kiełbasą", "cena": 18, "wege": False,
                       "ostre": False, "alergeny": ["gluten", "jaja", "seler"], "porcja": "350 ml"},
                      {"nazwa": "Pomidorowa", "opis": "z makaronem", "cena": 14.5, "wege": True, "ostre": False,
                       "alergeny": ["gluten", "seler"], "porcja": "350 ml"},
                      {"nazwa": "Gulaszowa", "opis": "pikantna, z papryką", "cena": 21, "wege": False, "ostre": True,
                       "alergeny": ["seler"], "porcja": None}]},
                  {"nazwa": "Dania główne", "pozycje": [
                      {"nazwa": "Pierogi ruskie", "opis": "z cebulką", "cena": 29, "wege": True, "ostre": False,
                       "alergeny": ["gluten", "mleko", "jaja"], "porcja": "10 szt."},
                      {"nazwa": "Schabowy z ziemniakami", "opis": "i kapustą zasmażaną", "cena": 42, "wege": False,
                       "ostre": False, "alergeny": ["gluten", "jaja", "mleko"], "porcja": None},
                      {"nazwa": "Placki ziemniaczane", "opis": "z gulaszem", "cena": {"od": 32, "do": 38},
                       "wege": False, "ostre": True, "alergeny": ["gluten", "jaja"], "porcja": None},
                      {"nazwa": "Sandacz z masłem", "opis": None, "cena": 58, "wege": False, "ostre": False,
                       "alergeny": ["ryby", "mleko"], "porcja": "200 g"}]},
                  {"nazwa": "Desery i napoje", "pozycje": [
                      {"nazwa": "Sernik", "opis": None, "cena": 16, "wege": True, "ostre": False,
                       "alergeny": ["mleko", "jaja", "gluten"], "porcja": None},
                      {"nazwa": "Kompot", "opis": "z sezonowych owoców", "cena": 8, "wege": True, "ostre": False,
                       "alergeny": [], "porcja": "0,3 l"},
                      {"nazwa": "Woda z kranu", "opis": "dzbanek", "cena": 0, "wege": True, "ostre": False,
                       "alergeny": None, "porcja": "1 l"}]}]},
        cennik={"naglowek": "Przyjęcia i catering", "dla": "konsumenci", "data": dni(-30), "uwagi": None, "pdf": None,
                "grupy": [{"nazwa": "Przyjęcia w sali", "pozycje": [
                    {"nazwa": "Menu okolicznościowe", "opis": "zupa, danie główne, deser", "cena": 120,
                     "jednostka": "os.", "czas": None},
                    {"nazwa": "Wynajem sali na wyłączność", "opis": None, "cena": {"od": 800, "do": 1500},
                     "jednostka": None, "czas": "4 h"}]},
                    {"nazwa": "Catering", "pozycje": [
                        {"nazwa": "Obiad w pojemnikach", "opis": "od 10 porcji", "cena": 32, "jednostka": "porcja",
                         "czas": None}]}]},
        galeria={"naglowek": None, "zdjecia": ["zupa", "pierogi", "ogrod", "bar", "kuchnia", "deser", "wejscie"]},
        o_firmie={"naglowek": None, "wstep": None, "tresc": "tresc/o-firmie.md", "zdjecie": "kuchnia",
                  "fakty": [{"nazwa": "Otwarta od", "wartosc": "2015 r."}, {"nazwa": "Miejsca", "wartosc": "48 w sali i 20 w ogródku"}]},
        zespol={"naglowek": None, "wstep": None, "osoby": [
            {"imie": "Jan Testowy", "rola": "szef kuchni, współwłaściciel", "fakt": "gotuje od 2004 r.",
             "zdjecie": "szef", "zgoda": True},
            {"imie": "Anna Próbna", "rola": "sala i rezerwacje, współwłaścicielka", "fakt": None, "zdjecie": None,
             "zgoda": False}]},
        opinie={"naglowek": None,
                "weryfikacja": "Cytujemy opinie z serwisu Mapy (test); nie sprawdzamy, czy autor był naszym gościem.",
                "pozycje": [
                    {"tekst": "Testowa opinia: żurek gorący, obsługa szybka, stolik czekał mimo spóźnienia.",
                     "autor": "Marta", "miejscowosc": "Testowo", "data": dni(-40),
                     "url": "https://mapy.example/restauracja-testowa/opinie/1"},
                    {"tekst": "Testowa opinia: pierogi jak u babci, ceny w porządku.", "autor": "Piotr K.",
                     "miejscowosc": None, "data": dni(-75), "url": "https://mapy.example/restauracja-testowa/opinie/2"}]},
        zasady={"naglowek": "Rezerwacje i płatności", "wstep": None, "pozycje": [
            {"nazwa": "Rezerwacje", "opis": "Telefonicznie, stolik trzymamy 15 minut po umówionej godzinie."},
            {"nazwa": "Płatność", "opis": "Gotówka, karta, BLIK."},
            {"nazwa": "Psy", "opis": "Mile widziane w ogródku."}]},
        faq={"naglowek": None, "pozycje": [
            {"pytanie": "Czy można zamówić na wynos?", "odpowiedz": "Tak, każde danie z karty. Pojemnik **2 zł**."},
            {"pytanie": "Czy jest menu dla dzieci?",
             "odpowiedz": "Porcje dziecięce za pół ceny:\n\n- pomidorowa\n- pierogi\n- placki"},
            {"pytanie": "Gdzie zaparkować?", "odpowiedz": "Na podwórzu (4 miejsca) albo przy [ul. Próbnej](/kontakt)."}]},
        kariera=kariera(naglowek=None, wstep="Szukamy osób do kuchni i na salę (oferty testowe).", kontakt=None,
                        pozycje=[kariera_pozycja(stanowisko="Kucharz / kucharka", miejsce="Testowo",
                                                 wymiar="pełny etat", wynagrodzenie="6500–7500 zł brutto",
                                                 opis="Kuchnia polska, praca od wtorku do soboty.",
                                                 wazne_do=dni(60), opublikowano=dni(-10)),
                                 kariera_pozycja(stanowisko="Kelner / kelnerka (weekendy)", miejsce="Testowo",
                                                 wymiar="umowa zlecenie", wynagrodzenie=None,
                                                 opis="Oferta wygasła — nie może się pokazać.",
                                                 wazne_do=dni(-31), opublikowano=dni(-90))]),
    )
    md = {"tresc/o-firmie.md": O_FIRMIE_RESTAURACJA}
    wpisy = {
        "aktualnosci/2026-09-kolacje-do-polnocy.md": wpis("Kolacje w piątek do 23:00", dni(-21),
                                                          "Od września kuchnia w piątek pracuje godzinę dłużej (wpis testowy).",
                                                          "sala", "Od września w piątki kuchnia wydaje dania do 23:00, a bar jest otwarty do 2:00.\n\n"
                                                                  "To jest **wpis testowy** — sprawdza listę aktualności i stronę wpisu."),
        "aktualnosci/2026-07-ogrodek.md": wpis("Otwieramy ogródek", dni(-91), "Ogródek na 20 miejsc jest otwarty do końca września (wpis testowy).",
                                               None, "Ogródek na podwórzu ma 20 miejsc.\n\n- stoliki z parasolami\n- miska wody dla psów"),
        "aktualnosci/2025-12-wigilia.md": wpis("Wigilia w restauracji", dni(-300), "Grudniowy wpis testowy.", None,
                                               "Wpis sprzed kilku miesięcy — sprawdza sortowanie po dacie."),
    }
    pliki = {"assets/img/pliki/karta-testowa.pdf": ("Karta testowa", 2)}
    return {"firma": f, "tresc": t, "zdjecia": zdj, "md": md | wpisy, "pliki": pliki,
            "logo": ("Restauracja Testowa", "#8A2E1F")}


# ----------------------------------------------------------------------------- producent

def producent() -> dict:
    kat = [("stoly", "Stoły"), ("krzesla", "Krzesła"), ("szafy", "Szafy")]
    zdj = [zdjecie("hala", "hala produkcyjna", alt_zastepczy("hala produkcyjna"), rozmiar=(1920, 1080)),
           zdjecie("salon", "salon firmowy", alt_zastepczy("salon firmowy"), podpis="Salon firmowy (zdjęcie testowe)")]
    produkty = []
    opisy = {"stoly": ["Stół dębowy 160", "Stół rozkładany 120–200", "Stolik kawowy"],
             "krzesla": ["Krzesło tapicerowane", "Krzesło barowe", "Taboret"],
             "szafy": ["Szafa dwudrzwiowa", "Komoda czterodrzwiowa"]}
    n = 0
    for slug_k, nazwy in opisy.items():
        for nazwa in nazwy:
            n += 1
            pid = f"produkt-{n}"
            ze_zdjeciem = n % 3 != 0          # co trzeci produkt bez zdjęcia
            if ze_zdjeciem:
                zdj.append(zdjecie(pid, nazwa.lower(), alt_zastepczy(nazwa.lower()), rozmiar=(1200, 900 if n % 2 else 1200)))
            produkty.append({"slug": f"{slug_k}-{n}", "nazwa": nazwa, "kategoria": slug_k,
                             "opis": f"Produkt testowy nr {n}, wymiary i materiał poglądowe.",
                             "parametry": [{"nazwa": "Materiał", "wartosc": "dąb lity" if n % 2 else "buk"},
                                           {"nazwa": "Wymiary", "wartosc": f"{80 + n * 10} × 60 × 75 cm"}],
                             "zdjecie": pid if ze_zdjeciem else None,
                             "cena": None if n % 4 == 0 else 1200 + n * 150, "jednostka": "szt."})
    produkty.append({"slug": "renowacja", "nazwa": "Renowacja mebli", "kategoria": None,
                     "opis": "Produkt bez kategorii — trafia do grupy „Pozostałe”.", "parametry": None, "zdjecie": None,
                     "cena": {"od": 300}, "jednostka": None})
    f = firma(
        "producent",
        firma={"nazwa": "Meble Próbne", "nazwa_prawna": "Meble Próbne sp. z o.o.",
               "opis": "Fikcyjny producent mebli z drewna do testów szablonu: stoły, krzesła i szafy na zamówienie.",
               "rok_zalozenia": 2009, "domena": "https://meble-probne.example", "adres_roboczy": None},
        kontakt={"telefon": "+48500000002", "email": "biuro@meble-probne.example",
                 "adres": {"ulica": "ul. Testowa 2", "kod": "00-002", "miasto": "Próbnik", "wojewodztwo": "wielkopolskie",
                           "kraj": "PL"},
                 "geo": {"lat": 52.40023, "lng": 16.92541},
                 "obszar_dzialania": ["cała Polska"],
                 "dzialy": [{"nazwa": "Sprzedaż hurtowa", "do_czego": "sklepy i architekci", "telefon": "+48500000012",
                             "email": "hurt@meble-probne.example", "osoba": None},
                            {"nazwa": "Reklamacje", "do_czego": "zgłoszenia i serwis", "telefon": None,
                             "email": "serwis@meble-probne.example", "osoba": None}],
                 "dojazd": None, "dostepnosc_lokalu": None, "czas_odpowiedzi": "odpowiadamy w ciągu 2 dni roboczych"},
        godziny={"nazwa": "Salon firmowy",
                 "tydzien": tydzien(pn=[["09:00", "17:00"]], wt=[["09:00", "17:00"]], sr=[["09:00", "17:00"]],
                                    cz=[["09:00", "17:00"]], pt=[["09:00", "17:00"]], sb=[["09:00", "13:00"]]),
                 "dodatkowe": [{"nazwa": "Hurtownia", "tydzien": tydzien(
                     pn=[["07:00", "15:00"]], wt=[["07:00", "15:00"]], sr=[["07:00", "15:00"]], cz=[["07:00", "15:00"]],
                     pt=[["07:00", "15:00"]])}],
                 "wyjatki": [], "uwagi": None, "pokazuj_status": True},
        rejestr=rejestr(forma_prawna="sp_z_oo", nip=nip("000000002"), regon=regon("00000002"), krs="0000900002",
                        sad_rejestrowy="Sąd Rejonowy Testowo, I Wydział Gospodarczy KRS (dane testowe)",
                        kapital_zakladowy=50000),
        marka={"logo": "assets/img/logo.png", "logo_na_ciemnym": None, "logo_szerokosc": 160, "kolor": "#1E6FD9",
               "kolor_zrodlo": ZRODLO, "kolor_dodatkowy": "#F2A900", "tlo": "chlodne", "font_naglowki": "archivo",
               "font_tekst": "public-sans", "promien": 0, "sekcja_ciemna": "kontakt"},
        seo={"fraza": "Meble z drewna na zamówienie", "miasto": "Próbnik",
             "opis": "Meble Próbne (dane fikcyjne): stoły, krzesła i szafy z drewna dębowego i bukowego, sprzedaż "
                     "hurtowa i salon firmowy w Próbniku."},
        social=social(linkedin="https://linkedin.example/meble-probne", instagram="https://instagram.example/meble-probne"),
        funkcje=funkcje(formularz={"tryb": "mailto", "adresat": "hurt@meble-probne.example", "zgoda_checkbox": True}),
    )
    t = tresc(
        {"naglowek": "Meble z litego drewna z Próbnika", "lead":
         "Stoły, krzesła i szafy robione na zamówienie w hali 1200 m². Sprzedaż hurtowa i salon firmowy (dane testowe).",
         "zdjecie": "hala", "podpis": None, "cta_glowne": None, "cta_drugie": None},
        produkty={"naglowek": None, "wstep": "Ceny brutto za sztukę, bez transportu (dane testowe).",
                  "kategorie": [{"slug": s, "nazwa": n} for s, n in kat], "pozycje": produkty},
        cennik={"naglowek": "Cennik hurtowy", "dla": "firmy", "data": dni(-60), "uwagi": "Rabat od 10 sztuk (test).",
                "pdf": None, "grupy": [{"nazwa": None, "pozycje": [
                    {"nazwa": "Transport na terenie województwa", "opis": None, "cena": 350, "jednostka": None},
                    {"nazwa": "Transport w Polsce", "opis": "za kilometr", "cena": 4.5, "jednostka": "km"},
                    {"nazwa": "Montaż u klienta", "opis": None, "cena": 120, "jednostka": "h"}]}]},
        o_firmie={"naglowek": None, "wstep": "Fikcyjna stolarnia, która sprawdza sekcje producenta.",
                  "tresc": "tresc/o-firmie.md", "zdjecie": "salon",
                  "fakty": [{"nazwa": "Założona", "wartosc": "2009 r."}, {"nazwa": "Drewno", "wartosc": "dąb i buk z Polski"}]},
        liczby={"naglowek": None, "pozycje": [
            {"wartosc": 1200, "jednostka": "m²", "opis": "hali produkcyjnej", "zrodlo": ZRODLO, "data": dni(-30)},
            {"wartosc": 14, "jednostka": "osób", "opis": "w zespole produkcji", "zrodlo": ZRODLO, "data": dni(-30)},
            {"wartosc": 3.5, "jednostka": "tys.", "opis": "mebli rocznie", "zrodlo": ZRODLO, "data": dni(-30)}]},
        proces={"naglowek": "Jak zamówić meble", "wstep": None, "kroki": [
            {"nazwa": "Wybierz model z katalogu", "opis": "Katalog PDF jest w sekcji **Do pobrania**.", "czas": None},
            {"nazwa": "Podaj wymiary i drewno", "opis": None, "czas": "wycena w 2 dni"},
            {"nazwa": "Zadatek i produkcja", "opis": "Zadatek 30 %.", "czas": "4–6 tygodni"},
            {"nazwa": "Odbiór albo dostawa", "opis": None, "czas": None}]},
        zasady={"naglowek": None, "wstep": None, "pozycje": [
            {"nazwa": "Gwarancja", "opis": "24 miesiące na konstrukcję."},
            {"nazwa": "Zadatek", "opis": "30 % przy zamówieniu, reszta przy odbiorze."}]},
        wspolpraca={"naglowek": "Dla sklepów i architektów", "wstep": "Warunki współpracy hurtowej (dane testowe).",
                    "tresc": "tresc/wspolpraca.md",
                    "warunki": ["minimalne zamówienie 5 sztuk", "płatność przelewem 14 dni", "próbki drewna bezpłatnie"]},
        gdzie_kupic={"naglowek": None, "wstep": "Punkty sprzedaży (fikcyjne).", "punkty": [
            {"nazwa": "Salon Testowy", "miasto": "Próbnik", "wojewodztwo": "wielkopolskie", "adres": "ul. Testowa 2",
             "www": None},
            {"nazwa": "Sklep Meblowy Próba", "miasto": "Testowo", "wojewodztwo": "mazowieckie",
             "adres": "ul. Próbna 5, 00-005 Testowo", "www": "https://sklep-proba.example"},
            {"nazwa": "Dom i Drewno (test)", "miasto": "Gdańsk", "wojewodztwo": "pomorskie", "adres": None,
             "www": "https://dom-i-drewno.example"},
            {"nazwa": "Sprzedaż internetowa (test)", "miasto": "internet", "wojewodztwo": None, "adres": None,
             "www": "https://sklep.meble-probne.example"}]},
        do_pobrania={"naglowek": None, "pozycje": [
            {"plik": "assets/img/pliki/katalog-testowy.pdf", "opis": "Katalog mebli (plik testowy)"},
            {"plik": "assets/img/pliki/cennik-testowy.pdf", "opis": "Cennik hurtowy (plik testowy)"}]},
        certyfikaty={"naglowek": None, "wstep": None, "pozycje": [
            {"nazwa": "Certyfikat testowy FSC", "wydawca": "Jednostka Testowa", "numer": "TEST-0001", "rok": 2024,
             "waznosc": dni(700), "plik": "assets/img/pliki/certyfikat-testowy.pdf"},
            {"nazwa": "Certyfikat wygasły (test)", "wydawca": "Jednostka Testowa", "numer": "TEST-0002", "rok": 2020,
             "waznosc": dni(-270), "plik": None}]},
        faq={"naglowek": None, "pozycje": [
            {"pytanie": "Czy robicie meble na wymiar?", "odpowiedz": "Tak, każdy model w dowolnym wymiarze."},
            {"pytanie": "Jak długo trwa realizacja?", "odpowiedz": "Zwykle 4–6 tygodni od wpłaty zadatku."}]},
        kariera=kariera(naglowek=None, wstep=None,
                        kontakt={"osoba": "Kadry (test)", "telefon": "+48500000022", "email": "praca@meble-probne.example"},
                        pozycje=[kariera_pozycja(stanowisko="Stolarz / stolarka", miejsce="Próbnik", wymiar="pełny etat",
                                                 wynagrodzenie="7000–8500 zł brutto", opis="Obróbka drewna litego.",
                                                 wazne_do=None, opublikowano=dni(-5))]),
    )
    md = {"tresc/o-firmie.md": O_FIRMIE_PRODUCENT, "tresc/wspolpraca.md": WSPOLPRACA,
          "aktualnosci/2026-08-nowa-linia.md": wpis("Nowa linia do lakierowania", dni(-40),
                                                    "Uruchomiliśmy drugą kabinę lakierniczą (wpis testowy).", "hala",
                                                    "Druga kabina skraca czas realizacji zamówień o tydzień.")}
    pliki = {"assets/img/pliki/katalog-testowy.pdf": ("Katalog testowy", 3),
             "assets/img/pliki/cennik-testowy.pdf": ("Cennik testowy", 1),
             "assets/img/pliki/certyfikat-testowy.pdf": ("Certyfikat testowy", 1)}
    return {"firma": f, "tresc": t, "zdjecia": zdj, "md": md, "pliki": pliki, "logo": ("Meble Próbne", "#1E6FD9")}


# ----------------------------------------------------------------------------- usługi

def uslugi() -> dict:
    zdj = [zdjecie("warsztat", "warsztat", alt_zastepczy("warsztat"), rozmiar=(1920, 1280)),
           zdjecie("naprawa", "naprawa", alt_zastepczy("naprawa"), rozmiar=(1440, 960)),
           zdjecie("osoba-a", "właścicielka", alt_zastepczy("właścicielka"), osoby=True, rozmiar=(960, 1200)),
           zdjecie("osoba-b", "pracownik", alt_zastepczy("pracownik"), osoby=True, rozmiar=(960, 1200))]
    f = firma(
        "uslugi",
        firma={"nazwa": "Serwis Próbny", "nazwa_prawna": "Serwis Próbny Kowalska i Wspólnik sp.j.",
               "opis": "Fikcyjny serwis rowerowy do testów szablonu: naprawy, przeglądy i dopasowanie roweru.",
               "rok_zalozenia": 2018, "domena": "https://serwis-probny.example", "adres_roboczy": None},
        kontakt={"telefon": "+48500000003", "email": "serwis@serwis-probny.example",
                 "adres": {"ulica": "ul. Testowa 3", "kod": "00-003", "miasto": "Testowo", "wojewodztwo": "mazowieckie",
                           "kraj": "PL"},
                 "geo": {"lat": 52.23518, "lng": 21.00562}, "obszar_dzialania": None, "dzialy": None,
                 "dojazd": None, "dostepnosc_lokalu": None, "czas_odpowiedzi": "oddzwaniamy tego samego dnia"},
        godziny={"nazwa": None,
                 "tydzien": tydzien(pn=[["08:00", "18:00"]], wt=[["08:00", "18:00"]], sr=[["08:00", "18:00"]],
                                    cz=[["08:00", "18:00"]], pt=[["08:00", "18:00"]], sb=[["09:00", "13:00"]]),
                 "dodatkowe": None, "wyjatki": [{"data": dni(10), "godziny": [["08:00", "12:00"]], "opis": "Inwentaryzacja"}],
                 "uwagi": None, "pokazuj_status": True},
        rejestr=rejestr(forma_prawna="sp_j", nip=nip("000000033"), regon=regon("00000003"), krs="0000900003",
                        sad_rejestrowy="Sąd Rejonowy Testowo, II Wydział Gospodarczy KRS (dane testowe)"),
        marka={"logo": "assets/img/logo.png", "logo_na_ciemnym": None, "logo_szerokosc": 140, "kolor": "#2F6B3A",
               "kolor_zrodlo": ZRODLO, "kolor_dodatkowy": None, "tlo": "biale", "font_naglowki": "barlow-condensed",
               "font_tekst": "barlow", "promien": 4, "sekcja_ciemna": "stopka"},
        seo={"fraza": "Serwis rowerowy", "miasto": "Testowo",
             "opis": "Serwis Próbny w Testowie (dane fikcyjne): naprawy i przeglądy rowerów, cennik usług, termin "
                     "zwykle w 2 dni robocze."},
        social=social(google_maps="https://mapy.example/serwis-probny"),
        funkcje=funkcje(formularz={"tryb": "mailto", "adresat": None, "zgoda_checkbox": True}, faq_schema=True,
                        myslnik="pauza"),
    )
    t = tresc(
        {"naglowek": "Serwis rowerowy w Testowie", "lead":
         "Przegląd od 120 zł, większość napraw w 2 dni robocze. Dane i zdjęcia na tej stronie są testowe.",
         "zdjecie": "warsztat", "podpis": None, "cta_glowne": None,
         "cta_drugie": {"tekst": "Zobacz cennik", "href": "/oferta"}},
        oferta={"naglowek": None, "wstep": None, "pozycje": [
            {"slug": "przeglad", "nazwa": "Przegląd roweru", "opis": "Regulacja hamulców i przerzutek, smarowanie.",
             "zakres": ["hamulce", "przerzutki", "łożyska", "koła"], "cena": 120, "jednostka": None, "czas": "1–2 dni",
             "zdjecie": "naprawa", "tresc": "tresc/uslugi/przeglad.md"},
            {"slug": "naprawy", "nazwa": "Naprawy", "opis": "Wymiana części, centrowanie kół.", "zakres": None,
             "cena": {"od": 40}, "jednostka": None, "czas": None, "zdjecie": None, "tresc": None},
            {"slug": "dopasowanie", "nazwa": "Dopasowanie roweru", "opis": "Ustawienie siodła i kierownicy.",
             "zakres": None, "cena": 200, "jednostka": None, "czas": "1 h", "zdjecie": None, "tresc": None},
            {"slug": "przechowanie", "nazwa": "Przechowanie na zimę", "opis": None, "zakres": None,
             "cena": 25, "jednostka": "mies.", "czas": None, "zdjecie": None, "tresc": None}]},
        cennik={"naglowek": None, "dla": "konsumenci", "data": dni(-20), "uwagi": "Ceny brutto (dane testowe).",
                "pdf": None, "grupy": [
                    {"nazwa": "Hamulce", "pozycje": [
                        {"nazwa": "Regulacja hamulca", "opis": None, "cena": 20, "jednostka": None, "czas": "15 min"},
                        {"nazwa": "Odpowietrzenie hydrauliki", "opis": "jedno koło", "cena": 70, "jednostka": None,
                         "czas": "45 min"}]},
                    {"nazwa": "Koła", "pozycje": [
                        {"nazwa": "Centrowanie", "opis": None, "cena": {"od": 30, "do": 60}, "jednostka": None},
                        {"nazwa": "Wymiana dętki", "opis": "bez części", "cena": 15, "jednostka": None},
                        {"nazwa": "Wymiana szprychy", "opis": None, "cena": 12.5, "jednostka": "szt."}]},
                    {"nazwa": "Napęd", "pozycje": [
                        {"nazwa": "Wymiana łańcucha", "opis": None, "cena": 25, "jednostka": None},
                        {"nazwa": "Diagnoza", "opis": None, "cena": 0, "jednostka": None}]}]},
        proces={"naglowek": None, "wstep": None, "kroki": [
            {"nazwa": "Zadzwoń i umów termin", "opis": None, "czas": None},
            {"nazwa": "Zostaw rower", "opis": "Wycena przed naprawą — bez zgody nic nie wymieniamy.", "czas": "wycena w 1 dzień"},
            {"nazwa": "Odbierz", "opis": None, "czas": "zwykle w 2 dni robocze"}]},
        zasady={"naglowek": None, "wstep": None, "pozycje": [
            {"nazwa": "Gwarancja", "opis": "3 miesiące na robociznę."},
            {"nazwa": "Rower nieodebrany", "opis": "Po 30 dniach naliczamy przechowanie 25 zł miesięcznie."}]},
        zespol={"naglowek": None, "wstep": None, "osoby": [
            {"imie": "Ewa Testowa", "rola": "właścicielka, mechanik", "fakt": "serwisuje rowery od 2010 r.",
             "zdjecie": "osoba-a", "zgoda": True},
            {"imie": "Tomasz", "rola": "mechanik", "fakt": None, "zdjecie": "osoba-b", "zgoda": False},
            {"imie": "Kasia", "rola": "przyjęcia i wydania", "fakt": None, "zdjecie": None, "zgoda": False}]},
        opinie={"naglowek": None,
                "weryfikacja": "Cytujemy opinie z serwisu opinie.example (test); nie sprawdzamy, czy autor był klientem.",
                "pozycje": [
                    {"tekst": "Testowa opinia: rower gotowy następnego dnia, cena zgodna z wyceną.", "autor": "Ola",
                     "miejscowosc": "Testowo", "data": dni(-12), "url": "https://opinie.example/serwis-probny/1"},
                    {"tekst": "Testowa opinia bez linku — build ostrzega, że cytatu nie da się sprawdzić.",
                     "autor": "Michał", "miejscowosc": None, "data": None, "url": None}]},
        faq={"naglowek": None, "pozycje": [
            {"pytanie": "Czy trzeba się umawiać?", "odpowiedz": "Na przegląd tak, drobne naprawy od ręki."},
            {"pytanie": "Czy naprawiacie rowery elektryczne?", "odpowiedz": "Tak, poza silnikiem i baterią."}]},
        kariera=None,
    )
    md = {"tresc/uslugi/przeglad.md": PRZEGLAD,
          "aktualnosci/2026-09-sezon.md": wpis("Koniec sezonu — przechowanie", dni(-3),
                                               "Przyjmujemy rowery na zimę (wpis testowy).", None,
                                               "Przechowanie kosztuje 25 zł miesięcznie.")}
    return {"firma": f, "tresc": t, "zdjecia": zdj, "md": md, "pliki": {}, "logo": ("Serwis Próbny", "#2F6B3A")}


# ----------------------------------------------------------------------------- gabinet

def gabinet() -> dict:
    zdj = [zdjecie("gabinet", "gabinet", alt_zastepczy("gabinet"), rozmiar=(1920, 1080)),
           zdjecie("poczekalnia", "poczekalnia", alt_zastepczy("poczekalnia"))]
    osoby = [("lek. Anna Testowa", "specjalistka chorób wewnętrznych, właścicielka"),
             ("lek. Jan Próbny", "pediatra"), ("mgr Ewa Przykład", "fizjoterapeutka"),
             ("Maria Test", "rejestracja")]
    for i, _ in enumerate(osoby, 1):
        zdj.append(zdjecie(f"portret-{i}", f"portret {i}", alt_zastepczy(f"portret {i}"), osoby=True, rozmiar=(960, 1200)))
    f = firma(
        "gabinet",
        firma={"nazwa": "Gabinet Testowy", "nazwa_prawna": "Gabinet Testowy Anna Testowa",
               "opis": "Fikcyjny gabinet lekarski do testów szablonu: interna, pediatria i fizjoterapia w Testowie.",
               "rok_zalozenia": 2012, "domena": "https://gabinet-testowy.example", "adres_roboczy": None},
        kontakt={"telefon": "+48500000004", "email": "rejestracja@gabinet-testowy.example",
                 "adres": {"ulica": "ul. Testowa 4 lok. 2", "kod": "00-004", "miasto": "Testowo",
                           "wojewodztwo": "mazowieckie", "kraj": "PL"},
                 "geo": {"lat": 52.24137, "lng": 21.02219}, "obszar_dzialania": None, "dzialy": None,
                 "dojazd": "Wejście od podwórza, drugie piętro, winda.",
                 "dostepnosc_lokalu": "Winda, toaleta dla osób z niepełnosprawnością.", "czas_odpowiedzi": None},
        godziny={"nazwa": "Gabinet",
                 "tydzien": tydzien(pn=[["08:00", "12:00"], ["15:00", "19:00"]], wt=[["08:00", "14:00"]],
                                    sr=[["08:00", "12:00"], ["15:00", "19:00"]], cz=[["12:00", "20:00"]],
                                    pt=[["08:00", "14:00"]]),
                 "dodatkowe": [{"nazwa": "Rejestracja telefoniczna", "tydzien": tydzien(
                     pn=[["07:30", "19:00"]], wt=[["07:30", "14:00"]], sr=[["07:30", "19:00"]], cz=[["11:00", "20:00"]],
                     pt=[["07:30", "14:00"]])}],
                 "wyjatki": [{"data": dni(13), "godziny": [], "opis": "Szkolenie zespołu"},
                             {"data": dni(84), "godziny": [["08:00", "12:00"]], "opis": "Wigilia"}],
                 "uwagi": "Wizyty domowe po wcześniejszym uzgodnieniu (dane testowe).", "pokazuj_status": True},
        rejestr=rejestr(forma_prawna="jdg", nip=nip("000000004"), regon=regon("00000004"), wlasciciel="Anna Testowa",
                        samorzad_zawodowy="Okręgowa Izba Lekarska w Testowie, nr prawa wykonywania zawodu 0000000 (test)"),
        marka={"logo": "assets/img/logo.png", "logo_na_ciemnym": None, "logo_szerokosc": 130, "kolor": "#7FC8C2",
               "kolor_zrodlo": ZRODLO, "kolor_dodatkowy": None, "tlo": "#FCFCFA", "font_naglowki": "source-serif-4",
               "font_tekst": "public-sans", "promien": 2, "sekcja_ciemna": "brak"},
        seo={"fraza": "Gabinet lekarski", "miasto": "Testowo",
             "opis": "Gabinet Testowy w Testowie (dane fikcyjne): interna, pediatria i fizjoterapia, wizyty prywatne, "
                     "cennik i godziny przyjęć."},
        social=social(google_maps="https://mapy.example/gabinet-testowy"),
        funkcje=funkcje(formularz=None, strona_dostepnosci=True, boty_ai="blokuj_trening"),
        # moduł publikacji: stare adresy (_redirects) i dane strony /dostepnosc
        przekierowania=[{"z": "/cennik.php", "do": "/oferta"}, {"z": "/zespol.html", "do": "/o-firmie"}],
        dostepnosc={"data_oceny": dni(-20), "metoda": "samoocena", "wykonawca": None, "zgodnosc": "czesciowa",
                    "niedostepne": ["Skan cennika w PDF nie ma warstwy tekstowej (dokument testowy)."]},
    )
    t = tresc(
        {"naglowek": "Gabinet lekarski w Testowie", "lead":
         "Interna, pediatria i fizjoterapia. Wizyty prywatne, zwykle w ciągu tygodnia. Dane są testowe.",
         "zdjecie": "gabinet", "podpis": None, "cta_glowne": None, "cta_drugie": None},
        ogloszenie={"tekst": "Test ogłoszenia bez daty początku: szczepienia przeciw grypie od października",
                    "od": None, "do": dni(45)},
        oferta={"naglowek": None, "wstep": None, "pozycje": [
            {"slug": "interna", "nazwa": "Konsultacja internistyczna", "opis": "Wizyta 30 minut.", "zakres": None,
             "cena": 200, "jednostka": None, "czas": "30 min", "zdjecie": None, "tresc": None},
            {"slug": "pediatria", "nazwa": "Wizyta pediatryczna", "opis": None, "zakres": None, "cena": 180,
             "jednostka": None, "czas": None, "zdjecie": None, "tresc": None},
            {"slug": "fizjoterapia", "nazwa": "Fizjoterapia", "opis": "Terapia manualna i ćwiczenia.", "zakres": None,
             "cena": None, "jednostka": None, "czas": None, "zdjecie": None, "tresc": None}]},
        zespol={"naglowek": None, "wstep": None, "osoby": [
            {"imie": imie, "rola": rola, "fakt": None, "zdjecie": f"portret-{i}", "zgoda": True}
            for i, (imie, rola) in enumerate(osoby, 1)]},
        cennik={"naglowek": None, "dla": "konsumenci", "data": dni(-100), "uwagi": None,
                "pdf": "assets/img/pliki/cennik-gabinetu.pdf", "grupy": [
                    {"nazwa": "Wizyty", "pozycje": [
                        {"nazwa": "Konsultacja internistyczna", "opis": None, "cena": 200, "jednostka": None, "czas": "30 min"},
                        {"nazwa": "Wizyta pediatryczna", "opis": None, "cena": 180, "jednostka": None, "czas": "20 min"},
                        {"nazwa": "Wizyta domowa", "opis": "w granicach Testowa", "cena": 350, "jednostka": None,
                         "czas": None}]},
                    {"nazwa": "Fizjoterapia", "pozycje": [
                        {"nazwa": "Terapia manualna", "opis": None, "cena": 180, "jednostka": None, "czas": "50 min"},
                        {"nazwa": "Pakiet 5 wizyt", "opis": None, "cena": 800, "jednostka": None, "czas": None}]}]},
        zasady={"naglowek": "Wizyty i odwołania", "wstep": None, "pozycje": [
            {"nazwa": "Odwołanie wizyty", "opis": "Najpóźniej 24 godziny wcześniej, telefonicznie."},
            {"nazwa": "Płatność", "opis": "Gotówka lub karta po wizycie."}]},
        faq={"naglowek": None, "pozycje": [
            {"pytanie": "Czy przyjmujecie na NFZ?", "odpowiedz": "Nie, tylko wizyty prywatne (dane testowe)."},
            {"pytanie": "Czy potrzebne jest skierowanie?", "odpowiedz": "Nie."}]},
        certyfikaty={"naglowek": None, "wstep": None, "pozycje": [
            {"nazwa": "Certyfikat jakości (test)", "wydawca": "Jednostka Testowa", "numer": None, "rok": 2023,
             "waznosc": None, "plik": None}]},
    )
    md = {"aktualnosci/2026-09-szczepienia.md": wpis("Szczepienia przeciw grypie", dni(-2),
                                                     "Zapisy na szczepienia od października (wpis testowy).",
                                                     "poczekalnia", "Zapisy telefonicznie w godzinach rejestracji.")}
    pliki = {"assets/img/pliki/cennik-gabinetu.pdf": ("Cennik gabinetu (test)", 1)}
    return {"firma": f, "tresc": t, "zdjecia": zdj, "md": md, "pliki": pliki, "logo": ("Gabinet Testowy", "#2A6F6A")}


# ----------------------------------------------------------------------------- teksty .md

def wpis(tytul: str, data: str, opis: str, zdj: str | None, tresc: str) -> str:
    return (f"---\ntytul: {tytul}\ndata: {data}\n" + (f"zdjecie: {zdj}\n" if zdj else "") + f"opis: {opis}\n---\n{tresc}\n")


O_FIRMIE_RESTAURACJA = """Restauracja Testowa nie istnieje. To fikcyjny lokal, na którym sprawdzamy szablon strony: tekst ma
ponad 250 słów, więc strona główna pokazuje tylko pierwszy akapit, a całość trafia na podstronę „O nas”.

## Kuchnia

Gotujemy dania kuchni polskiej z produktów od okolicznych dostawców. Karta zmienia się dwa razy w roku, a zupa dnia
codziennie. W piątek i sobotę kuchnia pracuje do 23:00, bar do 2:00 w nocy — to przypadek godzin po północy, który
szablon musi pokazać poprawnie w tabeli, w statusie „Otwarte” i w danych strukturalnych.

## Sala i ogródek

Sala ma 48 miejsc, ogródek od maja do września 20 miejsc. Przyjęcia do 40 osób przyjmujemy w dni, w które restauracja
jest zamknięta, czyli w poniedziałki. W tekście stoją liczby z jednostkami (48 m², 5 km, 12 zł) i zakresy godzin
12:00 - 15:00, żeby sprawdzić polską typografię: twarde spacje po liczbach i półpauzę w zakresach.

- wejście bez progu
- krzesełka dla dzieci
- miska wody dla psów w ogródku

## Po co ten tekst

Próg podstrony „O nas” to 250 słów. Tekst krótszy zmieściłby się na stronie głównej i podstrona by nie powstała —
wtedy test nie sprawdziłby linku „Cały tekst o firmie” ani okruszków. Dlatego piszemy jeszcze kilka zdań o niczym
konkretnym: o tym, że w poniedziałek sprzątamy, we wtorek przyjmujemy dostawy, a w środę testujemy nowe dania.
Każde zdanie jest wymyślone, a nazwy, adresy i numery na tej stronie należą do fikstury testowej, nie do prawdziwej
firmy. Link do [strony kontaktowej](/kontakt) sprawdza linki względne w Markdownie, a
[ten link](javascript:alert(1)) musi zniknąć (zostaje sam tekst). Pogrubienie **działa**, kursywa *też*.
"""

O_FIRMIE_PRODUCENT = """Meble Próbne to fikcyjna stolarnia. Robimy stoły, krzesła i szafy z drewna dębowego i bukowego
w hali w Próbniku.

Każdy mebel powstaje na zamówienie. Wymiary, drewno i wykończenie ustalamy z klientem przed wpłatą zadatku.
"""

WSPOLPRACA = """Sklepom meblowym i pracowniom architektonicznym dajemy stałe rabaty i próbki drewna.

## Jak zacząć

1. Wyślij nazwę firmy i NIP na adres hurtowy.
2. Dostaniesz cennik hurtowy i dostęp do zdjęć produktów.
3. Pierwsze zamówienie realizujemy po przedpłacie.
"""

PRZEGLAD = """Przegląd roweru w Serwisie Próbnym to fikcyjna usługa, która sprawdza podstronę usługi: plik ma ponad
150 słów, pozycja ma zdjęcie, cenę, zakres i czas, więc powstaje strona /oferta/przeglad z własnym obrazkiem
podglądu linku.

## Co sprawdzamy

- hamulce: klocki, linki, pancerze i odpowietrzenie hydrauliki
- przerzutki: regulacja, wymiana linek, stan kasety i łańcucha
- koła: centrowanie, naprężenie szprych, łożyska piast
- stery i suport: luzy, smarowanie, dokręcenie momentem

## Ile to trwa

Rower zostawiony rano odbierasz zwykle następnego dnia po południu. Jeśli potrzebne są części, dzwonimy z wyceną
i czekamy na zgodę — bez niej nic nie wymieniamy. Części na miejscu to najczęściej klocki, linki, dętki i łańcuchy;
inne zamawiamy u hurtowni, dostawa trwa 1–3 dni robocze.

## Cena

Przegląd kosztuje 120 zł brutto i obejmuje robociznę. Części płaci się osobno według cennika. Mycie roweru przed
przeglądem jest w cenie. Tekst jest wymyślony na potrzeby testu — nie opisuje prawdziwego serwisu, a ceny są
poglądowe. Kilka dodatkowych zdań sprawia, że plik na pewno przekracza próg 150 słów także po zmianie liczenia.
"""


# ----------------------------------------------------------------------------- pliki binarne (Pillow tylko tutaj)

TONY = ["#B8B2A7", "#A9B4B8", "#C2B9A3", "#9FA89A", "#B5A9A9", "#AEB3A4", "#B9AFA0", "#A7AFB9"]


def _font(rozmiar: int, pogrubiony: bool = False):
    from PIL import ImageFont
    for nazwa in ("DejaVuSans-Bold.ttf" if pogrubiony else "DejaVuSans.ttf",):
        for katalog in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/Library/Fonts"):
            p = Path(katalog) / nazwa
            if p.is_file():
                return ImageFont.truetype(str(p), rozmiar)
    try:
        return ImageFont.load_default(rozmiar)
    except TypeError:
        return ImageFont.load_default()


def zdjecie_zastepcze(cel: Path, co: str, rozmiar: tuple[int, int], nr: int) -> None:
    """Jednolity, przygaszony ton, cienka ramka i mały napis „zdjęcie testowe: <co>” — widać, że to nie jest zdjęcie."""
    from PIL import Image, ImageDraw
    w, h = rozmiar
    ton = TONY[nr % len(TONY)]
    img = Image.new("RGB", (w, h), ton)
    d = ImageDraw.Draw(img)
    margines = max(12, w // 60)
    ciemny = tuple(max(0, int(ton[i:i + 2], 16) - 70) for i in (1, 3, 5))
    d.rectangle([margines, margines, w - margines - 1, h - margines - 1], outline=ciemny, width=2)
    d.line([margines, margines, w - margines - 1, h - margines - 1], fill=ciemny, width=1)
    d.line([margines, h - margines - 1, w - margines - 1, margines], fill=ciemny, width=1)
    font = _font(max(16, w // 42))
    tekst = f"zdjęcie testowe: {co}  ·  {w}×{h}"
    x0, y0, x1, y1 = d.textbbox((0, 0), tekst, font=font)
    px, py = margines * 2, h - margines * 2 - (y1 - y0)
    d.rectangle([px - 8, py - 6, px + (x1 - x0) + 8, py + (y1 - y0) + 10], fill=ton)
    d.text((px, py - y0), tekst, fill=ciemny, font=font)
    cel.parent.mkdir(parents=True, exist_ok=True)
    img.save(cel, "JPEG", quality=85)


def logo(cel: Path, nazwa: str, kolor: str) -> None:
    """Logo tekstowe (PNG z przezroczystością, 1200 px szerokości — ≥ 512 px, jak wymaga KONTRAKT §4.1)."""
    from PIL import Image, ImageDraw
    font = _font(150, pogrubiony=True)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    x0, y0, x1, y1 = tmp.textbbox((0, 0), nazwa, font=font)
    w, h = x1 - x0 + 80, y1 - y0 + 80
    img = Image.new("RGBA", (max(w, 1200), h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 24, h - 1], fill=kolor)
    d.text((56, 40 - y0), nazwa, fill=kolor, font=font)
    img = img.crop(img.getbbox())
    if img.width < 1200:
        img = img.resize((1200, round(img.height * 1200 / img.width)))
    cel.parent.mkdir(parents=True, exist_ok=True)
    img.save(cel, optimize=True)


def pdf(cel: Path, tytul: str, stron: int) -> None:
    """Minimalny, poprawny PDF (bez bibliotek): `stron` stron A4 z jednym wierszem tekstu (Helvetica, bez polskich znaków)."""
    tekst = (tytul.translate(str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")) + " - plik testowy")
    obiekty = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    strony = []
    for i in range(stron):
        tresc = f"BT /F1 18 Tf 72 770 Td ({tekst}, strona {i + 1}) Tj ET".encode("latin-1")
        obiekty.append(f"<< /Length {len(tresc)} >>\nstream\n{tresc.decode('latin-1')}\nendstream")
        nr_tresci = len(obiekty)
        obiekty.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {nr_tresci} 0 R "
                       "/Resources << /Font << /F1 3 0 R >> >> >>")
        strony.append(len(obiekty))
    obiekty[1] = f"<< /Type /Pages /Kids [{' '.join(f'{n} 0 R' for n in strony)}] /Count {stron} >>"
    wynik = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    przesuniecia = []
    for i, o in enumerate(obiekty, 1):
        przesuniecia.append(len(wynik))
        wynik += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(wynik)
    wynik += f"xref\n0 {len(obiekty) + 1}\n0000000000 65535 f \n".encode()
    for p in przesuniecia:
        wynik += f"{p:010d} 00000 n \n".encode()
    wynik += f"trailer\n<< /Size {len(obiekty) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    cel.parent.mkdir(parents=True, exist_ok=True)
    cel.write_bytes(bytes(wynik))


# ----------------------------------------------------------------------------- zapis

def zapisz_json(plik: Path, obiekt) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(json.dumps(obiekt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generuj(branza: str, tylko_dane: bool) -> None:
    k = {"restauracja": restauracja, "producent": producent, "uslugi": uslugi, "gabinet": gabinet}[branza]()
    cel = TUTAJ / branza
    dane = cel / "data"
    if dane.exists():
        shutil.rmtree(dane)          # tylko dane — assets/ zostaje przy --tylko-dane
    zdjecia = [{x: y for x, y in z.items() if x != "_gen"} for z in k["zdjecia"]]
    zapisz_json(dane / "firma.json", k["firma"])
    zapisz_json(dane / "tresc.json", k["tresc"])
    zapisz_json(dane / "zdjecia.json", {"$schema": f"{SCHEMAT}/zdjecia.schema.json", "wersja_danych": 1,
                                        "zdjecia": zdjecia})
    (dane / "aktualnosci").mkdir(parents=True, exist_ok=True)
    for sciezka, tekst in k["md"].items():
        p = dane / sciezka
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(tekst, encoding="utf-8")
    print(f"{branza}: dane zapisane w {dane.relative_to(KORZEN)}")
    if tylko_dane:
        return
    for katalog in (cel / "assets", cel / "brief"):
        if katalog.exists():
            shutil.rmtree(katalog)
    for i, z in enumerate(k["zdjecia"]):
        zdjecie_zastepcze(cel / z["zrodlo_plik"], z["_gen"]["co"], z["_gen"]["rozmiar"], i)
    logo(cel / "assets" / "img" / "logo.png", *k["logo"])
    for sciezka, (tytul, stron) in k["pliki"].items():
        pdf(cel / sciezka, tytul, stron)
    subprocess.run([sys.executable, str(KORZEN / "tools" / "zdjecia.py"), "--klient", str(cel), "--nadpisz"], check=True,
                   stdout=subprocess.DEVNULL)
    print(f"{branza}: zdjęcia, logo, ikony i pliki PDF w {(cel / 'assets').relative_to(KORZEN)}")


def main() -> int:
    p = argparse.ArgumentParser(description="Generuje klientów testowych w tools/testy/klienci/.")
    p.add_argument("--branza", choices=BRANZE, action="append", help="tylko ta branża (można powtórzyć)")
    p.add_argument("--tylko-dane", action="store_true", help="tylko data/ (bez Pillow i bez zdjęć)")
    a = p.parse_args()
    for b in a.branza or BRANZE:
        generuj(b, a.tylko_dane)
    return 0


if __name__ == "__main__":
    sys.exit(main())
