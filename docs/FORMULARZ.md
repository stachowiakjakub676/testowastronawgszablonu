# Formularz zapytania — konfiguracja wysyłki

Stan na: wrzesień 2026.

Formularz ma dwa tryby (`data/firma.json` → `funkcje.formularz.tryb`):

| Tryb | Co widzi odwiedzający | Co trzeba ustawić |
|---|---|---|
| `mailto` | przycisk „Napisz zapytanie” — otwiera program pocztowy z gotowym tematem i szablonem wiadomości | nic (adres z `formularz.adresat` albo `kontakt.email`) |
| `worker` | formularz na stronie kontaktu (imię, telefon lub e-mail, treść) wysyłany na serwer | konto Resend + zmienne w Cloudflare (niżej) |
| `null` | brak zapytania — tylko telefon i e-mail | — |

`worker` działa tylko przy `funkcje.hosting: "cloudflare"` (na GitHub Pages nie ma Workera — build to zgłosi).
Wiadomości dostarcza [Resend](https://resend.com) (plan darmowy: 3 000 e-maili miesięcznie, 100 dziennie —
na zapytania z małej firmy wystarczy z zapasem).

## Jak to działa

```
formularz (POST /api/kontakt) → Worker (worker/index.js): Origin, limit 5/min z IP, pułapka, czas ≥ 3 s,
  długości, > 5 linków → Resend API → skrzynka firmy (Odpowiedz = do nadawcy, gdy podał e-mail)
```

- **Z JavaScriptem** (`assets/js/czesci/60-formularz.js`): wysyłka w tle, komunikat pod przyciskiem, błędy przy
  polach. Gdy wysyłka nie jest skonfigurowana (odpowiedź 503) albo Worker nie odpowiada, strona sama otwiera
  program pocztowy z treścią wpisaną w formularz — wiadomość nie ginie.
- **Bez JavaScriptu**: zwykłe wysłanie formularza; Worker przekierowuje na `/dziekujemy` albo na stronę błędu
  z opisem, co zrobić: `/blad-formularz` (brakujące albo za długie pola), `/blad-konfiguracja` (wysyłka niewłączona —
  gotowy e-mail i telefon firmy), `/blad` (reszta, z telefonem i adresem e-mail firmy).
- **Ochrona przed spamem** bez captchy i bez cookies: ukryte pole `strona_www` (wypełniają je tylko boty),
  formularz wysłany szybciej niż w 3 sekundy od otwarcia, więcej niż 5 linków w treści — boty dostają
  udawane „wysłano”, żeby nie próbowały dalej. Plus limit 5 wiadomości na minutę z jednego adresu IP
  (`ratelimits` w `wrangler.jsonc`) i przyjmowanie formularza tylko z własnej domeny (nagłówek Origin).
- Worker nie zapisuje treści ani adresów IP. W dzienniku (Observability → Logs) są tylko kody błędów Resend.

## 1. Konto w Resend

1. <https://resend.com/signup> — załóż konto **na adres, na który mają przychodzić zapytania** (najlepiej ogólny
   adres firmy, nie prywatny).
2. **API Keys → Create API Key**: nazwa `strona`, uprawnienie **Sending access**, domena: wybierz swoją, gdy już
   będzie zweryfikowana (rozdział 3). Skopiuj klucz `re_…` — Resend pokazuje go tylko raz.

Bez własnej domeny Resend wysyła z `onboarding@resend.dev` i dostarcza **tylko na adres właściciela konta** —
do pierwszych testów wystarczy.

## 2. Zmienne w Cloudflare

**Workers & Pages → <nazwa> → Settings → Variables and Secrets → Add**:

| Nazwa | Typ | Wartość |
|---|---|---|
| `RESEND_API_KEY` | **Secret** | klucz `re_…` |
| `ADRESAT` | Text | adres odbiorcy; kilka adresów po przecinku (wymaga własnej domeny w Resend) |
| `NADAWCA` | Text | po weryfikacji domeny: `Nazwa firmy – formularz <formularz@send.domena.pl>` |

Kliknij **Deploy** w tym oknie. Działa od razu, bez nowego buildu. W `data/firma.json` ustaw
`"formularz": {"tryb": "worker", …}` i zbuduj stronę — dopiero wtedy na stronie pojawi się formularz.

## 3. Wysyłka z własnej domeny (SPF, DKIM, DMARC)

Wysyłamy z **poddomeny** (np. `send.domena.pl`) — reputacja formularza nie miesza się wtedy ze zwykłą pocztą
firmy, a istniejące rekordy MX i SPF domeny głównej zostają nietknięte.

1. Resend → **Domains → Add Domain** → `send.domena.pl` (region: Europe — Ireland, `eu-west-1`).
2. Resend pokaże rekordy. Gdy DNS jest w Cloudflare, przycisk **Sign in to Cloudflare** doda je sam; ręcznie:
   | Typ | Nazwa (w Cloudflare bez domeny) | Wartość | Uwagi |
   |---|---|---|---|
   | TXT | `resend._domainkey.send` | `p=MIGf…` (klucz DKIM z panelu Resend) | DNS only |
   | MX | `send.send` | `feedback-smtp.eu-west-1.amazonses.com`, priorytet 10 | adres zwrotów (SPF) |
   | TXT | `send.send` | `v=spf1 include:amazonses.com ~all` | SPF adresu zwrotów |

   Dokładne nazwy i wartości przepisz z panelu Resend — zależą od regionu i nazwy poddomeny.
   Rekordy poczty zawsze **DNS only** (szara chmurka).
3. **DMARC** dla domeny głównej (jeśli jeszcze nie ma): TXT `_dmarc` → `v=DMARC1; p=none; rua=mailto:<adres firmy>`.
   Po kilku tygodniach bez problemów w raportach zmień `p=none` na `p=quarantine`. Nie dodawaj drugiego rekordu
   `_dmarc`, jeśli dostawca poczty firmy już go ustawił — popraw istniejący.
4. Po zielonym **Verified** w Resend ustaw `NADAWCA` (rozdział 2). Od teraz `ADRESAT` może być dowolnym adresem.

## 4. Gdy coś nie działa

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| strona otwiera program pocztowy zamiast wysłać | brak `RESEND_API_KEY` albo `ADRESAT` (odpowiedź 503 z listą braków) | rozdział 2 |
| „Nie udało się wysłać wiadomości” | Resend odrzucił wysyłkę (502) | Observability → Logs → wpis „Resend: błąd 4xx …”: zwykle niezweryfikowana domena w `NADAWCA` albo klucz bez uprawnień |
| wiadomość nie dochodzi, strona mówi „wysłano” | domena testowa Resend (dostarcza tylko właścicielowi konta) albo filtr spamu | rozdział 3; sprawdź folder spam i Resend → Emails |
| „Formularz można wysłać tylko ze strony firmy” | wysłano z innej domeny niż ta, na której działa Worker | wejdź przez główny adres; sprawdź przekierowanie www (`docs/CLOUDFLARE.md`, rozdział 3) |
| „Wysłano kilka wiadomości w krótkim czasie” | limit 5 na minutę z IP | poczekaj minutę |
| formularz nie pojawia się na stronie | `tryb` nie jest `worker` albo strona nie została przebudowana | `data/firma.json` → `funkcje.formularz`, nowy build |

## 5. Test

Lokalnie (bez Cloudflare): `node tools/test_worker.mjs` — sprawdza każdą gałąź Workera (pułapka, czas, limit, Origin,
braki, spam, błędy Resend, odpowiedzi JSON i przekierowania 303, nocny build) z podmienionym `fetch`.
`python3 tools/podglad.py` odpowiada na `/api/*` jak Worker bez konfiguracji (503) — widać ścieżkę z `mailto:`.

Na produkcji, po każdej zmianie ustawień:

1. Otwórz `/kontakt`, odczekaj kilka sekund, wypełnij formularz swoim adresem e-mail → „Dziękujemy, wiadomość wysłana”.
2. Wiadomość przychodzi na `ADRESAT` z tematem „Zapytanie ze strony domena.pl – imię”. **Odpowiedz** trafia do
   adresu z formularza.
3. Wyłącz JavaScript w przeglądarce i wyślij jeszcze raz → strona `/dziekujemy`.
4. Resend → **Emails**: status `delivered`.

Z wiersza poleceń (sprawdza Workera i konfigurację, wysyła prawdziwą wiadomość):

```sh
curl -i https://domena.pl/api/kontakt -H 'Accept: application/json' -H 'Origin: https://domena.pl' \
  -F imie=Test -F kontakt=ty@example.com -F wiadomosc='Próba formularza' -F strona_www= -F t=
```

Odpowiedź `{"ok":true}` = wysłano; `503 {"ok":false,"blad":"nie_skonfigurowano",…,"brakuje":[…]}` = brak zmiennych.
