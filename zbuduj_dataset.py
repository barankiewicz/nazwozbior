#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zbuduj_dataset.py
=================
Buduje dane dla "Nazwozbiór" — przeglądarki imion polskich.

Co robi:
  1. Pobiera z dane.gov.pl (dataset 1667) NAJNOWSZE listy imion z rejestru PESEL
  2. Skleja je w datasety (imie, wystapienia_pierwsze, wystapienia_drugie)
  3. Wzbogaca imiona o pochodzenie + opis z polskiej Wikipedii
  4. Zapisuje dataset_*.csv/.json oraz dane.js

Uruchomienie:
    pip install requests openpyxl
    python3 zbuduj_dataset.py
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

# ------------------------------------------------------------------- KONFIG ---

DATASET_ID     = 1667
LIMIT_NA_PLEC  = None
WIKI_LANG      = "pl"
RAW_DIR        = "raw_pesel"
CACHE_DIR      = ".cache_wiki"
USER_AGENT     = ("Nazwozbior/1.0 (https://github.com/barankiewicz; "
                  "barankiewicz@protonmail.ch)")
MAXLAG         = 5
RATE_LIMIT_REQ   = 100
RATE_LIMIT_WIN   = 60
MAX_RETRIES    = 5
BATCH_SIZE      = 20
API            = f"https://{WIKI_LANG}.wikipedia.org/w/api.php"

ORIGIN_MAP = [
    ("starogreck", "greckie"), ("grec", "greckie"),
    ("lacin", "lacinskie"), ("łaci", "lacinskie"),
    ("starogerm", "germanskie"), ("german", "germanskie"), ("germań", "germanskie"),
    ("starodolnoniem", "germanskie"), ("staronordyck", "skandynawskie"),
    ("skandyna", "skandynawskie"), ("nordyck", "skandynawskie"),
    ("slowia", "slowianskie"), ("słowia", "slowianskie"),
    ("staropol", "staropolskie"),
    ("hebr", "hebrajskie"), ("aramej", "aramejskie"), ("semick", "hebrajskie"), ("biblij", "hebrajskie"),
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
    ("iber", "iberyjskie"), ("etrur", "etruskie"), ("iber", "iberyjskie"),
    ("amer", "amerykanskie"), ("japo", "japonskie"), ("chin", "chinskie"),
    ("mongol", "mongolskie"), ("polinezyj", "polinezyjskie"),
    ("persk", "perskie"), ("hindi", "indyjskie"), ("urdu", "indyjskie"),
    ("staropers", "perskie"), ("prowans", "prowansalskie"),
    ("holend", "holenderskie"), ("niderland", "holenderskie"),
    ("burgund", "burgundzkie"), ("bizantyj", "bizantyjskie"),
    ("starobułgar", "slowianskie"), ("st.bułg", "slowianskie"),
    ("praslow", "slowianskie"), ("prasłow", "slowianskie"),
    ("palestyń", "palestynskie"), ("z hebr", "hebrajskie"),
]

# Wzorce do wykrywania pochodzenia z pierwszego zdania
ORIGIN_PATTERNS = [
    re.compile(r'pochodzeni[ae]\s+([a-ząćęłńóśźż]{3,})'),
    re.compile(r'wywodzi\s+si[ęe]\s+z\s+(j[ęe]zyka\s+)?([a-ząćęłńóśźż]{3,})'),
    re.compile(r'pochodzi\s+z\s+(j[ęe]zyka\s+)?([a-ząćęłńóśźż]{3,})'),
    re.compile(r'im[ięe][\s,][^.]+?\b([a-ząćęłńóśźż]*(?:greck|łaci|german|słowia|hebr|arab|celt|slowia|staropol|francus|angiel|włos|rosyj|ukrai|wegier|fińsk|pers|turec|indyj|egip|skandyn)[a-ząćęłńóśźż]*)\b'),
]



# ---------------------------------------------------- RATE LIMIT / API KLIENT

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
                    retry = int(r.headers.get("Retry-After", 30))
                    print(f"    429, czekam {retry}s")
                    time.sleep(retry)
                    continue
                if r.status_code in (502, 503, 504):
                    retry = int(r.headers.get("Retry-After", min(60, 2 ** attempt)))
                    print(f"    HTTP {r.status_code}, proba {attempt+1}/{self.max_retries} po {retry}s")
                    time.sleep(retry)
                    continue
                r.raise_for_status()
                time.sleep(0.15)
                return r.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt == self.max_retries - 1:
                    raise
                sleep = min(30, 2 ** attempt)
                print(f"    blad polaczenia: {e}, proba {attempt+1}/{self.max_retries} po {sleep}s")
                time.sleep(sleep)
        raise Exception(f"Przekroczono max prob ({self.max_retries}) dla: {params.get('page', params.get('titles', '?'))}")

# ---------------------------------------------------------------- POBIERANIE

def titlecase_pl(s):
    s = s.strip()
    out = []
    for t in re.split(r'([ \-])', s.lower()):
        out.append(t if t in (' ', '-') or t == '' else t[0].upper() + t[1:])
    return ''.join(out)

def pobierz_zasoby():
    url = f"https://api.dane.gov.pl/1.4/datasets/{DATASET_ID}/resources?lang=pl&page=1&per_page=100"
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    return r.json().get("data", [])

def wybierz_najnowsze(zasoby):
    wybor = {}
    for z in zasoby:
        a = z.get("attributes", {})
        title = (a.get("title") or "").lower()
        fmt = (a.get("format") or "").lower()
        url = a.get("file_url") or a.get("link")
        date = a.get("data_date") or ""
        if fmt != "xlsx" or not url:
            continue
        plec = "m" if ("męsk" in title or "mesk" in title) \
                else ("z" if ("żeńsk" in title or "zensk" in title) else None)
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
        rows.append({"imie": n, "wystapienia_pierwsze": first.get(n, 0),
                     "wystapienia_drugie": second.get(n, 0)})
    rows.sort(key=lambda r: -(r["wystapienia_pierwsze"] + r["wystapienia_drugie"]))
    return rows

# ------------------------------------------------------------ CACHE POMOCE

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
    json.dump(data, open(os.path.join(CACHE_DIR, name), "w", encoding="utf-8"),
              ensure_ascii=False)

# ----------------------------------------------------- POCHODZENIE Z TEKSTU

def wykryj_pochodzenie(plain, categories=None):
    """Wykrywa pochodzenie z tekstu intru + kategorii artykulu."""
    origin = ""
    if plain:
        for pat in ORIGIN_PATTERNS:
            m = pat.search(plain.lower())
            if m:
                token = m.group(m.lastindex)
                if token in ("języka", "język", "jezyka", "jezyk"):
                    continue
                for frag, label in ORIGIN_MAP:
                    if frag in token:
                        origin = label
                        break
                if origin:
                    break
    if not origin and categories:
        for cat in categories:
            c = cat.replace("Kategoria:", "").replace("|", "").strip()
            # "Imiona męskie pochodzenia hebrajskiego" -> wyciągnij "hebrajskiego"
            m = re.search(r'pochodzenia\s+([a-ząćęłńóśźż]+)', c.lower())
            if m:
                token = m.group(1)
                for frag, label in ORIGIN_MAP:
                    if frag in token:
                        origin = label
                        break
                if origin:
                    break
            for frag, label in ORIGIN_MAP:
                if frag in c.lower():
                    origin = label
                    break
            if origin:
                break
    return origin

# ----------------------------------------------------------- FAZA 1 — ISTNIENIE

def faza1_istnienie(names, client):
    """Wsadowo: sprawdza czy artykul istnieje + pobiera plaintext + kategorie.

    Jesli artykul okazuje sie strona ujednoznaczniajaca, probuje '(imię)'.
    """
    cache = load_cache("phase1.json")

    def _is_disambig(info):
        return any("ujednoznaczn" in c.lower() for c in info.get("cats", []))

    def _fetch(raw_batch):
        params = {
            "action": "query", "format": "json",
            "prop": "extracts|categories",
            "exintro": 1, "explaintext": 1,
            "exlimit": "max",
            "cllimit": "max", "clshow": "!hidden",
            "redirects": 1, "formatversion": 2,
            "titles": "|".join(raw_batch),
        }
        data = client.get(params)
        pages = data.get("query", {}).get("pages", [])
        ret = {}
        for pg in pages:
            title = pg.get("title", "")
            missing = pg.get("missing", False)
            extract = pg.get("extract", "") or ""
            cats = [c["title"] for c in pg.get("categories", [])]
            ret[title] = {"exists": (not missing), "plain": extract, "cats": cats}
        norm = {}
        for rd in data.get("query", {}).get("redirects", []):
            norm[rd["from"]] = rd["to"]
        for nm in data.get("query", {}).get("normalized", []):
            norm[nm["from"]] = nm["to"]
        return ret, norm

    todo = [n for n in names if n not in cache]
    print(f"  Faza 1 (istnienie/kategorie): {len(todo)} nowych z {len(names)} "
          f"(w cache: {len(cache)})")

    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        try:
            ret, norm = _fetch(batch)
        except Exception as e:
            print(f"    blad batch ({batch[0]}...{batch[-1]}): {e}")
            for n in batch:
                cache[n] = {"exists": False, "plain": "", "cats": []}
            continue

        disambig_names = []
        for n in batch:
            t = norm.get(n, n)
            info = ret.get(t) or ret.get(n) or {"exists": False, "plain": "", "cats": []}
            info["page_title"] = t
            cache[n] = info
            if info.get("exists") and _is_disambig(info):
                disambig_names.append(n)

        # retry disambiguated names with "(imię)" suffix
        if disambig_names:
            suffixed = [f"{n} (imi\u0119)" for n in disambig_names]
            try:
                ret2, norm2 = _fetch(suffixed)
            except Exception as e:
                print(f"    blad retry disambig: {e}")
                ret2, norm2 = {}, {}
            for n, s in zip(disambig_names, suffixed):
                t = norm2.get(s, s)
                info2 = ret2.get(t) or ret2.get(s) or {"exists": False, "plain": "", "cats": []}
                if info2.get("exists"):
                    info2["page_title"] = t
                    cache[n] = info2

        if (i // BATCH_SIZE) % 5 == 0:
            save_cache("phase1.json", cache)
            print(f"    ...{min(i+BATCH_SIZE, len(todo))}/{len(todo)}")
    save_cache("phase1.json", cache)

    # Oznacz disambig dla tych ktore nadal nia sa (nie mialy "(imię)" wariantu)
    for n in cache:
        if cache[n].get("exists") and _is_disambig(cache[n]):
            cache[n]["disambig"] = True
        else:
            cache[n]["disambig"] = False
    return cache

# ----------------------------------------------------------- FAZA 2 — OPIS HTML

RE_SUP   = re.compile(r'<sup\b[^>]*>.*?</sup>', re.S)
RE_STYLE = re.compile(r'<style\b[^>]*>.*?</style>', re.S)
RE_SPANO = re.compile(r'<span\b[^>]*>')
RE_SPANC = re.compile(r'</span>')

def wyczysc_akapit(html_text):
    if not html_text:
        return ""
    html_text = re.sub(r'<!--.*?-->', '', html_text, flags=re.S)
    html_text = RE_STYLE.sub('', html_text)
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
    s = RE_SUP.sub('', s)
    s = re.sub(r'<span\b[^>]*class="[^"]*mw-editsection[^"]*".*?</span>', '', s, flags=re.S)
    def fix_link(m):
        href = m.group(1)
        if href.startswith('/wiki/'):
            return f'<a href="https://{WIKI_LANG}.wikipedia.org{href}" target="_blank" rel="noopener noreferrer">'
        if href.startswith('http'):
            return f'<a href="{href}" target="_blank" rel="noopener noreferrer">'
        return '<a>'
    s = re.sub(r'<a\b[^>]*?href="([^"]*)"[^>]*>', fix_link, s)
    s = re.sub(r'<a>(.*?)</a>', r'\1', s, flags=re.S)
    s = RE_SPANO.sub('', s); s = RE_SPANC.sub('', s)
    s = re.sub(r'<(b|i|em|strong)\b[^>]*>', r'<\1>', s)
    s = re.sub(r'</?(?!a\b|b\b|i\b|em\b|strong\b)[a-zA-Z][^>]*>', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def faza2_opis(names, phase1, client):
    """Dla imion z artykulem: pobiera pierwszy akapit HTML."""
    cache = load_cache("phase2.json")
    kandydaci = [(n, phase1.get(n, {}).get("page_title", n))
                 for n in names if phase1.get(n, {}).get("exists") and n not in cache]
    print(f"  Faza 2 (opis HTML): {len(kandydaci)} do pobrania (w cache: {len(cache)})")
    done = 0
    for n, page_title in kandydaci:
        params = {
            "action": "parse", "format": "json", "prop": "text",
            "section": 0, "redirects": 1, "formatversion": 2, "page": page_title,
        }
        try:
            data = client.get(params)
            text = data.get("parse", {}).get("text", "")
            cache[n] = {"opis_html": wyczysc_akapit(text)}
        except Exception:
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
        if p1.get("exists") and not p1.get("disambig"):
            r["pochodzenie"] = wykryj_pochodzenie(p1.get("plain", ""),
                                                  p1.get("cats", []))
        else:
            r["pochodzenie"] = ""
        r["opis_html"] = phase2.get(n, {}).get("opis_html", "")
    return rows

# ------------------------------------------------------------------- ZAPIS

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
        f.write("// Wygenerowane przez zbuduj_dataset.py — dane dla strony.\n")
        f.write("window.DANE_MESKIE = ")
        json.dump(meskie, f, ensure_ascii=False)
        f.write(";\n window.DANE_ZENSKIE = ")
        json.dump(zenskie, f, ensure_ascii=False)
        f.write(";\n")

# ------------------------------------------------------------------- MAIN

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=LIMIT_NA_PLEC,
                    help="Wzbogac tylko N najpopularniejszych imion kazdej plci.")
    args = ap.parse_args()
    os.makedirs(RAW_DIR, exist_ok=True)

    print("[1/4] Pobieram liste zasobow z dane.gov.pl …")
    zasoby = pobierz_zasoby()
    wybor = wybierz_najnowsze(zasoby)
    if len(wybor) < 4:
        sys.exit(f"Nie znaleziono 4 plikow. Znaleziono: {list(wybor)}")
    pliki = {}
    for key, (date, url, title) in wybor.items():
        dest = os.path.join(RAW_DIR, key + ".xlsx")
        print(f"      {key}: {title} (stan {date})")
        sciagnij(url, dest)
        pliki[key] = dest

    print("[2/4] Buduje datasety …")
    meskie  = zbuduj(pliki["m_pierwsze"], pliki["m_drugie"])
    zenskie = zbuduj(pliki["z_pierwsze"], pliki["z_drugie"])
    print(f"      meskie: {len(meskie)} imion, zenskie: {len(zenskie)} imion")

    if args.limit:
        print(f"      LIMIT: tylko {args.limit} najpopularniejszych kazdej plci")
        do_m, do_z = meskie[:args.limit], zenskie[:args.limit]
    else:
        do_m, do_z = meskie, zenskie

    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    ratelimiter = RateLimiter(RATE_LIMIT_REQ, RATE_LIMIT_WIN)
    client = WikiAPIClient(sess, ratelimiter)

    print("[3/4] Wzbogacam o Wikipedie (meskie) …")
    wzbogac(do_m, client)
    print("[3/4] Wzbogacam o Wikipedie (zenskie) …")
    wzbogac(do_z, client)
    for r in meskie + zenskie:
        r.setdefault("pochodzenie", "")
        r.setdefault("opis_html", "")

    print("[4/4] Zapisuje pliki …")
    zapisz(meskie, "dataset_meskie")
    zapisz(zenskie, "dataset_zenskie")
    zapisz_dane_js(meskie, zenskie)
    n_op = sum(1 for r in meskie + zenskie if r.get("opis_html"))
    n_po = sum(1 for r in meskie + zenskie if r.get("pochodzenie"))
    print(f"GOTOWE. Imion z opisem: {n_op}, z pochodzeniem: {n_po}.")
    print("Pliki: dataset_*.csv/.json oraz dane.js")

if __name__ == "__main__":
    main()
