#!/usr/bin/env python3
"""Zdjęcia i ikony: oryginały z brief/zdjecia → pliki gotowe dla strony (KONTRAKT §4.3, critic §3.8).

Uruchamiane lokalnie (wymaga Pillow), wynik commituje się do repozytorium — build.py sam nie przetwarza obrazów.

  python3 tools/zdjecia.py                          dla danych w korzeniu repozytorium
  python3 tools/zdjecia.py --klient przyklady/bimex
  python3 tools/zdjecia.py --tylko wytwornia droga  tylko wybrane id
  python3 tools/zdjecia.py --nadpisz                przelicz także istniejące pliki

Co robi:
- usuwa EXIF (także GPS), obraca wg EXIF, zamienia na sRGB;
- zapisuje assets/img/foto/<id>-<szer>.{avif,webp,jpg} w szerokościach 480/960/1440/1920, nie większych niż oryginał
  (plus szerokość oryginału, jeśli jest o > 10 % większa od ostatniej); AVIF q50, WebP q75, JPEG q80 progresywny;
- assets/img/foto/manifest.json: {"<id>": {"szer", "wys", "szerokosci", "formaty"}};
- assets/img/og.jpg 1200×630 ze zdjęcia hero (kadr wg „punkt” z data/zdjecia.json), a bez zdjęcia hero — logo
  na środku, na kolorze tła strony (marka.tlo);
- assets/img/ikony/: favicon.ico (32), icon.svg (gdy logo jest SVG), apple-touch-icon.png (180, pełne tło),
  icon-192.png, icon-512.png, icon-maskable-512.png, logo-naglowek.png (3× szerokość logo w nagłówku).
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
SZEROKOSCI = (480, 960, 1440, 1920)
TLA = {"biale": "#FFFFFF", "cieple": "#FAF8F4", "chlodne": "#F7F9FA"}

try:
    from PIL import Image, ImageCms, ImageOps, features
except ImportError:
    sys.exit("Zainstaluj Pillow: python3 -m pip install pillow")


def srgb(obraz: "Image.Image") -> "Image.Image":
    """Obrót wg EXIF, profil kolorów → sRGB, bez metadanych. Przezroczystość zostaje: PNG z paletą (tryb P z kluczem
    „transparency”), LA i PA przechodzą na RGBA — inaczej logo z przezroczystym tłem robiło się czarnym kwadratem."""
    obraz = ImageOps.exif_transpose(obraz)
    if obraz.mode not in ("RGB", "RGBA"):
        przezroczyste = obraz.mode in ("PA", "LA", "La") or "transparency" in obraz.info
        obraz = obraz.convert("RGBA" if przezroczyste else "RGB")
    icc = obraz.info.get("icc_profile")
    if icc:
        try:
            wej = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            obraz = ImageCms.profileToProfile(obraz, wej, ImageCms.createProfile("sRGB"),
                                              outputMode="RGBA" if obraz.mode in ("RGBA", "LA") else "RGB")
        except (ImageCms.PyCMSError, OSError):
            pass
    if obraz.mode not in ("RGB", "RGBA"):
        obraz = obraz.convert("RGBA" if "A" in obraz.getbands() else "RGB")
    obraz.info.pop("exif", None)
    obraz.info.pop("icc_profile", None)
    return obraz


def splaszcz(obraz: "Image.Image", tlo: str = "#FFFFFF") -> "Image.Image":
    if obraz.mode == "RGBA":
        podklad = Image.new("RGB", obraz.size, tlo)
        podklad.paste(obraz, mask=obraz.split()[3])
        return podklad
    return obraz.convert("RGB")


def szerokosci(w: int) -> list[int]:
    lista = [s for s in SZEROKOSCI if s <= w]
    if not lista or w > lista[-1] * 1.1:
        lista.append(w)
    return lista


def kadr(obraz: "Image.Image", proporcja: float, punkt=(0.5, 0.5)) -> "Image.Image":
    """Wycięcie o zadanej proporcji (szer/wys) możliwie blisko punktu ostrości."""
    w, h = obraz.size
    if w / h > proporcja:
        nw = round(h * proporcja)
        x = min(max(round(punkt[0] * w - nw / 2), 0), w - nw)
        return obraz.crop((x, 0, x + nw, h))
    nh = round(w / proporcja)
    y = min(max(round(punkt[1] * h - nh / 2), 0), h - nh)
    return obraz.crop((0, y, w, y + nh))


def zapisz_warianty(zdj: dict, klient: Path, cel: Path, nadpisz: bool) -> dict | None:
    zrodlo = klient / zdj["zrodlo_plik"]
    if not zrodlo.is_file():
        print(f"  BŁĄD: {zdj['id']}: nie ma pliku {zdj['zrodlo_plik']}")
        return None
    with Image.open(zrodlo) as o:
        obraz = splaszcz(srgb(o))
    w, h = obraz.size
    lista = szerokosci(w)
    formaty = ["avif", "webp", "jpg"] if features.check("avif") else ["webp", "jpg"]
    for s in lista:
        mniejszy = obraz if s == w else obraz.resize((s, round(h * s / w)), Image.LANCZOS)
        for fmt in formaty:
            plik = cel / f"{zdj['id']}-{s}.{fmt}"
            if plik.exists() and not nadpisz:
                continue
            if fmt == "avif":
                mniejszy.save(plik, "AVIF", quality=50, speed=4)
            elif fmt == "webp":
                mniejszy.save(plik, "WEBP", quality=75, method=6)
            else:
                mniejszy.save(plik, "JPEG", quality=80, progressive=True, optimize=True)
    rozm = {f: sum((cel / f"{zdj['id']}-{s}.{f}").stat().st_size for s in lista) // 1024 for f in formaty}
    print(f"  {zdj['id']}: {w}×{h} → {', '.join(map(str, lista))} px ({', '.join(f'{f} {k} KB' for f, k in rozm.items())})")
    return {"szer": w, "wys": h, "szerokosci": lista, "formaty": formaty}


def og(zdj: dict, klient: Path, cel: Path) -> None:
    with Image.open(klient / zdj["zrodlo_plik"]) as o:
        obraz = splaszcz(srgb(o))
    wyciety = kadr(obraz, 1200 / 630, zdj.get("punkt") or (0.5, 0.5)).resize((1200, 630), Image.LANCZOS)
    wyciety.save(cel, "JPEG", quality=82, progressive=True, optimize=True)
    print(f"  {cel.parent.name + '/' if cel.parent.name == 'og' else ''}{cel.name}: 1200×630 z „{zdj['id']}” "
          f"({cel.stat().st_size // 1024} KB)")


def og_z_logo(firma: dict, klient: Path, cel: Path) -> bool:
    """og.jpg bez zdjęcia hero: logo (maks. 60 % szerokości i 45 % wysokości) na środku, na kolorze tła strony."""
    marka = firma["marka"]
    zrodlo = klient / marka["logo"] if marka.get("logo") else None
    if zrodlo is not None and zrodlo.suffix.lower() == ".svg":
        zrodlo = zrodlo.with_suffix(".png")
    if zrodlo is None or not zrodlo.is_file():
        return False
    tlo = TLA.get(marka.get("tlo") or "biale", marka.get("tlo") or "#FFFFFF")
    with Image.open(zrodlo) as o:
        logo = srgb(o).convert("RGBA")
    logo.thumbnail((720, 284), Image.LANCZOS)
    plotno = Image.new("RGBA", (1200, 630), tlo)
    plotno.alpha_composite(logo, ((1200 - logo.width) // 2, (630 - logo.height) // 2))
    plotno.convert("RGB").save(cel, "JPEG", quality=85, progressive=True, optimize=True)
    print(f"  og.jpg: 1200×630 z logo na tle {tlo} (brak zdjęcia hero) ({cel.stat().st_size // 1024} KB)")
    return True


def na_kwadrat(logo: "Image.Image", bok: int, wypelnienie: float, tlo=None) -> "Image.Image":
    """Logo wpasowane w kwadrat (wypelnienie = część boku zajęta przez logo)."""
    plotno = Image.new("RGBA", (bok, bok), tlo or (0, 0, 0, 0))
    miejsce = round(bok * wypelnienie)
    l = logo.copy()
    l.thumbnail((miejsce, miejsce), Image.LANCZOS)
    plotno.alpha_composite(l, ((bok - l.width) // 2, (bok - l.height) // 2))
    return plotno


def ikony(firma: dict, klient: Path, cel: Path) -> None:
    marka = firma["marka"]
    if not marka.get("logo"):
        print("  ikony: brak marka.logo — pomijam")
        return
    zrodlo = klient / marka["logo"]
    cel.mkdir(parents=True, exist_ok=True)
    tlo = TLA.get(marka.get("tlo") or "biale", marka.get("tlo") or "#FFFFFF")
    if zrodlo.suffix.lower() == ".svg":
        shutil.copy(zrodlo, cel / "icon.svg")
        png = next((p for p in [zrodlo.with_suffix(".png")] if p.is_file()), None)
        if png is None:
            print("  ikony: logo SVG skopiowane jako icon.svg; do PNG/ICO potrzebny jest też plik logo .png obok")
            return
        zrodlo = png
    with Image.open(zrodlo) as o:
        logo = srgb(o).convert("RGBA")
    na_kwadrat(logo, 32, 1.0).save(cel / "favicon.ico", sizes=[(32, 32)])
    na_kwadrat(logo, 180, 0.84, tlo).convert("RGB").save(cel / "apple-touch-icon.png", optimize=True)
    na_kwadrat(logo, 192, 1.0).save(cel / "icon-192.png", optimize=True)
    na_kwadrat(logo, 512, 1.0).save(cel / "icon-512.png", optimize=True)
    na_kwadrat(logo, 512, 0.62, tlo).convert("RGB").save(cel / "icon-maskable-512.png", optimize=True)
    # logo w nagłówku: maks. logo_szerokosc × wysokość 56 px (nagłówek 72 px), zapisane 3× — ostre także na telefonach
    # z gęstością 3 (iPhone, większość Androidów); paleta 256 kolorów (logo to zwykle kilka płaskich barw)
    szer = round(min(marka.get("logo_szerokosc") or 140, 56 * logo.width / logo.height) * 3)
    if logo.width > szer:
        l = logo.resize((szer, round(logo.height * szer / logo.width)), Image.LANCZOS)
        l.quantize(colors=256, method=Image.Quantize.FASTOCTREE).save(cel / "logo-naglowek.png", optimize=True)
    print(f"  ikony: favicon.ico, apple-touch-icon.png, icon-192/512, icon-maskable-512"
          + (", logo-naglowek.png" if logo.width > szer else ""))


def main() -> int:
    p = argparse.ArgumentParser(description="Zdjęcia → AVIF/WebP/JPEG, og.jpg i ikony (wymaga Pillow).")
    p.add_argument("--klient", default=".")
    p.add_argument("--tylko", nargs="*", help="tylko te id zdjęć")
    p.add_argument("--nadpisz", action="store_true", help="przelicz istniejące pliki")
    a = p.parse_args()
    klient = Path(a.klient)
    if not klient.is_absolute():
        klient = (Path.cwd() / klient) if (Path.cwd() / klient).exists() else KORZEN / klient
    dane = klient / "data"
    try:
        zdjecia = json.loads((dane / "zdjecia.json").read_text(encoding="utf-8"))["zdjecia"]
        firma = json.loads((dane / "firma.json").read_text(encoding="utf-8"))
        tresc = json.loads((dane / "tresc.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"BŁĄD: nie mogę wczytać danych z {dane}: {e}")
        return 1
    foto = klient / "assets" / "img" / "foto"
    foto.mkdir(parents=True, exist_ok=True)
    plik_manifestu = foto / "manifest.json"
    manifest = json.loads(plik_manifestu.read_text(encoding="utf-8")) if plik_manifestu.exists() else {}
    print(f"Zdjęcia ({klient}):")
    for z in zdjecia:
        if a.tylko and z["id"] not in a.tylko:
            continue
        wynik = zapisz_warianty(z, klient, foto, a.nadpisz)
        if wynik:
            manifest[z["id"]] = wynik
    ids = {z["id"] for z in zdjecia}
    for stary in [k for k in manifest if k not in ids]:
        del manifest[stary]
        for f in foto.glob(f"{stary}-*.*"):
            f.unlink()
        print(f"  usunięto warianty „{stary}” (nie ma go już w data/zdjecia.json)")
    plik_manifestu.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hero = (tresc.get("hero") or {}).get("zdjecie")
    zdj_hero = next((z for z in zdjecia if z["id"] == hero), None)
    if zdj_hero:
        og(zdj_hero, klient, klient / "assets" / "img" / "og.jpg")
    elif not og_z_logo(firma, klient, klient / "assets" / "img" / "og.jpg"):
        print("  og.jpg: brak zdjęcia hero (tresc.hero.zdjecie) i logo (marka.logo w assets/img/) — obrazka podglądu "
              "linku nie ma; dodaj jedno z nich i uruchom ponownie")
    # podstrony usług (/oferta/<slug>, pozycja z plikiem .md): własny obrazek podglądu linku ze zdjęcia pozycji —
    # build bierze assets/img/og/<id>.jpg, a gdy go nie ma, og.jpg strony (KONTRAKT §6.1)
    for poz in ((tresc.get("oferta") or {}).get("pozycje") or []):
        zdj = next((z for z in zdjecia if z["id"] == poz.get("zdjecie")), None)
        if poz.get("tresc") and zdj and (klient / zdj["zrodlo_plik"]).is_file():
            (klient / "assets" / "img" / "og").mkdir(parents=True, exist_ok=True)
            og(zdj, klient, klient / "assets" / "img" / "og" / f"{zdj['id']}.jpg")
    ikony(firma, klient, klient / "assets" / "img" / "ikony")
    return 0


if __name__ == "__main__":
    sys.exit(main())
