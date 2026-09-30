#!/usr/bin/env python3
"""Podgląd wyniku buildu jak na Cloudflare (tylko biblioteka standardowa).

  python3 tools/podglad.py                   http://localhost:8765 z katalogu dist/
  python3 tools/podglad.py --port 8000 --katalog dist-test
  python3 tools/podglad.py --bez-naglowkow   bez nagłówków z _headers

- adresy bez .html działają jak na produkcji (/kontakt → kontakt.html, /oferta/x → oferta/x.html);
- nieistniejący adres → 404.html ze statusem 404;
- POST /api/* → 503 {"blad":"nie_skonfigurowano"} (jak Worker bez Resend — formularz otwiera wtedy mailto:);
- nagłówki z dist/_headers (CSP, X-Frame-Options…) są dodawane do odpowiedzi, więc błędy CSP widać w konsoli
  przeglądarki już lokalnie; po ponownym buildzie serwer sam wczytuje nowy _headers (nie trzeba go restartować). Pomijamy tylko HSTS i „upgrade-insecure-requests” (lokalnie nie ma HTTPS).
"""
from __future__ import annotations

import argparse
import fnmatch
import http.server
import os
from functools import partial
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent


def wczytaj_naglowki(plik: Path) -> list[tuple[str, list[tuple[str, str | None]]]]:
    """_headers → [(wzorzec ścieżki, [(nazwa, wartość | None = usuń)])]. Reguły z pełnym adresem są pomijane."""
    reguly: list[tuple[str, list]] = []
    if not plik.is_file():
        return reguly
    for linia in plik.read_text(encoding="utf-8").splitlines():
        if not linia.strip() or linia.lstrip().startswith("#"):
            continue
        if not linia[0].isspace():
            reguly.append((linia.strip(), []))
        elif reguly:
            wpis = linia.strip()
            if wpis.startswith("!"):
                reguly[-1][1].append((wpis[1:].strip(), None))
            elif ":" in wpis:
                nazwa, _, wartosc = wpis.partition(":")
                reguly[-1][1].append((nazwa.strip(), wartosc.strip()))
    return [(w, n) for w, n in reguly if w.startswith("/")]


class Obsluga(http.server.SimpleHTTPRequestHandler):
    reguly: list = []
    plik_naglowkow: Path | None = None     # dist/_headers — czytany ponownie po każdym buildzie (zmiana mtime)
    _mtime: float | None = None

    @classmethod
    def odswiez_naglowki(cls):
        if cls.plik_naglowkow is None:
            return
        try:
            mtime = cls.plik_naglowkow.stat().st_mtime
        except OSError:
            mtime = None
        if mtime != cls._mtime:
            cls._mtime = mtime
            cls.reguly = wczytaj_naglowki(cls.plik_naglowkow)

    def _plik(self, sciezka: str) -> Path | None:
        katalog = Path(self.directory)
        sciezka = sciezka.split("?", 1)[0].split("#", 1)[0]
        wzgl = sciezka.lstrip("/")
        kandydaci = [katalog / wzgl] if wzgl else []
        kandydaci += [katalog / (wzgl.rstrip("/") + ".html"), katalog / wzgl / "index.html"]
        for k in kandydaci:
            try:
                k.resolve().relative_to(katalog.resolve())
            except ValueError:
                return None
            if k.is_file():
                return k
        return None

    def send_head(self):
        plik = self._plik(self.path)
        if plik is None:
            strona404 = Path(self.directory) / "404.html"
            dane = strona404.read_bytes() if strona404.is_file() else b"404"
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(dane)))
            self._naglowki("/404")
            self.end_headers()
            return _Bufor(dane)
        self.path = "/" + str(plik.relative_to(self.directory))
        return super().send_head()

    def do_POST(self):
        """Lokalnie nie ma Workera: /api/* odpowiada jak Worker bez skonfigurowanej wysyłki (JS otworzy mailto:)."""
        dane = b'{"blad":"nie_skonfigurowano"}' if self.path.startswith("/api/") else b"{}"
        self.send_response(503 if self.path.startswith("/api/") else 405)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dane)))
        self.end_headers()
        self.wfile.write(dane)

    def _naglowki(self, sciezka: str):
        self.odswiez_naglowki()
        naglowki: dict[str, str] = {}
        for wzorzec, lista in self.reguly:
            if fnmatch.fnmatch(sciezka, wzorzec) or (wzorzec.endswith("/*") and sciezka == wzorzec[:-2]):
                for nazwa, wartosc in lista:
                    if wartosc is None:
                        naglowki.pop(nazwa.lower(), None)
                    else:
                        naglowki[nazwa.lower()] = f"{nazwa}: {wartosc}"
        naglowki.pop("strict-transport-security", None)
        for klucz, linia in naglowki.items():
            nazwa, _, wartosc = linia.partition(": ")
            if klucz == "content-security-policy":
                wartosc = "; ".join(d for d in wartosc.split("; ") if d != "upgrade-insecure-requests")
            self.send_header(nazwa, wartosc)
        if "cache-control" not in naglowki:
            self.send_header("Cache-Control", "no-cache")

    def send_response(self, code, message=None):
        super().send_response(code, message)
        if code == 200:
            self._naglowki(self.path.split("?", 1)[0])

    def guess_type(self, path):
        if str(path).endswith(".webmanifest"):
            return "application/manifest+json"
        if str(path).endswith(".avif"):
            return "image/avif"
        return super().guess_type(path)

    def log_message(self, fmt, *args):
        if os.environ.get("PODGLAD_CICHO"):
            return
        super().log_message(fmt, *args)


class _Bufor:
    def __init__(self, dane: bytes):
        self.dane = dane

    def read(self, *_):
        d, self.dane = self.dane, b""
        return d

    def close(self):
        pass


def main():
    p = argparse.ArgumentParser(description="Podgląd dist/ z adresami bez .html, stroną 404 i nagłówkami z _headers.")
    p.add_argument("--katalog", default="dist")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--bez-naglowkow", action="store_true")
    a = p.parse_args()
    katalog = Path(a.katalog)
    katalog = katalog if katalog.is_absolute() else (Path.cwd() / katalog if (Path.cwd() / katalog).exists() else KORZEN / katalog)
    if not katalog.is_dir():
        raise SystemExit(f"Nie ma katalogu {katalog} — najpierw zbuduj stronę: python3 tools/build.py")
    Obsluga.plik_naglowkow = None if a.bez_naglowkow else katalog / "_headers"
    Obsluga.odswiez_naglowki()
    serwer = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), partial(Obsluga, directory=str(katalog)))
    print(f"Podgląd {katalog}: http://localhost:{a.port}/  (Ctrl+C kończy)")
    try:
        serwer.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
