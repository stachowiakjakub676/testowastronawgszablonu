#!/usr/bin/env python3
"""Aktualizacja strony klienta do nowszej wersji SZABLONU (pliki silnika), potem build --sprawdz.

Silnik (KONTRAKT §2, [silnik]) — to kopiujemy:
  AGENTS.md CLAUDE.md CHANGELOG.md SZABLON_WERSJA .htmlvalidate.json .claude/settings.json .claude/hooks/
  .claude/skills/ .gemini/ src/ tools/ assets/css/czesci/ assets/js/czesci/ assets/fonts/ worker/ docs/ przyklady/
Klient — tego nie dotykamy: data/ brief/ assets/img/ assets/css/wlasne.css README.md CLAUDE.local.md
Pliki mieszane: wrangler.jsonc (nazwa Workera i namespace_id są klienta) — nowa wersja trafia obok jako
wrangler.jsonc.szablon do ręcznego porównania; .gitignore — dopisujemy brakujące wiersze.

Źródło to repozytorium git SZABLONU:
  python3 tools/aktualizuj.py --szablon ../SZABLON --wersja v0.2.0
  git remote add szablon https://github.com/<konto>/SZABLON.git && git fetch szablon --tags
  python3 tools/aktualizuj.py --wersja v0.2.0          (bez --szablon: zdalne „szablon” w repozytorium klienta)
Opcje: --klient KATALOG (domyślnie bieżące repozytorium), --bazowa REF (wersja, z której klient startował;
domyślnie tag v<SZABLON_WERSJA klienta>), --proba (tylko pokaż, co się zmieni), --bez-buildu.

Bezpieczeństwo: jeśli klient zmienił plik silnika (inny niż w wersji bazowej), skrypt ODMAWIA i wypisuje listę.
Takie zmiany przenieś do assets/css/wlasne.css albo zgłoś do SZABLONU (wtedy trafią do wszystkich stron).
Tylko biblioteka standardowa Pythona + polecenie git.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SILNIK_PLIKI = ["AGENTS.md", "CLAUDE.md", "CHANGELOG.md", "SZABLON_WERSJA", ".htmlvalidate.json", ".claude/settings.json"]
SILNIK_KATALOGI = [".claude/hooks/", ".claude/skills/", ".gemini/", "src/", "tools/", "assets/css/czesci/",
                   "assets/js/czesci/", "assets/fonts/", "worker/", "docs/", "przyklady/"]
MIESZANE = ["wrangler.jsonc"]
POMIN = ("__pycache__/", ".pyc", ".DS_Store")


def silnikowy(sciezka: str) -> bool:
    if any(p in sciezka for p in POMIN):
        return False
    return sciezka in SILNIK_PLIKI or any(sciezka.startswith(k) for k in SILNIK_KATALOGI)


def git(repo: Path, *argumenty, binarnie=False):
    w = subprocess.run(["git", "-C", str(repo), *argumenty], capture_output=True, text=not binarnie)
    if w.returncode != 0:
        blad = w.stderr if not binarnie else w.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(argumenty)}: {blad.strip()}")
    return w.stdout


def istnieje_ref(repo: Path, ref: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                          capture_output=True).returncode == 0


def pliki_w_ref(repo: Path, ref: str) -> list[str]:
    return [p for p in git(repo, "ls-tree", "-r", "--name-only", ref).splitlines() if silnikowy(p)]


def tresc_w_ref(repo: Path, ref: str, sciezka: str) -> bytes:
    return git(repo, "show", f"{ref}:{sciezka}", binarnie=True)


def pliki_klienta(klient: Path) -> list[str]:
    wynik = []
    for p in klient.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            rel = p.relative_to(klient).as_posix()
            if silnikowy(rel) and not rel.startswith(".claude/worktrees/"):
                wynik.append(rel)
    return sorted(wynik)


def main() -> int:
    ap = argparse.ArgumentParser(description="Aktualizacja plików silnika z nowszej wersji SZABLONU.")
    ap.add_argument("--szablon", help="katalog z repozytorium git SZABLONU (domyślnie zdalne „szablon” klienta)")
    ap.add_argument("--wersja", help="docelowa wersja: tag (v0.2.0), gałąź albo commit")
    ap.add_argument("--bazowa", help="wersja, z której zbudowano stronę klienta (domyślnie v<SZABLON_WERSJA>)")
    ap.add_argument("--klient", default=".", help="katalog repozytorium klienta")
    ap.add_argument("--proba", action="store_true", help="nic nie zmieniaj, tylko wypisz")
    ap.add_argument("--bez-buildu", action="store_true")
    a = ap.parse_args()

    klient = Path(a.klient).resolve()
    if not (klient / "data" / "firma.json").is_file():
        print(f"BŁĄD: {klient} nie wygląda na repozytorium strony (brak data/firma.json).")
        return 1
    if a.szablon:
        zrodlo, prefiks = Path(a.szablon).resolve(), ""
        domyslna = "HEAD"
    else:
        zrodlo, prefiks = klient, "szablon/"
        if subprocess.run(["git", "-C", str(klient), "remote", "get-url", "szablon"], capture_output=True).returncode:
            print("BŁĄD: podaj --szablon <katalog SZABLONU> albo dodaj zdalne repozytorium:\n"
                  "  git remote add szablon https://github.com/<konto>/SZABLON.git && git fetch szablon --tags")
            return 1
        domyslna = "szablon/main"
    cel = a.wersja or domyslna
    if not istnieje_ref(zrodlo, cel):
        print(f"BŁĄD: w {zrodlo} nie ma wersji „{cel}” (git fetch szablon --tags? literówka w tagu?)")
        return 1

    wersja_klienta = (klient / "SZABLON_WERSJA").read_text(encoding="utf-8").strip() if (klient / "SZABLON_WERSJA").is_file() else None
    bazowa = a.bazowa
    if not bazowa and wersja_klienta:
        for kandydat in (f"v{wersja_klienta}", wersja_klienta, f"{prefiks}v{wersja_klienta}"):
            if istnieje_ref(zrodlo, kandydat):
                bazowa = kandydat
                break
    if not bazowa or not istnieje_ref(zrodlo, bazowa):
        print(f"BŁĄD: nie znam wersji bazowej (SZABLON_WERSJA klienta: {wersja_klienta or 'brak'}; w SZABLONIE nie ma "
              "takiego tagu). Podaj ją: --bazowa <tag albo commit, z którego powstała strona>. Bez niej nie da się "
              "odróżnić zmian klienta od zmian w nowej wersji.")
        return 1

    pliki_bazy = set(pliki_w_ref(zrodlo, bazowa))
    pliki_celu = set(pliki_w_ref(zrodlo, cel))
    obecne = set(pliki_klienta(klient))

    zmienione, dodane_kolizja, usuniete = [], [], []
    for p in sorted(obecne):
        if p in pliki_bazy:
            if (klient / p).read_bytes() != tresc_w_ref(zrodlo, bazowa, p):
                zmienione.append(p)
        elif p in pliki_celu and (klient / p).read_bytes() != tresc_w_ref(zrodlo, cel, p):
            dodane_kolizja.append(p)
    for p in sorted(pliki_bazy - obecne):
        if p in pliki_celu:
            usuniete.append(p)
    # pozwalamy na „zmianę” samego numeru wersji i listy zmian, gdy są identyczne z celem
    zmienione = [p for p in zmienione if not (p in pliki_celu and (klient / p).read_bytes() == tresc_w_ref(zrodlo, cel, p))]

    if zmienione or dodane_kolizja or usuniete:
        print(f"ODMOWA: klient zmienił pliki silnika (względem {bazowa}). Aktualizacja by je nadpisała:")
        for p in zmienione:
            print(f"  zmieniony   {p}")
        for p in dodane_kolizja:
            print(f"  dodany      {p}  (nowa wersja SZABLONU ma plik o tej nazwie)")
        for p in usuniete:
            print(f"  usunięty    {p}")
        print("\nCo zrobić: porównaj (git diff), przenieś zmiany do assets/css/wlasne.css albo danych, a zmianę, która "
              "ma sens dla wszystkich stron, zgłoś do SZABLONU. Potem przywróć plik i uruchom ponownie.")
        return 1

    do_zapisu = sorted(pliki_celu)
    do_usuniecia = sorted(p for p in (pliki_bazy - pliki_celu) if p in obecne)
    nowe = [p for p in do_zapisu if p not in obecne]
    zmiany = [p for p in do_zapisu if p in obecne and (klient / p).read_bytes() != tresc_w_ref(zrodlo, cel, p)]
    print(f"Aktualizacja silnika: {bazowa} → {cel}  (źródło: {zrodlo})")
    print(f"  nowe pliki: {len(nowe)}, zmienione: {len(zmiany)}, usunięte: {len(do_usuniecia)}")
    for p in nowe[:40]:
        print(f"    + {p}")
    for p in zmiany[:60]:
        print(f"    ~ {p}")
    for p in do_usuniecia:
        print(f"    - {p}")

    uwagi = []
    for p in MIESZANE:
        try:
            nowy = tresc_w_ref(zrodlo, cel, p)
        except RuntimeError:
            continue
        stary = (klient / p).read_bytes() if (klient / p).is_file() else None
        if stary is None:
            uwagi.append(f"{p}: nowy plik — zapisano, uzupełnij nazwę strony (docs/CLOUDFLARE.md)")
            if not a.proba:
                (klient / p).write_bytes(nowy)
        elif stary != nowy:
            baza = None
            try:
                baza = tresc_w_ref(zrodlo, bazowa, p)
            except RuntimeError:
                pass
            if baza != nowy:
                uwagi.append(f"{p}: SZABLON zmienił ten plik — nowa wersja obok jako {p}.szablon; przenieś zmiany ręcznie, "
                             "zostawiając nazwę Workera i namespace_id klienta")
                if not a.proba:
                    (klient / (p + ".szablon")).write_bytes(nowy)
    try:
        ignoruj = tresc_w_ref(zrodlo, cel, ".gitignore").decode("utf-8").splitlines()
        plik_ign = klient / ".gitignore"
        mamy = plik_ign.read_text(encoding="utf-8").splitlines() if plik_ign.is_file() else []
        brak = [w for w in ignoruj if w.strip() and w not in mamy]
        if brak:
            uwagi.append(f".gitignore: dopisano {len(brak)} wierszy z SZABLONU")
            if not a.proba:
                plik_ign.write_text("\n".join(mamy + ["", "# z SZABLONU"] + brak) + "\n", encoding="utf-8")
    except RuntimeError:
        pass
    for u in uwagi:
        print("  uwaga: " + u)

    if a.proba:
        print("\nTryb --proba: nic nie zmieniono.")
        return 0
    for p in do_zapisu:
        cel_plik = klient / p
        cel_plik.parent.mkdir(parents=True, exist_ok=True)
        cel_plik.write_bytes(tresc_w_ref(zrodlo, cel, p))
    for p in do_usuniecia:
        (klient / p).unlink(missing_ok=True)
    for p in ("tools/sprawdz.sh", "tools/build.py"):
        if (klient / p).is_file():
            (klient / p).chmod(0o755)

    if a.bez_buildu:
        print("\nGotowe (bez buildu). Sprawdź: python3 tools/build.py --sprawdz")
        return 0
    print("\nBuild po aktualizacji: python3 tools/build.py --sprawdz")
    w = subprocess.run([sys.executable, str(klient / "tools" / "build.py"), "--sprawdz"], cwd=klient)
    if w.returncode != 0:
        print("\nBuild nie przechodzi po aktualizacji. Najczęściej nowa wersja wymaga nowego pola w danych — "
              "komunikaty wyżej mówią, które; opis zmian: CHANGELOG.md. Cofnięcie: git checkout -- . && git clean -fd")
        return 1
    wersja = (klient / "SZABLON_WERSJA").read_text(encoding="utf-8").strip() if (klient / "SZABLON_WERSJA").is_file() else cel
    print(f"\nGotowe. Przejrzyj zmiany (git diff --stat) i zatwierdź:\n  git commit -am \"Aktualizacja SZABLONU do {wersja}\"")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"BŁĄD: {e}")
        sys.exit(1)
