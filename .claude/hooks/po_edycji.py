#!/usr/bin/env python3
"""Hook PostToolUse (Edit|Write|MultiEdit): po zmianie w data/, src/, assets/, tools/presety/, tools/schemat/
albo przyklady/ uruchamia `python3 tools/build.py --szybko --json` i pokazuje Claude'owi błędy.

Zawsze kończy się kodem 0 (edycja już się wykonała, nic nie blokujemy). Problemy trafiają do Claude'a przez
JSON `hookSpecificOutput.additionalContext` — zwykły tekst na wyjściu przy kodzie 0 widać tylko w logu debug.
Gdy build przechodzi, hook nic nie wypisuje (nie zajmuje kontekstu).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wspolne  # noqa: E402

OBSERWOWANE = ("data/", "src/", "assets/", "tools/presety/", "tools/schemat/", "tools/silnik/", "przyklady/")


def main() -> int:
    dane = wspolne.wejscie()
    wej = dane.get("tool_input") or {}
    plik = wej.get("file_path") or wej.get("notebook_path")
    if not plik:
        return 0
    plik = Path(plik)
    if not plik.is_absolute():
        plik = Path(dane.get("cwd") or ".") / plik
    korzen = wspolne.korzen_od(plik.parent)
    if not korzen:
        return 0
    try:
        rel = plik.resolve().relative_to(korzen).as_posix()
    except ValueError:
        return 0
    if not rel.startswith(OBSERWOWANE):
        return 0

    # który katalog klienta zbudować
    czesci = rel.split("/")
    if czesci[0] == "przyklady" and len(czesci) > 2:
        klient = korzen / "przyklady" / czesci[1]
    elif not wspolne.szkielet(korzen) or rel.startswith("data/"):
        klient = korzen                       # repozytorium klienta (albo wypełnianie szkieletu — braki są wskazówką)
    else:
        # repozytorium SZABLON z pustym szkieletem: zmiana silnika — sprawdź na pierwszym przykładzie
        pr = wspolne.przyklady(korzen)
        if not pr:
            return 0
        klient = pr[0]

    wyjscie = wspolne.katalog_wyniku(dane, korzen, klient, "po-edycji")
    kod, kom = wspolne.build(korzen, klient, "--szybko", wyjscie, 60)
    if kod == 0:
        return 0
    kto = wspolne.wzgledna(klient, korzen)
    tekst = (f"Po edycji {rel}: python3 tools/build.py --szybko --klient {kto} zgłasza błędy "
             f"(kod {kod}). Popraw dane albo szablon, nie osłabiaj kontroli:\n" + wspolne.opis_bledow(kom))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": tekst}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                    # hook nigdy nie może przeszkodzić w pracy
        print(f"po_edycji.py: {e}", file=sys.stderr)
        sys.exit(0)
