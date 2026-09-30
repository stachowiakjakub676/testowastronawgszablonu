Restauracja Testowa nie istnieje. To fikcyjny lokal, na którym sprawdzamy szablon strony: tekst ma
ponad 250 słów, więc strona główna pokazuje tylko pierwszy akapit, a całość trafia na podstronę „O nas”.

## Kuchnia

Gotujemy dania kuchni polskiej z produktów od okolicznych dostawców. Karta zmienia się dwa razy w roku, a zupa dnia
codziennie. W piątek i sobotę kuchnia pracuje do 23:00, bar do 2:00 w nocy — to przypadek godzin po północy, który
szablon musi pokazać poprawnie w tabeli, w statusie „Otwarte” i w danych strukturalnych.

## Sala i ogródek

Sala ma 48 miejsc, ogródek od maja do września 20 miejsc. Przyjęcia do 40 osób przyjmujemy w dni, w które restauracja
jest zamknięta, czyli w poniedziałki. W tekście stoją liczby z jednostkami (48 m², 5 km, 12 zł) i zakresy godzin
12:00 - 15:00, żeby sprawdzić polską typografię: twarde spacje po liczbach i półpauzę w zakresach.

- wejście bez progu
- krzesełka dla dzieci
- miska wody dla psów w ogródku

## Po co ten tekst

Próg podstrony „O nas” to 250 słów. Tekst krótszy zmieściłby się na stronie głównej i podstrona by nie powstała —
wtedy test nie sprawdziłby linku „Cały tekst o firmie” ani okruszków. Dlatego piszemy jeszcze kilka zdań o niczym
konkretnym: o tym, że w poniedziałek sprzątamy, we wtorek przyjmujemy dostawy, a w środę testujemy nowe dania.
Każde zdanie jest wymyślone, a nazwy, adresy i numery na tej stronie należą do fikstury testowej, nie do prawdziwej
firmy. Link do [strony kontaktowej](/kontakt) sprawdza linki względne w Markdownie, a
[ten link](javascript:alert(1)) musi zniknąć (zostaje sam tekst). Pogrubienie **działa**, kursywa *też*.
