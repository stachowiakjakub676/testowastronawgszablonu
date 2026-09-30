"""Zbieranie komunikatów buildu: błędy, ostrzeżenia, informacje i lista UKRYTO.

Każdy komunikat ma poziom, treść po polsku, opcjonalnie plik, pole i podpowiedź, jak naprawić.
W trybie --produkcja ostrzeżenia klasy „B” (domyślna) stają się błędami (KONTRAKT §9.2, §10).
Klasa „A” to ostrzeżenia, które zostają ostrzeżeniami także w produkcji (np. brak jeszcze pliku sekcji).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

BLAD = "BŁĄD"
OSTRZEZENIE = "OSTRZEŻENIE"
INFO = "INFO"
UKRYTO = "UKRYTO"


@dataclass
class Komunikat:
    poziom: str
    tresc: str
    plik: str | None = None
    pole: str | None = None
    naprawa: str | None = None
    klasa: str = "B"

    def tekst(self) -> str:
        czesci = []
        if self.plik:
            czesci.append(f"{self.plik}: ")
        if self.pole:
            czesci.append(f"[{self.pole}] ")
        czesci.append(self.tresc)
        if self.naprawa:
            czesci.append(f"\n      → {self.naprawa}")
        return "".join(czesci)


@dataclass
class Raport:
    produkcja: bool = False
    komunikaty: list[Komunikat] = field(default_factory=list)

    def _dodaj(self, k: Komunikat) -> None:
        # bez duplikatów (ta sama treść z kilku stron)
        for istn in self.komunikaty:
            if (istn.poziom, istn.tresc, istn.plik, istn.pole) == (k.poziom, k.tresc, k.plik, k.pole):
                return
        self.komunikaty.append(k)

    def blad(self, tresc, plik=None, pole=None, naprawa=None):
        self._dodaj(Komunikat(BLAD, tresc, plik, pole, naprawa))

    def ostrzezenie(self, tresc, plik=None, pole=None, naprawa=None, klasa="B"):
        if self.produkcja and klasa != "A":
            self._dodaj(Komunikat(BLAD, tresc + " (w trybie --produkcja to błąd)", plik, pole, naprawa, klasa))
        else:
            self._dodaj(Komunikat(OSTRZEZENIE, tresc, plik, pole, naprawa, klasa))

    def info(self, tresc, plik=None):
        self._dodaj(Komunikat(INFO, tresc, plik))

    def ukryto(self, tresc):
        self._dodaj(Komunikat(UKRYTO, tresc))

    def lista(self, poziom: str) -> list[Komunikat]:
        return [k for k in self.komunikaty if k.poziom == poziom]

    @property
    def bledy(self) -> list[Komunikat]:
        return self.lista(BLAD)

    def json(self) -> str:
        return json.dumps([asdict(k) for k in self.komunikaty], ensure_ascii=False, indent=2)
