"""Oferta, cennik, karta (menu) i produkty: wartości dla szablonów, kontrole danych i JSON-LD (KONTRAKT §4.2, §6.1, §9.1).

- auto()        → auto.oferta, auto.cennik, auto.menu, auto.produkty: skróty na stronę główną (limity z presetu),
                  adresy podstron usług, opis pliku PDF (typ, rozmiar, strony), legenda oznaczeń karty, grupy produktów
                  i tekst linku „…” ze skrótu do pełnej wersji (tylko gdy pełna wersja pokazuje coś więcej);
- kontrole()    → błędy, których nie wyrazi schemat: pusta cena {}, „od” > „do”, ceny netto w branży dla konsumentów,
                  nieznana kategoria produktu, brak pliku PDF, alergen spoza 14 grup;
- jsonld()      → Menu z MenuSection/MenuItem (hasMenu) na stronie z pełną kartą, Product z Offer wyłącznie przy
                  prawdziwej cenie, lekki OfferCatalog usług (bez rich result), Service na podstronie usługi;
- og_elementu() → obrazek podglądu linku podstrony usługi: assets/img/og/<id-zdjęcia>.jpg (1200×630, tools/zdjecia.py).

Ceny dla konsumentów są brutto (art. 3 ust. 2 ustawy z 9.05.2014 o informowaniu o cenach towarów i usług).
Ceny netto tylko w cenniku z "dla": "firmy" i tylko w branży, której preset ma "cennik_netto": true —
strona pokazuje wtedy przy cenach „netto”. Ceny w ofercie, karcie i produktach są zawsze brutto.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import pliki
from . import typografia as typo

# oznaczenia w karcie: pole w danych → (skrót na stronie, opis w legendzie i dla czytników ekranu)
ZNAKI = [("wege", "W", "danie wegetariańskie"), ("ostre", "O", "danie ostre")]
# 14 grup alergenów (rozporządzenie UE 1169/2011, zał. II) — krótkie nazwy używane w polskich kartach
ALERGENY = ("gluten", "skorupiaki", "jaja", "ryby", "orzeszki ziemne", "soja", "mleko", "orzechy", "seler",
            "gorczyca", "sezam", "dwutlenek siarki i siarczyny", "łubin", "mięczaki")
KUCHNIE = {"Restaurant", "FoodEstablishment", "CafeOrCoffeeShop", "BarOrPub", "Bakery", "FastFoodRestaurant",
           "IceCreamShop", "Winery", "Brewery", "Distillery"}


def _lista_slow(slowa: list[str]) -> str:
    """„a, b i c”."""
    if len(slowa) < 2:
        return "".join(slowa)
    return ", ".join(slowa[:-1]) + " i " + slowa[-1]


def _mala(nazwa: str) -> str:
    """Nazwa w środku zdania (opis strony): „Roboty drogowe” → „roboty drogowe”; skrót („BHP”) bez zmian.
    Nazwy własne na początku pozycji („Porotherm”) też dostaną małą literę — opis strony można wtedy wpisać ręcznie."""
    return nazwa[0].lower() + nazwa[1:] if len(nazwa) > 1 and nazwa[1].islower() else nazwa


def _po_trochu(grupy: list[dict], klucz: str, limit: int | None) -> list[dict]:
    """Skrót na stronę główną: po jednej pozycji z każdej grupy na zmianę, aż do limitu (6 działów karty i limit 12 →
    po 2 dania z każdego) — widać przekrój, nie tylko pierwszy dział. Kolejność grup i pozycji jak w danych."""
    if not limit:
        return [dict(g) for g in grupy]
    ile = [0] * len(grupy)
    zostalo = limit
    while zostalo > 0:
        dodano = False
        for i, g in enumerate(grupy):
            if zostalo and ile[i] < len(g[klucz]):
                ile[i] += 1
                zostalo -= 1
                dodano = True
        if not dodano:
            break
    return [dict(g, **{klucz: g[klucz][:ile[i]]}) for i, g in enumerate(grupy) if ile[i]]


def _pdf(d, sciezka: str | None) -> dict | None:
    if not sciezka:
        return None
    p = d.klient / sciezka
    if not p.is_file():
        return None                      # kontrole() zgłasza błąd przed renderem
    return dict(pliki.opis(p), href=sciezka)


def _pozycji(n: int) -> str:
    return f"{n} {typo.liczba_mnoga(n, 'pozycja,pozycje,pozycji')}"


# ----------------------------------------------------------------------------- auto

def auto(d, podstrony: set, sekcje_widoczne: list, baza: dict) -> dict:
    """baza = kontekst auto policzony do tej pory w dane.auto() (telefon, trasa — do przycisku podstrony usługi)."""
    from .dane import _cta                      # import w funkcji — dane.py importuje ten moduł
    t, limity = d.tresc, d.preset.get("limity", {})
    wynik: dict = {"oferta": None, "cennik": None, "menu": None, "produkty": None}
    cennik = t.get("cennik")

    of = t.get("oferta")
    if of and of.get("pozycje"):
        zdj = d.zdjecia
        # ceny z cennika (nazwa albo kwota) — skrót oferty na głównej nie powtarza ceny, którą tabela cennika
        # pokazuje kilka wierszy niżej
        w_cenniku_nazwy = {p["nazwa"].strip().lower() for g in (cennik or {}).get("grupy") or [] for p in g["pozycje"]}
        w_cenniku_ceny = [p.get("cena") for g in (cennik or {}).get("grupy") or [] for p in g["pozycje"]
                          if p.get("cena") is not None]
        poz = [dict(p, url=(f"/oferta/{p['slug']}" if f"/oferta/{p['slug']}" in podstrony else None),
                    podpis=(zdj.get(p.get("zdjecie")) or {}).get("podpis"),
                    cena_w_cenniku=p.get("cena") is not None and (p["nazwa"].strip().lower() in w_cenniku_nazwy
                                                                   or p.get("cena") in w_cenniku_ceny))
               for p in of["pozycje"]]
        limit = limity.get("oferta")
        skrot = poz[:limit] if limit else poz
        dodatki = []
        if any(p.get("zakres") for p in poz):
            dodatki.append("szczegółowy zakres")
        if any(p.get("czas") for p in poz):
            dodatki.append("czas realizacji")
        if any(p["url"] for p in poz):
            dodatki.append("opisy usług")
        if cennik:
            dodatki.append("cennik")
        if len(poz) > len(skrot):
            wiecej = f"Wszystkie pozycje ({len(poz)})" + (" i cennik" if cennik else "")
        else:
            wiecej = typo.wersaliki_pierwsza(_lista_slow(dodatki)) or None
        naglowek = of.get("naglowek") or d.preset.get("naglowki", {}).get("oferta") or "Oferta"
        wynik["oferta"] = {
            "pozycje": poz, "skrot": skrot, "wiecej": wiecej, "naglowek": naglowek,
            "nazwy": _lista_slow([_mala(p["nazwa"]) for p in poz]),
            "ma_zdjecia": any(p.get("zdjecie") for p in poz),
            # skrót na głównej: zdjęcia tylko wtedy, gdy ma je każda pozycja — inaczej wiersze skaczą 300 px / 80 px
            "skrot_zdjecia": all(p.get("zdjecie") for p in skrot),
            # jedno wezwanie do działania na podstronie usługi: z presetu (nie z hero — tam bywa „Zamów beton”)
            "cta": _cta(d.preset.get("cta_glowne"), baza, podstrony, (t.get("do_pobrania") or {}).get("pozycje") or []),
            "powrot": "/oferta" if "/oferta" in podstrony else ("/#oferta" if "oferta" in sekcje_widoczne else "/"),
        }

    if cennik and cennik.get("grupy"):
        # kolumna „Czas” tylko w tabeli, w której choć jedna pozycja ma czas
        z_czasem = lambda gg: [dict(g, ma_czas=any(p.get("czas") for p in g["pozycje"])) for g in gg]
        grupy = cennik["grupy"]
        n = sum(len(g["pozycje"]) for g in grupy)
        skrot = _po_trochu(grupy, "pozycje", limity.get("cennik"))
        pokazane = sum(len(g["pozycje"]) for g in skrot)
        wynik["cennik"] = {
            "grupy": z_czasem(grupy), "skrot": z_czasem(skrot), "liczba": n,
            "netto": cennik.get("dla") == "firmy",
            "pdf": _pdf(d, cennik.get("pdf")),
            "wiecej": f"Pełny cennik ({_pozycji(n)})" if pokazane < n else None,
        }

    menu = t.get("menu")
    if menu and menu.get("kategorie"):
        kat = [dict(k, pozycje=[dict(p, znaki=[{"skrot": s, "opis": o} for pole, s, o in ZNAKI if p.get(pole)])
                                for p in k["pozycje"]]) for k in menu["kategorie"]]
        n = sum(len(k["pozycje"]) for k in kat)
        skrot = _po_trochu(kat, "pozycje", limity.get("menu"))
        pokazane = sum(len(k["pozycje"]) for k in skrot)
        legenda = lambda kk: [{"skrot": s, "opis": o} for pole, s, o in ZNAKI
                              if any(p.get(pole) for k in kk for p in k["pozycje"])]
        alergeny = any(p.get("alergeny") for k in kat for p in k["pozycje"])
        if pokazane < n:
            wiecej = f"Cała karta ({_pozycji(n)})"
        else:
            wiecej = "Karta do druku" + (" z alergenami" if alergeny else "")
        # karta bez cen na stronie (menu.ceny = "w_lokalu"): zdanie pod kartą, na głównej i na /menu
        ceny_w_lokalu = menu.get("ceny") == "w_lokalu"
        uwagi = menu.get("uwagi") or ("Ceny podajemy w lokalu." if ceny_w_lokalu else None)
        wynik["menu"] = {"kategorie": kat, "skrot": skrot, "liczba": n, "legenda": legenda(kat), "uwagi": uwagi,
                         "ceny_w_lokalu": ceny_w_lokalu,
                         "nazwy": _lista_slow([_mala(k["nazwa"]) for k in kat]),
                         "legenda_skrot": legenda(skrot), "alergeny": alergeny, "pdf": _pdf(d, menu.get("pdf")),
                         "wiecej": wiecej}

    pr = t.get("produkty")
    if pr and pr.get("pozycje"):
        kategorie = pr.get("kategorie") or []
        nazwy = {k["slug"]: k["nazwa"] for k in kategorie}
        poz = [dict(p, kategoria_nazwa=nazwy.get(p.get("kategoria"))) for p in pr["pozycje"]]
        grupy = []
        for k in kategorie:
            w = [p for p in poz if p.get("kategoria") == k["slug"]]
            if w:
                grupy.append({"slug": k["slug"], "nazwa": k["nazwa"], "liczba": len(w), "pozycje": w})
        reszta = [p for p in poz if p.get("kategoria") not in nazwy]
        if reszta:
            # bez kategorii: jedna grupa bez nagłówka, gdy kategorii nie ma wcale; inaczej „Pozostałe”
            grupy.append({"slug": "pozostale", "nazwa": "Pozostałe" if grupy else None, "liczba": len(reszta),
                          "pozycje": reszta})
        limit = limity.get("produkty")
        skrot = poz[:limit] if limit else poz

        def listy(pozycje):
            """Najpierw produkty ze zdjęciem (siatka), potem bez zdjęcia (wiersze) — kolejność w obrębie listy z danych."""
            ze, bez = [p for p in pozycje if p.get("zdjecie")], [p for p in pozycje if not p.get("zdjecie")]
            return [x for x in ({"zdjecia": True, "pozycje": ze}, {"zdjecia": False, "pozycje": bez}) if x["pozycje"]]
        for g in grupy:
            g["listy"] = listy(g["pozycje"])
        wynik["produkty"] = {
            "pozycje": poz, "skrot": skrot, "skrot_listy": listy(skrot), "grupy": grupy, "liczba": len(poz),
            "nazwy": _lista_slow([_mala(g["nazwa"]) for g in grupy if g["nazwa"]] or [_mala(p["nazwa"]) for p in poz[:6]]),
            "ma_zdjecia": any(p.get("zdjecie") for p in poz),
            "filtr": len(grupy) >= 2,
            "ma_ceny": any(p.get("cena") is not None for p in poz),
            # „Ceny brutto.” raz: nie, gdy wstęp sekcji już to mówi
            "brutto_we_wstepie": "brutto" in (pr.get("wstep") or "").lower(),
            "ma_ceny_skrot": any(p.get("cena") is not None for p in skrot),
            "wiecej": f"Wszystkie produkty ({len(poz)})" if len(poz) > len(skrot) else None,
        }
    return wynik


# ----------------------------------------------------------------------------- kontrole danych

def _ceny(t: dict):
    """(ścieżka pola, cena) każdej ceny w ofercie, cenniku, karcie i produktach."""
    for i, p in enumerate((t.get("oferta") or {}).get("pozycje") or []):
        yield f"oferta.pozycje[{i}].cena", p.get("cena")
    for gi, g in enumerate((t.get("cennik") or {}).get("grupy") or []):
        for i, p in enumerate(g["pozycje"]):
            yield f"cennik.grupy[{gi}].pozycje[{i}].cena", p.get("cena")
    for ki, k in enumerate((t.get("menu") or {}).get("kategorie") or []):
        for i, p in enumerate(k["pozycje"]):
            yield f"menu.kategorie[{ki}].pozycje[{i}].cena", p.get("cena")
    for i, p in enumerate((t.get("produkty") or {}).get("pozycje") or []):
        yield f"produkty.pozycje[{i}].cena", p.get("cena")


def kontrole(d, raport) -> None:
    t = d.tresc
    plik = "data/tresc.json"
    # 1. ceny: obiekt bez „od” i „do” albo odwrócony zakres
    for pole, c in _ceny(t):
        if isinstance(c, dict):
            od, do = c.get("od"), c.get("do")
            if od is None and do is None:
                raport.blad("cena {} bez „od” i „do” — nic się nie wyświetli", plik=plik, pole=pole,
                            naprawa="wpisz liczbę (np. 120), zakres {\"od\": 90, \"do\": 140} albo null")
            elif od is not None and do is not None and od > do:
                raport.blad(f"cena: „od” ({typo.liczba(od)}) jest większe niż „do” ({typo.liczba(do)})", plik=plik, pole=pole)
    # 2. cennik netto tylko dla firm i tylko w branży, która na to pozwala (ceny dla konsumentów muszą być brutto)
    cennik = t.get("cennik")
    if cennik and cennik.get("dla") == "firmy" and not d.preset.get("cennik_netto", False):
        raport.blad(f"branża „{d.firma['branza']}” sprzedaje konsumentom — ceny muszą być brutto (art. 3 ust. 2 ustawy "
                    "o informowaniu o cenach towarów i usług), a \"dla\": \"firmy\" oznacza ceny netto",
                    plik=plik, pole="cennik.dla", naprawa="wpisz ceny brutto i \"dla\": \"konsumenci\"")
    if cennik:
        for gi, g in enumerate(cennik.get("grupy") or []):
            for i, p in enumerate(g["pozycje"]):
                if p.get("cena") is None:
                    raport.ostrzezenie(f"cennik: „{p['nazwa']}” nie ma ceny — w tabeli cen wygląda to jak brak danych",
                                       plik=plik, pole=f"cennik.grupy[{gi}].pozycje[{i}].cena",
                                       naprawa="wpisz cenę albo zakres „od–do”, albo przenieś pozycję do oferty", klasa="A")
        if len(cennik.get("grupy") or []) > 1 and any(not g.get("nazwa") for g in cennik["grupy"]):
            raport.blad("cennik ma kilka grup — każda potrzebuje nazwy (nagłówek nad tabelą)", plik=plik, pole="cennik.grupy")
    # 3. produkty: kategoria musi być zdefiniowana, slugi kategorii bez powtórzeń
    pr = t.get("produkty")
    if pr:
        kat = [k["slug"] for k in pr.get("kategorie") or []]
        for s in {x for x in kat if kat.count(x) > 1}:
            raport.blad(f"powtórzony slug kategorii „{s}”", plik=plik, pole="produkty.kategorie")
        for i, p in enumerate(pr.get("pozycje") or []):
            if p.get("kategoria") and p["kategoria"] not in kat:
                raport.blad(f"produkt „{p['nazwa']}”: nieznana kategoria „{p['kategoria']}”"
                            + (f" (są: {', '.join(kat)})" if kat else " (produkty.kategorie jest puste)"),
                            plik=plik, pole=f"produkty.pozycje[{i}].kategoria",
                            naprawa="dopisz kategorię do produkty.kategorie albo popraw slug")
    # 4. pliki PDF karty i cennika: istnieją, leżą w assets/ (trafiają do dist/), są PDF-em
    for blok in ("menu", "cennik"):
        sciezka = (t.get(blok) or {}).get("pdf")
        if not sciezka:
            continue
        if not sciezka.startswith("assets/") or not sciezka.lower().endswith(".pdf"):
            raport.blad(f"{blok}.pdf: „{sciezka}” — plik PDF musi leżeć w assets/img/pliki/", plik=plik, pole=f"{blok}.pdf",
                        naprawa="np. \"assets/img/pliki/karta.pdf\"")
        elif not (d.klient / sciezka).is_file():
            raport.blad(f"{blok}.pdf: nie ma pliku {sciezka}", plik=plik, pole=f"{blok}.pdf",
                        naprawa="dodaj plik albo wpisz null")
    # 4b. karta bez cen: jawny stan „ceny w lokalu” zamiast listy nazw, która wygląda jak brak danych
    menu = t.get("menu")
    if menu and menu.get("kategorie"):
        ceny = [p.get("cena") for k in menu["kategorie"] for p in k["pozycje"]]
        if menu.get("ceny") == "w_lokalu" and any(c is not None for c in ceny):
            raport.blad("menu.ceny = \"w_lokalu\", a przy części dań są ceny — albo ceny na stronie, albo tylko w lokalu",
                        plik=plik, pole="menu.ceny", naprawa="usuń \"ceny\" (ceny na stronie) albo wpisz \"cena\": null")
        elif menu.get("ceny") != "w_lokalu" and all(c is None for c in ceny):
            raport.ostrzezenie("karta nie ma żadnej ceny — jeśli ceny są tylko w lokalu, wpisz \"ceny\": \"w_lokalu\" "
                               "(pod kartą stanie zdanie o cenach), a jeśli ich nie znasz — dopisz je do do_potwierdzenia",
                               plik=plik, pole="menu.ceny", klasa="A")
    # 5. alergeny: nazwy 14 grup (jedna nazwa = jedna grupa, legenda zrozumiała dla gościa)
    for ki, k in enumerate((t.get("menu") or {}).get("kategorie") or []):
        for i, p in enumerate(k["pozycje"]):
            for a in p.get("alergeny") or []:
                if a.strip().lower() not in ALERGENY:
                    raport.ostrzezenie(f"karta: „{p['nazwa']}” — alergen „{a}” spoza 14 grup ({', '.join(ALERGENY)})",
                                       plik=plik, pole=f"menu.kategorie[{ki}].pozycje[{i}].alergeny",
                                       naprawa="użyj nazwy grupy, np. „mleko” zamiast „laktoza”, „gluten” zamiast „pszenica”")


# ----------------------------------------------------------------------------- JSON-LD

def _oferta_ld(cena, jednostka=None, url=None) -> dict | None:
    """Offer / AggregateOffer z ceną w PLN (brutto) albo None, gdy ceny nie ma."""
    if cena is None:
        return None
    if isinstance(cena, dict):
        od, do = cena.get("od"), cena.get("do")
        if od is None and do is None:
            return None
        o = {"@type": "AggregateOffer", "priceCurrency": "PLN"}
        if od is not None:
            o["lowPrice"] = float(od)
        if do is not None:
            o["highPrice"] = float(do)
    else:
        o = {"@type": "Offer", "price": float(cena), "priceCurrency": "PLN"}
    if jednostka:
        o["priceSpecification"] = {"@type": "UnitPriceSpecification", "priceCurrency": "PLN", "unitText": jednostka,
                                   **({"price": float(cena)} if not isinstance(cena, dict) else {})}
    if url:
        o["url"] = url
    return o


def _zdjecie_url(d, zid: str | None, abs_url) -> str | None:
    """Pełny adres największego JPEG-a zdjęcia (z ?v=) albo None."""
    if not zid:
        return None
    plik = d.klient / "assets" / "img" / "foto" / "manifest.json"
    manifest = json.loads(plik.read_text(encoding="utf-8")) if plik.is_file() else {}
    wpis = manifest.get(zid)
    if wpis:
        return abs_url(f"assets/img/foto/{zid}-{wpis['szerokosci'][-1]}.jpg")
    z = d.zdjecia.get(zid)
    return abs_url(f"assets/img/foto/{zid}{Path(z['zrodlo_plik']).suffix.lower()}") if z else None


def jsonld(d, auto: dict, strona_ctx: dict, abs_url, firma: dict, id_firmy: str) -> list[dict]:
    """Węzły do @graph dla bieżącej strony; uzupełnia też węzeł firmy (hasMenu, hasOfferCatalog)."""
    baza = d.firma["firma"]["domena"] or ""
    sc = strona_ctx.get("sciezka")
    podstrony, widoczne = set(auto.get("podstrony") or []), auto.get("sekcje_widoczne") or []
    typ = firma.get("@type")
    wezly: list[dict] = []
    t = d.tresc

    # karta: pełna wersja na /menu (albo na głównej, gdy podstrony nie ma); firma wskazuje ją przez hasMenu
    menu = t.get("menu")
    if menu and menu.get("kategorie"):
        strona_menu = "/menu" if "/menu" in podstrony else ("/" if "menu" in widoczne else None)
        if strona_menu and typ in KUCHNIE:
            firma["hasMenu"] = baza + strona_menu
        if strona_menu and sc == strona_menu:
            sekcje = []
            for k in menu["kategorie"]:
                pozycje = []
                for p in k["pozycje"]:
                    mi = {"@type": "MenuItem", "name": p["nazwa"]}
                    if p.get("opis"):
                        mi["description"] = p["opis"]
                    of = _oferta_ld(p.get("cena"))
                    if of:
                        mi["offers"] = of
                    if p.get("wege"):
                        mi["suitableForDiet"] = "https://schema.org/VegetarianDiet"
                    pozycje.append(mi)
                sekcje.append({"@type": "MenuSection", "name": k["nazwa"], "hasMenuItem": pozycje})
            url_menu = baza + strona_menu
            wezel = {"@type": "Menu", "@id": url_menu + "#karta", "inLanguage": "pl-PL", "url": url_menu,
                     "name": menu.get("naglowek") or d.preset.get("naglowki", {}).get("menu") or "Karta",
                     "hasMenuSection": sekcje}
            wezly.append(wezel)
            if typ in KUCHNIE:
                firma["hasMenu"] = {"@id": wezel["@id"]}

    # produkty: Product tylko z prawdziwą ceną (bez ceny Google i tak odrzuca węzeł), na stronie z pełną listą
    pr = t.get("produkty")
    if pr and pr.get("pozycje"):
        strona_pr = "/produkty" if "/produkty" in podstrony else ("/" if "produkty" in widoczne else None)
        if strona_pr and sc == strona_pr:
            nazwy = {k["slug"]: k["nazwa"] for k in pr.get("kategorie") or []}
            url_strony = baza + strona_pr
            for p in pr["pozycje"]:
                of = _oferta_ld(p.get("cena"), p.get("jednostka"), url_strony)
                if not of:
                    continue
                of["seller"] = {"@id": id_firmy}
                prod = {"@type": "Product", "@id": f"{url_strony}#produkt-{p['slug']}", "name": p["nazwa"],
                        "brand": {"@type": "Brand", "name": d.firma["firma"]["nazwa"]}, "offers": of}
                if p.get("opis"):
                    prod["description"] = p["opis"]
                if nazwy.get(p.get("kategoria")):
                    prod["category"] = nazwy[p["kategoria"]]
                img = _zdjecie_url(d, p.get("zdjecie"), abs_url)
                if img:
                    prod["image"] = img
                wezly.append(prod)

    # usługi: lekki katalog przy firmie na głównej i na /oferta (nazwa, adres podstrony, cena — gdy jest)
    of = t.get("oferta")
    ao = auto.get("oferta")
    if of and ao and (sc == "/oferta" or (sc == "/" and "oferta" in widoczne)):
        elementy = []
        for p in ao["pozycje"]:
            usluga = {"@type": "Service", "name": p["nazwa"]}
            if p.get("url"):
                usluga["url"] = baza + p["url"]
            o = _oferta_ld(p.get("cena"), p.get("jednostka")) or {"@type": "Offer"}
            o["itemOffered"] = usluga
            elementy.append(o)
        firma["hasOfferCatalog"] = {"@type": "OfferCatalog", "name": ao["naglowek"], "itemListElement": elementy}

    # podstrona usługi: Service z dostawcą, obszarem i ceną
    if sc and sc.startswith("/oferta/") and ao:
        p = next((x for x in ao["pozycje"] if x.get("url") == sc), None)
        if p:
            s = {"@type": "Service", "@id": baza + sc + "#usluga", "name": p["nazwa"], "url": baza + sc,
                 "provider": {"@id": id_firmy}}
            if p.get("opis"):
                s["description"] = p["opis"]
            if firma.get("areaServed"):
                s["areaServed"] = firma["areaServed"]
            if strona_ctx.get("og_obraz"):
                s["image"] = strona_ctx["og_obraz"]
            o = _oferta_ld(p.get("cena"), p.get("jednostka"), baza + sc)
            if o:
                s["offers"] = o
            wezly.append(s)
            # obrazek firmy zostaje obrazkiem strony głównej, nie zdjęciem usługi
            if strona_ctx.get("og_obraz_strony"):
                firma["image"] = strona_ctx["og_obraz_strony"]
    return wezly


# ----------------------------------------------------------------------------- obrazek podglądu linku

def og_elementu(element: dict | None, klient: Path, zdjecia: dict, abs_zasob) -> tuple[str, str] | None:
    """(adres, alt) obrazka 1200×630 ze zdjęcia elementu kolekcji (usługa, wpis) albo None — wtedy og.jpg strony.
    Kadr robi tools/zdjecia.py (assets/img/og/<id>.jpg); build nie przetwarza obrazów."""
    zid = (element or {}).get("zdjecie")
    if not zid or not (klient / "assets" / "img" / "og" / f"{zid}.jpg").is_file():
        return None
    return abs_zasob(f"assets/img/og/{zid}.jpg"), (zdjecia.get(zid) or {}).get("alt") or ""
