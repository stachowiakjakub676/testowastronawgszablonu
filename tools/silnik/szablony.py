"""Silnik szablonów SZABLON (KONTRAKT §3). Mała, zamknięta składnia — wszystko nierozpoznane jest błędem.

    {{ sciezka }}                     wartość (escapowana + polska typografia)
    {{ x | filtr }}  {{ x | filtr:"arg" | inny }}
    {% if w %} … {% elif w %} … {% else %} … {% endif %}
    {% for x in w %} … {% else %} … {% endfor %}      (zmienna petla: indeks, indeks0, pierwszy, ostatni, dlugosc)
    {% set nazwa = w %}
    {% include "czesci/x.html" nazwa=w … %}
    {% sekcje %}                      sekcje strony głównej w kolejności z presetu
    {# komentarz #}

Wyrażenia: ścieżki (a.b.0.c), literały ("tekst", 12, 1.5, true, false, null), filtry, porównania
== != < > <= >=, `in`, `not in`, and, or, not, nawiasy.

Nagłówki plików (pierwszy znacznik pliku):
    {# wymaga: tresc.oferta.pozycje, firma.godziny|tresc.menu #}      sekcje i części
    {# strona: sciezka="/kontakt" nav="Kontakt" tytul="Kontakt" #}   strony

Wiersz zawierający tylko znacznik {% … %} albo {# … #} znika w całości (bez pustych linii w wyniku).
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import typografia as typo


class Markup(str):
    """Tekst, który jest już bezpiecznym HTML-em — nie escapujemy go drugi raz."""


_RE_ADRES = re.compile(r"^(https?://|mailto:|tel:)\S*$")


class _Brak:
    """Brak klucza w danych (inny niż jawne null) — w wyrażeniach zachowuje się jak null."""

    def __bool__(self):
        return False

    def __repr__(self):
        return "BRAK"


BRAK = _Brak()


class BladSzablonu(Exception):
    def __init__(self, komunikat: str, plik: str | None = None, linia: int | None = None):
        self.komunikat, self.plik, self.linia = komunikat, plik, linia
        super().__init__(str(self))

    def __str__(self):
        miejsce = f"{self.plik}:{self.linia}: " if self.plik and self.linia else (f"{self.plik}: " if self.plik else "")
        return miejsce + self.komunikat


# ----------------------------------------------------------------------------- tokenizacja

# literał w cudzysłowie może zawierać „}}” i „%}” ({{ "a}}b" }}); komentarz kończy pierwsze „#}”
_LITERAL = r'"(?:[^"\\]|\\.)*"'
_RE_ZNACZNIK = re.compile(r"\{\{((?:" + _LITERAL + r"|[^\"}]|\}(?!\}))*)\}\}"
                          r"|\{%((?:" + _LITERAL + r"|[^\"%]|%(?!\}))*)%\}"
                          r"|\{#(.*?)#\}", re.S)
_RE_OTWARCIE = re.compile(r"\{\{|\{%|\{#")


def tokenizuj(zrodlo: str, plik: str) -> list[tuple[str, str, int]]:
    tokeny: list[list] = []
    poz = 0
    for m in _RE_ZNACZNIK.finditer(zrodlo):
        if m.start() > poz:
            tokeny.append(["tekst", zrodlo[poz:m.start()], zrodlo.count("\n", 0, poz) + 1])
        linia = zrodlo.count("\n", 0, m.start()) + 1
        if m.group(1) is not None:
            tokeny.append(["wyr", m.group(1).strip(), linia])
        elif m.group(2) is not None:
            tokeny.append(["blok", m.group(2).strip(), linia])
        else:
            tokeny.append(["kom", m.group(3).strip(), linia])
        poz = m.end()
    if poz < len(zrodlo):
        tokeny.append(["tekst", zrodlo[poz:], zrodlo.count("\n", 0, poz) + 1])
    # znacznik blokowy sam w wierszu → usuwamy wcięcie przed nim i znak nowego wiersza po nim.
    # Najpierw ustalamy (na niezmienionym tekście), które znaczniki są same w wierszu, potem przycinamy.
    do_przyciecia = []
    for i, t in enumerate(tokeny):
        if t[0] not in ("blok", "kom"):
            continue
        przed = tokeny[i - 1] if i > 0 else None
        po = tokeny[i + 1] if i + 1 < len(tokeny) else None
        if przed is None:
            przed_ok = True
        elif przed[0] != "tekst":
            przed_ok = False            # inny znacznik w tym samym wierszu
        elif "\n" in przed[1]:
            przed_ok = re.search(r"\n[ \t]*$", przed[1]) is not None
        else:
            przed_ok = i - 1 == 0 and not przed[1].strip()   # pierwszy wiersz pliku, samo wcięcie
        po_ok = po is None or (po[0] == "tekst" and re.match(r"[ \t]*(\n|$)", po[1]) is not None)
        if przed_ok and po_ok:
            do_przyciecia.append(i)
    for i in do_przyciecia:
        if i > 0:
            tokeny[i - 1][1] = re.sub(r"[ \t]*$", "", tokeny[i - 1][1])
        if i + 1 < len(tokeny):
            tokeny[i + 1][1] = re.sub(r"^[ \t]*\n?", "", tokeny[i + 1][1], count=1)
    wynik = [tuple(t) for t in tokeny if not (t[0] == "tekst" and t[1] == "")]
    # „{{”, „{%” albo „{#” w tekście = znacznik bez zamknięcia (błąd już przy renderze, także w --szybko)
    for typ, tresc, linia in wynik:
        m = _RE_OTWARCIE.search(tresc) if typ == "tekst" else None
        if m:
            zamkniecie = {"{{": "}}", "{%": "%}", "{#": "#}"}[m.group(0)]
            raise BladSzablonu(f"„{m.group(0)}” bez zamknięcia „{zamkniecie}”", plik, linia + tresc.count("\n", 0, m.start()))
    return wynik


# ----------------------------------------------------------------------------- wyrażenia

_RE_WYR = re.compile(r"""\s*(?:
    (?P<str>"(?:[^"\\]|\\.)*")
  | (?P<num>\d+(?:\.\d+)?)(?![\w])
  | (?P<op>==|!=|<=|>=|<|>|\||:|\(|\)|,|=)
  | (?P<nazwa>[A-Za-z_][\w]*(?:\.[\w]+)*)
)""", re.X)

SLOWA = {"and", "or", "not", "in", "true", "false", "null"}


def lex(tekst: str, plik: str, linia: int) -> list[tuple[str, object]]:
    tokeny = []
    poz = 0
    tekst = tekst.rstrip()
    while poz < len(tekst):
        m = _RE_WYR.match(tekst, poz)
        if not m or m.end() == poz:
            raise BladSzablonu(f"nie rozumiem wyrażenia od „{tekst[poz:poz + 20]}” w „{tekst}”", plik, linia)
        if m.group("str") is not None:
            tokeny.append(("lit", json.loads(m.group("str"))))
        elif m.group("num") is not None:
            n = m.group("num")
            tokeny.append(("lit", float(n) if "." in n else int(n)))
        elif m.group("op") is not None:
            tokeny.append(("op", m.group("op")))
        else:
            n = m.group("nazwa")
            if n in ("true", "false", "null"):
                tokeny.append(("lit", {"true": True, "false": False, "null": None}[n]))
            elif n in SLOWA:
                tokeny.append(("slowo", n))
            else:
                tokeny.append(("nazwa", n))
        poz = m.end()
    return tokeny


class ParserWyrazen:
    def __init__(self, tokeny, zrodlo, plik, linia):
        self.t, self.i, self.zrodlo, self.plik, self.linia = tokeny, 0, zrodlo, plik, linia

    def blad(self, komunikat):
        raise BladSzablonu(f"{komunikat} (w „{self.zrodlo}”)", self.plik, self.linia)

    def podejrzyj(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def wez(self):
        tok = self.podejrzyj()
        self.i += 1
        return tok

    def oczekuj(self, typ, wartosc=None):
        tok = self.wez()
        if tok[0] != typ or (wartosc is not None and tok[1] != wartosc):
            self.blad(f"oczekiwano „{wartosc or typ}”, jest „{tok[1]}”")
        return tok

    def koniec(self):
        return self.i >= len(self.t)

    def wyrazenie(self):
        return self._lub()

    def _lub(self):
        lewa = self._i()
        while self.podejrzyj() == ("slowo", "or"):
            self.wez()
            lewa = ("lub", lewa, self._i())
        return lewa

    def _i(self):
        lewa = self._nie()
        while self.podejrzyj() == ("slowo", "and"):
            self.wez()
            lewa = ("i", lewa, self._nie())
        return lewa

    def _nie(self):
        if self.podejrzyj() == ("slowo", "not"):
            self.wez()
            return ("nie", self._nie())
        return self._porownanie()

    def _porownanie(self):
        lewa = self._filtry()
        tok = self.podejrzyj()
        if tok[0] == "op" and tok[1] in ("==", "!=", "<", ">", "<=", ">="):
            self.wez()
            return ("por", tok[1], lewa, self._filtry())
        if tok == ("slowo", "in"):
            self.wez()
            return ("por", "in", lewa, self._filtry())
        if tok == ("slowo", "not") and self.i + 1 < len(self.t) and self.t[self.i + 1] == ("slowo", "in"):
            self.wez()
            self.wez()
            return ("nie", ("por", "in", lewa, self._filtry()))
        return lewa

    def _filtry(self):
        w = self._podstawa()
        while self.podejrzyj() == ("op", "|"):
            self.wez()
            nazwa = self.oczekuj("nazwa")[1]
            arg = None
            if self.podejrzyj() == ("op", ":"):
                self.wez()
                arg = self._podstawa()
            w = ("filtr", w, nazwa, arg)
        return w

    def _podstawa(self):
        tok = self.wez()
        if tok[0] == "lit":
            return ("lit", tok[1])
        if tok[0] == "nazwa":
            return ("sciezka", tok[1])
        if tok == ("op", "("):
            w = self.wyrazenie()
            self.oczekuj("op", ")")
            return w
        self.blad(f"nieoczekiwany element „{tok[1]}”")


def parsuj_wyrazenie(zrodlo: str, plik: str, linia: int):
    p = ParserWyrazen(lex(zrodlo, plik, linia), zrodlo, plik, linia)
    w = p.wyrazenie()
    if not p.koniec():
        p.blad(f"nadmiarowy fragment „{p.podejrzyj()[1]}”")
    return w


def _ma_domyslnie(w) -> bool:
    while w and w[0] == "filtr":
        if w[2] == "domyslnie":
            return True
        w = w[1]
    return False


# ----------------------------------------------------------------------------- parser szablonu

class Szablon:
    def __init__(self, plik: str, ast: list, wymaga: str | None, strona: dict | None):
        self.plik, self.ast, self.wymaga, self.strona = plik, ast, wymaga, strona


_RE_PARAM = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


def parsuj(zrodlo: str, plik: str) -> Szablon:
    tokeny = tokenizuj(zrodlo, plik)
    wymaga = strona = None
    for t in tokeny:
        if t[0] == "tekst" and not t[1].strip():
            continue
        if t[0] == "kom":
            if t[1].startswith("wymaga:"):
                wymaga = t[1][len("wymaga:"):].strip()
            elif t[1].startswith("strona:"):
                strona = {k: v.replace('\\"', '"') for k, v in _RE_PARAM.findall(t[1][len("strona:"):])}
        break
    ast, i, koniec = _parsuj_blok(tokeny, 0, plik, ())
    return Szablon(plik, ast, wymaga, strona)


def _parsuj_blok(tokeny, i, plik, konce):
    wynik = []
    while i < len(tokeny):
        typ, tresc, linia = tokeny[i]
        if typ == "tekst":
            wynik.append(("tekst", tresc))
        elif typ == "kom":
            pass
        elif typ == "wyr":
            if not tresc:
                raise BladSzablonu("puste {{ }}", plik, linia)
            wynik.append(("wyr", parsuj_wyrazenie(tresc, plik, linia), tresc, linia))
        else:
            slowo = tresc.split(None, 1)[0] if tresc else ""
            reszta = tresc[len(slowo):].strip()
            if slowo in konce:
                return wynik, i, (slowo, reszta, linia)
            if slowo == "if":
                galezie = [(parsuj_wyrazenie(reszta, plik, linia), None)]
                inaczej = None
                i += 1
                while True:
                    cialo, i, (k, kr, kl) = _parsuj_do(tokeny, i, plik, ("elif", "else", "endif"), "if", linia)
                    galezie[-1] = (galezie[-1][0], cialo)
                    if k == "elif":
                        galezie.append((parsuj_wyrazenie(kr, plik, kl), None))
                        i += 1
                        continue
                    if k == "else":
                        inaczej, i, (k2, _, _) = _parsuj_do(tokeny, i + 1, plik, ("endif",), "if", linia)
                    break
                wynik.append(("if", galezie, inaczej or [], linia))
            elif slowo == "for":
                m = re.match(r"^([A-Za-z_]\w*)\s+in\s+(.+)$", reszta, re.S)
                if not m:
                    raise BladSzablonu("składnia: {% for x in lista %}", plik, linia)
                wyr = parsuj_wyrazenie(m.group(2), plik, linia)
                cialo, i, (k, _, _) = _parsuj_do(tokeny, i + 1, plik, ("else", "endfor"), "for", linia)
                inaczej = []
                if k == "else":
                    inaczej, i, _ = _parsuj_do(tokeny, i + 1, plik, ("endfor",), "for", linia)
                wynik.append(("for", m.group(1), wyr, cialo, inaczej, linia))
            elif slowo == "set":
                m = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", reszta, re.S)
                if not m:
                    raise BladSzablonu("składnia: {% set nazwa = wyrażenie %}", plik, linia)
                wynik.append(("set", m.group(1), parsuj_wyrazenie(m.group(2), plik, linia), linia))
            elif slowo == "include":
                tok = lex(reszta, plik, linia)
                if not tok or tok[0][0] != "lit" or not isinstance(tok[0][1], str):
                    raise BladSzablonu('składnia: {% include "czesci/plik.html" nazwa=wartość %}', plik, linia)
                p = ParserWyrazen(tok[1:], reszta, plik, linia)
                parametry = {}
                while not p.koniec():
                    nazwa = p.oczekuj("nazwa")[1]
                    p.oczekuj("op", "=")
                    parametry[nazwa] = p._filtry() if p.podejrzyj()[0] != "slowo" else p.wyrazenie()
                wynik.append(("include", tok[0][1], parametry, linia))
            elif slowo == "sekcje":
                if reszta:
                    raise BladSzablonu("{% sekcje %} nie przyjmuje parametrów", plik, linia)
                wynik.append(("sekcje", linia))
            elif slowo in ("elif", "else", "endif", "endfor"):
                raise BladSzablonu(f"„{{% {slowo} %}}” bez pasującego otwarcia", plik, linia)
            else:
                raise BladSzablonu(f"nieznany znacznik „{{% {slowo} %}}”", plik, linia)
        i += 1
    if konce:
        raise BladSzablonu(f"brak zamknięcia ({' / '.join(konce)})", plik, None)
    return wynik, i, None


def _parsuj_do(tokeny, i, plik, konce, otwarcie, linia_otwarcia):
    try:
        cialo, i, koniec = _parsuj_blok(tokeny, i, plik, konce)
    except BladSzablonu as b:
        if b.linia is None:
            raise BladSzablonu(f"„{{% {otwarcie} %}}” nie ma zamknięcia „{{% end{otwarcie} %}}”", plik, linia_otwarcia)
        raise
    return cialo, i, koniec


# ----------------------------------------------------------------------------- render

class Zakres:
    """Stos ramek zmiennych: parametry include, zmienne pętli i {% set %}."""

    def __init__(self, globalne: dict):
        self.ramki = [globalne]

    def nowa(self, zmienne: dict | None = None):
        z = Zakres.__new__(Zakres)
        z.ramki = self.ramki + [dict(zmienne or {})]
        return z

    def ustaw(self, nazwa, wartosc):
        self.ramki[-1][nazwa] = wartosc

    def szukaj(self, nazwa):
        for r in reversed(self.ramki):
            if nazwa in r:
                return r[nazwa]
        return BRAK


def pobierz(obiekt, sciezka: str):
    """Ścieżka „a.b.0.c” w zagnieżdżonych słownikach/listach; brak → BRAK."""
    for kawalek in sciezka.split("."):
        if obiekt is None or obiekt is BRAK:
            return BRAK
        if isinstance(obiekt, dict):
            obiekt = obiekt.get(kawalek, BRAK)
        elif isinstance(obiekt, (list, tuple)) and kawalek.isdigit():
            idx = int(kawalek)
            obiekt = obiekt[idx] if idx < len(obiekt) else BRAK
        else:
            return BRAK
    return obiekt


def prawda(v) -> bool:
    if v is BRAK or v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v != 0
    if isinstance(v, (str, list, dict, tuple, set)):
        return len(v) > 0
    return bool(v)


class Silnik:
    """Parser + render. `srodowisko` dostarcza usługi zależne od buildu (url, zasob, obraz, sekcje…)."""

    def __init__(self, katalog_src: Path, raport, srodowisko=None):
        self.katalog = Path(katalog_src)
        self.raport = raport
        self.srodowisko = srodowisko
        self._cache: dict[str, Szablon] = {}
        self.filtry = FILTRY

    # --- pliki
    def szablon(self, sciezka: str) -> Szablon:
        if sciezka not in self._cache:
            plik = self.katalog / sciezka
            if not plik.is_file():
                raise BladSzablonu(f"nie ma pliku szablonu src/{sciezka}")
            self._cache[sciezka] = parsuj(plik.read_text(encoding="utf-8"), f"src/{sciezka}")
        return self._cache[sciezka]

    def istnieje(self, sciezka: str) -> bool:
        return (self.katalog / sciezka).is_file()

    def renderuj_plik(self, sciezka: str, kontekst: dict, lokalne: dict | None = None) -> str:
        sz = self.szablon(sciezka)
        zakres = Zakres(kontekst).nowa(lokalne)
        wyj: list[str] = []
        self._renderuj(sz.ast, zakres, wyj, sz.plik)
        return "".join(wyj)

    def renderuj_tekst(self, zrodlo: str, kontekst: dict, nazwa: str = "(tekst)") -> str:
        sz = parsuj(zrodlo, nazwa)
        wyj: list[str] = []
        self._renderuj(sz.ast, Zakres(kontekst).nowa(), wyj, nazwa)
        return "".join(wyj)

    # --- wymagania sekcji/stron
    def niespelnione(self, wymaga: str | None, kontekst) -> list[str]:
        """Zwraca listę niespełnionych warunków z nagłówka „wymaga:” (pusta = wszystko spełnione)."""
        if not wymaga:
            return []
        zakres = kontekst if isinstance(kontekst, Zakres) else Zakres(kontekst)
        braki = []
        for warunek in [w.strip() for w in wymaga.split(",") if w.strip()]:
            opcje = [o.strip() for o in warunek.split("|")]
            if not any(prawda(self._sciezka(o, zakres)) for o in opcje):
                braki.append(warunek)
        return braki

    # --- render
    def _sciezka(self, sciezka: str, zakres: Zakres):
        glowa, _, ogon = sciezka.partition(".")
        v = zakres.szukaj(glowa)
        return pobierz(v, ogon) if ogon else v

    def ocen(self, w, zakres: Zakres, plik: str, linia: int):
        typ = w[0]
        if typ == "lit":
            return w[1]
        if typ == "sciezka":
            return self._sciezka(w[1], zakres)
        if typ == "filtr":
            v = self.ocen(w[1], zakres, plik, linia)
            f = self.filtry.get(w[2])
            if f is None:
                raise BladSzablonu(f"nieznany filtr „{w[2]}” (dostępne: {', '.join(sorted(self.filtry))})", plik, linia)
            arg = self.ocen(w[3], zakres, plik, linia) if w[3] is not None else None
            try:
                return f(self, v, arg)
            except BladSzablonu:
                raise
            except Exception as e:  # noqa: BLE001 — każdy błąd filtra ma trafić do autora z miejscem w pliku
                raise BladSzablonu(f"filtr „{w[2]}”: {e}", plik, linia) from e
        if typ == "nie":
            return not prawda(self.ocen(w[1], zakres, plik, linia))
        if typ == "i":
            return prawda(self.ocen(w[1], zakres, plik, linia)) and prawda(self.ocen(w[2], zakres, plik, linia))
        if typ == "lub":
            a = self.ocen(w[1], zakres, plik, linia)
            return a if prawda(a) else self.ocen(w[2], zakres, plik, linia)
        if typ == "por":
            a = self.ocen(w[2], zakres, plik, linia)
            b = self.ocen(w[3], zakres, plik, linia)
            a = None if a is BRAK else a
            b = None if b is BRAK else b
            op = w[1]
            try:
                if op == "==":
                    return a == b
                if op == "!=":
                    return a != b
                if op == "in":
                    return b is not None and a in b
                if a is None or b is None:
                    return False
                return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            except TypeError:
                raise BladSzablonu(f"nie można porównać {a!r} {op} {b!r}", plik, linia)
        raise BladSzablonu(f"wewnętrzny błąd wyrażenia {w!r}", plik, linia)

    def _na_tekst(self, v, plik, linia) -> str:
        if isinstance(v, Markup):
            return v
        if v is True:
            return "tak"
        if v is False:
            return "nie"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return typo.liczba(v)          # „4,8”, nie „4,80” — tyle miejsc po przecinku, ile w danych
        if isinstance(v, (list, dict, tuple)):
            raise BladSzablonu("nie można wypisać listy ani słownika w {{ }} — użyj {% for %} albo filtra", plik, linia)
        s = str(v)
        if _RE_ADRES.match(s):
            # adres (https://…, mailto:, tel:) bez typografii — półpauza albo twarda spacja zepsułaby link,
            # nawet gdy autor szablonu zapomni o filtrze url
            return html.escape(s)
        myslnik = getattr(self.srodowisko, "myslnik", "polpauza")
        return html.escape(typo.typografia(s, myslnik))

    def _renderuj(self, ast, zakres: Zakres, wyj: list, plik: str):
        for wezel in ast:
            typ = wezel[0]
            if typ == "tekst":
                wyj.append(wezel[1])
            elif typ == "wyr":
                _, w, zrodlo, linia = wezel
                v = self.ocen(w, zakres, plik, linia)
                if v is BRAK or v is None:
                    if not _ma_domyslnie(w):
                        self.raport.ostrzezenie(f"pusta wartość w {{{{ {zrodlo} }}}} — brak danych albo literówka w nazwie pola",
                                                plik=f"{plik}:{linia}",
                                                naprawa="uzupełnij pole w data/ albo otocz fragment {% if … %}, albo użyj filtra domyslnie")
                    continue
                wyj.append(self._na_tekst(v, plik, linia))
            elif typ == "if":
                _, galezie, inaczej, linia = wezel
                for warunek, cialo in galezie:
                    if prawda(self.ocen(warunek, zakres, plik, linia)):
                        self._renderuj(cialo, zakres, wyj, plik)
                        break
                else:
                    self._renderuj(inaczej, zakres, wyj, plik)
            elif typ == "for":
                _, nazwa, w, cialo, inaczej, linia = wezel
                lista = self.ocen(w, zakres, plik, linia)
                if lista is BRAK or lista is None:
                    lista = []
                if isinstance(lista, dict):
                    lista = [{"klucz": k, "wartosc": v} for k, v in lista.items()]
                if not isinstance(lista, (list, tuple)):
                    raise BladSzablonu(f"{{% for %}} wymaga listy, jest {type(lista).__name__}", plik, linia)
                if not lista:
                    self._renderuj(inaczej, zakres, wyj, plik)
                    continue
                n = len(lista)
                for idx, element in enumerate(lista):
                    z = zakres.nowa({nazwa: element, "petla": {
                        "indeks": idx + 1, "indeks0": idx, "pierwszy": idx == 0, "ostatni": idx == n - 1, "dlugosc": n}})
                    self._renderuj(cialo, z, wyj, plik)
            elif typ == "set":
                _, nazwa, w, linia = wezel
                zakres.ustaw(nazwa, self.ocen(w, zakres, plik, linia))
            elif typ == "include":
                _, sciezka, parametry, linia = wezel
                lokalne = {k: self.ocen(v, zakres, plik, linia) for k, v in parametry.items()}
                self._include(sciezka, lokalne, zakres, wyj, plik, linia)
            elif typ == "sekcje":
                if self.srodowisko is None:
                    raise BladSzablonu("{% sekcje %} bez środowiska buildu", plik, wezel[1])
                for sekcja_id, lokalne in self.srodowisko.sekcje_strony():
                    self._include(f"sekcje/{sekcja_id}.html", lokalne, zakres, wyj, plik, wezel[1])

    def _include(self, sciezka, lokalne, zakres, wyj, plik, linia):
        if not self.istnieje(sciezka):
            raise BladSzablonu(f"{{% include %}}: nie ma pliku src/{sciezka}", plik, linia)
        sz = self.szablon(sciezka)
        if sciezka.startswith("sekcje/") and self.srodowisko is not None:
            sekcja_id = Path(sciezka).stem
            lokalne = {"tryb": "pelny", "limit": None, "bez_naglowka": False,
                       "sekcja": self.srodowisko.sekcja_info(sekcja_id), **lokalne}
            # hn = poziom nagłówków wewnątrz sekcji (h3 pod h2 sekcji; h2, gdy sekcja jest treścią podstrony z h1)
            lokalne.setdefault("hn", 2 if lokalne.get("bez_naglowka") else 3)
        z = zakres.nowa(lokalne)
        braki = self.niespelnione(sz.wymaga, z)
        if braki:
            nazwa = Path(sciezka).stem
            rodzaj = "sekcja" if sciezka.startswith("sekcje/") else "część"
            self.raport.ukryto(f"{rodzaj} „{nazwa}” (brak danych: {', '.join(braki)})")
            return
        self._renderuj(sz.ast, z, wyj, sz.plik)


# ----------------------------------------------------------------------------- filtry

def _pusty(v):
    return v is None or v is BRAK or v == ""


def _html(s: str) -> Markup:
    return Markup(html.escape(s))


def _lista(v):
    if _pusty(v):
        return []
    if not isinstance(v, (list, tuple)):
        raise ValueError("oczekiwano listy")
    return list(v)


def _srod(s: Silnik):
    if s.srodowisko is None:
        raise ValueError("ten filtr działa tylko w buildzie")
    return s.srodowisko


FILTRY = {
    "surowe": lambda s, v, a: Markup("" if _pusty(v) else str(v)),
    "tel": lambda s, v, a: Markup("") if _pusty(v) else _html(typo.tel(v, krajowy=(a == "krajowy"))),
    "tel_href": lambda s, v, a: Markup("") if _pusty(v) else _html(typo.tel_href(v)),
    "cena": lambda s, v, a: Markup("") if _pusty(v) else _html(typo.cena(v, a or "zł")),
    "data": lambda s, v, a: Markup("") if _pusty(v) else _html(typo.data_dluga(v)),
    "data_krotka": lambda s, v, a: Markup("") if _pusty(v) else _html(typo.data_krotka(v)),
    "data_iso": lambda s, v, a: Markup("") if _pusty(v) else _html(typo.data_iso(v)),
    "md": lambda s, v, a: Markup("") if _pusty(v) else Markup(typo.markdown(
        str(v), int(a or 2), getattr(s.srodowisko, "myslnik", "polpauza"), getattr(s.srodowisko, "link_md", None))),
    "md_plik": lambda s, v, a: Markup("") if _pusty(v) else Markup(typo.markdown(
        _srod(s).czytaj_md(str(v)), int(a or 2), _srod(s).myslnik, _srod(s).link_md)),
    # „<” → \u003c: w <script> nie zamknie znacznika (</script>) ani nie otworzy komentarza (<!--), JSON zostaje poprawny
    "json": lambda s, v, a: Markup(json.dumps(None if v is BRAK else v, ensure_ascii=False,
                                              separators=(",", ":")).replace("<", "\\u003c")),
    "url": lambda s, v, a: Markup("") if _pusty(v) else _html(_srod(s).url(str(v))),
    "mailto": lambda s, v, a: Markup("") if _pusty(v) else _html("mailto:" + str(v).strip()),
    "zasob": lambda s, v, a: Markup("") if _pusty(v) else _html(_srod(s).zasob(str(v))),
    "abs": lambda s, v, a: Markup("") if _pusty(v) else _html(_srod(s).abs(str(v))),
    "obraz": lambda s, v, a: Markup("") if _pusty(v) else Markup(_srod(s).obraz(str(v), a or "pol")),
    "slug": lambda s, v, a: "" if _pusty(v) else typo.slug(str(v)),
    "dlugosc": lambda s, v, a: 0 if _pusty(v) else len(v),
    "pierwsze": lambda s, v, a: _lista(v)[: int(a or 1)],
    "reszta": lambda s, v, a: _lista(v)[int(a or 1):],
    "domyslnie": lambda s, v, a: a if _pusty(v) else v,
    "polacz": lambda s, v, a: ("" if a is None else str(a)).join(str(x) for x in _lista(v)),
    "wersaliki_pierwsza": lambda s, v, a: "" if _pusty(v) else typo.wersaliki_pierwsza(str(v)),
    "liczba_mnoga": lambda s, v, a: typo.liczba_mnoga(0 if _pusty(v) else v, a or ""),
    "liczba": lambda s, v, a: Markup("") if _pusty(v) else _html(typo.liczba(v)),
    # pierwszy akapit pliku .md (bez nagłówków i list) — skrót na głównej, gdy cały tekst jest na podstronie
    "md_plik_poczatek": lambda s, v, a: Markup("") if _pusty(v) else Markup(typo.markdown(next(
        (b for b in re.split(r"\n\s*\n", _srod(s).czytaj_md(str(v)).strip())
         if b.strip() and not re.match(r"\s*(#|[-*]\s|\d+\.\s)", b)), ""), 2, _srod(s).myslnik, _srod(s).link_md)),
}
