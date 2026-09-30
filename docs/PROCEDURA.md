# Procedura: personalizacja strony dla firmy

Dostajesz to repozytorium, dane firmy i zdjęcia. Wynik: strona z prawdziwą treścią tej firmy, sprawdzona i opisana.
Idź fazami po kolei. **Każda faza kończy się poleceniem, które musi przejść** — dopiero wtedy przechodzisz dalej.
Stan pracy jest w plikach (`brief/`, `data/`, `assets/`), więc po fazie 3 i 5 można zacząć nową sesję.

Ta sama treść jest w `docs/PROCEDURA.md` i `.claude/skills/personalizuj/SKILL.md` (skill `/personalizuj`
w Claude Code). Źródłem jest ten plik; SKILL.md tworzy `python3 tools/skill.py` (test pilnuje zgodności).

Zasady nadrzędne (pełne: `AGENTS.md`): tylko prawdziwe dane ze źródłem; czego nie wiesz — `null`; obejrzyj każde
zdjęcie; nie ruszaj plików silnika (`src/`, `tools/`, `assets/css/czesci/`, `assets/js/czesci/`) bez pytania.

---

## Faza 0. Przyjęcie materiałów

1. Przeczytaj wszystko w `brief/`: `BRIEF.md` (kwestionariusz od właściciela), `zrodla.md`, notatki, maile,
   listę zdjęć w `brief/zdjecia/`. Jeśli `BRIEF.md` jest pusty — i tak zaczynasz od fazy 1 (źródła publiczne).
2. Wypisz w `brief/zrodla.md` → sekcja „Braki” wszystko, czego nie ma, według liter kwestionariusza
   (A podstawy, B oferta, C wygląd, D funkcje, E zdjęcia). Nie pytaj jeszcze właściciela — najpierw faza 1.
3. Ustal branżę (preset): `restauracja` (lokal z kartą), `budowlana` (wykonawca, przetargi), `producent` (B2B,
   katalog), `uslugi` (warsztat, salon, biuro), `gabinet` (medycyna, fizjoterapia, weterynaria).

Koniec fazy: `python3 tools/zrodla.py --faza 0` — sekcja „Braki” w `brief/zrodla.md` jest wypełniona
(albo „- brak braków”), a `ls brief/zdjecia/` pokazuje listę zdjęć.

## Faza 1. Źródła publiczne

Zbierz to, co da się sprawdzić bez właściciela. **Każdy fakt = wiersz w `brief/zrodla.md`: co, adres URL, data
odczytu.** To samo źródło trafi potem do `data/firma.json → zrodla`.

| Źródło | Co z niego bierzesz | Jak |
|---|---|---|
| Strona firmy (obecna lub archiwalna) | oferta, historia, telefony działów, kolory i kroje, zdjęcia | przeczytaj; stare wersje: web.archive.org |
| Facebook / Instagram firmy | godziny, telefon z baneru, zdjęcia **od firmy**, ogłoszenia | tylko wpisy i zdjęcia opublikowane przez firmę |
| Profil Firmy w Google (Mapy) | godziny, kategoria, ocena zbiorcza i liczba opinii, zdjęcia „od właściciela” | zdjęcia „od klientów” należą do autorów — nie bierz; ocenę zapisz z datą |
| KRS (spółki) | nazwa prawna, siedziba, KRS, NIP, REGON, kapitał, sąd, forma | `https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/<KRS>?rejestr=P&format=json` |
| Biała lista VAT (każda firma z NIP) | nazwa, adres, NIP, REGON, KRS, status VAT | `https://wl-api.mf.gov.pl/api/search/nip/<NIP>?date=RRRR-MM-DD` |
| CEIDG (JDG, s.c.) | imię i nazwisko właściciela, adres, NIP | wyszukiwarka `aplikacja.ceidg.gov.pl`; dane s.c. — z białej listy i od wspólników |
| BZP / e-Zamówienia, przetargi.egospodarka.pl („kto wygrał”) | realizacje zamówień publicznych: zadanie, zamawiający, rok, wartość | szukaj po nazwie i NIP wykonawcy; zapisz adres ogłoszenia |
| OpenStreetMap (Nominatim) | współrzędne **wejścia** (5 miejsc po przecinku) | `https://nominatim.openstreetmap.org/search?q=<adres>&format=json`; sprawdź na mapie, gdzie jest brama |
| Szyld, auta firmowe, ulotki, wizytówki (zdjęcia od firmy) | kolor marki, logo, dokładne nazwy usług | obejrzyj zdjęcia |

Uwaga na pułapki:
- Pod jednym adresem bywa kilka spółek o tej samej nazwie (np. sp. z o.o. i sp. k.). Sprawdź w KRS obie;
  który podmiot jest właścicielem strony — wpisz do `do_potwierdzenia`.
- Opis działalności z PKD to nie oferta. Oferta jest tym, co firma sama pokazuje (strona, ulotka, Facebook).
- Liczby z mediów i katalogów („100 pracowników”) bez daty i źródła pierwotnego — pomijasz.

Na koniec wyślij właścicielowi **jedną** krótką listę pytań: tylko to, czego nie znalazłeś (litery A–E z `BRIEF.md`).
Jeśli pracujesz bez kontaktu z właścicielem — braki zostają `null` i trafiają do `do_potwierdzenia`.
Brief bez domeny, współrzędnych albo formy prawnej nie wymaga zastępników (DECYZJE D13): `firma.domena: null`
+ `adres_roboczy`, `kontakt.geo: null` („Wyznacz trasę” poprowadzi do adresu), `rejestr.forma_prawna: "nieznana"`
— każde z nich to ostrzeżenie klasy A i wpis w `do_potwierdzenia`. Nie wpisuj adresu roboczego jako domeny ani
„inna” zamiast „nie wiem”. Wyjątek: e-mail firmy — bez niego `--produkcja` nie przejdzie (art. 5 ust. 2 u.ś.u.d.e.).

Koniec fazy: `python3 tools/zrodla.py --faza 1` — w tabeli „Fakty” są wiersze z wartością, źródłem (nie wzorem
z „…”) i datą dla nazwy, adresu, telefonu i danych rejestrowych.

## Faza 2. Szkielet danych

```
python3 tools/start.py --branza <branza>
```
Tworzy `data/firma.json`, `data/tresc.json`, `data/zdjecia.json` z samymi `null` (nigdy z przykładu). Szkielet
z kopii szablonu (nietknięty) zastępuje sam; plik, który ktoś zmieniał — tylko z `--nadpisz` (stare dane przepadną).
Przy okazji: README SZABLONU zmienia się w README klienta (tabela „Co i gdzie zmienić” dla branży, znaczniki
„Do potwierdzenia”), a `wrangler.jsonc` dostaje własne `namespace_id` limitu formularza.

Koniec fazy: `python3 tools/build.py --szybko` wypisuje listę braków (`brak danych: …`) — to Twoja lista zadań
na fazy 3–5. Kod 1 jest tu oczekiwany; kod 2 (błąd wewnętrzny) — nie.

## Faza 3. Dane firmy i marka (`data/firma.json`)

Opis pól: `docs/KONTRAKT.md` §4.1 i `tools/schemat/firma.schema.json`.

1. **Firma i NAP** (nazwa, adres, telefon): dokładnie tak jak w Google i na szyldzie — ten sam zapis wszędzie.
   Telefon w E.164 (`+48612345678`). `firma.opis` — jedno zdanie, co i gdzie (≤ 160 znaków).
2. **Rejestr** według formy prawnej: sp. z o.o. — KRS, sąd, NIP, REGON, kapitał; JDG — właściciel i NIP;
   s.c. — wspólnicy i NIP. Źródło: KRS / biała lista / CEIDG.
3. **Godziny**: każdy dzień osobno, kilka przedziałów, gdy jest przerwa; godziny kuchni, telefonu, wytwórni —
   w `godziny.dodatkowe`; święta — `godziny.wyjatki` (`python3 tools/swieta.py` pokaże daty na ten rok). Nie znasz
   godzin — `godziny: null` (strona ich nie pokaże), a nie „pn–pt 8–16” na wyczucie.
4. **Geo**: punkt wejścia/bramy, 5 miejsc po przecinku; bez pewnego punktu — `null` (trasa do adresu, D13). `obszar_dzialania` tylko ze źródła (np. zamawiający z BZP).
5. **Działy** (`kontakt.dzialy`): kto, w jakiej sprawie, numer — tylko gdy firma sama je podaje.
6. **Logo**: skopiuj plik z `brief/zdjecia/` do `assets/img/` (`cp brief/zdjecia/logo.png assets/img/logo.png`)
   i wpisz `"marka.logo": "assets/img/logo.png"`. `brief/` jest poza gitem i nie trafia na serwer — logo wskazane
   w `brief/` build odrzuca. PNG z przezroczystym tłem jest w porządku (`tools/zdjecia.py` zachowuje przezroczystość).
7. **Kolor marki** — z logo albo szyldu, nie z palety „ładnych kolorów”:
   ```
   python3 tools/kolory.py logo brief/zdjecia/logo.png      # kandydaci
   python3 tools/kolory.py raport "#RRGGBB"                  # tokeny i kontrast
   ```
   Wpisz `marka.kolor` i `marka.kolor_zrodlo` („żółta tablica w logo”, „czerwony klin z szyldu”). Drugi kolor
   z logo (`kolor_dodatkowy`) dostaje tylko jedną rolę (fokus). Za jasny kolor (żółty) jest OK — skrypt przeniesie
   go do wypełnień, a tekst zostanie ciemny.
8. **Funkcje** (`funkcje`): formularz `mailto` (domyślnie) albo `worker` (gdy firma ma skonfigurowany Resend —
   `docs/FORMULARZ.md`), mapa `link` albo `po_kliknieciu`, hosting `cloudflare`. Pozostałe przełączniki
   i ich uzasadnienia: `docs/DECYZJE.md`.
9. **Źródła i niepewne**: każde pole z faktem → `zrodla` („pole”: „źródło, RRRR-MM-DD”); niepewne →
   `do_potwierdzenia` (zdanie: co i dlaczego niepewne).

Koniec fazy: `python3 tools/build.py --szybko` — 0 błędów w `data/firma.json` (błędy `data/tresc.json` mogą zostać)
oraz `python3 tools/kolory.py raport --klient .` kończy się „Wynik: OK”.

## Faza 4. Zdjęcia (`data/zdjecia.json`)

1. **Obejrzyj każde zdjęcie** (otwórz plik). Odrzuć: stockowe, cudze (zdjęcia klientów z Google), obrazy z AI,
   zdjęcia innego lokalu, zrzuty ekranu z napisami, zdjęcia poniżej ~1000 px, jeśli mają być duże.
2. Dla każdego zdjęcia wpis:
   - `id` (krótkie, `[a-z0-9-]`: `wytwornia`, `droga-parkowo`), `zrodlo_plik` (`brief/zdjecia/…`);
   - `alt` — co widać, po polsku, 5–150 znaków: „Betonomieszarka z logo firmy przy wylewaniu stropu domu jednorodzinnego”,
     nie „Zdjęcie betonomieszarki”, nie „nasza firma”;
   - `podpis` — miejsce i rok, jeśli znane („Droga gminna w Żydowie, 2024”), inaczej `null`;
   - `zrodlo` (skąd i kiedy), `autor` (gdy nie firma), `osoby` / `zgoda` (twarz = zgoda właściciela lub osoby);
   - `punkt` — gdzie jest najważniejsza rzecz na zdjęciu (`[0.5, 0.4]`), `kadr_mobilny` — id pionowego kadru, jeśli jest.
3. Przypisz zdjęcia w treści (`hero.zdjecie`, `oferta.pozycje[].zdjecie`, `realizacje.pozycje[].zdjecia`…) dopiero
   w fazie 5. Zdjęcie hero: własne, poziome, z miejscem na tekst, ostre na telefonie.
4. Wygeneruj pliki:
   ```
   python3 tools/zdjecia.py
   ```
   Tworzy `assets/img/foto/*` (AVIF/WebP/JPEG w kilku szerokościach, bez EXIF/GPS), `assets/img/og.jpg`
   (1200×630 ze zdjęcia hero, a bez niego — logo na kolorze tła strony) i ikony z logo. Wynik commitujesz;
   oryginały z `brief/zdjecia/` zostają poza gitem.

Koniec fazy: `python3 tools/zdjecia.py` bez błędów i `ls assets/img/og.jpg assets/img/ikony/favicon.ico`.

## Faza 5. Treść (`data/tresc.json`, `data/tresc/*.md`)

Opis bloków: `docs/KONTRAKT.md` §4.2. Pisz głosem właściciela („budujemy”, „wozimy”), krótko i konkretnie.
Każdy fakt w treści musi mieć źródło (faza 1) — tekst nie może dodawać faktów, których nie ma w danych.

Zasady:
- Nagłówek h1: co + gdzie, ≤ 70 znaków. Lead: 1–2 zdania z faktem (rok, miejsce, liczba, nazwa).
- Każdy z pierwszych czterech akapitów ma liczbę, jednostkę, rok, cenę albo nazwę własną — jeśli brief ją ma.
  Przy cienkim briefie lint zgłosi `TRESC-BEZ-KONKRETU` (P2, informacja, nie blokada): nazwa własna też jest
  konkretem (ulica, dzielnica, nazwa pieca, dania); nie dopisuj liczb bez źródła — krótszy akapit jest lepszy.
- Oferta: nazwa usługi tak, jak mówi klient („wymiana rozrządu”, nie „serwis układów napędowych”), 1–2 zdania,
  zakres, czas, cena lub widełki — tylko jeśli są w źródle.
- Nagłówki sekcji zdaniem albo nazwą rzeczy, bez „Nasze …”, bez pytań retorycznych, bez etykiet nad nagłówkiem.
- Nic nie powtarzaj: to, co jest w hero, nie wraca w „O firmie”; telefon jest w kontakcie i stopce, nie w każdej sekcji.
- Sekcje bez danych zostaw `null` — szablon je ukryje. Nie dopisuj sekcji „na zapas”.
- Opinie: tylko prawdziwe, dosłowne cytaty z linkiem do źródła, maks. 3, plus zdanie, jak firma je weryfikuje
  (cytat bez linku — `--produkcja` go nie opublikuje).
- Karta bez cen (ceny tylko w lokalu): `cena: null` przy daniach i `"menu.ceny": "w_lokalu"` — pod kartą stanie
  zdanie o cenach (albo `menu.uwagi`). Nie wpisuj cen „na oko”; jeśli właściciel ma je podać — `do_potwierdzenia`.

Przykłady (źle → dobrze):

| Źle | Dobrze |
|---|---|
| Oferujemy kompleksowe usługi budowlane na najwyższym poziomie. | Budujemy i remontujemy drogi gminne i powiatowe w trzech powiatach wokół Gniezna. |
| Posiadamy wieloletnie doświadczenie w branży. | Firma działa od 2004 r.; od 2015 r. prowadzi ją syn założyciela. |
| Nasz zespół doświadczonych specjalistów zadba o każdy detal. | Na budowie pracuje nasza brygada i nasz sprzęt: walec, rozściełacz, dwie wywrotki. |
| Dlaczego my? Bo stawiamy na jakość i zadowolenie klienta! | (skreśl — zostaw fakty z oferty i realizacji) |
| Zapraszamy do zapoznania się z naszą bogatą ofertą. | Kostka brukowa z własnej produkcji, 12 wzorów; dowóz HDS-em do 40 km. |
| Świeże, domowe jedzenie przygotowane z pasją. | Pierogi lepimy rano, codziennie 6 rodzajów; zupa dnia 14 zł. |
| Indywidualne podejście do każdego pacjenta. | Pierwsza wizyta trwa 60 minut: wywiad, badanie i plan terapii na piśmie. |
| Szybko, tanio i profesjonalnie. | Wycena w 2 dni robocze, bez opłat za dojazd do 30 km. |

(Liczby w przykładach ilustrują formę — w stronie wolno użyć tylko liczb ze źródła.)

Koniec fazy: `python3 tools/build.py --json` — 0 błędów, a `python3 tools/lint_slop.py dist/ data/` bez P0 i P1.

## Faza 6. Wygląd (`data/firma.json → marka`, `assets/css/wlasne.css`)

1. **Kroje** (`marka.font_naglowki`, `marka.font_tekst`) — z `assets/fonts/fonty.json`, maks. dwa. Dobierz do branży
   i do charakteru logo (geometryczne, kondensowane, szeryfowe). Nie powtarzaj pary poprzedniego klienta.

   | Branża / charakter | Nagłówki | Tekst | Dlaczego |
   |---|---|---|---|
   | budowlana, transport, logo kondensowane (tablice, szyldy) | `barlow-condensed` | `barlow` | techniczny, jak oznakowanie i tablice budowy; wąski nagłówek mieści długie nazwy robót |
   | budowlana, producent, logo szerokie, grotesk | `archivo` | `public-sans` | mocny, rzeczowy; dobre cyfry w tabelach przetargów i parametrów |
   | restauracja, kawiarnia, piekarnia | `newsreader` | `public-sans` | szeryf redakcyjny jak karta dań, prosty tekst dla cen i alergenów |
   | restauracja tradycyjna, pensjonat | `literata` | `atkinson-next` | spokojny szeryf książkowy, bardzo czytelny tekst |
   | producent (meble, tekstylia, rzemiosło) | `source-serif-4` | `public-sans` | szeryf przy nazwach modeli, neutralny tekst przy parametrach |
   | usługi (warsztat, salon, biuro) | `archivo` | `atkinson-next` | wyraźny i przyjazny; dobrze działa na telefonie |
   | gabinet (medycyna, fizjoterapia) | `public-sans` albo `source-serif-4` | `public-sans` | spokojny i czytelny; zwykłe zero w cenach i godzinach przyjęć |
   | kancelaria, biuro rachunkowe | `source-serif-4` | `atkinson-next` | powaga bez ozdobników |

   Atkinson Hyperlegible Next rysuje zero z kreską („2Ø0 zł”, „8:ØØ”) i nie ma wariantu bez niej — w cennikach,
   godzinach i nagłówkach z cenami (`oferta` pokazuje cenę krojem nagłówków) czyta się technicznie. Przy wielu
   cenach i godzinach weź `public-sans` do tekstu.
2. **Tło** (`marka.tlo`): `biale` domyślnie; `cieple` dla gastronomii i rzemiosła, `chlodne` dla usług technicznych
   i medycznych. Kremowe tło z rdzawym akcentem tylko wtedy, gdy to naprawdę kolory firmy.
3. **Promień** (`marka.promien`): `0` przy logo o ostrych krawędziach (tablice, konstrukcje), `2` domyślnie,
   `4` dla marek łagodnych (gabinet, kawiarnia). Nigdy pigułki.
4. **Ciemna sekcja** (`marka.sekcja_ciemna`): `stopka` domyślnie; `kontakt`, gdy ciemne jest logo/szyld
   (np. czarny szyld restauracji); `brak` dla gabinetów.
5. **Jeden element-podpis** w `assets/css/wlasne.css` — jedna rzecz z świata tej firmy, reszta strony cicha.
   Tylko CSS (bez zmian w `src/`), tylko tokeny z `:root` (`var(--marka)`, `var(--linia)`…), bez gradientów, cieni
   i animacji bez `prefers-reduced-motion`. Przykłady:
   - **budowlana:** mapa obsługiwanego obszaru liniami 1 px — plik `assets/img/obszar.svg` narysowany z prawdziwych
     granic powiatów z `obszar_dzialania` (OpenStreetMap), jako dekoracyjne tło bloku kontaktu
     (`.kontakt { background: url(../img/obszar.svg) right top / min(40vw, 480px) no-repeat; }`); nazwy powiatów
     i tak są w treści. Albo: rok w tabeli przetargów wersalikami kroju kondensowanego w kolorze marki.
   - **restauracja:** pasek statusu na żywo — `.hero .status` jako pełnej szerokości pas w `var(--marka)` z kontrastowym
     tekstem („Otwarte do 22:00 · kuchnia do 21:30”); status liczy już silnik w strefie Europe/Warsaw.
   - **producent:** pasek próbek materiału — miniatury produktów (`.produkty`) ułożone ciasno w jeden rząd jak wzornik
     tkanin, bez odstępów i podpisów pod zdjęciem (podpis zostaje w `alt` i na podstronie).
   - **usługi / warsztat:** numer telefonu w stopce dużym krojem nagłówków, cyfry tabelaryczne — jak na szyldzie.
   - **gabinet:** godziny przyjęć jako główny element sekcji godzin — dzisiejszy dzień wyróżniony linią w kolorze marki.
   Po zmianie sprawdź, czy CSS nie przekracza limitu (build ostrzega powyżej 60 KB) i czy linter nie zgłasza P0/P1.

Koniec fazy: `python3 tools/build.py` — kod 0, 0 błędów kontrastu, bez P0/P1 z `lint_slop`.

## Faza 7. Build i poprawki

```
python3 tools/build.py --produkcja --json
```
Poprawiaj w pętli: każdy komunikat ma `plik`, `pole` i `naprawa`. Poprawiasz **dane** (albo `wlasne.css`), nie
kontrole. Typowe:
- `przyklad: true` / przeciek przykładu — skopiowano coś z `przyklady/`; napisz własnymi danymi.
- tytuł > 60 znaków — skróć `seo.fraza` albo nazwę; opis strony głównej 110–160 znaków (`seo.opis`).
- zdjęcie > 250 KB — mniejszy oryginał albo `python3 tools/zdjecia.py --tylko <id> --nadpisz`.
- `do_potwierdzenia` — ostrzeżenie informacyjne; nie blokuje, trafi do README.

Koniec fazy: `python3 tools/build.py --produkcja` — kod 0.

## Faza 8. Weryfikacja

```
bash tools/sprawdz.sh                 # albo z --url https://domena po publikacji
```
Kroki: build, podgląd, zrzuty 375/768/1440 (+ bez JS i w trybie wymuszonych kolorów), html-validate, pa11y (axe)
na każdej stronie, Lighthouse na telefonie i komputerze, karta jakości. Na początku skrypt wypisuje, których
narzędzi brakuje; brakujące narzędzie = POMINIĘTO. Bez uprawnień do systemowego Node instaluj do katalogu
użytkownika: `npm i -g --prefix ~/.szablon-node playwright html-validate pa11y lighthouse linkinator`, potem
`SZABLON_NODE_PREFIX=~/.szablon-node bash tools/sprawdz.sh` (Chromium: zmienna `CHROMIUM`). Każdy krok ma limit
czasu; zajęty port — `--port 8791`.

Potem **obejrzyj zrzuty** z `raport/zrzuty/` (`*-375-ekran.png`, `*-375.png`, `*-1440.png`) i sprawdź:
- [ ] na 375 px bez przewijania: nazwa firmy, miejscowość, co robi, przycisk telefonu, dzisiejsze godziny (jeśli są);
- [ ] pasek „Zadzwoń” na telefonie nie zasłania treści, przycisku mapy ani stopki (pasek widać na `*-375-ekran.png`
      i `*-375-bezjs-ekran.png`; na zrzutach całej strony jest ukryty, bo Chromium rysuje go w połowie treści);
- [ ] długie słowa i nazwy („Przedsiębiorstwo”, „czarnkowsko-trzcianecki”) nie wychodzą poza ekran;
- [ ] żadna informacja nie powtarza się w dwóch sekcjach (telefon, adres, oferta, rok założenia);
- [ ] zdjęcia są firmy, ostre, nie zniekształcone, kadr na telefonie pokazuje to, co ważne;
- [ ] kolory i kroje przypominają logo i szyld; element-podpis jest jeden;
- [ ] test sylwetki: po rozmyciu zrzutu 1440 sekcje nie wyglądają identycznie (różny układ pod treść);
- [ ] brak śladów szablonu: kart z cieniem, siatek ikon, etykiet nad nagłówkami, gradientów, „Dlaczego my?”;
- [ ] wersja bez JS (`*-bezjs.png`): menu, godziny i treść widoczne; wymuszone kolory: przyciski i pola mają obrys.

Koniec fazy: `bash tools/sprawdz.sh` — „Wynik: OK”, lista kontrolna odhaczona, `python3 tools/lint_slop.py dist/ data/`
bez P0/P1.

## Faza 9. Przekazanie

1. `python3 tools/raport.py --readme` — aktualizuje w `README.md` sekcję „Do potwierdzenia z właścicielem”
   (z `firma.do_potwierdzenia`) i zapisuje `raport/KARTA-JAKOSCI.md` + `.html` (wyniki do przekazania klientowi).
2. `python3 tools/co_zawiera.py --klient .` — `raport/CO-ZAWIERA-STRONA.md`: co strona ma i co można włączyć,
   gdy firma dostarczy dane.
3. `README.md` klienta (szkielet z `tools/start.py`): wpisz nazwę firmy w tytule i zdanie o stronie, sprawdź tabelę
   „Co i gdzie zmienić” (wiersze sekcji, których strona nie ma, usuń).
4. Publikacja i przekazanie kont: `docs/CLOUDFLARE.md`, `docs/PRZEKAZANIE.md`.
5. Ostatnia wiadomość do użytkownika: wyniki z karty (Lighthouse, axe, waga, 0 ciasteczek), ścieżki zrzutów,
   lista ukrytych sekcji (z powodem) i pytania do właściciela. Liczby i ścieżki, nie zapewnienia.

Koniec fazy: `python3 tools/build.py --produkcja && test -f raport/KARTA-JAKOSCI.md && grep -q "do-potwierdzenia:poczatek" README.md`.
