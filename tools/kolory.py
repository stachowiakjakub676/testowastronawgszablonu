#!/usr/bin/env python3
"""Kolor marki: odczyt z logo i raport kontrastu tokenów (KONTRAKT §7.2, docs/PROCEDURA.md faza 3).

  python3 tools/kolory.py logo brief/logo.png            najczęstsze kolory logo (bez bieli, czerni i przezroczystości)
  python3 tools/kolory.py raport "#C8471F"               tokeny :root z tego koloru i kontrast każdej pary
  python3 tools/kolory.py raport "#FFD100" --tlo cieple --dodatkowy "#D12A1E"
  python3 tools/kolory.py raport --klient przyklady/bimex   kolor, tło i kolor dodatkowy z data/firma.json → marka
  … --json                                                wynik jako JSON (dla AI)

Tokeny liczy ten sam kod co build (tools/silnik/kolory.py), więc raport = to, co będzie na stronie.
Odczyt z logo wymaga Pillow (lokalnie); raport — tylko biblioteka standardowa.
Kolor wybiera człowiek albo AI po obejrzeniu logo i szyldu — skrypt podaje kandydatów, nie decyduje.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN / "tools"))

from silnik import kolory  # noqa: E402


def kolory_logo(plik: Path, ile: int = 6) -> list[dict]:
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("Odczyt z logo wymaga Pillow: python3 -m pip install pillow "
                         "(albo odczytaj kolor z pliku SVG: atrybuty fill=\"#…\")")
    if plik.suffix.lower() == ".svg":
        import re
        tekst = plik.read_text(encoding="utf-8", errors="replace")
        licz: dict[str, int] = {}
        for h in re.findall(r"#([0-9a-fA-F]{6})\b", tekst):
            licz["#" + h.upper()] = licz.get("#" + h.upper(), 0) + 1
        razem = sum(licz.values()) or 1
        return [{"kolor": k, "udzial": round(v / razem, 3), "zrodlo": "SVG"} for k, v in
                sorted(licz.items(), key=lambda x: -x[1])[:ile]]
    obraz = Image.open(plik).convert("RGBA")
    obraz.thumbnail((256, 256))
    licz = {}
    piksele = getattr(obraz, "get_flattened_data", None) or obraz.getdata   # Pillow ≥ 12.1 / starsze
    for r, g, b, a in piksele():
        if a < 200:
            continue
        L, C, _ = kolory.rgb_na_oklch((r / 255, g / 255, b / 255))
        if C < 0.03 and (L > 0.92 or L < 0.25):     # tło i kontury: biel, czerń, szarości
            continue
        klucz = (r // 12 * 12 + 6, g // 12 * 12 + 6, b // 12 * 12 + 6)   # kubełki, żeby antyaliasing się nie liczył osobno
        licz[klucz] = licz.get(klucz, 0) + 1
    razem = sum(licz.values()) or 1
    wynik = []
    for (r, g, b), n in sorted(licz.items(), key=lambda x: -x[1]):
        h = kolory.rgb_na_hex((min(r, 255) / 255, min(g, 255) / 255, min(b, 255) / 255)).upper()
        if any(kolory.kontrast(h, w["kolor"]) < 1.15 for w in wynik):   # prawie ten sam kolor
            continue
        wynik.append({"kolor": h, "udzial": round(n / razem, 3)})
        if len(wynik) >= ile:
            break
    for w in wynik:
        w["na_bialym"] = round(kolory.kontrast(w["kolor"], "#FFFFFF"), 2)
    return wynik


def raport(marka: dict) -> dict:
    try:
        tokeny, pary = kolory.tokeny(marka)
    except ValueError as e:
        raise SystemExit(f"BŁĄD: {e}")
    return {
        "marka": {k: marka.get(k) for k in ("kolor", "tlo", "kolor_dodatkowy")},
        "tokeny": tokeny,
        "kontrast": [{"tekst": a, "tlo": b, "wynik": round(w, 2), "minimum": m, "opis": o, "ok": w >= m}
                     for a, b, w, m, o in pary],
        "uwagi": uwagi(marka, tokeny),
    }


def uwagi(marka: dict, t: dict) -> list[str]:
    u = []
    if t["--marka-tekst"] == t["--tekst"]:
        u.append("kolor marki jest za jasny na tekst — linki i akcenty tekstowe będą w kolorze tekstu, "
                 "a marka zostaje w wypełnieniach (przycisk, podkreślenia)")
    if t["--przycisk"] != (marka.get("kolor") or "").upper():
        u.append(f"przycisk ma przyciemniony kolor marki {t['--przycisk']}, bo oryginał nie daje 4,5:1 z napisem")
    if t["--na-przycisku"] != "#FFFFFF":
        u.append("napis na przycisku jest ciemny (kolor marki jest jasny)")
    return u


def druk(r: dict) -> None:
    m = r["marka"]
    print(f"Marka: {m['kolor']}  tło: {m['tlo'] or 'biale'}  kolor dodatkowy: {m['kolor_dodatkowy'] or '—'}\n")
    print("Tokeny (:root):")
    for k, v in r["tokeny"].items():
        print(f"  {k:24} {v}")
    print("\nKontrast (WCAG):")
    for p in r["kontrast"]:
        print(f"  {'OK ' if p['ok'] else 'ZA MAŁO'}  {p['wynik']:5.2f} ≥ {p['minimum']:<4}  {p['opis']} ({p['tekst']} na {p['tlo']})")
    for x in r["uwagi"]:
        print(f"\nUwaga: {x}")
    zle = [p for p in r["kontrast"] if not p["ok"]]
    print(f"\nWynik: {'OK — wszystkie pary przechodzą' if not zle else f'{len(zle)} par za słabych — build tego nie przepuści'}")


def main() -> int:
    p = argparse.ArgumentParser(description="Kolor marki: kandydaci z logo i raport kontrastu tokenów.")
    pod = p.add_subparsers(dest="polecenie", required=True)
    pl = pod.add_parser("logo", help="najczęstsze kolory logo")
    pl.add_argument("plik")
    pl.add_argument("--ile", type=int, default=6)
    pl.add_argument("--json", action="store_true")
    pr = pod.add_parser("raport", help="tokeny i kontrast dla koloru marki")
    pr.add_argument("kolor", nargs="?", help="#RRGGBB (albo --klient)")
    pr.add_argument("--tlo", default=None, help="biale | cieple | chlodne | #hex")
    pr.add_argument("--dodatkowy", default=None, help="drugi kolor z logo (fokus)")
    pr.add_argument("--klient", default=None, help="weź marka.* z <klient>/data/firma.json")
    pr.add_argument("--json", action="store_true")
    a = p.parse_args()

    if a.polecenie == "logo":
        plik = Path(a.plik)
        if not plik.is_file():
            raise SystemExit(f"Nie ma pliku {plik}")
        w = kolory_logo(plik, a.ile)
        if a.json:
            print(json.dumps(w, ensure_ascii=False, indent=2))
        else:
            print(f"Kolory w {plik} (bez bieli, czerni i przezroczystości), od najczęstszego:")
            for x in w:
                extra = f"  kontrast z bielą {x['na_bialym']}:1" if "na_bialym" in x else ""
                print(f"  {x['kolor']}  {x['udzial'] * 100:5.1f}%{extra}")
            print("\nWybierz kolor, który firma naprawdę kojarzy ze sobą (logo, szyld, auta), i sprawdź go:\n"
                  "  python3 tools/kolory.py raport \"#RRGGBB\"\n"
                  "Wpisz go w data/firma.json → marka.kolor, a skąd jest — w marka.kolor_zrodlo.")
        return 0

    marka = {"kolor": a.kolor, "tlo": a.tlo, "kolor_dodatkowy": a.dodatkowy}
    if a.klient:
        kl = Path(a.klient)
        kl = kl if kl.is_absolute() or kl.exists() else KORZEN / kl
        try:
            m = json.loads((kl / "data" / "firma.json").read_text(encoding="utf-8"))["marka"]
        except (OSError, ValueError, KeyError) as e:
            raise SystemExit(f"Nie da się odczytać marka z {kl / 'data' / 'firma.json'}: {e}")
        marka = {"kolor": a.kolor or m.get("kolor"), "tlo": a.tlo or m.get("tlo"),
                 "kolor_dodatkowy": a.dodatkowy or m.get("kolor_dodatkowy")}
    if not marka["kolor"]:
        raise SystemExit("Podaj kolor (#RRGGBB) albo --klient z uzupełnionym marka.kolor")
    try:
        kolory.hex_na_rgb(marka["kolor"])
    except Exception:
        raise SystemExit(f"„{marka['kolor']}” to nie jest kolor #RRGGBB")
    r = raport(marka)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        druk(r)
    return 0 if all(x["ok"] for x in r["kontrast"]) else 1


if __name__ == "__main__":
    sys.exit(main())
