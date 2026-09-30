"""Polska typografia i formatowanie wartości (KONTRAKT §3.1, §3.2).

- typografia(): twarde spacje, zakresy z półpauzą, myślnik, cudzysłowy „…”;
- tel(), cena(), liczba(), data_*(), liczba_mnoga(), slug();
- markdown(): mały podzbiór Markdown → HTML (HTML w źródle jest escapowany, linki tylko z bezpiecznych schematów).

Wszystkie funkcje przyjmują zwykły tekst (bez HTML). Escapowanie robi wywołujący (albo markdown()).
"""
from __future__ import annotations

import datetime as _dt
import html
import re

NBSP = " "

MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
            "września", "października", "listopada", "grudnia"]

# jednostki, przed którymi liczba dostaje twardą spację (i po których może stać zakres „32–46 zł”)
JEDNOSTKI = (r"zł|gr|€|%|m²|m³|m2|m3|mb|km|cm|mm|m|kg|t|l|h|min|s|godz\.|dni|dnia|doby|tyg\.|mies\.|"
             r"lat|lata|osób|os\.|szt\.|r\.|tys\.|mln|mld|kW|kWh|ha|zł/m²|zł/h")

_LITERA = r"[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]"

_RE_CUDZYSLOW = re.compile(r'"([^"\n]+)"')
_RE_ZAKRES_GODZIN = re.compile(r"(?<![\d:])(\d{1,2}[:.]\d{2})\s*[-–—]\s*(\d{1,2}[:.]\d{2})(?![\d:])")
_RE_ZAKRES_LAT = re.compile(r"(?<![\d-])((?:19|20)\d\d)\s*[-–—]\s*((?:19|20)\d\d)(?![\d-])")
_RE_ZAKRES_JEDN = re.compile(r"(?<![\d-])(\d+(?:[,.]\d+)?)\s*[-–—]\s*(\d+(?:[,.]\d+)?)(?=\s*(?:" + JEDNOSTKI + r")(?!" + _LITERA + r"))")
_RE_MYSLNIK = re.compile(r"[ \t ]+[-–—][ \t]+")
_RE_JEDNOLITEROWE = re.compile(r"(?<![\w\-])([aiouwzAIOUWZ]) +(?=\S)")
_RE_SKROTY = re.compile(r"(?<![\w])(ul\.|al\.|pl\.|os\.|nr|tel\.|godz\.|ok\.|r\.|św\.|im\.|ks\.|dr|mgr|inż\.|tj\.|np\.) +(?=\S)")
_RE_JEDNOSTKA = re.compile(r"(\d) +(" + JEDNOSTKI + r")(?!" + _LITERA + r")")
_RE_GRUPY = re.compile(r"(?<![\d,.])(\d{1,3})((?: \d{3})+)(?![\d])")


def typografia(tekst: str, myslnik: str = "polpauza") -> str:
    """Polska typografia dla zwykłego tekstu (bez HTML)."""
    if not tekst:
        return tekst
    t = tekst
    t = _RE_CUDZYSLOW.sub("„\\1”", t)
    t = _RE_ZAKRES_GODZIN.sub(r"\1–\2", t)
    t = _RE_ZAKRES_LAT.sub(r"\1–\2", t)
    t = _RE_ZAKRES_JEDN.sub(r"\1–\2", t)
    kreska = "—" if myslnik == "pauza" else "–"
    t = _RE_MYSLNIK.sub(NBSP + kreska + " ", t)
    t = _RE_GRUPY.sub(lambda m: m.group(1) + m.group(2).replace(" ", NBSP), t)
    t = _RE_JEDNOSTKA.sub("\\1" + NBSP + "\\2", t)
    t = _RE_SKROTY.sub("\\1" + NBSP, t)
    t = _RE_JEDNOLITEROWE.sub("\\1" + NBSP, t)
    return t


_RE_ZNACZNIKI_HTML = re.compile(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->|<[^>]*>", re.S | re.I)


def sierotki_html(dokument: str) -> str:
    """Twarda spacja po jednoliterowym wyrazie („w domu”, „i e-mail”) w tekście gotowej strony — także w tekstach
    samych szablonów (nagłówki, polityka prywatności), które nie przechodzą przez filtr typografii danych.
    Zmienia tylko tekst między znacznikami; atrybuty, skrypty (JSON-LD) i komentarze zostają bez zmian."""
    wynik, poz = [], 0
    for m in _RE_ZNACZNIKI_HTML.finditer(dokument):
        wynik.append(_RE_JEDNOLITEROWE.sub("\\1" + NBSP, dokument[poz:m.start()]))
        wynik.append(m.group(0))
        poz = m.end()
    wynik.append(_RE_JEDNOLITEROWE.sub("\\1" + NBSP, dokument[poz:]))
    return "".join(wynik)


# ---------------------------------------------------------------- telefon

# numery kierunkowe stacjonarne (2 cyfry) — reszta 9-cyfrowych numerów to komórki i numery specjalne
STACJONARNE = {"12", "13", "14", "15", "16", "17", "18", "22", "23", "24", "25", "29", "32", "33", "34", "41",
               "42", "43", "44", "46", "48", "52", "54", "55", "56", "58", "59", "61", "62", "63", "65", "67",
               "68", "71", "74", "75", "76", "77", "81", "82", "83", "84", "85", "86", "87", "89", "91", "94",
               "95"}


def tel(numer: str, krajowy: bool = False) -> str:
    """„+48672683408” → „+48 67 268 34 08” (twarde spacje); krajowy=True → „67 268 34 08”."""
    if not numer:
        return ""
    s = re.sub(r"[^\d+]", "", str(numer))
    if s.startswith("+48") and len(s) == 12:
        n = s[3:]
        if n[:2] in STACJONARNE:
            grupy = [n[:2], n[2:5], n[5:7], n[7:]]
        else:
            grupy = [n[:3], n[3:6], n[6:]]
        wynik = NBSP.join(grupy)
        return wynik if krajowy else "+48" + NBSP + wynik
    if s.startswith("+") and len(s) > 8:
        # inny kraj: kod kraju (+1, +7 = 1 cyfra; +35x, +37x, +38x, +42x = 3 cyfry; reszta 2) + grupy po 3 cyfry
        if s[1] in "17":
            kod, reszta = s[1:2], s[2:]
        elif s[1:3] in ("35", "37", "38", "42"):
            kod, reszta = s[1:4], s[4:]
        else:
            kod, reszta = s[1:3], s[3:]
        grupy = [reszta[i:i + 3] for i in range(0, len(reszta), 3)]
        if len(grupy) > 1 and len(grupy[-1]) == 1:
            grupy[-2:] = [grupy[-2][:2], grupy[-2][2:] + grupy[-1]]
        return "+" + kod + NBSP + NBSP.join(grupy)
    return str(numer)


def tel_href(numer: str) -> str:
    return "tel:" + re.sub(r"[^\d+]", "", str(numer or ""))


# ---------------------------------------------------------------- liczby i ceny

def liczba(v, miejsca: int | None = None) -> str:
    """1250 → „1 250”, 4.8 → „4,8”, 4.80 w danych → „4,80”, liczba(12.5, 2) → „12,50” (grupy tysięcy twardą spacją,
    przecinek dziesiętny). Bez `miejsca` — tyle cyfr po przecinku, ile w zapisie źródłowym (Liczba.tekst z dane.py)."""
    if isinstance(v, bool) or v is None:
        return ""
    if isinstance(v, float) and v.is_integer() and miejsca is None:
        v = int(v)
    if isinstance(v, int):
        s = f"{v:,}".replace(",", NBSP)
        return s
    if miejsca is None:
        zapis = getattr(v, "tekst", "") or repr(float(v))
        miejsca = len(zapis.split(".")[1]) if "." in zapis and "e" not in zapis.lower() else 2
    s = f"{v:,.{miejsca}f}"
    calk, _, ulam = s.partition(".")
    return calk.replace(",", NBSP) + ("," + ulam if ulam else "")


def _kwota(v) -> str:
    """Kwota: całe złote bez groszy, inaczej zawsze dwa miejsca („12,50”)."""
    return liczba(v, None if not isinstance(v, float) or v.is_integer() else 2)


def cena(v, waluta: str = "zł") -> str:
    """1250 → „1 250 zł”; {"od":32,"do":46} → „32–46 zł”; 12.5 → „12,50 zł”; {"od":32} → „od 32 zł”."""
    if v is None or v == "":
        return ""
    if isinstance(v, dict):
        od, do = v.get("od"), v.get("do")
        if od is not None and do is not None:
            return f"{_kwota(od)}–{_kwota(do)}{NBSP}{waluta}"
        if od is not None:
            return f"od{NBSP}{_kwota(od)}{NBSP}{waluta}"
        if do is not None:
            return f"do{NBSP}{_kwota(do)}{NBSP}{waluta}"
        return ""
    if isinstance(v, str):
        return v
    return f"{_kwota(v)}{NBSP}{waluta}"


# ---------------------------------------------------------------- daty

def na_date(v) -> _dt.date | None:
    if v is None or v == "":
        return None
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(v).strip())
    if not m:
        raise ValueError(f"nieprawidłowa data „{v}” (oczekiwano RRRR-MM-DD, np. 2026-12-24)")
    rok, mies, dzien = (int(x) for x in m.groups())
    if not 1 <= mies <= 12:
        raise ValueError(f"nie ma miesiąca {mies} w dacie „{v}” (zapis RRRR-MM-DD)")
    try:
        return _dt.date(rok, mies, dzien)
    except ValueError:
        raise ValueError(f"nie ma takiego dnia: {dzien:02d}.{mies:02d}.{rok} (zapis RRRR-MM-DD)") from None


def data_dluga(v) -> str:
    d = na_date(v)
    return f"{d.day}{NBSP}{MIESIACE[d.month - 1]} {d.year}" if d else ""


def data_krotka(v) -> str:
    d = na_date(v)
    return f"{d.day:02d}.{d.month:02d}.{d.year}" if d else ""


def data_iso(v) -> str:
    d = na_date(v)
    return d.isoformat() if d else ""


# ---------------------------------------------------------------- odmiana, slug

def liczba_mnoga(n, formy: str) -> str:
    """liczba_mnoga(24, "realizacja,realizacje,realizacji") → „realizacje”."""
    f = [x.strip() for x in str(formy).split(",")]
    if len(f) != 3:
        raise ValueError("liczba_mnoga wymaga trzech form, np. \"zlecenie,zlecenia,zleceń\"")
    try:
        n = abs(int(n))
    except (TypeError, ValueError):
        return f[2]
    if n == 1:
        return f[0]
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f[1]
    return f[2]


_PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slug(tekst: str) -> str:
    s = str(tekst or "").translate(_PL).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def wersaliki_pierwsza(tekst: str) -> str:
    t = str(tekst or "")
    return t[:1].upper() + t[1:]


def liczba_slow(tekst: str) -> int:
    return len(re.findall(r"[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", tekst or ""))


# ---------------------------------------------------------------- Markdown (podzbiór)

_RE_UL = re.compile(r"^\s*[-*]\s+")
_RE_OL = re.compile(r"^\s*\d+[.)]\s+")
# „//evil.com” to adres innej domeny (bez protokołu) — odrzucamy; względne tylko „/kontakt”, „#x”, „plik.html”
_BEZPIECZNE_URL = re.compile(r"^(https?://|mailto:|tel:|/(?!/)|#|[a-z0-9][a-z0-9\-/]*(\.html)?(#[\w-]+)?$)", re.I)
# adres linku może mieć jeden poziom nawiasów — „[x](javascript:alert(1))” zjadamy w całości (i odrzucamy)
_RE_INLINE = re.compile(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)|\*\*(.+?)\*\*|\*(.+?)\*|(?<![\w])_(.+?)_(?![\w])")


def _inline(tekst: str, myslnik: str, linki) -> str:
    """Tekst z **pogrubieniem**, *kursywą* i [linkami](url) → bezpieczny HTML z polską typografią."""
    wynik = []
    poz = 0
    for m in _RE_INLINE.finditer(tekst):
        wynik.append(html.escape(typografia(tekst[poz:m.start()], myslnik), quote=False))
        if m.group(1) is not None:
            url = m.group(2)
            if not _BEZPIECZNE_URL.match(url) or url.lower().startswith(("javascript:", "data:")):
                wynik.append(html.escape(typografia(m.group(1), myslnik), quote=False))
            else:
                href = linki(url) if linki else url
                wynik.append(f'<a href="{html.escape(href)}">{_inline(m.group(1), myslnik, linki)}</a>')
        elif m.group(3) is not None:
            wynik.append(f"<strong>{_inline(m.group(3), myslnik, linki)}</strong>")
        else:
            wynik.append(f"<em>{_inline(m.group(4) or m.group(5), myslnik, linki)}</em>")
        poz = m.end()
    wynik.append(html.escape(typografia(tekst[poz:], myslnik), quote=False))
    return "".join(wynik)


def markdown(tekst: str, poziom: int = 2, myslnik: str = "polpauza", linki=None) -> str:
    """Podzbiór Markdown: akapity, nagłówki ##/### (→ h<poziom>/h<poziom+1>), listy -, *, 1., pogrubienie,
    kursywa, linki. `linki` — funkcja zamieniająca adresy względne (np. /kontakt w trybie --plik)."""
    if not tekst:
        return ""
    bloki = re.split(r"\n\s*\n", tekst.strip().replace("\r\n", "\n"))
    wynik = []
    for blok in bloki:
        linie = [l.rstrip() for l in blok.split("\n") if l.strip()]
        if not linie:
            continue
        pierwsza = linie[0]
        m = re.match(r"^(#{1,6})\s+(.*)$", pierwsza)
        if m and len(linie) == 1:
            glebokosc = max(0, len(m.group(1)) - 2)
            h = min(6, poziom + glebokosc)
            wynik.append(f"<h{h}>{_inline(m.group(2), myslnik, linki)}</h{h}>")
            continue
        if all(_RE_UL.match(l) for l in linie):
            pozycje = "".join("<li>" + _inline(_RE_UL.sub("", l), myslnik, linki) + "</li>" for l in linie)
            wynik.append(f"<ul>{pozycje}</ul>")
            continue
        if all(_RE_OL.match(l) for l in linie):
            pozycje = "".join("<li>" + _inline(_RE_OL.sub("", l), myslnik, linki) + "</li>" for l in linie)
            wynik.append(f"<ol>{pozycje}</ol>")
            continue
        wynik.append(f"<p>{_inline(' '.join(l.strip() for l in linie), myslnik, linki)}</p>")
    return "\n".join(wynik)


def front_matter(tekst: str) -> tuple[dict, str]:
    """Nagłówek „--- klucz: wartość ---” na początku pliku .md → (słownik, treść)."""
    t = tekst.replace("\r\n", "\n")
    if not t.startswith("---\n"):
        return {}, t
    koniec = t.find("\n---", 4)
    if koniec < 0:
        return {}, t
    naglowek = t[4:koniec]
    tresc = t[koniec + 4:].lstrip("\n")
    dane = {}
    for linia in naglowek.split("\n"):
        linia = re.sub(r"\s+#.*$", "", linia).strip()
        if not linia or ":" not in linia:
            continue
        k, _, v = linia.partition(":")
        v = v.strip().strip('"')
        dane[k.strip()] = v if v else None
    return dane, tresc
