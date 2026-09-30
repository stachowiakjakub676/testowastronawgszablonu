"""Strony do zbudowania, sekcje strony głównej, nawigacja, okruszki i meta (KONTRAKT §6, D4).

Nagłówek pliku strony (src/strony/*.html), wartości mogą zawierać {{ … }}:
    {# strona: sciezka="/realizacje" sekcja="realizacje przetargi" nav="Realizacje" tytul="Realizacje"
               opis="…" wymaga="tresc.realizacje.pozycje|tresc.przetargi.pozycje" rodzic="/oferta"
               kolekcja="oferta" indeksuj="nie" h1="…" #}
- sekcja    — id sekcji (spacją), które ta strona pokazuje w pełnej wersji; nawigacja wskazuje wtedy stronę, nie kotwicę;
- kolekcja  — strona powstaje raz na element (oferta → /oferta/<slug>, aktualnosci → /aktualnosci/<slug>);
              w szablonie element jest pod zmienną `element`, a w ścieżce {slug};
- indeksuj="nie" — noindex i poza mapą strony (404, dziękujemy, błąd).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from . import typografia as typo
from .szablony import prawda

ZAWSZE = {"index", "kontakt", "polityka-prywatnosci", "404", "dziekujemy", "blad", "blad-formularz", "blad-konfiguracja"}
# strony błędów formularza bez JS (Worker przekierowuje na nie z ?powod=<kod>) — tylko przy formularzu przez Workera
TYLKO_WORKER = {"blad-formularz", "blad-konfiguracja"}
BEZ_MIASTA = {"polityka-prywatnosci", "dostepnosc"}
ID_HTML = {"o_firmie": "o-firmie", "do_pobrania": "do-pobrania", "gdzie_kupic": "gdzie-kupic"}


def html_id(sekcja_id: str) -> str:
    return ID_HTML.get(sekcja_id, sekcja_id.replace("_", "-"))


@dataclass
class Strona:
    nazwa: str                 # nazwa pliku bez .html
    plik: str                  # "strony/kontakt.html"
    sciezka: str               # "/kontakt"
    wyjscie: str               # "kontakt.html"
    naglowek: dict
    element: dict | None = None
    indeksuj: bool = True
    sekcje: list = field(default_factory=list)

    @property
    def glebokosc(self) -> int:
        return self.wyjscie.count("/")


def _slowa_md(d, sciezka: str | None) -> int:
    if not sciezka:
        return 0
    p = d.klient / "data" / sciezka.removeprefix("data/")
    return typo.liczba_slow(p.read_text(encoding="utf-8")) if p.is_file() else 0


def _dl(v) -> int:
    return len(v) if isinstance(v, list) else 0


def _uslugi(d) -> tuple[list, list]:
    """Pozycje oferty, które zasługują na własną podstronę (KONTRAKT §6.1, critic §4.5)."""
    tak, nie = [], []
    for p in ((d.tresc.get("oferta") or {}).get("pozycje") or []):
        slowa = _slowa_md(d, p.get("tresc"))
        if p.get("tresc") and slowa >= 150 and p.get("zdjecie") and (p.get("cena") is not None or p.get("zakres") or p.get("czas")):
            tak.append(p)
        elif p.get("tresc"):
            powod = "za mało treści" if slowa < 150 else ("brak zdjęcia" if not p.get("zdjecie") else "brak ceny, zakresu i czasu")
            nie.append((p, f"{powod}: {slowa} słów"))
    return tak, nie


def _menu_podstrona(d) -> bool:
    """/menu powstaje, gdy pełna karta pokazuje coś, czego skrót na głównej nie ma: alergeny, PDF albo wyraźnie więcej
    dań. Kilka nazw więcej to nie powód do osobnej strony — wtedy cała karta stoi na głównej (critic §4.5)."""
    menu = d.tresc.get("menu") or {}
    pozycje = [p for k in menu.get("kategorie") or [] for p in k["pozycje"]]
    if not pozycje:
        return False
    limit = d.preset.get("limity", {}).get("menu") or len(pozycje)
    return bool(menu.get("pdf")) or any(p.get("alergeny") for p in pozycje) or len(pozycje) > limit + 6


def _kariera(d, dzis: dt.date) -> list:
    poz = ((d.tresc.get("kariera") or {}).get("pozycje") or [])
    return [p for p in poz if not p.get("wazne_do") or typo.na_date(p["wazne_do"]) >= dzis]


def _aktualnosci_stare(d, dzis: dt.date, raport) -> bool:
    """Najnowszy wpis starszy niż 12 miesięcy → zapowiedź na stronie głównej znika (martwy blok „Aktualności”
    wygląda jak porzucona firma), a /aktualnosci i wpisy zostają. Ostrzeżenie klasy A: nocny build nie może stanąć
    tylko dlatego, że firma rok niczego nie napisała."""
    najnowszy = d.aktualnosci[0]["data"] if d.aktualnosci else None
    if not najnowszy or (dzis - typo.na_date(najnowszy)).days <= 365:
        return False
    raport.ukryto(f"sekcja „aktualnosci” na stronie głównej (najnowszy wpis z {typo.data_krotka(najnowszy)})")
    raport.ostrzezenie(f"najnowszy wpis w aktualnościach jest z {typo.data_krotka(najnowszy)} — starszy niż 12 miesięcy, "
                       "więc nie ma go na stronie głównej", plik=f"data/aktualnosci/{d.aktualnosci[0]['slug']}.md",
                       naprawa="dodaj nowy wpis albo usuń nieaktualne", klasa="A")
    return True


def progi(d, dzis: dt.date) -> dict:
    """nazwa strony → (czy powstaje, powód gdy nie)."""
    t = d.tresc
    of = t.get("oferta") or {}
    realiz = t.get("realizacje") or {}
    przet = t.get("przetargi") or {}
    ofi = t.get("o_firmie") or {}
    zesp = t.get("zespol") or {}
    return {
        "oferta": (_dl(of.get("pozycje")) >= 4 or bool(t.get("cennik")), "oferta ma mniej niż 4 pozycje i nie ma cennika"),
        "menu": (_menu_podstrona(d), "karta mieści się na stronie głównej (bez alergenów i PDF, pozycji ≤ limit skrótu + 6)"),
        "realizacje": (_dl(realiz.get("pozycje")) > 6 or _dl(przet.get("pozycje")) > 8,
                       "realizacji ≤ 6 i przetargów ≤ 8 — wszystko mieści się na stronie głównej"),
        "produkty": (_dl((t.get("produkty") or {}).get("pozycje")) > 6, "produktów ≤ 6 — mieszczą się na stronie głównej"),
        "o-firmie": (_slowa_md(d, ofi.get("tresc")) > 250 or _dl(zesp.get("osoby")) >= 4,
                     "tekst „o firmie” ≤ 250 słów i zespół < 4 osób — mieści się na stronie głównej"),
        "aktualnosci": (bool(d.aktualnosci), "brak wpisów w data/aktualnosci/"),
        "kariera": (bool(_kariera(d, dzis)), "brak aktualnych ofert pracy"),
        "dostepnosc": (bool(d.firma["funkcje"].get("strona_dostepnosci")), "funkcje.strona_dostepnosci = false"),
    }


def plan(silnik, d, raport, kontekst: dict, dzis: dt.date) -> tuple[list[Strona], list[str]]:
    """Lista stron do zbudowania i lista sekcji widocznych na stronie głównej."""
    # 1. sekcje strony głównej
    widoczne = []
    for sid in d.preset.get("sekcje_glowna", []):
        plik = f"sekcje/{sid}.html"
        if not silnik.istnieje(plik):
            raport.info(f"sekcja „{sid}” nie ma jeszcze pliku src/{plik} — pominięto")
            continue
        braki = silnik.niespelnione(silnik.szablon(plik).wymaga, kontekst)
        if braki:
            raport.ukryto(f"sekcja „{sid}” (brak danych: {', '.join(braki)})")
            continue
        if sid == "aktualnosci" and _aktualnosci_stare(d, dzis, raport):
            continue
        widoczne.append(sid)
    # 2. strony
    dozwolone = set(d.preset.get("strony", [])) | ZAWSZE
    p = progi(d, dzis)
    strony: list[Strona] = []
    for plik in sorted((silnik.katalog / "strony").glob("*.html")):
        nazwa = plik.stem
        sz = silnik.szablon(f"strony/{plik.name}")
        nagl = sz.strona
        if nagl is None or "sciezka" not in nagl:
            raport.blad("brak nagłówka {# strona: sciezka=\"/…\" … #} w pierwszej linii", plik=f"src/strony/{plik.name}")
            continue
        if nazwa not in dozwolone:
            continue
        if nazwa in TYLKO_WORKER and ((d.firma["funkcje"].get("formularz") or {}).get("tryb")) != "worker":
            continue
        if nazwa in p and not p[nazwa][0]:
            raport.ukryto(f"podstrona „{nagl['sciezka']}” ({p[nazwa][1]})")
            continue
        if nagl.get("wymaga"):
            braki = silnik.niespelnione(nagl["wymaga"], kontekst)
            if braki:
                raport.ukryto(f"podstrona „{nagl['sciezka']}” (brak danych: {', '.join(braki)})")
                continue
        indeksuj = nagl.get("indeksuj", "tak") != "nie"
        sekcje = [s for s in re.split(r"[\s,]+", nagl.get("sekcja", "")) if s]
        kolekcja = nagl.get("kolekcja")
        if kolekcja:
            if kolekcja == "oferta":
                elementy, odrzucone = _uslugi(d)
                for poz, powod in odrzucone:
                    raport.ukryto(f"podstrona usługi „{poz['nazwa']}” ({powod})")
            elif kolekcja == "aktualnosci":
                elementy = d.aktualnosci
            elif kolekcja == "kariera":
                elementy = _kariera(d, dzis)
            else:
                raport.blad(f"nieznana kolekcja „{kolekcja}” (dostępne: oferta, aktualnosci, kariera)",
                            plik=f"src/strony/{plik.name}")
                continue
            for el in elementy:
                sc = nagl["sciezka"].replace("{slug}", el["slug"])
                strony.append(Strona(nazwa, f"strony/{plik.name}", sc, sc.strip("/") + ".html", nagl, el, indeksuj, sekcje))
            continue
        sc = nagl["sciezka"]
        wyj = "index.html" if sc == "/" else sc.strip("/") + ".html"
        strony.append(Strona(nazwa, f"strony/{plik.name}", sc, wyj, nagl, None, indeksuj, sekcje))
    # strona główna pierwsza, potem wg ścieżki
    strony.sort(key=lambda s: (s.sciezka != "/", s.sciezka))
    return strony, widoczne


def nawigacja(strony: list[Strona], widoczne: list[str], d) -> list[dict]:
    """Maks. 6 pozycji w kolejności z presetu; podstrona, jeśli powstała, inaczej kotwica na głównej."""
    etykiety = d.preset.get("nav_etykiety", {})
    wynik, uzyte = [], set()
    for sid in d.preset.get("nav", []):
        if sid in d.tresc and not d.tresc.get(sid):
            continue      # sekcja bez danych: strona z kilkoma sekcjami (/oferta = oferta + cennik) nie dostaje cudzej etykiety
        strona = next((s for s in strony if sid in s.sekcje and s.element is None), None)
        if sid == "kontakt":
            strona = next((s for s in strony if s.sciezka == "/kontakt"), None)
        if strona:
            href = strona.sciezka
            etykieta = strona.naglowek.get("nav") or etykiety.get(sid, sid)
        elif sid in widoczne:
            href = "/#" + html_id(sid)
            etykieta = etykiety.get(sid, sid)
        else:
            continue
        if href in uzyte:
            continue
        uzyte.add(href)
        wynik.append({"id": sid, "etykieta": etykieta, "href": href})
    return wynik[:6]


def tytul(strona: Strona, tytul_strony: str, d) -> str:
    f = d.firma
    nazwa = f["firma"]["nazwa"]
    fraza, miasto = f["seo"].get("fraza") or "", f["seo"].get("miasto") or ""
    tryb = f["funkcje"].get("tytul_tryb", "fraza")
    if strona.sciezka == "/":
        if tryb == "marka":
            return nazwa
        pelny = f"{fraza} {miasto} – {nazwa}" if miasto.lower() not in fraza.lower() else f"{fraza} – {nazwa}"
        return pelny if len(pelny) <= 60 else f"{fraza} – {nazwa}"
    # podstrony w tym samym kształcie co główna (D4): „Realizacje Rogoźno – BIMEX” — miasto przed myślnikiem,
    # żeby nie czytało się jak część nazwy marki („BIMEX Rogoźno”); bez miasta na stronach prawnych i systemowych
    if tryb == "fraza" and miasto and strona.indeksuj and strona.nazwa not in BEZ_MIASTA \
            and miasto.lower() not in tytul_strony.lower():
        z_miastem = f"{tytul_strony} {miasto} – {nazwa}"
        if len(z_miastem) <= 60:
            return z_miastem
    return f"{tytul_strony} – {nazwa}"


def okruszki(strona: Strona, tytul_strony: str, strony: list[Strona], renderuj=None) -> list[dict]:
    """renderuj(tekst) — wartość nagłówka strony nadrzędnej może zawierać {{ … }} (np. tytuł /oferta z nagłówka sekcji)."""
    if strona.sciezka == "/" or not strona.indeksuj:
        return []
    wynik = [{"nazwa": "Strona główna", "url": "/"}]
    rodzic = strona.naglowek.get("rodzic")
    if rodzic:
        r = next((s for s in strony if s.sciezka == rodzic and s.element is None), None)
        if r:
            nazwa = r.naglowek.get("nav") or r.naglowek.get("tytul") or rodzic
            if renderuj and ("{{" in nazwa or "{%" in nazwa):
                nazwa = renderuj(nazwa)
            wynik.append({"nazwa": nazwa, "url": rodzic})
    wynik.append({"nazwa": tytul_strony, "url": None})
    return wynik
