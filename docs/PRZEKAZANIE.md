# Przekazanie strony klientowi

Zasada: **wszystkie konta są klienta**, a wykonawca ma do nich dostęp jako zaproszony użytkownik. Jeśli
współpraca się skończy, klient odbiera dostęp jednym kliknięciem i nic nie traci — domena, strona, statystyki
i profil w Google zostają u niego. Techniczne kroki wdrożenia: `docs/CLOUDFLARE.md`.

## 1. Przed przekazaniem (lista kontrolna wykonawcy)

- [ ] `python3 tools/build.py --produkcja` — kod 0; `bash tools/sprawdz.sh --url https://domena.pl` — „Wynik: OK”.
- [ ] `python3 tools/raport.py --readme` — karta jakości w `raport/KARTA-JAKOSCI.md` (i `.html` do wysłania),
      w README aktualna sekcja „Do potwierdzenia z właścicielem”.
- [ ] `python3 tools/co_zawiera.py --klient .` — `raport/CO-ZAWIERA-STRONA.md`: co strona ma i co można włączyć.
- [ ] Właściciel potwierdził pozycje z „Do potwierdzenia” albo wie, że są na stronie ukryte.
- [ ] Zgody na wizerunek osób ze zdjęć są u właściciela (na piśmie albo e-mailem).

## 2. Konta i kto jest właścicielem

| Co | Właściciel | Wykonawca | Uwagi |
|---|---|---|---|
| Domena (rejestrator: nazwa.pl, home.pl, OVH…) | klient — umowa i faktury na firmę | ewentualnie pełnomocnik do DNS | zapisz datę odnowienia; automatyczne odnawianie włączone |
| DNS | w Cloudflare na koncie klienta (serwery nazw ustawione u rejestratora) | członek konta | rekordy poczty (MX, SPF, DKIM, DMARC) zostają jak były — sprawdź przed przeniesieniem |
| Cloudflare (strona, Worker, DNS) | konto na e-mail firmy | **Members → Invite** (rola Administrator) | klucz Resend i adres Deploy Hook jako sekrety tylko tutaj |
| GitHub (repozytorium strony) | organizacja albo konto klienta, repozytorium prywatne | współpracownik (Write) | Workers Builds połączone z tym repozytorium |
| Google Search Console | klient (weryfikacja domeny rekordem TXT w DNS) | użytkownik z pełnymi uprawnieniami | wyślij `https://domena.pl/sitemap.xml` |
| Bing Webmaster Tools | klient (import z Search Console) | użytkownik | sitemap jak wyżej |
| Profil Firmy w Google | klient — właściciel profilu | menedżer | nazwa, adres, telefon i godziny **identyczne** jak w `data/firma.json`; link do strony |
| Facebook / Instagram | klient | redaktor, jeśli potrzeba | adres strony w profilu |
| Resend (formularz) | konto na e-mail firmy | członek zespołu | domena nadawcy zweryfikowana w DNS (`docs/FORMULARZ.md`) |
| Skrzynka e-mail na zapytania | klient | — | na ten adres przychodzą wiadomości z formularza |

## 3. Kolejność przełączenia domeny

1. Strona działa pod adresem roboczym `*.workers.dev` (ma `noindex`), klient ją obejrzał i zaakceptował.
2. W `data/firma.json`: `firma.domena` = docelowy adres (z `https://`, bez `/` na końcu), `firma.adres_roboczy` — adres
   roboczy (dostaje nagłówek `noindex`). Commit i push.
3. Cloudflare: własna domena dla Workera + przekierowanie drugiego wariantu (www ↔ bez www) — `docs/CLOUDFLARE.md` §3.
4. Stare adresy z poprzedniej strony (Google je zna) → przekierowania 301 w `_redirects` (np. `/oferta.html /oferta 301`).
   Listę starych adresów weź z Search Console (Strony → Zaindeksowane) albo z mapy starej strony.
5. Ustawienia strefy Cloudflare: Bot Fight Mode, Email Address Obfuscation i Rocket Loader **wyłączone**
   (psują ścisłą politykę skryptów) — potem `bash tools/sprawdz.sh --url https://domena.pl`.
6. Search Console: weryfikacja domeny (TXT), wysłanie sitemap, sprawdzenie adresu strony głównej („Sprawdź URL”).
7. Profil Firmy w Google: adres strony, godziny zgodne ze stroną.

## 4. Co klient musi aktualizować sam (albo zlecić)

| Co | Jak często | Gdzie |
|---|---|---|
| Godziny w święta i urlopy | przed każdym świętem (build przypomina 45 dni wcześniej) | `data/firma.json` → `godziny.wyjatki`, a także Profil Firmy w Google |
| Ogłoszenia (zamknięte, zmiana godzin) | gdy się zdarzy — znikają same po dacie `do` | `data/tresc.json` → `ogloszenie` |
| Ceny i cennik | przy każdej zmianie; data cennika starsza niż 12 miesięcy = ostrzeżenie | `data/tresc.json` → `cennik` / `menu` (pole `data`) |
| Oferty pracy | termin `wazne_do` — po nim oferta znika | `data/tresc.json` → `kariera` |
| Zdjęcia realizacji / dań | raz na kwartał dobrze, raz na rok minimum | `brief/zdjecia/` + `data/zdjecia.json` + `python3 tools/zdjecia.py` |
| Ocena z Google na stronie | co pół roku (starsza = ostrzeżenie) | `data/firma.json` → `opinie_zbiorczo` (z datą) |
| Telefon, e-mail, adres | przy zmianie — jednocześnie na stronie, w Google i na Facebooku | `data/firma.json` → `kontakt` |
| Odnowienie domeny | co rok | u rejestratora |
| Aktualizacja szablonu | gdy wyjdzie nowa wersja (poprawki, przepisy) | `python3 tools/aktualizuj.py` (README → „Aktualizacja”) |

Każda zmiana to commit w repozytorium; Cloudflare przebudowuje stronę sam w 1–2 minuty. Co noc strona przebudowuje
się też automatycznie, żeby daty (ogłoszenia, święta, rok w stopce) były aktualne.

## 5. Co przekazać klientowi na piśmie

- Adres strony, adres repozytorium, lista kont z tabeli w punkcie 2 (bez haseł — hasła zna tylko klient).
- `raport/KARTA-JAKOSCI.html` — zmierzone wyniki w dniu oddania.
- `raport/CO-ZAWIERA-STRONA.md` — co strona ma i co można włączyć, gdy pojawią się dane.
- Tabelę „Co i gdzie zmienić” z README i punkt 4 tego dokumentu.
- Listę „Do potwierdzenia z właścicielem” (README) — rzeczy, które czekają na odpowiedź.
- Sprawy do sprawdzenia z prawnikiem, jeśli dotyczą: regulamin usług elektronicznych (sprzedaż online), zgoda
  marketingowa (newsletter), obowiązek informacji o dostępności (sprzedaż konsumentom online, firma większa niż mikro).
