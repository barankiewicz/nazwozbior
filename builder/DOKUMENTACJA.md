# Nazwozbiór — jak to działa

Statyczna strona do przeglądania imion z rejestru PESEL oraz imion niebinarnych
z zaimki.pl. Zero backendu: cały „serwer" to jeden plik `dane.js` generowany
przez `zbuduj_dataset.py`. Ten dokument opisuje cały proces krok po kroku.

## Architektura w jednym obrazku

```
dane.gov.pl (PESEL, XLSX)        zaimki.pl (API)
        │                              │
        ▼                              ▼
┌─────────────────── zbuduj_dataset.py ───────────────────┐
│ 1. pobierz XLSX     4. wzbogacanie kaskadowe:           │
│ 2. scal datasety       PL Wiki → Wikidane → EN Wiki     │
│ 3. (limit/merge)       → dziedziczenie pochodzenia      │
│ 5. imiona niebinarne (zaimki.pl)                        │
│ 6. zapis: dataset_*.csv/.json + dane.js                 │
└──────────────────────────────────────────────────────────┘
        │
        ▼
   dane.js  ──►  index.html (vanilla JS, brak frameworków)
```

## Krok 1 — pobranie danych PESEL

- Źródło: [dane.gov.pl, dataset 1667](https://dane.gov.pl/pl/dataset/1667) —
  oficjalne listy imion osób żyjących w rejestrze PESEL.
- `pobierz_zasoby()` listuje zasoby przez API, `wybierz_najnowsze()` wybiera
  po dacie cztery pliki XLSX: imiona męskie/żeńskie × pierwsze/drugie imię.
- Pliki lądują w `raw_pesel/` i nie są pobierane ponownie, jeśli już istnieją.

## Krok 2 — budowa datasetów

- `wczytaj_liczby()` czyta XLSX (openpyxl), normalizuje pisownię imienia
  (`titlecase_pl`, np. "ANNA MARIA" → "Anna Maria") i sumuje wystąpienia.
- `NameDataset.from_pesel()` skleja imiona pierwsze i drugie w wiersze
  `{imie, wystapienia_pierwsze, wystapienia_drugie}`, posortowane po popularności.
- Tryb `--incremental` wczytuje istniejące `dataset_*.json` i dociąga dane
  tylko dla imion bez pochodzenia/opisu. `--limit N` ogranicza do N
  najpopularniejszych imion każdej płci (do szybkich testów).

## Krok 3 — wzbogacanie: skąd bierze się „pochodzenie" i opis

Źródła odpytujemy **kaskadowo, od najtańszego i najpewniejszego**. Każde
kolejne źródło dostaje tylko imiona, które wciąż nie mają pochodzenia.
Wszystko jest cache'owane na dysku w `.cache_wiki/`, więc przerwany bieg
wznawia się bez strat.

### 3a. Polska Wikipedia (faza 1 + 2)

- **Faza 1** (`_faza1_istnienie`): zapytania wsadowe po 20 tytułów
  (`prop=extracts|categories`). Dla każdego imienia dostajemy intro (czysty
  tekst) i kategorie. Cache: `phase1.json`.
- **Faza 1b — retry „(imię)"**: strony ujednoznaczniające ORAZ artykuły,
  które istnieją, ale nie są o imieniu (Dominika = państwo, Piotr = lista
  osób), dostają drugą szansę pod tytułem `X (imię)`. Flaga `imie_retry`
  w cache pilnuje, żeby nie sprawdzać w kółko.
- **Faza 2** (`_faza2_opis`): dla istniejących artykułów pobieramy sekcję 0
  jako HTML; do cache trafiają **surowe akapity** (`wytnij_akapity`, bez
  tabel/infoboksów — to z nich brały się opisy typu „682 516 osób w Polsce").
  Wyboru dokonuje `wybierz_akapit`: scoring premiuje akapity niosące
  ZNACZENIE („pochodzi", „oznacza", „etymologia"…), a odrzuca statystyki
  PESEL i listy imienin. Brak sensownego akapitu => brak opisu (strona
  mówi wtedy wprost „źródła nie podają znaczenia"). Dzięki surowym akapitom
  w cache zmiany scoringu nie wymagają ponownego pobierania.
  Opis dostają tylko artykuły, które nie są ewidentnie o czymś innym.
  Cache: `phase2.json` (klucz `src_title` wymusza refetch po zmianie
  artykułu w fazie 1b).
- **Wykrywanie pochodzenia** (`wykryj_pochodzenie`): wzorce regex na intro
  („pochodzenia greckiego", „z języka hebrajskiego", „staropolskie imię"…)
  oraz kategorie („Imiona pochodzenia łacińskiego"). Trafiony fragment
  mapujemy na slug przez `ORIGIN_MAP` (np. „grec…" → `greckie`).
- Filtr `is_name_article()` odsiewa artykuły o zespołach, rzekach, filmach
  itp., żeby nie przypisać imieniu opisu czegoś zupełnie innego.

### 3b. Wikidane — hurtowy dump (nowe podejście)

Zamiast pytać o każde imię osobno (80 000+ zapytań, niska skuteczność),
ściągamy **cały zbiór imion z Wikidanych jednorazowo**:

- `fetch_wikidata_bulk()` wykonuje zapytania SPARQL o wszystkie elementy klas:
  imię (Q202444), imię męskie (Q12308941), imię żeńskie (Q11879590),
  imię unisex (Q3409032) — wraz z właściwością **P407 „język nazwy"**.
- WDQS ma twardy timeout 60 s, więc każdą klasę tniemy na **16 shardów po
  pierwszym znaku MD5(QID)** → 64 małe zapytania. Jeśli shard mimo to nie
  schodzi, dzielimy go na 16 pod-shardów po drugim znaku MD5.
- Wynik: `.cache_wiki/wd_bulk.json` (~55 tys. imion, ~2 MB) — mapa
  `imię → {polska etykieta języka → liczba wystąpień}`.
- Dopasowanie jest **lokalne i natychmiastowe**: `imie.casefold()` w mapie,
  a `origin_from_wd_langs()` wybiera najczęstszy język i mapuje go przez
  `ORIGIN_MAP` („język litewski" → `litewskie`).
- Dump pobiera się raz; kolejne biegi (też w CI) używają cache.

### 3b-bis. Wikidane — opisy (drugi rzut)

Wiele elementów Wikidanych nie ma P407, ale ma opis w stylu „Polish masculine
given name" albo „imię męskie pochodzenia greckiego". `fetch_wikidata_desc()`
ściąga je tym samym mechanizmem shardowanym (FILTER NOT EXISTS na P407,
opisy en+pl) do `wd_desc.json` (~57 tys. imion). Dopasowanie lokalne:
opis pl → `ORIGIN_MAP`, opis en → `EN_CATEGORY_ORIGINS`. Źródło w logach: `WDD`.

### 3c. Angielska Wikipedia

Dla imion wciąż bez pochodzenia: zapytania wsadowe o **kategorie + intro**.

- Kategorie typu „Hungarian masculine given names" mapujemy przez
  `EN_CATEGORY_ORIGINS`.
- Nowość: gdy kategorie nie wystarczą, parsujemy intro wzorcami
  `EN_TEXT_PATTERNS` („of Welsh origin", „is a Hebrew given name",
  „derived from the Old Norse…"). Cache: `phase_en.json`.

### 3c-bis. Wikisłowniki (en + pl Wiktionary)

Dla imion wciąż bez pochodzenia, w kolejności:

- **en.wiktionary** (`_apply_enrich_wikt_en`): kategorie typu
  „Polish female given names **from Latin**" wprost kodują etymologię —
  parsujemy `given names from X` i mapujemy przez `EN_CATEGORY_ORIGINS`.
  Cache: `phase_wikt_en.json`. Źródło: `WIKT-EN`.
- **pl.wiktionary** (`_apply_enrich_wikt_pl`): pełny ekstrakt strony,
  z którego wycinamy okna wokół „etymologia" i czytamy skróty językowe
  („łac.", „gr.", „hebr.", „prasł." — mapa `WIKT_PL_ABBREV`) albo pełne
  przymiotniki. Wpis musi wyglądać na imię (`imię żeńskie/męskie`
  w znaczeniach). Cache: `phase_wikt_pl.json`. Źródło: `WIKT-PL`.

Flaga `--skip-wikt` pomija oba.

### 3d. Dziedziczenie pochodzenia (nowy etap)

Mnóstwo imion to zdrobnienia i warianty bez własnej etymologii na Wikipedii
(„Ola — zdrobnienie imienia Aleksandra"). `_inherit_origins()`:

1. Z intro PL Wikipedii wyciąga imię bazowe wzorcami `VARIANT_PATTERNS`
   („zdrobnienie/forma/wariant/odpowiednik… imienia X").
2. Pochodzenie bazy bierze z już wzbogaconych wierszy obu płci albo
   wprost z dumpu Wikidanych.
3. Działa w maks. 3 przebiegach, bo baza mogła sama odziedziczyć pochodzenie.

Bazą jest też **cel przekierowania** PL Wikipedii (Gosia → Małgorzata).
Wiersze tak uzupełnione mają w logach źródło `ODZ`.

### 3d-bis. Morfologia (ostatnia deska ratunku)

`_apply_morphology()`: żeńska forma bez etymologii dziedziczy po męskiej
bazie, jeśli ta istnieje w rejestrze i MA pochodzenie — `Karolina → Karol`
(końcówki `-ina/-yna` i `-a`). Świadomie konserwatywne (bez zdrobnień,
które są nieregularne). Źródło: `MORF`.

### 3e. Powiązania imion (bazowe / pochodne)

`link_bazowe()` używa tej samej ekstrakcji (`extract_base_relations` —
relacja + imię, np. „żeński odpowiednik" + „Karol") i zapisuje w wierszach:

- `bazowe`: lista `{relacja, imie}` — np. Karolina →
  `[{"relacja": "żeński odpowiednik", "imie": "Karol"}]`,
- `pochodne`: relacja odwrotna — np. Jan → `["Iwo", "Janina", "Jaś", …]`.

**Walidacja**: imię bazowe musi istnieć w rejestrze PESEL (w dowolnej płci),
self-referencje i duplikaty są odrzucane. Pola istnieją tylko tam, gdzie coś
znaleziono (brak pustych kluczy w `dane.js`).

### Logi i statystyki

Po każdym źródle `log_stats()` wypisuje przyrost i bilans, np.:

```
[PL] +289 skat.  PL=289  brak=19/308 (6.2%)
[WD] +123 skat.  PL=289 WD=123  brak=0/412 (0.0%)
```

## Krok 4 — imiona niebinarne z zaimki.pl

- `pobierz_zaimki()` ściąga `https://zaimki.pl/api/names` (publiczne API
  serwisu prowadzonego przez kolektyw „Rada Języka Neutralnego"); przy
  niedostępności używa cache `zaimki.json`.
- `przetworz_zaimki()`:
  - filtruje `locale=pl`, zaakceptowane, nieusunięte;
  - scala duplikaty (pierwsza niepusta wartość pola wygrywa);
  - rozbija warianty zapisu („Aleks/Alex") na listę `warianty`;
  - normalizuje pochodzenie do naszego sluga (`origin_slug_pl`), zachowując
    oryginalny opis w `pochodzenie_opis`;
  - zamienia „znane osoby" z Markdownu na bezpieczny HTML, formatuje
    imieniny („02-18" → „18 lutego"), zbiera linki.
- Wynik: `dataset_niebinarne.json` + `window.DANE_NIEBINARNE` w `dane.js`.
- Flaga `--skip-zaimki` pomija ten krok.

## Krok 5 — zapis

`_save_all()` zapisuje `dataset_meskie.*`, `dataset_zenskie.*`,
`dataset_niebinarne.json` oraz dane dla strony w dwóch częściach:

- `dane.js` — **rdzeń bez opisów** (imię, liczby, pochodzenie, źródło,
  powiązania) z globalami `DANE_MESKIE`, `DANE_ZENSKIE`, `DANE_NIEBINARNE`;
- `opisy/<litera>.js` — **leniwe shardy opisów** (`window.NZ_OPISY["a"]={…}`),
  dociągane przez stronę dynamicznym `<script>` dopiero przy pierwszym
  rozwinięciu wiersza na daną literę (działa z `file://` i pod CSP,
  w przeciwieństwie do `fetch`).

Opisy to ~40% danych, więc start strony lżeje z ~2,3 MB do ~0,7 MB (gzip).
Frontend jest kompatybilny wstecz: gdy wiersze mają jeszcze `opis_html`
(stary format), używa go bez dociągania shardów.

## Frontend (index.html)

Jeden plik: HTML + CSS + vanilla JS. Dane wczytuje z `dane.js`.

- **Tryby**: żeńskie / męskie / niebinarne / wszystkie. Stan filtrów żyje
  w URL-u (`?gender=nb&origin=...`), więc widoki da się linkować.
- **Tryb niebinarne**: tabela zmienia kolumny na „w rej. żeńskim" /
  „w rej. męskim". Liczniki to suma wystąpień (1. + 2. imię) danego imienia
  w obu rejestrach PESEL, liczona w przeglądarce z już załadowanych
  datasetów — z sumowaniem po wariantach zapisu. Panel szczegółów pokazuje
  komplet danych zaimki.pl: znaczenie, pochodzenie, użycie na świecie,
  zapis w rejestrach, plusy/minusy, imieniny, znane osoby, linki.
- **Powiązania imion**: panel szczegółów pokazuje klikalne relacje
  („Ola — zdrobnienie imienia *Aleksandra*", a u Aleksandry „pochodne
  imiona: …"). Klik (`gotoName()`) przełącza w razie potrzeby tryb rodzaju,
  luzuje tylko te filtry, które ukryłyby cel, wyszukuje imię i rozwija
  jego wiersz.
- Filtry (długość, wystąpienia, pochodzenie, szukajka), sortowanie,
  paginacja, losowanie i eksport CSV działają we wszystkich trybach
  (CSV ma w trybie niebinarnym własny zestaw kolumn).
- **Service worker** (`sw.js`): network-first z fallbackiem do cache
  (offline działa, a po wdrożeniu nikt nie utknie na starej wersji).
  Przy zmianach frontu podbij wersję cache (`nazwozbior-vN`).

## Audyt jakości

`python3 audyt_dataset.py` — powtarzalna kontrola po każdym buildzie.
Reguły: opis-statystyki (R1), opis-imieniny (R2), artykuł nie o imieniu (R3),
opis podejrzanie krótki (R4), opis bez wzmianki o imieniu (R5).
Raport z przykładami (posortowanymi po popularności imienia) ląduje
w `AUDYT.md`. Wiersze datasetu niosą też pole `zrodlo` (PL/WD/WDD/EN/
WIKT-EN/WIKT-PL/ODZ/MORF) + `zrodlo_baza` — strona pokazuje przy
pochodzeniu link do źródła, a audyt może filtrować po źródłach.

## CI/CD

`.github/workflows/build.yml`: na push do `main` (i raz w miesiącu z crona)
GitHub Actions odpala pełny `python3 zbuduj_dataset.py` (z cache
`.cache_wiki` między biegami) i publikuje całość na GitHub Pages.

## Uruchamianie lokalnie

```bash
pip install requests openpyxl
python3 zbuduj_dataset.py --limit 300   # szybki test
python3 zbuduj_dataset.py               # pełny bieg (długo!)
python3 zbuduj_dataset.py --incremental # tylko braki
python3 -m http.server                  # podgląd strony
```

Flagi: `--limit N`, `--incremental`, `--skip-pl`, `--skip-en`, `--skip-wd`,
`--skip-zaimki`, `--od-nowa` (czyści cache), `--no-sleep`, `--shutdown`.

## Jak rozszerzać

- **Nowy slug pochodzenia**: dodaj fragmenty do `ORIGIN_MAP` (PL) i/lub
  `EN_CATEGORY_ORIGINS` (EN) w `zbuduj_dataset.py` **oraz** etykietę do
  `ORIGIN_LABELS` w `index.html` — inaczej na stronie pokaże się surowy slug.
- **Nowe źródło wzbogacania**: dopisz metodę w `DatasetBuilder`, wywołaj ją
  w `_enrich()` w odpowiednim miejscu kaskady (tylko dla wierszy bez
  `pochodzenie`), ustawiaj `r["_zrodlo"]`, a statystyki w `log_stats()`
  podbiją się same.
- **Wzorce tekstowe**: `ORIGIN_PATTERNS` (PL intro), `EN_TEXT_PATTERNS`
  (EN intro), `VARIANT_PATTERNS` (dziedziczenie). Po zmianach map nie trzeba
  nic ponownie pobierać — parsowanie działa na cache.
