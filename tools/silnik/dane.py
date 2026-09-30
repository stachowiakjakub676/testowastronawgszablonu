"""Dane klienta: wczytanie data/*, walidacja schematem, kontrole semantyczne i kontekst `auto` (KONTRAKT §4, §9.1).

Ścieżki w komunikatach i w presetach: „tresc.…” → data/tresc.json, „zdjecia.…” → data/zdjecia.json,
wszystko inne → data/firma.json (np. „kontakt.telefon”, „godziny”).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from . import WERSJA_DANYCH
from . import typografia as typo
from .schemat import waliduj
from .strony import html_id
from .szablony import BRAK, Markup, pobierz, prawda

DNI = ["pn", "wt", "sr", "cz", "pt", "sb", "nd"]
DNI_NAZWY = {"pn": "poniedziałek", "wt": "wtorek", "sr": "środa", "cz": "czwartek", "pt": "piątek", "sb": "sobota",
             "nd": "niedziela"}
DNI_KROTKIE = {"pn": "pn.", "wt": "wt.", "sr": "śr.", "cz": "czw.", "pt": "pt.", "sb": "sob.", "nd": "niedz."}
DNI_SCHEMA = {"pn": "Monday", "wt": "Tuesday", "sr": "Wednesday", "cz": "Thursday", "pt": "Friday", "sb": "Saturday",
              "nd": "Sunday"}


class Liczba(float):
    """Liczba z JSON-a, która pamięta zapis źródłowy (np. „52.75360” — potrzebne do kontroli 5 miejsc po przecinku)."""
    tekst: str = ""


def _float(s: str) -> float:
    v = Liczba(s)
    v.tekst = s
    return v


@dataclass
class Dane:
    klient: Path
    korzen: Path
    firma: dict
    tresc: dict
    zdjecia_lista: list
    preset: dict
    fonty: dict
    aktualnosci: list = field(default_factory=list)

    @property
    def zdjecia(self) -> dict:
        return {z["id"]: z for z in self.zdjecia_lista}

    def pole(self, sciezka: str):
        """Wartość wg konwencji ścieżek presetu („tresc.x” / „zdjecia.x” / pole firma.json)."""
        glowa, _, ogon = sciezka.partition(".")
        if glowa == "tresc":
            return pobierz(self.tresc, ogon) if ogon else self.tresc
        if glowa == "zdjecia":
            return pobierz(self.zdjecia, ogon) if ogon else self.zdjecia
        return pobierz(self.firma, sciezka)


# ----------------------------------------------------------------------------- wczytanie

def wczytaj_json(plik: Path, raport, opis: str):
    if not plik.exists():
        raport.blad(f"brak pliku {opis}", plik=opis,
                    naprawa="utwórz szkielet danych: python3 tools/start.py --branza <restauracja|budowlana|producent|uslugi|gabinet>")
        return None
    try:
        return json.loads(plik.read_text(encoding="utf-8"), parse_float=_float)
    except json.JSONDecodeError as e:
        raport.blad(f"niepoprawny JSON: {e.msg} (wiersz {e.lineno}, kolumna {e.colno})", plik=opis,
                    naprawa="sprawdź przecinki i cudzysłowy w tym miejscu")
        return None


def wczytaj(klient: Path, korzen: Path, raport) -> Dane | None:
    data = klient / "data"
    firma = wczytaj_json(data / "firma.json", raport, "data/firma.json")
    tresc = wczytaj_json(data / "tresc.json", raport, "data/tresc.json")
    zdjecia = wczytaj_json(data / "zdjecia.json", raport, "data/zdjecia.json")
    if firma is None or tresc is None or zdjecia is None:
        return None
    ok = True
    for nazwa, dane in (("firma", firma), ("tresc", tresc), ("zdjecia", zdjecia)):
        wersja = dane.get("wersja_danych")
        if wersja != WERSJA_DANYCH:
            raport.blad(f"wersja_danych = {wersja!r}, silnik obsługuje {WERSJA_DANYCH}", plik=f"data/{nazwa}.json",
                        naprawa="zaktualizuj dane (tools/migruj.py) albo wpisz \"wersja_danych\": 1")
            ok = False
            continue
        schemat = json.loads((korzen / "tools" / "schemat" / f"{nazwa}.schema.json").read_text(encoding="utf-8"))
        for sciezka, tresc_bledu in waliduj(dane, schemat):
            raport.blad(tresc_bledu, plik=f"data/{nazwa}.json", pole=sciezka)
            ok = False
    if not ok:
        return None
    plik_presetu = korzen / "tools" / "presety" / f"{firma['branza']}.json"
    preset = json.loads(plik_presetu.read_text(encoding="utf-8"))
    fonty = json.loads((korzen / "assets" / "fonts" / "fonty.json").read_text(encoding="utf-8"))
    d = Dane(klient, korzen, firma, tresc, zdjecia["zdjecia"], preset, fonty)
    d.aktualnosci = wczytaj_aktualnosci(klient, raport)
    return d


POLA_WPISU = {"tytul", "data", "zdjecie", "opis"}


def wczytaj_aktualnosci(klient: Path, raport) -> list[dict]:
    wpisy = []
    katalog = klient / "data" / "aktualnosci"
    if not katalog.is_dir():
        return wpisy
    for plik in sorted(katalog.glob("*.md")):
        opis = f"data/aktualnosci/{plik.name}"
        naglowek, tresc = typo.front_matter(plik.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[a-z0-9-]+", plik.stem):
            raport.blad("nazwa pliku = adres wpisu: tylko małe litery, cyfry i myślniki", plik=opis)
            continue
        for k in sorted(set(naglowek) - POLA_WPISU):     # literówka w nagłówku („zdjęcie”) nie przechodzi po cichu
            raport.blad(f"nieznane pole „{k}” w nagłówku wpisu (dostępne: {', '.join(sorted(POLA_WPISU))})", plik=opis)
        for k in ("tytul", "data", "opis"):
            if not naglowek.get(k):
                raport.blad(f"brak pola „{k}” w nagłówku wpisu", plik=opis, naprawa="nagłówek: ---\\ntytul: …\\ndata: RRRR-MM-DD\\nopis: …\\n---")
        try:
            data = typo.na_date(naglowek.get("data"))
        except ValueError as e:
            raport.blad(str(e), plik=opis, pole="data")
            continue
        wpisy.append({"slug": plik.stem, "tytul": naglowek.get("tytul"), "data": data.isoformat() if data else None,
                      "opis": naglowek.get("opis"), "zdjecie": naglowek.get("zdjecie"), "tresc": tresc,
                      "sciezka": f"/aktualnosci/{plik.stem}"})
    wpisy.sort(key=lambda w: (w["data"] or "", w["slug"]), reverse=True)
    return wpisy


# ----------------------------------------------------------------------------- kontrole semantyczne

RE_POZOSTALOSCI = re.compile(r"\{\{|\{%|\{#|\[UZUPEŁNIJ|\bTODO\b|\bLorem\b|\bXXX\b")
# notatki, które nie trafiają na stronę
POLA_NOTATEK = {"zrodla", "do_potwierdzenia", "zrodlo", "zrodlo_opis", "kolor_zrodlo", "zrodlo_plik"}


def _teksty(o, sciezka: str = ""):
    """(ścieżka, tekst) każdego napisu w danych, bez kluczy „$…” i notatek."""
    if isinstance(o, str):
        yield sciezka, o
    elif isinstance(o, dict):
        for k, v in o.items():
            if not k.startswith("$") and k not in POLA_NOTATEK:
                yield from _teksty(v, f"{sciezka}.{k}" if sciezka else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _teksty(v, f"{sciezka}[{i}]")


def _data(v, raport, plik: str, pole: str, zapas: dt.date) -> dt.date:
    """Data z danych; nieistniejąca (2026-02-30) → błąd danych z nazwą pola zamiast wyjątku."""
    try:
        return typo.na_date(v) or zapas
    except ValueError as e:
        raport.blad(str(e), plik=plik, pole=pole)
        return zapas

WYMAGANE = [
    ("firma.nazwa", "krótka nazwa firmy (logo-tekst, tytuł strony)"),
    ("firma.opis", "jedno zdanie: co firma robi i gdzie (≤ 160 zn.)"),
    ("kontakt.telefon", "główny telefon w formacie E.164, np. \"+48672683408\""),
    ("kontakt.adres.ulica", "ulica i numer, np. \"ul. Fabryczna 7\""),
    ("kontakt.adres.kod", "kod pocztowy NN-NNN"),
    ("kontakt.adres.miasto", "miejscowość"),
    ("rejestr.forma_prawna", "forma prawna: jdg | spolka_cywilna | sp_j | sp_k | sp_z_oo | sa | psa | inna | nieznana "
                             "(nieznana = jeszcze nie sprawdzona w KRS/CEIDG — stopka bez danych rejestrowych)"),
    ("marka.kolor", "kolor z logo albo szyldu, #RRGGBB"),
    ("marka.font_naglowki", "krój nagłówków — id z assets/fonts/fonty.json"),
    ("marka.font_tekst", "krój tekstu — id z assets/fonts/fonty.json"),
    ("seo.fraza", "co firma robi, 2–5 słów, np. \"Roboty drogowe\" — do tytułu karty"),
    ("seo.miasto", "miasto do tytułu karty"),
    ("tresc.hero.naglowek", "nagłówek h1 strony głównej: co + gdzie, ≤ 70 zn."),
    ("tresc.hero.lead", "jedno–dwa zdania konkretu pod nagłówkiem"),
]

FORMY = {
    "sp_z_oo": ("spółka z o.o. (art. 206 KSH)", ["nazwa_prawna", "krs", "sad_rejestrowy", "nip", "kapital_zakladowy"]),
    "sa": ("spółka akcyjna (art. 374 KSH)", ["nazwa_prawna", "krs", "sad_rejestrowy", "nip", "kapital_zakladowy",
                                             "kapital_wplacony"]),
    "psa": ("prosta spółka akcyjna (art. 300² KSH)", ["nazwa_prawna", "krs", "sad_rejestrowy", "nip"]),
    "sp_k": ("spółka komandytowa", ["nazwa_prawna", "krs", "sad_rejestrowy", "nip"]),
    "sp_j": ("spółka jawna", ["nazwa_prawna", "krs", "sad_rejestrowy", "nip"]),
    "jdg": ("jednoosobowa działalność (art. 20 ust. 3 Prawa przedsiębiorców)", ["nazwa_prawna", "wlasciciel", "nip"]),
    "spolka_cywilna": ("spółka cywilna", ["nazwa_prawna", "wspolnicy", "nip"]),
    "inna": ("inna forma", ["nazwa_prawna"]),
    "nieznana": ("forma prawna nieznana", []),
}


def nip_ok(n: str) -> bool:
    w = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    s = sum(int(n[i]) * w[i] for i in range(9)) % 11
    return s != 10 and s == int(n[9])


def regon_ok(r: str) -> bool:
    if len(r) == 9:
        w = [8, 9, 2, 3, 4, 5, 6, 7]
    elif len(r) == 14:
        if not regon_ok(r[:9]):
            return False
        w = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
    else:
        return False
    s = sum(int(r[i]) * w[i] for i in range(len(w))) % 11
    return (0 if s == 10 else s) == int(r[-1])


def _minuty(g: str) -> int:
    h, m = g.split(":")
    return int(h) * 60 + int(m)


def _sprawdz_tydzien(tydzien: dict, raport, pole: str):
    """Zerowe przedziały, zamknięcie po 6:00 następnego dnia i nakładanie się przedziałów — także między dniami
    (piątek 20:00–04:00 i sobota 02:00–10:00) i z niedzieli na poniedziałek."""
    tydzien_min = 7 * 1440
    zakresy = []                               # (początek, koniec) w minutach od poniedziałku 0:00, dzień
    for i, d in enumerate(DNI):
        for od, do in tydzien.get(d) or []:
            a, b = _minuty(od), _minuty(do)
            if a == b:
                raport.blad(f"przedział {od}–{do} ma zerową długość (całą dobę zapisz jako 00:00–24:00)",
                            plik="data/firma.json", pole=f"{pole}.{d}")
                continue
            if 0 < b < a and b > 6 * 60:
                raport.ostrzezenie(f"przedział {od}–{do} kończy się po północy później niż o 6:00 — sprawdź, czy to nie pomyłka",
                                   plik="data/firma.json", pole=f"{pole}.{d}")
            koniec = b if b > a else b + 1440
            zakresy.append((i * 1440 + a, i * 1440 + koniec, d))
    zakresy.sort()
    zgloszone = set()
    for j, (a1, b1, d1) in enumerate(zakresy):
        for a2, b2, d2 in zakresy[j + 1:] + [(a + tydzien_min, b + tydzien_min, d) for a, b, d in zakresy[:j]]:
            if a2 < b1 and (d1, d2) not in zgloszone:
                zgloszone.add((d1, d2))
                dni = DNI_NAZWY[d1] if d1 == d2 else f"{DNI_NAZWY[d1]} i {DNI_NAZWY[d2]}"
                raport.blad(f"przedziały godzin nachodzą na siebie: {dni}", plik="data/firma.json", pole=f"{pole}.{d1}",
                            naprawa="godziny po północy należą do dnia otwarcia — nie powtarzaj ich w następnym dniu")


GEO_MIN_MIEJSC = 4   # 52.75360 zapisane przez json.dump, jq, Prettier albo Decap to 52.7536 — końcowe zera znikają


def _miejsca_po_przecinku(v) -> int:
    tekst = getattr(v, "tekst", None) or repr(v)
    return len(tekst.split(".")[1]) if "." in tekst else 0


def _uzyte_zdjecia(tresc: dict) -> list[tuple[str, str]]:
    """(ścieżka, id) wszystkich pól „zdjecie”/„zdjecia” w tresc.json."""
    wynik = []

    def idz(o, sciezka):
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{sciezka}.{k}" if sciezka else k
                if k == "zdjecie" and isinstance(v, str):
                    wynik.append((p, v))
                elif k == "zdjecia" and isinstance(v, list):
                    wynik.extend((f"{p}[{i}]", x) for i, x in enumerate(v) if isinstance(x, str))
                else:
                    idz(v, p)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                idz(v, f"{sciezka}[{i}]")
    idz(tresc, "")
    return wynik


def kontrole(d: Dane, raport, produkcja: bool, dzis: dt.date) -> None:
    f, t = d.firma, d.tresc
    plik_dla = lambda p: "data/tresc.json" if p.startswith("tresc.") else "data/firma.json"
    # 1. pola wymagane zawsze
    for sciezka, opis in WYMAGANE:
        if not prawda(d.pole(sciezka)):
            raport.blad(f"brak danych: {opis}", plik=plik_dla(sciezka), pole=sciezka.removeprefix("tresc."))
    # 2. wymagane i zalecane presetu
    for w in d.preset.get("wymagane", []):
        if not any(prawda(d.pole(o)) for o in w.split("|")):
            raport.blad(f"branża „{f['branza']}” wymaga: {' albo '.join(w.split('|'))}", plik=plik_dla(w),
                        pole=w.replace("tresc.", ""), naprawa="uzupełnij dane albo zmień branżę (tools/presety/)")
    for w in d.preset.get("zalecane", []):
        if not any(prawda(d.pole(o)) for o in w.split("|")):
            raport.ostrzezenie(f"zalecane dla branży „{f['branza']}”: {' albo '.join(w.split('|'))}", plik=plik_dla(w),
                               pole=w.replace("tresc.", ""), klasa="A")
    # 1b. adres strony: domena albo — dopóki jej nie ma — adres roboczy (strona z noindex, D13)
    if not f["firma"].get("domena"):
        if f["firma"].get("adres_roboczy"):
            raport.ostrzezenie(f"brak firma.domena — strona powstaje pod adresem roboczym {f['firma']['adres_roboczy']} "
                               "z noindex (wyszukiwarki jej nie pokażą), a canonical, sitemap i og:image wskazują ten adres",
                               plik="data/firma.json", pole="firma.domena", klasa="A",
                               naprawa="wpisz domenę firmy (\"https://firma.pl\") przed podpięciem domeny i dopisz ją do "
                                       "do_potwierdzenia, dopóki właściciel jej nie potwierdzi")
        else:
            raport.blad("brak danych: adres strony — firma.domena (\"https://firma.pl\") albo, dopóki domeny nie ma, "
                        "firma.adres_roboczy (\"https://nazwa.konto.workers.dev\"; strona dostanie noindex)",
                        plik="data/firma.json", pole="firma.domena")
    # 1c. e-mail: art. 5 ust. 2 ustawy o świadczeniu usług drogą elektroniczną — adres elektroniczny musi być na stronie
    if not f["kontakt"].get("email"):
        raport.ostrzezenie("brak kontakt.email — strona firmy musi podawać adres poczty elektronicznej (art. 5 ust. 2 "
                           "ustawy o świadczeniu usług drogą elektroniczną); bez niego polityka prywatności i security.txt "
                           "podają tylko telefon", plik="data/firma.json", pole="kontakt.email",
                           naprawa="zapytaj właściciela o adres e-mail (--sprawdz przejdzie, --produkcja nie)")
    # 1d. geo zalecane: bez współrzędnych „Wyznacz trasę” prowadzi do adresu, nie do wejścia, i nie ma mapy
    if not f["kontakt"].get("geo"):
        raport.ostrzezenie("brak kontakt.geo — „Wyznacz trasę” poprowadzi do adresu (Mapy Google same go znajdą), "
                           "nie do wejścia; nie będzie mapy OpenStreetMap ani geo w danych strukturalnych",
                           plik="data/firma.json", pole="kontakt.geo", klasa="A",
                           naprawa="współrzędne wejścia z Map Google/OpenStreetMap, {\"lat\": 52.75360, \"lng\": 16.98759}")
    # 3. rejestr: sumy kontrolne i pola wymagane dla formy prawnej
    r = f["rejestr"]
    if r.get("nip") and not nip_ok(r["nip"]):
        raport.blad(f"NIP {r['nip']} ma złą sumę kontrolną", plik="data/firma.json", pole="rejestr.nip")
    if r.get("regon") and not regon_ok(r["regon"]):
        raport.blad(f"REGON {r['regon']} ma złą sumę kontrolną", plik="data/firma.json", pole="rejestr.regon")
    forma = r.get("forma_prawna")
    if forma == "nieznana":
        raport.ostrzezenie("forma prawna nieznana — w stopce jest tylko nazwa firmy, bez NIP/KRS/REGON wymaganych dla "
                           "formy prawnej", plik="data/firma.json", pole="rejestr.forma_prawna", klasa="A",
                           naprawa="sprawdź firmę w KRS (ekrs.ms.gov.pl) albo CEIDG (aplikacja.ceidg.gov.pl) po NIP z białej "
                                   "listy i wpisz formę; do tego czasu dopisz ją do do_potwierdzenia")
    if forma == "sa" and r.get("kapital_wplacony") is not None and r.get("kapital_zakladowy") is not None \
            and r["kapital_wplacony"] > r["kapital_zakladowy"]:
        raport.blad("kapitał wpłacony jest większy niż zakładowy", plik="data/firma.json", pole="rejestr.kapital_wplacony")
    if forma in FORMY:
        nazwa_formy, pola = FORMY[forma]
        for p in pola:
            zrodlo = f["firma"] if p == "nazwa_prawna" else r
            if not prawda(zrodlo.get(p)):
                raport.blad(f"{nazwa_formy}: w stopce musi być „{p}”", plik="data/firma.json",
                            pole=("firma." if p == "nazwa_prawna" else "rejestr.") + p,
                            naprawa="dane z KRS/CEIDG (wyszukiwarka: ekrs.ms.gov.pl, aplikacja.ceidg.gov.pl)")
    # 4. geo
    geo = f["kontakt"].get("geo")
    if geo:
        for k in ("lat", "lng"):
            if _miejsca_po_przecinku(geo[k]) < GEO_MIN_MIEJSC:
                raport.blad(f"współrzędna {k} = {getattr(geo[k], 'tekst', geo[k])} ma mniej niż {GEO_MIN_MIEJSC} miejsca "
                            f"po przecinku (dokładność gorsza niż ok. 10 m — „Wyznacz trasę” nie trafi do wejścia)",
                            plik="data/firma.json", pole=f"kontakt.geo.{k}",
                            naprawa="skopiuj współrzędne wejścia z Map Google/OpenStreetMap (prawy klik → współrzędne), "
                                    "zalecane 5 miejsc po przecinku")
        if not (49.0 <= geo["lat"] <= 54.9 and 14.1 <= geo["lng"] <= 24.2) and f["kontakt"]["adres"] and \
                f["kontakt"]["adres"].get("kraj", "PL") == "PL":
            raport.ostrzezenie("współrzędne leżą poza Polską — czy lat i lng nie są zamienione?", plik="data/firma.json",
                               pole="kontakt.geo")
    # 5. godziny
    g = f.get("godziny")
    if g:
        _sprawdz_tydzien(g["tydzien"], raport, "godziny.tydzien")
        for i, dod in enumerate(g.get("dodatkowe") or []):
            _sprawdz_tydzien(dod["tydzien"], raport, f"godziny.dodatkowe[{i}].tydzien")
        if not any(g["tydzien"].get(x) for x in DNI):
            raport.blad("godziny: wszystkie dni zamknięte — jeśli firma nie ma stałych godzin, wpisz \"godziny\": null",
                        plik="data/firma.json", pole="godziny.tydzien")
    # 6. marka
    m = f["marka"]
    for rola in ("font_naglowki", "font_tekst"):
        if m.get(rola) and m[rola] not in d.fonty:
            dostepne = ", ".join(k for k in d.fonty if not k.startswith("$"))
            raport.blad(f"nie ma kroju „{m[rola]}” w assets/fonts/fonty.json (dostępne: {dostepne})",
                        plik="data/firma.json", pole=f"marka.{rola}",
                        naprawa="wybierz krój z listy albo dodaj nowy: python3 tools/fonty.py dodaj …")
    for rola in ("logo", "logo_na_ciemnym"):
        if m.get(rola) and not m[rola].startswith("assets/img/"):
            # brief/ jest poza gitem i poza dist/ — lokalnie działa, na Cloudflare logo by zniknęło
            raport.blad(f"logo „{m[rola]}” musi leżeć w assets/img/ (brief/ nie trafia do repozytorium ani na serwer)",
                        plik="data/firma.json", pole=f"marka.{rola}",
                        naprawa=f"cp {m[rola]} assets/img/ i wpisz \"assets/img/{Path(m[rola]).name}\"")
        elif m.get(rola) and not (d.klient / m[rola]).is_file():
            raport.blad(f"nie ma pliku {m[rola]}", plik="data/firma.json", pole=f"marka.{rola}")
    if m.get("kolor") and not m.get("kolor_zrodlo"):
        raport.ostrzezenie("kolor marki bez źródła (logo, szyld, księga znaku)", plik="data/firma.json",
                           pole="marka.kolor_zrodlo")
    # 7. zdjęcia
    zdj = d.zdjecia
    ids = [z["id"] for z in d.zdjecia_lista]
    for i in {x for x in ids if ids.count(x) > 1}:
        raport.blad(f"powtórzone id zdjęcia „{i}”", plik="data/zdjecia.json")
    for z in d.zdjecia_lista:
        if z.get("osoby") and z.get("zgoda") is not True:
            raport.blad(f"zdjęcie „{z['id']}” pokazuje rozpoznawalne osoby — potrzebna zgoda (art. 81 prawa autorskiego)",
                        plik="data/zdjecia.json", pole=f"{z['id']}.zgoda", naprawa="wpisz \"zgoda\": true po uzyskaniu zgody albo usuń zdjęcie")
        if not (d.klient / z["zrodlo_plik"]).is_file() and not (d.klient / "assets/img/foto/manifest.json").exists():
            raport.ostrzezenie(f"nie ma oryginału {z['zrodlo_plik']}", plik="data/zdjecia.json", pole=f"{z['id']}.zrodlo_plik")
        if z.get("kadr_mobilny") and z["kadr_mobilny"] not in zdj:
            raport.blad(f"kadr_mobilny „{z['kadr_mobilny']}” nie istnieje", plik="data/zdjecia.json", pole=f"{z['id']}.kadr_mobilny")
    for sciezka, zid in _uzyte_zdjecia(t):
        if zid not in zdj:
            raport.blad(f"zdjęcie „{zid}” nie istnieje w data/zdjecia.json", plik="data/tresc.json", pole=sciezka)
    # 8. slugi w ofercie/produktach
    for blok in ("oferta", "produkty"):
        poz = (t.get(blok) or {}).get("pozycje") or []
        slugi = [p["slug"] for p in poz]
        for s in {x for x in slugi if slugi.count(x) > 1}:
            raport.blad(f"powtórzony slug „{s}”", plik="data/tresc.json", pole=f"{blok}.pozycje")
    # 9. formularz
    form = f["funkcje"].get("formularz")
    if form and form["tryb"] == "mailto" and not (form.get("adresat") or f["kontakt"].get("email")):
        raport.blad("formularz w trybie mailto potrzebuje adresu (funkcje.formularz.adresat albo kontakt.email)",
                    plik="data/firma.json", pole="funkcje.formularz")
    # 10. SEO
    opis = (f["seo"].get("opis") or f["firma"].get("opis") or "")
    pole_opisu = "seo.opis" if f["seo"].get("opis") else "firma.opis"
    if len(opis) > 160:
        raport.ostrzezenie(f"opis strony głównej ma {len(opis)} zn. (limit 160) — Google go przytnie",
                           plik="data/firma.json", pole=pole_opisu)
    elif opis and len(opis) < 70:
        # tylko informacja: krótki, konkretny opis jest lepszy niż dopisane ogólniki
        raport.ostrzezenie(f"opis strony głównej ma {len(opis)} zn. — jeśli masz jeszcze jeden fakt (godziny, zakres, "
                           "miejsce), dopisz go; nie dopisuj ogólników, żeby dobić do długości",
                           plik="data/firma.json", pole=pole_opisu, klasa="A")
    # 11. ogłoszenie
    og = t.get("ogloszenie")
    if og and og.get("od") and og.get("do") and og["od"] > og["do"]:
        raport.blad("ogłoszenie: data „od” jest późniejsza niż „do”", plik="data/tresc.json", pole="ogloszenie")
    # 12. przykład, do potwierdzenia, cennik
    if f.get("przyklad") and produkcja:
        raport.blad("to są dane przykładowe (\"przyklad\": true) — nie publikujemy ich jako strony klienta",
                    plik="data/firma.json", pole="przyklad")
    if f.get("do_potwierdzenia"):
        klucze = [x.split(" — ")[0].split(" (")[0] for x in f["do_potwierdzenia"]]
        # klasa A (D10): lista trafia do README „Do potwierdzenia z właścicielem”, nie blokuje publikacji —
        # niepewny fakt ma być null (ukryty) albo poglądowy i wpisany tutaj
        raport.ostrzezenie(f"{len(klucze)} {typo.liczba_mnoga(len(klucze), 'pozycja,pozycje,pozycji')} do potwierdzenia "
                           "z właścicielem: " + ", ".join(klucze), plik="data/firma.json", pole="do_potwierdzenia", klasa="A")
    for blok in ("cennik", "menu"):
        data = (t.get(blok) or {}).get("data")
        if data and (dzis - _data(data, raport, "data/tresc.json", f"{blok}.data", dzis)).days > 365:
            raport.ostrzezenie(f"{blok}: ceny z {typo.data_krotka(data)} — starsze niż 12 miesięcy", plik="data/tresc.json",
                               pole=f"{blok}.data")
    # 13. hosting
    if f["funkcje"].get("hosting") == "github_pages":
        if form and form["tryb"] == "worker":
            raport.blad("formularz w trybie worker działa tylko na Cloudflare (Worker /api/kontakt)", plik="data/firma.json",
                        pole="funkcje.formularz.tryb", naprawa="na GitHub Pages użyj \"tryb\": \"mailto\"")
        raport.ostrzezenie("GitHub Pages nie czyta pliku _headers — CSP, HSTS i pozostałe nagłówki bezpieczeństwa nie zadziałają",
                           plik="data/firma.json", pole="funkcje.hosting", klasa="A")
    # 13b. limit formularza: namespace_id z szablonu („1101”) dzieliłby limit z każdą inną stroną na tym samym koncie
    wrangler = d.klient / "wrangler.jsonc"
    if form and form["tryb"] == "worker" and f["funkcje"].get("hosting") == "cloudflare" and wrangler.is_file():
        if re.search(r'"namespace_id"\s*:\s*"1101"', wrangler.read_text(encoding="utf-8")):
            raport.ostrzezenie("wrangler.jsonc: ratelimits.namespace_id = \"1101\" (wartość z szablonu) — strony na jednym "
                               "koncie Cloudflare dzieliłyby limit 5 wiadomości na minutę", plik="wrangler.jsonc",
                               pole="ratelimits[0].namespace_id",
                               naprawa="wpisz inną liczbę dla tej strony (python3 tools/start.py robi to sam przy nowym kliencie)")
    # 14. składnia szablonu i tekst zastępczy w danych — błąd z nazwą pola, zanim trafi do dist/
    for plik, obiekt in (("data/firma.json", f), ("data/tresc.json", t), ("data/zdjecia.json", {"zdjecia": d.zdjecia_lista})):
        for sciezka, tekst in _teksty(obiekt):
            m = RE_POZOSTALOSCI.search(tekst)
            if m:
                raport.blad(f"w tekście jest „{m.group(0)}” — dane nie mogą zawierać składni szablonu ani tekstu zastępczego",
                            plik=plik, pole=sciezka, naprawa="wpisz prawdziwą treść albo null")
    for md in sorted((d.klient / "data").rglob("*.md")):
        tekst = md.read_text(encoding="utf-8")
        m = RE_POZOSTALOSCI.search(tekst)
        if m:
            raport.blad(f"w tekście jest „{m.group(0)}” — dane nie mogą zawierać składni szablonu ani tekstu zastępczego",
                        plik=f"{md.relative_to(d.klient)}:{tekst.count(chr(10), 0, m.start()) + 1}")
    if f["funkcje"].get("tytul_tryb") == "marka":
        raport.ostrzezenie("tytuł karty = sama marka na każdej stronie — wyszukiwarka nie odróżni podstron (D4)",
                           plik="data/firma.json", pole="funkcje.tytul_tryb", klasa="A")
    # 15. oferta, cennik, karta, produkty: ceny, netto, kategorie, pliki PDF, alergeny (tools/silnik/oferta.py)
    from . import oferta
    oferta.kontrole(d, raport)
    kontrole_realizacji(d, raport, dzis)
    # 15b. sekcje o firmie: opinie (Omnibus), zespół (zgoda na wizerunek), liczby, certyfikaty
    kontrole_firma(d, raport, dzis)
    # 16. godziny, ogłoszenie, aktualności, kariera, do pobrania, współpraca, gdzie kupić
    kontrole_modulow(d, raport, dzis)
    # 17. publikacja: przekierowania (_redirects), informacja o dostępności
    kontrole_publikacji(d, raport, dzis)
    # 18. godziny świąteczne (tools/swieta.py): święto za ≤ 45 dni bez wpisu w godziny.wyjatki
    kontrole_swiat(d, raport, dzis)


# ----------------------------------------------------------------------------- moduły dodatkowe (godziny, ogłoszenie,
# aktualności, kariera, do pobrania, współpraca, gdzie kupić — KONTRAKT §4.2, §9.1)

WOJEWODZTWA = {"dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie", "małopolskie", "mazowieckie",
               "opolskie", "podkarpackie", "podlaskie", "pomorskie", "śląskie", "świętokrzyskie", "warmińsko-mazurskie",
               "wielkopolskie", "zachodniopomorskie"}
_ALFABET_PL = "aąbcćdeęfghijklłmnńoóprsśtuvwxyzźż"


def klucz_pl(tekst: str) -> list[int]:
    """Klucz sortowania po polskim alfabecie („łódzkie” po „lubuskie”, „śląskie” po „pomorskie”)."""
    return [_ALFABET_PL.index(c) if c in _ALFABET_PL else 100 + ord(c) for c in (tekst or "").lower()]


def kontrole_modulow(d: Dane, raport, dzis: dt.date) -> None:
    t = d.tresc
    # pliki do pobrania: brak pliku = błąd (link donikąd); tylko assets/img/ klienta trafia do dist/
    img = (d.klient / "assets" / "img").resolve()
    for i, poz in enumerate((t.get("do_pobrania") or {}).get("pozycje") or []):
        sciezka = poz["plik"].lstrip("/")
        pole = f"do_pobrania.pozycje[{i}].plik"
        cel = (d.klient / sciezka).resolve()
        if not cel.is_relative_to(img):
            raport.blad(f"plik „{poz['plik']}” leży poza assets/img/ — na serwer trafia tylko ten katalog klienta",
                        plik="data/tresc.json", pole=pole, naprawa="przenieś plik do assets/img/pliki/ i wpisz \"assets/img/pliki/nazwa.pdf\"")
        elif not cel.is_file():
            raport.blad(f"nie ma pliku {sciezka}", plik="data/tresc.json", pole=pole,
                        naprawa="dodaj plik do assets/img/pliki/ albo usuń pozycję z listy")
    # zdjęcia wpisów (nagłówek „zdjecie:” w data/aktualnosci/*.md)
    for w in d.aktualnosci:
        if w.get("zdjecie") and w["zdjecie"] not in d.zdjecia:
            raport.blad(f"zdjęcie „{w['zdjecie']}” nie istnieje w data/zdjecia.json", plik=f"data/aktualnosci/{w['slug']}.md",
                        pole="zdjecie", naprawa="wpisz id z data/zdjecia.json albo usuń wiersz „zdjecie:”")
    # oferty pracy: kolejność dat, oferty po terminie znikają (strona /kariera powstaje tylko z aktualnymi)
    for i, poz in enumerate((t.get("kariera") or {}).get("pozycje") or []):
        od, do = typo.na_date(poz.get("opublikowano")), typo.na_date(poz.get("wazne_do"))
        if od and do and od > do:
            raport.blad(f"oferta „{poz['stanowisko']}”: data publikacji jest późniejsza niż „wazne_do”",
                        plik="data/tresc.json", pole=f"kariera.pozycje[{i}]")
        if do and do < dzis:
            raport.ukryto(f"oferta pracy „{poz['stanowisko']}” (ważna do {typo.data_krotka(do)})")
    # punkty sprzedaży: literówka w województwie („wielkoplskie”) rozbiłaby grupę; nazwa kraju („Niemcy”) jest w porządku
    for i, p in enumerate((t.get("gdzie_kupic") or {}).get("punkty") or []):
        woj = (p.get("wojewodztwo") or "").lower()
        if woj.endswith("kie") and woj not in WOJEWODZTWA:
            raport.blad(f"„{p['wojewodztwo']}” — nie ma takiego województwa", plik="data/tresc.json",
                        pole=f"gdzie_kupic.punkty[{i}].wojewodztwo",
                        naprawa="wpisz nazwę z listy: " + ", ".join(sorted(WOJEWODZTWA, key=klucz_pl)))


def godziny_wiersze(g: dict) -> tuple[list, list]:
    """Sekcja „godziny”: jedna tabela, wiersz na dzień, kolumna na zestaw godzin (główne + dodatkowe: kuchnia, telefon).
    Zwraca (nazwy kolumn — pierwsza None, gdy godziny.nazwa = null; wiersze {kod, dzien, dzien_krotki, komorki})."""
    zestawy = [g["tydzien"]] + [x["tydzien"] for x in (g.get("dodatkowe") or [])]
    nazwy = [g.get("nazwa")] + [x["nazwa"] for x in (g.get("dodatkowe") or [])]
    wiersze = []
    for kod in DNI:
        # przedział nie łamie się w środku („12:00–22:00”), dwa przedziały mogą się złamać po przecinku
        komorki = [{"tekst": _przedzialy_tekst(z.get(kod) or []) or "zamknięte", "zamkniete": not z.get(kod),
                    "html": Markup(", ".join(f'<span class="nowrap">{_przedzialy_tekst([p])}</span>' for p in z.get(kod) or [])
                                   or "zamknięte")} for z in zestawy]
        wiersze.append({"kod": kod, "dzien": DNI_NAZWY[kod], "dzien_krotki": DNI_KROTKIE[kod], "komorki": komorki,
                        "zamkniete": all(k["zamkniete"] for k in komorki)})
    return nazwy, wiersze


def pliki_do_pobrania(d: Dane) -> list[dict]:
    """tresc.do_pobrania → [{plik, opis, typ, mime, rozmiar, strony, strony_tekst, meta}] (pliki.py)."""
    from . import pliki
    wynik = []
    for poz in (d.tresc.get("do_pobrania") or {}).get("pozycje") or []:
        sciezka = poz["plik"].lstrip("/")
        if (d.klient / sciezka).is_file():          # brak pliku zgłosiła kontrole_modulow()
            wynik.append({"plik": sciezka, "opis": poz["opis"], **pliki.informacje(d.klient / sciezka)})
    return wynik


def punkty_sprzedazy(t: dict) -> list[dict]:
    """tresc.gdzie_kupic → grupy [{wojewodztwo, nazwa, punkty}]: województwa alfabetycznie (polski alfabet), potem inne
    nazwy (kraje), na końcu punkty bez województwa („Pozostałe”; bez nagłówka, gdy to jedyna grupa)."""
    grupy: dict = {}
    pisownia: dict = {}             # kraj w pisowni z danych („Wielka Brytania”), województwo — „Wielkopolskie”
    for p in (t.get("gdzie_kupic") or {}).get("punkty") or []:
        klucz = (p.get("wojewodztwo") or "").lower() or None
        grupy.setdefault(klucz, []).append(p)
        pisownia.setdefault(klucz, p.get("wojewodztwo"))
    kolejnosc = sorted((k for k in grupy if k), key=lambda k: (k not in WOJEWODZTWA, klucz_pl(k)))
    wynik = [{"wojewodztwo": k, "nazwa": typo.wersaliki_pierwsza(k if k in WOJEWODZTWA else pisownia[k]), "punkty": grupy[k]}
             for k in kolejnosc]
    if None in grupy:
        wynik.append({"wojewodztwo": None, "nazwa": "Pozostałe" if wynik else None, "punkty": grupy[None]})
    for g in wynik:
        g["punkty"] = [dict(p, adres_html=_adres_punktu(p)) for p in
                       sorted(g["punkty"], key=lambda p: (klucz_pl(p["miasto"]), klucz_pl(p["nazwa"])))]
    return wynik


def _adres_punktu(p: dict) -> Markup:
    """„ul. Długa 5, 60-101 Poznań” — kod pocztowy nie łamie się na dywizie; miasto dopisane, gdy nie ma go w adresie."""
    adres = p.get("adres") or ""
    if p["miasto"].lower() not in adres.lower():
        adres = f"{adres}, {p['miasto']}" if adres else p["miasto"]
    return Markup(re.sub(r"\b(\d{2}-\d{3})\b", r'<span class="nowrap">\1</span>', _html_typo(adres)))


def oferty_pracy(d: Dane, dzis: dt.date) -> list[dict]:
    """Aktualne oferty (bez wazne_do albo z wazne_do ≥ dziś) z kotwicą; JobPosting tylko z datą publikacji,
    datą ważności i opisem (jsonld.py)."""
    from .strony import _kariera
    wynik, uzyte = [], set()
    for p in _kariera(d, dzis):
        s = typo.slug(p["stanowisko"]) or "oferta"
        slug, n = s, 2
        while slug in uzyte:
            slug, n = f"{s}-{n}", n + 1
        uzyte.add(slug)
        wynik.append(dict(p, slug=slug, html_id=f"praca-{slug}"))
    return wynik


def auto_moduly(d: Dane, dzis: dt.date, podstrony: set, wynik: dict) -> None:
    f, t, k = d.firma, d.tresc, d.firma["kontakt"]
    g = f.get("godziny")
    if g:
        wynik["godziny_zestawy"], wynik["godziny_wiersze"] = godziny_wiersze(g)
    else:
        wynik["godziny_zestawy"], wynik["godziny_wiersze"] = [], []
    for w in wynik.get("godziny_wyjatki") or []:     # „śr. 14 października” (rok tylko, gdy inny niż bieżący)
        data = typo.na_date(w["data"])
        w["dzien_tygodnia"] = DNI_NAZWY[DNI[data.weekday()]]
        w["kiedy"] = f"{DNI_KROTKIE[DNI[data.weekday()]]} {data.day} {typo.MIESIACE[data.month - 1]}" + \
            (f" {data.year}" if data.year != dzis.year else "")
    wynik["do_pobrania"] = pliki_do_pobrania(d)
    wynik["gdzie_kupic"] = punkty_sprzedazy(t)
    wynik["kariera"] = oferty_pracy(d, dzis)
    kk = (t.get("kariera") or {}).get("kontakt") or {}
    tel, email = kk.get("telefon") or k.get("telefon"), kk.get("email") or k.get("email")
    wynik["kariera_kontakt"] = {
        "osoba": kk.get("osoba"), "email": email,
        "tel_href": typo.tel_href(tel) if tel else None, "telefon_krajowy": typo.tel(tel, krajowy=True) if tel else None,
        "mailto": f"mailto:{email}?subject={quote('Praca – ' + f['firma']['nazwa'])}" if email else None}
    for p in wynik["kariera"]:     # e-mail z CV — temat z nazwą stanowiska
        p["mailto"] = f"mailto:{email}?subject={quote('CV – ' + p['stanowisko'])}" if email else None
    wynik["kariera_stanowiska"] = [p["stanowisko"] for p in wynik["kariera"]]
    wsp_temat = quote(f"Współpraca – {f['firma']['nazwa']}")
    wynik["wspolpraca_mailto"] = f"mailto:{k['email']}?subject={wsp_temat}" if k.get("email") else None
    # kanał RSS tylko razem ze stroną /aktualnosci (preset może jej nie mieć)
    wynik["rss"] = bool(f["funkcje"].get("rss") and "/aktualnosci" in podstrony)


# ----------------------------------------------------------------------------- kontekst auto

def _godzina(g: str, zamkniecie: bool = False) -> str:
    """„07:00” → „7:00”; zamknięcie o północy („00:00” albo „24:00”) → „24:00”."""
    if zamkniecie and g in ("00:00", "24:00"):
        return "24:00"
    h, m = g.split(":")
    return f"{int(h)}:{m}"


def _przedzialy_tekst(przedzialy) -> str:
    return ", ".join(f"{_godzina(a)}–{_godzina(b, zamkniecie=True)}" for a, b in przedzialy)


def godziny_tabela(tydzien: dict) -> list[dict]:
    return [{"dzien": DNI_NAZWY[k], "dzien_krotki": DNI_KROTKIE[k], "kod": k,
             "przedzialy_tekst": _przedzialy_tekst(tydzien.get(k) or []) or "zamknięte",
             "zamkniete": not tydzien.get(k)} for k in DNI]


def godziny_skrot(tydzien: dict) -> str:
    """„pn.–pt. 7:00–15:00; sob. 8:00–12:00” — kolejne dni o tych samych godzinach łączone, grupy dni rozdziela „; ”
    (przecinek rozdziela przedziały jednego dnia: „wt. 12:00–15:00, 18:00–22:00”); dni zamknięte pomijane."""
    grupy = []
    for k in DNI:
        tekst = _przedzialy_tekst(tydzien.get(k) or [])
        if grupy and grupy[-1][2] == tekst:
            grupy[-1][1] = k
        else:
            grupy.append([k, k, tekst])
    czesci = []
    for od, do, tekst in grupy:
        if not tekst:
            continue
        dni = DNI_KROTKIE[od] if od == do else f"{DNI_KROTKIE[od]}–{DNI_KROTKIE[do]}"
        czesci.append(f"{dni} {tekst}")
    return "; ".join(czesci)


def _html_typo(tekst: str) -> str:
    return html.escape(typo.typografia(tekst))


def kod_miasto_html(a: dict) -> Markup:
    """„64-610 Rogoźno” z kodem, który nie łamie się na dywizie (U+2011 nie ma w podzbiorach fontów)."""
    czesci = []
    if a.get("kod"):
        czesci.append(f'<span class="nowrap">{html.escape(a["kod"])}</span>')
    if a.get("miasto"):
        czesci.append(_html_typo(a["miasto"]))
    return Markup(" ".join(czesci))


def rejestr_linie(f: dict) -> list[Markup]:
    """Linie danych rejestrowych do stopki (art. 206 KSH / art. 20 ust. 3 Prawa przedsiębiorców). Pierwsza linia to nazwa
    prawna — pomijana, gdy jest taka sama jak nazwa firmy (ta stoi w stopce nad rejestrem i przy ©).
    Adres siedziby (= kontakt.adres) stoi raz, w kolumnie „Dane kontaktowe” tej samej stopki — tu go nie powtarzamy."""
    r, fi = f["rejestr"], f["firma"]
    linie = []
    forma = r.get("forma_prawna")
    nazwa = fi.get("nazwa_prawna") or fi.get("nazwa")
    if forma == "jdg" and r.get("wlasciciel") and r["wlasciciel"].lower() not in nazwa.lower():
        linie.append(f"{nazwa}, {r['wlasciciel']}")
    elif forma == "spolka_cywilna" and r.get("wspolnicy"):
        linie.append(f"{nazwa} s.c., wspólnicy: {', '.join(r['wspolnicy'])}")
    elif nazwa != fi.get("nazwa"):
        linie.append(nazwa)          # nazwa prawna = krótka nazwa → stoi już nad rejestrem i przy © (bez powtórzenia)
    if r.get("krs"):
        linie.append(f"KRS{typo.NBSP}{r['krs']}" + (f", {r['sad_rejestrowy']}" if r.get("sad_rejestrowy") else ""))
    ident = []
    if r.get("nip"):
        ident.append(f"NIP{typo.NBSP}{r['nip']}")
    if r.get("regon"):
        ident.append(f"REGON{typo.NBSP}{r['regon']}")
    if ident:
        linie.append(", ".join(ident))
    if r.get("kapital_zakladowy") is not None and forma in ("sp_z_oo", "sa"):
        wplacony = r.get("kapital_wplacony")
        if forma == "sp_z_oo" or (wplacony is not None and wplacony >= r["kapital_zakladowy"]):
            dopisek = " (wpłacony w całości)"
        elif wplacony is not None:          # art. 374 § 1 pkt 4 KSH: S.A. podaje też kapitał wpłacony
            dopisek = f", kapitał wpłacony {typo.cena(wplacony)}"
        else:
            dopisek = ""
        linie.append(f"Kapitał zakładowy {typo.cena(r['kapital_zakladowy'])}{dopisek}")
    siedziba = r.get("adres_siedziby")
    kontakt_adres = f["kontakt"].get("adres") or {}
    if siedziba and any((siedziba.get(k) or "").strip().lower() != (kontakt_adres.get(k) or "").strip().lower()
                        for k in ("ulica", "kod", "miasto")):
        # KSH: „siedziba i adres” — gdy siedziba jest gdzie indziej niż lokal z kolumny „Dane kontaktowe”
        linie.append("Siedziba: " + ", ".join(x for x in (siedziba.get("ulica"),
                                                         " ".join(y for y in (siedziba.get("kod"), siedziba.get("miasto")) if y)) if x))
    if r.get("samorzad_zawodowy"):
        linie.append(r["samorzad_zawodowy"])
    return [Markup(_html_typo(x)) for x in linie]


# adres przycisku: słowo kluczowe albo bezpieczny adres (to samo co pattern $defs.cta.href w tresc.schema.json) —
# „javascript:…” nie może trafić do href także z presetu i przy podglądzie --plik, gdzie nie ma CSP
RE_CTA = re.compile(r"(https://\S+|mailto:\S+|tel:\+?\d+|/(?!/)\S*|#[\w-]+|tel|trasa|kontakt|katalog)")


def _cta(spec: dict | None, auto: dict, podstrony: set, pliki_do_pobrania: list) -> dict | None:
    if not spec:
        return None
    href = spec.get("href") or ""
    if not RE_CTA.fullmatch(href):
        raise ValueError(f"przycisk „{spec.get('tekst')}”: niedozwolony adres {href!r}")
    tekst = spec.get("tekst") or ""
    typ = "link"
    numer = None
    if href == "tel":
        href, typ, numer = auto["tel_href"], "tel", auto["telefon_e164"]
    elif href.startswith("tel:"):
        typ, numer = "tel", href[4:]
    elif href == "trasa":
        href, typ = auto["trasa_url"], "trasa"
    elif href == "kontakt":
        href, typ = "/kontakt", "kontakt"
    elif href == "katalog":
        pdf = next((p["plik"] for p in pliki_do_pobrania if p["plik"].lower().endswith(".pdf")), None)
        href, typ = ("/" + pdf.lstrip("/"), "katalog") if pdf else ("/kontakt", "kontakt")
    elif href.startswith("/") and "#" not in href and href != "/" and href not in podstrony:
        href = "/#" + href.strip("/").replace("_", "-")          # podstrony nie ma → kotwica na głównej
    if "{tel}" in tekst:
        tekst = tekst.replace("{tel}", typo.tel(numer or auto["telefon_e164"], krajowy=True))
    return {"tekst": tekst, "href": href, "typ": typ, "zewnetrzny": href.startswith("http"), "zrodlo": spec.get("href")}


def sprawdz_cta(auto: dict, d: Dane, widoczne: list, raport) -> None:
    """Przycisk hero prowadzący donikąd: /menu bez podstrony i bez sekcji „menu” na głównej. Sprawdzane po planie
    stron (dopiero wtedy wiadomo, które podstrony i sekcje powstały) — błąd z nazwą pola zamiast „kotwica nie istnieje”."""
    kotwice = {"tresc", "tytul-strony"} | {html_id(s) for s in widoczne}
    hero = d.tresc.get("hero") or {}
    for klucz in ("cta_glowne", "cta_drugie"):
        c = auto.get(klucz)
        if not c or not c["href"].startswith("/#"):
            continue
        kotwica = c["href"][2:]
        if kotwica not in kotwice:
            z_danych = bool(hero.get(klucz))
            raport.blad(f"przycisk „{c['tekst']}” prowadzi do „{c['zrodlo']}”, a nie ma takiej podstrony "
                        f"ani sekcji „{kotwica}” na stronie głównej",
                        plik="data/tresc.json" if z_danych else f"tools/presety/{d.firma['branza']}.json",
                        pole=f"hero.{klucz}.href" if z_danych else klucz,
                        naprawa="wskaż istniejącą stronę (\"kontakt\", \"tel\", \"trasa\", \"/kontakt\") albo uzupełnij dane "
                                "sekcji, do której prowadzi przycisk")



PASEK = {"tel": ("Zadzwoń", "tel"), "trasa": ("Wyznacz trasę", "trasa"), "kontakt": ("Kontakt", "kontakt"),
         "katalog": ("Katalog", "katalog")}


def auto(d: Dane, dzis: dt.date, podstrony: set, sekcje_widoczne: list) -> dict:
    f, t = d.firma, d.tresc
    k = f["kontakt"]
    a = k.get("adres") or {}
    geo = k.get("geo") or {}
    lat, lng = (getattr(geo.get("lat"), "tekst", None) or str(geo.get("lat", ""))), \
               (getattr(geo.get("lng"), "tekst", None) or str(geo.get("lng", "")))
    wynik: dict = {}
    wynik["telefon_e164"] = k.get("telefon")
    wynik["telefon"] = typo.tel(k.get("telefon")) if k.get("telefon") else None
    wynik["telefon_krajowy"] = typo.tel(k.get("telefon"), krajowy=True) if k.get("telefon") else None
    wynik["tel_href"] = typo.tel_href(k.get("telefon")) if k.get("telefon") else None
    kod_miasto = " ".join(x for x in [a.get("kod"), a.get("miasto")] if x)
    wynik["adres_linia"] = ", ".join(x for x in [a.get("ulica"), kod_miasto] if x) or None   # zwykły tekst (atrybuty, meta)
    ulica_html = _html_typo(a["ulica"]) if a.get("ulica") else ""
    km_html = kod_miasto_html(a)
    wynik["adres_html"] = Markup("<br>".join(x for x in [ulica_html, km_html] if x)) or None
    wynik["adres_linia_html"] = Markup(", ".join(x for x in [ulica_html, km_html] if x)) or None
    if geo:
        wynik["trasa_url"] = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
        wynik["osm_url"] = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=17/{lat}/{lng}"
        la, ln = float(geo["lat"]), float(geo["lng"])
        wynik["osm_embed"] = ("https://www.openstreetmap.org/export/embed.html?bbox="
                              f"{ln - 0.006:.5f},{la - 0.003:.5f},{ln + 0.006:.5f},{la + 0.003:.5f}&layer=mapnik&marker={lat},{lng}")
    else:
        # bez współrzędnych: trasa do adresu (Mapy Google same go znajdą), bez mapy OpenStreetMap
        wynik["trasa_url"] = (f"https://www.google.com/maps/dir/?api=1&destination={quote(wynik['adres_linia'])}"
                              if wynik["adres_linia"] else None)
        wynik["osm_url"] = wynik["osm_embed"] = None
    g = f.get("godziny")
    if g:
        wynik["godziny_tabela"] = godziny_tabela(g["tydzien"])
        wynik["godziny_skrot"] = godziny_skrot(g["tydzien"])
        wynik["godziny_dodatkowe"] = [{"nazwa": x["nazwa"], "tabela": godziny_tabela(x["tydzien"]),
                                       "skrot": godziny_skrot(x["tydzien"])} for x in (g.get("dodatkowe") or [])]
        wynik["godziny_wyjatki"] = [
            {"data": w["data"], "data_tekst": typo.data_dluga(w["data"]), "opis": w.get("opis"),
             "tekst": _przedzialy_tekst(w["godziny"]) or "zamknięte"}
            for w in g.get("wyjatki") or [] if 0 <= (typo.na_date(w["data"]) - dzis).days <= 60]   # daty sprawdził schemat
    else:
        wynik["godziny_tabela"] = wynik["godziny_skrot"] = None
        wynik["godziny_dodatkowe"] = wynik["godziny_wyjatki"] = []
    wynik["status_start"] = ""
    wynik["pokaz_status"] = bool(g and g.get("pokazuj_status"))
    wynik["status_w_hero"] = bool(g and g.get("pokazuj_status") and d.preset.get("pokazuj_status_w_hero"))
    wynik["godziny_osobno"] = "godziny" in sekcje_widoczne
    wynik["rejestr_linie"] = rejestr_linie(f)
    wynik["rok"] = dzis.year
    wynik["dzis"] = dzis.isoformat()
    do_pobrania = (t.get("do_pobrania") or {}).get("pozycje") or []
    hero = t.get("hero") or {}
    wynik["cta_glowne"] = _cta(hero.get("cta_glowne") or d.preset.get("cta_glowne"), wynik, podstrony, do_pobrania)
    wynik["cta_drugie"] = _cta(hero.get("cta_drugie") or d.preset.get("cta_drugie"), wynik, podstrony, do_pobrania)
    pasek = []
    for kod in d.preset.get("pasek_mobilny", []):
        if kod == "tel" and not wynik["tel_href"] or kod == "trasa" and not wynik["trasa_url"]:
            continue
        tekst, href = PASEK[kod]
        pasek.append(_cta({"tekst": tekst, "href": href}, wynik, podstrony, do_pobrania))
    wynik["pasek_mobilny"] = pasek
    tel_nagl = f["funkcje"].get("telefon_w_naglowku")
    wynik["telefon_w_naglowku"] = bool(d.preset.get("telefon_w_naglowku") if tel_nagl is None else tel_nagl) and bool(wynik["tel_href"])
    wynik["naglowki"] = {k2: v for k2, v in d.preset.get("naglowki", {}).items()}
    wynik["podstrony"] = sorted(podstrony)
    wynik["sekcje_widoczne"] = list(sekcje_widoczne)
    form = f["funkcje"].get("formularz")
    if form:
        adresat = form.get("adresat") or k.get("email")
        temat = f"Zapytanie ze strony {f['firma']['nazwa']}"
        tresc_maila = "Imię i nazwisko:\nTelefon:\nCzego dotyczy zapytanie:\n"
        mailto = f"mailto:{adresat}?subject={quote(temat)}&body={quote(tresc_maila)}" if adresat else None
        wynik["formularz"] = {"tryb": form["tryb"], "akcja": "/api/kontakt", "mailto_href": mailto, "adresat": adresat,
                              "zgoda_checkbox": form.get("zgoda_checkbox", False)}
    else:
        wynik["formularz"] = None
    wynik["email_href"] = f"mailto:{k['email']}" if k.get("email") else None
    # link ze skrótu kontaktu na głównej do /kontakt — wymienia to, czego na głównej nie ma (opisowy tekst linku)
    wiecej = []
    if k.get("dzialy"):
        wiecej.append("telefony działów")
    if form:
        wiecej.append("formularz zapytania" if form["tryb"] == "worker" else "zapytanie e-mailem")
    if f["funkcje"].get("mapa") == "po_kliknieciu" and geo:
        wiecej.append("mapa")
    if k.get("dojazd"):
        wiecej.append("opis dojazdu")
    if k.get("dostepnosc_lokalu"):
        wiecej.append("dostępność lokalu")
    tekst_wiecej = (", ".join(wiecej[:-1]) + " i " + wiecej[-1]) if len(wiecej) > 1 else (wiecej[0] if wiecej else "")
    wynik["kontakt_wiecej"] = typo.wersaliki_pierwsza(tekst_wiecej) or None
    nazwy_social = {"facebook": "Facebook", "instagram": "Instagram", "google_maps": "Mapy Google",
                    "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok"}
    wynik["social"] = [{"nazwa": n, "url": f["social"][kl]} for kl, n in nazwy_social.items() if f["social"].get(kl)]
    autorzy = sorted({z["autor"] for z in d.zdjecia_lista if z.get("autor")})
    wynik["zdjecia_autorzy"] = autorzy
    og = t.get("ogloszenie")
    aktywne = None
    if og:
        od = typo.na_date(og.get("od")) or dzis
        do = typo.na_date(og.get("do"))
        if od <= dzis and (do is None or dzis <= do):
            aktywne = og
    wynik["ogloszenie"] = aktywne
    # auto.oferta, auto.cennik, auto.menu, auto.produkty (tools/silnik/oferta.py)
    from . import oferta
    wynik.update(oferta.auto(d, podstrony, sekcje_widoczne, wynik))
    wynik.update(auto_realizacje(d))
    wynik.update(auto_firma(d, dzis, podstrony, sekcje_widoczne))
    auto_moduly(d, dzis, podstrony, wynik)
    return wynik


# ----------------------------------------------------------------------------- realizacje, przetargi, galeria

# Wyszukiwarka ogłoszeń Biuletynu Zamówień Publicznych (platforma e-Zamówienia). Link stoi pod tabelą przetargów,
# gdy wiersze mają źródło „BZP” — odwiedzający sprawdzi zamówienie sam, po nazwie zadania albo zamawiającego.
BZP_URL = "https://ezamowienia.gov.pl/mo-client-board/bzp/list"
# ulica albo numer w polu „miejsce” — przy realizacji prywatnej to byłby adres czyjegoś domu
_RE_ULICA = re.compile(r"(?:^|\s)(?:ul|al|os|pl)\.|\d")


def _host(url: str) -> str:
    from urllib.parse import urlsplit
    return urlsplit(url).netloc.removeprefix("www.")


def _skrot(tekst: str, n: int = 60) -> str:
    """Początek długiej nazwy do komunikatu — ucięty na słowie."""
    return tekst if len(tekst) <= n else tekst[:n].rsplit(" ", 1)[0] + "…"


def kontrole_realizacji(d: Dane, raport, dzis: dt.date) -> None:
    """Realizacje i przetargi: kategorie, tryb prywatny, lata w przyszłości, powtórzone wiersze."""
    t = d.tresc
    r = t.get("realizacje")
    if r:
        slugi = [k["slug"] for k in (r.get("kategorie") or [])]
        for s in {x for x in slugi if slugi.count(x) > 1}:
            raport.blad(f"powtórzona kategoria realizacji „{s}”", plik="data/tresc.json", pole="realizacje.kategorie")
        for i, p in enumerate(r["pozycje"]):
            pole = f"realizacje.pozycje[{i}]"
            if p.get("kategoria") and p["kategoria"] not in slugi:
                raport.blad(f"realizacja „{p['tytul']}”: nieznana kategoria „{p['kategoria']}”"
                            + (f" (są: {', '.join(dict.fromkeys(slugi))})" if slugi else ""), plik="data/tresc.json", pole=f"{pole}.kategoria",
                            naprawa="dopisz kategorię do realizacje.kategorie ({\"slug\": …, \"nazwa\": …}) albo popraw slug")
            elif slugi and not p.get("kategoria"):
                raport.ostrzezenie(f"realizacja „{p['tytul']}” nie ma kategorii — w filtrze będzie tylko pod „Wszystkie”",
                                   plik="data/tresc.json", pole=f"{pole}.kategoria")
            if p.get("prywatna") and p.get("miejsce") and _RE_ULICA.search(p["miejsce"]):
                raport.blad(f"realizacja „{p['tytul']}” jest prywatna, a „miejsce” ma ulicę albo numer: „{p['miejsce']}”",
                            plik="data/tresc.json", pole=f"{pole}.miejsce",
                            naprawa="przy \"prywatna\": true wpisz samą miejscowość albo gminę, np. „Rogoźno” albo „gm. Oborniki”")
            if p.get("rok") and p["rok"] > dzis.year:
                # ostrzeżenie (w --produkcja błąd): SZABLON_DZIS z przeszłą datą nie może zatrzymać zwykłego buildu
                raport.ostrzezenie(f"realizacja „{p['tytul']}”: rok {p['rok']} jest w przyszłości", plik="data/tresc.json",
                                   pole=f"{pole}.rok", naprawa="realizacje to prace wykonane — wpisz rok zakończenia albo usuń pozycję")
    pr = t.get("przetargi")
    if pr:
        widziane = set()
        for i, p in enumerate(pr["pozycje"]):
            pole = f"przetargi.pozycje[{i}]"
            if p["rok"] > dzis.year:
                raport.ostrzezenie(f"przetarg „{_skrot(p['zadanie'])}”: rok {p['rok']} jest w przyszłości", plik="data/tresc.json",
                                   pole=f"{pole}.rok", naprawa="wpisz rok udzielenia zamówienia z ogłoszenia o wyniku (BZP)")
            klucz = (" ".join(p["zadanie"].lower().split()), " ".join(p["zamawiajacy"].lower().split()), p["rok"])
            if klucz in widziane:
                raport.ostrzezenie(f"przetarg „{_skrot(p['zadanie'])}” ({p['rok']}) jest na liście dwa razy", plik="data/tresc.json",
                                   pole=pole)
            widziane.add(klucz)
            zr = (p.get("zrodlo") or "").strip()
            if zr.startswith("http") and not zr.startswith("https://"):
                raport.blad(f"źródło przetargu „{_skrot(p['zadanie'])}” musi być adresem https://…", plik="data/tresc.json",
                            pole=f"{pole}.zrodlo")


def auto_realizacje(d: Dane) -> dict:
    """auto.realizacje, auto.przetargi, auto.galeria (KONTRAKT §9.1) — to, czego szablon sam nie policzy: nazwa kategorii
    i podpis zdjęcia po id, liczniki, poprzedni wiersz (grupy lat w tabeli przetargów). Brak danych = None."""
    t, zdj = d.tresc, d.zdjecia
    foto = lambda zid: {"id": zid, "podpis": (zdj.get(zid) or {}).get("podpis")}
    https = lambda s: s.strip() if isinstance(s, str) and s.strip().startswith("https://") else None
    wynik: dict = {"realizacje": None, "przetargi": None, "galeria": None}

    r = t.get("realizacje")
    if r and r.get("pozycje"):
        nazwy = {k["slug"]: k["nazwa"] for k in (r.get("kategorie") or [])}
        pozycje = []
        for p in r["pozycje"]:
            miejsce, tytul = (p.get("miejsce") or "").strip(), p["tytul"].strip()
            # tytuł „{miejsce} – {typ}” (web-smb-best U5); gdy miejsce już jest w tytule — bez powtórzenia
            pelny = f"{miejsce} – {tytul}" if miejsce and miejsce.lower() not in tytul.lower() else tytul
            url = https(p.get("zrodlo"))
            pozycje.append({**p, "tytul_pelny": typo.wersaliki_pierwsza(pelny),
                            "klient_tekst": "Klient prywatny" if p.get("prywatna") else p.get("klient"),
                            "kategoria_nazwa": nazwy.get(p.get("kategoria")),
                            "zdjecia": [foto(z) for z in (p.get("zdjecia") or [])],
                            "zrodlo_url": url, "zrodlo_host": _host(url) if url else None})
        liczniki: dict = {}
        for p in pozycje:
            if p.get("kategoria") in nazwy:
                liczniki[p["kategoria"]] = liczniki.get(p["kategoria"], 0) + 1
        kategorie = [{"slug": k["slug"], "nazwa": k["nazwa"], "liczba": liczniki[k["slug"]]}
                     for k in (r.get("kategorie") or []) if liczniki.get(k["slug"])]
        wynik["realizacje"] = {"pozycje": pozycje, "liczba": len(pozycje), "kategorie": kategorie,
                               "filtr": len(kategorie) >= 2}

    pr = t.get("przetargi")
    if pr and pr.get("pozycje"):
        # od najnowszych; w obrębie roku kolejność z danych (sortowanie stabilne)
        wiersze = sorted(pr["pozycje"], key=lambda p: -p["rok"])
        pozycje, poprzedni = [], None
        for p in wiersze:
            url = https(p.get("zrodlo"))
            pozycje.append({**p, "nowy_rok": p["rok"] != poprzedni, "zrodlo_url": url,
                            "zrodlo_host": _host(url) if url else None,
                            "zrodlo_tekst": None if url else ((p.get("zrodlo") or "").strip() or None)})
            poprzedni = p["rok"]
        lata = [p["rok"] for p in wiersze]
        wynik["przetargi"] = {
            "pozycje": pozycje, "liczba": len(pozycje), "rok_od": min(lata), "rok_do": max(lata),
            "zamawiajacych": len({" ".join(p["zamawiajacy"].lower().split()) for p in wiersze}),
            "z_wartoscia": any(p.get("wartosc") is not None for p in wiersze),
            "z_linkami": any(p["zrodlo_url"] for p in pozycje),
            "bzp_url": BZP_URL if any((p.get("zrodlo") or "").strip().upper() == "BZP" for p in wiersze) else None,
        }

    g = t.get("galeria")
    if g and g.get("zdjecia"):
        wynik["galeria"] = [foto(z) for z in g["zdjecia"]]
    return wynik


# ----------------------------------------------------------------------------- sekcje o firmie
# proces, zasady, faq, o_firmie, zespol, liczby, opinie, certyfikaty (src/sekcje/*.html, KONTRAKT §6.2).
# Szablon nie policzy osób ani nie sprawdzi pliku na dysku — robi to Python, sekcje czytają gotowe auto.*.

SERWISY_OPINII = (("google.", "Google"), ("goo.gl", "Google"), ("g.page", "Google"), ("facebook.", "Facebook"),
                  ("fb.com", "Facebook"), ("znanylekarz.", "ZnanyLekarz"), ("booksy.", "Booksy"),
                  ("booking.", "Booking.com"), ("tripadvisor.", "Tripadvisor"), ("oferteo.", "Oferteo"),
                  ("fixly.", "Fixly"), ("houzz.", "Houzz"), ("trustpilot.", "Trustpilot"), ("ceneo.", "Ceneo"),
                  ("allegro.", "Allegro"), ("pyszne.", "Pyszne.pl"))


def serwis_opinii(url: str) -> str:
    """Nazwa serwisu z adresu opinii („https://maps.app.goo.gl/…” → „Google”) — do opisowego tekstu linku."""
    from urllib.parse import urlsplit
    host = (urlsplit(url).hostname or "").lower()
    return next((nazwa for klucz, nazwa in SERWISY_OPINII if klucz in host), host.removeprefix("www."))


def plik_info(klient: Path, sciezka: str) -> dict | None:
    """Typ i rozmiar pliku do tekstu linku („PDF, 240 kB”); None, gdy pliku nie ma (certyfikaty). Liczy pliki.py."""
    from . import pliki
    p = klient / sciezka
    if not p.is_file():
        return None
    i = pliki.informacje(p)
    return {"typ": i["typ"], "rozmiar": i["rozmiar"]}


def _wylicz(czesci: list[str]) -> str:
    return (", ".join(czesci[:-1]) + " i " + czesci[-1]) if len(czesci) > 1 else (czesci[0] if czesci else "")


def _wazny(c: dict, dzis: dt.date) -> bool:
    try:
        return not c.get("waznosc") or typo.na_date(c["waznosc"]) >= dzis
    except ValueError:
        return True          # zła data — błąd zgłasza schemat


def auto_firma(d: Dane, dzis: dt.date, podstrony: set, sekcje_widoczne: list) -> dict:
    """auto.zespol, auto.liczby, auto.opinie, auto.certyfikaty, auto.o_firmie_podpis, auto.o_firmie_wiecej (KONTRAKT §9.1)."""
    t = d.tresc
    wynik: dict = {}
    # zespół: zdjęcie tylko przy zgodzie osoby (art. 81 prawa autorskiego); portrety = każda osoba ma zdjęcie
    # (siatka portretów), inaczej lista w kolejności z danych — właściciel zostaje pierwszy
    osoby = [dict(o, pokaz_zdjecie=bool(o.get("zdjecie") and o.get("zgoda") is True and o["zdjecie"] in d.zdjecia))
             for o in ((t.get("zespol") or {}).get("osoby") or [])]
    wynik["zespol"] = {"osoby": osoby, "portrety": all(o["pokaz_zdjecie"] for o in osoby)} if osoby else None
    # liczby: od dwóch pozycji (jedna liczba to nie „firma w liczbach”); wartość liczbowa z grupami cyfr
    poz = (t.get("liczby") or {}).get("pozycje") or []
    wynik["liczby"] = [dict(p, wartosc_tekst=typo.liczba(p["wartosc"]) if isinstance(p["wartosc"], (int, float))
                            and not isinstance(p["wartosc"], bool) else p["wartosc"]) for p in poz] if len(poz) >= 2 else None
    # opinie: nazwa serwisu z adresu cytatu — link „opinia w serwisie Google, 12.03.2026”
    wynik["opinie"] = [dict(o, serwis=serwis_opinii(o["url"]) if o.get("url") else None)
                       for o in ((t.get("opinie") or {}).get("pozycje") or [])]
    # certyfikaty: tylko ważne (wygasłe pomijamy, kontrola ostrzega), plik z typem i rozmiarem
    cert = [dict(c, plik_info=plik_info(d.klient, c["plik"]) if c.get("plik") else None)
            for c in ((t.get("certyfikaty") or {}).get("pozycje") or []) if _wazny(c, dzis)]
    wynik["certyfikaty"] = cert or None
    # podpis zdjęcia sekcji „o firmie” z data/zdjecia.json (szablon nie sięgnie do słownika po zmiennym kluczu)
    zdj_of = (t.get("o_firmie") or {}).get("zdjecie")
    wynik["o_firmie_podpis"] = (d.zdjecia.get(zdj_of) or {}).get("podpis") if zdj_of else None
    # link ze skrótu „o firmie” na głównej do /o-firmie — wymienia to, co jest tylko tam (jak auto.kontakt_wiecej)
    czesci = []
    if "/o-firmie" in podstrony:
        if (t.get("o_firmie") or {}).get("tresc"):
            czesci.append("cały tekst o firmie")
        if osoby and "zespol" not in sekcje_widoczne:
            czesci.append(f"zespół ({len(osoby)}{typo.NBSP}{typo.liczba_mnoga(len(osoby), 'osoba,osoby,osób')})")
        if wynik["liczby"] and "liczby" not in sekcje_widoczne:
            czesci.append("dane liczbowe ze źródłami")
        if cert and "certyfikaty" not in sekcje_widoczne:
            czesci.append("certyfikaty")
    wynik["o_firmie_wiecej"] = typo.wersaliki_pierwsza(_wylicz(czesci)) or None
    return wynik


def kontrole_firma(d: Dane, raport, dzis: dt.date) -> None:
    """Kontrole sekcji o firmie — wołane z kontrole() (punkt 15)."""
    t, f = d.tresc, d.firma
    T, F = "data/tresc.json", "data/firma.json"
    omnibus = ("przy opiniach konsumentów strona musi powiedzieć, czy i jak sprawdzacie, że pochodzą od klientów "
               "(dyrektywa Omnibus, ustawa o przeciwdziałaniu nieuczciwym praktykom rynkowym)")
    op, oz = t.get("opinie"), f.get("opinie_zbiorczo")
    if oz and op is None:
        raport.blad(f"jest ocena zbiorcza (opinie_zbiorczo), a nie ma sekcji opinii ze zdaniem o weryfikacji — {omnibus}",
                    plik=F, pole="opinie_zbiorczo",
                    naprawa='dodaj w data/tresc.json "opinie": {"naglowek": null, "weryfikacja": "Cytujemy opinie z Google; '
                            'nie sprawdzamy, czy autor skorzystał z usługi.", "pozycje": []} albo wpisz "opinie_zbiorczo": null')
    if op:
        if not op["weryfikacja"].strip():
            raport.blad(f"opinie: puste zdanie o weryfikacji — {omnibus}", plik=T, pole="opinie.weryfikacja",
                        naprawa="np. \"Cytujemy opinie z Google Maps; nie weryfikujemy, czy autor skorzystał z usługi.\"")
        if not op["pozycje"] and not oz:
            raport.ostrzezenie("opinie: nie ma ani cytatów, ani oceny zbiorczej (opinie_zbiorczo) — sekcja ukryta",
                               plik=T, pole="opinie.pozycje", klasa="A")
        for i, o in enumerate(op["pozycje"]):
            if not o.get("url"):
                raport.ostrzezenie(f"opinia „{o['autor']}” bez linku do źródła — cytujemy dosłownie opinie, które da się "
                                   "sprawdzić (albo za pisemną zgodą autora)", plik=T, pole=f"opinie.pozycje[{i}].url",
                                   naprawa="dodaj adres opinii w serwisie (Google, Facebook…) albo usuń cytat — bez linku "
                                           "--produkcja go nie opublikuje")
            if re.search(r"\s[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}", o["autor"].strip()):
                raport.ostrzezenie(f"opinia: „{o['autor']}” wygląda na imię i nazwisko — podpisujemy imieniem "
                                   "i miejscowością, nazwisko tylko za zgodą autora", plik=T,
                                   pole=f"opinie.pozycje[{i}].autor", klasa="A")
    if oz:
        try:
            wiek = (dzis - typo.na_date(oz["data"])).days
        except ValueError:
            wiek = 0
        if wiek > 183:
            raport.ostrzezenie(f"ocena zbiorcza ma datę {typo.data_krotka(oz['data'])} — starsza niż pół roku; zaktualizuj "
                               "ocenę, liczbę opinii i datę", plik=F, pole="opinie_zbiorczo.data")
    for i, o in enumerate(((t.get("zespol") or {}).get("osoby") or [])):
        if o.get("zdjecie") and o.get("zgoda") is not True:
            raport.ostrzezenie(f"zespół: „{o['imie']}” ma zdjęcie bez zgody na publikację wizerunku — zdjęcie się nie "
                               "pokaże", plik=T, pole=f"zespol.osoby[{i}].zgoda", klasa="A",
                               naprawa="wpisz \"zgoda\": true po uzyskaniu zgody (art. 81 prawa autorskiego) albo \"zdjecie\": null")
        elif o.get("zdjecie") and o["zdjecie"] in d.zdjecia and not d.zdjecia[o["zdjecie"]].get("osoby"):
            raport.ostrzezenie(f"zdjęcie „{o['zdjecie']}” pokazuje osobę z zespołu — oznacz je \"osoby\": true i \"zgoda\": true",
                               plik="data/zdjecia.json", pole=f"{o['zdjecie']}.osoby", klasa="A")
    liczby = (t.get("liczby") or {}).get("pozycje") or []
    if len(liczby) == 1:
        raport.ostrzezenie("liczby: jedna pozycja — sekcja pokazuje się od dwóch; pojedynczą liczbę wpisz w o_firmie.fakty "
                           "albo w tekst", plik=T, pole="liczby.pozycje", klasa="A")
    fakty = " ".join(x["wartosc"] for x in ((t.get("o_firmie") or {}).get("fakty") or []))
    for i, p in enumerate(liczby):
        if not p.get("data"):
            raport.ostrzezenie(f"liczby: „{p['opis']}” bez daty — przy liczbie podajemy, na kiedy jest aktualna (stan na …)",
                               plik=T, pole=f"liczby.pozycje[{i}].data", klasa="A")
        w = getattr(p["wartosc"], "tekst", None) or str(p["wartosc"])
        if len(w) >= 2 and re.search(r"(?<![\d,.])" + re.escape(w) + r"(?![\d,])", fakty):
            raport.ostrzezenie(f"liczba „{w}” stoi i w liczbach, i w o_firmie.fakty — jedna informacja w jednym miejscu",
                               plik=T, pole=f"liczby.pozycje[{i}]", klasa="A")
    for i, c in enumerate(((t.get("certyfikaty") or {}).get("pozycje") or [])):
        pole = f"certyfikaty.pozycje[{i}]"
        if c.get("plik"):
            if not c["plik"].startswith("assets/img/"):
                raport.blad(f"plik certyfikatu „{c['plik']}” musi leżeć w assets/img/ (tylko stamtąd trafia do dist/)",
                            plik=T, pole=f"{pole}.plik", naprawa="np. \"assets/img/pliki/iso-9001.pdf\"")
            elif not (d.klient / c["plik"]).is_file():
                raport.blad(f"nie ma pliku {c['plik']}", plik=T, pole=f"{pole}.plik",
                            naprawa="skopiuj skan do tego katalogu albo wpisz \"plik\": null")
        if not _wazny(c, dzis):
            raport.ostrzezenie(f"certyfikat „{c['nazwa']}” wygasł {typo.data_krotka(c['waznosc'])} — nie pokazujemy go",
                               plik=T, pole=f"{pole}.waznosc", klasa="A")
        if c.get("rok") and c["rok"] > dzis.year:
            raport.blad(f"certyfikat „{c['nazwa']}”: rok {c['rok']} jest w przyszłości", plik=T, pole=f"{pole}.rok")
    if f["funkcje"].get("faq_schema") and not t.get("faq"):
        raport.ostrzezenie("funkcje.faq_schema = true, ale nie ma pytań (tresc.faq) — FAQPage nie powstanie", plik=F,
                           pole="funkcje.faq_schema", klasa="A")


def kontrole_publikacji(d: Dane, raport, dzis: dt.date) -> None:
    """Przekierowania ze starych adresów (firma.przekierowania → dist/_redirects) i dane strony /dostepnosc.
    Zderzenie przekierowania ze stroną, która powstaje, sprawdza build (naglowki.przekierowania) — zna listę stron."""
    f = d.firma
    F = "data/firma.json"
    przek = f.get("przekierowania") or []
    widziane = set()
    for i, r in enumerate(przek):
        pole = f"przekierowania[{i}]"
        z, do = r["z"], r["do"]
        if z in widziane:
            raport.blad(f"powtórzone przekierowanie z „{z}”", plik=F, pole=f"{pole}.z", naprawa="zostaw jeden wpis")
        widziane.add(z)
        if z.rstrip("/") == do.rstrip("/"):
            raport.blad(f"przekierowanie „{z}” prowadzi samo do siebie", plik=F, pole=pole)
        if z == "/" or z.startswith("/api/") or z.startswith("/assets/"):
            raport.blad(f"nie można przekierować „{z}” (strona główna, /api/ i /assets/ są zarezerwowane)", plik=F,
                        pole=f"{pole}.z")
    if przek and f["funkcje"].get("hosting") == "github_pages":
        raport.ostrzezenie("GitHub Pages nie czyta pliku _redirects — przekierowania ze starych adresów nie zadziałają",
                           plik=F, pole="przekierowania", klasa="A")
    if len(przek) > 2000:
        raport.blad(f"{len(przek)} przekierowań — Cloudflare przyjmuje najwyżej 2000", plik=F, pole="przekierowania")
    dos = f.get("dostepnosc")
    if dos and not f["funkcje"].get("strona_dostepnosci"):
        raport.ostrzezenie("są dane w „dostepnosc”, ale funkcje.strona_dostepnosci = false — strona /dostepnosc nie powstanie",
                           plik=F, pole="funkcje.strona_dostepnosci", klasa="A")
    if dos:
        data = typo.na_date(dos["data_oceny"])
        if data and data > dzis:
            raport.blad(f"data oceny dostępności {typo.data_krotka(dos['data_oceny'])} jest w przyszłości", plik=F,
                        pole="dostepnosc.data_oceny")
        elif data and (dzis - data).days > 365:
            raport.ostrzezenie(f"ocena dostępności z {typo.data_krotka(dos['data_oceny'])} ma ponad rok — sprawdź stronę ponownie",
                               plik=F, pole="dostepnosc.data_oceny")
        if dos["zgodnosc"] == "pelna" and dos.get("niedostepne"):
            raport.blad("zgodność „pelna”, a lista „niedostepne” nie jest pusta", plik=F, pole="dostepnosc.zgodnosc",
                        naprawa="\"zgodnosc\": \"czesciowa\" albo \"niedostepne\": null")
        if dos["metoda"] == "audyt" and not dos.get("wykonawca"):
            raport.blad("audyt dostępności bez wykonawcy", plik=F, pole="dostepnosc.wykonawca",
                        naprawa="wpisz, kto przeprowadził audyt, albo \"metoda\": \"samoocena\"")

# ----------------------------------------------------------------------------- godziny świąteczne (tools/swieta.py)

def kontrole_swiat(d: Dane, raport, dzis: dt.date) -> None:
    """Święto za ≤ 45 dni, w dzień zwykle otwarty, bez wpisu w godziny.wyjatki → „POTWIERDŹ: godziny na 24.12 (Wigilia)”.

    Tylko branże z godzinami dla klientów (preset „pokazuj_status_w_hero”: restauracja, usługi, gabinet) — biuro firmy
    budowlanej czy producenta nie potrzebuje przypomnienia. Ostrzeżenie klasy A (D12): przypomina o niepotwierdzonym
    fakcie jak do_potwierdzenia (D10) i nie blokuje nocnego buildu --produkcja — w 45 dniach prawie zawsze jest święto.
    """
    g = d.firma.get("godziny")
    if not g or not d.preset.get("pokazuj_status_w_hero"):
        return
    import swieta          # tools/swieta.py — katalog tools/ jest na ścieżce, skoro zaimportowano pakiet silnik
    for s in swieta.do_potwierdzenia(g.get("tydzien"), g.get("wyjatki"), dzis, 45):
        raport.ostrzezenie(swieta.komunikat(s), plik="data/firma.json", pole="godziny.wyjatki",
                           naprawa=f'dopisz {{"data": "{s.data.isoformat()}", "godziny": [], "opis": "{s.nazwa}"}} '
                                   '(zamknięte) albo godziny tego dnia, np. [["10:00", "14:00"]]', klasa="A")
