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
API_PL         = "https://pl.wikipedia.org/w/api.php"
API_EN         = "https://en.wikipedia.org/w/api.php"
API_WIKIDATA   = "https://www.wikidata.org/w/api.php"

WD_RATE_LIMIT_REQ = 50
WD_RATE_LIMIT_WIN = 60
EN_RATE_LIMIT_REQ = 100
EN_RATE_LIMIT_WIN = 60

# Mapowanie angielskich kategorii Wikipedii → nasze etykiety pochodzenia
EN_CATEGORY_ORIGINS = [
    ("polish", "slowianskie"),
    ("ukrainian", "ukrainskie"), ("belarusian", "slowianskie"),
    ("russian", "rosyjskie"),
    ("czech", "slowianskie"), ("slovak", "slowianskie"),
    ("croatian", "slowianskie"), ("serbian", "slowianskie"),
    ("bulgarian", "slowianskie"), ("slovene", "slowianskie"),
    ("bosnian", "slowianskie"), ("macedonian", "slowianskie"),
    ("montenegrin", "slowianskie"),
    ("slavic", "slowianskie"), ("slav", "slowianskie"),
    ("lithuanian", "litewskie"), ("latvian", "litewskie"),
    ("italian", "wloskie"), ("romance", "romanskie"), ("romanian", "romanskie"),
    ("french", "francuskie"), ("provençal", "prowansalskie"),
    ("spanish", "hiszpanskie"), ("portuguese", "hiszpanskie"), ("portugal", "hiszpanskie"),
    ("catalan", "hiszpanskie"), ("galician", "hiszpanskie"),
    ("german", "germanskie"), ("germanic", "germanskie"),
    ("dutch", "holenderskie"), ("netherlands", "holenderskie"),
    ("swiss", "germanskie"), ("austrian", "germanskie"),
    ("old high german", "germanskie"),
    ("greek", "greckie"),
    ("latin", "lacinskie"),
    ("hebrew", "hebrajskie"), ("biblical", "hebrajskie"), ("israeli", "hebrajskie"),
    ("arabic", "arabskie"), ("muslim", "arabskie"), ("islamic", "arabskie"),
    ("turkish", "tureckie"), ("turkic", "tureckie"), ("azerbaijani", "tureckie"),
    ("celtic", "celtyckie"), ("gaelic", "celtyckie"), ("irish", "celtyckie"),
    ("scottish", "celtyckie"), ("welsh", "celtyckie"), ("breton", "celtyckie"),
    ("cornish", "celtyckie"), ("manx", "celtyckie"),
    ("norse", "skandynawskie"), ("scandinavian", "skandynawskie"),
    ("swedish", "skandynawskie"), ("norwegian", "skandynawskie"),
    ("danish", "skandynawskie"), ("icelandic", "skandynawskie"), ("faroese", "skandynawskie"),
    ("old norse", "skandynawskie"),
    ("finnish", "finskie"), ("estonian", "finskie"),
    ("hungarian", "wegierskie"),
    ("persian", "perskie"), ("iranian", "perskie"), ("old persian", "perskie"),
    ("indian", "indyjskie"), ("hindi", "indyjskie"), ("sanskrit", "sanskryckie"),
    ("tamil", "indyjskie"), ("bengali", "indyjskie"), ("punjabi", "indyjskie"),
    ("japanese", "japonskie"), ("chinese", "chinskie"), ("korean", "chinskie"),
    ("assyrian", "arabskie"),
    ("egyptian", "egipskie"), ("phoenician", "fenickie"), ("hethit", "hebrajskie"),
    ("english", "angielskie"), ("anglo-saxon", "anglosaskie"), ("anglo-s", "anglosaskie"),
    ("old english", "anglosaskie"),
    ("american", "amerykanskie"),
    ("african", "arabskie"), ("swahili", "arabskie"),
    ("mongolian", "mongolskie"), ("basque", "baskijskie"),
    ("old church slavonic", "slowianskie"),
    ("old slavonic", "slowianskie"),
]

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
    ("indyj", "indyjskie"), ("indii", "indyjskie"), ("turec", "tureckie"), ("baskij", "baskijskie"),
    ("anglosas", "anglosaskie"), ("angiel", "angielskie"),
    ("francus", "francuskie"), ("hiszpa", "hiszpanskie"),
    ("włos", "wloskie"), ("wlos", "wloskie"), ("roman", "romanskie"),
    ("ros", "rosyjskie"), ("rusk", "ruskie"), ("ukrai", "ukrainskie"),
    ("wegier", "wegierskie"), ("węgier", "wegierskie"),
    ("fin", "finskie"), ("etiop", "etiopskie"), ("fenick", "fenickie"),
    ("akadyj", "akadyjskie"), ("sumeryj", "sumeryjskie"), ("egipsk", "egipskie"),
    ("iber", "iberyjskie"), ("etrur", "etruskie"),
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
    def __init__(self, session, rate_limiter, max_retries=MAX_RETRIES,
                 base_url=API_PL):
        self.session = session
        self.ratelimit = rate_limiter
        self.max_retries = max_retries
        self.base_url = base_url

    def get(self, params, timeout=60):
        self.ratelimit.wait_if_needed()
        if "maxlag" in params:
            pass  # jesli juz ustawione, zostaw
        else:
            params["maxlag"] = MAXLAG
        for attempt in range(self.max_retries):
            try:
                r = self.session.get(self.base_url, params=params, timeout=timeout)
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

def is_name_article(categories):
    """Sprawdza czy kategorie wskazuja na artykul o imieniu (nie o bandzie/filmie/etc)."""
    if not categories:
        return None
    name_hints = 0
    other_hints = 0
    other_keywords = [
        "zespół", "zespoły", "album", "albumy", "utwór", "utwory",
        "film", "filmy", "serial", "seriale", "piosenka", "piosenki",
        "singel", "single", "gra", "gry", "książka", "książki",
        "powieść", "powieści", "muzyk", "muzyka",
        "miasto", "miasta", "wieś", "wsi", "gmina", "państwo", "państwa",
        "wyspa", "wyspy", "rzeka", "rzeki", "jezioro", "jeziora",
        "roślina", "rośliny", "zwierzę", "zwierzęta", "organizm",
        "przedsiębiorstwo", "linia lotnicza", "statek", "statki",
        "sportowiec", "piłkarz", "aktor", "aktorka", "polityk",
        "wojskowy", "duchowny", "naukowiec", "reżyser",
        "dostawca", "konstruktor", "producent",
    ]
    for c in categories:
        cl = c.lower()
        if "ujednoznaczn" in cl:
            return False
        if any(w in cl for w in ["imion", "imię", "imienia", "imieniem", "imieniu"]):
            name_hints += 1
        elif any(w in cl for w in other_keywords):
            other_hints += 1
    if name_hints > 0:
        return True
    if other_hints > 0:
        return False
    return None

EN_NAME_CAT_RE = re.compile(r'(masculine|feminine|unisex)\s+given\s+name', re.I)

def is_name_article_en(categories):
    """Sprawdza po EN kategoriach czy artykul dotyczy imienia."""
    if not categories:
        return False
    for c in categories:
        if EN_NAME_CAT_RE.search(c):
            return True
    return False

def origin_from_en_categories(categories):
    """Wykrywa pochodzenie z angielskich kategorii Wikipedii."""
    if not categories:
        return ""
    for c in categories:
        cl = c.lower().replace("category:", "")
        for keyword, origin in EN_CATEGORY_ORIGINS:
            if keyword in cl:
                return origin
    return ""

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

# -------------------------------------------------------- WIKIDANE

WD_SEARCH_CACHE = {}

def search_wikidata(name, client_wd):
    """Szuka encji w Wikidanych po etykiecie."""
    if name in WD_SEARCH_CACHE:
        return WD_SEARCH_CACHE[name]
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "pl",
        "limit": 5,
        "format": "json",
    }
    try:
        data = client_wd.get(params, timeout=30)
    except Exception:
        WD_SEARCH_CACHE[name] = []
        return []
    results = []
    for ent in data.get("search", []):
        qid = ent.get("id", "")
        label = ent.get("label", "")
        desc = ent.get("description", "")
        match_score = 0
        # prefer exact match
        if label.lower() == name.lower():
            match_score = 2
        elif label.lower() in name.lower() or name.lower() in label.lower():
            match_score = 1
        # prefer 'given name' or 'name' description
        dlow = desc.lower()
        if "given name" in dlow or "imię" in dlow or "surname" in dlow:
            match_score += 1
        results.append({"id": qid, "label": label, "desc": desc, "score": match_score})
    results.sort(key=lambda x: -x["score"])
    WD_SEARCH_CACHE[name] = results
    return results

# Mapowanie wartości P495 (kraj) i P407 (język) z Wikidanych na nasze etykiety
# Używamy polskich etykiet z Wikidanych, dopasowujemy przez ORIGIN_MAP
def origin_from_wikidata_claims(claims, value_labels=None):
    """Wyciaga pochodzenie z claimow Wikidanych.

    value_labels: dict {qid: {"pl": label, "en": label}} dla wartosci claimow
    """
    if value_labels is None:
        value_labels = {}
    for prop_id in ("P495", "P407", "P1416"):
        prop_claims = claims.get(prop_id, [])
        for claim in prop_claims:
            mainsnak = claim.get("mainsnak", {})
            if mainsnak.get("snaktype") != "value":
                continue
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            if isinstance(value, dict):
                qid = value.get("id", "")
                # Najpierw sprawdzamy pobrane etykiety
                lbls = value_labels.get(qid, {})
                for lang in ("pl", "en"):
                    label = (lbls.get(lang, "") or "").lower()
                    if label:
                        for frag, origin in ORIGIN_MAP:
                            if frag in label:
                                return origin
                # Jesli nie ma etykiet, sprawdz label z datavalue
                label = (value.get("label", "") or value.get("id", "") or "").lower()
                if label and label.startswith("q"):
                    continue
                if label:
                    for frag, origin in ORIGIN_MAP:
                        if frag in label:
                            return origin
    return ""

def get_wikidata_entities(qids, client_wd):
    """Pobiera encje Wikidanych + polskie etykiety dla listy QIDow."""
    if not qids:
        return {}
    params = {
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "claims|sitelinks|labels",
        "languages": "pl|en",
        "format": "json",
    }
    try:
        data = client_wd.get(params, timeout=60)
    except Exception:
        return {}
    return data.get("entities", {})

# -------------------------------------------------------- EN WIKIPEDIA

def check_en_wikipedia(names, client_en):
    """Sprawdza angielska Wikipedie: kategorie + czy to imie.
    Zwraca dict {name: {"exists": bool, "is_name": bool, "origin": str, "cats": [str]}}
    """
    cache = load_cache("phase_en.json")
    todo = [n for n in names if n not in cache]
    print(f"  EN Wikipedia: {len(todo)} nowych z {len(names)} (w cache: {len(cache)})")
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        params = {
            "action": "query", "format": "json",
            "prop": "categories",
            "cllimit": "max", "clshow": "!hidden",
            "redirects": 1, "formatversion": 2,
            "titles": "|".join(batch),
        }
        try:
            data = client_en.get(params)
        except Exception as e:
            print(f"    blad EN batch: {e}")
            for n in batch:
                cache[n] = {"exists": False, "is_name": False, "origin": "", "cats": []}
            continue
        pages = data.get("query", {}).get("pages", [])
        norm = {}
        for rd in data.get("query", {}).get("redirects", []):
            norm[rd["from"]] = rd["to"]
        for nm in data.get("query", {}).get("normalized", []):
            norm[nm["from"]] = nm["to"]
        pg_by_title = {}
        for pg in pages:
            pg_by_title[pg.get("title", "")] = pg
        for n in batch:
            t = norm.get(n, n)
            pg = pg_by_title.get(t) or pg_by_title.get(n) or {}
            missing = pg.get("missing", False)
            cats = [c["title"] for c in pg.get("categories", [])]
            is_name = is_name_article_en(cats)
            origin = origin_from_en_categories(cats) if is_name else ""
            cache[n] = {"exists": (not missing), "is_name": is_name, "origin": origin, "cats": cats}
        if (i // BATCH_SIZE) % 5 == 0:
            save_cache("phase_en.json", cache)
            print(f"    ...{min(i+BATCH_SIZE, len(todo))}/{len(todo)}")
    save_cache("phase_en.json", cache)
    return cache

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
    save_cache("phase1.json", cache)
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

def wczytaj_istniejace_dane():
    """Wczytuje istniejace datasety JSON jesli istnieja."""
    def _load(path):
        if os.path.exists(path):
            try:
                return json.load(open(path, encoding="utf-8"))
            except Exception:
                return None
        return None
    m = _load("dataset_meskie.json")
    z = _load("dataset_zenskie.json")
    return m, z

def log_stats(rows, phase_label, counts_before=None):
    """Loguje statystyki kategoryzacji: po zrodle + nieskategoryzowane."""
    total = len(rows)
    cat = sum(1 for r in rows if r.get("pochodzenie"))
    if counts_before is not None:
        new = cat - counts_before.get("cat", 0)
    else:
        new = 0
    # podzial wg zrodla
    from_pl = sum(1 for r in rows if r.get("_zrodlo") == "PL")
    from_en = sum(1 for r in rows if r.get("_zrodlo") == "EN")
    from_wd = sum(1 for r in rows if r.get("_zrodlo") == "WD")
    uncat = total - cat
    if new:
        print(f"  [{phase_label}] +{new} skat.  "
              f"PL={from_pl} EN={from_en} WD={from_wd}  "
              f"brak={uncat}/{total} ({uncat/total*100:.1f}%)")
    else:
        print(f"  [{phase_label}]  "
              f"PL={from_pl} EN={from_en} WD={from_wd}  "
              f"brak={uncat}/{total} ({uncat/total*100:.1f}%)")

def wzbogac(rows, client_pl, client_en=None, client_wd=None, incremental=False):
    """Wzbogaca imiona o pochodzenie i opis z wielu zrodel.

    Kolejnosc:
      1. Polska Wikipedia (tekst + kategorie)
      2. Jesli brak pochodzenia: angielska Wikipedia (kategorie)
      3. Jesli nadal brak: Wikidane (strukturalne dane)
    """
    if incremental:
        do_process = [r for r in rows if not r.get("pochodzenie") and not r.get("opis_html")]
        kept = [r for r in rows if r.get("pochodzenie") or r.get("opis_html")]
        print(f"  Tryb incremental: {len(do_process)} do przetworzenia, "
              f"{len(kept)} juz gotowych")
        rows = do_process
        if not rows:
            return kept

    names = [r["imie"] for r in rows]
    phase1 = faza1_istnienie(names, client_pl) if client_pl else {}
    phase2 = faza2_opis(names, phase1, client_pl) if client_pl else {}

    # PL Wikipedia
    before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
    for r in rows:
        n = r["imie"]
        p1 = phase1.get(n, {})
        is_name = is_name_article(p1.get("cats", []))
        is_disambig = (
            p1.get("disambig", False) or
            any("ujednoznaczn" in c.lower() for c in p1.get("cats", []))
        )
        if p1.get("exists") and not is_disambig and is_name is not False:
            o = wykryj_pochodzenie(p1.get("plain", ""), p1.get("cats", []))
            if o:
                r["pochodzenie"] = o
                r["_zrodlo"] = "PL"
                print(f"    PL: {n} -> {o}")
        r["opis_html"] = phase2.get(n, {}).get("opis_html", "")
    log_stats(rows, "PL", before)

    # EN Wikipedia
    if client_en:
        need_en = [r for r in rows if not r.get("pochodzenie")]
        if need_en:
            before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
            print(f"  EN Wikipedia (fallback): {len(need_en)} imion bez pochodzenia")
            en_cache = check_en_wikipedia([r["imie"] for r in need_en], client_en)
            for r in need_en:
                en = en_cache.get(r["imie"], {})
                if en.get("is_name") and en.get("origin"):
                    r["pochodzenie"] = en["origin"]
                    r["_zrodlo"] = "EN"
                    print(f"    EN: {r['imie']} -> {r['pochodzenie']}")
            log_stats(rows, "EN", before)

    # Wikidane
    if client_wd:
        need_wd = [r for r in rows if not r.get("pochodzenie")]
        if need_wd:
            before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
            print(f"  Wikidane (fallback): {len(need_wd)} imion bez pochodzenia")
            wd_results = {}
            found_qids = []
            name_to_qid = {}
            for r in need_wd:
                results = search_wikidata(r["imie"], client_wd)
                if results and results[0].get("score", 0) >= 2:
                    qid = results[0]["id"]
                    found_qids.append(qid)
                    name_to_qid[r["imie"]] = qid
            for i in range(0, len(found_qids), 50):
                batch = found_qids[i:i+50]
                entities = get_wikidata_entities(batch, client_wd)
                for qid, ent in entities.items():
                    wd_results[qid] = ent
            value_qids = set()
            for qid, ent in wd_results.items():
                claims = ent.get("claims", {})
                for prop in ("P495", "P407", "P1416"):
                    for claim in claims.get(prop, []):
                        ms = claim.get("mainsnak", {})
                        if ms.get("snaktype") == "value":
                            val = ms.get("datavalue", {}).get("value", {})
                            if isinstance(val, dict) and val.get("id", "").startswith("Q"):
                                value_qids.add(val["id"])
            value_labels = {}
            vq_list = list(value_qids)
            for i in range(0, len(vq_list), 50):
                batch = vq_list[i:i+50]
                entities = get_wikidata_entities(batch, client_wd)
                for qid, ent in entities.items():
                    lbls = ent.get("labels", {})
                    value_labels[qid] = {
                        "pl": (lbls.get("pl", {}) or {}).get("value", ""),
                        "en": (lbls.get("en", {}) or {}).get("value", ""),
                    }
            for r in need_wd:
                qid = name_to_qid.get(r["imie"])
                if qid and qid in wd_results:
                    claims = wd_results[qid].get("claims", {})
                    origin = origin_from_wikidata_claims(claims, value_labels)
                    if origin:
                        r["pochodzenie"] = origin
                        r["_zrodlo"] = "WD"
                        print(f"    WD: {r['imie']} -> {r['pochodzenie']}")
            log_stats(rows, "WD", before)

    if incremental:
        rows = kept + rows
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
    ap = argparse.ArgumentParser(
        description="Buduje i wzbogaca dataset imion polskich z PESEL + Wikipedii")
    ap.add_argument("--limit", type=int, default=LIMIT_NA_PLEC,
                    help="Wzbogac tylko N najpopularniejszych imion kazdej plci.")
    ap.add_argument("--incremental", "-i", action="store_true",
                    help="Tryb przyrostowy: wczytaj istniejace dane, "
                         "przetworz tylko imiona bez pochodzenia/opisu.")
    ap.add_argument("--shutdown", action="store_true",
                    help="Wylacz komputer po zakonczeniu.")
    ap.add_argument("--skip-pl", action="store_true",
                    help="Pomin polska Wikipedie (uzyj jesli cache jest gotowy).")
    ap.add_argument("--skip-en", action="store_true",
                    help="Pomin angielska Wikipedie.")
    ap.add_argument("--skip-wd", action="store_true",
                    help="Pomin Wikidane.")
    args = ap.parse_args()
    os.makedirs(RAW_DIR, exist_ok=True)

    if args.incremental:
        print("[0/4] Tryb przyrostowy - laduje istniejace dane …")
        m_istniejace, z_istniejace = wczytaj_istniejace_dane()
        if m_istniejace is not None and z_istniejace is not None:
            print(f"      Wczytano: meskie {len(m_istniejace)}, "
                  f"zenskie {len(z_istniejace)}")
            # Zbuduj tylko nowe dane z PESEL (ale PESEL moze miec nowsze dane)
            # W trybie incremental lączymy: najpierw wczytujemy PESEL,
            # potem mergujemy z istniejacymi danymi
        else:
            print("      Brak istniejacych danych, przechodze do normalnego trybu.")

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

    # W trybie incremental: merge PESEL z istniejacymi danymi
    if args.incremental and m_istniejace is not None and z_istniejace is not None:
        def merge(new_rows, old_rows):
            old_by_name = {r["imie"]: r for r in old_rows}
            for r in new_rows:
                old = old_by_name.get(r["imie"])
                if old:
                    r["pochodzenie"] = old.get("pochodzenie", "")
                    r["opis_html"] = old.get("opis_html", "")
            return new_rows
        meskie = merge(meskie, m_istniejace)
        zenskie = merge(zenskie, z_istniejace)
        n_zrodlo = sum(1 for r in meskie + zenskie
                       if r.get("pochodzenie") or r.get("opis_html"))
        print(f"      Z istniejacych danych: {n_zrodlo} imion ma pochodzenie/opis")

    if args.limit:
        print(f"      LIMIT: tylko {args.limit} najpopularniejszych kazdej plci")
        do_m, do_z = meskie[:args.limit], zenskie[:args.limit]
    else:
        do_m, do_z = meskie, zenskie

    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    ratelimiter_pl = RateLimiter(RATE_LIMIT_REQ, RATE_LIMIT_WIN)
    client_pl = WikiAPIClient(sess, ratelimiter_pl)

    client_en = None
    if not args.skip_en:
        ratelimiter_en = RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN)
        client_en = WikiAPIClient(sess, ratelimiter_en, base_url=API_EN)

    client_wd = None
    if not args.skip_wd:
        ratelimiter_wd = RateLimiter(WD_RATE_LIMIT_REQ, WD_RATE_LIMIT_WIN)
        client_wd = WikiAPIClient(sess, ratelimiter_wd, base_url=API_WIKIDATA)

    needs_en = not args.skip_en
    needs_wd = not args.skip_wd

    if not args.skip_pl:
        print("[3/4] Wzbogacam (meskie) …")
        wzbogac(do_m, client_pl, client_en, client_wd,
                incremental=args.incremental)
        print("[3/4] Wzbogacam (zenskie) …")
        wzbogac(do_z, client_pl, client_en, client_wd,
                incremental=args.incremental)
    else:
        print("[3/4] Pomijam PL Wikipedie (--skip-pl) …")
        if needs_en or needs_wd:
            all_rows = do_m + do_z
            need = [r for r in all_rows if not r.get("pochodzenie")]
            if need and needs_en:
                before = {"cat": sum(1 for r in all_rows if r.get("pochodzenie"))}
                print(f"  EN Wikipedia: {len(need)} imion …")
                en_cache = check_en_wikipedia([r["imie"] for r in need], client_en)
                for r in need:
                    en = en_cache.get(r["imie"], {})
                    if en.get("is_name") and en.get("origin"):
                        r["pochodzenie"] = en["origin"]
                        r["_zrodlo"] = "EN"
                        print(f"    EN: {r['imie']} -> {r['pochodzenie']}")
                log_stats(all_rows, "EN", before)
            need = [r for r in all_rows if not r.get("pochodzenie")]
            if need and needs_wd:
                before = {"cat": sum(1 for r in all_rows if r.get("pochodzenie"))}
                print(f"  Wikidane: {len(need)} imion …")
                wd_results = {}
                found_qids = []
                name_to_qid = {}
                for r in need:
                    results = search_wikidata(r["imie"], client_wd)
                    if results and results[0].get("score", 0) >= 2:
                        qid = results[0]["id"]
                        found_qids.append(qid)
                        name_to_qid[r["imie"]] = qid
                for i in range(0, len(found_qids), 50):
                    batch = found_qids[i:i+50]
                    entities = get_wikidata_entities(batch, client_wd)
                    for qid, ent in entities.items():
                        wd_results[qid] = ent
                value_qids = set()
                for qid, ent in wd_results.items():
                    claims = ent.get("claims", {})
                    for prop in ("P495", "P407", "P1416"):
                        for claim in claims.get(prop, []):
                            ms = claim.get("mainsnak", {})
                            if ms.get("snaktype") == "value":
                                val = ms.get("datavalue", {}).get("value", {})
                                if isinstance(val, dict) and val.get("id", "").startswith("Q"):
                                    value_qids.add(val["id"])
                value_labels = {}
                vq_list = list(value_qids)
                for i in range(0, len(vq_list), 50):
                    batch = vq_list[i:i+50]
                    entities = get_wikidata_entities(batch, client_wd)
                    for qid, ent in entities.items():
                        lbls = ent.get("labels", {})
                        value_labels[qid] = {
                            "pl": (lbls.get("pl", {}) or {}).get("value", ""),
                            "en": (lbls.get("en", {}) or {}).get("value", ""),
                        }
                for r in need:
                    qid = name_to_qid.get(r["imie"])
                    if qid and qid in wd_results:
                        claims = wd_results[qid].get("claims", {})
                        origin = origin_from_wikidata_claims(claims, value_labels)
                        if origin:
                            r["pochodzenie"] = origin
                            r["_zrodlo"] = "WD"
                            print(f"    WD: {r['imie']} -> {r['pochodzenie']}")
                log_stats(all_rows, "WD", before)

    print("\n  Podsumowanie kategoryzacji:")
    log_stats(meskie, "MĘSKIE")
    log_stats(zenskie, "ŻEŃSKIE")
    all_rows = meskie + zenskie
    log_stats(all_rows, "ŁĄCZNIE")

    for r in meskie + zenskie:
        r.setdefault("pochodzenie", "")
        r.setdefault("opis_html", "")
        r.pop("_zrodlo", None)

    print("[4/4] Zapisuje pliki …")
    zapisz(meskie, "dataset_meskie")
    zapisz(zenskie, "dataset_zenskie")
    zapisz_dane_js(meskie, zenskie)
    n_op = sum(1 for r in meskie + zenskie if r.get("opis_html"))
    n_po = sum(1 for r in meskie + zenskie if r.get("pochodzenie"))
    print(f"GOTOWE. Imion z opisem: {n_op}, z pochodzeniem: {n_po}.")
    print("Pliki: dataset_*.csv/.json oraz dane.js")
    if args.shutdown:
        print("WYŁĄCZAM…")
        os.system("shutdown -h now")

if __name__ == "__main__":
    main()
