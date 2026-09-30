# Co zawiera strona zbudowana na SZABLONIE

Spis dla właściciela firmy: co dostaje razem ze stroną i po co mu to. Każda pozycja istnieje w szablonie —
część modułów pojawia się tylko wtedy, gdy firma ma na nie prawdziwe dane (np. realizacje, opinie, godziny).
Wersję dla konkretnej firmy, z zaznaczeniem, co jest włączone: `python3 tools/co_zawiera.py --klient .`

## Treść i sekcje

- **Pierwszy ekran „kto, co, gdzie”: nagłówek z usługą i miejscowością, jedno zdanie konkretu, własne zdjęcie z podpisem i przycisk „Zadzwoń”** — Klient w kilka sekund wie, że trafił do właściwej firmy, i może od razu zadzwonić.
- **Na telefonie nazwa, miejscowość, telefon i dzisiejsze godziny widoczne bez przewijania** — Większość klientów lokalnych szuka firmy na telefonie i chce tylko zadzwonić albo dojechać.
- **Status „Otwarte do 15:00 / Zamknięte, otwieramy jutro o 7:00” liczony w czasie polskim, z podświetleniem dzisiejszego dnia** *(gdy są dane)* — Odpowiada na najczęstsze pytanie przed wizytą — także wtedy, gdy ktoś ogląda stronę z zagranicy.
- **Godziny otwarcia z kilkoma przedziałami, osobnymi godzinami (np. kuchnia, wytwórnia) i wyjątkami świątecznymi** *(gdy są dane)* — Jedno źródło zasila tabelę, status i dane dla Google, więc godziny nigdy się nie rozjadą.
- **Przypomnienie w buildzie o godzinach na święta (45 dni wcześniej, z Wigilią jako dniem wolnym od 2025 r.)** *(gdy są dane)* — Nieaktualne godziny w święta to najczęstsza skarga klientów lokali.
- **Ogłoszenie z datą ważności („24–26.12 nieczynne”), które samo znika po terminie** *(gdy są dane)* — Pilna informacja jest na górze strony tylko wtedy, gdy obowiązuje.
- **Oferta: usługi z zakresem prac, czasem wykonania i ceną albo widełkami; własne zdjęcia zamiast ikon** *(gdy są dane)* — Klient porównuje konkrety, a nie hasła — konkret skraca rozmowę telefoniczną.
- **Podstrony usług — tylko gdy jest dość treści (opis, zdjęcie, cena lub zakres)** *(gdy są dane)* — Każda podstrona odpowiada na konkretne wyszukiwanie w Google, bez pustych stron „na miasto”.
- **Cennik w HTML: ceny brutto dla konsumentów (netto tylko dla firm, wyraźnie opisane), data cennika, PDF jako dodatek** *(gdy są dane)* — Ceny na stronie odsiewają niepasujące zapytania i są zgodne z ustawą o informowaniu o cenach.
- **Karta dań: ceny (albo wyraźne „ceny w lokalu”), porcje, oznaczenia wege i ostre, alergeny (14 grup UE), data karty, wersja do druku** *(gdy są dane)* — Gość sprawdza menu przed wizytą; alergeny są wymagane przepisami UE.
- **Katalog produktów z parametrami, zdjęciami i filtrem kategorii (działa też bez JavaScriptu)** *(gdy są dane)* — Hurtownik albo klient od razu znajduje model i parametry, zamiast dzwonić o katalog.
- **Realizacje: miejsce, rok, jedna liczba (km, m²), zdjęcia, filtr kategorii i tryb „klient prywatny”** *(gdy są dane)* — Sprawdzalne realizacje przekonują bardziej niż zapewnienia o doświadczeniu.
- **Tabela zamówień publicznych: zadanie, zamawiający, rok, źródło (Biuletyn Zamówień Publicznych)** *(gdy są dane)* — Dla firm budowlanych to najmocniejsza referencja — każdy wiersz można sprawdzić.
- **Galeria zdjęć z podpisami** *(gdy są dane)* — Pokazuje prawdziwe miejsce i prace firmy.
- **Przebieg współpracy jako numerowana lista kroków z terminem lub rezultatem każdego kroku** *(gdy są dane)* — Klient wie, co go czeka i ile to potrwa, zanim zadzwoni.
- **Zasady: płatności, gwarancja, zadatek, ważność wyceny, rezerwacje, dostawa** *(gdy są dane)* — Odpowiada na pytania, które inaczej padają przy każdym zapytaniu.
- **Pytania i odpowiedzi — prawdziwe pytania klientów, rozwijane** *(gdy są dane)* — Mniej telefonów z tymi samymi pytaniami; treść pomaga w wyszukiwarce.
- **O firmie: historia, zdjęcie i fakty (rok założenia, sprzęt, uprawnienia); dłuższy tekst na podstronie /o-firmie** *(gdy są dane)* — Konkretna historia buduje zaufanie lepiej niż slogan.
- **Zespół: imię, rola, jeden fakt; zdjęcie tylko za zgodą osoby, właściciel pierwszy** *(gdy są dane)* — Klient wie, z kim rozmawia; zgoda na wizerunek chroni firmę.
- **Liczby z datą i źródłem (blok ukryty, gdy jest mniej niż dwie)** *(gdy są dane)* — Każda liczba jest prawdziwa i sprawdzalna — bez „500+ zadowolonych klientów”.
- **Opinie: ocena zbiorcza z linkiem do źródła, do 3 cytatów i zdanie, jak firma weryfikuje opinie** *(gdy są dane)* — Wiarygodne opinie sprzedają, a zdanie o weryfikacji jest wymagane przez dyrektywę Omnibus.
- **Certyfikaty i uprawnienia z numerem, wydawcą, rokiem i skanem; wygasłe znikają same** *(gdy są dane)* — Zamawiający i klienci biznesowi sprawdzają uprawnienia przed zleceniem.
- **Aktualności z własnymi adresami** *(gdy są dane)* — Świeże wpisy pokazują, że firma działa, i dają Google nowe treści.
- **Kanał RSS aktualności** *(opcja)* — Stali klienci i portale lokalne dostają nowe wpisy automatycznie.
- **Oferty pracy z terminem ważności (po terminie znikają) i danymi dla Google Jobs** *(gdy są dane)* — Ogłoszenie trafia do wyszukiwarki ofert pracy bez płatnych portali.
- **Pliki do pobrania z typem, rozmiarem i liczbą stron („PDF, 240 KB, 2 strony”)** *(gdy są dane)* — Klient wie, co pobiera, zanim kliknie — szczególnie na telefonie.
- **Współpraca dla firm (warunki hurtowe, dystrybucja)** *(gdy są dane)* — Partnerzy B2B znajdują warunki bez pytania mailem.
- **Gdzie kupić: punkty sprzedaży pogrupowane według województw** *(gdy są dane)* — Klient producenta od razu znajduje najbliższy sklep.
- **Kontakt: klikalny telefon i e-mail, adres, telefony działów (kto, w jakiej sprawie), dojazd i dostępność lokalu** *(gdy są dane)* — Klient dzwoni od razu pod właściwy numer, a nie do centrali.
- **Przycisk „Wyznacz trasę” prowadzący do nawigacji po współrzędnych wejścia** *(gdy są dane)* — Jedno dotknięcie na telefonie uruchamia nawigację do właściwej bramy, nie do środka działki.
- **Formularz zapytania (3–4 pola, podpowiedzi przeglądarki, błędy przy polach, także bez JavaScriptu — strona z opisem, co poprawić); bez serwera — gotowa wiadomość e-mail** *(opcja)* — Zapytanie wysyła się w minutę także z telefonu i trafia prosto do skrzynki firmy.
- **Pasek „Zadzwoń / Wyznacz trasę” na telefonie, który pokazuje się, gdy przycisków nie widać na ekranie** — Najważniejsza akcja jest zawsze pod kciukiem i nie dubluje przycisków z pierwszego ekranu.
- **Stopka z danymi rejestrowymi według formy prawnej (nazwa, adres, KRS i sąd, NIP, REGON, kapitał albo właściciel JDG)** — Wymóg prawa (m.in. art. 206 KSH) i sygnał, że firma jest prawdziwa.
- **Strony 404, „Dziękujemy” i „Błąd wysyłki” z telefonem i przydatnymi linkami** — Zepsuty link nie gubi klienta — zawsze ma drogę do kontaktu.
- **Sekcje bez prawdziwych danych nie powstają; niepewne fakty trafiają na listę „Do potwierdzenia”** — Na stronie nie ma zmyślonych liczb, cen ani tekstów zastępczych.

## Wygląd

- **Kolory z logo i szyldu firmy, zamienione na paletę z kontrastem sprawdzanym przy każdym buildzie** — Strona wygląda jak ta firma, a nie jak szablon, i jest czytelna dla każdego.
- **Dwa kroje pisma z biblioteki szablonu dobrane do branży, z polskimi znakami** — Spójny, profesjonalny wygląd bez „typowego wyglądu stron z AI”.
- **Polska typografia automatycznie: twarde spacje po „w”, „z”, między liczbą a jednostką, półpauzy, „polskie cudzysłowy”** — Tekst wygląda na złożony przez człowieka, nie przez maszynę.
- **Układ dopasowany do treści: tabele, listy, duże własne zdjęcia, cienkie linie zamiast kart z cieniem** — Strona jest rzeczowa i różni się od tysięcy stron z tego samego szablonu.
- **Kontrola „AI slop” w każdym buildzie: frazesy („kompleksowe usługi”), emoji, gradienty, liczniki „500+”** — Tekst i wygląd nie zdradzają automatu — klient czyta fakty.
- **Zdjęcia kadrowane według punktu ostrości, z osobnym kadrem na telefon** — Najważniejszy fragment zdjęcia widać na każdym ekranie.
- **Wersja do druku karty, cennika, godzin i dojazdu** — Klient drukuje menu czy dojazd bez menu strony i reklam.
- **Jedno subtelne wejście pierwszego ekranu (wyłączone dla osób, które ograniczają animacje)** *(opcja)* — Odrobina ruchu bez spowalniania strony i bez chowania nagłówka.

## Szybkość

- **Gotowe pliki HTML bez WordPressa, wtyczek i bibliotek JavaScript; strona działa też bez JavaScriptu** — Szybkie ładowanie na słabym zasięgu i nic do aktualizowania co tydzień.
- **Zdjęcia w AVIF, WebP i JPEG w kilku rozmiarach; niżej na stronie ładowane dopiero przy przewijaniu** — Telefon pobiera tylko to, co pokazuje — mniej danych, szybszy pierwszy ekran.
- **Fonty z własnego serwera z zamiennikiem o tych samych wymiarach** — Tekst nie „skacze” przy ładowaniu i nie czeka na obcy serwer.
- **Pliki CSS i JS z wersją w adresie i rocznym czasem w pamięci przeglądarki** — Powracający klient ładuje stronę natychmiast, a po zmianie od razu widzi nową wersję.
- **Limity wagi sprawdzane przy każdym buildzie (zdjęcia, CSS, JS, HTML)** — Strona nie zwalnia z czasem, gdy przybywa treści.
- **Hosting na sieci Cloudflare (serwery blisko odwiedzającego)** *(opcja)* — Szybko z każdego miejsca, bez opłat za serwer.

## Widoczność w Google (SEO)

- **Tytuł karty „usługa miejscowość – firma” i opis inny na każdej podstronie** — Google pokazuje właściwą podstronę na właściwe zapytanie.
- **Dane strukturalne JSON-LD: rodzaj firmy, adres, współrzędne, telefon, godziny, NIP, profile społecznościowe, okruszki** — Google rozumie, czym jest firma i gdzie jest — lepsza widoczność w wynikach i w Mapach.
- **Dane strukturalne treści: karta dań, produkty z ceną, usługi, oferty pracy, artykuły — tylko przy prawdziwych danych; bez własnych „gwiazdek”** — Szansa na bogate wyniki bez ryzyka kary za zawyżone oceny.
- **Podgląd przy udostępnianiu (Facebook, Messenger, WhatsApp): zdjęcie 1200 × 630 z pełnym adresem** — Link wysłany znajomemu wygląda porządnie i zachęca do kliknięcia.
- **sitemap.xml z datami zmian, robots.txt z decyzją o botach AI, adres kanoniczny każdej strony** — Wyszukiwarki szybciej znajdują nowe treści i nie dublują stron.
- **Jeden nagłówek h1 i poprawna kolejność nagłówków, opisowe linki (nigdy „Czytaj więcej”)** — Wyszukiwarka i czytnik ekranu rozumieją strukturę strony.
- **Adresy bez „.html” i przekierowania starych adresów (_redirects)** — Linki ze starej strony i z Google dalej działają po zmianie strony.
- **Pytania i odpowiedzi jako FAQPage (opcjonalnie)** *(opcja)* — Dodatkowa szansa na widoczność pytań w wynikach.
- **Nocna przebudowa strony (ogłoszenia, święta, rok w stopce zawsze aktualne) — po ustawieniu Deploy Hook w Cloudflare (docs/CLOUDFLARE.md)** *(opcja)* — Treść zależna od daty nie starzeje się, nawet gdy nikt nic nie zmienia.

## Dostępność i prawo

- **Dostępność WCAG 2.2 AA: link „Przejdź do treści”, widoczny fokus, kontrast, duże cele dotyku, tryb wysokiego kontrastu, ograniczenie animacji** — Stronę obsłuży każdy klient, także starszy i słabowidzący; mniejsze ryzyko prawne.
- **Sprawdzenie automatyczne axe na każdej stronie przed oddaniem (cel: 0 problemów)** — Dostępność jest zmierzona, a nie obiecana.
- **Polityka prywatności napisana według tego, co strona naprawdę robi (hosting, formularz, mapa, statystyki)** — Zgodność z RODO bez kopiowania cudzych regulaminów.
- **Klauzula informacyjna pod formularzem, bez zbędnego obowiązkowego „checkboxa” zgody** *(opcja)* — Mniej porzuconych formularzy, a obowiązek informacyjny RODO spełniony.
- **Strona z informacją o dostępności** *(opcja)* — Dla firm, które muszą ją mieć według ustawy o dostępności.
- **Zdjęcia z zapisanym źródłem, autorem i zgodą osób na wizerunek; bez zdjęć stockowych i obrazów z AI udających firmę** — Brak ryzyka roszczeń autorów i osób na zdjęciach.

## Bezpieczeństwo

- **Nagłówki bezpieczeństwa: ścisła polityka treści (CSP), HSTS, ochrona przed osadzaniem strony w ramce** *(opcja)* — Trudniej wstrzyknąć na stronę obcy skrypt albo podszyć się pod nią.
- **Formularz przez własny Worker: limit wysyłek z adresu IP, pole-pułapka, minimalny czas wypełnienia (niezależny od zegara w telefonie), sprawdzenie pochodzenia, limit rozmiaru** *(opcja)* — Spam nie zasypuje skrzynki, a formularz działa bez CAPTCHA.
- **Adres roboczy i panel ukryte przed wyszukiwarkami; plik security.txt z kontaktem** — Wersja testowa nie konkuruje w Google z właściwą stroną.
- **Klucze i hasła tylko w ustawieniach Cloudflare, nigdy w repozytorium** — Wyciek kodu nie oznacza wycieku dostępu do poczty czy konta.
- **Kontrola, czy Cloudflare nie wstrzykuje skryptów psujących stronę (np. ukrywanie e-maili)** — Strona na serwerze jest taka sama jak sprawdzona przed publikacją.

## Prywatność

- **Bez ciasteczek i bez obcych skryptów przy wejściu (0 zapytań do Google, Facebooka itp.)** — Nie potrzeba banera cookies — klient od razu widzi treść.
- **Mapa ładowana dopiero po kliknięciu (OpenStreetMap), a domyślnie tylko link do trasy** — Dane odwiedzających nie trafiają do dostawcy mapy bez ich decyzji.
- **Statystyki Cloudflare bez ciasteczek (opcjonalnie)** *(opcja)* — Firma wie, ile osób odwiedza stronę, bez śledzenia ich.
- **Zdjęcia bez metadanych (EXIF, GPS)** — Ze zdjęć nie da się odczytać, gdzie i czym zostały zrobione.

## Utrzymanie i rozwój

- **Cała treść w kilku plikach danych (data/) — jedna zmiana poprawia nagłówek, stopkę, kontakt, Google i politykę prywatności** — Zmiana telefonu czy godzin to jedna poprawka, a nie szukanie po wszystkich podstronach.
- **Kontrola przy każdej publikacji z komunikatami po polsku (plik, pole, jak naprawić); błąd zatrzymuje publikację** — Literówka w danych nie trafi na stronę.
- **Publikacja automatyczna: zapis zmian w GitHubie → Cloudflare buduje i wdraża stronę** *(opcja)* — Bez FTP i ręcznego wgrywania plików.
- **Karta jakości: zmierzone wyniki Lighthouse, dostępności, wagi strony, ciasteczek i obcych serwerów** — Firma dostaje dowód jakości w liczbach, a nie zapewnienia.
- **Aktualizacje z nowszych wersji szablonu (poprawki, nowe przepisy) bez ruszania treści firmy** — Strona nie starzeje się technicznie po oddaniu.
- **Lista „Do potwierdzenia z właścicielem” generowana z danych** — Nic niepewnego nie zostaje przeoczone.
- **Instrukcja dla asystenta AI i procedura krok po kroku** — Kolejne zmiany może bezpiecznie zrobić asystent AI według tych samych reguł.

---

Wygenerowano: `python3 tools/co_zawiera.py`. Zmierzone wyniki konkretnej strony: `raport/KARTA-JAKOSCI.md` (`bash tools/sprawdz.sh`).
