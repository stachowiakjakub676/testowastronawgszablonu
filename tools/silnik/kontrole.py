"""Kontrole gotowego wyniku w dist/ (KONTRAKT §10). Czytamy HTML parserem z biblioteki standardowej.

Błąd (zawsze): pozostałości szablonu i tekst zastępczy; <img> bez alt/width/height; ≠ 1 h1; przeskok poziomu
nagłówka; powtórzone id; link wewnętrzny do nieistniejącej strony/kotwicy/pliku; style="" albo <style>; skrypt
w HTML inny niż jeden dozwolony; zasób z obcej domeny; tel: nie w E.164; brak lub względny og:image;
HTML > 100 KB; link/przycisk bez nazwy; pole formularza bez etykiety.
Adres (href, src, srcset, data-src, action, og:url/og:image) z twardą spacją, półpauzą albo „…” = błąd (typografia
zepsuła link). JSON-LD z „<!--” albo „<script” = błąd (przeglądarka inaczej przeczyta resztę strony).
Ostrzeżenie (w --produkcja błąd): HTML > 60 KB. Tytuł > 60 zn. sprawdza build.py (działa też w --szybko).
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

ZNAKI_TYPOGRAFII = {"\u00a0": "twardą spację", "–": "półpauzę „–”", "—": "pauzę „—”", "„": "cudzysłów „„”",
                    "”": "cudzysłów „””"}
POZOSTALOSCI = re.compile(r"\{\{|\{%|\{#|\[UZUPEŁNIJ|\bTODO\b|\bLorem\b|\bXXX\b")
PUSTE = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Analiza(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: dict[str, int] = {}
        self.powtorzone: list[tuple[str, int]] = []
        self.naglowki: list[tuple[int, int]] = []
        self.obrazy: list[tuple[dict, int]] = []
        self.linki: list[tuple[str, int, str]] = []       # (adres, linia, atrybut)
        self.adresy: list[tuple[str, int, str]] = []      # każdy atrybut z adresem (kontrola typografii w linkach)
        self.skrypty: list[tuple[dict, str, int]] = []
        self.style_bloki: list[int] = []
        self.style_atr: list[tuple[str, int]] = []
        self.meta: dict[str, str] = {}
        self.tytul = ""
        self.lang = None
        self._w_tytule = False
        self._skrypt: tuple[dict, list, int] | None = None
        self._otwarte: list[dict] = []                     # otwarte <a>/<button>/<label>
        self.bez_nazwy: list[tuple[str, int]] = []
        self.pola: list[tuple[dict, int]] = []
        self.etykiety_for: set[str] = set()
        self.pola_w_label: set[int] = set()

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        linia = self.getpos()[0]
        if "id" in a:
            if a["id"] in self.ids:
                self.powtorzone.append((a["id"], linia))
            else:
                self.ids[a["id"]] = linia
        if "style" in a:
            self.style_atr.append((tag, linia))
        if tag == "html":
            self.lang = a.get("lang")
        if re.fullmatch(r"h[1-6]", tag):
            self.naglowki.append((int(tag[1]), linia))
        if tag == "img":
            self.obrazy.append((a, linia))
            for o in self._otwarte:
                if a.get("alt"):
                    o["tekst"] += a["alt"]
        if tag == "style":
            self.style_bloki.append(linia)
        if tag == "script":
            self._skrypt = (a, [], linia)
        if tag == "title":
            self._w_tytule = True
        if tag == "meta":
            klucz = a.get("property") or a.get("name")
            if klucz:
                self.meta[klucz] = a.get("content", "")
        for atr in ("href", "src", "data-src", "action"):
            if atr in a:
                self.adresy.append((a[atr], linia, f"{tag}[{atr}]"))
        if tag == "meta" and (a.get("property") or "") in ("og:url", "og:image"):
            self.adresy.append((a.get("content", ""), linia, f"meta[{a['property']}]"))
        for atr in ("href", "src"):
            if atr in a:
                self.linki.append((a[atr], linia, f"{tag}[{atr}]" + (f"[rel={a.get('rel')}]" if tag == "link" else "")))
        for atr in ("srcset", "imagesrcset"):
            if atr in a:
                self.adresy.append((a[atr], linia, f"{tag}[{atr}]"))
                for kand in a[atr].split(","):
                    kand = kand.strip().split(" ")[0]
                    if kand:
                        self.linki.append((kand, linia, f"{tag}[{atr}]"))
        if tag in ("a", "button", "label"):
            self._otwarte.append({"tag": tag, "tekst": a.get("aria-label", "") + a.get("title", ""), "linia": linia,
                                  "for": a.get("for")})
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit", "button"):
            self.pola.append((a, linia))
            if any(o["tag"] == "label" for o in self._otwarte):
                self.pola_w_label.add(len(self.pola) - 1)
        if tag in PUSTE and tag in ("a", "button"):
            pass

    def handle_endtag(self, tag):
        if tag == "title":
            self._w_tytule = False
        if tag == "script" and self._skrypt:
            a, tresc, linia = self._skrypt
            self.skrypty.append((a, "".join(tresc), linia))
            self._skrypt = None
        if tag in ("a", "button", "label"):
            for i in range(len(self._otwarte) - 1, -1, -1):
                if self._otwarte[i]["tag"] == tag:
                    o = self._otwarte.pop(i)
                    if tag == "label":
                        if o["for"]:
                            self.etykiety_for.add(o["for"])
                    elif not o["tekst"].strip():
                        self.bez_nazwy.append((tag, o["linia"]))
                    break

    def handle_data(self, data):
        if self._w_tytule:
            self.tytul += data
        if self._skrypt:
            self._skrypt[1].append(data)
        for o in self._otwarte:
            o["tekst"] += data


def _cel_linku(adres: str, strona_wyj: str, dist: Path, plik_tryb: bool) -> tuple[Path | None, str]:
    """Plik w dist/ i kotwica, na które wskazuje link wewnętrzny (None = link zewnętrzny/specjalny)."""
    cz = urlsplit(adres)
    if cz.scheme or adres.startswith("//"):
        return None, ""
    sciezka, kotwica = unquote(cz.path), cz.fragment
    if not sciezka:
        return dist / strona_wyj, kotwica
    if sciezka.startswith("/"):
        baza = dist
        sciezka = sciezka.lstrip("/")
    else:
        baza = (dist / strona_wyj).parent
    if sciezka in ("", "."):
        return baza / "index.html", kotwica
    cel = (baza / sciezka).resolve()
    for kandydat in (cel, cel.with_name(cel.name + ".html"), cel / "index.html"):
        if kandydat.is_file():
            return kandydat, kotwica
    return cel, kotwica


def sprawdz(dist: Path, raport, domena: str, inline_js: str, plik_tryb: bool = False,
            dozwolone_zewn: tuple = ()) -> dict:
    strony = sorted(dist.rglob("*.html"))
    analizy: dict[Path, Analiza] = {}
    zrodla: dict[Path, str] = {}
    for p in strony:
        html = p.read_text(encoding="utf-8")
        zrodla[p] = html
        a = Analiza()
        a.feed(html)
        analizy[p] = a
    host = urlsplit(domena or "").netloc
    for p, a in analizy.items():
        rel = str(p.relative_to(dist))
        html = zrodla[p]
        rozmiar = len(html.encode("utf-8"))
        # 1. pozostałości
        for m in POZOSTALOSCI.finditer(html):
            linia = html.count("\n", 0, m.start()) + 1
            raport.blad(f"pozostałość szablonu albo tekst zastępczy „{m.group(0)}”", plik=f"dist/{rel}:{linia}")
        # 2. nagłówki
        h1 = [n for n in a.naglowki if n[0] == 1]
        if len(h1) != 1:
            raport.blad(f"strona ma {len(h1)} nagłówków h1 (musi być dokładnie jeden)", plik=f"dist/{rel}")
        poprz = 0
        for poziom, linia in a.naglowki:
            if poziom > poprz + 1:
                raport.blad(f"przeskok poziomu nagłówka: h{poprz or '–'} → h{poziom}", plik=f"dist/{rel}:{linia}")
            poprz = poziom
        # 3. obrazy
        for atr, linia in a.obrazy:
            braki = [x for x in ("alt", "width", "height") if x not in atr]
            if braki:
                raport.blad(f"<img> bez atrybutów: {', '.join(braki)}", plik=f"dist/{rel}:{linia}")
        # 4. id
        for i, linia in a.powtorzone:
            raport.blad(f"powtórzone id=\"{i}\"", plik=f"dist/{rel}:{linia}")
        # 5. style
        for linia in a.style_bloki:
            raport.blad("blok <style> (CSP style-src 'self' — style tylko w assets/css)", plik=f"dist/{rel}:{linia}")
        for tag, linia in a.style_atr:
            raport.blad(f"atrybut style=\"\" w <{tag}> (CSP — przenieś do CSS)", plik=f"dist/{rel}:{linia}")
        # 6. skrypty
        for atr, tresc, linia in a.skrypty:
            if "src" in atr:
                continue
            if atr.get("type") == "application/ld+json":
                try:
                    json.loads(tresc)
                except ValueError as e:
                    raport.blad(f"JSON-LD nie jest poprawnym JSON-em: {e}", plik=f"dist/{rel}:{linia}")
                m = re.search(r"<!--|<script", tresc, re.I)
                if m:
                    raport.blad(f"JSON-LD zawiera „{m.group(0)}” — przeglądarka potraktuje resztę strony jak skrypt "
                                "(pusta strona)", plik=f"dist/{rel}:{linia}",
                                naprawa="dane do JSON-LD tylko przez jsonld.jako_skrypt() albo filtr json (escapują „<”)")
                continue
            if tresc.strip() != inline_js:
                raport.blad("skrypt wbudowany w HTML inny niż dozwolony (CSP go zablokuje)", plik=f"dist/{rel}:{linia}")
        # 7. linki i zasoby
        for adres, linia, skad in a.adresy:
            zly = next((z for z in ZNAKI_TYPOGRAFII if z in adres), None)
            if zly:
                raport.blad(f"adres w {skad} zawiera {ZNAKI_TYPOGRAFII[zly]} — typografia zepsuła link: „{adres[:80]}”",
                            plik=f"dist/{rel}:{linia}", naprawa="w szablonie wypisz adres przez filtr url: {{ … | url }}")
        for adres, linia, skad in a.linki:
            if adres.startswith("tel:"):
                if not re.fullmatch(r"tel:\+[1-9]\d{7,14}", adres):
                    raport.blad(f"numer {adres} nie jest w formacie E.164 (tel:+48…)", plik=f"dist/{rel}:{linia}")
                continue
            if adres.startswith("mailto:"):
                if not re.match(r"mailto:[^@\s]+@[^@\s]+\.[a-z]{2,}", adres, re.I):
                    raport.blad(f"zły adres e-mail w {adres}", plik=f"dist/{rel}:{linia}")
                continue
            cz = urlsplit(adres)
            if cz.scheme in ("http", "https") or adres.startswith("//"):
                obcy = cz.netloc and cz.netloc != host
                if obcy and not skad.startswith("a[") and cz.netloc not in dozwolone_zewn:
                    if not (skad.startswith("link[href]") and ("canonical" in skad or "alternate" in skad)):
                        raport.blad(f"zasób z obcej domeny ({cz.netloc}) w {skad} — przenieś plik na własny serwer",
                                    plik=f"dist/{rel}:{linia}")
                continue
            if cz.scheme:
                continue
            cel, kotwica = _cel_linku(adres, rel, dist, plik_tryb)
            if cel is None:
                continue
            if not cel.exists():
                raport.blad(f"link do nieistniejącej strony/pliku: {adres}", plik=f"dist/{rel}:{linia}")
                continue
            if kotwica and cel.suffix == ".html":
                docel = analizy.get(cel)
                if docel is not None and kotwica not in docel.ids:
                    raport.blad(f"kotwica #{kotwica} nie istnieje na {cel.relative_to(dist)}", plik=f"dist/{rel}:{linia}")
        # 8. meta
        og = a.meta.get("og:image", "")
        if not og:
            raport.blad("brak og:image (obrazek podglądu linku)", plik=f"dist/{rel}",
                        naprawa="uruchom tools/zdjecia.py — tworzy assets/img/og.jpg 1200×630 ze zdjęcia hero")
        elif not og.startswith("https://"):
            raport.blad(f"og:image musi być pełnym adresem https://… (jest „{og}”)", plik=f"dist/{rel}")
        if a.lang != "pl":
            raport.blad("<html> bez lang=\"pl\"", plik=f"dist/{rel}")
        # 9. nazwy linków/przycisków i etykiety pól
        for tag, linia in a.bez_nazwy:
            raport.blad(f"<{tag}> bez nazwy (tekst, alt obrazka albo aria-label)", plik=f"dist/{rel}:{linia}")
        for i, (atr, linia) in enumerate(a.pola):
            if not (atr.get("aria-label") or atr.get("aria-labelledby") or atr.get("id") in a.etykiety_for
                    or i in a.pola_w_label):
                raport.blad(f"pole formularza „{atr.get('name')}” bez etykiety <label>", plik=f"dist/{rel}:{linia}")
        # 10. rozmiar
        if rozmiar > 100 * 1024:
            raport.blad(f"HTML ma {rozmiar // 1024} KB (limit 100 KB)", plik=f"dist/{rel}")
        elif rozmiar > 60 * 1024:
            raport.ostrzezenie(f"HTML ma {rozmiar // 1024} KB (zalecane ≤ 60 KB)", plik=f"dist/{rel}")
    return {"strony": len(strony)}


# ----------------------------------------------------------------------------- przeciek tekstów przykładu (--produkcja)

# zdania i napisy z tych pól tresc.json/zdjecia.json mogą zdradzić skopiowany przykład (reszta to nazwy, zakresy, id)
POLA_ZDAN = {"lead", "opis", "wstep", "podpis", "tekst", "odpowiedz", "pytanie", "uwagi", "weryfikacja", "zadanie",
             "dojazd", "dostepnosc_lokalu", "czas_odpowiedzi", "alt"}
MIN_ZDANIE = 30


def _norma(s: str) -> str:
    """Tekst do porównania bez typografii: twarda spacja → spacja, „…” → "…", – — → -, jedna spacja."""
    s = s.replace("\u00a0", " ").replace("„", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def _zdania(tekst: str) -> list[str]:
    """Markdown/tekst → zdania ≥ MIN_ZDANIE znaków (bez znaczników ##, **, [x](y), -)."""
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", tekst)
    t = re.sub(r"^\s*(#{1,6}|[-*]|\d+[.)])\s+", "", t, flags=re.M)
    t = t.replace("**", "").replace("*", "").replace("_", " ")
    wynik = []
    for z in re.split(r"(?<=[.!?:])\s+|\n+", t):
        z = _norma(z)
        if len(z) >= MIN_ZDANIE:
            wynik.append(z)
    return wynik


class _Widoczny(HTMLParser):
    """Widoczny tekst strony (bez <script>/<style>) + alt, title, aria-label i treść meta description / og:*."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.czesci: list[str] = []
        self._pomin = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._pomin += 1
        for k in ("alt", "title", "aria-label"):
            if a.get(k):
                self.czesci.append(a[k])
        if tag == "meta" and ((a.get("name") or "") == "description" or (a.get("property") or "").startswith("og:")) \
                and not (a.get("property") or "").startswith(("og:url", "og:image")):
            self.czesci.append(a.get("content") or "")
        if tag in ("p", "li", "br", "h1", "h2", "h3", "h4", "td", "th", "div", "address", "figcaption"):
            self.czesci.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._pomin:
            self._pomin -= 1
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "td", "th", "div", "address", "figcaption"):
            self.czesci.append("\n")

    def handle_data(self, data):
        if not self._pomin:
            self.czesci.append(data)


def _cyfry(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _wzorce_przykladu(katalog: Path) -> list[tuple[str, str, str]]:
    """(rodzaj, wzorzec, opis) z jednego katalogu przyklady/<nazwa>/data. rodzaj: „tekst” (widoczny tekst,
    po normalizacji), „surowe” (cały HTML — domena, e-mail, numery), „cyfry” (NIP/KRS/REGON/telefon w HTML)."""
    wzorce: list[tuple[str, str, str]] = []
    dane = katalog / "data"
    wczytaj = lambda n: json.loads((dane / f"{n}.json").read_text(encoding="utf-8")) if (dane / f"{n}.json").is_file() else {}
    f, t, z = wczytaj("firma"), wczytaj("tresc"), wczytaj("zdjecia")
    fi, k, r = f.get("firma") or {}, f.get("kontakt") or {}, f.get("rejestr") or {}
    # pola identyfikujące firmę
    for pole in ("nazwa_prawna", "opis"):
        if fi.get(pole) and len(fi[pole]) >= 12:
            wzorce.append(("tekst", _norma(fi[pole]), f"firma.{pole}"))
    if fi.get("domena"):
        host = re.sub(r"^https?://(www\.)?", "", fi["domena"]).strip("/")
        wzorce.append(("surowe", host, "firma.domena"))
    telefony = [k.get("telefon")] + [d.get("telefon") for d in (k.get("dzialy") or [])]
    maile = [k.get("email")] + [d.get("email") for d in (k.get("dzialy") or [])]
    wzorce += [("cyfry", _cyfry(x), "kontakt.telefon") for x in telefony if x]
    wzorce += [("surowe", x, "kontakt.email") for x in maile if x]
    wzorce += [("cyfry", r[x], f"rejestr.{x}") for x in ("nip", "regon", "krs") if r.get(x)]
    adres = k.get("adres") or {}
    if adres.get("ulica") and adres.get("kod"):
        wzorce.append(("adres", _norma(adres["ulica"]) + "|" + adres["kod"], "kontakt.adres"))
    if (f.get("seo") or {}).get("opis"):
        wzorce.append(("tekst", _norma(f["seo"]["opis"]), "seo.opis"))
    # tresc.json: nagłówek i lead hero w całości, z pozostałych pól — zdania ≥ 30 znaków
    hero = t.get("hero") or {}
    for pole in ("naglowek", "lead"):
        if hero.get(pole):
            wzorce.append(("tekst", _norma(hero[pole]), f"tresc.hero.{pole}"))

    def idz(o, sciezka):
        if isinstance(o, dict):
            for kl, v in o.items():
                if kl.startswith("$"):
                    continue
                if isinstance(v, str) and kl in POLA_ZDAN:
                    wzorce.extend(("tekst", zd, f"{sciezka}.{kl}") for zd in _zdania(v))
                else:
                    idz(v, f"{sciezka}.{kl}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                idz(v, f"{sciezka}[{i}]")
    idz(t, "tresc")
    idz(z, "zdjecia")
    for md in sorted(dane.rglob("*.md")):
        wzorce.extend(("tekst", zd, str(md.relative_to(katalog))) for zd in _zdania(md.read_text(encoding="utf-8")))
    return wzorce


def przeciek_przykladow(korzen: Path, klient: Path, dist: Path, raport) -> None:
    """--produkcja: dane z przyklady/* nie mogą trafić na stronę klienta. Porównujemy tylko to, co identyfikuje
    przykład: nazwę prawną, domenę, e-maile, telefony, NIP/KRS/REGON, adres, nagłówek i lead hero oraz zdania
    ≥ 30 znaków z opisów i altów (także z plików .md) — w widocznym tekście, bez typografii. Zwykłe słowa branżowe
    („Roboty drogowe”), kroje z marka.*, id i wartości wyliczeniowe nie są porównywane."""
    if (korzen / "przyklady") in klient.resolve().parents or not (korzen / "przyklady").is_dir():
        return
    wzorce = []
    for katalog in sorted(p for p in (korzen / "przyklady").iterdir() if (p / "data").is_dir()):
        wzorce += [(rodzaj, w, opis, katalog.name) for rodzaj, w, opis in _wzorce_przykladu(katalog)]
    trafienia: dict[tuple[str, str], tuple[str, list[str]]] = {}     # (przykład, pole) → (tekst, strony)
    for strona in sorted(dist.rglob("*.html")):
        surowe = strona.read_text(encoding="utf-8")
        parser = _Widoczny()
        parser.feed(surowe)
        widoczny = "\n".join(_norma(x) for x in "".join(parser.czesci).split("\n"))
        widoczny_jednolinia = _norma(widoczny)
        cyfry_html = re.sub(r"[\s\u00a0.-]", "", surowe)
        rel = strona.relative_to(dist)
        for rodzaj, w, opis, przyklad in wzorce:
            if rodzaj == "tekst":
                trafienie = w in widoczny_jednolinia
            elif rodzaj == "surowe":
                trafienie = re.search(r"(?<![\w.-])" + re.escape(w) + r"(?![\w-])", surowe, re.I) is not None
            elif rodzaj == "cyfry":
                trafienie = len(w) >= 9 and re.search(r"(?<!\d)(?:48)?" + re.escape(w[-9:] if len(w) > 10 else w)
                                                      + r"(?!\d)", cyfry_html) is not None
            else:   # adres: ulica i kod pocztowy na tej samej stronie
                ulica, kod = w.split("|")
                trafienie = ulica in widoczny_jednolinia and kod in widoczny_jednolinia
            if trafienie:
                tekst, strony = trafienia.setdefault((przyklad, opis), (w.replace("|", ", "), []))
                if str(rel) not in strony:
                    strony.append(str(rel))
    # jeden komunikat na pole przykładu (a nie na każdą stronę i każde zdanie)
    for (przyklad, opis), (tekst, strony) in trafienia.items():
        gdzie = ", ".join(strony[:3]) + (f" i {len(strony) - 3} innych" if len(strony) > 3 else "")
        raport.blad(f"dane z przykładu „{przyklad}” ({opis}) są na stronie: „{tekst[:70]}” — {gdzie}",
                    plik=f"przyklady/{przyklad}/data", pole=opis, naprawa="zastąp dane przykładowe danymi klienta")
