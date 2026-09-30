# Kwestionariusz dla właściciela firmy

Na podstawie tych odpowiedzi powstaje strona. Wystarczą krótkie odpowiedzi i zdjęcia z telefonu.
Czego Pan/Pani nie wie albo nie chce pokazywać — proszę zostawić puste: **strona pokaże tylko to, co prawdziwe**,
bez tekstów „na wypełnienie”. Część danych (KRS, NIP, adres, godziny z Google) sprawdzimy sami — wtedy wystarczy
je potwierdzić.

Oznaczenia przy odpowiedzi: ✔ potwierdzone · ? do sprawdzenia · ✘ nie pokazujemy.
W nawiasie — pole w danych strony (dla osoby, która buduje stronę).

## A. Podstawy

1. Nazwa firmy, jak ma być na stronie i szyldzie: ____ (`firma.nazwa`)
2. Pełna nazwa prawna i forma (JDG, s.c., sp. j., sp. z o.o., sp. k.): ____ (`firma.nazwa_prawna`, `rejestr.forma_prawna`)
3. NIP, REGON, KRS (spółki): ____ (`rejestr.*` — sprawdzamy w KRS / CEIDG)
4. Adres siedziby i adres, pod który przyjeżdżają klienci (jeśli inny); gdzie wejście, brama, parking: ____
   (`kontakt.adres`, `kontakt.geo`, `kontakt.dojazd`)
5. Czy lokal jest dostępny dla osób na wózku (próg, winda, toaleta)? ____ (`kontakt.dostepnosc_lokalu`)
6. Główny telefon (ten na przycisku „Zadzwoń”) i e-mail do zapytań: ____ (`kontakt.telefon`, `kontakt.email`)
7. Inne telefony: kto odbiera, w jakiej sprawie (np. „zamówienia betonu — 600 000 000”): ____ (`kontakt.dzialy`)
8. Godziny: każdy dzień tygodnia; przerwy; osobne godziny (kuchnia, telefon, magazyn); sezon; święta: ____ (`godziny`)
9. Obszar działania: miejscowości, powiaty albo „do X km”: ____ (`kontakt.obszar_dzialania`)
10. Jak szybko odpowiadacie na zapytania (tylko jeśli zawsze się to udaje)? ____ (`kontakt.czas_odpowiedzi`)
11. Domena: czy jest? Kto ma dostęp do jej ustawień (DNS) i do skrzynki e-mail? ____ (`firma.domena`, `docs/PRZEKAZANIE.md`)
12. Rok założenia (i ewentualnie ważne daty: zmiana właściciela, nowa hala): ____ (`firma.rok_zalozenia`, `o_firmie`)

## B. Co dokładnie robicie

1. Jednym zdaniem: co, dla kogo, gdzie: ____ (`firma.opis`, `hero`)
2. Lista usług lub produktów, każda 1–2 zdania — tak, jak nazywają je klienci: ____ (`oferta`, `produkty`, `menu`)
3. Zakres każdej usługi (co wchodzi, czego nie robicie): ____ (`oferta.pozycje[].zakres`)
4. Ceny, które można pokazać (dokładne albo „od–do”, jednostka: zł/m², zł/h, za sztukę). Dla konsumentów zawsze brutto.
   Data, od kiedy obowiązują: ____ (`cennik`, `oferta.pozycje[].cena`)
5. Ile trwa typowe zlecenie / wizyta / realizacja: ____ (`oferta.pozycje[].czas`)
6. Jak wygląda współpraca krok po kroku (od telefonu do odbioru) i ile trwa każdy krok: ____ (`proces`)
7. Zasady: zadatek, płatności, gwarancja, ważność wyceny, rezerwacje, dostawa, odwołanie wizyty: ____ (`zasady`)
8. Realizacje: co, gdzie, rok, jedna liczba (km, m², sztuki), zdjęcia; czy klienta można wymienić z nazwy: ____
   (`realizacje`; zamówienia publiczne sprawdzamy w BZP — `przetargi`)
9. Fakty, które da się sprawdzić: sprzęt, uprawnienia, certyfikaty (numer, wydawca, rok), członkostwa, nagrody: ____
   (`o_firmie.fakty`, `certyfikaty`, `liczby`)
10. Najczęstsze pytania klientów przez telefon — i odpowiedzi: ____ (`faq`)
11. Kto ma być na stronie z zespołu: imię, rola, jeden fakt; czy jest zgoda na zdjęcie: ____ (`zespol`)
12. Opinie: link do profilu w Google / na Facebooku; czy i jak sprawdzacie, że opinie są od klientów: ____ (`opinie`)
13. Czy są stałe ogłoszenia (urlop, zmiana godzin), oferty pracy, pliki do pobrania (katalog, karta techniczna)? ____
    (`ogloszenie`, `kariera`, `do_pobrania`)

## C. Wygląd

1. Logo — najlepiej plik wektorowy (SVG, PDF, AI, EPS) albo PNG ≥ 1000 px; wersja na ciemne tło, jeśli jest: ____ (`marka.logo`)
2. Zdjęcia szyldu, samochodu firmowego, wizytówki, ulotki (z nich bierzemy kolory i styl): ____ (`marka.kolor`)
3. Kolory firmy (jeśli są ustalone) i kolory, których **nie** chcecie: ____
4. Strony, które się Panu/Pani podobają — i co konkretnie: ____
5. Poprzednia strona / Facebook / Instagram / profil w Google — adresy: ____ (`social.*`)

## D. Funkcje

1. Formularz zapytania: tak / nie. Na jaki adres mają przychodzić wiadomości? ____ (`funkcje.formularz`)
2. Mapa: wystarczy przycisk „Wyznacz trasę”, czy mapa na stronie (ładowana dopiero po kliknięciu)? ____ (`funkcje.mapa`)
3. Statystyki odwiedzin bez ciasteczek (Cloudflare) — tak / nie: ____ (`funkcje.statystyki_cf_token`)
4. Aktualności (kto i jak często będzie je pisał?): ____ (`data/aktualnosci/`)
5. Sprzedajecie online konsumentom? (ważne dla informacji o dostępności): ____ (`funkcje.strona_dostepnosci`)
6. Kto po oddaniu strony będzie zmieniał godziny, ceny, ogłoszenia? ____ (`docs/PRZEKAZANIE.md`)

## E. Zdjęcia

Przy każdym zdjęciu proszę napisać: **co przedstawia** (miejsce, rok), **kto je zrobił** (firma, fotograf — imię
i nazwisko) i **czy widać na nim osoby** (jeśli tak — czy te osoby zgodziły się na publikację).
Nie wysyłamy zdjęć z internetu, stockowych ani zdjęć klientów z Google — tylko własne.
Najlepiej: poziome, w dzień, ostre, pełna rozdzielczość z telefonu (nie z komunikatora — kompresuje).

| Branża | Czego potrzebujemy |
|---|---|
| restauracja, kawiarnia | 1–2 wnętrza (szeroko, w dzień), fasada z szyldem, 6–12 dań (z góry i pod kątem 45°, światło dzienne), karta (zdjęcie lub PDF), ogródek, jeśli jest |
| budowlana, drogowa | 3–6 realizacji (najlepiej przed i po, z miejscem i rokiem), sprzęt z logo, ekipa przy pracy (za zgodą), baza lub plac, wytwórnia lub warsztat |
| producent | produkty na jasnym tle i w aranżacji, hala i etapy produkcji, materiały (tkaniny, drewno, próbki), logo na produkcie, salon sprzedaży |
| usługi (warsztat, salon, biuro) | wejście od ulicy (jak nas znaleźć), wnętrze, stanowisko pracy, zespół (za zgodą), efekty pracy (za zgodą klienta) |
| gabinet | wejście i poczekalnia, gabinet, sprzęt, specjaliści (portret za zgodą), dojazd / parking |

Tabela do wypełnienia (albo nazwy plików w wiadomości):

| Plik | Co przedstawia (miejsce, rok) | Autor | Osoby na zdjęciu / zgoda |
|---|---|---|---|
| | | | |
