"""Wspólne funkcje hooków Claude Code (po_edycji.py, przed_koncem.py). Tylko biblioteka standardowa.

Hooki nie ufają CLAUDE_PROJECT_DIR (w roboczej kopii git worktree wskazuje główne repozytorium) — korzeń
repozytorium to katalog z tools/build.py nad edytowanym plikiem albo nad bieżącym katalogiem sesji.
Build piszą do katalogu tymczasowego, nigdy do dist/, który może właśnie obsługiwać podgląd.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TUTAJ = Path(__file__).resolve()


def wejscie() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}


def korzen_od(start: str | os.PathLike | None) -> Path | None:
    """Najbliższy katalog w górę od `start`, w którym jest tools/build.py."""
    kandydaci = []
    if start:
        p = Path(start).resolve()
        kandydaci += [p, *p.parents]
    kandydaci += list(TUTAJ.parents)
    for k in kandydaci:
        if (k / "tools" / "build.py").is_file() and (k / "src").is_dir():
            return k
    return None


def szkielet(klient: Path) -> bool:
    """Dane z tools/start.py bez uzupełnionej nazwy firmy (albo brak danych) — build i tak wypisze tylko braki."""
    try:
        d = json.loads((klient / "data" / "firma.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return not (d.get("firma") or {}).get("nazwa")


def przyklady(korzen: Path) -> list[Path]:
    return sorted(p for p in (korzen / "przyklady").glob("*") if (p / "data" / "firma.json").is_file())


def katalog_wyniku(dane: dict, korzen: Path, klient: Path, nazwa: str) -> Path:
    baza = Path(dane.get("scratchpad_dir") or tempfile.gettempdir())
    skrot = hashlib.sha1(str(klient.resolve()).encode()).hexdigest()[:10]
    return baza / f"szablon-{nazwa}-{skrot}"


def build(korzen: Path, klient: Path, tryb: str, wyjscie: Path, limit_s: int) -> tuple[int, list[dict]]:
    """Uruchamia build.py z --json. Zwraca (kod wyjścia, komunikaty)."""
    polecenie = [sys.executable, str(korzen / "tools" / "build.py"), tryb, "--json",
                 "--klient", str(klient), "--wyjscie", str(wyjscie)]
    try:
        w = subprocess.run(polecenie, cwd=korzen, capture_output=True, text=True, timeout=limit_s)
    except subprocess.TimeoutExpired:
        return 2, [{"poziom": "BŁĄD", "tresc": f"build nie skończył się w {limit_s} s"}]
    try:
        kom = json.loads(w.stdout).get("komunikaty", [])
    except ValueError:
        kom = [{"poziom": "BŁĄD", "tresc": "build zakończył się bez wyniku JSON:\n" + (w.stdout + w.stderr).strip()[-1500:]}]
    return w.returncode, kom


def opis_bledow(kom: list[dict], ile: int = 15) -> str:
    bledy = [k for k in kom if k.get("poziom") == "BŁĄD"]
    wiersze = []
    for k in bledy[:ile]:
        miejsce = (k.get("plik") or "") + (f" [{k['pole']}]" if k.get("pole") else "")
        wiersze.append(f"- {miejsce + ': ' if miejsce else ''}{k['tresc']}")
        if k.get("naprawa"):
            wiersze.append(f"  → {k['naprawa']}")
    if len(bledy) > ile:
        wiersze.append(f"- … i {len(bledy) - ile} kolejnych (python3 tools/build.py --json)")
    return "\n".join(wiersze)


def wzgledna(klient: Path, korzen: Path) -> str:
    try:
        return str(klient.resolve().relative_to(korzen.resolve())) or "."
    except ValueError:
        return str(klient)
