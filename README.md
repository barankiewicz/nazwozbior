![flag](data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0MDAgMjAiPjxyZWN0IHk9IjAiIHdpZHRoPSI0MDAiIGhlaWdodD0iNCIgZmlsbD0iIzVCQ0VGQSIvPjxyZWN0IHk9IjQiIHdpZHRoPSI0MDAiIGhlaWdodD0iNCIgZmlsbD0iI0Y1QTlCOCIvPjxyZWN0IHk9IjgiIHdpZHRoPSI0MDAiIGhlaWdodD0iNCIgZmlsbD0iI0ZGRkZGRiIvPjxyZWN0IHk9IjEyIiB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQiIGZpbGw9IiNGNUE5QjgiLz48cmVjdCB5PSIxNiIgd2lkdGg9IjQwMCIgaGVpZ2h0PSI0IiBmaWxsPSIjNUJDRUZBIi8+PC9zdmc+)

# Nazwozbiór

> Strona działa pod **[nazwozbior.pl](https://nazwozbior.pl)**.

Przeglądasz imiona z rejestru PESEL i niebinarne z [zaimki.pl](https://zaimki.pl/imiona). Bez logowania, bez ciasteczek, bez śledzenia. Projekt robiony przez osoby trans, dla osób trans — ale każdy może z niego korzystać. Jeśli szukasz imienia dla siebie, zastanawiasz się nad zmianą albo po prostu chcesz wiedzieć, skąd się wzięło Twoje — jesteś w dobrym miejscu.

## Co tu znajdziesz

- **~50 tys. imion** z rejestru PESEL — żeńskie i męskie, z danymi o wystąpieniach (pierwsze i drugie imię). Źródło: [dane.gov.pl](https://dane.gov.pl/pl/dataset/1667). Aktualizowane raz w miesiącu przez CI.
- **~2700 imion unisex** — wyliczamy je sami z PESEL-u: imiona, które pojawiają się zarówno z żeńską, jak i męską metryką (co najmniej 10% nadań w drugiej płci).
- **~220 imion niebinarnych** z [zaimki.pl](https://zaimki.pl/imiona) — baza prowadzona przez kolektyw Rada Języka Neutralnego. Każde ma swój profil: znaczenie, pochodzenie, użycie, status prawny, plusy i minusy, imieniny, znane osoby.
- **Opisy i etymologia** z Wikipedii (polskiej, angielskiej, ukraińskiej, rosyjskiej, wietnamskiej), tłumaczone maszynowo przez [MinT](https://translate.wmcloud.org/).
- **Ż / M** — kolumna pokazująca procent nadań żeńskich i męskich. Im bliżej 50/50, tym bardziej neutralne. Dostępna w widoku niebinarnym i unisex.

## Co można tu robić

Klikasz, filtrujesz, sortujesz. Wszystko, co wybierzesz, trafia do URL-a — możesz komuś podesłać link z konkretnym widokiem.

- **Rodzaj**: żeńskie, męskie, unisex (nasze wyliczenia z PESEL-u), niebinarne (z zaimki.pl), wszystkie
- **Długość**: suwaki 1–35 liter
- **Wystąpienia**: pola min/max — ile razy imię nadano
- **Pochodzenie**: greckie, hebrajskie, łacińskie, słowiańskie, germańskie i jeszcze ~40 innych. Przy każdej opcji widzisz licznik — wiesz, ile imion pasuje, zanim klikniesz
- **Szukajka**: zwykłe wyszukiwanie i regex (`^A`, `a$`, `[aeiou]{2}`, `^.{3}$`). Przełącznik `.*` obok pola
- **Sortowanie**: klikasz w nagłówek, sortuje. Drugie kliknięcie — odwrotnie
- **Szczegóły**: klikasz wiersz, rozwija się panel z etymologią, trendem nadań (2022→2024), imionami pochodnymi i bazowymi (klikalnymi). Dla niebinarnych — pełny profil z zaimki.pl
- **Losuj**: dostajesz przypadkowe imię z obecnych filtrów
- **CSV**: pobierasz widoczne wyniki jako plik CSV
- **Paginacja**: 250 imion na stronę, z przyciskiem „pokaż wszystkie"

## Architektura

Zero backendu. Jeden plik HTML i jeden wygenerowany plik JS. Wszystko po stronie klienta.

```
dane.gov.pl (PESEL, XLSX)        zaimki.pl (API)
        │                              │
        ▼                              ▼
┌─────── builder/zbuduj_dataset.py ──────────────────┐
│ 1. pobiera XLSX z PESEL-u                           │
│ 2. buduje dataset męski i żeński                    │
│ 3. kaskadowo wzbogaca o pochodzenie i opis:         │
│    PL Wiki → Wikidane → EN Wiki → Wikisłowniki      │
│    → dziedziczenie → morfologia                      │
│ 4. pobiera imiona niebinarne przez API              │
│ 5. zapisuje: dane.js + dataset_*.json + opisy/*.js  │
└─────────────────────────────────────────────────────┘
        │
        ▼
   dane.js  ──►  index.html (vanilla JS, jeden plik)
```

### Jak znajdujemy pochodzenie

Każde imię z PESEL-u przechodzi przez kilka źródeł. Jeśli któreś da wynik, następne są pomijane:

1. **Polska Wikipedia** — parsujemy intro i kategorie. Szukamy fraz typu „pochodzenia greckiego", „z języka hebrajskiego". Przy okazji pobieramy sekcję 0 jako HTML do opisu (algorytm punktuje akapity o etymologii, odrzuca statystyki PESEL i listy imienin).
2. **Wikidane (hurtowo)** — ściągamy hurtem wszystkie elementy z klas „imię" / „imię męskie" / „imię żeńskie" / „imię unisex" przez SPARQL, shardując po MD5 QID. Dostajemy mapę ~55 tys. imion → język pochodzenia. Dopasowujemy lokalnie, bez kolejnych zapytań.
3. **Angielska Wikipedia** — kategorie (`Hungarian masculine given names`) i wzorce w intro (`of Welsh origin`).
4. **Wikisłowniki** — en.wiktionary (kategorie `given names from X`) i pl.wiktionary (sekcje z etymologią).
5. **Dziedziczenie** — „Ola to zdrobnienie Aleksandry". Parsujemy relacje z intro polskiej Wikipedii, śledzimy cele przekierowań. Działa w max. 3 przebiegach.
6. **Morfologia** — ostatnia deska: żeńska forma bez etymologii dziedziczy po męskiej (`Karolina → Karol`, przez końcówki `-ina/-yna/-a`).

Wszystko ląduje w cache (`.cache_wiki/`). Jak się przerwie — wznawiasz bez straty.

### Leniwe opisy

Opisy to jakieś 40% danych (surowo ~2,3 MB). Zamiast ładować wszystko na start, trzymamy je w osobnych plikach `opisy/<litera>.js`. Strona doczytuje je dynamicznym `<script>` dopiero gdy klikniesz pierwszy wiersz na daną literę. Start lżeje z ~2,3 MB do ~0,7 MB (po gzipie). Działa pod `file://` i z CSP.

### Powiązania między imionami

Każde imię może mieć informację, od kogo pochodzi (`bazowe`) i co od niego pochodzi (`pochodne`). Relacje są klikalne — przenoszą do konkretnego imienia, luzując tylko te filtry, które by je ukryły. Walidacja: imię bazowe musi istnieć w PESEL-u.

## Czym to jest zrobione

- **Frontend**: `index.html` — HTML, CSS i JS w jednym pliku. Zero frameworków, zero npm. ES5 dla kompatybilności.
- **CSS**: custom properties, dark/light theme (`data-theme` + `prefers-color-scheme`), flexbox, sticky nagłówki, tooltipy na `::after` + `data-tip`.
- **JS**: stan filtrów w URL (`history.replaceState`), sortowanie, paginacja, leniwe ładowanie shardów opisów.
- **Service worker** (`sw.js` v4): network-first, z cache jako fallbackiem. Offline działa, a po wdrożeniu nikt nie utknie na starej wersji.
- **CSP**: `default-src 'self'`, `style-src` z Google Fonts, `connect-src` tylko GoatCounter.
- **Czcionki**: Baloo 2 (nagłówek, imiona) + Atkinson Hyperlegible (tekst).
- **Backend**: Python 3.13 — `builder/zbuduj_dataset.py`. Zależności: `requests`, `openpyxl`. Output to statyczne pliki.
- **CI/CD**: GitHub Actions — przy pushu do main i raz w miesiącu z crona buduje dane i wrzuca na GitHub Pages (plus opcjonalny deploy FTP).
- **Hosting**: statyczne pliki, dowolny HTTP server albo Pages.

## Jak to odpalić lokalnie

```bash
pip install requests openpyxl
python3 builder/zbuduj_dataset.py --limit 300   # na próbę (~top 300 imion)
python3 builder/zbuduj_dataset.py               # pełen bieg (~godzina)
python3 builder/zbuduj_dataset.py --incremental # tylko uzupełnia braki
python3 -m http.server 8080
# → http://localhost:8080
```

Przydatne flagi: `--limit N`, `--incremental`, `--skip-pl`, `--skip-en`, `--skip-wd`, `--skip-wikt`, `--skip-zaimki`, `--od-nowa`, `--no-sleep`, `--shutdown`.

## Audyt jakości

`python3 builder/audyt_dataset.py` sprawdza każdy build. Pięć reguł: czy opis to nie statystyki PESEL (R1), czy to nie lista imienin (R2), czy artykuł na pewno jest o imieniu (R3), czy opis nie jest za krótki (R4), czy w ogóle wspomina o imieniu (R5). Raport z przykładami trafia do `builder/AUDYT.md`.

## Struktura katalogów

```
.
├── index.html              # frontend
├── dane.js                 # dane (bez opisów)
├── opisy/*.js              # shardy opisów (leniwe)
├── dataset_*.json          # pełne datasety (JSON)
├── dataset_*.csv           # pełne datasety (CSV)
├── builder/                # skrypty budujące dane
│   ├── zbuduj_dataset.py   # główny
│   ├── audyt_dataset.py    # kontrola jakości
│   ├── wzbogac_opisy.py    # dodatkowe wzbogacanie
│   ├── wzbogac_nowe_wiki.py
│   ├── DOKUMENTACJA.md     # pełna dokumentacja
│   └── AUDYT.md            # raport z audytu
├── sw.js                   # service worker
├── count.js                # GoatCounter (self-hosted)
├── kontakt.html            # kontakt
├── .cache_wiki/            # cache zapytań wiki
├── raw_pesel/              # XLSX z dane.gov.pl
└── .github/workflows/      # CI/CD
```

## Źródła i podziękowania

- Rejestr PESEL: [dane.gov.pl](https://dane.gov.pl/pl/dataset/1667)
- Imiona niebinarne: [zaimki.pl](https://zaimki.pl/imiona) — kolektyw [Rada Języka Neutralnego](https://zaimki.pl/kolektyw-rjn)
- Opisy: Wikipedia (CC BY-SA) przez [MinT](https://translate.wmcloud.org/)
- Flaga w logo: flaga transpłciowa
- Made in Warsaw

## Licencja

[OQL](https://gitlab.com/PronounsPage/PronounsPage/-/blob/main/LICENSE) — Open Queer License (zgodna z zaimki.pl).
