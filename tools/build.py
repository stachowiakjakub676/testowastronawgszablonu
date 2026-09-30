#!/usr/bin/env python3
"""Build strony: walidacja danych → render szablonów → kontrole wyniku → dist/ (KONTRAKT §9).

Użycie:
  python3 tools/build.py                          sprawdzenie pełne (ostrzeżenia nie przerywają)
  python3 tools/build.py --szybko                 render + walidacja danych, bez kontroli wyniku
  python3 tools/build.py --produkcja              ostrzeżenia = błędy; dane przykładowe = błąd (Cloudflare)
  python3 tools/build.py --klient przyklady/bimex katalog klienta (data/, assets/img/, assets/css/wlasne.css)
  python3 tools/build.py --wyjscie dist-test      katalog wyniku (domyślnie dist)
  python3 tools/build.py --plik                   linki względne z .html — podgląd z dysku (file://, iPad)
  python3 tools/build.py --json                   komunikaty jako JSON (dla AI)

Kod wyjścia: 0 = OK, 1 = błędy danych albo kontroli, 2 = błąd wewnętrzny.
Tylko biblioteka standardowa Pythona ≥ 3.10.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN / "tools"))

from silnik import dane as dane_mod  # noqa: E402
from silnik import jsonld, kolory, kontrole, naglowki, strony as strony_mod, zasoby  # noqa: E402
from silnik import oferta as oferta_mod  # noqa: E402
from silnik.komunikaty import BLAD, INFO, OSTRZEZENIE, UKRYTO, Raport  # noqa: E402
from silnik.obrazy import Obrazy, wymiary  # noqa: E402
from silnik.szablony import BladSzablonu, Markup, Silnik  # noqa: E402
from silnik.typografia import liczba_mnoga, sierotki_html  # noqa: E402


LOGO_MAX_WYS = 56   # px — najwyższe logo w nagłówku (72 px − 2 × 8 px), zgodnie z 02-uklad.css i tools/zdjecia.py


class Srodowisko:
    """Usługi dla szablonów zależne od buildu: adresy, zasoby z ?v=, obrazy, sekcje bieżącej strony."""

    def __init__(self, d, dist: Path, plik_tryb: bool, obrazy: Obrazy, skroty):
        self.d, self.dist, self.plik_tryb, self.obrazy, self.skroty = d, dist, plik_tryb, obrazy, skroty
        self.myslnik = d.firma["funkcje"].get("myslnik") or "polpauza"
        self.domena = d.firma["firma"].get("domena") or ""
        self.biezaca = None
        self.widoczne: list[str] = []
        self.strony: list = []
        self.limity = d.preset.get("limity", {})

    def _prefiks(self) -> str:
        return "../" * (self.biezaca.glebokosc if self.biezaca else 0)

    def url(self, s: str) -> str:
        if s.startswith(("http:", "https:", "mailto:", "tel:", "#", "data:")):
            return s
        if not self.plik_tryb:
            return s
        sciezka, _, kotwica = s.partition("#")
        sciezka = sciezka.strip("/")
        if sciezka.startswith("assets/") or "." in Path(sciezka).name:
            cel = sciezka
        else:
            cel = (sciezka or "index") + ".html"
        return self._prefiks() + cel + (f"#{kotwica}" if kotwica else "")

    def zasob(self, s: str) -> str:
        """Plik z dist/ → adres z ?v=<skrót zawartości> (także fonty — ten sam adres w preload i w @font-face)."""
        s = s.lstrip("/")
        h = self.skroty(s)
        wersja = "" if h is None else f"?v={h}"
        return (self._prefiks() if self.plik_tryb else "/") + s + wersja

    def abs(self, s: str) -> str:
        if s.startswith("http"):
            return s
        return self.domena + "/" + s.lstrip("/")

    def abs_zasob(self, s: str) -> str:
        """Pełny adres pliku z ?v= (og:image, logo w JSON-LD) — zmiana pliku = nowy adres mimo rocznego cache."""
        s = s.lstrip("/")
        h = self.skroty(s)
        return self.domena + "/" + s + ("" if h is None else f"?v={h}")

    def obraz(self, zid: str, wariant: str) -> str:
        return self.obrazy.picture(zid, wariant)

    def czytaj_md(self, sciezka: str) -> str:
        p = self.d.klient / "data" / sciezka.removeprefix("data/")
        if not p.is_file():
            raise ValueError(f"nie ma pliku data/{sciezka.removeprefix('data/')}")
        return p.read_text(encoding="utf-8")

    def link_md(self, adres: str) -> str:
        return self.url(adres) if adres.startswith("/") else adres

    def sekcje_strony(self):
        return [(sid, {"tryb": "skrot", "limit": self.limity.get(sid)}) for sid in self.widoczne]

    def sekcja_info(self, sid: str) -> dict:
        t = self.d.tresc
        dane_sekcji = self.d.firma.get("godziny") if sid == "godziny" else t.get(sid)
        naglowek = (dane_sekcji or {}).get("naglowek") if isinstance(dane_sekcji, dict) else None
        strona = next((s.sciezka for s in self.strony if sid in s.sekcje and s.element is None), None)
        # wariant tła/odstępu z presetu (warianty: {"proces": "tint", "zasady": "sm"}) — tylko na stronie głównej, gdzie
        # sekcje stoją jedna pod drugą; jedna sekcja z tłem w środku strony przerywa rytm „linia, h2, treść”
        wariant = self.d.preset.get("warianty", {}).get(sid) if self.biezaca and self.biezaca.sciezka == "/" else None
        return {"id": sid, "html_id": strony_mod.html_id(sid),
                "naglowek": naglowek or self.d.preset.get("naglowki", {}).get(sid) or sid,
                "dane": dane_sekcji, "strona": strona, "klasa": WARIANTY_SEKCJI.get(wariant)}


WARIANTY_SEKCJI = {"tint": "section--tint", "sm": "section--sm"}

ZNACZNIK = ".szablon-wynik"   # plik w katalogu wyniku: tylko taki katalog build może usunąć przy następnym uruchomieniu


def _sledzone_przez_git(sciezka: Path) -> bool:
    """Czy w katalogu są pliki śledzone przez git (repozytorium, w którym leży katalog). Bez gita — nie."""
    try:
        wynik = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=sciezka, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return wynik.returncode == 0 and bool(wynik.stdout.strip(b"\0"))


def _stary_wynik(dist: Path) -> bool:
    """Wynik buildu sprzed znacznika (_headers + strona.css + index.html, nic więcej z repozytorium)."""
    return all((dist / p).is_file() for p in ("_headers", "index.html", "assets/css/strona.css")) \
        and not any((dist / p).exists() for p in ("data", "src", "tools", ".git", "docs"))


def _przygotuj_dist(dist: Path, klient: Path, raport: Raport) -> bool:
    """Czyści katalog wyniku. Usuwa wyłącznie katalog oznaczony przez poprzedni build (ZNACZNIK) i nigdy
    katalogu z plikami śledzonymi przez git — pomyłka w --wyjscie nie może skasować docs/, src/ ani .git."""
    d = dist.resolve()
    chronione = [KORZEN.resolve(), klient.resolve(), Path.home().resolve()]
    if d == Path(d.anchor) or any(d == c or d in c.parents for c in chronione):
        raport.blad(f"--wyjscie {dist}: to katalog repozytorium, klienta albo jego nadrzędny — build go nie wyczyści",
                    naprawa="podaj osobny katalog wyniku, np. --wyjscie dist-test")
        return False
    if d.exists():
        if not d.is_dir():
            raport.blad(f"--wyjscie {dist}: to plik, nie katalog", naprawa="podaj inną nazwę katalogu wyniku")
            return False
        if any(d.iterdir()):
            if _sledzone_przez_git(d):
                raport.blad(f"--wyjscie {dist}: katalog zawiera pliki śledzone przez git — build go nie usunie",
                            naprawa="podaj osobny katalog wyniku, np. --wyjscie dist-test")
                return False
            if not (d / ZNACZNIK).is_file() and not _stary_wynik(d):
                raport.blad(f"--wyjscie {dist}: katalog nie jest wynikiem buildu (brak pliku {ZNACZNIK}) — build go nie usunie",
                            naprawa=f"sprawdź, co w nim jest, i usuń go ręcznie albo podaj inny katalog wyniku")
                return False
        shutil.rmtree(d)
    (d / "assets" / "css").mkdir(parents=True)
    (d / "assets" / "js").mkdir(parents=True)
    (d / ZNACZNIK).write_text("Katalog wyniku tools/build.py — build usuwa go i tworzy od nowa.\n", encoding="utf-8")
    # Cloudflare (wrangler) nie wysyła na serwer plików z .assetsignore
    (d / ".assetsignore").write_text(ZNACZNIK + "\n", encoding="utf-8")
    return True


def _katalog(sciezka: str) -> Path:
    """Ścieżka względna: najpierw względem bieżącego katalogu, a gdy tam jej nie ma — względem repozytorium
    (tak samo dla --klient i --wyjscie)."""
    p = Path(sciezka)
    if p.is_absolute():
        return p
    return (Path.cwd() / p) if (Path.cwd() / p).exists() else (KORZEN / p)


def build(a, raport: Raport, dzis: dt.date) -> dict:
    klient = _katalog(a.klient).resolve()
    dist = (_katalog(a.wyjscie) if a.wyjscie else KORZEN / "dist").resolve()
    wynik = {"klient": str(klient), "dist": str(dist), "strony": []}

    # 1. dane
    d = dane_mod.wczytaj(klient, KORZEN, raport)
    if d is None:
        return wynik
    dane_mod.kontrole(d, raport, a.produkcja, dzis)
    if raport.bledy:
        return wynik
    # bez domeny (D13): strona pod adresem roboczym — ten adres zastępuje domenę w canonical, sitemap i og:image,
    # a każda strona dostaje noindex (_headers ma już X-Robots-Tag dla adresu roboczego)
    bez_domeny = not d.firma["firma"].get("domena")
    if bez_domeny:
        d.firma["firma"]["domena"] = d.firma["firma"]["adres_roboczy"]
    # 2. kolory
    try:
        tokeny, pary = kolory.tokeny(d.firma["marka"])
    except ValueError as e:
        raport.blad(str(e), plik="data/firma.json", pole="marka.tlo")
        return wynik
    for fg, bg, w, minimum, opis in pary:
        if w < minimum:
            raport.blad(f"kontrast {fg} na {bg} ({opis}) = {w:.2f}:1, wymagane {minimum}:1", plik="data/firma.json",
                        pole="marka", naprawa="zmień marka.kolor/kolor_dodatkowy/tlo albo zgłoś błąd w tools/silnik/kolory.py")
    if raport.bledy:
        return wynik
    # 3. zasoby
    if not _przygotuj_dist(dist, klient, raport):
        return wynik
    zasoby.kopiuj(KORZEN, klient, dist, d.fonty, d.firma["marka"])
    skroty = zasoby.Skroty(dist)
    obrazy = Obrazy(klient, d.zdjecia, raport, None, dist)
    # 91-ruch.css (wejście hero, @view-transition) tylko przy funkcje.animacje = "wejscie" (D6)
    bez_ruchu = set() if d.firma["funkcje"].get("animacje") == "wejscie" else {"91-ruch.css"}
    css, preload = zasoby.zbuduj_css(KORZEN, klient, d.fonty, d.firma["marka"], tokeny, obrazy.css_punkty(), skroty,
                                     pomin=bez_ruchu)
    (dist / "assets" / "css" / "strona.css").write_text(css, encoding="utf-8")
    js = zasoby.zbuduj_js(KORZEN)
    (dist / "assets" / "js" / "strona.js").write_text(js, encoding="utf-8")
    srod = Srodowisko(d, dist, a.plik, obrazy, skroty)
    obrazy.zasob = srod.zasob
    silnik = Silnik(KORZEN / "src", raport, srod)

    # 4. kontekst bazowy i plan stron
    ctx = {"firma": d.firma, "tresc": d.tresc, "zdjecia": d.zdjecia, "preset": d.preset, "funkcje": d.firma["funkcje"],
           "aktualnosci": d.aktualnosci, "auto": {}, "nav": [], "strona": {}}
    ctx["auto"] = dane_mod.auto(d, dzis, set(), [])      # wstępnie — nagłówki „wymaga:” mogą sięgać do auto
    lista, widoczne = strony_mod.plan(silnik, d, raport, ctx, dzis)
    srod.widoczne, srod.strony = widoczne, lista
    podstrony = {s.sciezka for s in lista}
    auto = dane_mod.auto(d, dzis, podstrony, widoczne)
    dane_mod.sprawdz_cta(auto, d, widoczne, raport)
    if raport.bledy:
        return wynik
    auto["bez_domeny"] = bez_domeny
    auto["tokeny"] = tokeny
    auto["fonty_preload"] = [f"assets/fonts/{p}" for p in preload]
    auto["inline_js"] = zasoby.INLINE_JS
    auto["kolor_tla"] = tokeny["--tlo"]
    ikony_dir = klient / "assets" / "img" / "ikony"
    auto["ikony"] = {"ico": (ikony_dir / "favicon.ico").is_file(), "svg": (ikony_dir / "icon.svg").is_file(),
                     "png": (ikony_dir / "icon-192.png").is_file(), "apple": (ikony_dir / "apple-touch-icon.png").is_file(),
                     "manifest": (ikony_dir / "icon-192.png").is_file()}
    logo = None
    m = d.firma["marka"]
    if m.get("logo"):
        plik_logo = m["logo"]
        naglowkowe = sorted((klient / "assets" / "img" / "ikony").glob("logo-naglowek.*"))
        w, h = wymiary(klient / plik_logo)
        logo = {"plik": plik_logo, "szer": w, "wys": h}
        src = str(naglowkowe[0].relative_to(klient)) if naglowkowe else plik_logo
        # width/height = rozmiar, w jakim CSS pokazuje logo w nagłówku ≥ 960 px: logo_szerokosc, ale nie wyżej niż 56 px
        # (02-uklad.css: max-height = --header-h − 16 px); plik logo-naglowek ma 3× tę szerokość (tools/zdjecia.py)
        szer = round(min(m.get("logo_szerokosc") or 140, LOGO_MAX_WYS * w / h))
        auto["logo"] = {"src": src, "szer": szer, "wys": round(szer * h / w), "alt": f"{d.firma['firma']['nazwa']} – strona główna"}
        if m.get("logo_na_ciemnym"):
            w2, h2 = wymiary(klient / m["logo_na_ciemnym"])
            src2 = src if m["logo_na_ciemnym"] == plik_logo else m["logo_na_ciemnym"]   # to samo logo → mniejszy wariant
            szer2 = m.get("logo_szerokosc") or 140        # w stopce logo nie ma limitu wysokości
            auto["logo_na_ciemnym"] = {"src": src2, "szer": szer2, "wys": round(szer2 * h2 / w2)}
    else:
        auto["logo"] = None
    # „Stan na” w polityce prywatności i informacji o dostępności: ostatnia zmiana danych firmy albo szablonu strony
    # (z historii git) — nie data buildu, która zmienia się co noc
    for nazwa_s in ("polityka-prywatnosci", "dostepnosc"):
        auto[f"{nazwa_s.replace('-', '_')}_data"] = naglowki.data_zmiany(
            [klient / "data" / "firma.json", KORZEN / "src" / "strony" / f"{nazwa_s}.html"], klient)
    ctx["auto"] = auto
    ctx["nav"] = strony_mod.nawigacja(lista, widoczne, d)
    og_plik = klient / "assets" / "img" / "og.jpg"
    hero_zdj = (d.tresc.get("hero") or {}).get("zdjecie")
    og_alt = d.zdjecia[hero_zdj]["alt"] if hero_zdj in d.zdjecia else d.firma["firma"]["nazwa"]

    man = naglowki.manifest(d.firma, tokeny["--tlo"], klient / "assets" / "img" / "ikony", srod.zasob)
    if man:   # przed renderem — link w <head> dostaje ?v=<skrót>
        (dist / "site.webmanifest").write_text(man, encoding="utf-8")

    # 5. render stron
    for s in lista:
        srod.biezaca = s
        lokalne = {"element": s.element}
        ctx_s = dict(ctx)
        ctx_s["element"] = s.element
        rend = lambda klucz, dom=None: silnik.renderuj_tekst(s.naglowek[klucz], ctx_s, f"src/{s.plik} (nagłówek {klucz})") \
            if s.naglowek.get(klucz) else dom
        tytul_krotki = html.unescape(rend("tytul", "") or "")
        opis = html.unescape(rend("opis", "") or "") if s.sciezka != "/" else \
            (d.firma["seo"].get("opis") or d.firma["firma"].get("opis") or "")
        opis = opis or d.firma["firma"].get("opis") or ""
        kanoniczny = srod.domena + (s.sciezka if s.sciezka != "/" else "/") if s.indeksuj else None
        okr = strony_mod.okruszki(s, tytul_krotki, lista, lambda t: html.unescape(
            silnik.renderuj_tekst(t, ctx_s, f"src/{s.plik} (okruszki: tytuł strony nadrzędnej)")))
        strona_ctx = {
            "sciezka": s.sciezka, "nazwa": s.nazwa, "glowna": s.sciezka == "/",
            "tytul": strony_mod.tytul(s, tytul_krotki, d), "tytul_krotki": tytul_krotki,
            "h1": html.unescape(rend("h1", "") or "") or tytul_krotki,
            "opis": opis, "okruszki": okr, "kanoniczny": kanoniczny, "indeksuj": s.indeksuj,
            "og_obraz": srod.abs_zasob("assets/img/og.jpg") if og_plik.is_file() else None, "og_obraz_alt": og_alt,
            "wstep": html.unescape(rend("wstep", "") or "") or None,
            "element": s.element,          # wpis/oferta kolekcji — JSON-LD Article (jsonld.wezly_modulow)
        }
        og_el = oferta_mod.og_elementu(s.element, klient, d.zdjecia, srod.abs_zasob)   # usługa: kadr ze swojego zdjęcia
        if og_el:
            strona_ctx["og_obraz_strony"] = strona_ctx["og_obraz"]
            strona_ctx["og_obraz"], strona_ctx["og_obraz_alt"] = og_el
        ctx_s["strona"] = strona_ctx
        graf = jsonld.graf(d, auto, strona_ctx, srod.abs_zasob, logo, dzis)
        ctx_s["auto"] = dict(auto, jsonld=Markup(jsonld.jako_skrypt(graf)))
        ctx_s["nav"] = [dict(n, biezaca=(n["href"] == s.sciezka)) for n in ctx["nav"]]
        tresc_strony = silnik.renderuj_plik(s.plik, ctx_s, lokalne)
        wynik_html = silnik.renderuj_plik("uklad.html", ctx_s, {"tresc_strony": Markup(tresc_strony)})
        wynik_html = sierotki_html(wynik_html)
        cel = dist / s.wyjscie
        cel.parent.mkdir(parents=True, exist_ok=True)
        cel.write_text(wynik_html, encoding="utf-8")
        wynik["strony"].append(s.sciezka)
        if len(strona_ctx["tytul"]) > 60:
            raport.ostrzezenie(f"tytuł „{strona_ctx['tytul']}” ma {len(strona_ctx['tytul'])} zn. (limit 60)", plik=f"src/{s.plik}")

    # 5b. CSS tylko z sekcjami, które strona ma: reguły bloków bez ani jednego elementu na stronach znikają z plików
    #     sekcji (czesci/1*.css), a adres ?v= na stronach dostaje nowy skrót (limit CSS 60 KB, KONTRAKT §10)
    strony_html = [p.read_text(encoding="utf-8") for p in dist.rglob("*.html")]
    bloki = zasoby.uzyte_bloki(strony_html, [js, zasoby.INLINE_JS])
    css_przyciety, _ = zasoby.zbuduj_css(KORZEN, klient, d.fonty, d.firma["marka"], tokeny, obrazy.css_punkty(),
                                         skroty, pomin=bez_ruchu, bloki=bloki)
    if css_przyciety != css:
        stary = f"strona.css?v={zasoby.skrot(css.encode())}"
        nowy = f"strona.css?v={zasoby.skrot(css_przyciety.encode())}"
        (dist / "assets" / "css" / "strona.css").write_text(css_przyciety, encoding="utf-8")
        for p in dist.rglob("*.html"):
            t = p.read_text(encoding="utf-8")
            if stary in t:
                p.write_text(t.replace(stary, nowy), encoding="utf-8")
        css = css_przyciety

    # 6. pliki techniczne
    (dist / "_headers").write_text(naglowki.headers(d.firma, zasoby.INLINE_JS), encoding="utf-8")
    (dist / "robots.txt").write_text(naglowki.robots(d.firma), encoding="utf-8")
    red = naglowki.przekierowania(d.firma, {s.sciezka for s in lista}, raport)
    if red:
        (dist / "_redirects").write_text(red, encoding="utf-8")
    pliki_danych = sorted((klient / "data").rglob("*"))
    adresy = [(srod.domena + (s.sciezka if s.sciezka != "/" else "/"),
               naglowki.data_zmiany(pliki_danych + [KORZEN / "src" / s.plik], klient))
              for s in lista if s.indeksuj]
    (dist / "sitemap.xml").write_text(naglowki.sitemap(adresy), encoding="utf-8")
    if auto.get("rss"):
        (dist / "aktualnosci.xml").write_text(naglowki.rss(d.firma, d.aktualnosci, srod.abs), encoding="utf-8")
    sec = naglowki.security_txt(d.firma, dzis)
    if sec:
        (dist / ".well-known").mkdir(exist_ok=True)
        (dist / ".well-known" / "security.txt").write_text(sec, encoding="utf-8")

    # 7. kontrole wyniku
    rozmiary = {"css": len(css.encode()), "js": len(js.encode())}
    wynik["rozmiary"] = rozmiary
    if not a.szybko:
        zewn = ("static.cloudflareinsights.com",) if d.firma["funkcje"].get("statystyki_cf_token") else ()
        kontrole.sprawdz(dist, raport, srod.domena, zasoby.INLINE_JS, a.plik, zewn)
        if rozmiary["css"] > 60 * 1024:
            raport.ostrzezenie(f"CSS ma {rozmiary['css'] // 1024} KB (limit 60 KB)", plik="dist/assets/css/strona.css")
        if rozmiary["js"] > 30 * 1024:
            raport.ostrzezenie(f"JS ma {rozmiary['js'] // 1024} KB (limit 30 KB)", plik="dist/assets/js/strona.js")
        for p in (dist / "assets" / "img").rglob("*") if (dist / "assets" / "img").exists() else []:
            limit = 400 if p.suffix in (".jpg", ".jpeg") else 250
            if p.suffix in (".jpg", ".jpeg", ".webp", ".avif") and p.stat().st_size > limit * 1024:
                raport.ostrzezenie(f"zdjęcie {p.name} ma {p.stat().st_size // 1024} KB (limit {limit} KB)",
                                   plik=f"dist/{p.relative_to(dist)}")
        # ogłoszenie to pasek pod hero na kilka dni, nie sekcja — nie liczy się do limitu
        n_sekcji = len([x for x in widoczne if x != "ogloszenie"])
        if n_sekcji > 9:
            raport.ostrzezenie(f"strona główna ma {n_sekcji} sekcji (zalecane ≤ 9)")
        if a.produkcja:
            kontrole.przeciek_przykladow(KORZEN, klient, dist, raport)
        lint = KORZEN / "tools" / "lint_slop.py"
        if lint.is_file():
            polecenie = [sys.executable, str(lint), str(dist), str(klient / "data"), "--json"] + (["--produkcja"] if a.produkcja else [])
            wynik_lint = subprocess.run(polecenie, capture_output=True, text=True)
            lint_slop_raport(wynik_lint, raport, polecenie)
    return wynik


def lint_slop_raport(wynik_lint, raport: Raport, polecenie: list) -> None:
    """Wyniki tools/lint_slop.py --json → komunikaty buildu: P0 = błąd, P1 = ostrzeżenie (w --produkcja błąd), P2 = jedna informacja."""
    try:
        lw = json.loads(wynik_lint.stdout)
    except ValueError:
        raport.blad("tools/lint_slop.py nie zadziałał:\n" + (wynik_lint.stdout + wynik_lint.stderr).strip()[-2000:])
        return
    p2 = {}
    for w in lw["wyniki"]:
        tresc = f"[{w['id']}] {w['komunikat']}" + (f" (też: {', '.join(w['tez'][:4])}…)" if w.get("tez") else "")
        miejsce = f"{w['plik']}:{w['linia']}"
        if w["poziom"] == "P0":
            raport.blad(tresc, plik=miejsce, pole=w.get("pole"), naprawa=w.get("naprawa"))
        elif w["poziom"] == "P1":
            raport.ostrzezenie(tresc, plik=miejsce, pole=w.get("pole"), naprawa=w.get("naprawa"))
        else:
            p2[w["id"]] = p2.get(w["id"], 0) + 1
    if p2:
        raport.info(f"lint_slop: {sum(p2.values())} uwag P2 (" + ", ".join(f"{k} {v}" for k, v in sorted(p2.items()))
                    + ") — szczegóły: python3 tools/lint_slop.py " + " ".join(
                        x if os.path.relpath(x).startswith("..") else os.path.relpath(x) for x in polecenie[2:4]))


def podsumowanie(raport: Raport, wynik: dict, a) -> None:
    if a.json:
        print(json.dumps({"wynik": wynik, "komunikaty": json.loads(raport.json())}, ensure_ascii=False, indent=2))
        return
    tryb = "produkcja" if a.produkcja else ("szybko" if a.szybko else "sprawdz")
    print(f"SZABLON build — klient: {os.path.relpath(wynik['klient'], KORZEN)}, tryb: {tryb}"
          + (", linki do plików (--plik)" if a.plik else ""))
    if wynik.get("strony"):
        print(f"\nStrony ({len(wynik['strony'])}): " + ", ".join(wynik["strony"]))
    for poziom, tytul in ((UKRYTO, "UKRYTO"), (INFO, "INFORMACJE"), (OSTRZEZENIE, "OSTRZEŻENIA"), (BLAD, "BŁĘDY")):
        lista = raport.lista(poziom)
        if not lista:
            continue
        print(f"\n{tytul} ({len(lista)}):")
        for k in lista:
            print("  - " + k.tekst().replace("\n", "\n    "))
    if wynik.get("rozmiary"):
        r = wynik["rozmiary"]
        print(f"\nRozmiary: CSS {r['css'] / 1024:.1f} KB, JS {r['js'] / 1024:.1f} KB")
    if raport.bledy:
        n = len(raport.bledy)
        print(f"\nWynik: {n} {liczba_mnoga(n, 'błąd,błędy,błędów')} — popraw i uruchom build ponownie.")
    else:
        print(f"\nWynik: OK → {os.path.relpath(wynik['dist'], Path.cwd())}/")


def podglad_szablonu(a) -> bool:
    """Czy --produkcja uruchomiono w samym repozytorium SZABLON (dane = nietknięty szkielet z start.py).

    Cloudflare (Workers Builds) podpięty do repozytorium szablonu wywołuje „build.py --produkcja” — bez tego
    build kończyłby się błędami „brak danych” i podgląd nigdy by nie powstał. Wtedy budujemy przykład.
    W repozytorium klienta z wypełnionymi danymi nic się nie zmienia."""
    if Path(a.klient).resolve() != KORZEN.resolve() or not (KORZEN / "przyklady" / "bimex" / "data").is_dir():
        return False
    from start import nietkniety_szkielet  # tools/start.py — ten sam test, którym start.py pozwala zastąpić szkielet
    return nietkniety_szkielet(KORZEN / "data", "../tools/schemat")


def main() -> int:
    p = argparse.ArgumentParser(description="Build strony SZABLON (dane → dist/).")
    tryb = p.add_mutually_exclusive_group()
    tryb.add_argument("--szybko", action="store_true", help="bez kontroli wyniku")
    tryb.add_argument("--sprawdz", action="store_true", help="(domyślnie) wszystko, ostrzeżenia nie przerywają")
    tryb.add_argument("--produkcja", action="store_true", help="ostrzeżenia = błędy, dane przykładowe = błąd")
    p.add_argument("--klient", default=".", help="katalog klienta (domyślnie korzeń repozytorium)")
    p.add_argument("--wyjscie", default=None,
                   help="katalog wyniku (domyślnie dist/ w repozytorium; ścieżka względna jak w --klient)")
    p.add_argument("--plik", action="store_true", help="linki względne z .html (podgląd z dysku)")
    p.add_argument("--json", action="store_true", help="komunikaty jako JSON")
    a = p.parse_args()
    if a.produkcja and podglad_szablonu(a):
        a.produkcja, a.klient = False, "przyklady/bimex"
        print("PODGLĄD SZABLONU: data/ to nietknięty szkielet (repozytorium SZABLON, a nie strona klienta) — "
              "buduję przykład przyklady/bimex w trybie --sprawdz, z noindex. Strona klienta: najpierw "
              "python3 tools/start.py --branza … i dane firmy (AGENTS.md).\n")
    raport = Raport(produkcja=a.produkcja)
    try:
        dzis = dt.date.fromisoformat(os.environ["SZABLON_DZIS"]) if os.environ.get("SZABLON_DZIS") else dt.date.today()
    except ValueError:
        print(f"BŁĄD: SZABLON_DZIS={os.environ['SZABLON_DZIS']!r} — oczekiwano daty RRRR-MM-DD, np. 2026-12-24", file=sys.stderr)
        return 1
    try:
        wynik = build(a, raport, dzis)
    except BladSzablonu as e:
        raport.blad(f"błąd szablonu: {e}")
        wynik = {"klient": a.klient, "dist": a.wyjscie or "dist", "strony": []}
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("\nBŁĄD WEWNĘTRZNY buildu (to błąd silnika, nie danych) — zgłoś go z powyższym śladem.", file=sys.stderr)
        return 2
    podsumowanie(raport, wynik, a)
    return 1 if raport.bledy else 0


if __name__ == "__main__":
    sys.exit(main())
