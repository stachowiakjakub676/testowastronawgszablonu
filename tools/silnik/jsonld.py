"""Dane strukturalne schema.org jako jeden @graph (KONTRAKT §9, critic §5.4).

Na każdej stronie: WebSite + firma (podtyp LocalBusiness z presetu albo Organization) z adresem, geo, telefonem,
godzinami (jedna specyfikacja na przedział; dni po angielsku), wyjątkami (specialOpeningHoursSpecification),
sameAs, areaServed, legalName, taxID, identyfikatorami KRS/REGON i logo. Na podstronach dodatkowo BreadcrumbList.
Skrypt godzin (20-godziny.js) czyta godziny właśnie stąd — jedno źródło w HTML.
Bez aggregateRating/review (Google nie pokazuje gwiazdek dla opinii o sobie) i bez FAQPage (domyślnie).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re

from . import typografia as typo
from .dane import DNI, DNI_SCHEMA


def _specyfikacje(tydzien: dict) -> list[dict]:
    """Jedna OpeningHoursSpecification na przedział; dni o tych samych przedziałach łączone w dayOfWeek."""
    grupy: dict[tuple, list[str]] = {}
    for d in DNI:
        for od, do in tydzien.get(d) or []:
            grupy.setdefault((od, do), []).append(DNI_SCHEMA[d])
    wynik = []
    for (od, do), dni in grupy.items():
        wynik.append({"@type": "OpeningHoursSpecification", "dayOfWeek": dni if len(dni) > 1 else dni[0],
                      "opens": od, "closes": _zamkniecie(do)})
    return wynik


def _zamkniecie(do: str) -> str:
    """Zamknięcie o północy („24:00” albo „00:00”) → „23:59”, jak zaleca Google; 20-godziny.js czyta je jako 24:00."""
    return "23:59" if do in ("24:00", "00:00") else do


def _wyjatki(godziny: dict, dzis: dt.date) -> list[dict]:
    wynik = []
    for w in godziny.get("wyjatki") or []:
        data = typo.na_date(w["data"])
        if data < dzis or (data - dzis).days > 366:
            continue
        if not w["godziny"]:
            wynik.append({"@type": "OpeningHoursSpecification", "validFrom": w["data"], "validThrough": w["data"],
                          "opens": "00:00", "closes": "00:00"})
        for od, do in w["godziny"]:
            wynik.append({"@type": "OpeningHoursSpecification", "validFrom": w["data"], "validThrough": w["data"],
                          "opens": od, "closes": _zamkniecie(do)})
    return wynik


def graf(d, auto: dict, strona_ctx: dict, abs_url, logo: dict | None, dzis: dt.date) -> dict:
    f = d.firma
    baza = f["firma"]["domena"] or ""
    typ = f.get("typ_schema") or d.preset.get("typ_schema") or "LocalBusiness"
    k = f["kontakt"]
    a = k.get("adres") or {}
    id_firmy = baza + "/#firma"
    firma: dict = {"@type": typ, "@id": id_firmy, "name": f["firma"]["nazwa"], "url": baza + "/"}
    if f["firma"].get("nazwa_prawna"):
        firma["legalName"] = f["firma"]["nazwa_prawna"]
    if f["firma"].get("opis"):
        firma["description"] = f["firma"]["opis"]
    if k.get("telefon"):
        firma["telephone"] = k["telefon"]
    if k.get("email"):
        firma["email"] = k["email"]
    if a:
        adres = {"@type": "PostalAddress", "streetAddress": a.get("ulica"), "postalCode": a.get("kod"),
                 "addressLocality": a.get("miasto"), "addressCountry": a.get("kraj") or "PL"}
        if a.get("wojewodztwo"):
            adres["addressRegion"] = a["wojewodztwo"]
        firma["address"] = {x: y for x, y in adres.items() if y}
    geo = k.get("geo")
    geo_node = {"@type": "GeoCoordinates", "latitude": float(geo["lat"]), "longitude": float(geo["lng"])} if geo else None
    if f["firma"].get("rok_zalozenia"):
        firma["foundingDate"] = str(f["firma"]["rok_zalozenia"])
    r = f["rejestr"]
    if r.get("nip"):
        firma["taxID"] = r["nip"]
    ident = [{"@type": "PropertyValue", "propertyID": n, "value": r[p]} for n, p in (("KRS", "krs"), ("REGON", "regon"))
             if r.get(p)]
    if ident:
        firma["identifier"] = ident
    if logo:
        firma["logo"] = {"@type": "ImageObject", "url": abs_url(logo["plik"]), "width": logo["szer"], "height": logo["wys"]}
    if strona_ctx.get("og_obraz"):
        firma["image"] = strona_ctx["og_obraz"]
    same = [v for v in f["social"].values() if v]
    if same:
        firma["sameAs"] = same
    if k.get("obszar_dzialania"):
        firma["areaServed"] = [{"@type": "AdministrativeArea", "name": o} for o in k["obszar_dzialania"]]
    dzialy = k.get("dzialy") or []
    punkty = [{"@type": "ContactPoint", "name": x["nazwa"], "telephone": x.get("telefon"), "email": x.get("email"),
               "contactType": x.get("do_czego") or x["nazwa"], "availableLanguage": "pl"} for x in dzialy]
    if punkty:
        firma["contactPoint"] = [{kk: vv for kk, vv in p.items() if vv} for p in punkty]
    g = f.get("godziny")
    wezly = []
    lokal = None
    if typ == "Organization":
        # organizacja nie ma godzin ani geo — jeśli jest salon/biuro z godzinami, osobny LocalBusiness
        if g or geo_node:
            lokal = {"@type": "LocalBusiness", "@id": baza + "/#lokal",
                     "name": f["firma"]["nazwa"] + (f" – {g['nazwa']}" if g and g.get("nazwa") else ""),
                     "parentOrganization": {"@id": id_firmy}, "url": baza + "/"}
            for kk in ("address", "telephone", "image"):
                if kk in firma:
                    lokal[kk] = firma[kk]
            cel = lokal
        else:
            cel = None
    else:
        cel = firma
    if cel is not None:
        if geo_node:
            cel["geo"] = geo_node
            cel["hasMap"] = auto.get("osm_url")
        if g:
            cel["openingHoursSpecification"] = _specyfikacje(g["tydzien"])
            spec = _wyjatki(g, dzis)
            if spec:
                cel["specialOpeningHoursSpecification"] = spec
    strona_www = {"@type": "WebSite", "@id": baza + "/#strona", "url": baza + "/", "name": f["firma"]["nazwa"],
                  "inLanguage": "pl-PL", "publisher": {"@id": id_firmy}}
    if f["firma"].get("nazwa_prawna"):
        strona_www["alternateName"] = f["firma"]["nazwa_prawna"]
    wezly = [strona_www, firma] + ([lokal] if lokal else [])
    wezly += _faq(d, auto, strona_ctx, baza)
    okr = strona_ctx.get("okruszki") or []
    if okr:
        wezly.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": o["nazwa"],
             **({"item": baza + (o["url"] if o["url"] != "/" else "/")} if o.get("url") else
                {"item": strona_ctx.get("kanoniczny")})}
            for i, o in enumerate(okr)]})
    # karta (Menu), produkty z ceną, katalog usług, usługa (tools/silnik/oferta.py)
    from . import oferta
    wezly.extend(oferta.jsonld(d, auto, strona_ctx, abs_url, firma, id_firmy))
    wezly.extend(wezly_modulow(d, auto, strona_ctx, abs_url, logo, dzis, id_firmy))
    return {"@context": "https://schema.org", "@graph": wezly}


def _faq(d, auto: dict, strona_ctx: dict, baza: str) -> list[dict]:
    """FAQPage tylko przy funkcje.faq_schema = true i tylko na stronie, która pokazuje pytania (dziś: główna z sekcją faq —
    sekcja nie ma podstrony i pokazuje wszystkie pytania). Odpowiedź = czysty tekst z Markdownu (bez znaczników).
    Google od 2023 r. pokazuje wyniki FAQ prawie wyłącznie serwisom rządowym i medycznym — stąd domyślnie wyłączone."""
    pozycje = (d.tresc.get("faq") or {}).get("pozycje") or []
    if not (d.firma["funkcje"].get("faq_schema") and pozycje and strona_ctx.get("sciezka") == "/"
            and "faq" in (auto.get("sekcje_widoczne") or [])):
        return []
    # akapity i punkty listy rozdziela spacja, pozostałe znaczniki (a, strong, em) znikają bez śladu
    tekst = lambda s: html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"</?(?:p|li|ul|ol|h\d)>", " ", typo.markdown(s)))).split()
    return [{"@type": "FAQPage", "@id": baza + "/#faq", "url": baza + "/", "inLanguage": "pl-PL",
             "mainEntity": [{"@type": "Question", "name": p["pytanie"],
                             "acceptedAnswer": {"@type": "Answer", "text": " ".join(tekst(p["odpowiedz"]))}}
                            for p in pozycje]}]


# ----------------------------------------------------------------------------- Article (wpis), JobPosting (/kariera)

ETATY = [(r"pełn\w* etat|pełen etat|cał\w* etat", "FULL_TIME"), (r"pół etatu|część etatu|niepełn\w* (?:etat|wymiar)", "PART_TIME"),
         (r"sezon|tymczasow|dorywcz", "TEMPORARY"), (r"staż|praktyk", "INTERN"), (r"zleceni|\bb2b\b|o dzieło|kontrakt", "CONTRACTOR")]


def _zdjecie_abs(d, zid: str | None, abs_url) -> str | None:
    """Pełny adres największego JPEG zdjęcia z manifestu (tools/zdjecia.py) albo None."""
    plik = d.klient / "assets" / "img" / "foto" / "manifest.json"
    if not zid or not plik.is_file():
        return None
    wpis = json.loads(plik.read_text(encoding="utf-8")).get(zid)
    if not wpis or "jpg" not in wpis.get("formaty", []):
        return None
    return abs_url(f"assets/img/foto/{zid}-{max(wpis['szerokosci'])}.jpg")


def _etat(wymiar: str | None) -> list[str]:
    import re
    return [typ for wzor, typ in ETATY if wymiar and re.search(wzor, wymiar.lower())]


def wezly_modulow(d, auto: dict, strona_ctx: dict, abs_url, logo, dzis: dt.date, id_firmy: str) -> list[dict]:
    import html
    f = d.firma
    baza = f["firma"]["domena"] or ""
    nazwa = strona_ctx.get("nazwa")
    wynik = []
    if nazwa == "wpis" and strona_ctx.get("element") and strona_ctx.get("kanoniczny"):
        w = strona_ctx["element"]
        art = {"@type": "Article", "@id": strona_ctx["kanoniczny"] + "#artykul", "headline": w["tytul"][:110],
               "datePublished": w["data"], "inLanguage": "pl-PL", "url": strona_ctx["kanoniczny"],
               "mainEntityOfPage": strona_ctx["kanoniczny"],
               "author": {"@type": "Organization", "@id": id_firmy, "name": f["firma"]["nazwa"], "url": baza + "/"},
               "publisher": {"@id": id_firmy}, "isPartOf": {"@id": baza + "/#strona"}}
        if w.get("opis"):
            art["description"] = w["opis"]
        obraz = _zdjecie_abs(d, w.get("zdjecie"), abs_url) or strona_ctx.get("og_obraz")
        if obraz:
            art["image"] = obraz
        wynik.append(art)
    if nazwa == "kariera":
        a = f["kontakt"].get("adres") or {}
        adres_firmy = {"@type": "PostalAddress", "streetAddress": a.get("ulica"), "postalCode": a.get("kod"),
                       "addressLocality": a.get("miasto"), "addressRegion": a.get("wojewodztwo"), "addressCountry": a.get("kraj") or "PL"}
        # bez @id firmy: ten sam @id z innymi właściwościami scaliłby się z węzłem firmy (sameAs = własna strona)
        organizacja = {"@type": "Organization", "name": f["firma"]["nazwa"], "url": baza + "/"}
        if logo:
            organizacja["logo"] = abs_url(logo["plik"])
        for p in auto.get("kariera") or []:
            od, do = typo.na_date(p.get("opublikowano")), typo.na_date(p.get("wazne_do"))
            # Google wymaga datePosted i description; wygasłej oferty nie zgłaszamy (validThrough ≥ dziś)
            if not (od and do and p.get("opis")) or do < dzis or od > dzis:
                continue
            miejsce = p.get("miejsce")
            if miejsce and a.get("miasto") and a["miasto"].lower() not in miejsce.lower():
                adres = {"@type": "PostalAddress", "addressLocality": miejsce, "addressCountry": a.get("kraj") or "PL"}
            else:
                adres = {x: y for x, y in adres_firmy.items() if y}
            opis = [p["opis"]] + [f"{n}: {p[kl]}" for n, kl in (("Wymiar", "wymiar"), ("Miejsce pracy", "miejsce"),
                                                                    ("Wynagrodzenie", "wynagrodzenie")) if p.get(kl)]
            jp = {"@type": "JobPosting", "@id": f"{baza}/kariera#{p['html_id']}", "title": p["stanowisko"],
                  "description": "".join(f"<p>{html.escape(x)}</p>" for x in opis),
                  "datePosted": od.isoformat(), "validThrough": do.isoformat(),
                  "hiringOrganization": organizacja, "jobLocation": {"@type": "Place", "address": adres},
                  "directApply": False, "url": f"{baza}/kariera#{p['html_id']}", "inLanguage": "pl-PL"}
            etat = _etat(p.get("wymiar"))
            if etat:
                jp["employmentType"] = etat if len(etat) > 1 else etat[0]
            wynik.append(jp)
    return wynik


def jako_skrypt(g: dict) -> str:
    """JSON do <script type="application/ld+json">: każde „<” jako \\u003c — ani „</script>”, ani „<!--” z danych
    nie zmieni sposobu, w jaki przeglądarka czyta resztę strony (JSON pozostaje poprawny)."""
    return json.dumps(g, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
