"""Zasoby: sklejanie CSS i JS, @font-face wybranych krojów, tokeny :root, kopiowanie assets/ do dist/ (KONTRAKT §7, §11).

Kolejność CSS: [@font-face + zamienniki] → [:root z tokenami marki] → [object-position zdjęć] →
assets/css/czesci/*.css (alfabetycznie — numer na początku nazwy ustala kolejność) → assets/css/wlasne.css klienta.
Kolejność JS: assets/js/czesci/*.js alfabetycznie. Adresy w HTML (także fonty w @font-face i preload, og.jpg, logo
w JSON-LD, ikony w site.webmanifest) dostają ?v=<skrót zawartości> — /assets/* jest w pamięci przeglądarki rok.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

# jedyny skrypt w HTML — jego skrót sha256 trafia do CSP (naglowki.py)
INLINE_JS = "document.documentElement.classList.add('js')"

ZAKRES = ("U+0000-00FF, U+0104-0107, U+0118-0119, U+0141-0144, U+015A-015B, U+0179-017C, U+2013-2014, "
          "U+2018-201A, U+201C-201E, U+2022, U+2026, U+20AC, U+2122, U+2212")
STOSY = {"sans": 'Arial, Helvetica, sans-serif', "serif": '"Times New Roman", Times, serif'}


def skrot(dane: bytes) -> str:
    return hashlib.sha256(dane).hexdigest()[:10]


def _plik_dla_wagi(wpis: dict, waga: int) -> dict:
    """Plik kroju, który obejmuje wagę (zmienny „400 700”) albo ma najbliższą wagę (statyczny)."""
    def odl(p):
        w = [int(x) for x in p["waga"].split()]
        return 0 if len(w) == 2 and w[0] <= waga <= w[1] else min(abs(x - waga) for x in w)
    return min(wpis["pliki"], key=odl)


def _waga_dostepna(wpis: dict, waga: int) -> int:
    p = _plik_dla_wagi(wpis, waga)
    w = [int(x) for x in p["waga"].split()]
    return waga if len(w) == 2 and w[0] <= waga <= w[1] else min(w, key=lambda x: abs(x - waga))


def uzyte_pliki(katalog: dict, marka: dict) -> dict[str, list[dict]]:
    """id kroju → pliki, których strona naprawdę używa (wagi --fw-naglowki, --fw-tekst, --fw-mocna). Krój statyczny
    ma plik na wagę — nieużywanej wagi nie deklarujemy w @font-face i nie kopiujemy do dist/."""
    naglowki, tekst = katalog[marka["font_naglowki"]], katalog[marka["font_tekst"]]
    potrzebne = [(marka["font_naglowki"], _plik_dla_wagi(naglowki, naglowki.get("waga_naglowkow", 600))),
                 (marka["font_tekst"], _plik_dla_wagi(tekst, tekst.get("waga_tekstu", 400))),
                 (marka["font_tekst"], _plik_dla_wagi(tekst, tekst.get("waga_mocna", 600)))]
    wynik: dict[str, list[dict]] = {}
    for kid, plik in potrzebne:
        lista = wynik.setdefault(kid, [])
        if plik not in lista:
            lista.append(plik)
    return wynik


def fonty_css(katalog: dict, marka: dict, skroty=None) -> tuple[str, dict, list[str]]:
    """(CSS @font-face, tokeny krojów, lista plików do preloadu — ścieżki względem assets/fonts/).
    Adres w url() ma ?v=<skrót> — ten sam co w <link rel="preload"> (inaczej przeglądarka pobierze font dwa razy)."""
    naglowki, tekst = katalog[marka["font_naglowki"]], katalog[marka["font_tekst"]]
    css = []
    for kid, pliki in uzyte_pliki(katalog, marka).items():
        w = katalog[kid]
        for p in pliki:
            h = skroty(f"assets/fonts/{p['plik']}") if skroty else None
            css.append(f'@font-face{{font-family:"{w["nazwa"]}";src:url(../fonts/{p["plik"]}{"?v=" + h if h else ""}) '
                       f'format("woff2");font-weight:{p["waga"]};font-style:{p.get("styl_kroju", "normal")};'
                       f'font-display:swap;unicode-range:{ZAKRES}}}')
        z = w["zamiennik"]
        lokalne = ",".join(f'local("{n}")' for n in z["lokalny"])
        css.append(f'@font-face{{font-family:"{w["nazwa"]} zamiennik";src:{lokalne};size-adjust:{z["size_adjust"]};'
                   f'ascent-override:{z["ascent"]};descent-override:{z["descent"]};line-gap-override:{z["line_gap"]}}}')
    stos = lambda w: f'"{w["nazwa"]}", "{w["nazwa"]} zamiennik", {STOSY[w["styl"]]}'
    tokeny = {
        "--font-naglowki": stos(naglowki),
        "--font-tekst": stos(tekst),
        "--fw-naglowki": str(_waga_dostepna(naglowki, naglowki.get("waga_naglowkow", 600))),
        "--fw-tekst": str(_waga_dostepna(tekst, tekst.get("waga_tekstu", 400))),
        "--fw-mocna": str(_waga_dostepna(tekst, tekst.get("waga_mocna", 600))),
    }
    preload = list(dict.fromkeys([
        _plik_dla_wagi(naglowki, naglowki.get("waga_naglowkow", 600))["plik"],
        _plik_dla_wagi(tekst, tekst.get("waga_tekstu", 400))["plik"],
    ]))
    return "\n".join(css), tokeny, preload


def zbuduj_css(korzen: Path, klient: Path, katalog_fontow: dict, marka: dict, tokeny_kolorow: dict,
               css_punkty: str, skroty=None, pomin=frozenset(), bloki=None) -> tuple[str, list[str]]:
    """`pomin` — nazwy plików z czesci/ niepotrzebnych tej stronie (91-ruch.css bez funkcje.animacje = "wejscie").
    `bloki` — bloki klas użyte na stronie (`uzyte_bloki`); gdy podane, z plików sekcji (czesci/1*.css) znikają reguły
    sekcji, których strona nie ma (limit CSS 60 KB, KONTRAKT §10)."""
    fonty, tokeny_fontow, preload = fonty_css(katalog_fontow, marka, skroty)
    promien = marka.get("promien", 2)
    tokeny = {**tokeny_kolorow, **tokeny_fontow,
              # zdjęcia zawsze bez zaokrągleń: na telefonie część jest na całą szerokość (0), część nie — 4 px tu
              # i 0 tam wyglądało na przypadek; marka.promien dotyczy tylko przycisków i pól
              "--radius-ctl": f"{promien}px", "--radius-img": "0",
              "--logo-szer": f"{marka.get('logo_szerokosc') or 140}px"}
    czesci = ["/* SZABLON — plik generowany przez tools/build.py, nie edytuj. Źródła: assets/css/czesci/, "
              "assets/css/wlasne.css, tokeny: data/firma.json → marka */",
              fonty,
              ":root{" + ";".join(f"{k}:{v}" for k, v in tokeny.items()) + "}"]
    if css_punkty:
        czesci.append(css_punkty)
    for plik in sorted((korzen / "assets" / "css" / "czesci").glob("*.css")):
        if plik.name in pomin:
            continue
        tekst = bez_komentarzy(plik.read_text(encoding="utf-8")).strip()
        if bloki is not None and plik.name.startswith("1"):
            tekst = przytnij_css(tekst, bloki)
        czesci.append(f"/* {plik.name} */\n" + tekst)
    wlasne = klient / "assets" / "css" / "wlasne.css"
    tekst_wlasny = bez_komentarzy(wlasne.read_text(encoding="utf-8")).strip() if wlasne.is_file() else ""
    if tekst_wlasny:
        czesci.append("/* wlasne.css (klient) */\n" + tekst_wlasny)
    return "\n".join(czesci) + "\n", preload


# ----------------------------------------------------------------------------- przycinanie CSS sekcji

_RE_KLASA = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
_RE_SLOWO = re.compile(r"[a-zA-Z][\w-]*")
_BLOKOWE_AT = ("@media", "@supports", "@container", "@layer")


def bez_komentarzy(css: str) -> str:
    """Komentarze źródeł CSS nie jadą do przeglądarki (ok. 10 KB); zostają tylko zwolnienia „slop-ok” dla lint_slop."""
    return re.sub(r"[ \t]*/\*(?:(?!slop-ok).)*?\*/[ \t]*\n?", "", css, flags=re.S)


def blok_klasy(klasa: str) -> str:
    """BEM: „oferta__cena--od” → „oferta”."""
    return klasa.split("__", 1)[0].split("--", 1)[0]


def uzyte_bloki(html_teksty, js_teksty) -> set[str]:
    """Bloki klas z atrybutów class="…" stron i każde słowo z JS (klasy dodawane skryptem: is-open, mapa__ramka, js)."""
    wynik = set()
    for t in html_teksty:
        for m in re.finditer(r'\sclass="([^"]*)"', t):
            wynik |= {blok_klasy(k) for k in m.group(1).split()}
    for t in js_teksty:
        wynik |= {blok_klasy(k) for k in _RE_SLOWO.findall(t)}
    return wynik


def _bez_funkcji(selektor: str) -> str:
    """Usuwa argumenty :not() :has() :is() :where() :nth-…() — klasa w nich nie przesądza, że reguła jest martwa —
    i atrybuty ([href$=".pdf"] to nie klasa „pdf”)."""
    selektor = re.sub(r"\[[^\]]*\]", "", selektor)
    wynik, i = [], 0
    while i < len(selektor):
        if selektor[i] == "(":
            gl = 1
            i += 1
            while i < len(selektor) and gl:
                gl += {"(": 1, ")": -1}.get(selektor[i], 0)
                i += 1
            continue
        wynik.append(selektor[i])
        i += 1
    return "".join(wynik)


def _martwy(selektor: str, bloki: set) -> bool:
    return any(blok_klasy(k) not in bloki for k in _RE_KLASA.findall(_bez_funkcji(selektor)))


def _koniec_bloku(css: str, i: int) -> int:
    """Indeks za „}” zamykającym blok otwarty przez „{” na pozycji i (z pominięciem komentarzy i napisów)."""
    gl, n = 0, len(css)
    while i < n:
        c = css[i]
        if css.startswith("/*", i):
            i = css.find("*/", i + 2)
            i = n if i < 0 else i + 2
            continue
        if c in "\"'":
            j = i + 1
            while j < n and css[j] != c:
                j += 2 if css[j] == "\\" else 1
            i = j + 1
            continue
        if c == "{":
            gl += 1
        elif c == "}":
            gl -= 1
            if gl == 0:
                return i + 1
        i += 1
    return n


def przytnij_css(css: str, bloki: set) -> str:
    """Zostawia reguły, w których choć jeden selektor może trafić w stronę; @media/@supports przycinane w środku
    (puste znikają), pozostałe @-reguły (@keyframes, @page) i komentarze bez zmian."""
    wynik, i, n = [], 0, len(css)
    while i < n:
        if css[i].isspace():
            wynik.append(css[i])
            i += 1
            continue
        if css.startswith("/*", i):
            j = css.find("*/", i + 2)
            j = n if j < 0 else j + 2
            wynik.append(css[i:j])
            i = j
            continue
        klamra = css.find("{", i)
        srednik = css.find(";", i)
        if css[i] == "@" and (klamra < 0 or 0 <= srednik < klamra):          # @import, @charset
            wynik.append(css[i:srednik + 1])
            i = srednik + 1
            continue
        if klamra < 0:
            wynik.append(css[i:])
            break
        koniec = _koniec_bloku(css, klamra)
        naglowek = css[i:klamra]
        if naglowek.lstrip().startswith(_BLOKOWE_AT):
            srodek = przytnij_css(css[klamra + 1:koniec - 1], bloki)
            if srodek.strip() and re.sub(r"/\*.*?\*/", "", srodek, flags=re.S).strip():
                wynik.append(naglowek + "{" + srodek + "}")
        elif naglowek.lstrip().startswith("@") or \
                not all(_martwy(sel, bloki) for sel in _podziel_selektory(naglowek)):
            wynik.append(css[i:koniec])
        i = koniec
    return re.sub(r"\n{3,}", "\n\n", "".join(wynik))


def _podziel_selektory(naglowek: str) -> list[str]:
    """„a, b:is(c, d)” → ["a", "b:is(c, d)"] — przecinki w nawiasach nie dzielą."""
    czesci, gl, biezacy = [], 0, []
    for c in naglowek:
        if c == "(":
            gl += 1
        elif c == ")":
            gl -= 1
        if c == "," and gl == 0:
            czesci.append("".join(biezacy))
            biezacy = []
        else:
            biezacy.append(c)
    czesci.append("".join(biezacy))
    return czesci


def zbuduj_js(korzen: Path) -> str:
    czesci = ["/* SZABLON — plik generowany przez tools/build.py, nie edytuj. Źródła: assets/js/czesci/ */"]
    for plik in sorted((korzen / "assets" / "js" / "czesci").glob("*.js")):
        czesci.append(f"/* {plik.name} */\n" + plik.read_text(encoding="utf-8").strip())
    return "\n".join(czesci) + "\n"


def kopiuj(korzen: Path, klient: Path, dist: Path, katalog_fontow: dict, marka: dict) -> None:
    """assets/img klienta i wybrane kroje → dist/assets/."""
    img = klient / "assets" / "img"
    if img.is_dir():
        for plik in img.rglob("*"):
            if plik.is_file() and plik.name != "manifest.json" and not plik.name.startswith("."):
                cel = dist / "assets" / "img" / plik.relative_to(img)
                cel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(plik, cel)
        ico = img / "ikony" / "favicon.ico"
        if ico.is_file():
            shutil.copy2(ico, dist / "favicon.ico")
    for kid, pliki in uzyte_pliki(katalog_fontow, marka).items():
        w = katalog_fontow[kid]
        for p in pliki:
            cel = dist / "assets" / "fonts" / p["plik"]
            cel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(korzen / "assets" / "fonts" / p["plik"], cel)
        lic = korzen / "assets" / "fonts" / w.get("licencja", "")
        if lic.is_file():
            shutil.copy2(lic, dist / "assets" / "fonts" / w["licencja"])


class Skroty:
    """Skróty zawartości plików w dist/ (do ?v=) — liczone raz na plik."""

    def __init__(self, dist: Path):
        self.dist = dist
        self._pamiec: dict[str, str | None] = {}

    def __call__(self, sciezka: str) -> str | None:
        sciezka = sciezka.lstrip("/")
        if sciezka not in self._pamiec:
            p = self.dist / sciezka
            self._pamiec[sciezka] = skrot(p.read_bytes()) if p.is_file() else None
        return self._pamiec[sciezka]
