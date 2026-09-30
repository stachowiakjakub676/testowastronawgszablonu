#!/usr/bin/env python3
"""Skill /personalizuj = nagłówek skilla + docs/PROCEDURA.md (jedno źródło, bez ręcznego kopiowania).

  python3 tools/skill.py              zapisuje .claude/skills/personalizuj/SKILL.md z docs/PROCEDURA.md
  python3 tools/skill.py --sprawdz    kod 1, gdy SKILL.md różni się od PROCEDURA (test i CI)

Zmieniasz procedurę tylko w docs/PROCEDURA.md, potem uruchamiasz ten skrypt.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
PROCEDURA = KORZEN / "docs" / "PROCEDURA.md"
SKILL = KORZEN / ".claude" / "skills" / "personalizuj" / "SKILL.md"


def naglowek() -> str:
    """Nagłówek YAML z obecnego SKILL.md (name, description) — opis skilla zmienia się tam."""
    tekst = SKILL.read_text(encoding="utf-8")
    if not tekst.startswith("---\n"):
        raise SystemExit(f"{SKILL}: brak nagłówka --- name/description ---")
    koniec = tekst.index("\n---\n", 4) + len("\n---\n")
    return tekst[:koniec]


def oczekiwany() -> str:
    return naglowek() + "\n" + PROCEDURA.read_text(encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="SKILL.md skilla /personalizuj z docs/PROCEDURA.md.")
    p.add_argument("--sprawdz", action="store_true", help="tylko sprawdź zgodność")
    a = p.parse_args()
    if a.sprawdz:
        if SKILL.read_text(encoding="utf-8") != oczekiwany():
            print("SKILL.md różni się od docs/PROCEDURA.md — uruchom: python3 tools/skill.py")
            return 1
        print("SKILL.md = docs/PROCEDURA.md: OK")
        return 0
    SKILL.write_text(oczekiwany(), encoding="utf-8")
    print(f"Zapisano {SKILL.relative_to(KORZEN)} z docs/PROCEDURA.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
