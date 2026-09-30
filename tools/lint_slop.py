#!/usr/bin/env python3
"""Linter „AI slop”: frazesy, wzorce szablonowego wyglądu i braki warsztatu w zbudowanej stronie (KONTRAKT §7.5, §10).

Sprawdza:
  * dist/ — wszystkie *.html (widoczny tekst, alt, title, meta) i *.css (także <style>),
  * data/ — napisy z *.json (bez notatek: zrodla, do_potwierdzenia…) i akapity z data/**/*.md,
  * markę: kolor i kroje z szablonu albo skopiowane z przykładu (MARKA-DOMYSLNA).

Poziomy:
  P0  błąd zawsze (kod 2) — laik powie „to z AI”/„szablon”: frazesy, emoji, gradient, zdjęcia stockowe, zaślepki;
  P1  ostrzeżenie; w --produkcja błąd (kod 1), chyba że zwolnione w data/slop-ok.json;
  P2  informacja (warsztat: sierotki, myślniki, akapit bez konkretu).

Zwolnienia (tylko P1 i P2 — P0 nie da się zwolnić, trzeba poprawić treść albo regułę):
  data/slop-ok.json:  [ {"id": "V-NUMERY-01", "powod": "kroki betonowania to prawdziwa kolejność", "gdzie": "realizacje.html"} ]
  „gdzie” (opcjonalnie) = fragment ścieżki pliku, pola danych albo cytowanego tekstu; bez „gdzie” — cała strona.
  W CSS także komentarz w wierszu reguły albo tuż nad nią:  /* slop-ok: V-SZKLO nagłówek nad zdjęciem */

Użycie:
  python3 tools/lint_slop.py dist/ data/                    raport po polsku
  python3 tools/lint_slop.py dist/ data/ --produkcja        P1 bez zwolnienia = kod 1
  python3 tools/lint_slop.py dist/ data/ --json             wyniki jako JSON (pętla AI: popraw → uruchom ponownie)
  python3 tools/lint_slop.py strona.html --min=P1           tylko P0 i P1
  python3 tools/lint_slop.py --reguly                       katalog reguł (id, poziom, co zamiast)

Kod wyjścia: 2 = jest P0, 1 = P1 w --produkcja, 0 = w porządku. Ostatni wiersz raportu to podsumowanie.
Tylko biblioteka standardowa Pythona ≥ 3.10. Reguły: badanie „AI slop” (§4–§9), prototyp lint_slop_proto.py;
część reguł wizualnych za avoid-ai-design/detect.mjs (MIT) i unslop_text_scan.py (MIT).
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
POZIOMY = ("P0", "P1", "P2")
KOLEJNOSC = {p: i for i, p in enumerate(POZIOMY)}
L = "a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ"            # litery polskie (klasy znaków)
UP = "A-ZĄĆĘŁŃÓŚŹŻ"
POMIN_KATALOGI = {".git", "node_modules", "fonts", "admin", "vendor", "__pycache__", ".well-known"}

# --------------------------------------------------------------------------------------------- reguły tekstu
# (id, poziom, zakres, wzorce, co zamiast, wyjątek_z_konkretem)
#   zakres: tekst — każdy tekst (akapity, nagłówki, alt, meta); naglowek — h1–h3 i <title>; cta — cały tekst linku/przycisku
#   wyjątek_z_konkretem: gdy w tym samym zdaniu jest cyfra, jednostka albo nazwa własna — P1 → P2, P2 → pomiń
REGULY_TEKSTU = [
    ("PL-OPENER", "P0", "tekst", [
        r"\bw dzisiejszych czasach\b", r"\bw dzisiejszym\s+(?:\w+\s+){0,3}świecie\b",
        r"\bw erze (?:cyfrowej|AI|internetu|technologii|smartfonów)\b", r"\bw dobie (?:cyfryzacji|internetu|AI|sztucznej)\b",
        r"\bnie sposób nie zauważyć\b", r"\bczy zastanawiał(?:eś|aś|eś się|aś się)\b", r"\bw obliczu (?:wyzwań|dynamicznych)\b",
        r"\bw dzisiejszym krajobrazie\b", r"\bwiele osób (?:zadaje sobie pytanie|zastanawia się)\b",
        r"\bszybko zmieniając\w+ się\s+(?:świec|rynk|rzeczywistoś)\w*"],
     "Skreśl zdanie wstępne. Zacznij od faktu: co, gdzie, od kiedy, za ile.", False),
    ("PL-FRAZES", "P0", "tekst", [
        r"\bkompleksow\w{1,4}\s+(?:usług\w*|rozwiąza\w*|obsług\w*|ofert\w*|podejści\w*|realizacj\w*|wsparci\w*)",
        r"\bkompleksowo\b", r"\bindywidualn\w{1,3}\s+podejści\w*", r"\bpodchodzimy indywidualnie\b",
        r"\b(?:wieloletni|bogat|ogromn|długoletni|wieloletnim|wieloletniemu)\w{0,3}\s+doświadczeni\w*",
        r"\bnajwyższ\w{1,3}\s+(?:jakoś\w*|klas\w*|standard\w*|poziom\w*)", r"\bna najwyższym poziomie\b",
        r"\bszyt\w{1,3}\s+na\s+miarę\b", r"\bz pasją\b", r"\bz pasji\b", r"\bnasz\w{0,2}\s+pasj\w+\b",
        r"\bpasj\w+\s+(?:i|oraz)\s+(?:zaangażowani|profesjonaliz|doświadczeni)\w*",
        r"\bzesp\w{1,4}\s+(?:doświadczonych|wykwalifikowanych|wysoko wykwalifikowanych|profesjonalnych)\s+"
        r"(?:specjalistów|fachowców|ekspertów|pracowników|profesjonalistów)\b",
        r"\bwykwalifikowan\w+\s+kadr\w+", r"\b(?:twoje|twoich|państwa)\s+potrzeby\s+(?:są|to)\b",
        r"\bklient\w*\s+(?:jest|są)\s+dla\s+nas\s+najważniejs", r"\b(?:satysfakcj|zadowoleni)\w*\s+klient\w*\s+(?:to|jest)\s+(?:nasz|dla nas)",
        r"\b100\s?%\s+satysfakcji\b", r"\bstawiamy na (?:jakość|klient|profesjonaliz|zadowoleni)\w*",
        r"\bdbałoś\w+\s+o\s+(?:każdy|najmniejsz)\w*\s+(?:detal|szczeg)\w*", r"\blider\w*\s+(?:w branży|na rynku|rynku)\b",
        r"\bdynamicznie rozwijając\w+\s+się\b", r"\bwychodzimy naprzeciw\b",
        r"\bspełni\w*\s+oczekiwania\s+(?:nawet\s+)?(?:najbardziej\s+)?wymagając", r"\bgwarancj\w+\s+(?:jakości|satysfakcji|zadowolenia)\b",
        r"\bzespół doświadczonych specjalistów\b", r"\bprofesjonalizm\w*\s+i\s+(?:rzetelnoś|zaangażowa|terminowoś)\w*"],
     "Zamień na fakt, który da się sprawdzić: liczba, rok, nazwa, miejsce, cena, termin, nazwisko.", False),
    ("PL-FRAZES-LEKKIE", "P1", "tekst", [
        r"\bprofesjonaliz\w+", r"\bprofesjonaln\w+\s+(?:obsług|podejści|usług|zesp|kadr|doradztw)\w*",
        r"\b(?:konkurencyjn|atrakcyjn|przystępn)\w+\s+cen\w*", r"\bwysokiej jakości\b",
        r"\bszerok\w+\s+(?:zakres\w*|wachlarz\w*|gam\w*)\s+(?:usług|produktów|możliwości)\b", r"\bbogat\w+\s+ofert\w*",
        r"\b(?:innowacyjn|nowoczesn)\w+\s+rozwiąza\w*", r"\b(?:sprawdzon|zaufan|rzeteln|solidn)\w+\s+partner\w*",
        r"\b(?:dopasowan|dostosowan|dopasuj|dostosuj|dopasujemy|dostosujemy)\w*\s+do\s+(?:twoich|państwa|indywidualnych|twoje)\s+"
        r"(?:potrzeb|oczekiwań|wymagań)\w*", r"\bdługoletni\w*\s+tradycj\w+"],
     "Dopisz dowód w tym samym zdaniu (liczba, norma, nazwa) albo skreśl przymiotnik.", True),
    ("PL-FILLER", "P1", "tekst", [
        r"\bwarto (?:zauważyć|podkreślić|zaznaczyć|wspomnieć|pamiętać|zwrócić uwagę)\b",
        r"\bnależy (?:zauważyć|podkreślić|mieć na uwadze)\b", r"\bmając na uwadze\b", r"\bw związku z powyższym\b",
        r"\bjak wspomniano\b", r"\bco (?:więcej|ciekawe)\b",
        r"(?:^|[.!?]\s+)(?:Ponadto|Dodatkowo|Niemniej jednak|Podsumowując|Reasumując|Konkludując|Na zakończenie)\b",
        r"\bodgrywa\w*\s+kluczow\w+ rolę\b", r"\bkluczow\w{1,3}\s+(?:rol\w*|znaczeni\w*|aspekt\w*|czynnik\w*)",
        r"\bw praktyce oznacza to\b"],
     "Skreśl łącznik. Zdanie bez niego jest krótsze i mówi to samo.", False),
    ("PL-HYPE", "P1", "tekst", [
        r"\bprzenie\w+\s+(?:\w+\s+){0,3}na\s+(?:wyższy|nowy|kolejny)\s+poziom\b", r"\bna (?:zupełnie )?nowy poziom\b",
        r"\b(?:uwolnij|odblokuj|uwolnić|odblokować|wyzwól|wyzwolić)\w*\s+(?:\w+\s+)?potencjał\w*",
        r"\bzrewolucjoniz\w+", r"\brewolucyjn\w+", r"\bprzełomow\w+", r"\bholistyczn\w+", r"\bsynergi\w+", r"\bekosystem\w*",
        r"\btransformacyjn\w+", r"\bbezszwow\w+", r"\bbezkonkurencyjn\w+", r"\bniezrównan\w+",
        r"\bpodróż\w*\s+(?:kulinarn|przez|w świat|smaków)\w*", r"\buczt\w+\s+dla\s+(?:podniebienia|zmysłów|oka)\b",
        r"\bw (?:samym )?sercu\s+(?-i:[" + UP + r"])\w+", r"\bniepowtarzaln\w+\s+(?:klimat|atmosfer|smak|charakter|styl)\w*",
        r"\bwyjątkow\w+\s+(?:atmosfer|klimat|miejsc|doświadcz|smak)\w*",
        r"\btradycj\w+\s+(?:i|z)\s+nowoczesnoś\w+", r"\bpołączeni\w+\s+tradycji\s+(?:i|z)\s+nowoczesnoś\w+",
        r"\bsmak\w*,?\s+któr\w+\s+(?:zachwyca|uwodzi|pokochasz|zapamiętasz)\b", r"\brozpływa\w*\s+się\s+w\s+ustach\b",
        r"\bzanurz\w*\s+się\b", r"\bodkryj\s+(?:świat|smak|magi|nasz|wyjątkow|sekret)\w*", r"\bmagi\w+\s+(?:smaku|miejsca|chwil)\w*",
        r"^\s*(?:Odkryj|Doświadcz|Poczuj|Zanurz się)\b"],
     "Pokaż rzecz zamiast przymiotnika: nazwa dania i cena, model i wymiar, maszyna i rok, dostawca i miejscowość.", False),
    ("PL-HYPE-SLOWO", "P2", "tekst", [r"\binnowacyjn\w+", r"\bunikaln\w+", r"\bbezproblemow\w+", r"\bwyjątkow\w+"],
     "Pospolite słowo reklamy; bez konkretu obok brzmi jak szablon.", True),
    ("PL-KALKA", "P1", "tekst", [
        r"\bdedykowan\w+", r"\badres\w+\s+(?:potrzeb|problem|wyzwa)\w*", r"\bdostarcza\w*\s+rozwiąza\w*",
        r"\brobi\w*\s+różnicę\b", r"\bna koniec dnia\b", r"\bwartoś\w+\s+dodan\w+", r"\bcustomer experience\b"],
     "Kalka z angielskiego: przeznaczony dla…, rozwiązujemy…, robimy… — po polsku i konkretnie.", False),
    ("PL-CTA", "P1", "tekst", [
        r"\bnie czekaj\b", r"\b(?:zadzwoń|napisz|skontaktuj się)(?: z nami)?\s+już dziś\b",
        r"\bzaufaj\s+(?:nam|profesjonalistom|ekspertom|fachowcom)\b", r"\bpostaw na\s+(?:jakość|profesjonal|nas)\w*",
        r"\bzapraszamy do (?:zapoznania się|współpracy|kontaktu|skorzystania)\b", r"\bserdecznie zapraszamy\b",
        r"\bgotow\w+\s+(?:na|by|, by)\s+[^?]{0,40}\?", r"\bkliknij (?:tutaj|tu)\b"],
     "Zamiast zachęty — co się stanie: „Zadzwoń: 61 000 00 00”, „Pobierz katalog (PDF, 8 MB)”, „Wyznacz trasę”.", False),
    ("PL-CTA-OGOLNE", "P1", "cta", [
        r"^\s*(?:dowiedz się więcej|czytaj (?:więcej|dalej)|zobacz więcej|więcej|sprawdź|kliknij(?: tutaj| tu)?|tutaj|szczegóły|"
        r"poznaj (?:nas|szczegóły|ofertę)|zobacz ofertę|przejdź)\s*[.…→»›]*\s*$"],
     "Tekst linku mówi, dokąd prowadzi: „Wszystkie realizacje (24)”, „Cennik robót 2026”, „Zadzwoń: …”.", False),
    ("PL-DLACZEGO-MY", "P0", "naglowek", [
        r"^\s*Dlaczego (?:my|warto (?:nam zaufać|nas wybrać|wybrać nas|z nami współpracować)|wybrać nas|nas)\s*\??\s*$",
        r"^\s*Dlaczego (?:warto )?(?:my|nas)\b.{0,30}\?\s*$"],
     "Nagłówek „Dlaczego my?” to wzór szablonu. Nazwij, co jest w sekcji: „Beton z własnej wytwórni w Rogoźnie”.", False),
    ("PL-SEKCJA", "P1", "naglowek", [
        r"^\s*Co nas wyróżnia\s*\??\s*$", r"^\s*Nasz[ae] (?:misja|wizja|wartości)\b", r"^\s*Zaufali nam\b",
        r"^\s*Poznaj nas(?: bliżej)?\b", r"^\s*Opinie (?:naszych )?klientów\b", r"^\s*(?:O nas|Nasze usługi|Nasza oferta)\s*$",
        r"^\s*Jak (?:działamy|pracujemy)\s*\??\s*$", r"^\s*Nasi klienci\s*$"],
     "Nagłówek mówi, co jest w sekcji: „Beton z własnej wytwórni w Rogoźnie”, „Karta: 14 pizz, 32–46 zł”.", False),
    ("PL-ANTYTEZA", "P0", "tekst", [
        r"\bto nie (?:tylko |jedynie |po prostu |kolejn\w+ )?[^.,;!?]{2,40}[,.—–-]\s*to\s",
        r"\bto (?:coś )?więcej niż\b", r"\bbez\s+[^.]{2,25}\.\s*bez\s+[^.]{2,25}\.\s*(?:tylko|po prostu|sam\w*)\b",
        r"\balbo\s+[^.]{2,40}\.\s*albo\s",
        r"\bnie (?:sprzedajemy|robimy|budujemy|gotujemy|tworzymy|szyjemy)\s+[^.,]{2,30}[.,]\s*(?:sprzedajemy|robimy|budujemy|gotujemy|tworzymy|szyjemy)\b"],
     "Powiedz wprost, co to jest. Bez zaprzeczenia i puenty („To nie X, to Y”).", False),
    ("PL-NIE-TYLKO", "P2", "tekst", [r"\bnie tylko\s+[^.;!?]{2,50},?\s+ale\s+(?:także|również|też|i)\b"],
     "„Nie tylko…, ale także…” — częsty rytm tekstu z AI; zwykle wystarczy wyliczenie.", False),
    ("PL-LICZNIK", "P1", "tekst", [
        r"\b\d{1,6}\s?\+\s+(?:zadowolonych|lat\w*|realizacji|projektów|klientów|inwestycji|opinii|zleceń|budów|wdrożeń)\b",
        r"\b(?:ponad|blisko|przeszło)\s+\d[\d\s]{1,6}\s+zadowolonych\b", r"\b100\s?%\s+(?:zadowolonych|zadowolenia|gwarancji)\b"],
     "Liczba tylko prawdziwa, z datą i źródłem, w zdaniu („41 zadań z BZP od 2014 r.” + lista). Okrągłe „500+” ukryj.", False),
    ("PL-TRIADA", "P2", "tekst", [
        r"\b(?:szybko|tanio|solidnie|rzetelnie|terminowo|profesjonalnie|sprawnie|bezpiecznie|wygodnie|skutecznie)\w*,\s+\w+\s+i\s+\w+\b",
        r"\b(?:rzetelnoś\w+|terminowoś\w+|profesjonaliz\w+|jakoś\w+|zaufani\w+|doświadczeni\w+|pasj\w+),\s+\w+\s+(?:i|oraz)\s+\w+\b",
        r"^(?:[" + UP + r"]\w+[.,]\s+){2}[" + L + r"]\w+\.$"],
     "Trzy przymiotniki/wartości z rzędu to wzór AI. Zostaw jeden i dopisz dowód.", False),
    ("PL-ZLE-OTWARCIE", "P1", "tekst", [
        r"\bostatnio (?:coraz częściej|zauważam)\b", r"\bczęsto (?:widzę|zauważam|spotykam się)\b", r"\bi szczerze\?",
        r"\bnajciekawsze jest jednak\b", r"\bzagłębmy się\b"],
     "Fałszywa szczerość w stylu LinkedIn. Zacznij od konkretu.", False),
    ("PL-TY-WIELKA", "P2", "tekst", [r"(?<=[" + L + r",] )(?-i:Tw(?:ój|oja|oje|oich|oim|oimi|ojego|ojej|ojemu|oją|ego))\b"],
     "„Twój/Twoje” wielką literą w środku zdania to nawyk reklamy/ChatGPT; małą literą albo bez zwracania się do czytelnika.", False),
    # ---- angielski
    ("EN-HEADLINE", "P0", "tekst", [
        r"\belevate your\b", r"\bunlock (?:the |your )?(?:full )?(?:power|potential)\b", r"\bunleash\b", r"\brevolutioni[sz]e\b",
        r"\btransform (?:your|the way)\b", r"\bsupercharge\b", r"\breimagine (?:your|how)\b", r"\ball-in-one (?:platform|solution|workspace)\b",
        r"\bscale without limits\b", r"\bthe future of \w+ is here\b", r"\bnext-generation\b", r"\bbuild the future\b",
        r"\btake (?:your|it) \w* ?to the next level\b", r"\bnestled in\b", r"\bin the heart of\b"],
     "Write what it is, for whom, with a number (po polsku: co, dla kogo, liczba).", False),
    ("EN-BUZZ", "P1", "tekst", [
        r"\bseamless(?:ly)?\b", r"\bempower\w*", r"\bleverag\w+", r"\bstreamlin\w+", r"\brobust\b", r"\bcutting-edge\b",
        r"\bstate-of-the-art\b", r"\bbest-in-class\b", r"\bworld-class\b", r"\bgame-?chang\w+", r"\beffortless(?:ly)?\b",
        r"\bdelve[sd]?\b", r"\bdelving\b", r"\btapestr\w+", r"\btestament to\b", r"\bharness(?:es|ing)?\b", r"\bbespoke\b",
        r"\bmeticulous\w*", r"\bpassionate about\b", r"\bcommitted to excellence\b", r"\btrusted partner\b", r"\bone-stop shop\b",
        r"\blook no further\b", r"\bwe'?ve got you covered\b", r"\bin today'?s (?:fast-paced|digital|ever-changing) (?:world|landscape)\b",
        r"\bever-evolving\b", r"\bvibrant\b", r"\bboasts\b", r"\b(?:digital|innovative|tailored) solutions\b", r"\bholistic\b",
        r"\bsynerg\w+", r"\bunderscore[sd]?\b", r"\bpivotal\b", r"\bnavigat\w+ the complexit\w+"],
     "Angielski żargon reklamy — zamień na czasownik i fakt (a na polskiej stronie: po polsku).", False),
    ("EN-ANTITHESIS", "P0", "tekst", [
        r"\b(?:it'?s|this is|that'?s|they'?re)\s+not\s+(?:just|only|merely|simply)\b[^.?!\n]{0,60}\bit'?s\b",
        r"\bnot\s+(?:just|only)\s+[^.,]{2,40},?\s+but\b", r"\bmore than just an?\b", r"\bno\s+\w+,\s+no\s+\w+,\s+just\b"],
     "State the thing plainly (bez „not just X, it's Y”).", False),
    ("EN-FILLER", "P1", "tekst", [
        r"\bit'?s worth (?:noting|mentioning)\b", r"\bimportant to note\b", r"(?:^|[.!?]\s+)(?:Moreover|Furthermore|Additionally),",
        r"\b(?:deep dive|dive (?:in|into|deep)|let'?s dive)\b", r"\bat its core\b", r"\ba new era of\b"],
     "Skreśl łącznik.", False),
    ("EN-CTA", "P2", "cta", [r"^\s*(?:get started|learn more|submit|click here|discover more|explore more|read more)\s*[→»]*\s*$"],
     "Nazwij działanie: „Pobierz katalog 2026 (PDF, 8 MB)”.", False),
    ("EN-ASSISTANT", "P0", "tekst", [
        r"\bas an? (?:ai|large) language model\b", r"\bi hope this helps\b", r"\bwould you like me to\b", r"\bgreat question\b",
        r"contentReference|oaicite|turn0search\d|\[cite: ?\d+\]", r"\bjako model językowy\b", r"\bmam nadzieję, że (?:to )?pomoże\b",
        r"\boto (?:propozycja|przykładowy) (?:tekst|treść|opis)\w*"],
     "Resztka odpowiedzi czatu w treści strony. Usuń.", False),
]

KONKRET = re.compile(r"\d|\b(?:zł|km|m²|m³|m2|m3|kg|cm|mm|°C|min|godz|t|l|ha)\b|\bPN-EN\b|\bISO\b|\bnorm\w+")

# --------------------------------------------------------------------------------------------- pozostałe reguły
# id: (poziom, co zamiast)
REGULY = {
    # treść i typografia
    "TRESC-LOREM": ("P0", "Wpisz prawdziwą treść albo ukryj sekcję (null w danych)."),
    "TRESC-ZASLEPKA": ("P0", "Niewypełniony znacznik szablonu — wpisz prawdziwą wartość albo null."),
    "TRESC-STOCK": ("P0", "Tylko zdjęcia firmy (strona, Facebook, własna sesja). Bez zdjęć — mniej sekcji, typografia, rysunek produktu."),
    "TRESC-BEZ-KONKRETU": ("P2", "Akapit na górze strony bez liczby, jednostki, roku, ceny ani nazwy własnej — dopisz fakt, jeśli jest prawdziwy."),
    "TRESC-POWTORKA": ("P1", "Ta sama informacja w dwóch sekcjach jednej strony (CLAUDE.md §2) — zostaw ją w jednym miejscu."),
    "PL-TITLE-CASE": ("P1", "Po polsku wielka litera tylko na początku i w nazwach własnych (PWN): „Roboty drogowe i beton”."),
    "PL-MYSLNIK-MIX": ("P1", "Jeden znak myślnika w całym tekście (PWN); szablon: „ – ” (funkcje.myslnik)."),
    "PL-MYSLNIK-GESTOSC": ("P1", "Za dużo myślników — najczęstszy znak tekstu z AI. Zamień część na przecinek, kropkę albo dwukropek."),
    "PL-MYSLNIK-WTRACENIE": ("P2", "Wtrącenia „ – … – ” w wielu zdaniach to rytm AI; przecinki albo dwa zdania."),
    "PL-MYSLNIK-NAGLOWEK": ("P2", "Myślnik w nagłówku/przycisku — kropka, dwukropek albo nagłówek + wstęp."),
    "PL-ZAKRES-SPACJE": ("P2", "W zakresach półpauza bez spacji: 7:00–15:00, pn.–pt., 32–46 zł."),
    "PL-CUDZYSLOW": ("P2", "Po polsku cudzysłów „…”, zagnieżdżony «…»."),
    "PL-SIEROTKI": ("P2", "Jednoliterowy wyraz (a, i, o, u, w, z) ze zwykłą spacją — typografia buildu powinna wstawić twardą spację; sprawdź, skąd tekst omija typografię."),
    "PL-WYKRZYKNIKI": ("P2", "Wykrzykniki na końcu zdań to ton ulotki. Kropka."),
    "PL-TRIADA-NAGLOWEK": ("P1", "Trzy słowa-wartości w nagłówku („Rzetelnie, terminowo i solidnie”) — nagłówek z faktem."),
    # wygląd — HTML
    "V-EMOJI": ("P0", "Emoji zamiast ikon/punktorów — tekst albo jeden zestaw ikon SVG."),
    "V-ISKRY": ("P0", "„✨ Nowość” nad h1 — tylko prawdziwe, datowane ogłoszenie jako zwykły tekst."),
    "V-ODZNAKA-NAD-H1": ("P1", "Pigułka/odznaka nad h1 — otwórz stronę zdjęciem, nazwą, faktem i telefonem."),
    "V-TRZY-KARTY": ("P0", "Siatka kart z ikoną, tytułem i zdaniem — lista, tabela albo jeden duży element i proza."),
    "V-NUMERY-01": ("P1", "Ozdobne „01/02/03” poza prawdziwą listą kroków — numeruj tylko sekwencje w <ol>."),
    "V-AKCENT-SLOWA": ("P1", "Jedno słowo w nagłówku kursywą/kolorem — cały nagłówek jednym krojem; wyróżnij liczbą albo nazwą."),
    "V-LICZNIK-ANIM": ("P1", "Animowany licznik — pokaż liczbę wprost (i tylko prawdziwą, ze źródłem)."),
    "V-PASEK-STATYSTYK": ("P1", "Pasek „500+ · 98% · 15+” — tylko prawdziwe liczby w zdaniu, ze źródłem i datą."),
    "V-GWIAZDKI": ("P1", "Gwiazdki opinii bez linku do źródła (Google/Facebook) — Omnibus: opinie tylko zweryfikowane, z linkiem."),
    "V-ETYKIETY-NAD-H": ("P1", "Mała etykieta nad każdym nagłówkiem — usuń; informację wpisz w nagłówek (D1: maks. 2)."),
    "V-STRZALKA-CTA": ("P2", "Strzałka doklejona do tekstu przycisku — bez niej; ikona tylko, gdy kierunek coś znaczy."),
    "V-SLIDER": ("P1", "Karuzela/slider — jedno najlepsze zdjęcie albo siatka; nigdy autoplay."),
    "V-PRELOADER": ("P1", "Ekran ładowania — strona ma się ładować szybko, nie udawać."),
    "V-DO-GORY": ("P2", "Pływający przycisk „do góry” — zbędny (klawisz Home, krótka strona)."),
    "V-FADE-UP-WSZEDZIE": ("P2", "To samo wejście „fade-up” na każdej sekcji — jedno wejście hero albo nic (D6)."),
    "V-EFEKTY-BIBLIOTEKI": ("P1", "Biblioteka efektów (AOS, GSAP, particles, typed…) — usuń."),
    "V-SYGNATURA": ("P1", "Ślad generatora (v0, Lovable, Bolt…) w kodzie — usuń."),
    "V-PIGULKA": ("P1", "Przycisk-pigułka (pełne zaokrąglenie) — promień z marki (0–4 px)."),
    # wygląd — CSS
    "V-GRAD-FIOLET": ("P0", "Fioletowo-niebieski gradient — płaski kolor marki."),
    "V-TEKST-GRADIENT": ("P0", "Tekst wypełniony gradientem — jednolity kolor tekstu albo marki."),
    "V-GRADIENT": ("P1", "Gradient tła (KONTRAKT §7.5: tylko przyciemnienie zdjęcia) — płaskie tło z tokenów."),
    "V-KARTY-ZAOKR-CIEN": ("P1", "Karty z zaokrągleniem ≥ 12 px i cieniem — płaskie powierzchnie, linie 1 px, odstęp."),
    "V-PASEK-BOCZNY": ("P1", "Kolorowy pasek z boku/u góry karty — wyróżnij położeniem i wielkością."),
    "V-WERSALIKI": ("P1", "Etykiety WERSALIKAMI z rozstrzeleniem w wielu miejscach — zdanie zwykłym krojem; maks. 3 użycia."),
    "V-SZKLO": ("P1", "backdrop-filter: blur (szkło) poza przyklejonym nagłówkiem — pełne tło."),
    "V-POSWIATA": ("P2", "Kolorowa poświata (box-shadow) — bez cienia albo neutralny cień tylko dla rzeczy, które się unoszą."),
    "V-SPREZYNA": ("P2", "Sprężynowanie (cubic-bezier z przestrzeleniem) — ease-out bez odbicia."),
    "V-KROJ-DOMYSLNY": ("P0", "Tylko Inter/Roboto/Arial/systemowy — krój z biblioteki szablonu dobrany do marki."),
    "V-KROJ-MODNY": ("P1", "Krój z listy „modnych darmowych” (Geist, Instrument Serif, Space Grotesk…) — dobierz do marki."),
    "V-KREM-TERAKOTA": ("P2", "Kremowe tło + rdzawy akcent = rozpoznawalny „styl Claude'a” — tylko, gdy kolory są z logo/szyldu."),
    "V-NAPIS-STOPKA": ("P1", "Gigantyczny napis w stopce — stopka z adresu, telefonu, godzin i danych rejestrowych."),
    "A11Y-RUCH": ("P0", "Animacje bez @media (prefers-reduced-motion: reduce)."),
    "A11Y-FOKUS": ("P0", "Brak :focus-visible w stylach — widoczny obrys 2 px."),
    "A11Y-ALT": ("P1", "<img> bez atrybutu alt."),
    # zasady domu (CLAUDE.md)
    "DOM-GOOGLE-FONTS": ("P0", "Google Fonts (RODO) — fonty z własnego serwera (assets/fonts)."),
    "DOM-MAPA-IFRAME": ("P0", "Iframe Google Maps od razu przy wejściu (RODO) — „Pokaż mapę” po kliknięciu / „Wyznacz trasę”."),
    "DOM-WIDZET": ("P0", "Widżet zewnętrzny (czat, opinie, Facebook) — przekazuje dane przy wejściu; link zamiast widżetu."),
    "DOM-DATA-URI": ("P1", "Obrazek jako data URI — osobny plik (cache)."),
    "DOM-OG-WZGLEDNY": ("P1", "og:image musi mieć pełny adres https://…"),
    "DOM-CSS-WERSJA": ("P2", "CSS bez ?v=<skrót> w adresie — stary plik z cache rozjedzie stronę po wdrożeniu."),
    "DOM-JS-WERSJA": ("P2", "JS bez ?v=<skrót> w adresie."),
    "DOM-IMG-WH": ("P2", "<img> bez width/height — przesunięcia układu (CLS)."),
    "DOM-BANER-BEZ-COOKIES": ("P2", "Baner cookies, choć strona nie ma cookies ani trackerów — usuń."),
    # marka
    "MARKA-DOMYSLNA": ("P0", "Marka z szablonu albo z przykładu — kolor z logo/szyldu klienta i kroje dobrane do niego (data/firma.json → marka)."),
    # zwolnienia
    "SLOP-OK-BEZ-POWODU": ("P1", "Zwolnienie w data/slop-ok.json bez powodu (pole „powod”, min. 10 znaków) nie działa."),
    "SLOP-OK-P0": ("P1", "P0 nie da się zwolnić — popraw treść; jeśli to fałszywy alarm, popraw regułę w tools/lint_slop.py."),
    "SLOP-OK-NIEUZYWANE": ("P2", "Zwolnienie nie pasuje do żadnego wyniku — usuń je z data/slop-ok.json."),
}
for _r in REGULY_TEKSTU:
    REGULY.setdefault(_r[0], (_r[1], _r[4]))

# --------------------------------------------------------------------------------------------- wynik


@dataclass
class Wynik:
    id: str
    poziom: str
    plik: str
    linia: int
    komunikat: str
    fragment: str = ""
    pole: str | None = None
    naprawa: str = ""
    tez: list = field(default_factory=list)      # inne miejsca (plik:linia) z tym samym wynikiem
    klucz: str = ""                              # do łączenia takich samych wyników z wielu stron

    def slownik(self) -> dict:
        d = {"id": self.id, "poziom": self.poziom, "plik": self.plik, "linia": self.linia, "komunikat": self.komunikat,
             "fragment": self.fragment, "pole": self.pole, "naprawa": self.naprawa}
        if self.tez:
            d["tez"] = self.tez
        return d


class Zbior:
    """Wyniki jednego przebiegu; takie same wyniki (ten sam klucz) z kilku stron łączy w jeden z listą „też”."""

    def __init__(self):
        self.lista: list[Wynik] = []
        self._po_kluczu: dict[str, Wynik] = {}

    def dodaj(self, rid, plik, linia, komunikat, fragment="", poziom=None, pole=None, klucz=None):
        poz, naprawa = REGULY.get(rid, ("P2", ""))
        w = Wynik(rid, poziom or poz, plik, linia, komunikat, fragment, pole, naprawa)
        w.klucz = klucz or f"{rid}|{plik}|{linia}|{komunikat}"
        stary = self._po_kluczu.get(w.klucz)
        if stary:
            miejsce = f"{plik}:{linia}"
            if miejsce != f"{stary.plik}:{stary.linia}" and miejsce not in stary.tez:
                stary.tez.append(miejsce)
            if KOLEJNOSC[w.poziom] < KOLEJNOSC[stary.poziom]:
                stary.poziom = w.poziom
            return stary
        self._po_kluczu[w.klucz] = w
        self.lista.append(w)
        return w


def norm(t: str) -> str:
    """Tekst bez typografii (twarde spacje, półpauzy, cudzysłowy) i wielkości liter — do porównań."""
    t = t.replace(" ", " ").replace(" ", " ").replace("‑", "-")
    t = re.sub(r"[–—]", "-", t)
    t = re.sub(r"[„”“\"«»‚’']", "", t)
    t = t.replace("…", "...")
    return " ".join(t.split()).lower()


_BIALE = re.compile(r"[ \t\n\r\f\v]+")


def scal(t: str) -> str:
    """Zwija zwykłe białe znaki, zostawia twarde spacje (potrzebne do reguły PL-SIEROTKI)."""
    return _BIALE.sub(" ", t).strip()


def sciezka_wysw(p) -> str:
    p = os.path.abspath(str(p))
    try:
        r = os.path.relpath(p)
        return r if not r.startswith("..") else p
    except ValueError:
        return p


# --------------------------------------------------------------------------------------------- HTML → drzewo
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
POMIN_TAGI = {"script", "style", "noscript", "svg", "template", "code", "pre", "math"}
BLOKI = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dt", "dd", "figcaption", "blockquote", "button",
         "label", "summary", "caption", "div", "section", "article", "header", "footer", "main", "nav", "ul", "ol", "dl",
         "figure", "form", "table", "thead", "tbody", "tr", "title", "address", "aside", "legend", "fieldset", "details",
         "option", "select", "body", "html", "head"}
ZAMYKA_P = {"p", "div", "ul", "ol", "dl", "table", "section", "article", "header", "footer", "h1", "h2", "h3", "h4", "h5",
            "h6", "figure", "form", "blockquote", "address", "aside", "nav", "main", "details", "fieldset", "pre", "hr"}
REGIONY = {"section", "header", "footer", "nav", "aside", "main", "article"}


class Wezel:
    __slots__ = ("tag", "a", "dzieci", "linia", "rodzic")

    def __init__(self, tag, a, linia, rodzic):
        self.tag, self.a, self.linia, self.rodzic, self.dzieci = tag, a, linia, rodzic, []

    def klasy(self) -> str:
        return self.a.get("class", "")

    def elementy(self):
        return [d for d in self.dzieci if isinstance(d, Wezel)]

    def przodkowie(self):
        w = self.rodzic
        while w is not None:
            yield w
            w = w.rodzic

    def tekst(self) -> str:
        """Cały tekst potomków (bez script/style/svg…)."""
        czesci = []

        def idz(w):
            for d in w.dzieci:
                if isinstance(d, Wezel):
                    if d.tag in POMIN_TAGI:
                        continue
                    if d.tag == "br":
                        czesci.append(" ")
                    idz(d)
                    if d.tag in BLOKI:
                        czesci.append(" ")
                else:
                    czesci.append(d[0])
        idz(self)
        return scal("".join(czesci))


class Drzewo(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.korzen = Wezel("#dok", {}, 1, None)
        self.biezacy = self.korzen

    def handle_starttag(self, tag, attrs):
        linia = self.getpos()[0]
        if self.biezacy.tag == "p" and tag in ZAMYKA_P:
            self.biezacy = self.biezacy.rodzic
        if tag == "li" and self.biezacy.tag == "li":
            self.biezacy = self.biezacy.rodzic
        w = Wezel(tag, {k: (v or "") for k, v in attrs}, linia, self.biezacy)
        self.biezacy.dzieci.append(w)
        if tag not in VOID:
            self.biezacy = w

    def handle_startendtag(self, tag, attrs):
        w = Wezel(tag, {k: (v or "") for k, v in attrs}, self.getpos()[0], self.biezacy)
        self.biezacy.dzieci.append(w)

    def handle_endtag(self, tag):
        w = self.biezacy
        while w is not self.korzen and w.tag != tag:
            w = w.rodzic
        if w is not self.korzen:
            self.biezacy = w.rodzic

    def handle_data(self, data):
        self.biezacy.dzieci.append((data, self.getpos()[0]))


def wszystkie(w: Wezel):
    for d in w.dzieci:
        if isinstance(d, Wezel):
            yield d
            yield from wszystkie(d)


@dataclass
class Jednostka:
    """Kawałek widocznego tekstu z kontekstem."""
    tekst: str
    linia: int
    rodzaj: str            # blok | naglowek | cta | atrybut | tytul
    tag: str = ""
    region: str = ""       # id/klasa najbliższej sekcji (do powtórzeń)
    obudowa: bool = False  # w header/footer/nav (powtórzenia tam są dozwolone)


def _region(w: Wezel) -> tuple[str, bool]:
    reg, obudowa = "", False
    for p in [w] + list(w.przodkowie()):
        if p.tag in ("header", "footer", "nav") or "site-header" in p.klasy() or "site-footer" in p.klasy():
            obudowa = True
        if not reg and p.tag in REGIONY:
            reg = p.a.get("id") or f"{p.tag}.{p.klasy()}@{p.linia}"
    return reg, obudowa


def _tekst_wlasny(w: Wezel) -> str:
    """Tekst elementu bez zagnieżdżonych bloków (te dają własne jednostki)."""
    czesci = []

    def idz(x):
        for d in x.dzieci:
            if isinstance(d, Wezel):
                if d.tag in POMIN_TAGI or d.tag in BLOKI:
                    czesci.append(" ")
                    continue
                if d.tag == "br":
                    czesci.append(" ")
                idz(d)
            else:
                czesci.append(d[0])
    idz(w)
    return scal("".join(czesci))


def jednostki(korzen: Wezel) -> list[Jednostka]:
    wyn = []
    for w in wszystkie(korzen):
        if any(p.tag in POMIN_TAGI for p in [w] + list(w.przodkowie())):
            continue
        reg, obud = _region(w)
        if w.tag in BLOKI:
            t = _tekst_wlasny(w)
            if t:
                rodzaj = "naglowek" if re.fullmatch(r"h[1-6]", w.tag) else ("tytul" if w.tag == "title" else "blok")
                wyn.append(Jednostka(t, w.linia, rodzaj, w.tag, reg, obud))
        if w.tag in ("a", "button") or (w.tag == "input" and w.a.get("type") in ("submit", "button")):
            t = w.tekst() or w.a.get("value", "")
            if t:
                wyn.append(Jednostka(t, w.linia, "cta", w.tag, reg, obud))
        for k in ("alt", "title", "aria-label", "placeholder"):
            if w.a.get(k):
                wyn.append(Jednostka(w.a[k], w.linia, "atrybut", f"{w.tag}[{k}]", reg, obud))
        if w.tag == "meta" and (w.a.get("name") == "description" or w.a.get("property") in ("og:title", "og:description")):
            if w.a.get("content"):
                wyn.append(Jednostka(w.a["content"], w.linia, "atrybut", "meta", reg, obud))
    return wyn


# --------------------------------------------------------------------------------------------- reguły tekstu (wspólne dla dist i danych)
_SKOMPILOWANE = [(rid, poz, zakres, [re.compile(p, re.I | re.M) for p in wz], nap, wyj)
                 for rid, poz, zakres, wz, nap, wyj in REGULY_TEKSTU]


def _zdanie(t: str, a: int, b: int) -> str:
    p = max(t.rfind(".", 0, a), t.rfind("!", 0, a), t.rfind("?", 0, a)) + 1
    k = [i for i in (t.find(".", b), t.find("!", b), t.find("?", b)) if i >= 0]
    return t[p:min(k) if k else len(t)].strip()


def ma_konkret(zdanie: str, nazwy: set) -> bool:
    if KONKRET.search(zdanie):
        return True
    slowa = re.findall(rf"[{L}][{L}-]*", zdanie)
    if any(s in nazwy for s in slowa):
        return True
    # wielka litera w środku zdania = zwykle nazwa własna (w polskim zdaniu tylko pierwsze słowo jest wielką literą)
    return bool(re.search(rf"[{L},;:)]\s+(?-i:[{UP}])[{L}]{{2,}}", zdanie))


def reguly_tekstu(t: str, rodzaj: str, nazwy: set):
    """Zwraca [(id, poziom, dopasowanie, zdanie)] dla jednego tekstu (twarde spacje liczą się jak zwykłe)."""
    t = " ".join(t.replace("\u00a0", " ").replace("\u202f", " ").split())
    wyn = []
    for rid, poz, zakres, wzorce, _nap, wyjatek in _SKOMPILOWANE:
        if zakres == "cta" and rodzaj != "cta":
            continue
        if zakres == "naglowek" and rodzaj not in ("naglowek", "tytul"):
            continue
        if zakres == "tekst" and rodzaj == "cta":
            continue
        for rx in wzorce:
            for m in rx.finditer(t):
                zd = _zdanie(t, m.start(), m.end())
                p = poz
                if wyjatek and ma_konkret(zd, nazwy):
                    if poz == "P2":
                        continue
                    p = "P2"
                if rid == "PL-TRIADA" and rodzaj in ("naglowek", "tytul"):
                    wyn.append(("PL-TRIADA-NAGLOWEK", "P1", m.group(0), zd))
                    continue
                wyn.append((rid, p, m.group(0), zd))
    return wyn


def dodaj_tekst(z, plik, linia, t, rodzaj, nazwy, pole=None):
    """Reguły tekstu dla jednego napisu; kilka trafień tej samej reguły w jednym zdaniu = jeden wynik."""
    grupy: dict = {}
    for rid, poz, dop, zd in reguly_tekstu(t, rodzaj, nazwy):
        g = grupy.setdefault((rid, zd), [poz, []])
        if KOLEJNOSC[poz] < KOLEJNOSC[g[0]]:
            g[0] = poz
        if dop.strip() and dop.strip() not in g[1]:
            g[1].append(dop.strip())
    for (rid, zd), (poz, dops) in grupy.items():
        cyt = _cytat(zd or t, dops[0] if dops else "")
        co = ", ".join(f"„{d}”" for d in dops)
        kom = f"{co} w „{cyt}”" if dops and norm(dops[0]) != norm(cyt) else f"„{cyt}”"
        z.dodaj(rid, plik, linia, kom, dops[0] if dops else "", poziom=poz, pole=pole,
                klucz=f"{rid}|{norm(zd or t)[:120]}")


def _cytat(zdanie: str, dop: str, n: int = 110) -> str:
    z = " ".join(zdanie.split())
    if len(z) <= n:
        return z
    i = z.lower().find(dop.lower())
    a = max(0, i - 40) if i >= 0 else 0
    return ("…" if a else "") + z[a:a + n].strip() + "…"


# --------------------------------------------------------------------------------------------- kolor
KOLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)")


def kolor(s: str):
    s = s.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3,8})", s)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + ((int(h[6:8], 16) / 255) if len(h) == 8 else 1.0,)
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+%?))?\s*\)", s)
    if m:
        a = m.group(4)
        a = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), a)
    m = re.fullmatch(r"hsla?\(\s*([\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%(?:[\s,/]+([\d.]+%?))?\s*\)", s)
    if m:
        r, g, b = colorsys.hls_to_rgb(float(m.group(1)) / 360, float(m.group(3)) / 100, float(m.group(2)) / 100)
        a = m.group(4)
        a = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return (r * 255, g * 255, b * 255, a)
    return None


def hsl(c):
    h, l_, s = colorsys.rgb_to_hls(c[0] / 255, c[1] / 255, c[2] / 255)
    return h * 360, s * 100, l_ * 100


def _w_zakresie(h, od, do):
    return od <= h <= do if od <= do else (h >= od or h <= do)


def fioletowy(c):
    h, s, l_ = hsl(c)
    return _w_zakresie(h, 228, 300) and s >= 40 and 15 < l_ < 90


def nasycony(c):
    h, s, l_ = hsl(c)
    return s >= 45 and 20 <= l_ <= 80


def kremowy(c):
    h, s, l_ = hsl(c)
    return 89 <= l_ < 99.5 and s >= 12 and _w_zakresie(h, 20, 60)


def terakota(c):
    h, s, l_ = hsl(c)
    return _w_zakresie(h, 355, 28) and s >= 45 and 35 <= l_ <= 68


# --------------------------------------------------------------------------------------------- CSS

@dataclass
class RegulaCSS:
    selektor: str
    cialo: str
    linia: int
    plik: str
    zrodlo: str      # część źródłowa (assets/css/czesci/xx.css), gdy znana z komentarza w strona.css
    wiersze: tuple   # (od, do) — do zwolnień w komentarzach


def reguly_css(css: str, plik: str) -> list[RegulaCSS]:
    czesci = [(css.count("\n", 0, m.start()) + 1, m.group(1))
              for m in re.finditer(r"^/\* ([\w.-]+\.css) \*/\s*$", css, re.M)]
    bez_kom = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), css, flags=re.S)
    wyn = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", bez_kom):
        linia = bez_kom.count("\n", 0, m.start() + len(m.group(1)) - len(m.group(1).lstrip())) + 1
        koniec = bez_kom.count("\n", 0, m.end()) + 1
        zr = ""
        for ln, nazwa in czesci:
            if ln <= linia:
                zr = nazwa
        sel = " ".join(m.group(1).split())
        sel = re.sub(r"^.*;\s*", "", sel)          # resztki @import/@charset przed selektorem
        wyn.append(RegulaCSS(sel, m.group(2), linia, plik, zr, (linia - 1, koniec)))
    return wyn


def zmienne(reguly: list[RegulaCSS]) -> dict:
    v = {}
    for r in reguly:
        if re.search(r"(^|,)\s*(:root|html)\b", r.selektor) and "prefers-color-scheme" not in r.selektor:
            for m in re.finditer(r"--([\w-]+)\s*:\s*([^;]+)", r.cialo):
                v.setdefault(m.group(1), m.group(2).strip())
    for r in reguly:
        for m in re.finditer(r"--([\w-]+)\s*:\s*([^;]+)", r.cialo):
            v.setdefault(m.group(1), m.group(2).strip())
    return v


def rozwin(t: str, v: dict) -> str:
    for _ in range(6):
        nowy = re.sub(r"var\(\s*--([\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\))?[^()]*))?\)",
                      lambda m: v.get(m.group(1), m.group(2) or ""), t)
        if nowy == t:
            break
        t = nowy
    return t


def _px(wartosc: str, jednostka: str) -> float:
    return float(wartosc) * (16 if jednostka in ("rem", "em") else 1)


MODNE = re.compile(r"\b(space grotesk|geist(?! mono)|syne|sora|instrument serif|fraunces|cal sans|dm sans|manrope|"
                   r"plus jakarta sans|outfit)\b", re.I)
DOMYSLNE_KROJE = re.compile(r"^(inter|roboto|arial|open sans|montserrat|poppins|lato|system-ui|-apple-system|helvetica|"
                            r"helvetica neue|segoe ui|sans-serif|serif|inherit|initial|unset|monospace|ui-sans-serif)$", re.I)
PHOTO_SEL = re.compile(r"hero|foto|photo|zdjec|obraz|img|image|picture|media|cover|overlay|scrim|przyciem|cien|mapa|video|banner", re.I)


def sprawdz_css(reguly: list[RegulaCSS], teksty: list[tuple[str, str]], z: Zbior):
    """Reguły wizualne dla całej witryny (tokeny w jednym pliku, użycie w innym)."""
    v = zmienne(reguly)
    caly = "\n".join(t for _, t in teksty)

    def gdzie(r: RegulaCSS) -> str:
        return f" ({r.zrodlo})" if r.zrodlo else ""

    zaokr_cien, wersaliki = [], []
    for r in reguly:
        rb = rozwin(r.cialo, v)
        sel = r.selektor
        for m in re.finditer(r"(?:linear|radial|conic)-gradient\(((?:[^()]|\([^()]*\))*)\)", rb):
            kolory = [kolor(x) for x in KOLOR_RE.findall(m.group(1))]
            if any(c and fioletowy(c) for c in kolory):
                z.dodaj("V-GRAD-FIOLET", r.plik, r.linia, f"{sel[:70]}: gradient w odcieniach fioletu{gdzie(r)}", sel)
            elif not PHOTO_SEL.search(sel) and not all(c and hsl(c)[1] < 8 for c in kolory if c):
                z.dodaj("V-GRADIENT", r.plik, r.linia, f"{sel[:70]}: gradient tła{gdzie(r)}", sel)
        if re.search(r"background-clip\s*:\s*text", rb) and re.search(r"(?:-webkit-text-fill-color|(?<![\w-])color)\s*:\s*transparent", rb):
            z.dodaj("V-TEKST-GRADIENT", r.plik, r.linia, f"{sel[:70]}: tekst z gradientem{gdzie(r)}", sel)
        if re.search(r"backdrop-filter\s*:[^;]*blur", rb) and not re.search(r"header|nav|menu|bar|pasek|naglowek", sel, re.I):
            z.dodaj("V-SZKLO", r.plik, r.linia, f"{sel[:70]}: backdrop-filter: blur{gdzie(r)}", sel)
        mr = re.search(r"border-radius\s*:\s*([\d.]+)(px|rem|em|%|vh|vw)?", rb)
        if mr:
            jedn = mr.group(2) or "px"
            px = _px(mr.group(1), jedn) if jedn in ("px", "rem", "em") else 0
            if 12 <= px < 100 and re.search(r"box-shadow\s*:(?![^;]*\binset\b)(?!\s*none)", rb):
                zaokr_cien.append(r)
            duzy = (jedn in ("px", "rem", "em") and px >= 100) or (jedn in ("vh", "vw") and float(mr.group(1)) >= 10)
            if duzy and re.search(r"btn|button|przycisk|cta|pill|chip|badge|tag\b|link", sel, re.I):
                z.dodaj("V-PIGULKA", r.plik, r.linia, f"{sel[:70]}: border-radius {mr.group(0).split(':')[1].strip()}{gdzie(r)}", sel)
        mb = re.search(r"border-(?:left|top|inline-start)\s*:\s*([2-9]|\d{2})px\s+solid\s+([^;]+)", rb)
        if mb and not re.search(r"blockquote|quote|cytat|input|:focus|table|\bth\b|\btd\b|\bhr\b|aria-current|is-dzis|"
                                r"is-aktyw|current|\.pole|select|textarea", sel, re.I):
            if any((c := kolor(x)) and nasycony(c) for x in KOLOR_RE.findall(mb.group(2))):
                z.dodaj("V-PASEK-BOCZNY", r.plik, r.linia, f"{sel[:70]}: {mb.group(0)[:50]}{gdzie(r)}", sel)
        if re.search(r"text-transform\s*:\s*uppercase", rb) and re.search(r"letter-spacing\s*:\s*\.?[1-9]|letter-spacing\s*:\s*0?\.\d*[1-9]", rb):
            wersaliki.append(r)
        for m in re.finditer(r"box-shadow\s*:\s*([^;]+)", rb):
            w = m.group(1)
            rozm = re.match(r"\s*-?[\d.]+(?:px)?\s+-?[\d.]+(?:px)?\s+([\d.]+)px", w)
            if "inset" in w or not rozm or float(rozm.group(1)) < 8:
                continue
            if any((c := kolor(x)) and c[3] >= .25 and nasycony(c) for x in KOLOR_RE.findall(w)):
                z.dodaj("V-POSWIATA", r.plik, r.linia, f"{sel[:70]}: kolorowy cień{gdzie(r)}", sel)
        for m in re.finditer(r"cubic-bezier\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", rb):
            if not (-0.05 <= float(m.group(2)) <= 1.05 and -0.05 <= float(m.group(4)) <= 1.05):
                z.dodaj("V-SPREZYNA", r.plik, r.linia, f"{sel[:70]}: {m.group(0)}{gdzie(r)}", sel)
        if re.search(r"footer|stopka", sel, re.I):
            for m in re.finditer(r"font-size\s*:\s*([^;]+)", rb):
                w = m.group(1)
                vw = [float(x) for x in re.findall(r"([\d.]+)vw", w)]
                pxs = [_px(a, b) for a, b in re.findall(r"([\d.]+)(px|rem)", w)]
                if (vw and max(vw) >= 12) or (pxs and max(pxs) >= 200):
                    z.dodaj("V-NAPIS-STOPKA", r.plik, r.linia, f"{sel[:70]}: font-size {w.strip()[:40]}{gdzie(r)}", sel)
    if len(zaokr_cien) >= 3:
        r = zaokr_cien[0]
        z.dodaj("V-KARTY-ZAOKR-CIEN", r.plik, r.linia,
                f"{len(zaokr_cien)} reguł z border-radius ≥ 12 px i cieniem (np. {r.selektor[:50]}{gdzie(r)})")
    if len(wersaliki) >= 4:
        r = wersaliki[0]
        z.dodaj("V-WERSALIKI", r.plik, r.linia, f"{len(wersaliki)} reguł uppercase + letter-spacing (maks. 3; np. "
                f"{', '.join(x.selektor[:30] for x in wersaliki[:4])})")
    # kroje
    rodziny = [f.strip().strip("\"'") for f in re.findall(r"@font-face\s*\{[^}]*?font-family\s*:\s*([^;]+)", caly)]
    plik0 = teksty[0][0] if teksty else ""
    for f in sorted(set(rodziny)):
        if MODNE.search(f):
            z.dodaj("V-KROJ-MODNY", plik0, 1, f"„{f}” w @font-face", f)
    pierwsze = []
    for r in reguly:
        for m in re.finditer(r"font-family\s*:\s*([^;]+)", rozwin(r.cialo, v)):
            pierwsze.append(m.group(1).split(",")[0].strip().strip("\"'"))
    if pierwsze and all(DOMYSLNE_KROJE.match(f) for f in pierwsze) and not any(
            f.lower() == x.lower() for f in pierwsze for x in rodziny if not DOMYSLNE_KROJE.match(x)):
        z.dodaj("V-KROJ-DOMYSLNY", plik0, 1, "wszystkie font-family to Inter/Roboto/Arial/systemowy")
    if re.search(r"@import\s+(?:url\()?[\"']?[^;]*fonts\.googleapis", caly):
        z.dodaj("DOM-GOOGLE-FONTS", plik0, 1, "@import z fonts.googleapis.com w CSS")
    if re.search(r"@keyframes|animation\s*:", caly) and "prefers-reduced-motion" not in caly:
        z.dodaj("A11Y-RUCH", plik0, 1, "są animacje, nie ma @media (prefers-reduced-motion)")
    if reguly and not re.search(r":focus-visible|:focus\b", caly):
        z.dodaj("A11Y-FOKUS", plik0, 1, "w stylach nie ma :focus-visible ani :focus")
    if re.search(r"@keyframes\s+(?:fade-?in-?up|fadeup|slide-?up|fade-up|reveal)", caly, re.I) and \
            len(re.findall(r"animation(?:-name)?\s*:[^;]*(?:fade-?in-?up|fadeup|slide-?up|reveal)", caly, re.I)) >= 3:
        z.dodaj("V-FADE-UP-WSZEDZIE", plik0, 1, "ta sama animacja wejścia w ≥ 3 regułach")
    # tło kremowe + terakota
    tlo = None
    for r in reguly:
        if re.search(r"(^|,)\s*(html|body)\s*($|,)", r.selektor):
            m = re.search(r"background(?:-color)?\s*:\s*([^;]+)", rozwin(r.cialo, v))
            if m and KOLOR_RE.search(m.group(1)):
                tlo = kolor(KOLOR_RE.findall(m.group(1))[-1])
    if tlo and kremowy(tlo) and any((c := kolor(x)) and terakota(c) for x in KOLOR_RE.findall(rozwin(caly, v))):
        z.dodaj("V-KREM-TERAKOTA", plik0, 1, "kremowe tło i rdzawy akcent")


# --------------------------------------------------------------------------------------------- HTML: strona
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF\U0001F000-\U0001F0FF\U00002B50\U00002B06\U00002934\U00002935]")
EMOJI_DOZWOLONE = set("★☆✓✔✗✘☎✉✆✎✂♀♂☐☑☒✱✳✴❯❮➔")
STRZALKA = re.compile(r"\s[→⟶➜➔»›]\s*$|^\s*[←«‹]\s")
STOCK = re.compile(r"unsplash|pexels|pixabay|freepik|shutterstock|istock(?:photo)?|gettyimages|stock\.adobe|adobe[ _-]?stock|"
                   r"adobestock|depositphotos|dreamstime|123rf|pravatar|dicebear|randomuser|ui-avatars|placehold|picsum|"
                   r"lorempixel|midjourney|dall[-_ ]?e\b|stable[-_ ]?diffusion|firefly|ai[-_ ]?generated|generated[-_ ]by[-_ ]ai|"
                   r"wygenerowan\w*\s+(?:przez\s+)?(?:ai|sztuczn)|zdjęci\w+\s+stockow\w+|\bstock(?:owe|owy|owa|[-_ ]?photo|[-_ ]?image)?\b", re.I)
LOREM = re.compile(r"\blorem ipsum\b|\bdolor sit amet\b", re.I)
ZASLEPKA = re.compile(r"\{\{\s*[\w.|\" ]+\s*\}\}|\{%|\[(?:NAZWA|Nazwa|TELEFON|Telefon|ADRES|Adres|MIASTO|Miasto|FIRMA|Firma|"
                      r"UZUPEŁNIJ|Uzupełnij)[^\]]*\]|\bXX[\s:]?XX\b|\b000[ -]000[ -]000\b|\bTODO\b|\bFIXME\b|\bXXX\b")
NUMER_OZDOBNY = re.compile(r"^\s*[\[(#]?\s*0[1-9]\s*[\]).\/]?\s*$")
STATYSTYKA = re.compile(r"^\s*\d[\d\s.,]*\s?(?:\+|%|★|tys\.?\s?\+|k\+)\s*$")
ETYKIETA_KL = re.compile(r"\b(?:label|eyebrow|kicker|overline|tagline|sec-head|section-label|subtitle|etykieta|nadtytul|"
                         r"section__etykieta|pre-?title|supertitle)\b", re.I)
IKONA_KL = re.compile(r"ikon|icon|\bi-|fa-|lucide|symbol", re.I)

# nazwy własne, które mogą stać wielką literą w nagłówku (oprócz nazw z data/firma.json)
NAZWY_STALE = set("""Europejski Europejska Europejskiego Europejskiej Obszar Obszaru Gospodarczy Gospodarczego Unia Unii
Polska Polski Polsce Rzeczypospolitej Polskiej Cloudflare Google Facebook Instagram LinkedIn YouTube TikTok OpenStreetMap
GitHub Pages Mapy Map Maps RODO UODO Prezes Prezesa Urząd Urzędu Ochrony Danych Osobowych KRS NIP REGON BZP Biuletyn
Biuletynu Zamówień Publicznych Sąd Rejonowy Wydział Gospodarczy Krajowego Rejestru Sądowego Wielkopolska Wielkopolski
Wielkopolskiego Wielkopolsce Poznań Poznania Poznaniu Warszawa Warszawy Kraków Krakowa Wrocław Gdańsk Łódź Szczecin
Boże Narodzenie Narodzenia Wielkanoc Wielkiej Nocy Wigilia Sylwester PDF DOCX JPG VAT BHP ISO CE PN EN""".split())


def czy_title_case(t: str, nazwy: set) -> bool:
    slowa = re.findall(rf"[{L}][{L}-]*", t)
    if len(slowa) < 3:
        return False
    reszta = [s for s in slowa[1:] if len(s) > 2 and s not in nazwy and s not in NAZWY_STALE and not s.isupper()]
    wielkie = [s for s in reszta if s[0].isupper()]
    return len(reszta) >= 2 and len(wielkie) >= 2 and len(wielkie) / len(reszta) >= 0.75


def _bez_marki(tytul: str, nazwy: set) -> str:
    """„Roboty drogowe Rogoźno – BIMEX” → „Roboty drogowe Rogoźno” (część z marką po separatorze)."""
    czesci = re.split(r"\s[–—|·-]\s", tytul)
    return max(czesci, key=len) if len(czesci) > 1 else tytul


def _slowa(t: str) -> int:
    return len(re.findall(rf"[{L}0-9]+", t))


def sprawdz_strone(plik: str, src: str, z: Zbior, nazwy: set, teksty_stron: list):
    d = Drzewo()
    d.feed(src)
    d.close()
    kor = d.korzen
    jed = jednostki(kor)
    elementy = list(wszystkie(kor))

    # ---- reguły tekstu
    for j in jed:
        dodaj_tekst(z, plik, j.linia, j.tekst, j.rodzaj, nazwy)
    teksty_stron.append((plik, jed))

    widoczne = [j for j in jed if j.rodzaj in ("blok", "naglowek")]
    proza = [j for j in widoczne if j.tag in ("p", "li", "dd", "figcaption", "blockquote", "div", "td") and not j.obudowa]
    caly = " ".join(j.tekst for j in widoczne)

    # ---- typografia: myślniki
    tekst_prozy = " ".join(j.tekst for j in proza)
    tekst_prozy = re.sub(r"\d[\d:.,]*\s*[–—-]\s*\d|\b(?:pn|pon|wt|śr|czw|pt|sob|nd|niedz)\.?\s*[–—-]\s*(?:pt|sob|nd|niedz|pn)\b",
                         " ", tekst_prozy, flags=re.I)
    pauzy = len(re.findall(r"\s—\s", tekst_prozy)) + len(re.findall(r"\w—\w", tekst_prozy))
    polpauzy = len(re.findall(r"\s–\s", tekst_prozy))
    slow = max(1, _slowa(tekst_prozy))
    if pauzy and polpauzy:
        z.dodaj("PL-MYSLNIK-MIX", plik, 1, f"w tekście „—” ×{pauzy} i „ – ” ×{polpauzy}")
    gest = (pauzy + polpauzy) * 1000 / slow
    if slow >= 300 and pauzy + polpauzy >= 4 and gest > 8:
        z.dodaj("PL-MYSLNIK-GESTOSC", plik, 1, f"{pauzy + polpauzy} myślników na {slow} słów = {gest:.1f} na 1000 (limit 8)",
                poziom="P1" if gest > 12 else "P2")
    wtr = re.findall(r"\s[—–]\s[^—–.!?]{3,80}\s[—–]\s", tekst_prozy)
    if len(wtr) >= 2:
        z.dodaj("PL-MYSLNIK-WTRACENIE", plik, 1, f"{len(wtr)}× wtrącenie między myślnikami, np. „{wtr[0].strip()[:60]}”")
    zakresy = re.findall(r"\b\d{1,2}(?::\d{2})?\s+[–—-]\s+\d{1,2}(?::\d{2})\b", caly)
    if zakresy:
        z.dodaj("PL-ZAKRES-SPACJE", plik, 1, f"zakres ze spacjami: „{zakresy[0]}”")
    proste = re.findall(r'(?<![=\w])"[^"<>]{2,80}"', caly)
    if proste:
        z.dodaj("PL-CUDZYSLOW", plik, 1, f"{len(proste)}× cudzysłów prosty, np. {proste[0][:40]}")
    sierotki = [j for j in widoczne if re.search(rf"(?:^|(?<=[\s(„]))[aiouwzAIOUWZ] (?=[{L}0-9„(])", j.tekst)]
    if sierotki:
        rx = re.compile(rf"(?:^|(?<=[\s(„]))[aiouwzAIOUWZ] (?=[{L}0-9„(])")
        n = sum(len(rx.findall(j.tekst)) for j in sierotki)
        m0 = rx.search(sierotki[0].tekst)
        wycinek = sierotki[0].tekst[max(0, m0.start() - 30):m0.end() + 25].strip()
        z.dodaj("PL-SIEROTKI", plik, sierotki[0].linia, f"{n}× jednoliterowy wyraz ze zwykłą spacją, np. „…{wycinek}…” "
                f"(<{sierotki[0].tag}>)")
    wykrz = len(re.findall(r"[" + L + r"]!(?:\s|$)", caly))
    if re.search(r"!{2,}", caly) or wykrz >= 3:
        z.dodaj("PL-WYKRZYKNIKI", plik, 1, f"{wykrz} zdań z wykrzyknikiem")

    # ---- nagłówki, tytuł, przyciski
    for j in jed:
        if j.rodzaj in ("naglowek", "tytul", "cta"):
            t = _bez_marki(j.tekst, nazwy) if j.rodzaj == "tytul" else j.tekst
            if j.rodzaj == "tytul" or j.tag in ("h1", "h2", "h3") or j.rodzaj == "cta":
                if czy_title_case(t, nazwy):
                    z.dodaj("PL-TITLE-CASE", plik, j.linia, f"<{j.tag}> „{t[:80]}”", t, klucz=f"PL-TITLE-CASE|{norm(t)}")
            if j.rodzaj == "cta" and STRZALKA.search(j.tekst):
                z.dodaj("V-STRZALKA-CTA", plik, j.linia, f"„{j.tekst[:60]}”", j.tekst, klucz=f"V-STRZALKA-CTA|{norm(j.tekst)}")
            if j.tag in ("h1", "h2", "h3") and re.search(r"\s[—–]\s", j.tekst):
                z.dodaj("PL-MYSLNIK-NAGLOWEK", plik, j.linia, f"<{j.tag}> „{j.tekst[:80]}”", j.tekst,
                        klucz=f"PL-MYSLNIK-NAGLOWEK|{norm(j.tekst)}")

    # ---- emoji, lorem, zaślepki (widoczny tekst i atrybuty)
    emo = [j for j in jed if any(ch not in EMOJI_DOZWOLONE for ch in EMOJI_RE.findall(j.tekst))]
    if emo:
        z.dodaj("V-EMOJI", plik, emo[0].linia, f"{len(emo)}× emoji, np. „{emo[0].tekst[:50]}”")
    for j in jed:
        if LOREM.search(j.tekst):
            z.dodaj("TRESC-LOREM", plik, j.linia, f"„{j.tekst[:60]}”")
        m = ZASLEPKA.search(j.tekst)
        if m:
            z.dodaj("TRESC-ZASLEPKA", plik, j.linia, f"„{m.group(0)}” w „{j.tekst[:60]}”")

    # ---- elementy
    num_poza_ol, statystyki, etykiety = [], [], []
    for w in elementy:
        kl = w.klasy()
        przod = list(w.przodkowie())
        if any(p.tag in POMIN_TAGI for p in przod):
            continue
        tekst_w = w.tekst() if w.tag not in VOID else ""
        if w.elementy() == [] and tekst_w and NUMER_OZDOBNY.match(tekst_w) and not any(p.tag == "ol" for p in przod):
            num_poza_ol.append(w)
        if w.elementy() == [] and tekst_w and STATYSTYKA.match(tekst_w) and not any(p.tag in ("td", "th", "table") for p in przod):
            statystyki.append(w)
        if re.fullmatch(r"h[12]", w.tag):
            for dz in w.elementy():
                cel = dz.tag in ("em", "i", "mark", "strong", "b") or (dz.tag == "span" and re.search(r"accent|akcent|wyroz|highlight|kolor", dz.klasy(), re.I))
                if cel and dz.tekst() and len(dz.tekst().split()) <= 3 and len(w.tekst().split()) > len(dz.tekst().split()):
                    z.dodaj("V-AKCENT-SLOWA", plik, w.linia, f"<{w.tag}> „{w.tekst()[:60]}” — wyróżnione „{dz.tekst()}”")
                    break
            if w.tag == "h2" and w.rodzic is not None:
                rodz = w.rodzic.elementy()
                i = rodz.index(w)
                if i > 0:
                    przed = rodz[i - 1]
                    if przed.tag in ("p", "span", "div", "small") and 0 < len(przed.tekst().split()) <= 6 and \
                            (ETYKIETA_KL.search(przed.klasy()) or przed.tag in ("span", "small")):
                        etykiety.append(przed)
        if w.tag == "img":
            s = w.a.get("src", "") + " " + w.a.get("srcset", "")
            if STOCK.search(s) or STOCK.search(w.a.get("alt", "")):
                z.dodaj("TRESC-STOCK", plik, w.linia, f"zdjęcie: {(STOCK.search(s) or STOCK.search(w.a.get('alt', ''))).group(0)} — {w.a.get('src', '')[:70]}")
            if w.a.get("src", "").startswith("data:") and len(w.a.get("src", "")) > 4000:
                z.dodaj("DOM-DATA-URI", plik, w.linia, f"data URI {len(w.a['src']) // 1024} kB")
            if not (w.a.get("width") and w.a.get("height")):
                z.dodaj("DOM-IMG-WH", plik, w.linia, f"{w.a.get('src', '')[:70]}")
            if "alt" not in w.a:
                z.dodaj("A11Y-ALT", plik, w.linia, f"{w.a.get('src', '')[:70]}")
        if w.tag == "source" and STOCK.search(w.a.get("srcset", "")):
            z.dodaj("TRESC-STOCK", plik, w.linia, f"zdjęcie: {w.a.get('srcset', '')[:70]}")
        if w.tag == "link":
            h = w.a.get("href", "")
            if "fonts.googleapis" in h or "fonts.gstatic" in h:
                z.dodaj("DOM-GOOGLE-FONTS", plik, w.linia, h[:70])
            if "stylesheet" in w.a.get("rel", "") and h.split("?")[0].endswith(".css") and not h.startswith(("http:", "https:", "//")) and "?v=" not in h:
                z.dodaj("DOM-CSS-WERSJA", plik, w.linia, h[:70])
        if w.tag == "script" and w.a.get("src"):
            s = w.a["src"]
            if re.search(r"\baos\b|wow\.js|animate\.css|gsap|lottie|particles|typed\.js|swiper|slick|splide|glide|flickity", s, re.I):
                z.dodaj("V-EFEKTY-BIBLIOTEKI", plik, w.linia, s[:70])
            if s.split("?")[0].endswith(".js") and not s.startswith(("http:", "https:", "//")) and "?v=" not in s:
                z.dodaj("DOM-JS-WERSJA", plik, w.linia, s[:70])
        if w.tag == "iframe" and re.search(r"google\.[a-z.]+/maps|maps\.google", w.a.get("src", "")):
            z.dodaj("DOM-MAPA-IFRAME", plik, w.linia, w.a["src"][:70])
        if w.tag in ("a", "button") and re.search(r"\brounded-full\b", kl):
            z.dodaj("V-PIGULKA", plik, w.linia, f"<{w.tag} class=\"{kl[:50]}\">")
        # siatka kart z ikonami
        dz = w.elementy()
        if len(dz) in (3, 4, 6, 8, 9):
            wspolne = set(dz[0].klasy().split())
            for x in dz[1:]:
                wspolne &= set(x.klasy().split())
            if (wspolne or all(x.tag == dz[0].tag for x in dz)) and dz[0].tag in ("div", "li", "article", "a"):
                def karta(x):
                    potomki = list(wszystkie(x))
                    ikona = any(p.tag == "svg" or (p.tag in ("i", "span", "img") and IKONA_KL.search(p.klasy() + " " + p.a.get("src", "")))
                                for p in potomki) or bool(EMOJI_RE.search(x.tekst()[:3]))
                    naglowek = any(re.fullmatch(r"h[2-5]", p.tag) or p.tag == "strong" for p in potomki)
                    opis = any(p.tag == "p" for p in potomki)
                    return ikona and naglowek and opis
                if all(karta(x) for x in dz):
                    z.dodaj("V-TRZY-KARTY", plik, w.linia, f"{len(dz)} jednakowych kart z ikoną, tytułem i opisem "
                            f"(<{dz[0].tag} class=\"{dz[0].klasy()[:40]}\">)")
    if len(num_poza_ol) >= 3:
        z.dodaj("V-NUMERY-01", plik, num_poza_ol[0].linia, f"{len(num_poza_ol)}× „{num_poza_ol[0].tekst()}” poza <ol>")
    if len(statystyki) >= 3:
        z.dodaj("V-PASEK-STATYSTYK", plik, statystyki[0].linia,
                f"{len(statystyki)} liczb typu „500+ / 98%”: " + ", ".join(s.tekst() for s in statystyki[:5]))
    if len(etykiety) >= 3:
        z.dodaj("V-ETYKIETY-NAD-H", plik, etykiety[0].linia, f"{len(etykiety)}× etykieta nad h2, np. „{etykiety[0].tekst()[:40]}”")

    # ---- wzorce w źródle
    for m in re.finditer(r"<h1\b", src, re.I):
        przed = src[max(0, m.start() - 700):m.start()]
        ln = src.count("\n", 0, m.start()) + 1
        if re.search(r"class=\"[^\"]*\b(?:pill|badge|chip|tag)\b", przed):
            z.dodaj("V-ODZNAKA-NAD-H1", plik, ln, "pigułka/odznaka tuż przed h1")
        if re.search(r"✨|✦|nowość!|>\s*new:", przed, re.I):
            z.dodaj("V-ISKRY", plik, ln, "✨/„Nowość!” tuż przed h1")
    if re.search(r"data-(?:countup|counter|count-to|count-end|target-number)=|\bcountUp\(|new CountUp|odometer", src):
        z.dodaj("V-LICZNIK-ANIM", plik, 1, "atrybut data-countup/data-counter albo biblioteka licznika")
    if caly.count("★") + caly.count("⭐") >= 5 and not re.search(r"href=\"https://(?:www\.)?(?:google\.[a-z.]+/maps|g\.page|maps\.app\.goo\.gl|"
                                                            r"(?:www\.)?facebook\.com|pl\.trustpilot|www\.znanylekarz)", src):
        z.dodaj("V-GWIAZDKI", plik, 1, "gwiazdki bez linku do serwisu z opiniami")
    if re.search(r"swiper|slick-slider|owl-carousel|splide|glide__|flickity|revslider", src, re.I):
        z.dodaj("V-SLIDER", plik, 1, "klasy karuzeli (swiper/slick/owl…)")
    if re.search(r'id="(?:preloader|loader)"|class="[^"]*\b(?:preloader|page-loader)\b', src):
        z.dodaj("V-PRELOADER", plik, 1, "element preloadera")
    if re.search(r'class="[^"]*\b(?:back-to-top|scroll-top|to-top|do-gory)\b|id="(?:back-to-top|scrollTop)"', src):
        z.dodaj("V-DO-GORY", plik, 1, "przycisk „do góry”")
    if re.search(r"connect\.facebook\.net|customerchat|tawk\.to|smartsupp|livechat|elfsight|trustindex|widget\.trustpilot", src, re.I):
        z.dodaj("DOM-WIDZET", plik, 1, "skrypt/element widżetu zewnętrznego")
    if re.search(r'class="[^"]*\b(?:cookie-banner|cookie-consent|cookies-bar|cookie-notice)\b', src) and \
            not re.search(r"googletagmanager|gtag\(|fbq\(|_ga\b|hotjar|clarity\.ms", src):
        z.dodaj("DOM-BANER-BEZ-COOKIES", plik, 1, "baner cookies")
    if re.search(r'data-aos=|class="[^"]*\b(?:wow|animate__\w+)\b', src):
        z.dodaj("V-FADE-UP-WSZEDZIE", plik, 1, "data-aos / wow / animate__ na elementach")
    if re.search(r'name="generator"[^>]*content="(?:v0|Lovable|Bolt|Framer|Wix)', src, re.I) or \
            re.search(r"lovable-tagger|gpt-engineer|v0\.dev|bolt\.new|Made with (?:❤|love)", src):
        z.dodaj("V-SYGNATURA", plik, 1, "ślad generatora")
    if re.search(r"\bbg-gradient-to-\w+[^\"]*\bfrom-(?:indigo|violet|purple|fuchsia)-\d", src):
        z.dodaj("V-GRAD-FIOLET", plik, 1, "klasy Tailwind: bg-gradient-to-* from-indigo/violet/purple")
    if re.search(r"\bbg-clip-text\b[^\"]*\btext-transparent\b|\btext-transparent\b[^\"]*\bbg-clip-text\b", src):
        z.dodaj("V-TEKST-GRADIENT", plik, 1, "klasy Tailwind: bg-clip-text text-transparent")
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', src) or \
        re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', src)
    if m and not m.group(1).startswith("https://"):
        z.dodaj("DOM-OG-WZGLEDNY", plik, 1, m.group(1)[:70])

    # ---- pozytywna reguła: pierwsze 4 akapity ≥ 12 słów w treści głównej muszą mieć konkret
    akapity = [j for j in jed if j.rodzaj == "blok" and j.tag in ("p", "li", "dd", "blockquote") and not j.obudowa
               and _slowa(j.tekst) >= 12][:4]
    for j in akapity:
        if not ma_konkret(j.tekst, nazwy):
            z.dodaj("TRESC-BEZ-KONKRETU", plik, j.linia, f"„{_cytat(j.tekst, '', 90)}”", klucz=f"TRESC-BEZ-KONKRETU|{norm(j.tekst)}")

    # ---- ta sama informacja w dwóch sekcjach jednej strony (poza nagłówkiem, stopką, nawigacją)
    widziane: dict[str, Jednostka] = {}
    for j in jed:
        if j.rodzaj not in ("blok", "naglowek") or j.obudowa or not j.region:
            continue
        for zd in re.split(r"(?<=[.!?])\s+", j.tekst):
            if _slowa(zd) < 8:
                continue
            k = hashlib.sha1(norm(zd).rstrip(".!? ").encode()).hexdigest()
            if k in widziane and widziane[k].region != j.region:
                z.dodaj("TRESC-POWTORKA", plik, j.linia, f"„{_cytat(zd, '', 90)}” — też w wierszu {widziane[k].linia}",
                        klucz=f"TRESC-POWTORKA|{plik}|{k}")
            widziane.setdefault(k, j)

    if "<style" in src:
        tresc_stylu = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", src, re.S | re.I))
        return (plik + " <style>", tresc_stylu)
    return None


# --------------------------------------------------------------------------------------------- dane klienta
POLA_NOTATEK = {"zrodla", "do_potwierdzenia", "zrodlo", "zrodlo_opis", "kolor_zrodlo", "zrodlo_plik", "$schema", "$komentarz"}
KLUCZE_TECHNICZNE = {"id", "slug", "href", "url", "plik", "zdjecie", "zdjecia", "kategoria", "typ", "tryb", "email", "telefon",
                     "domena", "logo", "logo_na_ciemnym", "font_naglowki", "font_tekst", "kolor", "kolor_dodatkowy", "tlo",
                     "branza", "data", "od", "do", "adres_roboczy", "kadr_mobilny", "licencja"}


def teksty_danych(o, sciezka=""):
    """(ścieżka, napis) każdego tekstu w danych; bez notatek, kluczy technicznych i identyfikatorów."""
    if isinstance(o, str):
        if " " in o.strip() and not re.match(r"^(?:https?:|mailto:|tel:|/|#|\.\./)", o):
            yield sciezka, o
    elif isinstance(o, dict):
        for k, v in o.items():
            if k.startswith("$") or k in POLA_NOTATEK or k in KLUCZE_TECHNICZNE:
                continue
            yield from teksty_danych(v, f"{sciezka}.{k}" if sciezka else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from teksty_danych(v, f"{sciezka}[{i}]")


def wszystkie_napisy(o, sciezka=""):
    if isinstance(o, str):
        yield sciezka, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from wszystkie_napisy(v, f"{sciezka}.{k}" if sciezka else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from wszystkie_napisy(v, f"{sciezka}[{i}]")


def _linia_w_zrodle(src: str, napis: str) -> int:
    for kand in (json.dumps(napis, ensure_ascii=False), napis[:40]):
        i = src.find(kand)
        if i >= 0:
            return src.count("\n", 0, i) + 1
    return 1


def nazwy_wlasne(firma: dict | None) -> set:
    if not firma:
        return set()
    zrodla = []
    f = firma.get("firma") or {}
    k = firma.get("kontakt") or {}
    a = k.get("adres") or {}
    zrodla += [f.get("nazwa"), f.get("nazwa_prawna"), a.get("ulica"), a.get("miasto"), a.get("wojewodztwo"),
               (firma.get("seo") or {}).get("miasto"), (firma.get("rejestr") or {}).get("wlasciciel")]
    zrodla += list(k.get("obszar_dzialania") or [])
    zrodla += [x.get("nazwa") for x in (k.get("dzialy") or []) if isinstance(x, dict)]
    wyn = set()
    for s in zrodla:
        if isinstance(s, str):
            wyn |= {w for w in re.findall(rf"[{L}][{L}-]*", s) if w[:1].isupper()}
            wyn |= {w.capitalize() for w in re.findall(rf"[{L}][{L}-]*", s) if w.isupper() and len(w) > 2}
    return wyn


# pola tresc.json z nazwami własnymi (osoby, firmy, miejsca) — ich wielkie litery nie są „Title Case”
POLA_NAZW = (("zespol", "osoby", "imie"), ("opinie", "pozycje", "autor"), ("opinie", "pozycje", "miejscowosc"),
             ("gdzie_kupic", "punkty", "nazwa"), ("gdzie_kupic", "punkty", "miasto"), ("certyfikaty", "pozycje", "wydawca"),
             ("realizacje", "pozycje", "klient"), ("realizacje", "pozycje", "miejsce"),
             ("przetargi", "pozycje", "zamawiajacy"), ("kariera", "pozycje", "miejsce"))


def nazwy_z_tresci(tresc: dict | None) -> set:
    """Wyrazy z wielkiej litery z pól-nazw treści („lek. Jan Próbny”, „Sklep Meblowy Próba”)."""
    if not isinstance(tresc, dict):
        return set()
    napisy = []
    for blok, lista, pole in POLA_NAZW:
        for poz in ((tresc.get(blok) or {}).get(lista) or []):
            if isinstance(poz, dict):
                napisy.append(poz.get(pole))
    napisy.append((((tresc.get("kariera") or {}).get("kontakt")) or {}).get("osoba"))
    wyn = set()
    for s in napisy:
        if isinstance(s, str):
            wyn |= {w for w in re.findall(rf"[{L}][{L}-]*", s) if w[:1].isupper()}
    return wyn


def sprawdz_dane(katalog: Path, z: Zbior, nazwy: set, indeks: list):
    """Napisy z data/*.json i akapity z data/**/*.md; indeks: [(norm tekstu, plik, pole)] do wskazania pola przy wynikach z dist."""
    for p in sorted(katalog.rglob("*.json")):
        if p.name == "slop-ok.json" or "assets" in p.relative_to(katalog).parts:
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        try:
            dane = json.loads(src)
        except json.JSONDecodeError:
            continue
        wysw = sciezka_wysw(p)
        for pole, napis in teksty_danych(dane):
            indeks.append((norm(napis), wysw, pole))
            rodzaj = "naglowek" if re.search(r"(?:^|\.)(?:naglowek|tytul|nazwa)$", pole) else "tekst"
            dodaj_tekst(z, wysw, _linia_w_zrodle(src, napis), napis, rodzaj, nazwy, pole=pole)
            if LOREM.search(napis):
                z.dodaj("TRESC-LOREM", wysw, _linia_w_zrodle(src, napis), f"„{napis[:60]}”", pole=pole)
            if rodzaj == "naglowek" and czy_title_case(napis, nazwy):
                z.dodaj("PL-TITLE-CASE", wysw, _linia_w_zrodle(src, napis), f"„{napis[:80]}”", napis, pole=pole,
                        klucz=f"PL-TITLE-CASE|{norm(napis)}")
            if any(ch not in EMOJI_DOZWOLONE for ch in EMOJI_RE.findall(napis)):
                z.dodaj("V-EMOJI", wysw, _linia_w_zrodle(src, napis), f"„{napis[:50]}”", pole=pole)
        # zdjęcia stockowe/AI: także w notatkach (źródło, plik)
        for pole, napis in wszystkie_napisy(dane):
            if re.search(r"(?:^|\.)(?:\$schema|\$komentarz)$", pole):
                continue
            m = STOCK.search(napis)
            if m and not re.search(r"(?:^|\.)(?:do_potwierdzenia)", pole):
                z.dodaj("TRESC-STOCK", wysw, _linia_w_zrodle(src, napis), f"„{m.group(0)}” w „{napis[:70]}”", m.group(0), pole=pole)
    for p in sorted(katalog.rglob("*.md")):
        src = p.read_text(encoding="utf-8", errors="replace")
        wysw = sciezka_wysw(p)
        linie = src.split("\n")
        start = 0
        if linie and linie[0].strip() == "---":
            for i in range(1, len(linie)):
                if linie[i].strip() == "---":
                    start = i + 1
                    break
        akapit, od = [], start + 1
        for i in range(start, len(linie) + 1):
            wiersz = linie[i] if i < len(linie) else ""
            if wiersz.strip() == "" or re.match(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+\.\s|>)", wiersz):
                if akapit:
                    _md_akapit(" ".join(akapit), wysw, od, z, nazwy, indeks)
                akapit, od = [], i + 2
                if wiersz.strip():
                    tresc = re.sub(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+\.\s|>\s?)", "", wiersz)
                    rodzaj = "naglowek" if wiersz.lstrip().startswith("#") else "tekst"
                    _md_akapit(tresc, wysw, i + 1, z, nazwy, indeks, rodzaj)
                continue
            akapit.append(wiersz)


def _md_akapit(t, wysw, linia, z, nazwy, indeks, rodzaj="tekst"):
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_`]{1,3}", "", t)
    indeks.append((norm(t), wysw, f"wiersz {linia}"))
    dodaj_tekst(z, wysw, linia, t, rodzaj, nazwy)
    if rodzaj == "naglowek" and czy_title_case(t, nazwy):
        z.dodaj("PL-TITLE-CASE", wysw, linia, f"„{t[:80]}”", t, klucz=f"PL-TITLE-CASE|{norm(t)}")


def sprawdz_marke(katalog: Path, firma: dict, z: Zbior):
    if not firma or firma.get("przyklad"):
        return
    m = firma.get("marka") or {}
    plik = sciezka_wysw(katalog / "firma.json")
    if not m.get("kolor"):
        z.dodaj("MARKA-DOMYSLNA", plik, 1, "marka.kolor = null — strona ma szary #555555 z szablonu", pole="marka.kolor")
        return
    trojka = ((m.get("kolor") or "").upper(), m.get("font_naglowki"), m.get("font_tekst"))
    wzory = {("#C8471F", "archivo", "public-sans"): "przykład z docs/KONTRAKT.md §4.1"}
    for fp in sorted((KORZEN / "przyklady").glob("*/data/firma.json")):
        if fp.resolve() == (katalog / "firma.json").resolve():
            continue
        try:
            mk = json.loads(fp.read_text(encoding="utf-8")).get("marka") or {}
        except (OSError, json.JSONDecodeError):
            continue
        wzory[((mk.get("kolor") or "").upper(), mk.get("font_naglowki"), mk.get("font_tekst"))] = \
            f"marka przykładu {fp.parent.parent.name} ({sciezka_wysw(fp)})"
    if trojka in wzory:
        z.dodaj("MARKA-DOMYSLNA", plik, 1, f"kolor {trojka[0]} i kroje {trojka[1]} + {trojka[2]} = {wzory[trojka]}", pole="marka")


# --------------------------------------------------------------------------------------------- zwolnienia

def wczytaj_zwolnienia(katalogi: list[Path], z: Zbior) -> list[dict]:
    wyn = []
    for k in katalogi:
        p = k / "slop-ok.json"
        if not p.is_file():
            continue
        try:
            dane = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            z.dodaj("SLOP-OK-BEZ-POWODU", sciezka_wysw(p), e.lineno, f"niepoprawny JSON: {e.msg}")
            continue
        lista = dane.get("zwolnienia", []) if isinstance(dane, dict) else dane
        for i, x in enumerate(lista if isinstance(lista, list) else []):
            if not isinstance(x, dict) or not x.get("id"):
                z.dodaj("SLOP-OK-BEZ-POWODU", sciezka_wysw(p), 1, f"pozycja [{i}] bez „id”")
                continue
            if len((x.get("powod") or "").strip()) < 10:
                z.dodaj("SLOP-OK-BEZ-POWODU", sciezka_wysw(p), 1, f"[{i}] {x['id']}: brak powodu", pole=f"[{i}].powod")
                continue
            wyn.append({"id": x["id"], "powod": x["powod"].strip(), "gdzie": x.get("gdzie"), "plik": sciezka_wysw(p),
                        "nr": i, "uzyte": 0})
    return wyn


def _pasuje(zw: dict, w: Wynik) -> bool:
    if zw["id"] != w.id and not (zw["id"].endswith("*") and w.id.startswith(zw["id"][:-1])):
        return False
    g = (zw.get("gdzie") or "").strip()
    if not g:
        return True
    miejsca = [w.plik] + list(w.tez)
    return any(g in m for m in miejsca) or g in (w.pole or "") or norm(g) in norm(w.komunikat + " " + w.fragment)


def zwolnione_w_css(w: Wynik, zrodla: dict) -> str | None:
    src = zrodla.get(w.plik)
    if not src:
        return None
    linie = src.split("\n")
    for i in range(max(0, w.linia - 2), min(len(linie), w.linia + 6)):
        m = re.search(r"slop-ok:\s*([\w*-]+(?:\s*,\s*[\w*-]+)*)\s*([^*]*)", linie[i])
        if m and (w.id in [x.strip() for x in m.group(1).split(",")]):
            return m.group(2).strip() or ""
    return None


# --------------------------------------------------------------------------------------------- przebieg

def zbierz(sciezki: list[str]):
    html_pliki, css_pliki, katalogi_danych = [], [], []
    for s in sciezki:
        p = Path(s)
        if p.is_file():
            if p.suffix in (".html", ".htm"):
                html_pliki.append(p)
            elif p.suffix == ".css":
                css_pliki.append(p)
            continue
        if not p.is_dir():
            print(f"lint_slop: nie ma ścieżki {s}", file=sys.stderr)
            continue
        if (p / "firma.json").is_file() or (p.name == "data" and not (p / "index.html").exists()):
            katalogi_danych.append(p)
            continue
        for kat, podkat, pliki in os.walk(p):
            podkat[:] = sorted(d for d in podkat if d not in POMIN_KATALOGI and not d.startswith("."))
            for f in sorted(pliki):
                fp = Path(kat) / f
                if f.endswith((".html", ".htm")):
                    html_pliki.append(fp)
                elif f.endswith(".css"):
                    css_pliki.append(fp)
    return html_pliki, css_pliki, katalogi_danych


def uruchom(sciezki: list[str], produkcja: bool = False) -> dict:
    z = Zbior()
    html_pliki, css_pliki, kat_danych = zbierz(sciezki)
    firma = None
    for k in kat_danych:
        if (k / "firma.json").is_file():
            try:
                firma = json.loads((k / "firma.json").read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    nazwy = nazwy_wlasne(firma)
    for k in kat_danych:
        if (k / "tresc.json").is_file():
            try:
                nazwy |= nazwy_z_tresci(json.loads((k / "tresc.json").read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass

    # 1. strona (dist)
    teksty_stron, css_teksty = [], []
    for p in html_pliki:
        src = p.read_text(encoding="utf-8", errors="replace")
        styl = sprawdz_strone(sciezka_wysw(p), src, z, nazwy, teksty_stron)
        if styl:
            css_teksty.append(styl)
    for p in css_pliki:
        css_teksty.append((sciezka_wysw(p), p.read_text(encoding="utf-8", errors="replace")))
    reguly = [r for plik, t in css_teksty for r in reguly_css(t, plik)]
    if css_teksty:
        sprawdz_css(reguly, css_teksty, z)
    wyniki_strony = {w.klucz for w in z.lista}

    # 2. dane klienta — wynik z tym samym kluczem co na stronie dopisuje pole; napis, którego nie ma na stronie → P2
    indeks: list = []
    zd = Zbior()
    for k in kat_danych:
        sprawdz_dane(k, zd, nazwy, indeks)
        if (k / "firma.json").is_file():
            sprawdz_marke(k, firma, zd)
    for w in zd.lista:
        if w.klucz in wyniki_strony:
            st = z._po_kluczu[w.klucz]
            if not st.pole and w.pole:
                st.pole = f"{w.plik} → {w.pole}"
            continue
        if html_pliki and w.id in {r[0] for r in REGULY_TEKSTU} | {"PL-TITLE-CASE", "TRESC-LOREM", "V-EMOJI"}:
            w.poziom = "P2"
            w.komunikat += " (tego tekstu nie ma na stronie — pole ukryte albo nieużywane)"
        z.lista.append(w)
        z._po_kluczu[w.klucz] = w
    # wynik z dist bez pola: poszukaj napisu w danych
    for w in z.lista:
        if w.pole or not w.fragment or not indeks:
            continue
        cel = norm(w.fragment)
        if len(cel) < 6:
            continue
        for tekst, plik, pole in indeks:
            if cel in tekst:
                w.pole = f"{plik} → {pole}"
                break

    # 3. zwolnienia
    zwolnienia = wczytaj_zwolnienia(kat_danych, z)
    zrodla_css = {plik: t for plik, t in css_teksty}
    aktywne, zwolnione = [], []
    for w in z.lista:
        powod = None
        if w.id.startswith("SLOP-OK"):
            aktywne.append(w)
            continue
        for zw in zwolnienia:
            if _pasuje(zw, w):
                if w.poziom == "P0":
                    z_ = Wynik("SLOP-OK-P0", REGULY["SLOP-OK-P0"][0], zw["plik"], 1,
                               f"[{zw['nr']}] {zw['id']}: {w.komunikat[:80]}", naprawa=REGULY["SLOP-OK-P0"][1])
                    aktywne.append(z_)
                    zw["uzyte"] += 1
                    break
                powod = zw["powod"]
                zw["uzyte"] += 1
                break
        if powod is None and w.poziom != "P0":
            powod = zwolnione_w_css(w, zrodla_css)
        if powod is not None:
            zwolnione.append((w, powod))
        else:
            aktywne.append(w)
    for zw in zwolnienia:
        if not zw["uzyte"]:
            aktywne.append(Wynik("SLOP-OK-NIEUZYWANE", "P2", zw["plik"], 1, f"[{zw['nr']}] {zw['id']}"
                                 + (f" (gdzie: {zw['gdzie']})" if zw.get("gdzie") else ""),
                                 naprawa=REGULY["SLOP-OK-NIEUZYWANE"][1]))
    aktywne.sort(key=lambda w: (KOLEJNOSC[w.poziom], w.id, w.plik, w.linia))
    licz = {p: sum(1 for w in aktywne if w.poziom == p) for p in POZIOMY}
    kod = 2 if licz["P0"] else (1 if produkcja and licz["P1"] else 0)
    return {"wyniki": aktywne, "zwolnione": zwolnione, "liczby": licz, "kod": kod,
            "pliki": {"html": len(html_pliki), "css": len(css_pliki), "dane": [sciezka_wysw(k) for k in kat_danych]}}


NAGLOWKI_POZIOMOW = {"P0": "P0 — błąd, blokuje publikację", "P1": "P1 — ostrzeżenie (w --produkcja błąd, chyba że zwolnione)",
                     "P2": "P2 — informacja"}


def raport_tekst(r: dict, produkcja: bool, minimum: str) -> str:
    out = []
    for poz in POZIOMY:
        if KOLEJNOSC[poz] > KOLEJNOSC[minimum]:
            continue
        lista = [w for w in r["wyniki"] if w.poziom == poz]
        if not lista:
            continue
        out.append(f"\n{NAGLOWKI_POZIOMOW[poz]} ({len(lista)}):")
        for w in lista:
            out.append(f"  {w.id}  {w.plik}:{w.linia}" + (f"  [{w.pole}]" if w.pole else ""))
            out.append(f"      {w.komunikat}")
            if w.tez:
                out.append("      też: " + ", ".join(w.tez[:6]) + (f" i {len(w.tez) - 6} innych" if len(w.tez) > 6 else ""))
            if w.naprawa:
                out.append(f"      → {w.naprawa}")
    if r["zwolnione"]:
        out.append(f"\nZwolnione (slop-ok) ({len(r['zwolnione'])}):")
        for w, powod in r["zwolnione"]:
            out.append(f"  {w.id}  {w.plik}:{w.linia} — {powod}")
    l_ = r["liczby"]
    out.append(f"\nlint_slop: P0 {l_['P0']} · P1 {l_['P1']} · P2 {l_['P2']} · zwolnione {len(r['zwolnione'])} "
               f"({r['pliki']['html']} HTML, {r['pliki']['css']} CSS" + (", dane" if r["pliki"]["dane"] else "") + ")"
               + (" — tryb produkcja" if produkcja else ""))
    return "\n".join(out).lstrip("\n")


def katalog_regul() -> str:
    wyn = []
    for rid in sorted(REGULY, key=lambda k: (KOLEJNOSC[REGULY[k][0]], k)):
        poz, nap = REGULY[rid]
        wyn.append(f"{poz}  {rid:22} {nap}")
    return "\n".join(wyn)


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    if "--reguly" in argv:
        if "--json" in argv:
            print(json.dumps({k: {"poziom": v[0], "naprawa": v[1]} for k, v in REGULY.items()}, ensure_ascii=False, indent=1))
        else:
            print(katalog_regul())
        return 0
    produkcja = "--produkcja" in argv
    minimum = next((a.split("=", 1)[1] for a in argv if a.startswith("--min=")), "P2")
    if minimum not in POZIOMY:
        print("lint_slop: --min=P0|P1|P2", file=sys.stderr)
        return 2
    sciezki = [a for a in argv if not a.startswith("--")]
    if not sciezki:
        sciezki = [str(KORZEN / "dist"), str(KORZEN / "data")]
    r = uruchom(sciezki, produkcja)
    if "--json" in argv:
        print(json.dumps({
            "wersja": 1, "produkcja": produkcja, "kod": r["kod"], "liczby": r["liczby"],
            "wyniki": [w.slownik() for w in r["wyniki"] if KOLEJNOSC[w.poziom] <= KOLEJNOSC[minimum]],
            "zwolnione": [dict(w.slownik(), powod=p) for w, p in r["zwolnione"]],
        }, ensure_ascii=False, indent=1))
    else:
        print(raport_tekst(r, produkcja, minimum))
    return r["kod"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
