#!/usr/bin/env bash
# Pełna kontrola strony przed oddaniem (KONTRAKT §2, docs/PROCEDURA.md faza 8).
#
#   bash tools/sprawdz.sh                               klient = korzeń repozytorium, build --produkcja
#   bash tools/sprawdz.sh --klient przyklady/bimex      przykład: build --sprawdz (przykład nie przejdzie --produkcja)
#   bash tools/sprawdz.sh --url https://firma.pl        dodatkowo: czy Cloudflare nie wstrzykuje skryptów na produkcji
#
# Opcje: --klient KATALOG  --wyjscie KATALOG (domyślnie dist)  --raport KATALOG (domyślnie raport)
#        --port N (domyślnie 8765)  --url ADRES  --linki (sprawdź linki zewnętrzne, linkinator)
#        --bez-lighthouse  --szybko (bez Lighthouse i bez zrzutów bez JS / wymuszonych kolorów)
#
# Kroki (każdy wypisuje OK / BŁĄD / POMINIĘTO):
#   1 build          python3 tools/build.py --produkcja|--sprawdz --json → raport/build.json
#   2 podgląd        python3 tools/podglad.py (adresy bez .html, 404, nagłówki z _headers)
#   3 zrzuty         tools/zrzuty.cjs 375/768/1440 na każdej stronie + bez JS + wymuszone kolory → raport/zrzuty/
#   4 html-validate  wszystkie strony
#   5 pa11y (axe)    każda strona, WCAG 2 AA → raport/pa11y/
#   6 Lighthouse     telefon + komputer na stronach kluczowych → raport/lighthouse/
#   7 linkinator     (opcja --linki) linki zewnętrzne
#   8 produkcja      (opcja --url) skrypty wstrzyknięte przez Cloudflare, nagłówki bezpieczeństwa
#   9 karta jakości  python3 tools/raport.py → raport/KARTA-JAKOSCI.md i .html
#
# Brakujące narzędzia (Node, Playwright, pa11y…) nie przerywają — krok ma status POMINIĘTO z poleceniem instalacji.
# Lista narzędzi jest wypisana na początku. Instalacja bez uprawnień do systemowego Node (do katalogu użytkownika):
#   npm i -g --prefix ~/.szablon-node playwright html-validate pa11y lighthouse linkinator
#   SZABLON_NODE_PREFIX=~/.szablon-node bash tools/sprawdz.sh
# (SZABLON_NODE_PREFIX dodaje <prefiks>/bin do PATH i <prefiks>/lib/node_modules do NODE_PATH; działa też
#  z układem npm i --prefix: <prefiks>/node_modules/.bin i <prefiks>/node_modules). Chromium: zmienna CHROMIUM.
# Każdy krok z przeglądarką ma limit czasu (SZABLON_LIMIT_KROKU_S, domyślnie 900 s), a Ctrl+C / kill zamyka podgląd
# i przeglądarki. Port zajęty przez podgląd z przerwanego uruchomienia skrypt zwalnia sam.
# Kod wyjścia: 0 = wszystkie wykonane kroki OK, 1 = któryś krok ma BŁĄD.
set -uo pipefail

KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KORZEN" || exit 2

KLIENT="."
WYJSCIE="dist"
RAPORT="raport"
PORT=8765
URL_PROD=""
LINKI=0
LIGHTHOUSE=1
SZYBKO=0
while [ $# -gt 0 ]; do
  case "$1" in
    --klient) KLIENT="$2"; shift 2 ;;
    --wyjscie) WYJSCIE="$2"; shift 2 ;;
    --raport) RAPORT="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --url) URL_PROD="${2%/}"; shift 2 ;;
    --linki) LINKI=1; shift ;;
    --bez-lighthouse) LIGHTHOUSE=0; shift ;;
    --szybko) SZYBKO=1; LIGHTHOUSE=0; shift ;;
    -h|--help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Nieznana opcja: $1 (pomoc: bash tools/sprawdz.sh --help)"; exit 2 ;;
  esac
done

mkdir -p "$RAPORT/zrzuty" "$RAPORT/pa11y" "$RAPORT/lighthouse"

# sprzątanie przy każdym wyjściu (także Ctrl+C i kill): podgląd i dzieci tego skryptu (node, Chromium)
PID_PODGLADU=""
sprzataj() {
  [ -n "$PID_PODGLADU" ] && kill "$PID_PODGLADU" 2>/dev/null
  pkill -P $$ 2>/dev/null
  return 0
}
trap sprzataj EXIT
trap 'echo; echo "Przerwano — zamykam podgląd i przeglądarki."; exit 130' INT TERM
LIMIT_KROKU="${SZABLON_LIMIT_KROKU_S:-900}"
z_limitem() {  # z_limitem <polecenie…> — polecenie z limitem czasu (timeout z coreutils; bez niego bez limitu)
  if command -v timeout >/dev/null 2>&1; then timeout --kill-after=10 "$LIMIT_KROKU" "$@"; else "$@"; fi
}
KROKI="$RAPORT/kroki.tsv"
: > "$KROKI"
BLEDY=0

krok() {  # krok <nazwa> <OK|BŁĄD|POMINIĘTO> <opis>
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$KROKI"
  case "$2" in
    OK) printf '  OK         %-14s %s\n' "$1" "$3" ;;
    BŁĄD) printf '  BŁĄD       %-14s %s\n' "$1" "$3"; BLEDY=$((BLEDY + 1)) ;;
    *) printf '  POMINIĘTO  %-14s %s\n' "$1" "$3" ;;
  esac
}

echo "SZABLON sprawdz.sh — klient: $KLIENT, wynik: $WYJSCIE, raport: $RAPORT"
echo

# ---------------------------------------------------------------- narzędzia
if [ -d /opt/node22/bin ] && ! command -v node >/dev/null 2>&1; then export PATH="/opt/node22/bin:$PATH"; fi
if [ -n "${SZABLON_NODE_PREFIX:-}" ]; then
  P="${SZABLON_NODE_PREFIX%/}"
  export PATH="$P/bin:$P/node_modules/.bin:$PATH"
  export NODE_PATH="$P/lib/node_modules:$P/node_modules${NODE_PATH:+:$NODE_PATH}"
fi
MA_NODE=0; command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1 && MA_NODE=1
PODPOWIEDZ_NODE="zainstaluj Node.js ≥ 20 (https://nodejs.org), potem: npm i -g --prefix ~/.szablon-node playwright html-validate pa11y lighthouse linkinator && npx playwright install chromium; uruchom z SZABLON_NODE_PREFIX=~/.szablon-node"

MA_PLAYWRIGHT=0
if [ $MA_NODE -eq 1 ]; then
  if ! node -e "require('playwright')" >/dev/null 2>&1; then
    GLOBALNE="$(npm root -g 2>/dev/null)"
    [ -n "$GLOBALNE" ] && export NODE_PATH="${NODE_PATH:+$NODE_PATH:}$GLOBALNE"
  fi
  node -e "require('playwright')" >/dev/null 2>&1 && MA_PLAYWRIGHT=1
fi
if [ $MA_PLAYWRIGHT -eq 1 ]; then
  [ -z "${PLAYWRIGHT_BROWSERS_PATH:-}" ] && [ -d /opt/pw-browsers ] && export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
  if [ -z "${CHROMIUM:-}" ]; then
    CHROMIUM="${CHROME_PATH:-}"
    [ -z "$CHROMIUM" ] && CHROMIUM="$(node -e "console.log(require('playwright').chromium.executablePath())" 2>/dev/null)"
    [ -n "$CHROMIUM" ] && [ ! -x "$CHROMIUM" ] && CHROMIUM="$(ls /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | tail -n 1)"
  fi
  export CHROMIUM
  export CHROME_PATH="${CHROME_PATH:-$CHROMIUM}"
fi

ma_npx() {  # ma_npx <pakiet> — czy narzędzie jest zainstalowane (w PATH albo lokalnie; bez pobierania z sieci)
  [ $MA_NODE -eq 1 ] && { command -v "$1" >/dev/null 2>&1 || npx --no-install "$1" --version >/dev/null 2>&1; }
}
uruchom() {  # uruchom <narzędzie> <argumenty…> — z PATH (albo npx --no-install), z limitem czasu kroku
  local n="$1"; shift
  if command -v "$n" >/dev/null 2>&1; then z_limitem "$(command -v "$n")" "$@"; else z_limitem npx --no-install "$n" "$@"; fi
}

# jedna linia na początku: czego brakuje, zanim cokolwiek zacznie się liczyć
BRAKI=()
[ $MA_NODE -eq 1 ] || BRAKI+=("node")
[ $MA_PLAYWRIGHT -eq 1 ] || BRAKI+=("playwright")
for n in html-validate pa11y lighthouse; do ma_npx "$n" || BRAKI+=("$n"); done
[ $MA_PLAYWRIGHT -eq 1 ] && [ -z "${CHROMIUM:-}" ] && BRAKI+=("chromium")
if [ ${#BRAKI[@]} -eq 0 ]; then
  echo "  narzędzia: node, playwright, html-validate, pa11y, lighthouse, Chromium — są"
else
  echo "  narzędzia: brakuje ${BRAKI[*]} — te kroki będą POMINIĘTO"
  echo "    instalacja: $PODPOWIEDZ_NODE"
fi

# ---------------------------------------------------------------- 1. build
TRYB="--produkcja"
if [[ "$KLIENT" == *przyklady/* ]] || python3 - "$KLIENT" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "data" / "firma.json"
try:
    sys.exit(0 if json.loads(p.read_text(encoding="utf-8")).get("przyklad") else 1)
except Exception:
    sys.exit(1)
PY
then
  TRYB="--sprawdz"   # przykład ma przyklad: true — --produkcja celowo go odrzuca
fi
python3 tools/build.py "$TRYB" --klient "$KLIENT" --wyjscie "$WYJSCIE" --json > "$RAPORT/build.json" 2> "$RAPORT/build.err"
KOD_BUILD=$?
python3 - "$RAPORT/build.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(0)
wazne = [k for k in d.get("komunikaty", []) if k["poziom"] in ("BŁĄD", "OSTRZEŻENIE")]
for k in wazne[:25]:
    miejsce = (k.get("plik") or "") + (f" [{k['pole']}]" if k.get("pole") else "")
    print(f"    {k['poziom']}: {miejsce} {k['tresc']}".rstrip())
    if k.get("naprawa"):
        print(f"      → {k['naprawa']}")
if len(wazne) > 25:
    print(f"    … i {len(wazne) - 25} kolejnych komunikatów (pełna lista: {sys.argv[1]})")
PY
if [ $KOD_BUILD -ne 0 ]; then
  krok build BŁĄD "python3 tools/build.py $TRYB --klient $KLIENT — kod $KOD_BUILD (lista wyżej, pełna: $RAPORT/build.json)"
  [ -s "$RAPORT/build.err" ] && tail -n 20 "$RAPORT/build.err"
  echo
  echo "Bez udanego buildu dalsze kroki nie mają sensu. Popraw błędy i uruchom ponownie."
  python3 tools/raport.py --raport "$RAPORT" --klient "$KLIENT" --wyjscie "$WYJSCIE" >/dev/null 2>&1
  exit 1
fi
krok build OK "python3 tools/build.py $TRYB (wynik: $WYJSCIE/)"

STRONY=$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
print(' '.join(s for s in d['wynik']['strony'] if s not in ('/404',)))" "$RAPORT/build.json")
STRONY_KLUCZOWE=$(python3 -c "
import sys
s=sys.argv[1].split()
wazne=['/']+[x for x in ('/oferta','/menu','/produkty','/realizacje') if x in s][:1]+['/kontakt']
print(' '.join(dict.fromkeys(x for x in wazne if x in s)))" "$STRONY")

# ---------------------------------------------------------------- 2. podgląd
# SO_REUSEADDR jak w podglad.py (HTTPServer) — port po poprzednim uruchomieniu (TIME_WAIT) nie jest „zajęty”
port_wolny() { python3 -c "import socket,sys; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('127.0.0.1', int(sys.argv[1]))); s.close()" "$PORT" 2>/dev/null; }
if ! port_wolny && command -v pkill >/dev/null 2>&1 && pkill -f "tools/podglad.py .*--port $PORT" 2>/dev/null; then
  echo "  port $PORT zajmował podgląd z przerwanego uruchomienia — zamknięty"
  sleep 1
fi
if ! port_wolny; then
  krok podglad BŁĄD "port $PORT jest zajęty — użyj innego: bash tools/sprawdz.sh --port 8791 (kto go zajmuje: lsof -i :$PORT)"
  exit 1
fi
PODGLAD_CICHO=1 python3 tools/podglad.py --katalog "$WYJSCIE" --port "$PORT" > "$RAPORT/podglad.log" 2>&1 &
PID_PODGLADU=$!
BAZA="http://localhost:$PORT"
for _ in $(seq 1 50); do
  python3 -c "import urllib.request,sys; urllib.request.urlopen(sys.argv[1], timeout=1)" "$BAZA/" 2>/dev/null && break
  sleep 0.1
done
if ! kill -0 $PID_PODGLADU 2>/dev/null || ! python3 -c "import urllib.request,sys; urllib.request.urlopen(sys.argv[1], timeout=2)" "$BAZA/" 2>/dev/null; then
  krok podglad BŁĄD "tools/podglad.py nie odpowiada na porcie $PORT (zajęty? użyj --port) — $RAPORT/podglad.log"
  exit 1
fi
krok podglad OK "$BAZA/"

# ---------------------------------------------------------------- 3. zrzuty
if [ $MA_PLAYWRIGHT -eq 1 ]; then
  rm -f "$RAPORT"/zrzuty/*.png
  # shellcheck disable=SC2086
  ZRZUTY_JSON="$RAPORT/zrzuty.json" z_limitem node tools/zrzuty.cjs "$BAZA" "$RAPORT/zrzuty" strona $STRONY /nie-ma-takiej > "$RAPORT/zrzuty.txt" 2>&1
  KOD=$?
  grep -v '^OK' "$RAPORT/zrzuty.txt" | head -n 20
  N=$(grep -c . "$RAPORT/zrzuty.txt")
  if [ $SZYBKO -eq 0 ]; then
    # shellcheck disable=SC2086
    ZRZUTY_TRYBY=bezjs,wymuszone,tylko ZRZUTY_JSON="$RAPORT/zrzuty-tryby.json" z_limitem node tools/zrzuty.cjs "$BAZA" "$RAPORT/zrzuty" strona $STRONY_KLUCZOWE > "$RAPORT/zrzuty-tryby.txt" 2>&1
    KOD2=$?
    grep -v '^OK' "$RAPORT/zrzuty-tryby.txt" | head -n 20
    [ $KOD -eq 0 ] && KOD=$KOD2
    N=$((N + $(grep -c . "$RAPORT/zrzuty-tryby.txt")))
  fi
  if [ $KOD -eq 0 ]; then
    krok zrzuty OK "$N widoków: 0 px przewijania w poziomie, pusta konsola, 0 obcych domen, 0 ciasteczek → $RAPORT/zrzuty/"
  else
    krok zrzuty BŁĄD "problemy w $RAPORT/zrzuty.txt (przewijanie, konsola, obce domeny albo ciasteczka)"
  fi
elif [ $MA_NODE -eq 0 ]; then
  krok zrzuty POMINIĘTO "brak Node.js — $PODPOWIEDZ_NODE"
else
  krok zrzuty POMINIĘTO "brak pakietu playwright — npm i -g playwright && npx playwright install chromium"
fi

# ---------------------------------------------------------------- 4. html-validate
if ma_npx html-validate; then
  # bez mapfile — działa też w bash 3.2 (macOS); glob rozwija samo html-validate
  N_HTML=$(find "$WYJSCIE" -name '*.html' | wc -l | tr -d ' ')
  if uruchom html-validate --config .htmlvalidate.json "$WYJSCIE/**/*.html" > "$RAPORT/html-validate.txt" 2>&1; then
    krok html-validate OK "$N_HTML plików bez błędów"
  else
    head -n 30 "$RAPORT/html-validate.txt"
    krok html-validate BŁĄD "szczegóły: $RAPORT/html-validate.txt"
  fi
else
  krok html-validate POMINIĘTO "brak narzędzia — npm i -g html-validate"
fi

# ---------------------------------------------------------------- 5. pa11y (axe)
if ma_npx pa11y && [ -n "${CHROMIUM:-}" ]; then
  python3 - "$RAPORT/pa11y.json" "$CHROMIUM" <<'PY'
import json, sys
json.dump({"chromeLaunchConfig": {"executablePath": sys.argv[2], "args": ["--no-sandbox"]},
           "standard": "WCAG2AA", "runners": ["axe"], "timeout": 60000}, open(sys.argv[1], "w"))
PY
  rm -f "$RAPORT"/pa11y/*.json
  BLEDY_PA11Y=0
  for s in $STRONY /nie-ma-takiej; do
    nazwa=$( [ "$s" = "/" ] && echo glowna || echo "${s#/}" | tr '/' '_')
    uruchom pa11y --config "$RAPORT/pa11y.json" --reporter json "$BAZA$s" > "$RAPORT/pa11y/$nazwa.json" 2>/dev/null
    n=$(python3 -c "
import json,sys
try: print(len(json.load(open(sys.argv[1]))))
except Exception: print(-1)" "$RAPORT/pa11y/$nazwa.json")
    if [ "$n" != "0" ]; then
      BLEDY_PA11Y=$((BLEDY_PA11Y + 1))
      echo "    $s: $( [ "$n" = "-1" ] && echo 'pa11y nie zadziałał' || echo "$n problemów") → $RAPORT/pa11y/$nazwa.json"
    fi
  done
  if [ $BLEDY_PA11Y -eq 0 ]; then krok pa11y OK "axe WCAG 2 AA: 0 problemów na $(echo $STRONY /x | wc -w) stronach"
  else krok pa11y BŁĄD "$BLEDY_PA11Y stron z problemami (szczegóły: $RAPORT/pa11y/)"; fi
elif ! ma_npx pa11y; then
  krok pa11y POMINIĘTO "brak narzędzia — npm i -g pa11y"
else
  krok pa11y POMINIĘTO "brak Chromium — npx playwright install chromium albo ustaw CHROMIUM=/ścieżka/do/chrome"
fi

# ---------------------------------------------------------------- 6. Lighthouse
if [ $LIGHTHOUSE -eq 0 ]; then
  krok lighthouse POMINIĘTO "wyłączony opcją (--bez-lighthouse / --szybko)"
elif ma_npx lighthouse && [ -n "${CHROMIUM:-}" ]; then
  rm -f "$RAPORT"/lighthouse/*.json
  for s in $STRONY_KLUCZOWE; do
    nazwa=$( [ "$s" = "/" ] && echo glowna || echo "${s#/}" | tr '/' '_')
    for urzadzenie in telefon komputer; do
      dodatkowe=(); [ "$urzadzenie" = "komputer" ] && dodatkowe=(--preset=desktop)
      plik_lh="$RAPORT/lighthouse/$nazwa-$urzadzenie.json"
      # druga próba, gdy pomiar się nie udał (np. obciążony komputer: brak wyniku wydajności)
      for proba in 1 2; do
        uruchom lighthouse "$BAZA$s" --quiet "${dodatkowe[@]}" \
          --chrome-flags="--headless=new --no-sandbox" \
          --only-categories=performance,accessibility,best-practices,seo \
          --output=json --output-path="$plik_lh" >/dev/null 2>&1
        python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
sys.exit(0 if not d.get('runtimeError') and all(c['score'] is not None for c in d['categories'].values()) else 1)" "$plik_lh" 2>/dev/null && break
        [ $proba -eq 2 ] && echo "    Lighthouse nie zadziałał dla $s ($urzadzenie) — $plik_lh"
      done
    done
  done
  WYNIK_LH=$(python3 - "$RAPORT/lighthouse" <<'PY'
import json, sys
from pathlib import Path
zle, wiersze = 0, []
for p in sorted(Path(sys.argv[1]).glob("*.json")):
    try:
        k = json.loads(p.read_text(encoding="utf-8"))["categories"]
    except Exception:
        zle += 1; continue
    w = {c: round((k[c]["score"] or 0) * 100) for c in ("performance", "accessibility", "best-practices", "seo")}
    # cel: dostępność, dobre praktyki i SEO = 100; wydajność ≥ 90 (lokalnie bez kompresji Cloudflare)
    if min(w["accessibility"], w["best-practices"], w["seo"]) < 100 or w["performance"] < 90:
        zle += 1
    wiersze.append(f"    {p.stem:28} wydajność {w['performance']:3}  dostępność {w['accessibility']:3}  "
                   f"dobre praktyki {w['best-practices']:3}  SEO {w['seo']:3}")
print("\n".join(wiersze))
print(zle)
PY
)
  echo "$WYNIK_LH" | sed '$d'
  if [ "$(echo "$WYNIK_LH" | tail -n 1)" = "0" ] && [ -n "$(ls "$RAPORT"/lighthouse/*.json 2>/dev/null)" ]; then
    krok lighthouse OK "telefon + komputer: $STRONY_KLUCZOWE (dostępność, dobre praktyki, SEO = 100; wydajność ≥ 90)"
  else
    krok lighthouse BŁĄD "wynik poniżej celu albo brak raportu — $RAPORT/lighthouse/*.json"
  fi
elif ! ma_npx lighthouse; then
  krok lighthouse POMINIĘTO "brak narzędzia — npm i -g lighthouse"
else
  krok lighthouse POMINIĘTO "brak Chromium — npx playwright install chromium albo ustaw CHROME_PATH"
fi

# ---------------------------------------------------------------- 7. linkinator (opcja)
if [ $LINKI -eq 0 ]; then
  krok linki POMINIĘTO "linki zewnętrzne sprawdza opcja --linki (wewnętrzne sprawdza już build)"
elif ma_npx linkinator; then
  if uruchom linkinator "$BAZA/" --recurse --timeout 15000 > "$RAPORT/linki.txt" 2>&1; then
    krok linki OK "linkinator: brak zepsutych linków"
  else
    grep -E '\[[0-9]{3}\]|BROKEN|✖' "$RAPORT/linki.txt" | head -n 20
    krok linki BŁĄD "zepsute linki — $RAPORT/linki.txt"
  fi
else
  krok linki POMINIĘTO "brak narzędzia — npm i -g linkinator"
fi

# ---------------------------------------------------------------- 8. produkcja: wstrzyknięcia Cloudflare
if [ -z "$URL_PROD" ]; then
  krok produkcja POMINIĘTO "podaj --url https://domena, żeby sprawdzić stronę na serwerze"
else
  python3 - "$URL_PROD" "$RAPORT/produkcja.json" <<'PY'
import json, sys, urllib.request
baza, plik = sys.argv[1], sys.argv[2]
# ślady funkcji strefy Cloudflare, które psują CSP z sha256 albo zmieniają przetestowany HTML (docs/CLOUDFLARE.md)
WZORCE = {
    "/cdn-cgi/challenge-platform": "Bot Fight Mode (JavaScript Detections) — wyłącz: Security → Bots",
    "email-decode": "Email Address Obfuscation — wyłącz: Scrape Shield",
    "[email protected]": "Email Address Obfuscation — wyłącz: Scrape Shield",
    "[email protected]": "Email Address Obfuscation — wyłącz: Scrape Shield",
    "rocket-loader": "Rocket Loader — wyłącz: Speed → Optimization",
    "static.cloudflareinsights.com/beacon": "Web Analytics w trybie automatycznym — użyj funkcje.statystyki_cf_token",
    "/cdn-cgi/zaraz": "Zaraz — wyłącz",
}
NAGLOWKI = ["content-security-policy", "strict-transport-security", "x-content-type-options", "referrer-policy",
            "permissions-policy"]
wynik = {"url": baza, "problemy": [], "strony": {}}
for s in ("/", "/kontakt"):
    try:
        req = urllib.request.Request(baza + s, headers={"User-Agent": "Mozilla/5.0 (sprawdz.sh SZABLON)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            tresc = r.read().decode("utf-8", "replace")
            nag = {k.lower(): v for k, v in r.headers.items()}
    except Exception as e:
        wynik["problemy"].append(f"{s}: nie udało się pobrać ({e})")
        continue
    wynik["strony"][s] = {"naglowki": {k: nag.get(k) for k in NAGLOWKI}}
    for w, co in WZORCE.items():
        if w in tresc:
            wynik["problemy"].append(f"{s}: w HTML jest „{w}” — {co}")
    for k in NAGLOWKI:
        if k not in nag:
            wynik["problemy"].append(f"{s}: brak nagłówka {k} (plik _headers nie działa?)")
    if "noindex" in (nag.get("x-robots-tag") or ""):
        wynik["problemy"].append(f"{s}: X-Robots-Tag noindex na adresie produkcyjnym")
json.dump(wynik, open(plik, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
for p in wynik["problemy"]:
    print("    " + p)
sys.exit(1 if wynik["problemy"] else 0)
PY
  if [ $? -eq 0 ]; then krok produkcja OK "$URL_PROD: bez wstrzykniętych skryptów, nagłówki bezpieczeństwa są"
  else krok produkcja BŁĄD "$URL_PROD — lista wyżej, $RAPORT/produkcja.json"; fi
fi

# ---------------------------------------------------------------- 9. karta jakości
if python3 tools/raport.py --raport "$RAPORT" --klient "$KLIENT" --wyjscie "$WYJSCIE" > "$RAPORT/raport.txt" 2>&1; then
  krok karta OK "$RAPORT/KARTA-JAKOSCI.md i $RAPORT/KARTA-JAKOSCI.html"
else
  cat "$RAPORT/raport.txt"
  krok karta BŁĄD "tools/raport.py nie zadziałał"
fi

echo
if [ $BLEDY -eq 0 ]; then
  echo "Wynik: OK. Teraz obejrzyj zrzuty $RAPORT/zrzuty/*-375.png i *-1440.png (lista kontrolna: docs/PROCEDURA.md, faza 8)."
  exit 0
fi
echo "Wynik: $BLEDY kroków z błędem — popraw i uruchom ponownie."
exit 1
