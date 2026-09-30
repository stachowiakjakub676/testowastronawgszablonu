#!/usr/bin/env python3
"""Karta jakości strony: raport/KARTA-JAKOSCI.md i raport/KARTA-JAKOSCI.html z wyników tools/sprawdz.sh.

To jest dokument dla klienta: zmierzone liczby zamiast zapewnień (KONTRAKT §2, docs/PROCEDURA.md faza 9).

  python3 tools/raport.py                                  z raport/ i dist/ (po bash tools/sprawdz.sh)
  python3 tools/raport.py --klient przyklady/bimex --wyjscie dist-bimex --raport raport-bimex
  python3 tools/raport.py --readme                         dodatkowo: sekcja „Do potwierdzenia z właścicielem”
                                                           w README.md klienta (z data/firma.json → do_potwierdzenia)

Czyta (co jest — brakujące pozycje karta oznacza „nie zmierzono”):
  raport/build.json          wynik build.py --json: strony, UKRYTO, ostrzeżenia, rozmiary
  raport/kroki.tsv           statusy kroków sprawdz.sh
  raport/zrzuty.json         przewijanie, konsola, obce domeny, ciasteczka, waga i żądania pierwszego widoku
  raport/pa11y/*.json        axe (WCAG 2 AA)
  raport/lighthouse/*.json   Lighthouse: telefon i komputer
  dist/**/*.html             typy JSON-LD
  data/firma.json, data/zdjecia.json, brief/zrodla.md   źródła i lista do potwierdzenia

Tylko biblioteka standardowa Pythona ≥ 3.10.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
KATEGORIE = [("performance", "Wydajność"), ("accessibility", "Dostępność"), ("best-practices", "Dobre praktyki"),
             ("seo", "SEO")]
POCZATEK = "<!-- do-potwierdzenia:poczatek -->"
KONIEC = "<!-- do-potwierdzenia:koniec -->"


def sciezka(s: str) -> Path:
    """Jak build.py: względna od bieżącego katalogu, a gdy tam jej nie ma — od korzenia repozytorium."""
    p = Path(s)
    if p.is_absolute():
        return p
    return Path.cwd() / p if (Path.cwd() / p).exists() else KORZEN / p


def czytaj_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class JsonLd(HTMLParser):
    def __init__(self):
        super().__init__()
        self.w = False
        self.bloki: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.w = True
            self.bloki.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self.w = False

    def handle_data(self, data):
        if self.w:
            self.bloki[-1] += data


def typy_jsonld(dist: Path) -> dict[str, list[str]]:
    """Typ → lista stron, na których występuje (węzły najwyższego poziomu @graph)."""
    typy: dict[str, list[str]] = {}
    for plik in sorted(dist.rglob("*.html")):
        if "admin" in plik.parts:
            continue
        p = JsonLd()
        try:
            p.feed(plik.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        strona = "/" + str(plik.relative_to(dist).with_suffix("")).replace(os.sep, "/")
        strona = "/" if strona == "/index" else strona
        for blok in p.bloki:
            try:
                d = json.loads(blok)
            except ValueError:
                continue
            wezly = d.get("@graph", [d]) if isinstance(d, dict) else d
            for w in wezly:
                t = w.get("@type") if isinstance(w, dict) else None
                for x in (t if isinstance(t, list) else [t]):
                    if x and strona not in typy.setdefault(x, []):
                        typy[x].append(strona)
    return typy


def lighthouse(katalog: Path) -> dict[str, dict]:
    wynik = {}
    for p in sorted(katalog.glob("*.json")):
        d = czytaj_json(p)
        if not d or "categories" not in d:
            continue
        audyty = d.get("audits", {})
        wynik[p.stem] = {
            # brak wyniku (nieudany pomiar) = „—”, nie 0
            "kategorie": {k: (None if d["categories"][k]["score"] is None else round(d["categories"][k]["score"] * 100))
                          for k, _ in KATEGORIE if k in d["categories"]},
            "lcp": audyty.get("largest-contentful-paint", {}).get("displayValue"),
            "cls": audyty.get("cumulative-layout-shift", {}).get("displayValue"),
            "waga": audyty.get("total-byte-weight", {}).get("numericValue"),
        }
    return wynik


def pa11y(katalog: Path) -> dict[str, int | None]:
    wynik = {}
    for p in sorted(katalog.glob("*.json")):
        d = czytaj_json(p)
        wynik[p.stem] = len(d) if isinstance(d, list) else None
    return wynik


def zrodla_liczba(klient: Path, firma: dict | None) -> tuple[int, int, int]:
    """(pola z firma.zrodla, zdjęcia ze źródłem, adresy w brief/zrodla.md)."""
    f = len((firma or {}).get("zrodla") or {})
    zd = czytaj_json(klient / "data" / "zdjecia.json") or {}
    z = sum(1 for x in zd.get("zdjecia") or [] if x.get("zrodlo"))
    b = 0
    plik = klient / "brief" / "zrodla.md"
    if plik.is_file():
        # adresy-wzory z szablonu pliku („…?rejestr=P”) się nie liczą
        b = len({u for u in re.findall(r"https?://[^\s)>|]+", plik.read_text(encoding="utf-8")) if "…" not in u})
    return f, z, b


def kb(b) -> str:
    return "—" if b is None else f"{b / 1024:,.0f} KB".replace(",", " ")


def zbierz(raport: Path, klient: Path, dist: Path) -> dict:
    build = czytaj_json(raport / "build.json") or {}
    kom = build.get("komunikaty", [])
    firma = czytaj_json(klient / "data" / "firma.json")
    zrz = czytaj_json(raport / "zrzuty.json") or {}
    zrz_t = czytaj_json(raport / "zrzuty-tryby.json") or {}
    wszystkie = (zrz.get("wyniki") or []) + (zrz_t.get("wyniki") or [])
    pierwszy = next((w for w in zrz.get("wyniki") or [] if w["sciezka"] == "/" and w["widok"] == "375"), None)
    kroki = []
    if (raport / "kroki.tsv").is_file():
        for wiersz in (raport / "kroki.tsv").read_text(encoding="utf-8").splitlines():
            czesci = wiersz.split("\t")
            if len(czesci) == 3:
                kroki.append(czesci)
    dzis = os.environ.get("SZABLON_DZIS") or dt.date.today().isoformat()
    return {
        "data": dzis,
        "firma": ((firma or {}).get("firma") or {}).get("nazwa") or "(brak nazwy)",
        "domena": ((firma or {}).get("firma") or {}).get("domena"),
        "strony": (build.get("wynik") or {}).get("strony") or [],
        "rozmiary": (build.get("wynik") or {}).get("rozmiary") or {},
        "ukryto": [k["tresc"] for k in kom if k["poziom"] == "UKRYTO"],
        "bledy": [k["tresc"] for k in kom if k["poziom"] == "BŁĄD"],
        "ostrzezenia": [k["tresc"] for k in kom if k["poziom"] == "OSTRZEŻENIE"],
        "do_potwierdzenia": (firma or {}).get("do_potwierdzenia") or [],
        "kroki": kroki,
        "lighthouse": lighthouse(raport / "lighthouse"),
        "pa11y": pa11y(raport / "pa11y"),
        "pierwszy_widok": (pierwszy or {}).get("pierwszy_widok"),
        "obce_domeny": sorted({d for w in wszystkie for d in w.get("obce_domeny", [])}) if wszystkie else None,
        "ciasteczka": max((w.get("ciasteczka", 0) for w in wszystkie), default=None) if wszystkie else None,
        "pamiec": max((w.get("pamiec", 0) for w in wszystkie), default=None) if wszystkie else None,
        "przewijanie": max((w.get("przewijanie", 0) for w in wszystkie), default=None) if wszystkie else None,
        "konsola": sum(len(w.get("konsola", [])) for w in wszystkie) if wszystkie else None,
        "widoki": len(wszystkie),
        "jsonld": typy_jsonld(dist) if dist.is_dir() else {},
        "zrodla": zrodla_liczba(klient, firma),
    }


def markdown(d: dict) -> str:
    w = [f"# Karta jakości — {d['firma']}", ""]
    w.append(f"Stan na {d['data']}. Wszystkie liczby są zmierzone narzędziami (`bash tools/sprawdz.sh`), "
             "nie wpisane ręcznie. Surowe wyniki: katalog `raport/`.")
    if d["domena"]:
        w.append(f"Adres: {d['domena']}")
    w += ["", "## Lighthouse (Google)", ""]
    if d["lighthouse"]:
        w.append("| Strona i urządzenie | " + " | ".join(n for _, n in KATEGORIE) + " | LCP |")
        w.append("|---|" + "---:|" * (len(KATEGORIE) + 1))
        for nazwa, x in d["lighthouse"].items():
            strona, _, urz = nazwa.rpartition("-")
            strona = "/" if strona == "glowna" else "/" + strona.replace("_", "/")
            w.append(f"| {strona} ({urz}) | " + " | ".join(str(x["kategorie"].get(k) if x["kategorie"].get(k) is not None else "—")
                                                           for k, _ in KATEGORIE)
                     + f" | {x['lcp'] or '—'} |")
        w.append("")
        w.append("Cel: dostępność, dobre praktyki i SEO = 100, wydajność ≥ 90. Pomiar lokalny (bez kompresji i CDN "
                 "Cloudflare) — na serwerze wydajność jest zwykle wyższa.")
    else:
        w.append("Nie zmierzono (brak `raport/lighthouse/*.json` — Lighthouse nie jest zainstalowany albo pominięty).")
    w += ["", "## Szybkość i prywatność pierwszego wejścia (telefon 375 × 667)", ""]
    pw = d["pierwszy_widok"]
    w.append("| Pomiar | Wynik | Cel |")
    w.append("|---|---:|---:|")
    w.append(f"| Waga pierwszego widoku strony głównej | {kb(pw['bajty']) if pw else '—'} | ≤ 600 KB |")
    w.append(f"| Liczba żądań pierwszego widoku | {pw['zadania'] if pw else '—'} | ≤ 30 |")
    roz = d["rozmiary"]
    w.append(f"| CSS strony / JS strony (bez kompresji) | {kb(roz.get('css'))} / {kb(roz.get('js'))} | ≤ 60 KB / ≤ 30 KB |")
    od = d["obce_domeny"]
    w.append(f"| Zapytania do obcych serwerów (Google, Facebook…) | {'—' if od is None else len(od)} | 0 |")
    w.append(f"| Ciasteczka po wejściu | {'—' if d['ciasteczka'] is None else d['ciasteczka']} | 0 |")
    w.append(f"| Dane w localStorage / sessionStorage | {'—' if d['pamiec'] is None else d['pamiec']} | 0 |")
    w.append(f"| Przewijanie w poziomie (375 / 768 / 1440 px) | {'—' if d['przewijanie'] is None else str(d['przewijanie']) + ' px'} | 0 px |")
    w.append(f"| Błędy w konsoli przeglądarki | {'—' if d['konsola'] is None else d['konsola']} | 0 |")
    if od:
        w.append("")
        w.append("Obce serwery: " + ", ".join(od))
    if d["widoki"]:
        w.append("")
        w.append(f"Sprawdzono {d['widoki']} widoków (każda strona w 3 szerokościach, strony kluczowe także bez JavaScriptu "
                 "i z emulacją trybu wymuszonych kolorów). Bez ciasteczek i obcych skryptów strona nie potrzebuje banera cookies.")
    w += ["", "## Dostępność (axe, WCAG 2 AA)", ""]
    if d["pa11y"]:
        zle = {k: v for k, v in d["pa11y"].items() if v != 0}
        if not zle:
            w.append(f"0 problemów na {len(d['pa11y'])} stronach.")
        else:
            w.append(f"Problemy na {len(zle)} z {len(d['pa11y'])} stron: "
                     + ", ".join(f"{k} ({'błąd pomiaru' if v is None else v})" for k, v in zle.items()))
    else:
        w.append("Nie zmierzono (brak `raport/pa11y/*.json`).")
    w += ["", "## Dane dla wyszukiwarek (JSON-LD)", ""]
    if d["jsonld"]:
        for t, strony in sorted(d["jsonld"].items()):
            w.append(f"- `{t}` — " + (", ".join(strony[:6]) + (f" i {len(strony) - 6} innych" if len(strony) > 6 else "")))
    else:
        w.append("Brak (nie znaleziono zbudowanej strony).")
    w += ["", "## Kroki kontroli", ""]
    if d["kroki"]:
        for nazwa, status, opis in d["kroki"]:
            w.append(f"- **{status}** {nazwa}: {opis}")
    else:
        w.append("Brak `raport/kroki.tsv` — uruchom `bash tools/sprawdz.sh`.")
    if d["bledy"]:
        w += ["", "Błędy buildu:"] + [f"- {x}" for x in d["bledy"]]
    w += ["", f"## Strony ({len(d['strony'])})", "", ", ".join(d["strony"]) or "—"]
    w += ["", "## Czego strona nie pokazuje i dlaczego", ""]
    w.append("Szablon nie wstawia tekstów zastępczych: sekcja bez prawdziwych danych nie powstaje.")
    w.append("")
    w += [f"- {x}" for x in d["ukryto"]] or ["- nic — wszystkie sekcje mają dane"]
    w += ["", "## Do potwierdzenia z właścicielem", ""]
    w += [f"- {x}" for x in d["do_potwierdzenia"]] or ["- nic"]
    f, z, b = d["zrodla"]
    w += ["", "## Źródła treści", ""]
    w.append(f"Pola danych ze źródłem: {f}. Zdjęcia z opisanym pochodzeniem: {z}. Adresy źródeł w `brief/zrodla.md`: {b}.")
    w += ["", "---", "", "Wygenerowano: `python3 tools/raport.py` (SZABLON). Lista funkcji strony: `docs/CO-ZAWIERA-STRONA.md`."]
    return "\n".join(w) + "\n"


def html_z_markdown(md: str, tytul: str) -> str:
    """Prosta, samodzielna strona z karty (tabele, listy, nagłówki) — do wysłania klientowi jako plik."""
    wyjscie, tabela, lista = [], [], False

    def inline(t: str) -> str:
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", t)

    def zamknij():
        nonlocal tabela, lista
        if tabela:
            wiersze = [r for r in tabela if not re.fullmatch(r"\|[-:|]+\|?", r)]
            komorki = [[c.strip() for c in r.strip("|").split("|")] for r in wiersze]
            wyjscie.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in komorki[0]) + "</tr></thead><tbody>"
                           + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in komorki[1:])
                           + "</tbody></table>")
            tabela = []
        if lista:
            wyjscie.append("</ul>")
            lista = False

    for w in md.splitlines():
        if w.startswith("|"):
            tabela.append(w)
            continue
        if w.startswith("- "):
            if tabela:
                zamknij()
            if not lista:
                wyjscie.append("<ul>")
                lista = True
            wyjscie.append(f"<li>{inline(w[2:])}</li>")
            continue
        zamknij()
        if w.startswith("# "):
            wyjscie.append(f"<h1>{inline(w[2:])}</h1>")
        elif w.startswith("## "):
            wyjscie.append(f"<h2>{inline(w[3:])}</h2>")
        elif w == "---":
            wyjscie.append("<hr>")
        elif w.strip():
            wyjscie.append(f"<p>{inline(w)}</p>")
    zamknij()
    styl = ("body{font:17px/1.6 system-ui,sans-serif;color:#1a1a1a;background:#fff;max-width:960px;margin:0 auto;padding:32px 16px}"
            "h1{font-size:2rem;line-height:1.15;margin:0 0 16px}h2{font-size:1.25rem;margin:40px 0 12px;padding-top:12px;"
            "border-top:1px solid #1a1a1a}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}"
            "th,td{text-align:left;padding:8px 12px 8px 0;border-bottom:1px solid #d0d0d0;vertical-align:top}"
            "td:not(:first-child),th:not(:first-child){text-align:right}code{font-size:.9em}hr{border:0;border-top:1px solid #d0d0d0}"
            "@media print{body{padding:0}}")
    return (f'<!doctype html>\n<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
            f'initial-scale=1"><title>{html.escape(tytul)}</title><style>{styl}</style></head><body>\n'
            + "\n".join(wyjscie) + "\n</body></html>\n")


def sekcja_readme(lista: list[str]) -> str:
    wiersze = [POCZATEK,
               "<!-- generuje: python3 tools/raport.py --readme (z data/firma.json → do_potwierdzenia); nie edytuj ręcznie -->"]
    wiersze += [f"- {x}" for x in lista] or ["- nic — wszystkie fakty na stronie mają źródło"]
    wiersze.append(KONIEC)
    return "\n".join(wiersze)


def aktualizuj_readme(readme: Path, lista: list[str]) -> str:
    nowa = sekcja_readme(lista)
    tekst = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    if POCZATEK in tekst and KONIEC in tekst:
        a, _, reszta = tekst.partition(POCZATEK)
        _, _, b = reszta.partition(KONIEC)
        tekst = a + nowa + b
    else:
        tekst = tekst.rstrip() + ("\n\n" if tekst else "") + "## Do potwierdzenia z właścicielem\n\n" + nowa + "\n"
    readme.write_text(tekst, encoding="utf-8")
    return str(readme)


def main() -> int:
    p = argparse.ArgumentParser(description="Karta jakości z wyników tools/sprawdz.sh.")
    p.add_argument("--raport", default="raport", help="katalog wyników sprawdz.sh (domyślnie raport)")
    p.add_argument("--klient", default=".", help="katalog klienta (domyślnie korzeń repozytorium)")
    p.add_argument("--wyjscie", default="dist", help="katalog zbudowanej strony (domyślnie dist)")
    p.add_argument("--readme", action="store_true", help="zaktualizuj sekcję „Do potwierdzenia z właścicielem” w README.md klienta")
    p.add_argument("--json", action="store_true", help="zebrane dane jako JSON")
    a = p.parse_args()
    raport, klient, dist = sciezka(a.raport), sciezka(a.klient), sciezka(a.wyjscie)
    if not (klient / "data" / "firma.json").is_file():
        print(f"Nie ma {klient / 'data' / 'firma.json'} — podaj --klient", file=sys.stderr)
        return 1
    raport.mkdir(parents=True, exist_ok=True)
    d = zbierz(raport, klient, dist)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    md = markdown(d)
    (raport / "KARTA-JAKOSCI.md").write_text(md, encoding="utf-8")
    (raport / "KARTA-JAKOSCI.html").write_text(html_z_markdown(md, f"Karta jakości — {d['firma']}"), encoding="utf-8")
    if not a.json:
        print(f"Zapisano: {raport / 'KARTA-JAKOSCI.md'} i {raport / 'KARTA-JAKOSCI.html'}")
    if a.readme:
        print("Zaktualizowano: " + aktualizuj_readme(klient / "README.md", d["do_potwierdzenia"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
