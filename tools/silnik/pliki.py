"""Pliki na stronie: typ, rozmiar i liczba stron PDF liczone przez build (KONTRAKT §4.2, §9.1).

Jeden moduł dla wszystkich sekcji z plikami: do_pobrania (`informacje`), karta i cennik w PDF (`opis`),
skany certyfikatów (`dane.plik_info`). Autor danych podaje tylko ścieżkę, więc rozmiar i strony nie rozjadą się
z plikiem. Na stronie: „Katalog 2026 — PDF, 8,4 MB, 48 stron”. Liczby stron nie zgadujemy: gdy nie da się jej odczytać
(uszkodzony albo zaszyfrowany PDF), na stronie jej nie ma. Tylko biblioteka standardowa (re, zlib).
"""
from __future__ import annotations

import re
import zlib
from pathlib import Path

from . import typografia as typo

# drzewo stron: węzeł /Type /Pages z /Count = liczba stron (korzeń drzewa ma największą wartość)
_RE_PAGES = re.compile(rb"/Type\s*/Pages(?![A-Za-z])")
_RE_COUNT = re.compile(rb"/Count\s+(\d+)")
# pojedyncza strona: /Type /Page — ale nie /Pages
_RE_PAGE = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
# początek strumienia: „>> stream” (PDF 1.5+ trzyma obiekty stron w skompresowanych strumieniach /ObjStm)
_RE_STRUMIEN = re.compile(rb">>\s*stream\r?\n")


def _slownik(dane: bytes, poz: int) -> bytes:
    """Najmniejszy słownik << … >>, w którym stoi pozycja `poz` (bez zagnieżdżonych słowników w środku liczenia)."""
    i, glebokosc = poz, 0
    while i > 1:
        para = dane[i - 2:i]
        if para == b">>":
            glebokosc += 1
            i -= 2
        elif para == b"<<":
            if glebokosc == 0:
                break
            glebokosc -= 1
            i -= 2
        else:
            i -= 1
    poczatek = i - 2 if i > 1 else 0
    j, glebokosc = poz, 0
    while j < len(dane) - 1:
        para = dane[j:j + 2]
        if para == b"<<":
            glebokosc += 1
            j += 2
        elif para == b">>":
            if glebokosc == 0:
                break
            glebokosc -= 1
            j += 2
        else:
            j += 1
    return dane[poczatek:j + 2]


def _policz(dane: bytes) -> int:
    liczniki = []
    for m in _RE_PAGES.finditer(dane):
        c = _RE_COUNT.search(_slownik(dane, m.start()))
        if c:
            liczniki.append(int(c.group(1)))
    if liczniki:
        return max(liczniki)
    return len(_RE_PAGE.findall(dane))


TYPY = {"pdf": "PDF", "doc": "DOC", "docx": "DOCX", "xls": "XLS", "xlsx": "XLSX", "odt": "ODT", "ods": "ODS",
        "zip": "ZIP", "dwg": "DWG", "dxf": "DXF", "jpg": "JPG", "jpeg": "JPG", "png": "PNG", "txt": "TXT", "csv": "CSV"}
MIME = {"pdf": "application/pdf", "zip": "application/zip", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "doc": "application/msword", "xls": "application/vnd.ms-excel", "csv": "text/csv", "txt": "text/plain",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "odt": "application/vnd.oasis.opendocument.text", "ods": "application/vnd.oasis.opendocument.spreadsheet"}


def strony_pdf(dane: bytes) -> int | None:
    """Liczba stron PDF albo None, gdy nie da się jej ustalić. Najpierw zwykły tekst pliku, potem rozpakowane
    strumienie obiektów /ObjStm (FlateDecode). W pliku zaszyfrowanym (/Encrypt) strumienie są nieczytelne — wtedy
    tylko zwykły tekst."""
    if not dane.startswith(b"%PDF-"):
        return None
    n = _policz(dane)
    if n or b"/Encrypt" in dane:
        return n or None
    rozpakowane = []
    for m in _RE_STRUMIEN.finditer(dane):
        poczatek = dane.rfind(b"obj", max(0, m.start() - 4000), m.start())     # „12 0 obj << … >> stream”
        slownik = dane[poczatek:m.start()] if poczatek >= 0 else b""
        if b"/ObjStm" not in slownik or b"/FlateDecode" not in slownik:
            continue                           # tylko strumienie obiektów — treść stron (rysunki) pomijamy
        koniec = dane.find(b"endstream", m.end())
        try:
            rozpakowane.append(zlib.decompressobj().decompress(dane[m.end():koniec if koniec > 0 else None]))
        except zlib.error:
            continue
    n = _policz(b"\n".join(rozpakowane))
    return n or None


def rozmiar(bajty: int) -> str:
    """„640 kB”, „8,4 MB” — przecinek dziesiętny i twarda spacja przed jednostką (kB i MB nie ma w typografia.JEDNOSTKI)."""
    if bajty < 1024 * 1024:
        return f"{max(1, round(bajty / 1024))}{typo.NBSP}kB"
    mb = bajty / (1024 * 1024)
    return f"{mb:.1f}".replace(".", ",") + f"{typo.NBSP}MB"


def informacje(plik: Path) -> dict:
    """{typ, mime, rozmiar, strony, strony_tekst, meta} — meta = „PDF, 8,4 MB, 48 stron” (do linku i opisu)."""
    rozsz = plik.suffix.lower().lstrip(".")
    dane = plik.read_bytes()
    strony = strony_pdf(dane) if rozsz == "pdf" else None
    typ = TYPY.get(rozsz, rozsz.upper() or "plik")
    czesci = [typ, rozmiar(len(dane))]
    strony_tekst = None
    if strony:
        strony_tekst = f"{strony}{typo.NBSP}{typo.liczba_mnoga(strony, 'strona,strony,stron')}"
        czesci.append(strony_tekst)
    return {"typ": typ, "mime": MIME.get(rozsz), "rozmiar": rozmiar(len(dane)), "bajty": len(dane),
            "strony": strony, "strony_tekst": strony_tekst, "meta": ", ".join(czesci)}


def opis(plik: Path) -> dict:
    """Skrót dla linków „… do pobrania (PDF, 240 kB, 2 strony)” w karcie i cenniku: {typ, rozmiar, strony, tekst}."""
    i = informacje(plik)
    return {"typ": i["typ"], "rozmiar": i["rozmiar"], "strony": i["strony"], "tekst": i["meta"]}
