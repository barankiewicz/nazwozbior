# Nazwozbiór 🏳️‍⚧️

> **[nazwozbior.pl](https://nazwozbior.pl)**

Przeglądarka imion z rejestru PESEL i niebinarnych z [zaimki.pl](https://zaimki.pl/imiona). Bez logowania, bez ciasteczek, bez śledzenia. Zrobione przez osoby trans dla osób trans, ale korzystać może każdy. Szukasz imienia dla siebie? Myślisz o zmianie? Chcesz wiedzieć, skąd się wzięło Twoje? To tu.

## Co tu jest

**~50 tys. imion** z PESEL-u. Żeńskie i męskie. Z danymi o tym, ile osób nosi je jako pierwsze, a ile jako drugie. Źródło: [dane.gov.pl](https://dane.gov.pl/pl/dataset/1667). Odświeżamy raz w miesiącu.

**~2700 imion unisex** – sami je wyliczamy. Imię pojawia się zarówno u osób z metryką żeńską, jak i męską, przynajmniej po 10% w obu grupach. Nie ma tego w rejestrze, to nasza robota.

**~220 imion niebinarnych** z [zaimki.pl/imiona](https://zaimki.pl/imiona). Każde ma profil: znaczenie, pochodzenie, użycie, status w urzędach, plusy, minusy, imieniny, znane osoby. Bazę prowadzi kolektyw Rada Języka Neutralnego.

**Opisy i etymologia** z Wikipedii. Polska, angielska, ukraińska, rosyjska, wietnamska. Tłumaczy [MinT](https://translate.wmcloud.org/), automatycznie.

**Kolumna ż / m** – ile procent nadań żeńskich, ile męskich. Im bliżej 50/50, tym bardziej neutralne imię. Widać w zakładkach „niebinarne” i „unisex”.

**Ile tego wypełnione.** Pochodzenie rozpoznajemy dla 99,5% nadań, opis dla 97% – licząc po tym, ile osób faktycznie nosi dane imię. Surowo, każde imię tak samo, wychodzi 52% i 28%; nierozpoznany zostaje długi ogon bardzo rzadkich i obcych zapisów.

## Jak używać

Wszystkie filtry zapisują się w adresie strony. Możesz skopiować link i wysłać komuś dokładnie ten widok.

- **Rodzaj**: żeńskie, męskie, unisex (PESEL, nasze wyliczenia), niebinarne (zaimki.pl), wszystkie naraz
- **Długość**: suwak 1–35 liter
- **Wystąpienia**: minimum i maksimum nadań
- **Pochodzenie**: greckie, hebrajskie, łacińskie, słowiańskie, germańskie i jeszcze ~40 innych. Każda opcja pokazuje, ile imion pasuje
- **Szukajka**: zwykłe wyszukiwanie i regex. Przełącznik `.*` przy polu
- **Sortowanie**: klikasz nagłówek kolumny. Drugi raz odwraca kierunek
- **Szczegóły**: klikasz wiersz i rozwija ci się etymologia, wykres popularności imienia od 2000 do 2024, imiona pochodne i bazowe. Wszystkie klikalne. Dla niebinarnych pokazuje pełen profil z zaimki.pl
- **Losuj**: dostajesz jedno imię z widocznych wyników
- **CSV**: pobierasz wszystko co widać jako plik
- **Stronicowanie**: 250 imion na stronę, zawsze możesz rozwinąć wszystko

## Jak to działa pod spodem

Strona jest w całości po stronie klienta. Żadnego backendu. Jeden plik HTML i jeden plik `dane.js` z wygenerowanymi danymi.

```
dane.gov.pl (PESEL, XLSX)        zaimki.pl (API)
        │                              │
        ▼                              ▼
┌─────── builder/zbuduj_dataset.py ──────────────────┐
│ 1. pobiera XLSX z PESEL-u                           │
│ 2. buduje osobne datasety dla imion męskich i żeńskich
│ 3. szuka pochodzenia i opisu dla każdego imienia:   │
│    PL Wikipedia → Wikidane → EN Wikipedia           │
│    → Wikisłowniki → dziedziczenie → morfologia       │
│ 4. pobiera imiona niebinarne przez API              │
│ 5. zapisuje wszystko do dane.js + dataset_*.json    │
│    + opisy/*.js                                     │
└─────────────────────────────────────────────────────┘
        │
        ▼
   dane.js  ──►  index.html (vanilla JS, jeden plik)
```

### Skąd znamy pochodzenie imienia

Każde imię z PESEL-u przeglądamy przez kilka źródeł, po kolei. Jak któreś trafi, następne już nie szukają.

1. **Polska Wikipedia**. Analizujemy intro artykułu i kategorie. Szukamy zwrotów w rodzaju „pochodzenia greckiego” albo „z języka hebrajskiego”. Z intro wyciągamy też opis (promujemy akapity o etymologii, wyrzucamy statystyki PESEL).
2. **Wikidane**. Ściągamy hurtem wszystkie imiona przez SPARQL, shardując zapytania po MD5. Dostajemy ~55 tys. imion przypisanych do języka. Dalsze dopasowania robimy lokalnie.
3. **Angielska Wikipedia**. Kategorie w stylu `Hungarian masculine given names` i wzorce w tekście (`of Welsh origin`).
4. **Wikisłowniki**. en.wiktionary szuka `given names from X`, pl.wiktionary czyta sekcje z etymologią.
5. **Dziedziczenie**. „Ola to zdrobnienie Aleksandry”. Wyciągamy takie relacje z intro polskiej Wikipedii i sprawdzamy przekierowania. Maksymalnie 3 przebiegi.
6. **Morfologia**. Żeńska forma bez etymologii dostaje pochodzenie od swojej męskiej wersji. Karolina ← Karol, przez końcówki `-ina`, `-yna`, `-a`.

Cache trzymamy w `.cache_wiki/`. Przerwiesz, uruchomisz jeszcze raz i leci od miejsca, gdzie skończyło.

### Opisy ładują się na raty

Opisy to ~40% wszystkich danych. Zamiast pakować je do głównego pliku, trzymamy w shardach `opisy/<litera>.js`. Strona doczytuje literę dopiero jak klikniesz pierwsze imię na nią. Dzięki temu start strony waży ~0,7 MB zamiast ~2,3 MB. Działa nawet przy `file://`.

### Powiązania

Każde imię wie, od kogo pochodzi (`bazowe`) i jakie imiona pochodzą od niego (`pochodne`). Wszystkie te linki są klikalne, przenoszą od razu do właściwego wiersza, same luzują filtry.

## Stack

Frontend to jeden plik `index.html`: HTML, CSS i JS. Żadnych frameworków, żadnego npm.

- **CSS**: custom properties, ciemny/jasny motyw, flexbox, sticky nagłówki, tooltipy na `data-tip` + `::after`
- **JS**: ES5, stan filtrów w URL-u (`history.replaceState`), sortowanie, paginacja, leniwe shardy
- **Service worker**: `sw.js`, network-first z cache fallbackiem. Działa offline
- **CSP**: wszystko zablokowane poza tym co trzeba
- **Czcionki**: Baloo 2 do nagłówków, Atkinson Hyperlegible do tekstu
- **Backend/dane**: Python 3.13, `requests` + `openpyxl`. Skrypt buduje statyczne pliki
- **CI/CD**: GitHub Actions przy każdym pushu wysyła pliki na FTP (lh.pl). Dane buduje się lokalnie
- **Hosting**: statyczne pliki

## Audyt jakości

`python3 builder/audyt_dataset.py` przechodzi po datasetach i sprawdza 5 rzeczy: czy opis to nie statystyki PESEL zamiast etymologii, czy to nie lista imienin, czy artykuł z Wikipedii faktycznie jest o imieniu, czy opis nie jest za krótki, czy w ogóle wspomina imię. Raport z przykładami ląduje w `builder/AUDYT.md`.

## Pliki

```
.
├── index.html              # frontend (HTML + CSS + JS)
├── dane.js                 # dane bez opisów
├── opisy/*.js              # opisy, shardowane po literze
├── dataset_*.json, *.csv   # pełne datasety
├── builder/                # skrypty budujące
│   ├── zbuduj_dataset.py    # cały pipeline w jednym pliku
│   ├── audyt_dataset.py
│   ├── DOKUMENTACJA.md
│   └── AUDYT.md
├── sw.js, count.js         # service worker, analityka
├── kontakt.html
├── .cache_wiki/, raw_pesel/# cache (w .gitignore)
└── .github/workflows/      # CI/CD
```

## Podziękowania

- Rejestr PESEL: [dane.gov.pl](https://dane.gov.pl/pl/dataset/1667)
- Imiona niebinarne: [Rada Języka Neutralnego](https://zaimki.pl/kolektyw-rjn)
- Tłumaczenia: [MinT / NLLB](https://translate.wmcloud.org/)
- Flaga w logo: flaga transpłciowa
- Made in Warsaw

## Licencja

[OQL](https://gitlab.com/PronounsPage/PronounsPage/-/blob/main/LICENSE), Open Queer License. Taka sama, jak na zaimki.pl.
