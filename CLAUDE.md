@AGENTS.md

## Tylko Claude Code

- Personalizacja strony: skill `/personalizuj` (`.claude/skills/personalizuj/SKILL.md`, ta sama treść co
  `docs/PROCEDURA.md`). Każda faza kończy się poleceniem, które musi przejść. Po fazach 3 (marka) i 5 (treść)
  zaproponuj użytkownikowi nową sesję, jeśli ta jest długa — stan jest w plikach, nie w rozmowie.
- Hooki (`.claude/settings.json`):
  - po każdej edycji w `data/`, `src/`, `assets/`, `tools/presety|schemat|silnik/`, `przyklady/` hook uruchamia
    `python3 tools/build.py --szybko --json` i dopisuje błędy do kontekstu — popraw je od razu;
  - przed zakończeniem pracy hook uruchamia `python3 tools/build.py --sprawdz` (w repozytorium SZABLON: dla każdego
    przykładu) i nie pozwala skończyć, dopóki są błędy (po 3 próbach przepuszcza — wtedy powiedz o błędach wprost).
  Napraw przyczynę; nie obchodź, nie wyłączaj i nie edytuj hooków.
- Zdjęcia oglądaj narzędziem Read (otwiera JPG/PNG) — przed napisaniem `alt`, `podpis`, `punkt`.
- Zrzuty z `bash tools/sprawdz.sh` też oglądaj przez Read, zanim napiszesz, że strona jest gotowa.
- Notatki tylko dla siebie i tej firmy trzymaj w `CLAUDE.local.md` (poza gitem), nie w tym pliku.
