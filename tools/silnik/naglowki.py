"""Pliki techniczne w dist/: _headers (CSP, HSTS, noindex), robots.txt, sitemap.xml, .well-known/security.txt,
site.webmanifest (KONTRAKT §9, critic §5.6).

CSP jest ścisła: skrypty tylko z własnego serwera plus skrót sha256 jedynego skryptu w <head>, style tylko z pliku,
zero zewnętrznych źródeł. Zewnętrzne adresy dochodzą wyłącznie przy włączonej funkcji (mapa po kliknięciu,
statystyki Cloudflare) — ta sama flaga opisuje je w polityce prywatności.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

BOTY_AI_TRENING = ["GPTBot", "Google-Extended", "CCBot", "ClaudeBot", "anthropic-ai", "Applebot-Extended",
                   "meta-externalagent", "Bytespider", "Amazonbot", "cohere-training-data-crawler"]


def sha256_csp(skrypt: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(skrypt.encode("utf-8")).digest()).decode() + "'"


def csp(funkcje: dict, inline_js: str) -> str:
    script = ["'self'", sha256_csp(inline_js)]
    connect = ["'self'"]
    frame = ["'none'"]
    img = ["'self'"]          # bez data: — strona nie ma obrazków w adresach data: (kontrole.py je odrzuca)
    if funkcje.get("mapa") == "po_kliknieciu":
        frame = ["https://www.openstreetmap.org"]
    if funkcje.get("statystyki_cf_token"):
        script.append("https://static.cloudflareinsights.com")
        connect.append("https://cloudflareinsights.com")
    dyrektywy = [
        "default-src 'self'", f"script-src {' '.join(script)}", "style-src 'self'", f"img-src {' '.join(img)}",
        "font-src 'self'", f"connect-src {' '.join(connect)}", f"frame-src {' '.join(frame)}",
        "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'", "object-src 'none'",
        "manifest-src 'self'", "upgrade-insecure-requests",
    ]
    return "; ".join(dyrektywy)


def _jeden_wiersz(wartosc: str, pole: str) -> str:
    """Druga zapora (pierwsza: schemat, re.fullmatch): nowa linia w wartości wpisanej do _headers/_redirects/robots.txt
    dopisałaby własny wiersz — np. „/*” + „X-Robots-Tag: noindex” dla całej domeny produkcyjnej."""
    if any(c in wartosc for c in "\r\n\u2028\u2029\x00"):
        raise ValueError(f"{pole}: wartość {wartosc!r} ma znak nowej linii — popraw data/firma.json")
    return wartosc


def headers(firma: dict, inline_js: str) -> str:
    fu = firma["funkcje"]
    hsts = "max-age=63072000"
    if fu.get("hsts_subdomeny") or fu.get("hsts_preload"):
        hsts += "; includeSubDomains"
    if fu.get("hsts_preload"):
        hsts += "; preload"
    linie = [
        "# Nagłówki HTTP (Cloudflare Workers — pliki statyczne). Plik generowany przez tools/build.py — nie edytuj.",
        "# CSP: skrypty tylko z własnego serwera + skrót sha256 jedynego skryptu w <head> (klasa „js”).",
        "/*",
        f"  Content-Security-Policy: {csp(fu, inline_js)}",
        f"  Strict-Transport-Security: {hsts}",
        "  X-Content-Type-Options: nosniff",
        "  X-Frame-Options: DENY",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        "  Cross-Origin-Opener-Policy: same-origin",
        "  Cross-Origin-Resource-Policy: same-origin",
        "",
        "# Zasoby z ?v=<skrót> w adresie — rok w pamięci przeglądarki; zmiana pliku = nowy adres.",
        "/assets/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
        "# Logo i zdjęcia można osadzać gdzie indziej (np. stopka e-maila).",
        "/assets/img/*",
        "  ! Cross-Origin-Resource-Policy",
        "  Cross-Origin-Resource-Policy: cross-origin",
        "",
        "/admin/*",
        "  X-Robots-Tag: noindex, nofollow",
        "  Cache-Control: no-store",
    ]
    # Adres *.workers.dev (także podgląd wersji) nigdy nie trafia do wyszukiwarki — działa bez wpisywania adres_roboczy.
    linie += ["", "# Adres roboczy Cloudflare (<nazwa>.<konto>.workers.dev) — tylko do sprawdzania przed podpięciem domeny.",
              "https://:nazwa.:konto.workers.dev/*", "  X-Robots-Tag: noindex, nofollow"]
    if firma.get("przyklad"):
        linie += ["", "# Dane przykładowe (podgląd szablonu) — cała strona poza wyszukiwarkami.",
                  "/*", "  X-Robots-Tag: noindex, nofollow"]
    roboczy = firma["firma"].get("adres_roboczy")
    if roboczy:
        linie += ["", "# Adres roboczy nie może trafić do wyszukiwarki (docelowo strona działa pod własną domeną).",
                  f"{_jeden_wiersz(roboczy, 'firma.adres_roboczy')}/*", "  X-Robots-Tag: noindex, nofollow"]
    return "\n".join(linie) + "\n"


def robots(firma: dict) -> str:
    linie = ["User-agent: *", "Allow: /", "Disallow: /api/", "Disallow: /admin/", ""]
    if firma["funkcje"].get("boty_ai") == "blokuj_trening":
        linie.append("# Boty zbierające dane do trenowania modeli AI (wyszukiwarki, także AI, mają dostęp).")
        for bot in BOTY_AI_TRENING:
            linie += [f"User-agent: {bot}", "Disallow: /", ""]
    linie.append(f"Sitemap: {firma['firma']['domena']}/sitemap.xml")
    return "\n".join(linie) + "\n"


def data_zmiany(pliki: list[Path], katalog: Path) -> str:
    """Data ostatniej zmiany plików: z historii git (prawdziwa), a bez gita — z daty modyfikacji."""
    istniejace = [p for p in pliki if p.exists()]
    try:
        wynik = subprocess.run(["git", "log", "-1", "--format=%cs", "--", *[str(p) for p in istniejace]],
                               cwd=katalog, capture_output=True, text=True, timeout=10)
        if wynik.returncode == 0 and wynik.stdout.strip():
            return wynik.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    if not istniejace:
        return dt.date.today().isoformat()
    return dt.date.fromtimestamp(max(p.stat().st_mtime for p in istniejace)).isoformat()


def sitemap(adresy: list[tuple[str, str]]) -> str:
    """adresy: (pełny URL, lastmod RRRR-MM-DD). Bez priority/changefreq (Google je pomija)."""
    wpisy = "".join(f"  <url><loc>{escape(u)}</loc><lastmod>{m}</lastmod></url>\n" for u, m in adresy)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + wpisy + "</urlset>\n")


def security_txt(firma: dict, dzis: dt.date) -> str | None:
    k = firma["kontakt"]
    kontakt = f"mailto:{k['email']}" if k.get("email") else (f"tel:{k['telefon']}" if k.get("telefon") else None)
    if not kontakt:
        return None
    wygasa = (dzis + dt.timedelta(days=180)).isoformat() + "T00:00:00.000Z"
    domena = firma["firma"]["domena"]
    return (f"Contact: {kontakt}\nExpires: {wygasa}\nPreferred-Languages: pl, en\n"
            f"Canonical: {domena}/.well-known/security.txt\n")


def manifest(firma: dict, tlo: str, ikony_dir: Path, zasob=None) -> str | None:
    """site.webmanifest; `zasob` dodaje ?v=<skrót> do adresów ikon (zmiana logo = nowy adres mimo rocznego cache)."""
    ikony = []
    for plik, rozmiar, cel in (("icon-192.png", "192x192", "any"), ("icon-512.png", "512x512", "any"),
                               ("icon-maskable-512.png", "512x512", "maskable")):
        if (ikony_dir / plik).is_file():
            src = zasob(f"assets/img/ikony/{plik}") if zasob else f"/assets/img/ikony/{plik}"
            ikony.append({"src": src, "sizes": rozmiar, "type": "image/png", "purpose": cel})
    if not ikony:
        return None
    nazwa = firma["firma"]["nazwa"]
    return json.dumps({"name": nazwa, "short_name": nazwa[:12], "lang": "pl", "start_url": "/", "display": "browser",
                       "background_color": tlo, "theme_color": tlo, "icons": ikony}, ensure_ascii=False, indent=2) + "\n"


def rss(firma: dict, wpisy: list[dict], abs_url) -> str:
    """Kanał RSS 2.0 /aktualnosci.xml (funkcje.rss): 20 najnowszych wpisów z tytułem, opisem i datą (KONTRAKT §9.1).
    Daty wpisów nie mają godziny — pubDate to północ czasu polskiego; strefę bierzemy stałą (+0100), bo godzina
    i tak nie jest prawdziwa, a czytniki sortują po dniu."""
    from email.utils import format_datetime
    strefa = dt.timezone(dt.timedelta(hours=1))
    nazwa = firma["firma"]["nazwa"]
    kanal = abs_url("/aktualnosci.xml")
    pozycje = []
    for w in wpisy[:20]:
        url = abs_url(w["sciezka"])
        data = format_datetime(dt.datetime.fromisoformat(w["data"]).replace(tzinfo=strefa))
        pozycje.append(f"    <item>\n      <title>{escape(w['tytul'])}</title>\n      <link>{escape(url)}</link>\n"
                       f"      <guid isPermaLink=\"true\">{escape(url)}</guid>\n      <pubDate>{data}</pubDate>\n"
                       + (f"      <description>{escape(w['opis'])}</description>\n" if w.get("opis") else "")
                       + "    </item>\n")
    ostatni = format_datetime(dt.datetime.fromisoformat(wpisy[0]["data"]).replace(tzinfo=strefa)) if wpisy else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n  <channel>\n'
            f"    <title>{escape(f'Aktualności – {nazwa}')}</title>\n"
            f"    <link>{escape(abs_url('/aktualnosci'))}</link>\n"
            f"    <description>{escape(firma['firma'].get('opis') or nazwa)}</description>\n"
            "    <language>pl</language>\n"
            f"    <atom:link href=\"{escape(kanal)}\" rel=\"self\" type=\"application/rss+xml\"/>\n"
            + (f"    <lastBuildDate>{ostatni}</lastBuildDate>\n" if ostatni else "")
            + "".join(pozycje) + "  </channel>\n</rss>\n")


def przekierowania(firma: dict, sciezki: set[str], raport=None) -> str | None:
    """dist/_redirects z firma.przekierowania: stare adresy (dawna strona) → nowe, kod 301.
    Cloudflare stosuje _redirects przed plikami strony, więc przekierowanie ze ścieżki, pod którą powstaje strona,
    zasłoniłoby ją — to błąd. Przekierowania domeny (www → bez www) są w Redirect Rules strefy (docs/CLOUDFLARE.md)."""
    lista = firma.get("przekierowania") or []
    if not lista:
        return None
    zajete = set()
    for s in sciezki:
        zajete |= {s, s.rstrip("/") + "/", s.rstrip("/") + ".html"} if s != "/" else {"/", "/index.html"}
    linie = ["# Przekierowania ze starych adresów (data/firma.json → przekierowania). Plik generowany przez tools/build.py."]
    for i, r in enumerate(lista):
        if r["z"] in zajete and raport is not None:
            raport.blad(f"przekierowanie z „{r['z']}” zasłoniłoby stronę, która powstaje pod tym adresem",
                        plik="data/firma.json", pole=f"przekierowania[{i}].z", naprawa="usuń wpis albo zmień ścieżkę „z”")
        cel = r["do"].split("#", 1)[0].split("?", 1)[0] or "/"
        if r["do"].startswith("/") and cel not in zajete and raport is not None:
            raport.ostrzezenie(f"przekierowanie „{r['z']}” prowadzi do „{r['do']}”, a takiej strony nie ma — odwiedzający trafi na 404",
                               plik="data/firma.json", pole=f"przekierowania[{i}].do")
        linie.append(f"{_jeden_wiersz(r['z'], f'przekierowania[{i}].z')} {_jeden_wiersz(r['do'], f'przekierowania[{i}].do')} 301")
    return "\n".join(linie) + "\n"
