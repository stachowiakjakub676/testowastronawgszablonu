#!/usr/bin/env python3
"""Hook Stop: zanim Claude skończy, `python3 tools/build.py --sprawdz` musi przejść.

- Repozytorium klienta (data/firma.json ma nazwę firmy): build klienta.
- Repozytorium SZABLON (pusty szkielet w data/): build każdego przykładu z przyklady/.
Przy błędach hook zwraca {"decision": "block", "reason": "…"} — Claude dostaje listę błędów i pracuje dalej.

Zabezpieczenie przed pętlą: `stop_hook_active` (starsze wersje Claude Code) oraz licznik blokad w sesji —
po 3 blokadach z rzędu hook przepuszcza zakończenie z ostrzeżeniem (wtedy decyduje człowiek).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wspolne  # noqa: E402

MAKS_BLOKAD = 3


def licznik(dane: dict) -> Path:
    baza = Path(dane.get("scratchpad_dir") or tempfile.gettempdir())
    sesja = "".join(c for c in str(dane.get("session_id") or "sesja") if c.isalnum() or c in "-_")[:64]
    return baza / f"szablon-stop-{sesja}.txt"


def main() -> int:
    dane = wspolne.wejscie()
    if dane.get("stop_hook_active"):
        return 0
    korzen = wspolne.korzen_od(dane.get("cwd"))
    if not korzen:
        return 0
    klienci = [korzen] if not wspolne.szkielet(korzen) else wspolne.przyklady(korzen)
    if not klienci:
        return 0

    problemy = []
    for klient in klienci:
        wyjscie = wspolne.katalog_wyniku(dane, korzen, klient, "przed-koncem")
        kod, kom = wspolne.build(korzen, klient, "--sprawdz", wyjscie, 240)
        if kod != 0:
            problemy.append(f"python3 tools/build.py --sprawdz --klient {wspolne.wzgledna(klient, korzen)} (kod {kod}):\n"
                            + wspolne.opis_bledow(kom))

    plik = licznik(dane)
    if not problemy:
        plik.unlink(missing_ok=True)
        return 0
    try:
        n = int(plik.read_text()) + 1
    except (OSError, ValueError):
        n = 1
    if n > MAKS_BLOKAD:
        plik.unlink(missing_ok=True)
        print(f"Build nadal ma błędy po {MAKS_BLOKAD} próbach — kończę bez blokady. Powiedz o tym użytkownikowi "
              "wprost i wypisz błędy:\n" + "\n\n".join(problemy))
        return 0
    try:
        plik.write_text(str(n))
    except OSError:
        pass
    powod = ("Build nie przechodzi — popraw przyczynę (dane, szablon), nie obchodź kontroli i nie kończ, "
             f"dopóki build nie przejdzie (próba {n}/{MAKS_BLOKAD}):\n\n" + "\n\n".join(problemy))
    print(json.dumps({"decision": "block", "reason": powod}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"przed_koncem.py: {e}", file=sys.stderr)
        sys.exit(0)
