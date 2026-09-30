"""Kolory: jeden kolor marki (z logo/szyldu) → tokeny :root z gwarantowanym kontrastem WCAG (KONTRAKT §7.2).

Liczymy w OKLCH (jasność L, nasycenie C, odcień H), bo zmiana samej jasności nie zmienia odcienia marki.
Build sprawdza kontrast każdej pary tekst/tło i przerywa, gdy któraś nie przechodzi.
"""
from __future__ import annotations

import math

# ------------------------------------------------------------------ konwersje (z prototypu kolory_proto.py)


def hex_na_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_na_hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02X}" for c in rgb)


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def rgb_na_oklch(rgb):
    r, g, b = (_lin(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def _oklch_na_rgb_surowe(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(_gam(c) if c >= 0 else -_gam(-c) for c in (r, g, bl))


def oklch_na_hex(L, C, H) -> str:
    """Poza gamutem sRGB zmniejszamy nasycenie (C), zachowując jasność i odcień."""
    L = max(0.0, min(1.0, L))
    rgb = _oklch_na_rgb_surowe(L, C, H)
    if not all(-1e-4 <= c <= 1 + 1e-4 for c in rgb):
        lo, hi = 0.0, C
        for _ in range(30):
            mid = (lo + hi) / 2
            if all(-1e-4 <= c <= 1 + 1e-4 for c in _oklch_na_rgb_surowe(L, mid, H)):
                lo = mid
            else:
                hi = mid
        rgb = _oklch_na_rgb_surowe(L, lo, H)
    return rgb_na_hex(rgb)


def oklch(h: str):
    return rgb_na_oklch(hex_na_rgb(h))


def luminancja(h: str) -> float:
    r, g, b = (_lin(c) for c in hex_na_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(a: str, b: str) -> float:
    la, lb = luminancja(a), luminancja(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def dopasuj(kolor: str, tla: list[str], cel: float, kierunek: int | None = None) -> str | None:
    """Najbliższa (w jasności) wersja koloru o tym samym odcieniu, która ma ≥ cel na wszystkich tłach.
    kierunek: -1 tylko ciemniej, +1 tylko jaśniej, None — oba, wybierz bliższy."""
    if all(kontrast(kolor, t) >= cel for t in tla):
        return kolor
    L, C, H = oklch(kolor)
    kandydaci = []
    for k in ([kierunek] if kierunek else [-1, 1]):
        l = L
        while 0 <= l <= 1:
            l += 0.004 * k
            h = oklch_na_hex(l, C, H)
            if all(kontrast(h, t) >= cel for t in tla):
                kandydaci.append((abs(l - L), h))
                break
    return min(kandydaci)[1] if kandydaci else None


# ------------------------------------------------------------------ tokeny

TLA = {
    "biale": ("#FFFFFF", None),
    "cieple": ("#FAF8F4", None),
    "chlodne": ("#F7F9FA", None),
}


def tokeny(marka: dict) -> tuple[dict, list[tuple[str, str, float, float, str]]]:
    """Zwraca (tokeny CSS, lista kontroli kontrastu: (pierwszy plan, tło, wynik, wymagane, opis))."""
    kolor = (marka.get("kolor") or "#555555").upper()
    Lm, Cm, Hm = oklch(kolor)
    tlo_ust = marka.get("tlo") or "biale"
    tlo = TLA[tlo_ust][0] if tlo_ust in TLA else tlo_ust.upper()
    Lt, Ct, Ht = oklch(tlo)
    if Lt < 0.9:
        raise ValueError(f"marka.tlo {tlo} jest za ciemne — szablon zakłada jasne tło strony (jasność OKLCH ≥ 0,9)")
    # odcień neutralnych kolorów: lekko w stronę marki (bardzo małe nasycenie), żeby szarości nie były „martwe”
    Hn = Hm if Cm > 0.02 else Ht
    t: dict[str, str] = {"--tlo": tlo}
    t["--tlo-2"] = oklch_na_hex(Lt - 0.035, min(0.012, Ct + 0.006), Ht if Ct > 0.005 else Hn)
    t["--tekst"] = dopasuj(oklch_na_hex(0.21, 0.012, Hn), [t["--tlo"], t["--tlo-2"]], 12.0, -1) or "#111111"
    t["--tekst-2"] = dopasuj(oklch_na_hex(0.47, 0.014, Hn), [t["--tlo"], t["--tlo-2"]], 5.8, -1) or "#4A4A4A"
    t["--linia"] = oklch_na_hex(Lt - 0.10, 0.008, Hn)
    t["--linia-mocna"] = dopasuj(oklch_na_hex(0.62, 0.01, Hn), [t["--tlo"], t["--tlo-2"]], 3.0, -1) or "#767676"
    t["--marka"] = kolor
    # kolor marki w tekście (linki, akcenty): ta sama barwa, przyciemniona do 4,5:1. Jeśli trzeba ją przyciemnić
    # tak bardzo, że przestaje przypominać markę (np. żółty → oliwkowy), używamy koloru tekstu.
    mt = dopasuj(kolor, [t["--tlo"], t["--tlo-2"]], 4.8, -1)
    t["--marka-tekst"] = mt if mt and Lm - oklch(mt)[0] <= 0.25 else t["--tekst"]
    # przycisk główny: kolor marki z białym albo ciemnym napisem (≥ 4,5:1); inaczej przyciemniona marka
    na_bialy, na_ciemny = kontrast("#FFFFFF", kolor), kontrast(t["--tekst"], kolor)
    if na_bialy >= 4.5:
        t["--przycisk"], t["--na-przycisku"] = kolor, "#FFFFFF"
    elif na_ciemny >= 4.5:
        t["--przycisk"], t["--na-przycisku"] = kolor, t["--tekst"]
    else:
        t["--przycisk"], t["--na-przycisku"] = dopasuj(kolor, ["#FFFFFF"], 4.6, -1) or "#333333", "#FFFFFF"
    # przycisk prawie bezbarwny i jasny (biel, jasna szarość) zlałby się z tłem — wtedy ciemne wypełnienie
    if kontrast(t["--przycisk"], tlo) < 3.0 and oklch(t["--przycisk"])[1] < 0.03:
        t["--przycisk"], t["--na-przycisku"] = t["--tekst"], tlo
    Lp, Cp, Hp = oklch(t["--przycisk"])
    # po najechaniu: wyraźnie ciemniej (≥ 0,10 jasności OKLCH — przy 0,06 żółty przycisk BIMEX wyglądał tak samo);
    # gdy ciemniej się nie da (czerń) albo napis traci kontrast — jaśniej; ostatecznie mniejszy krok
    if Lp < 0.3:                                      # czerń i bardzo ciemne: ciemniej już nie widać różnicy
        hover = oklch_na_hex(max(Lp + 0.1, 0.3), Cp, Hp)
    else:
        hover = next((h for h in (oklch_na_hex(Lp - 0.10, Cp, Hp), oklch_na_hex(Lp + 0.10, Cp, Hp),
                                  oklch_na_hex(Lp - 0.06, Cp, Hp)) if kontrast(h, t["--na-przycisku"]) >= 4.5),
                     oklch_na_hex(Lp + 0.05, Cp, Hp))
    t["--przycisk-hover"] = hover
    # obrys przycisku (WCAG 1.4.11, ≥ 3:1 z tłem): kolor marki, a gdy jest za jasny (żółty) — kolor tekstu,
    # jak ramka tablicy z logo; tak samo po najechaniu
    ramka = lambda kolor: kolor if kontrast(kolor, tlo) >= 3.0 and kontrast(kolor, t["--tlo-2"]) >= 3.0 else t["--tekst"]
    t["--przycisk-ramka"] = ramka(t["--przycisk"])
    t["--przycisk-ramka-hover"] = ramka(hover)
    t["--marka-jasna"] = oklch_na_hex(0.965, min(Cm * 0.35, 0.04), Hm)
    # ciemna sekcja (stopka albo kontakt)
    t["--ciemne"] = oklch_na_hex(0.2, min(0.015, Cm * 0.2 + 0.004), Hn)
    t["--na-ciemnym"] = dopasuj(oklch_na_hex(0.97, 0.004, Hn), [t["--ciemne"]], 12.0, 1) or "#FFFFFF"
    t["--na-ciemnym-2"] = dopasuj(oklch_na_hex(0.78, 0.01, Hn), [t["--ciemne"]], 6.0, 1) or "#CCCCCC"
    t["--linia-na-ciemnym"] = oklch_na_hex(0.34, 0.008, Hn)
    t["--akcent-na-ciemnym"] = dopasuj(kolor, [t["--ciemne"]], 4.8, 1) or t["--na-ciemnym"]
    # fokus: jeden kolor widoczny (≥ 3:1) na jasnych tłach; na ciemnym osobny wariant, jeśli trzeba
    zrodlo_focus = (marka.get("kolor_dodatkowy") or "").upper() or kolor
    jasne_tla = [t["--tlo"], t["--tlo-2"], t["--marka-jasna"]]
    f = dopasuj(zrodlo_focus, jasne_tla + [t["--ciemne"]], 3.2)
    if f:
        t["--focus"] = t["--focus-na-ciemnym"] = f
    else:
        t["--focus"] = dopasuj(zrodlo_focus, jasne_tla, 3.2, -1) or t["--tekst"]
        t["--focus-na-ciemnym"] = dopasuj(zrodlo_focus, [t["--ciemne"]], 3.2, 1) or t["--na-ciemnym"]
    t["--blad"] = dopasuj("#C62828", [t["--tlo"], t["--tlo-2"]], 5.0, -1) or "#8B0000"
    t["--ok"] = dopasuj("#2E7D32", [t["--tlo"], t["--tlo-2"]], 5.0, -1) or "#1B5E20"

    pary = [
        ("--tekst", "--tlo", 7.0, "tekst na tle strony"),
        ("--tekst", "--tlo-2", 7.0, "tekst na tle sekcji wyróżnionej"),
        ("--tekst", "--marka-jasna", 7.0, "tekst na jasnym tle marki"),
        ("--tekst-2", "--tlo", 5.5, "tekst pomocniczy na tle strony"),
        ("--tekst-2", "--tlo-2", 5.5, "tekst pomocniczy na tle sekcji"),
        ("--tekst-2", "--marka-jasna", 4.5, "tekst pomocniczy na jasnym tle marki"),
        ("--linia-mocna", "--tlo", 3.0, "obramowanie pól formularza"),
        ("--linia-mocna", "--tlo-2", 3.0, "obramowanie pól na tle sekcji"),
        ("--marka-tekst", "--tlo", 4.5, "linki i akcenty w tekście"),
        ("--marka-tekst", "--tlo-2", 4.5, "linki na tle sekcji"),
        ("--na-przycisku", "--przycisk", 4.5, "napis na przycisku"),
        ("--na-przycisku", "--przycisk-hover", 4.5, "napis na przycisku po najechaniu"),
        ("--przycisk-ramka", "--tlo", 3.0, "obrys przycisku głównego na tle strony"),
        ("--przycisk-ramka", "--tlo-2", 3.0, "obrys przycisku głównego na tle sekcji"),
        ("--na-ciemnym", "--ciemne", 7.0, "tekst w ciemnej sekcji"),
        ("--na-ciemnym-2", "--ciemne", 5.5, "tekst pomocniczy w ciemnej sekcji"),
        ("--akcent-na-ciemnym", "--ciemne", 4.5, "akcent w ciemnej sekcji"),
        ("--focus", "--tlo", 3.0, "obwódka fokusu na tle strony"),
        ("--focus", "--tlo-2", 3.0, "obwódka fokusu na tle sekcji"),
        ("--focus-na-ciemnym", "--ciemne", 3.0, "obwódka fokusu w ciemnej sekcji"),
        ("--blad", "--tlo", 4.5, "komunikat błędu"),
        ("--ok", "--tlo", 4.5, "komunikat potwierdzenia"),
    ]
    kontrole = [(a, b, kontrast(t[a], t[b]), minimum, opis) for a, b, minimum, opis in pary]
    return t, kontrole


def css_root(t: dict) -> str:
    return ":root{" + ";".join(f"{k}:{v}" for k, v in t.items()) + "}"


if __name__ == "__main__":
    for k in ["#C8471F", "#FFD100", "#3B9EDB", "#1F7A4D", "#E30613", "#6B6B6B", "#FFFFFF", "#F2F2F2", "#FFF3B0",
              "#000000", "#111111"]:
        tok, kon = tokeny({"kolor": k, "tlo": "biale", "kolor_dodatkowy": None})
        zle = [f"{a}/{b} {w:.2f}<{m}" for a, b, w, m, _ in kon if w < m]
        print(k, {x: tok[x] for x in ("--marka-tekst", "--przycisk", "--na-przycisku", "--przycisk-hover",
                                      "--przycisk-ramka", "--focus")}, "BŁĘDY:" if zle else "ok", zle)
