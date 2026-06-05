#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zbuduj_dataset.py
=================
Buduje dane dla strony "Znajdź swoje imię".

Co robi:
  1. Pobiera z dane.gov.pl (dataset 1667) NAJNOWSZE listy imion z rejestru PESEL:
       - imiona meskie:  pierwsze + drugie
       - imiona zenskie: pierwsze + drugie
  2. Skleja je w dwa datasety:
       meskie / zenskie  ->  kolumny: imie, wystapienia_pierwsze, wystapienia_drugie
  3. Wzbogaca KAZDE imie o dane z polskiej Wikipedii:
       - pochodzenie (wykryte z tekstu, np. "greckie", "lacinskie", "slowianskie")
       - opis = PIERWSZY AKAPIT artykulu, z DZIALAJACYMI linkami (przepisanymi na pelne URL-e)
  4. Zapisuje wynik:
       - dataset_meskie.csv / .json
       - dataset_zenskie.csv / .json
       - dane.js   <-- tego uzywa strona (index.html)

Uruchomienie:
    pip install requests openpyxl
    python3 zbuduj_dataset.py

Wskazowki:
  - Skrypt jest WZNAWIALNY. Postep zapisuje w folderze .cache_wiki/.
    Mozesz go przerwac (Ctrl+C) i uruchomic ponownie - dokonczy od miejsca przerwania.
  - Wzbogacenie WSZYSTKICH imion (dziesiatki tysiecy) trwa dlugo. Wiekszosc bardzo
    rzadkich imion (literowki, transliteracje) nie ma artykulu na Wikipedii - to normalne,
    takie imiona zostana w danych bez opisu, tylko z liczba wystapien.
  - Chcesz szybki test? Ustaw nizej LIMIT_NA_PLEC = 300 (wzbogaci tylko 300 najpopularniejszych
    imion kazdej plci), albo uruchom:  python3 zbuduj_dataset.py --limit 300
"""

import os, re, csv, json, time, html, argparse, sys
from collections import deque

try:
    import requests
except ImportError:
    sys.exit("Brak biblioteki 'requests'. Zainstaluj: pip install requests")
try:
    import openpyxl
except ImportError:
    sys.exit("Brak biblioteki 'openpyxl'. Zainstaluj: pip install openpyxl")

# ------------------------------------------------------------------ KONFIG ---
DATASET_ID      = 1667
LIMIT_NA_PLEC   = None      # None = wszystkie imiona; np. 300 = tylko 300 najpopularniejszych kazdej plci
WIKI_LANG       = "pl"
RAW_DIR         = "raw_pesel"
CACHE_DIR       = ".cache_wiki"
USER_AGENT      = "PoImieniu/1.0 (https://github.com/barankiewicz; barankiewicz@protonmail.ch)"
MAXLAG          = 5             # zalecany przez MediaWiki dla skryptow
RATE_LIMIT_REQ  = 180           # max zapytan na okno czasowe (90% oficjalnego limitu 200)
RATE_LIMIT_WIN  = 60            # okno czasowe w sekundach
MAX_RETRIES     = 5             # maksymalna liczba powtorzen przy bledach HTTP/connection
BATCH_SIZE      = 50            # ile tytulow na jedno zapytanie wsadowe (faza 1)
API             = f"https://{WIKI_LANG}.wikipedia.org/w/api.php"

# Normalizacja pochodzenia: fragment slowa -> etykieta kanoniczna (do dropdownu)
ORIGIN_MAP = [
    ("starogreck", "greckie"), ("grec", "greckie"),
    ("lacin", "lacinskie"), ("łaci", "lacinskie"),
    ("starogerm", "germanskie"), ("german", "germanskie"),
    ("starodolnoniem", "germanskie"), ("staronordyck", "skandynawskie"),
    ("skandyna", "skandynawskie"), ("nordyck", "skandynawskie"),
    ("slowia", "slowianskie"), ("słowia", "slowianskie"),
    ("staropol", "staropolskie"),
    ("hebr", "hebrajskie"), ("aramej", "aramejskie"),
    ("celt", "celtyckie"), ("arab", "arabskie"), ("pers", "perskie"),
    ("litew", "litewskie"), ("egip", "egipskie"), ("sanskry", "sanskryckie"),
    ("ind", "indyjskie"), ("turec", "tureckie"), ("baskij", "baskijskie"),
    ("anglosas", "anglosaskie"), ("angiel", "angielskie"),
    ("francus", "francuskie"), ("hiszpa", "hiszpanskie"),
    ("włos", "wloskie"), ("wlos", "wloskie"), ("roman", "romanskie"),
    ("ros", "rosyjskie"), ("rusk", "ruskie"), ("ukrai", "ukrainskie"),
    ("wegier", "wegierskie"), ("węgier", "wegierskie"),
    ("fin", "finskie"), ("etiop", "etiopskie"), ("fenick", "fenickie"),
    ("akadyj", "akadyjskie"), ("sumeryj", "sumeryjskie"), ("egipsk", "egipskie"),
]

# -------------------------------------------------------- RATE LIMIT / API KLIENT

class RateLimiter:
    def __init__(self, max_requests, window_seconds):
        self.max_req = max_requests
        self.window = window_seconds
        self._timestamps = deque()

    def wait_if_needed(self):
        now = time.monotonic()
        cutoff = now - self.window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_req:
            sleep = self._timestamps[0] + self.window - now
            if sleep > 0:
                print(f"    osiagnieto limit {self.max_req} req/{self.window}s, czekam {sleep:.0f}s")
                time.sleep(sleep + 0.1)
            now = time.monotonic()
            cutoff = now - self.window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
        self._timestamps.append(now)

class WikiAPIClient:
    def __init__(self, session, rate_limiter, max_retries=MAX_RETRIES):
        self.session = session
        self.ratelimit = rate_limiter
        self.max_retries = max_retries

    def get(self, params, timeout=60):
        self.ratelimit.wait_if_needed()
        params["maxlag"] = MAXLAG
        for attempt in range(self.max_retries):
            try:
                r = self.session.get(API, params=params, timeout=timeout)
                if r.status_code == 429:
                    retry = int(r.headers.get("Retry-After", 5))
                    print(f"    429 Too Many Requests, retry po {retry}s")
                    time.sleep(retry)
                    continue
                if r.status_code in (502, 503, 504):
                    retry = int(r.headers.get("Retry-After", min(60, 2 ** attempt)))
                    print(f"    HTTP {r.status_code}, proba {attempt+1}/{self.max_retries} po {retry}s")
                    time.sleep(retry)
                    continue
                r.raise_for_status()
                return r.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt == self.max_retries - 1:
                    raise
                sleep = min(30, 2 ** attempt)
                print(f"    blad polaczenia: {e}, proba {attempt+1}/{self.max_retries} po {sleep}s")
                time.sleep(sleep)
        raise Exception(f"Przekroczono maksymalna liczbe prob ({self.max_retries}) dla: {params.get('page', params.get('titles', '?'))}")

# ---------------------------------------------------------------- POBIERANIE -

def titlecase_pl(s):
    s = s.strip()
    out = []
    for t in re.split(r'([ \-])', s.lower()):
        out.append(t if t in (' ', '-') or t == '' else t[0].upper() + t[1:])
    return ''.join(out)

def pobierz_zasoby():
    """Zwraca liste zasobow datasetu z API dane.gov.pl."""
    url = f"https://api.dane.gov.pl/1.4/datasets/{DATASET_ID}/resources?lang=pl&page=1&per_page=100"
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    return r.json().get("data", [])

def wybierz_najnowsze(zasoby):
    """Wybiera najnowszy plik (xlsx) dla 4 kategorii."""
    wybor = {}  # klucz -> (data_date, url, title)
    for z in zasoby:
        a = z.get("attributes", {})
        title = (a.get("title") or "").lower()
        fmt = (a.get("format") or "").lower()
        url = a.get("file_url") or a.get("link")
        date = a.get("data_date") or ""
        if fmt != "xlsx" or not url:
            continue
        plec = "m" if ("męsk" in title or "mesk" in title) else ("z" if ("żeńsk" in title or "zensk" in title) else None)
        if plec is None:
            continue
        kolejnosc = "drugie" if "drugie" in title else ("pierwsze" if "pierwsze" in title else None)
        if kolejnosc is None:
            continue
        key = f"{plec}_{kolejnosc}"
        if key not in wybor or date > wybor[key][0]:
            wybor[key] = (date, url, a.get("title"))
    return wybor

def sciagnij(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)

def wczytaj_liczby(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    counts = {}
    first = True
    for row in ws.iter_rows(values_only=True):
        if first:
            first = False
            continue
        if not row or row[0] is None:
            continue
        name = str(row[0]).strip()
        if not name:
            continue
        try:
            cnt = int(row[2])
        except (TypeError, ValueError):
            continue
        name = titlecase_pl(name)
        counts[name] = counts.get(name, 0) + cnt
    wb.close()
    return counts

def zbuduj(first_path, second_path):
    first = wczytaj_liczby(first_path)
    second = wczytaj_liczby(second_path)
    rows = []
    for n in (set(first) | set(second)):
        rows.append({
            "imie": n,
            "wystapienia_pierwsze": first.get(n, 0),
            "wystapienia_drugie": second.get(n, 0),
        })
    rows.sort(key=lambda r: -(r["wystapienia_pierwsze"] + r["wystapienia_drugie"]))
    return rows

# ------------------------------------------------------------------- WIKIPEDIA

def load_cache(name):
    p = os.path.join(CACHE_DIR, name)
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(name, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    json.dump(data, open(os.path.join(CACHE_DIR, name), "w", encoding="utf-8"), ensure_ascii=False)

def wykryj_pochodzenie(plain):
    """Z tekstu wyciaga pochodzenie i normalizuje do etykiety."""
    if not plain:
        return ""
    m = re.search(r'pochodzeni[ae]\s+([a-ząćęłńóśźż]+)', plain.lower())
    token = m.group(1) if m else ""
    if not token:
        # czasem: "imie ... greckie" bez slowa "pochodzenia"
        m2 = re.search(r'imi[eę]\b[^.]{0,40}?\b([a-ząćęłńóśźż]*(?:greck|łaci|german|słowia|hebr)[a-ząćęłńóśźż]*)', plain.lower())
        token = m2.group(1) if m2 else ""
    if not token:
        return ""
    for frag, label in ORIGIN_MAP:
        if frag in token:
            return label
    return ""

def faza1_istnienie(names, client):
    """Wsadowo: sprawdza istnienie artykulu + pobiera plaintext intro (do pochodzenia)."""
    cache = load_cache("phase1.json")
    todo = [n for n in names if n not in cache]
    print(f"  Faza 1 (istnienie/pochodzenie): {len(todo)} nowych z {len(names)} (w cache: {len(cache)})")
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        params = {
            "action": "query", "format": "json", "prop": "extracts|pageprops",
            "exintro": 1, "explaintext": 1, "redirects": 1, "formatversion": 2,
            "titles": "|".join(batch),
        }
        try:
            data = client.get(params)
        except Exception as e:
            print(f"    blad batch ({batch[0]}...{batch[-1]}): {e}")
            for n in batch:
                cache[n] = {"exists": False, "plain": "", "disambig": False}
            continue
        ret = {}
        for pg in data.get("query", {}).get("pages", []):
            title = pg.get("title", "")
            missing = pg.get("missing", False)
            extract = pg.get("extract", "") or ""
            disambig = "disambiguation" in (pg.get("pageprops") or {})
            ret[title] = {"exists": (not missing), "plain": extract, "disambig": disambig}
        norm = {}
        for n in batch:
            norm[n] = n
        for rd in data.get("query", {}).get("redirects", []):
            norm[rd["from"]] = rd["to"]
        for nm in data.get("query", {}).get("normalized", []):
            norm[nm["from"]] = nm["to"]
        for n in batch:
            t = norm.get(n, n)
            info = ret.get(t) or ret.get(n) or {"exists": False, "plain": "", "disambig": False}
            cache[n] = info
        if (i // BATCH_SIZE) % 5 == 0:
            save_cache("phase1.json", cache)
            print(f"    ...{min(i+BATCH_SIZE,len(todo))}/{len(todo)}")
    save_cache("phase1.json", cache)
    return cache

# czyszczenie pierwszego akapitu HTML
RE_SUP   = re.compile(r'<sup\b[^>]*>.*?</sup>', re.S)
RE_STYLE = re.compile(r'<style\b[^>]*>.*?</style>', re.S)
RE_SPANO = re.compile(r'<span\b[^>]*>')
RE_SPANC = re.compile(r'</span>')
RE_TAGS_KEEP = None

def wyczysc_akapit(html_text):
    """Zostawia pierwszy sensowny <p>, przepisuje linki na pelne URL-e, czysci smieci."""
    if not html_text:
        return ""
    # usun komentarze
    html_text = re.sub(r'<!--.*?-->', '', html_text, flags=re.S)
    html_text = RE_STYLE.sub('', html_text)
    # znajdz wszystkie <p>...</p> i wybierz pierwszy z odpowiednia iloscia tekstu
    paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p>', html_text, flags=re.S)
    chosen = ""
    for p in paragraphs:
        txt = re.sub(r'<[^>]+>', '', p)
        txt = html.unescape(txt).strip()
        if len(txt) >= 40:
            chosen = p
            break
    if not chosen and paragraphs:
        chosen = max(paragraphs, key=lambda p: len(re.sub(r'<[^>]+>', '', p)))
    if not chosen:
        return ""
    s = chosen
    s = RE_SUP.sub('', s)                       # przypisy [1]
    s = re.sub(r'<span\b[^>]*class="[^"]*mw-editsection[^"]*".*?</span>', '', s, flags=re.S)
    # przepisz linki: /wiki/... -> pelny URL, otwieraj w nowej karcie
    def fix_link(m):
        href = m.group(1)
        if href.startswith('/wiki/'):
            full = f"https://{WIKI_LANG}.wikipedia.org" + href
            return f'<a href="{full}" target="_blank" rel="noopener noreferrer">'
        if href.startswith('http'):
            return f'<a href="{href}" target="_blank" rel="noopener noreferrer">'
        # czerwone linki / edycja -> usun link, zostaw tekst
        return '<a>'
    s = re.sub(r'<a\b[^>]*?href="([^"]*)"[^>]*>', fix_link, s)
    s = re.sub(r'<a>(.*?)</a>', r'\1', s, flags=re.S)   # puste <a> -> sam tekst
    # usun spany (zostaw tresc), usun pozostale atrybuty z tagow inline ktore zostawiamy
    s = RE_SPANO.sub('', s); s = RE_SPANC.sub('', s)
    s = re.sub(r'<(b|i|em|strong)\b[^>]*>', r'<\1>', s)
    # wytnij wszystkie tagi POZA dozwolonymi
    s = re.sub(r'</?(?!a\b|b\b|i\b|em\b|strong\b)[a-zA-Z][^>]*>', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def faza2_opis(names, phase1, client):
    """Dla imion ktore maja artykul: pobiera pierwszy akapit z dzialajacymi linkami."""
    cache = load_cache("phase2.json")
    kandydaci = [n for n in names if phase1.get(n, {}).get("exists") and n not in cache]
    print(f"  Faza 2 (opis+linki): {len(kandydaci)} do pobrania (w cache: {len(cache)})")
    done = 0
    for n in kandydaci:
        params = {
            "action": "parse", "format": "json", "prop": "text",
            "section": 0, "redirects": 1, "formatversion": 2, "page": n,
        }
        try:
            data = client.get(params)
            text = data.get("parse", {}).get("text", "")
            cache[n] = {"opis_html": wyczysc_akapit(text)}
        except Exception as e:
            cache[n] = {"opis_html": ""}
        done += 1
        if done % 25 == 0:
            save_cache("phase2.json", cache)
            print(f"    ...{done}/{len(kandydaci)}")
    save_cache("phase2.json", cache)
    return cache

def wzbogac(rows, client):
    names = [r["imie"] for r in rows]
    phase1 = faza1_istnienie(names, client)
    phase2 = faza2_opis(names, phase1, client)
    for r in rows:
        n = r["imie"]
        p1 = phase1.get(n, {})
        r["pochodzenie"] = wykryj_pochodzenie(p1.get("plain", "")) if p1.get("exists") else ""
        r["opis_html"]   = phase2.get(n, {}).get("opis_html", "")
    return rows

# ----------------------------------------------------------------- ZAPIS -----

def zapisz(rows, base):
    cols = ["imie", "wystapienia_pierwsze", "wystapienia_drugie", "pochodzenie", "opis_html"]
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    json.dump(rows, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False)

def zapisz_dane_js(meskie, zenskie):
    with open("dane.js", "w", encoding="utf-8") as f:
        f.write("// Wygenerowane przez zbuduj_dataset.py - dane dla strony.\n")
        f.write("window.DANE_MESKIE = ")
        json.dump(meskie, f, ensure_ascii=False)
        f.write(";\n window.DANE_ZENSKIE = ")
        json.dump(zenskie, f, ensure_ascii=False)
        f.write(";\n")

# ------------------------------------------------------------------- MAIN ----

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=LIMIT_NA_PLEC,
                    help="Wzbogac tylko N najpopularniejszych imion kazdej plci (szybki test).")
    args = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    print("[1/4] Pobieram liste zasobow z dane.gov.pl ...")
    zasoby = pobierz_zasoby()
    wybor = wybierz_najnowsze(zasoby)
    if len(wybor) < 4:
        sys.exit(f"Nie znaleziono wszystkich 4 plikow. Znaleziono: {list(wybor)}")
    pliki = {}
    for key, (date, url, title) in wybor.items():
        dest = os.path.join(RAW_DIR, key + ".xlsx")
        print(f"      {key}: {title} (stan {date})")
        sciagnij(url, dest)
        pliki[key] = dest

    print("[2/4] Buduje datasety ...")
    meskie  = zbuduj(pliki["m_pierwsze"], pliki["m_drugie"])
    zenskie = zbuduj(pliki["z_pierwsze"], pliki["z_drugie"])
    print(f"      meskie: {len(meskie)} imion, zenskie: {len(zenskie)} imion")

    if args.limit:
        print(f"      LIMIT: wzbogacam tylko {args.limit} najpopularniejszych kazdej plci")
        do_m, do_z = meskie[:args.limit], zenskie[:args.limit]
    else:
        do_m, do_z = meskie, zenskie

    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    ratelimiter = RateLimiter(RATE_LIMIT_REQ, RATE_LIMIT_WIN)
    client = WikiAPIClient(sess, ratelimiter)

    print("[3/4] Wzbogacam o Wikipedie (meskie) ...")
    wzbogac(do_m, client)
    print("[3/4] Wzbogacam o Wikipedie (zenskie) ...")
    wzbogac(do_z, client)
    # imiona poza limitem dostaja puste pola
    for r in meskie + zenskie:
        r.setdefault("pochodzenie", "")
        r.setdefault("opis_html", "")

    print("[4/4] Zapisuje pliki ...")
    zapisz(meskie, "dataset_meskie")
    zapisz(zenskie, "dataset_zenskie")
    zapisz_dane_js(meskie, zenskie)
    n_op = sum(1 for r in meskie + zenskie if r.get("opis_html"))
    print(f"GOTOWE. Imion z opisem z Wikipedii: {n_op}. Pliki: dataset_*.csv/.json oraz dane.js")
    print("Otworz index.html w przegladarce (dane.js musi byc w tym samym folderze).")

if __name__ == "__main__":
    main()
