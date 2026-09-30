#!/usr/bin/env python3
"""„Co zawiera strona” — spis wszystkiego, co ma strona zbudowana na SZABLONIE, i po co to firmie.

  python3 tools/co_zawiera.py                         → docs/CO-ZAWIERA-STRONA.md (wersja ogólna, do oferty)
  python3 tools/co_zawiera.py --klient przyklady/bimex → raport/CO-ZAWIERA-STRONA.md: co jest włączone u tego klienta
  python3 tools/co_zawiera.py --klient . --wyjscie raport/co-zawiera.md

Lista jest w tym pliku (LISTA niżej) i obejmuje wyłącznie funkcje, które istnieją w repozytorium. Kto dodaje funkcję
do silnika, dopisuje ją tutaj i generuje plik od nowa. Wersja dla klienta buduje stronę (build --szybko do katalogu
tymczasowego) i zaznacza, które moduły są aktywne; moduły bez danych opisuje jako „do włączenia”.
Wersję klienta zapisujemy w raport/, bo docs/ należy do silnika (tools/aktualizuj.py go nadpisuje).
Tylko biblioteka standardowa Pythona ≥ 3.10.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent

GRUPY = [
    ("tresc", "Treść i sekcje"),
    ("wyglad", "Wygląd"),
    ("szybkosc", "Szybkość"),
    ("seo", "Widoczność w Google (SEO)"),
    ("prawo", "Dostępność i prawo"),
    ("bezpieczenstwo", "Bezpieczeństwo"),
    ("prywatnosc", "Prywatność"),
    ("utrzymanie", "Utrzymanie i rozwój"),
]

# (grupa, co, dlaczego to ważne dla firmy, warunek)
# warunek: None = zawsze; "sekcja:<id>" = sekcja widoczna; "strona:/x" = podstrona powstała;
#          "funkcja:<klucz>=<wartość>" albo "funkcja:<klucz>" (prawda) = ustawienie w data/firma.json → funkcje;
#          "firma:<ścieżka>" = pole w data/firma.json nie jest puste
LISTA = [
    # ------------------------------------------------------------------ treść
    ("tresc", "Pierwszy ekran „kto, co, gdzie”: nagłówek z usługą i miejscowością, jedno zdanie konkretu, własne zdjęcie z podpisem i przycisk „Zadzwoń”",
     "Klient w kilka sekund wie, że trafił do właściwej firmy, i może od razu zadzwonić.", None),
    ("tresc", "Na telefonie nazwa, miejscowość, telefon i dzisiejsze godziny widoczne bez przewijania",
     "Większość klientów lokalnych szuka firmy na telefonie i chce tylko zadzwonić albo dojechać.", None),
    ("tresc", "Status „Otwarte do 15:00 / Zamknięte, otwieramy jutro o 7:00” liczony w czasie polskim, z podświetleniem dzisiejszego dnia",
     "Odpowiada na najczęstsze pytanie przed wizytą — także wtedy, gdy ktoś ogląda stronę z zagranicy.", "firma:godziny"),
    ("tresc", "Godziny otwarcia z kilkoma przedziałami, osobnymi godzinami (np. kuchnia, wytwórnia) i wyjątkami świątecznymi",
     "Jedno źródło zasila tabelę, status i dane dla Google, więc godziny nigdy się nie rozjadą.", "firma:godziny"),
    ("tresc", "Przypomnienie w buildzie o godzinach na święta (45 dni wcześniej, z Wigilią jako dniem wolnym od 2025 r.)",
     "Nieaktualne godziny w święta to najczęstsza skarga klientów lokali.", "firma:godziny"),
    ("tresc", "Ogłoszenie z datą ważności („24–26.12 nieczynne”), które samo znika po terminie",
     "Pilna informacja jest na górze strony tylko wtedy, gdy obowiązuje.", "sekcja:ogloszenie"),
    ("tresc", "Oferta: usługi z zakresem prac, czasem wykonania i ceną albo widełkami; własne zdjęcia zamiast ikon",
     "Klient porównuje konkrety, a nie hasła — konkret skraca rozmowę telefoniczną.", "sekcja:oferta"),
    ("tresc", "Podstrony usług — tylko gdy jest dość treści (opis, zdjęcie, cena lub zakres)",
     "Każda podstrona odpowiada na konkretne wyszukiwanie w Google, bez pustych stron „na miasto”.", "strona:/oferta/"),
    ("tresc", "Cennik w HTML: ceny brutto dla konsumentów (netto tylko dla firm, wyraźnie opisane), data cennika, PDF jako dodatek",
     "Ceny na stronie odsiewają niepasujące zapytania i są zgodne z ustawą o informowaniu o cenach.", "sekcja:cennik"),
    ("tresc", "Karta dań: ceny (albo wyraźne „ceny w lokalu”), porcje, oznaczenia wege i ostre, alergeny (14 grup UE), data karty, wersja do druku",
     "Gość sprawdza menu przed wizytą; alergeny są wymagane przepisami UE.", "sekcja:menu"),
    ("tresc", "Katalog produktów z parametrami, zdjęciami i filtrem kategorii (działa też bez JavaScriptu)",
     "Hurtownik albo klient od razu znajduje model i parametry, zamiast dzwonić o katalog.", "sekcja:produkty"),
    ("tresc", "Realizacje: miejsce, rok, jedna liczba (km, m²), zdjęcia, filtr kategorii i tryb „klient prywatny”",
     "Sprawdzalne realizacje przekonują bardziej niż zapewnienia o doświadczeniu.", "sekcja:realizacje"),
    ("tresc", "Tabela zamówień publicznych: zadanie, zamawiający, rok, źródło (Biuletyn Zamówień Publicznych)",
     "Dla firm budowlanych to najmocniejsza referencja — każdy wiersz można sprawdzić.", "sekcja:przetargi"),
    ("tresc", "Galeria zdjęć z podpisami", "Pokazuje prawdziwe miejsce i prace firmy.", "sekcja:galeria"),
    ("tresc", "Przebieg współpracy jako numerowana lista kroków z terminem lub rezultatem każdego kroku",
     "Klient wie, co go czeka i ile to potrwa, zanim zadzwoni.", "sekcja:proces"),
    ("tresc", "Zasady: płatności, gwarancja, zadatek, ważność wyceny, rezerwacje, dostawa",
     "Odpowiada na pytania, które inaczej padają przy każdym zapytaniu.", "sekcja:zasady"),
    ("tresc", "Pytania i odpowiedzi — prawdziwe pytania klientów, rozwijane",
     "Mniej telefonów z tymi samymi pytaniami; treść pomaga w wyszukiwarce.", "sekcja:faq"),
    ("tresc", "O firmie: historia, zdjęcie i fakty (rok założenia, sprzęt, uprawnienia); dłuższy tekst na podstronie /o-firmie",
     "Konkretna historia buduje zaufanie lepiej niż slogan.", "sekcja:o_firmie"),
    ("tresc", "Zespół: imię, rola, jeden fakt; zdjęcie tylko za zgodą osoby, właściciel pierwszy",
     "Klient wie, z kim rozmawia; zgoda na wizerunek chroni firmę.", "sekcja:zespol"),
    ("tresc", "Liczby z datą i źródłem (blok ukryty, gdy jest mniej niż dwie)",
     "Każda liczba jest prawdziwa i sprawdzalna — bez „500+ zadowolonych klientów”.", "sekcja:liczby"),
    ("tresc", "Opinie: ocena zbiorcza z linkiem do źródła, do 3 cytatów i zdanie, jak firma weryfikuje opinie",
     "Wiarygodne opinie sprzedają, a zdanie o weryfikacji jest wymagane przez dyrektywę Omnibus.", "sekcja:opinie"),
    ("tresc", "Certyfikaty i uprawnienia z numerem, wydawcą, rokiem i skanem; wygasłe znikają same",
     "Zamawiający i klienci biznesowi sprawdzają uprawnienia przed zleceniem.", "sekcja:certyfikaty"),
    ("tresc", "Aktualności z własnymi adresami",
     "Świeże wpisy pokazują, że firma działa, i dają Google nowe treści.", "strona:/aktualnosci"),
    ("tresc", "Kanał RSS aktualności", "Stali klienci i portale lokalne dostają nowe wpisy automatycznie.",
     "funkcja:rss"),
    ("tresc", "Oferty pracy z terminem ważności (po terminie znikają) i danymi dla Google Jobs",
     "Ogłoszenie trafia do wyszukiwarki ofert pracy bez płatnych portali.", "sekcja:kariera"),
    ("tresc", "Pliki do pobrania z typem, rozmiarem i liczbą stron („PDF, 240 KB, 2 strony”)",
     "Klient wie, co pobiera, zanim kliknie — szczególnie na telefonie.", "sekcja:do_pobrania"),
    ("tresc", "Współpraca dla firm (warunki hurtowe, dystrybucja)", "Partnerzy B2B znajdują warunki bez pytania mailem.",
     "sekcja:wspolpraca"),
    ("tresc", "Gdzie kupić: punkty sprzedaży pogrupowane według województw",
     "Klient producenta od razu znajduje najbliższy sklep.", "sekcja:gdzie_kupic"),
    ("tresc", "Kontakt: klikalny telefon i e-mail, adres, telefony działów (kto, w jakiej sprawie), dojazd i dostępność lokalu",
     "Klient dzwoni od razu pod właściwy numer, a nie do centrali.", "sekcja:kontakt"),
    ("tresc", "Przycisk „Wyznacz trasę” prowadzący do nawigacji po współrzędnych wejścia",
     "Jedno dotknięcie na telefonie uruchamia nawigację do właściwej bramy, nie do środka działki.", "firma:kontakt.geo"),
    ("tresc", "Formularz zapytania (3–4 pola, podpowiedzi przeglądarki, błędy przy polach, także bez JavaScriptu — strona z opisem, co poprawić); bez serwera — gotowa wiadomość e-mail",
     "Zapytanie wysyła się w minutę także z telefonu i trafia prosto do skrzynki firmy.", "funkcja:formularz"),
    ("tresc", "Pasek „Zadzwoń / Wyznacz trasę” na telefonie, który pokazuje się, gdy przycisków nie widać na ekranie",
     "Najważniejsza akcja jest zawsze pod kciukiem i nie dubluje przycisków z pierwszego ekranu.", None),
    ("tresc", "Stopka z danymi rejestrowymi według formy prawnej (nazwa, adres, KRS i sąd, NIP, REGON, kapitał albo właściciel JDG)",
     "Wymóg prawa (m.in. art. 206 KSH) i sygnał, że firma jest prawdziwa.", None),
    ("tresc", "Strony 404, „Dziękujemy” i „Błąd wysyłki” z telefonem i przydatnymi linkami",
     "Zepsuty link nie gubi klienta — zawsze ma drogę do kontaktu.", None),
    ("tresc", "Sekcje bez prawdziwych danych nie powstają; niepewne fakty trafiają na listę „Do potwierdzenia”",
     "Na stronie nie ma zmyślonych liczb, cen ani tekstów zastępczych.", None),
    # ------------------------------------------------------------------ wygląd
    ("wyglad", "Kolory z logo i szyldu firmy, zamienione na paletę z kontrastem sprawdzanym przy każdym buildzie",
     "Strona wygląda jak ta firma, a nie jak szablon, i jest czytelna dla każdego.", None),
    ("wyglad", "Dwa kroje pisma z biblioteki szablonu dobrane do branży, z polskimi znakami",
     "Spójny, profesjonalny wygląd bez „typowego wyglądu stron z AI”.", None),
    ("wyglad", "Polska typografia automatycznie: twarde spacje po „w”, „z”, między liczbą a jednostką, półpauzy, „polskie cudzysłowy”",
     "Tekst wygląda na złożony przez człowieka, nie przez maszynę.", None),
    ("wyglad", "Układ dopasowany do treści: tabele, listy, duże własne zdjęcia, cienkie linie zamiast kart z cieniem",
     "Strona jest rzeczowa i różni się od tysięcy stron z tego samego szablonu.", None),
    ("wyglad", "Kontrola „AI slop” w każdym buildzie: frazesy („kompleksowe usługi”), emoji, gradienty, liczniki „500+”",
     "Tekst i wygląd nie zdradzają automatu — klient czyta fakty.", None),
    ("wyglad", "Zdjęcia kadrowane według punktu ostrości, z osobnym kadrem na telefon",
     "Najważniejszy fragment zdjęcia widać na każdym ekranie.", None),
    ("wyglad", "Wersja do druku karty, cennika, godzin i dojazdu", "Klient drukuje menu czy dojazd bez menu strony i reklam.", None),
    ("wyglad", "Jedno subtelne wejście pierwszego ekranu (wyłączone dla osób, które ograniczają animacje)",
     "Odrobina ruchu bez spowalniania strony i bez chowania nagłówka.", "funkcja:animacje=wejscie"),
    # ------------------------------------------------------------------ szybkość
    ("szybkosc", "Gotowe pliki HTML bez WordPressa, wtyczek i bibliotek JavaScript; strona działa też bez JavaScriptu",
     "Szybkie ładowanie na słabym zasięgu i nic do aktualizowania co tydzień.", None),
    ("szybkosc", "Zdjęcia w AVIF, WebP i JPEG w kilku rozmiarach; niżej na stronie ładowane dopiero przy przewijaniu",
     "Telefon pobiera tylko to, co pokazuje — mniej danych, szybszy pierwszy ekran.", None),
    ("szybkosc", "Fonty z własnego serwera z zamiennikiem o tych samych wymiarach",
     "Tekst nie „skacze” przy ładowaniu i nie czeka na obcy serwer.", None),
    ("szybkosc", "Pliki CSS i JS z wersją w adresie i rocznym czasem w pamięci przeglądarki",
     "Powracający klient ładuje stronę natychmiast, a po zmianie od razu widzi nową wersję.", None),
    ("szybkosc", "Limity wagi sprawdzane przy każdym buildzie (zdjęcia, CSS, JS, HTML)",
     "Strona nie zwalnia z czasem, gdy przybywa treści.", None),
    ("szybkosc", "Hosting na sieci Cloudflare (serwery blisko odwiedzającego)", "Szybko z każdego miejsca, bez opłat za serwer.",
     "funkcja:hosting=cloudflare"),
    # ------------------------------------------------------------------ SEO
    ("seo", "Tytuł karty „usługa miejscowość – firma” i opis inny na każdej podstronie",
     "Google pokazuje właściwą podstronę na właściwe zapytanie.", None),
    ("seo", "Dane strukturalne JSON-LD: rodzaj firmy, adres, współrzędne, telefon, godziny, NIP, profile społecznościowe, okruszki",
     "Google rozumie, czym jest firma i gdzie jest — lepsza widoczność w wynikach i w Mapach.", None),
    ("seo", "Dane strukturalne treści: karta dań, produkty z ceną, usługi, oferty pracy, artykuły — tylko przy prawdziwych danych; bez własnych „gwiazdek”",
     "Szansa na bogate wyniki bez ryzyka kary za zawyżone oceny.", None),
    ("seo", "Podgląd przy udostępnianiu (Facebook, Messenger, WhatsApp): zdjęcie 1200 × 630 z pełnym adresem",
     "Link wysłany znajomemu wygląda porządnie i zachęca do kliknięcia.", None),
    ("seo", "sitemap.xml z datami zmian, robots.txt z decyzją o botach AI, adres kanoniczny każdej strony",
     "Wyszukiwarki szybciej znajdują nowe treści i nie dublują stron.", None),
    ("seo", "Jeden nagłówek h1 i poprawna kolejność nagłówków, opisowe linki (nigdy „Czytaj więcej”)",
     "Wyszukiwarka i czytnik ekranu rozumieją strukturę strony.", None),
    ("seo", "Adresy bez „.html” i przekierowania starych adresów (_redirects)",
     "Linki ze starej strony i z Google dalej działają po zmianie strony.", None),
    ("seo", "Pytania i odpowiedzi jako FAQPage (opcjonalnie)", "Dodatkowa szansa na widoczność pytań w wynikach.",
     "funkcja:faq_schema"),
    ("seo", "Nocna przebudowa strony (ogłoszenia, święta, rok w stopce zawsze aktualne) — po ustawieniu Deploy Hook w Cloudflare (docs/CLOUDFLARE.md)",
     "Treść zależna od daty nie starzeje się, nawet gdy nikt nic nie zmienia.", "funkcja:hosting=cloudflare"),
    # ------------------------------------------------------------------ dostępność i prawo
    ("prawo", "Dostępność WCAG 2.2 AA: link „Przejdź do treści”, widoczny fokus, kontrast, duże cele dotyku, tryb wysokiego kontrastu, ograniczenie animacji",
     "Stronę obsłuży każdy klient, także starszy i słabowidzący; mniejsze ryzyko prawne.", None),
    ("prawo", "Sprawdzenie automatyczne axe na każdej stronie przed oddaniem (cel: 0 problemów)",
     "Dostępność jest zmierzona, a nie obiecana.", None),
    ("prawo", "Polityka prywatności napisana według tego, co strona naprawdę robi (hosting, formularz, mapa, statystyki)",
     "Zgodność z RODO bez kopiowania cudzych regulaminów.", None),
    ("prawo", "Klauzula informacyjna pod formularzem, bez zbędnego obowiązkowego „checkboxa” zgody",
     "Mniej porzuconych formularzy, a obowiązek informacyjny RODO spełniony.", "funkcja:formularz"),
    ("prawo", "Strona z informacją o dostępności", "Dla firm, które muszą ją mieć według ustawy o dostępności.",
     "funkcja:strona_dostepnosci"),
    ("prawo", "Zdjęcia z zapisanym źródłem, autorem i zgodą osób na wizerunek; bez zdjęć stockowych i obrazów z AI udających firmę",
     "Brak ryzyka roszczeń autorów i osób na zdjęciach.", None),
    # ------------------------------------------------------------------ bezpieczeństwo
    ("bezpieczenstwo", "Nagłówki bezpieczeństwa: ścisła polityka treści (CSP), HSTS, ochrona przed osadzaniem strony w ramce",
     "Trudniej wstrzyknąć na stronę obcy skrypt albo podszyć się pod nią.", "funkcja:hosting=cloudflare"),
    ("bezpieczenstwo", "Formularz przez własny Worker: limit wysyłek z adresu IP, pole-pułapka, minimalny czas wypełnienia (niezależny od zegara w telefonie), sprawdzenie pochodzenia, limit rozmiaru",
     "Spam nie zasypuje skrzynki, a formularz działa bez CAPTCHA.", "funkcja:formularz.tryb=worker"),
    ("bezpieczenstwo", "Adres roboczy i panel ukryte przed wyszukiwarkami; plik security.txt z kontaktem",
     "Wersja testowa nie konkuruje w Google z właściwą stroną.", None),
    ("bezpieczenstwo", "Klucze i hasła tylko w ustawieniach Cloudflare, nigdy w repozytorium",
     "Wyciek kodu nie oznacza wycieku dostępu do poczty czy konta.", None),
    ("bezpieczenstwo", "Kontrola, czy Cloudflare nie wstrzykuje skryptów psujących stronę (np. ukrywanie e-maili)",
     "Strona na serwerze jest taka sama jak sprawdzona przed publikacją.", None),
    # ------------------------------------------------------------------ prywatność
    ("prywatnosc", "Bez ciasteczek i bez obcych skryptów przy wejściu (0 zapytań do Google, Facebooka itp.)",
     "Nie potrzeba banera cookies — klient od razu widzi treść.", None),
    ("prywatnosc", "Mapa ładowana dopiero po kliknięciu (OpenStreetMap), a domyślnie tylko link do trasy",
     "Dane odwiedzających nie trafiają do dostawcy mapy bez ich decyzji.", None),
    ("prywatnosc", "Statystyki Cloudflare bez ciasteczek (opcjonalnie)", "Firma wie, ile osób odwiedza stronę, bez śledzenia ich.",
     "funkcja:statystyki_cf_token"),
    ("prywatnosc", "Zdjęcia bez metadanych (EXIF, GPS)", "Ze zdjęć nie da się odczytać, gdzie i czym zostały zrobione.", None),
    # ------------------------------------------------------------------ utrzymanie
    ("utrzymanie", "Cała treść w kilku plikach danych (data/) — jedna zmiana poprawia nagłówek, stopkę, kontakt, Google i politykę prywatności",
     "Zmiana telefonu czy godzin to jedna poprawka, a nie szukanie po wszystkich podstronach.", None),
    ("utrzymanie", "Kontrola przy każdej publikacji z komunikatami po polsku (plik, pole, jak naprawić); błąd zatrzymuje publikację",
     "Literówka w danych nie trafi na stronę.", None),
    ("utrzymanie", "Publikacja automatyczna: zapis zmian w GitHubie → Cloudflare buduje i wdraża stronę",
     "Bez FTP i ręcznego wgrywania plików.", "funkcja:hosting=cloudflare"),
    ("utrzymanie", "Karta jakości: zmierzone wyniki Lighthouse, dostępności, wagi strony, ciasteczek i obcych serwerów",
     "Firma dostaje dowód jakości w liczbach, a nie zapewnienia.", None),
    ("utrzymanie", "Aktualizacje z nowszych wersji szablonu (poprawki, nowe przepisy) bez ruszania treści firmy",
     "Strona nie starzeje się technicznie po oddaniu.", None),
    ("utrzymanie", "Lista „Do potwierdzenia z właścicielem” generowana z danych", "Nic niepewnego nie zostaje przeoczone.", None),
    ("utrzymanie", "Instrukcja dla asystenta AI i procedura krok po kroku", "Kolejne zmiany może bezpiecznie zrobić asystent AI według tych samych reguł.", None),
]


def stan_klienta(klient: Path) -> dict:
    """Buduje stronę (--szybko, katalog tymczasowy) i zbiera: strony, ukryte sekcje, dane firmy."""
    firma = json.loads((klient / "data" / "firma.json").read_text(encoding="utf-8"))
    tresc = json.loads((klient / "data" / "tresc.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="szablon-co-zawiera-") as tmp:
        w = subprocess.run([sys.executable, str(KORZEN / "tools" / "build.py"), "--szybko", "--json", "--klient", str(klient),
                            "--wyjscie", str(Path(tmp) / "dist")], capture_output=True, text=True, cwd=KORZEN)
    try:
        wynik = json.loads(w.stdout)
    except ValueError:
        raise SystemExit("Build nie zwrócił wyniku — najpierw: python3 tools/build.py --klient " + str(klient))
    if w.returncode != 0:
        raise SystemExit("Build ma błędy — popraw je (python3 tools/build.py --klient ...), potem generuj spis.")
    ukryte = set()
    for k in wynik["komunikaty"]:
        if k["poziom"] in ("UKRYTO", "INFO") and "sekcja „" in k["tresc"]:
            ukryte.add(k["tresc"].split("sekcja „", 1)[1].split("”", 1)[0])
    return {"firma": firma, "tresc": tresc, "strony": wynik["wynik"]["strony"], "ukryte": ukryte}


def pole(d, sciezka: str):
    for cz in sciezka.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(cz)
    return d


def aktywne(warunek: str | None, s: dict) -> bool:
    if warunek is None:
        return True
    rodzaj, _, reszta = warunek.partition(":")
    if rodzaj == "sekcja":
        dane = True if reszta in ("hero", "kontakt") else s["tresc"].get(reszta)
        return bool(dane) and reszta not in s["ukryte"]
    if rodzaj == "strona":
        return any(x == reszta or (reszta.endswith("/") and x.startswith(reszta)) for x in s["strony"])
    if rodzaj == "firma":
        return bool(pole(s["firma"], reszta))
    if rodzaj == "funkcja":
        klucz, _, wartosc = reszta.partition("=")
        v = pole(s["firma"].get("funkcje") or {}, klucz)
        return (str(v) == wartosc) if wartosc else bool(v)
    return True


def dokument(s: dict | None) -> str:
    w = []
    if s is None:
        w += ["# Co zawiera strona zbudowana na SZABLONIE", "",
              "Spis dla właściciela firmy: co dostaje razem ze stroną i po co mu to. Każda pozycja istnieje w szablonie —",
              "część modułów pojawia się tylko wtedy, gdy firma ma na nie prawdziwe dane (np. realizacje, opinie, godziny).",
              "Wersję dla konkretnej firmy, z zaznaczeniem, co jest włączone: `python3 tools/co_zawiera.py --klient .`", ""]
    else:
        nazwa = pole(s["firma"], "firma.nazwa") or "firma"
        w += [f"# Co zawiera strona {nazwa}", "",
              "**Jest** — działa na stronie. **Do włączenia** — szablon to potrafi; wystarczy dostarczyć prawdziwe dane",
              "(np. zdjęcia realizacji, godziny, opinie z linkiem) albo włączyć ustawienie.", "",
              f"Strony ({len(s['strony'])}): " + ", ".join(s["strony"]), ""]
    for klucz, tytul in GRUPY:
        w += [f"## {tytul}", ""]
        for grupa, co, dlaczego, war in LISTA:
            if grupa != klucz:
                continue
            if s is None:
                dopisek = " *(gdy są dane)*" if war and war.startswith(("sekcja:", "strona:", "firma:")) else (
                    " *(opcja)*" if war else "")
                w.append(f"- **{co}**{dopisek} — {dlaczego}")
            else:
                znak = "Jest" if aktywne(war, s) else "Do włączenia"
                w.append(f"- [{znak}] **{co}** — {dlaczego}")
        w.append("")
    w += ["---", "", "Wygenerowano: `python3 tools/co_zawiera.py`. Zmierzone wyniki konkretnej strony: `raport/KARTA-JAKOSCI.md`"
          " (`bash tools/sprawdz.sh`)."]
    return "\n".join(w) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Spis funkcji strony dla klienta (docs/CO-ZAWIERA-STRONA.md).")
    p.add_argument("--klient", help="katalog klienta — wersja z zaznaczeniem, co jest włączone")
    p.add_argument("--wyjscie", help="plik wyniku (domyślnie docs/CO-ZAWIERA-STRONA.md albo raport/CO-ZAWIERA-STRONA.md)")
    a = p.parse_args()
    if a.klient:
        klient = Path(a.klient)
        klient = klient if klient.is_absolute() or klient.exists() else KORZEN / klient
        tekst = dokument(stan_klienta(klient.resolve()))
        cel = Path(a.wyjscie) if a.wyjscie else KORZEN / "raport" / "CO-ZAWIERA-STRONA.md"
    else:
        tekst = dokument(None)
        cel = Path(a.wyjscie) if a.wyjscie else KORZEN / "docs" / "CO-ZAWIERA-STRONA.md"
    cel.parent.mkdir(parents=True, exist_ok=True)
    cel.write_text(tekst, encoding="utf-8")
    print(f"Zapisano: {cel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
