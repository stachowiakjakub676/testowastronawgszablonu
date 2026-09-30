"""Obrazy: odczyt wymiarów bez Pillow i gotowy <picture> (KONTRAKT §8).

build.py nie przetwarza zdjęć — czyta tylko assets/img/foto/manifest.json (wynik tools/zdjecia.py)
i data/zdjecia.json. Brak wariantów w manifeście: w --produkcja błąd, poza nim ostrzeżenie i zwykły <img>
z oryginałem (skopiowanym do dist/assets/img/foto/).
"""
from __future__ import annotations

import html
import json
import re
import shutil
import struct
from pathlib import Path


def wymiary(sciezka) -> tuple[int, int]:
    """(szerokość, wysokość) obrazka JPEG, PNG, WebP, AVIF, GIF albo SVG (viewBox)."""
    with open(sciezka, "rb") as f:
        d = f.read(1 << 16)
    if d[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", d[16:24])
    if d[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", d[6:10])
    if d[:4] == b"RIFF" and d[8:12] == b"WEBP":
        rodzaj = d[12:16]
        if rodzaj == b"VP8 ":
            w, h = struct.unpack("<HH", d[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if rodzaj == b"VP8L":
            b = int.from_bytes(d[21:25], "little")
            return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
        if rodzaj == b"VP8X":
            return int.from_bytes(d[24:27], "little") + 1, int.from_bytes(d[27:30], "little") + 1
    if d[:2] == b"\xff\xd8":  # JPEG: szukamy znacznika SOFn
        with open(sciezka, "rb") as f:
            d = f.read()
        i = 2
        while i < len(d) - 9:
            if d[i] != 0xFF:
                i += 1
                continue
            znacznik = d[i + 1]
            if znacznik in (0xD8, 0x01, 0xFF) or 0xD0 <= znacznik <= 0xD7:
                i += 1 if znacznik == 0xFF else 2
                continue
            dl = struct.unpack(">H", d[i + 2:i + 4])[0]
            if znacznik in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", d[i + 5:i + 9])
                return w, h
            i += 2 + dl
    if d[4:12] in (b"ftypavif", b"ftypavis", b"ftypmif1", b"ftypheic"):
        j = d.find(b"ispe")
        if j > 0:
            return struct.unpack(">II", d[j + 8:j + 16])
    if b"<svg" in d[:1024]:
        m = re.search(rb'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"', d)
        if m:
            return round(float(m.group(1))), round(float(m.group(2)))
        mw = re.search(rb'<svg[^>]*\swidth="([\d.]+)', d)
        mh = re.search(rb'<svg[^>]*\sheight="([\d.]+)', d)
        if mw and mh:
            return round(float(mw.group(1))), round(float(mh.group(1)))
    raise ValueError(f"nie rozpoznano formatu obrazka: {sciezka}")


# wariant → (sizes, lazy?)
WARIANTY = {
    "hero": ("(min-width: 960px) 58vw, 100vw", False),
    "pol": ("(min-width: 960px) 50vw, 100vw", True),
    "tercja": ("(min-width: 960px) 33vw, (min-width: 600px) 50vw, 100vw", True),
    "miniatura": ("(min-width: 600px) 240px, 50vw", True),
    "pelny": ("100vw", True),
}
TYPY = {"avif": "image/avif", "webp": "image/webp", "jpg": "image/jpeg"}


class Obrazy:
    def __init__(self, klient: Path, zdjecia: dict, raport, zasob, dist: Path):
        self.klient, self.zdjecia, self.raport, self.zasob, self.dist = klient, zdjecia, raport, zasob, dist
        plik = klient / "assets" / "img" / "foto" / "manifest.json"
        self.manifest = json.loads(plik.read_text(encoding="utf-8")) if plik.exists() else {}

    def _srcset(self, zid: str, wpis: dict, fmt: str) -> str:
        return ", ".join(f"{self.zasob(f'assets/img/foto/{zid}-{w}.{fmt}')} {w}w" for w in wpis["szerokosci"])

    def _zapasowy(self, zid: str, zdj: dict, wariant: str) -> str:
        """Bez wariantów z tools/zdjecia.py: kopiujemy oryginał i dajemy zwykły <img>."""
        self.raport.ostrzezenie(f"zdjęcie „{zid}” nie ma wariantów AVIF/WebP/JPEG — użyto oryginału",
                                plik="assets/img/foto/manifest.json",
                                naprawa=f"uruchom: python3 tools/zdjecia.py --klient {self.klient}")
        zrodlo = self.klient / zdj["zrodlo_plik"]
        if not zrodlo.is_file():
            self.raport.blad(f"zdjęcie „{zid}”: nie ma pliku {zdj['zrodlo_plik']}", plik="data/zdjecia.json",
                             pole=f"zdjecia[{zid}].zrodlo_plik")
            return ""
        cel = self.dist / "assets" / "img" / "foto" / f"{zid}{zrodlo.suffix.lower()}"
        cel.parent.mkdir(parents=True, exist_ok=True)
        if not cel.exists():
            shutil.copy(zrodlo, cel)
        w, h = wymiary(zrodlo)
        _, lazy = WARIANTY[wariant]
        atr = ' loading="lazy"' if lazy else ' fetchpriority="high"'
        return (f'<img class="foto foto--{zid}" src="{html.escape(self.zasob(f"assets/img/foto/{cel.name}"))}" '
                f'width="{w}" height="{h}" alt="{html.escape(zdj["alt"])}" decoding="async"{atr}>')

    def picture(self, zid: str, wariant: str = "pol") -> str:
        if wariant not in WARIANTY:
            raise ValueError(f"nieznany wariant obrazu „{wariant}” (dostępne: {', '.join(WARIANTY)})")
        zdj = self.zdjecia.get(zid)
        if zdj is None:
            raise ValueError(f"nie ma zdjęcia o id „{zid}” w data/zdjecia.json")
        wpis = self.manifest.get(zid)
        if not wpis:
            return self._zapasowy(zid, zdj, wariant)
        sizes, lazy = WARIANTY[wariant]
        zrodla = []
        mob = zdj.get("kadr_mobilny")
        if mob and self.manifest.get(mob):
            wm = self.manifest[mob]
            for fmt in wm["formaty"]:
                zrodla.append(f'<source media="(max-width: 599px)" type="{TYPY[fmt]}" '
                              f'srcset="{html.escape(self._srcset(mob, wm, fmt))}" sizes="100vw">')
        for fmt in wpis["formaty"]:
            if fmt == "jpg":
                continue
            zrodla.append(f'<source type="{TYPY[fmt]}" srcset="{html.escape(self._srcset(zid, wpis, fmt))}" '
                          f'sizes="{sizes}">')
        szer = wpis["szerokosci"]
        najw = szer[-1]
        wys = round(najw * wpis["wys"] / wpis["szer"])
        src = next((w for w in szer if w >= 960), najw)
        atr = ' loading="lazy"' if lazy else ' fetchpriority="high"'
        img = (f'<img src="{html.escape(self.zasob(f"assets/img/foto/{zid}-{src}.jpg"))}" '
               f'srcset="{html.escape(self._srcset(zid, wpis, "jpg"))}" sizes="{sizes}" '
               f'width="{najw}" height="{wys}" alt="{html.escape(zdj["alt"])}" decoding="async"{atr}>')
        return f'<picture class="foto foto--{zid}">{"".join(zrodla)}{img}</picture>'

    def css_punkty(self) -> str:
        """Reguły object-position dla zdjęć z punktem ostrości innym niż środek (bez atrybutów style)."""
        reguly = []
        for zid, z in self.zdjecia.items():
            p = z.get("punkt") or [0.5, 0.5]
            if abs(p[0] - 0.5) > 0.01 or abs(p[1] - 0.5) > 0.01:
                reguly.append(f".foto--{zid} img,img.foto--{zid}{{object-position:{p[0] * 100:.0f}% {p[1] * 100:.0f}%}}")
        return "\n".join(reguly)
