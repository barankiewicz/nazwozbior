# MEMORY: Nazwozbiór

## Opis
Statyczna strona internetowa do przeglądania prawdziwych polskich imion z rejestru PESEL, z filtrowaniem wg rodzaju, długości i pochodzenia, wzbogacona o opisy z Wikipedii.

## Lokalizacja
`/home/alice/wymysl-imie-trans/`

## Pliki
| Plik | Rola |
|---|---|
| `index.html` | Cały frontend (HTML + CSS + JS w jednym pliku) |
| `zbuduj_dataset.py` | Potok danych w Pythonie |
| `dane.js` | Generowany plik danych dla przeglądarki |
| `dataset_meskie.csv/.json` | Generowany zbiór imion męskich |
| `dataset_zenskie.csv/.json` | Generowany zbiór imion żeńskich |
| `.cache_wiki/` | Cache zapytań do Wikipedii (tworzony przez skrypt) |
| `raw_pesel/` | Surowe pliki XLSX z dane.gov.pl (tworzony przez skrypt) |
| `MEMORY.md` | Ten plik |

## Tech stack
- **Frontend:** Vanilla HTML/CSS/JS - zero frameworków, zero bundlerów, zero npm
- **Czcionki:** Google Fonts - Baloo 2 (display) + Atkinson Hyperlegible (text)
- **Potok danych:** Python 3 + `requests` + `openpyxl`
- **Architektura:** Całkowicie statyczna - nie ma serwera, otwiera się `index.html` w przeglądarce
- **Motyw:** Dark/light mode (systemowy + ręczny toggle)

## Źródła danych
1. **Rejestr PESEL** via `dane.gov.pl` (dataset 1667) - oficjalne polskie dane otwarte
   - 4 pliki XLSX: imiona męskie/żeńskie × pierwsze/drugie
2. **Polska Wikipedia** (`pl.wikipedia.org`) - wykrywanie pochodzenia + opis (CC BY-SA)

## Frontend - funkcje
- Filtry: rodzaj (żeńskie/męskie/wszystkie), długość (2–20), pochodzenie, szukaj tekstu
- Sortowanie: nazwa, długość, pochodzenie, wystąpienia pierwsze/drugie
- Rozwijane szczegóły z opisem z Wikipedii
- Responsywny, dostępny, z animacjami

## Potok danych (zbuduj_dataset.py)
1. Pobiera 4 pliki XLSX z API dane.gov.pl
2. Scala w dwa zbiory: męskie/żeńskie
3. Dla każdego imienia: sprawdza Wikipedię → wykrywa pochodzenie + pobiera opis
4. Eksportuje do CSV, JSON, oraz `dane.js` (zmienne globalne `DANE_MESKIE`, `DANE_ZENSKIE`)
5. W pełni wzrawialny (cache dyskowy), opcjonalny `--limit` dla szybkich testów
6. Uruchomienie: `python3 zbuduj_dataset.py` (lub `--limit 300`)
