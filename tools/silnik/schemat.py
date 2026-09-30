"""Mini-walidator podzbioru JSON Schema 2020-12 z polskimi komunikatami (tylko biblioteka standardowa).

Obsługuje: type (także lista, "null"), required, properties, additionalProperties (false albo schemat),
enum, const, pattern, format (email, date, uri, time), minLength, maxLength, minimum, maximum, items,
minItems, maxItems, uniqueItems, oneOf, anyOf, $ref (#/$defs/...). Klucze danych zaczynające się od „$”
(np. "$schema", "$komentarz") są pomijane.

Komunikat: (ścieżka „kontakt.adres.kod”, treść). Ścieżki list: „oferta.pozycje[2].nazwa”.

„pattern” musi pasować do całego tekstu (re.fullmatch): w re.search „$” pasuje też przed końcowym „\n”, więc
„https://x.workers.dev\n” przechodził i łamał wiersz w _headers. Znaki sterujące (poza nową linią i tabulatorem
w tekstach Markdown) oraz separatory U+2028/U+2029 są błędem w każdym polu tekstowym.
"""
from __future__ import annotations

import datetime as _dt
import re

TYPY = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
NAZWY_TYPOW = {"object": "obiekt {…}", "array": "lista […]", "string": "tekst", "boolean": "true/false",
               "null": "null", "integer": "liczba całkowita", "number": "liczba"}
FORMATY = {
    "email": r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}",
    "date": r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])",
    "uri": r"https://[^\s]+",
    "time": r"([01]\d|2[0-3]):[0-5]\d",
}


# znaki, których nie ma w żadnym tekście od firmy: sterujące C0 (bez \t i \n), DEL, C1, separatory wiersza/akapitu
RE_STERUJACE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029]")


def _typ_ok(v, t) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, TYPY[t])


def _nazwa_typu(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true/false"
    if isinstance(v, int):
        return "liczba całkowita"
    if isinstance(v, float):
        return "liczba"
    if isinstance(v, str):
        return "tekst"
    if isinstance(v, list):
        return "lista"
    if isinstance(v, dict):
        return "obiekt"
    return type(v).__name__


def _sciezka(baza: str, klucz) -> str:
    if isinstance(klucz, int):
        return f"{baza}[{klucz}]"
    return f"{baza}.{klucz}" if baza else str(klucz)


def waliduj(v, s: dict, root: dict | None = None, sciezka: str = "") -> list[tuple[str, str]]:
    root = root or s
    if "$ref" in s:
        nazwa = s["$ref"].split("/")[-1]
        s = {**root["$defs"][nazwa], **{k: x for k, x in s.items() if k != "$ref"}}
    bledy: list[tuple[str, str]] = []
    miejsce = sciezka or "(plik)"

    if "oneOf" in s or "anyOf" in s:
        warianty = s.get("oneOf") or s.get("anyOf")
        wyniki = [waliduj(v, w, root, sciezka) for w in warianty]
        pasujace = [w for w in wyniki if not w]
        if not pasujace:
            # pokaż błędy wariantu, który „najbardziej pasuje” (najmniej błędów, nie-null)
            niepuste = [w for w, war in zip(wyniki, warianty) if war.get("type") != "null"]
            return min(niepuste or wyniki, key=len)
        rest = {k: x for k, x in s.items() if k not in ("oneOf", "anyOf")}
        if not rest:
            return []
        s = rest

    t = s.get("type")
    if t is not None:
        typy = t if isinstance(t, list) else [t]
        if not any(_typ_ok(v, x) for x in typy):
            oczek = " albo ".join(NAZWY_TYPOW.get(x, x) for x in typy)
            return [(miejsce, f"oczekiwano: {oczek}; jest: {_nazwa_typu(v)}")]
    if v is None:
        return bledy
    if "enum" in s and v not in s["enum"]:
        bledy.append((miejsce, f"wartość {v!r} spoza listy: {', '.join(repr(x) for x in s['enum'])}"))
    if "const" in s and v != s["const"]:
        bledy.append((miejsce, f"musi być {s['const']!r}"))
    if isinstance(v, str):
        zly = RE_STERUJACE.search(v)
        if zly:
            bledy.append((miejsce, f"niedozwolony znak sterujący U+{ord(zly.group(0)):04X} w tekście "
                                   "(np. skopiowany z Worda albo PDF) — usuń go"))
        if len(v) < s.get("minLength", 0):
            bledy.append((miejsce, f"za krótkie — {len(v)} zn., minimum {s['minLength']}"))
        if "maxLength" in s and len(v) > s["maxLength"]:
            bledy.append((miejsce, f"za długie — {len(v)} zn., limit {s['maxLength']}"))
        wzor = s.get("pattern")
        if wzor and not re.fullmatch(wzor, v):
            bledy.append((miejsce, f"{v!r} ma zły format" + (f" ({s['opis_formatu']})" if s.get("opis_formatu") else
                                                              f" (wzorzec {wzor})")))
        fmt = s.get("format")
        if fmt in FORMATY and not re.fullmatch(FORMATY[fmt], v):
            opis = {"email": "adres e-mail", "date": "data RRRR-MM-DD", "uri": "adres https://…",
                    "time": "godzina GG:MM"}[fmt]
            bledy.append((miejsce, f"{v!r} to nie jest {opis}"))
        elif fmt == "date":
            # wzorzec przepuszcza 2026-02-30 — kalendarz sprawdza dopiero date()
            try:
                _dt.date.fromisoformat(v)
            except ValueError:
                r, m, d = v.split("-")
                bledy.append((miejsce, f"nie ma takiego dnia: {d}.{m}.{r} (zapis RRRR-MM-DD)"))
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            bledy.append((miejsce, f"{v} jest mniejsze niż {s['minimum']}"))
        if "maximum" in s and v > s["maximum"]:
            bledy.append((miejsce, f"{v} jest większe niż {s['maximum']}"))
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            bledy.append((miejsce, f"lista ma {len(v)} pozycji, minimum {s['minItems']}"))
        if "maxItems" in s and len(v) > s["maxItems"]:
            bledy.append((miejsce, f"lista ma {len(v)} pozycji, maksimum {s['maxItems']}"))
        if s.get("uniqueItems"):
            widziane = []
            for x in v:
                if x in widziane:
                    bledy.append((miejsce, f"powtórzona pozycja {x!r}"))
                widziane.append(x)
        if "items" in s:
            for i, x in enumerate(v):
                bledy += waliduj(x, s["items"], root, _sciezka(sciezka, i))
    if isinstance(v, dict):
        props = s.get("properties", {})
        for k in s.get("required", []):
            if k not in v:
                bledy.append((miejsce, f"brak pola „{k}” (wpisz null, jeśli nie ma danych)"))
        dodatkowe = s.get("additionalProperties", True)
        for k, x in v.items():
            if k.startswith("$"):
                continue
            if k in props:
                bledy += waliduj(x, props[k], root, _sciezka(sciezka, k))
            elif dodatkowe is False:
                podobne = [p for p in props if _podobne(p, k)]
                wsk = f" — może chodziło o „{podobne[0]}”?" if podobne else ""
                bledy.append((miejsce, f"nieznane pole „{k}”{wsk}"))
            elif isinstance(dodatkowe, dict):
                bledy += waliduj(x, dodatkowe, root, _sciezka(sciezka, k))
    return bledy


def _podobne(a: str, b: str) -> bool:
    """Proste wykrywanie literówek: odległość edycyjna ≤ 2."""
    if abs(len(a) - len(b)) > 2:
        return False
    poprz = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        biez = [i]
        for j, cb in enumerate(b, 1):
            biez.append(min(poprz[j] + 1, biez[j - 1] + 1, poprz[j - 1] + (ca != cb)))
        poprz = biez
    return poprz[-1] <= 2
