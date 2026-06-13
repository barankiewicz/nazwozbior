# Nazwozbiór

Przeglądarka imion z rejestru PESEL i niebinarnych z [zaimki.pl](https://zaimki.pl/imiona). Znajdź imię, które jest Twoje.

Bez logowania, bez ciasteczek, bez śledzenia. Projekt zrobiony przez osoby trans, dla osób trans — ale korzystać może każdy.

## Co tu jest

Przeglądasz kilkadziesiąt tysięcy imion, filtrujesz i sortujesz po czym chcesz. Przy każdym imieniu masz etymologię i opis z Wikipedii, a przy niebinarnych — kompletny profil z zaimki.pl.

- **~50 tys. imion** z rejestru PESEL (osoby żyjące) — żeńskie i męskie, z liczbą wystąpień jako pierwsze i drugie imię. Dane z [dane.gov.pl](https://dane.gov.pl/pl/dataset/1667), odświeżane co miesiąc przez CI.
- **~220 imion niebinarnych** z API [zaimki.pl](https://zaimki.pl/imiona) — kolektyw Rada Języka Neutralnego. Każde ma opis: znaczenie, pochodzenie, użycie na świecie, status prawny, plusy i minusy, imieniny, znane osoby.
- **~2700 imion unisex** — wyliczane przez nas z PESEL-u: imiona, które występują w obu rejestrach (≥10% nadań w drugiej płci).
- **Opisy i etymologia** z Wikipedii (PL/EN/UK/RU/VI), tłumaczone automatycznie przez [MinT](https://translate.wmcloud.org/).
- Kolumna **ż / m** — procentowy stosunek nadań żeńskich do męskich dla widoku niebinarnego i unisex.

## Filtry i funkcje

- **Rodzaj**: żeńskie, męskie, **unisex** (wyliczenia z PESEL), **niebinarne** (z zaimki.pl), wszystkie. Stan filtrów zapisuje się w URL-u.
- **Suwaki długości** (1–35 liter) i **pola wystąpień** (min/max).
- **Pochodzenie** — greckie, hebrajskie, łacińskie, słowiańskie, germańskie i ~40 innych (wybór dynamiczny, pokazuje licznik przy każdej opcji).
- **Szukajka** — zwykłe wyszukiwanie i regex (`^A`, `a$`, `[aeiou]{2}`, `^.{3}$`…). Przełącznik `.*` obok pola.
- **Sortowanie** — klikasz nagłówek kolumny, sortuje się po tej kolumnie. Drugie kliknięcie odwraca kierunek.
- **Szczegóły** — klikasz wiersz, rozwija się panel: etymologia, trend nadań (2022→2024), imiona pochodne i bazowe (klikalne), a dla niebinarnych — pełny profil z zaimki.pl (znaczenie, użycie, prawnie, plusy, minusy, imieniny, znane osoby, linki).
- **Losowanie** — jedno kliknięcie, dostajesz losowe imię z obecnych filtrów.
- **Eksport CSV** — pobierasz widoczne wyniki jako plik CSV.
- **Paginacja** — domyślnie 250 imion na stronę, z opcją "pokaż wszystkie".

## Architektura

Zero backendu. Wszystko po stronie klienta. Jeden plik HTML i jeden wygenerowany plik JS z danymi.

```
dane.gov.pl (PESEL, XLSX)        zaimki.pl (API)
        │                              │
        ▼                              ▼
┌──────────── builder/zbuduj_dataset.py ──────────────┐
│ 1. pobierz XLSX z PESEL-u                           │
│ 2. zbuduj dataset męski i żeński                    │
│ 3. wzbogać kaskadowo: PL Wiki → Wikidane → EN Wiki │
│    → Wikisłowniki → dziedziczenie → morfologia       │
│ 4. pobierz i przetwórz imiona niebinarne (API)      │
│ 5. zapisz: dane.js + dataset_*.json + opisy/*.js    │
└─────────────────────────────────────────────────────┘
        │
        ▼
   dane.js  ──►  index.html (vanilla JS, jeden plik)
```

### Wzbogacanie — kaskada źródeł pochodzenia

Każde imię z PESEL-u przechodzi przez sekwencję źródeł, aż znajdzie pochodzenie:

1. **Polska Wikipedia** — parsowanie intro i kategorii. Wzorce regex na frazy typu „pochodzenia greckiego", „z języka hebrajskiego". Równolegle pobieramy sekcję 0 jako HTML do opisu (scoring akapitów: premiujemy etymologię, odrzucamy statystyki PESEL).
2. **Wikidane (hurtowo)** — dump wszystkich elementów klas Q202444/Q12308941/Q11879590/Q3409032 przez SPARQL (shardowany po MD5 QID, 64+ zapytań). Mapa ~55 tys. imion → język nazwy (P407) + opisy en/pl (drugi rzut). Dopasowanie lokalne i natychmiastowe.
3. **Angielska Wikipedia** — kategorie (`Hungarian masculine given names`) i wzorce tekstowe w intro (`of Welsh origin`, `is a Hebrew given name`).
4. **Wikisłowniki** — en.wiktionary (kategorie `given names from X`) i pl.wiktionary (sekcje etymologii, skróty językowe `łac.`, `gr.`, `hebr.`).
5. **Dziedziczenie** — „Ola — zdrobnienie imienia Aleksandra". Parsowanie relacji w intro PL Wikipedii, cel przekierowań, do 3 przebiegów.
6. **Morfologia** — ostatnia deska: żeńska forma dziedziczy po męskiej (`Karolina → Karol`, końcówki `-ina/-yna/-a`).

Wszystko cache'owane w `.cache_wiki/` — przerwany bieg wznawia się bez strat.

### Leniwe opisy

Opisy (~40% danych, ~2,3 MB raw) są odseparowane od `dane.js`. Lądują w shardach `opisy/<litera>.js`, dociąganych dynamicznym `<script>` dopiero przy pierwszym rozwinięciu wiersza na daną literę. Start strony lżeje z ~2,3 MB do ~0,7 MB (gzip). Działa pod file:// i z CSP (brak fetch).

### Powiązania imion

Każde imię może mieć `bazowe` (od kogo pochodzi) i `pochodne` (co od niego pochodzi). Relacje są klikalne — przenoszą do konkretnego imienia, luzując filtry tylko tam gdzie trzeba. Walidacja: baza musi istnieć w PESEL-u.

## Tech stack

- **Frontend**: jeden plik `index.html` — HTML + CSS + vanilla JS. Brak frameworków, brak bundlerów, brak npm.
- **CSS**: custom properties (zmienne), dark/light theme przez `data-theme` + `prefers-color-scheme`, flexbox, `position: sticky`, CSS tooltipy (`::after` + `data-tip`), animacje.
- **JS**: ES5 (kompatybilność). Stan filtrów w URL (`history.replaceState`), sortowanie, paginacja, leniwe ładowanie shardów opisów, service worker.
- **Service worker** (`sw.js` v4): network-first z cache fallbackiem — offline działa, a po wdrożeniu nikt nie utknie na starej wersji.
- **CSP**: zablokowane wszystko poza tym co potrzebne — `default-src 'self'`, `style-src` z Google Fonts, `connect-src` tylko GoatCounter.
- **Czcionki**: Baloo 2 (nagłówek, nazwy imion) + Atkinson Hyperlegible (tekst, dane).
- **Backend**: Python 3.13 — `builder/zbuduj_dataset.py`. Paczki: `requests`, `openpyxl`. Bez serwera — output to statyczne pliki.
- **CI/CD**: GitHub Actions (`.github/workflows/build.yml`). Na push do main i raz w miesiącu z crona: buduje dane, deploy na GitHub Pages + opcjonalnie FTP.
- **Hosting**: statyczne pliki, serwowane z dowolnego HTTP servera.

## Audyt jakości

`python3 builder/audyt_dataset.py` sprawdza każdy build pod kątem reguł: opisy-statystyki (R1), opisy-imieniny (R2), artykuł nie o imieniu (R3), podejrzanie krótki opis (R4), opis bez wzmianki o imieniu (R5). Raport z przykładami ląduje w `AUDYT.md`.

## Szybki start lokalnie

```bash
pip install requests openpyxl
python3 builder/zbuduj_dataset.py --limit 300   # szybki test (~imiona z top 300)
python3 builder/zbuduj_dataset.py               # pełny bieg (długo, ~godzinę)
python3 builder/zbuduj_dataset.py --incremental # tylko uzupełnienie braków
python3 -m http.server 8080             # i lecisz na localhost:8080
```

Flagi: `--limit N`, `--incremental`, `--skip-pl`, `--skip-en`, `--skip-wd`, `--skip-wikt`, `--skip-zaimki`, `--od-nowa`, `--no-sleep`, `--shutdown`.

## Struktura katalogów

```
.
├── index.html              # cały frontend
├── dane.js                 # wygenerowane dane (bez opisów)
├── opisy/*.js              # shardy opisów (leniwe ładowanie)
├── dataset_*.json          # pełne datasety (JSON)
├── dataset_*.csv           # pełne datasety (CSV, do własnych analiz)
├── builder/                # skrypty budujące dane
│   ├── zbuduj_dataset.py   # główny skrypt budujący
│   ├── audyt_dataset.py    # audyt jakości po buildzie
│   ├── wzbogac_opisy.py    # dodatkowe wzbogacanie opisów
│   ├── wzbogac_nowe_wiki.py
│   ├── DOKUMENTACJA.md     # pełna dokumentacja techniczna
│   └── AUDYT.md            # raport z ostatniego audytu
├── sw.js                   # service worker
├── count.js                # GoatCounter (self-hosted)
├── kontakt.html            # strona kontaktowa
├── .cache_wiki/            # cache zapytań do Wikipedii/Wikidanych
├── raw_pesel/              # pobrane XLSX z dane.gov.pl
└── .github/workflows/      # CI/CD
```

## Źródła i podziękowania

- Rejestr PESEL: [dane.gov.pl](https://dane.gov.pl/pl/dataset/1667)
- Imiona niebinarne: [zaimki.pl](https://zaimki.pl/imiona) — kolektyw [Rada Języka Neutralnego](https://zaimki.pl/kolektyw-rjn)
- Opisy: Wikipedia (CC BY-SA) przez [MinT](https://translate.wmcloud.org/) (NLLB)
- Ikona/flaga: flaga transpłciowa
- Made in Warsaw

## Licencja

[OQL](https://gitlab.com/PronounsPage/PronounsPage/-/blob/main/LICENSE) — Open Queer License (zgodna z zaimki.pl).
