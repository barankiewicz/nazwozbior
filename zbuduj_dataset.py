#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zbuduj_dataset.py
=================
Buduje dane dla "Nazwozbiór" — przeglądarki imion polskich.

Co robi:
  1. Pobiera z dane.gov.pl (dataset 1667) NAJNOWSZE listy imion z rejestru PESEL
  2. Skleja je w datasety (imie, wystapienia_pierwsze, wystapienia_drugie)
  3. Wzbogaca imiona o pochodzenie + opis, źródła w kolejności:
       PL Wikipedia (intro + kategorie) -> Wikidane (hurtowy dump SPARQL,
       dopasowanie lokalne) -> EN Wikipedia (kategorie + intro)
       -> dziedziczenie pochodzenia ("zdrobnienie imienia X" bierze od X)
  4. Pobiera imiona niebinarne z zaimki.pl (API) -> dataset_niebinarne.json
  5. Zapisuje dataset_*.csv/.json oraz dane.js

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

# --- Configuration ---

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
WD_SPARQL      = "https://query.wikidata.org/sparql"
ZAIMKI_API     = "https://zaimki.pl/api/names"

EN_RATE_LIMIT_REQ = 100
EN_RATE_LIMIT_WIN = 60

# Klasy Wikidanych: imię, imię męskie, imię żeńskie, imię unisex
WD_NAME_CLASSES = ["Q202444", "Q12308941", "Q11879590", "Q3409032"]
# WDQS nie udźwignie całego dumpu w jednym zapytaniu (timeout 60 s),
# więc tniemy każdą klasę na 16 shardów po pierwszym znaku MD5(QID).
WD_SHARDS = "0123456789abcdef"

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
    ("japanese", "japonskie"), ("chinese", "chinskie"), ("korean", "koreanskie"),
    ("hawaiian", "hawajskie"), ("armenian", "ormianskie"), ("georgian", "gruzinskie"),
    ("yiddish", "hebrajskie"), ("polish-language", "slowianskie"),
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
    ("polsk", "slowianskie"), ("czesk", "slowianskie"),
    ("słowac", "slowianskie"), ("slowac", "slowianskie"),
    ("chorwac", "slowianskie"), ("serbsk", "slowianskie"),
    ("bułgar", "slowianskie"), ("bulgar", "slowianskie"),
    ("słoweń", "slowianskie"), ("slowen", "slowianskie"),
    ("macedoń", "slowianskie"), ("macedon", "slowianskie"),
    ("białorus", "slowianskie"), ("bialorus", "slowianskie"),
    ("niemiec", "germanskie"),
    ("szwedz", "skandynawskie"), ("norwes", "skandynawskie"),
    ("duńsk", "skandynawskie"), ("dunsk", "skandynawskie"),
    ("island", "skandynawskie"), ("nordyj", "skandynawskie"),
    ("portugal", "hiszpanskie"), ("katalo", "hiszpanskie"),
    ("łotew", "litewskie"), ("lotew", "litewskie"),
    ("estoń", "finskie"), ("eston", "finskie"),
    ("koreań", "koreanskie"), ("korean", "koreanskie"),
    ("hawaj", "hawajskie"),
    ("walij", "celtyckie"), ("irlandz", "celtyckie"), ("szkock", "celtyckie"),
    ("gruziń", "gruzinskie"), ("gruzin", "gruzinskie"),
    ("ormiań", "ormianskie"), ("ormian", "ormianskie"),
    ("armeń", "ormianskie"), ("armen", "ormianskie"),
    ("jidysz", "hebrajskie"),
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
    ("palestyń", "palestynskie"), ("z hebr", "hebrajskie"),
]

ORIGIN_PATTERNS = [
    re.compile(r'pochodzeni[ae]\s+([a-ząćęłńóśźż]{3,})'),
    re.compile(r'wywodzi\s+si[ęe]\s+z\s+(j[ęe]zyka\s+)?([a-ząćęłńóśźż]{3,})'),
    re.compile(r'pochodzi\s+z\s+(j[ęe]zyka\s+)?([a-ząćęłńóśźż]{3,})'),
    re.compile(r'\bz\s+j[ęe]zyka\s+([a-ząćęłńóśźż]{3,})'),
    re.compile(r'\b(?:od|z)\s+((?:staro)?(?:greckiego|łacińskiego|hebrajskiego|germańskiego|'
               r'aramejskiego|celtyckiego|arabskiego|perskiego|tureckiego|słowiańskiego|'
               r'skandynawskiego|sanskrytu|jidysz))\b'),
    re.compile(r'\b([a-ząćęłńóśźż]{4,}(?:skie|ckie))\s+imi[ęe]\b'),
    re.compile(r'\bimi[ęe]\s+([a-ząćęłńóśźż]{4,}(?:skie|ckie))\b'),
    re.compile(r'\bod\s+(?:słowa\s+)?([a-ząćęłńóśźż]{5,}(?:skiego|ckiego))\b'),
]

# "Ola - zdrobnienie imienia Aleksandra" -> relacja do imienia bazowego
# (dziedziczenie pochodzenia + klikalne powiązania na stronie)
RE_BASE_REL = re.compile(
    r'(?:(żeńsk\w+|męsk\w+|skrócon\w+|zdrobniał\w+|spolszczon\w+)\s+)?'
    r'(zdrobnieni\w+|spieszczeni\w+|form\w+|wariant\w*|odmian\w+|odpowiednik\w*|wersj\w+)'
    r'\s+(?:od\s+)?(?:imienia|imion)\s+([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)')
RE_BASE_OD = re.compile(
    r'(?:pochodz\w+|wywodz\w+\s+si[ęe])\s+od\s+imienia\s+([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)')

# (rdzeń, lemat, rodzaj gramatyczny lematu)
RELACJA_LABELS = [
    ("zdrobnieni", "zdrobnienie", "n"), ("spieszczeni", "spieszczenie", "n"),
    ("wariant", "wariant", "m"), ("odmian", "odmiana", "f"),
    ("odpowiednik", "odpowiednik", "m"), ("wersj", "wersja", "f"),
    ("form", "forma", "f"),
]
RELACJA_PREFIXES = {
    "żeńsk":     {"f": "żeńska", "m": "żeński", "n": "żeńskie"},
    "męsk":      {"f": "męska", "m": "męski", "n": "męskie"},
    "skrócon":   {"f": "skrócona", "m": "skrócony", "n": "skrócone"},
    "zdrobniał": {"f": "zdrobniała", "m": "zdrobniały", "n": "zdrobniałe"},
    "spolszczon": {"f": "spolszczona", "m": "spolszczony", "n": "spolszczone"},
}


def extract_base_relations(plain):
    """[(relacja, imię bazowe), ...] z intro PL Wikipedii."""
    if not plain:
        return []
    out, seen = [], set()
    for m in RE_BASE_REL.finditer(plain):
        prefix = (m.group(1) or "").lower()
        stem = m.group(2).lower()
        name = m.group(3).strip()
        label, gender = next(((lbl, g) for st, lbl, g in RELACJA_LABELS
                              if stem.startswith(st)), ("forma", "f"))
        for st, forms in RELACJA_PREFIXES.items():
            if prefix.startswith(st):
                label = f"{forms[gender]} {label}"
                break
        if name.casefold() not in seen:
            seen.add(name.casefold())
            out.append((label, name))
    for m in RE_BASE_OD.finditer(plain):
        name = m.group(1).strip()
        if name.casefold() not in seen:
            seen.add(name.casefold())
            out.append(("pochodzi od", name))
    return out

# Wzorce na intro z EN Wikipedii, tokeny mapowane przez EN_CATEGORY_ORIGINS
EN_TEXT_PATTERNS = [
    re.compile(r'of\s+((?:[a-z]+\s){0,2}?[a-z]+)\s+origin', re.I),
    re.compile(r'\bis\s+an?\s+([a-z]+(?:\s[a-z]+)?)\s+(?:masculine|feminine|male|female|unisex)?\s*'
               r'(?:given\s+name|first\s+name|form\b)', re.I),
    re.compile(r'\b(?:derive[ds]?|derived|originat\w+|coming|comes)\s+from\s+(?:the\s+)?'
               r'((?:old|ancient|middle)?\s?[a-z]+)\b', re.I),
]

# --- Rate Limiter & API Client ---

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
                 base_url=API_PL, maxlag=None):
        self.session = session
        self.ratelimit = rate_limiter
        self.max_retries = max_retries
        self.base_url = base_url
        self.maxlag = maxlag

    def get(self, params, timeout=60):
        self.ratelimit.wait_if_needed()
        if self.maxlag is not None and "maxlag" not in params:
            params["maxlag"] = self.maxlag
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
                data = r.json()
                if isinstance(data, dict) and "error" in data:
                    err = data["error"]
                    code = err.get("code", "")
                    info = err.get("info", "?")
                    if code == "maxlag":
                        lag = err.get("lag", "?")
                        print(f"    maxlag={lag}s, proba {attempt+1}/{self.max_retries} po 10s")
                        time.sleep(10)
                        continue
                    print(f"    blad API: {code}: {info}")
                    return {}
                time.sleep(0.15)
                return data
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt == self.max_retries - 1:
                    raise
                sleep = min(30, 2 ** attempt)
                print(f"    blad polaczenia: {e}, proba {attempt+1}/{self.max_retries} po {sleep}s")
                time.sleep(sleep)
        raise Exception(f"Przekroczono max prob ({self.max_retries}) dla: {params.get('page', params.get('titles', '?'))}")


# --- HTML Cleaning Regexes ---

RE_SUP   = re.compile(r'<sup\b[^>]*>.*?</sup>', re.S)
RE_STYLE = re.compile(r'<style\b[^>]*>.*?</style>', re.S)
RE_SPANO = re.compile(r'<span\b[^>]*>')
RE_SPANC = re.compile(r'</span>')
EN_NAME_CAT_RE = re.compile(r'(masculine|feminine|unisex)\s+given\s+name', re.I)


# --- Utility Functions ---

SHARD_PL = str.maketrans("ąćęłńóśźż", "acelnoszz")


def shard_opisow(imie):
    """Litera sharda dla leniwie ładowanych opisów (musi zgadzać się z JS!)."""
    c = imie[:1].casefold().translate(SHARD_PL)
    return c if (c.isascii() and c.isalpha() and len(c) == 1) else "_"


def titlecase_pl(s):
    s = s.strip()
    out = []
    for t in re.split(r'([ \-])', s.lower()):
        out.append(t if t in (' ', '-') or t == '' else t[0].upper() + t[1:])
    return ''.join(out)


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


def is_name_article(categories):
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


def is_name_article_en(categories):
    if not categories:
        return False
    for c in categories:
        if EN_NAME_CAT_RE.search(c):
            return True
    return False


def origin_from_en_categories(categories):
    if not categories:
        return ""
    for c in categories:
        cl = c.lower().replace("category:", "")
        for keyword, origin in EN_CATEGORY_ORIGINS:
            if keyword in cl:
                return origin
    return ""


def origin_from_en_text(extract):
    if not extract:
        return ""
    low = extract.lower()
    for pat in EN_TEXT_PATTERNS:
        m = pat.search(low)
        if not m:
            continue
        token = m.group(1).strip()
        for keyword, origin in EN_CATEGORY_ORIGINS:
            if keyword in token:
                return origin
    return ""


def extract_base_names(plain):
    """Imiona bazowe z intro PL Wikipedii ("zdrobnienie imienia X" itp.)."""
    return [name for _, name in extract_base_relations(plain)]


def link_bazowe(all_rows, phase1):
    """Pola 'bazowe' (relacja + imię bazowe) i odwrotne 'pochodne'.

    Walidacja: imię bazowe musi istnieć w rejestrze PESEL (w dowolnej płci),
    inaczej link nie miałby dokąd prowadzić; odrzucamy też self-referencje.
    """
    by_name = {}
    for r in all_rows:
        by_name.setdefault(r["imie"].casefold(), r["imie"])
    pochodne = {}
    n_links = 0
    for r in all_rows:
        r.pop("bazowe", None)
        plain = phase1.get(r["imie"], {}).get("plain", "")
        if not plain:
            continue
        bazy = []
        for relacja, base in extract_base_relations(plain):
            canon = by_name.get(base.casefold())
            if not canon or canon.casefold() == r["imie"].casefold():
                continue
            if any(b["imie"] == canon for b in bazy):
                continue
            bazy.append({"relacja": relacja, "imie": canon})
            bucket = pochodne.setdefault(canon.casefold(), set())
            bucket.add(r["imie"])
        if bazy:
            r["bazowe"] = bazy
            n_links += len(bazy)
    n_poch = 0
    for r in all_rows:
        r.pop("pochodne", None)
        w = pochodne.get(r["imie"].casefold())
        if w:
            r["pochodne"] = sorted(w)
            n_poch += 1
    print(f"      powiązania imion: {n_links} relacji baza<-wariant, "
          f"{n_poch} imion z pochodnymi")


def wykryj_pochodzenie(plain, categories=None):
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


def origin_from_wd_langs(lang_counts):
    """lang_counts: {"język hebrajski": 3, ...} -> najczęstsze zmapowane pochodzenie."""
    scores = {}
    for label, cnt in lang_counts.items():
        low = label.lower()
        for frag, origin in ORIGIN_MAP:
            if frag in low:
                scores[origin] = scores.get(origin, 0) + cnt
                break
    if not scores:
        return ""
    return max(sorted(scores), key=lambda o: scores[o])


def _sparql_dump(cache_mgr, session, cache_name, build_query, add_row, label):
    """Shardowany dump z WDQS (64 zapytania: 4 klasy imion x 16 shardów MD5).

    Wynik akumuluje add_row(names, row) w słowniku `names`, cache wznawialny.
    Oporne shardy są dzielone na 16 pod-shardów po drugim znaku MD5.
    """
    cache = cache_mgr.load(cache_name)
    names = cache.get("names", {})
    done = set(cache.get("done", []))
    all_keys = [f"{cls}:{sh}" for cls in WD_NAME_CLASSES for sh in WD_SHARDS]
    todo = [k for k in all_keys if k not in done]
    if not todo:
        return names

    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
    print(f"  Wikidane ({label}): {len(todo)}/{len(all_keys)} shardów do pobrania")

    def _fetch_rows(cls, prefix, retries):
        query = build_query(cls, prefix)
        for attempt in range(retries):
            try:
                r = session.get(WD_SPARQL, params={"query": query},
                                headers={"Accept": "text/csv"}, timeout=120)
                if r.status_code in (429, 500, 502, 503, 504):
                    wait = int(r.headers.get("Retry-After", min(60, 5 * (attempt + 1))))
                    print(f"    WDQS HTTP {r.status_code} ({cls}:{prefix}), czekam {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                text = r.text
                if "java." in text[-500:] or "Exception" in text[-500:]:
                    raise ValueError("timeout WDQS (ucięta odpowiedź)")
                return list(csv.reader(text.splitlines()))[1:]
            except (requests.exceptions.RequestException, ValueError) as e:
                print(f"    WDQS błąd ({cls}:{prefix}): {e}, próba {attempt+1}/{retries}")
                time.sleep(min(60, 5 * (attempt + 1)))
        return None

    for key in todo:
        cls, shard = key.split(":")
        rows = _fetch_rows(cls, shard, 3)
        if rows is None:
            # oporny shard: tniemy drobniej, po drugim znaku MD5
            print(f"    WDQS: shard {key} nie schodzi w całości, dzielę na 16 pod-shardów")
            rows = []
            for sub in WD_SHARDS:
                sub_rows = _fetch_rows(cls, shard + sub, MAX_RETRIES)
                if sub_rows is None:
                    rows = None
                    break
                rows.extend(sub_rows)
                time.sleep(0.5)
        if rows is None:
            print(f"    WDQS: pomijam shard {key} po {MAX_RETRIES} próbach")
            continue
        for row in rows:
            if len(row) == 2:
                add_row(names, row)
        done.add(key)
        cache_mgr.save(cache_name, {"names": names, "done": sorted(done)})
        print(f"    {key}: +{len(rows)} wierszy ({len(names)} imion łącznie)")
        time.sleep(1)
    return names


def fetch_wikidata_bulk(cache_mgr, session=None):
    """Imiona z Wikidanych z językiem nazwy (P407).

    Zwraca: {imie_casefold: {"etykieta języka po polsku": liczba_wystąpień}}
    """
    def build_query(cls, prefix):
        return ('SELECT ?itemLabel ?langLabel WHERE { '
                f'?item wdt:P31 wd:{cls} ; wdt:P407 ?lang . '
                f'FILTER(STRSTARTS(MD5(STR(?item)), "{prefix}")) '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "mul,pl,en". } }')

    def add_row(names, row):
        name, lang = row[0].strip(), row[1].strip()
        if not name or not lang or lang == "wiele języków":
            return
        bucket = names.setdefault(name.casefold(), {})
        bucket[lang] = bucket.get(lang, 0) + 1

    return _sparql_dump(cache_mgr, session, "wd_bulk.json", build_query, add_row, "P407")


def fetch_wikidata_desc(cache_mgr, session=None):
    """Imiona z Wikidanych BEZ P407, ale z opisem ("Polish masculine given name",
    "imię męskie pochodzenia greckiego"). Drugi rzut po dumpie P407.

    Zwraca: {imie_casefold: [opisy...]}
    """
    def build_query(cls, prefix):
        return ('SELECT ?itemLabel ?d WHERE { '
                f'?item wdt:P31 wd:{cls} . '
                f'FILTER(STRSTARTS(MD5(STR(?item)), "{prefix}")) '
                'FILTER NOT EXISTS { ?item wdt:P407 [] } '
                '?item schema:description ?d . FILTER(LANG(?d) IN ("en","pl")) '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "mul,pl,en". } }')

    def add_row(names, row):
        name, desc = row[0].strip(), row[1].strip()
        if not name or not desc:
            return
        bucket = names.setdefault(name.casefold(), [])
        if desc not in bucket and len(bucket) < 6:
            bucket.append(desc)

    return _sparql_dump(cache_mgr, session, "wd_desc.json", build_query, add_row, "opisy")


def wd_desc_is_name(descs):
    return any("given name" in d.lower() or "first name" in d.lower()
               or "imię" in d.lower() for d in descs)


def origin_from_wd_descs(descs):
    for d in descs:
        low = d.lower()
        if "imię" in low:
            for frag, origin in ORIGIN_MAP:
                if frag in low:
                    return origin
        if "given name" in low or "first name" in low:
            for kw, origin in EN_CATEGORY_ORIGINS:
                if kw in low:
                    return origin
    return ""


MEANING_HINTS = ("pochodz", "wywodz", "oznacza", "znaczen", "etymolog",
                 "od słowa", "od imienia", "odpowiednik", "zdrobnien",
                 "spieszczen", "forma", "imię", "imienia", "imieniem")
STATS_HINTS = ("osób w polsce", "miejsce wśród", "miejsce z imion",
               "pesel", "popularnoś", "wedle danych", "według danych")


def wytnij_akapity(html_text):
    """Surowe akapity <p> z sekcji 0 (bez tabel/infoboksów) — do cache."""
    if not html_text:
        return []
    html_text = re.sub(r'<!--.*?-->', '', html_text, flags=re.S)
    html_text = RE_STYLE.sub('', html_text)
    # infoboksy generują akapity typu "682 516 osób w Polsce (1. miejsce…)"
    html_text = re.sub(r'<table\b.*?</table>', '', html_text, flags=re.S)
    paras = re.findall(r'<p\b[^>]*>(.*?)</p>', html_text, flags=re.S)
    return [p[:8000] for p in paras[:12]]


def wybierz_akapit(paras):
    """Akapit niosący ZNACZENIE imienia; statystyki i listy imienin odpadają.

    Brak sensownego akapitu => "" (strona pokaże "źródła nie podają znaczenia").
    """
    best, best_score = "", 0
    for i, p in enumerate(paras):
        t = html.unescape(re.sub(r'<[^>]+>', '', p)).strip()
        if len(t) < 25:
            continue
        low = t.lower()
        months = sum(1 for mn in MIESIACE_DOPELNIACZ if mn in low)
        digits = sum(c.isdigit() for c in t)
        stats = (any(h in low for h in STATS_HINTS) or months >= 3
                 or low.startswith("imieniny") or digits > len(t) * 0.2)
        meaning = sum(1 for h in MEANING_HINTS if h in low)
        if stats and not meaning:
            continue
        score = meaning * 10 - i - (15 if stats else 0)
        if score > best_score:
            best_score, best = score, p
    return best


# Sekcje, z których po krótkim lead'zie dociągamy akapity etymologiczne
# (faza 2b). Część artykułów ma w lead'zie tylko jedno generyczne zdanie
# typu "X – imię żeńskie pochodzenia greckiego", a właściwa etymologia
# (np. "od margarites — perła") siedzi w sekcji "Etymologia" / "Pochodzenie"
# / "Budowa oraz znaczenie" itp. Bez tego — patrz Małgorzata, Mirosław.
ETY_SECTION_PREFIX = ("etymolog", "pochodzenie", "znaczenie", "budowa",
                      "geneza", "etyma", "źródł")


def wytnij_akapity_etym(html_text):
    """Akapity z sekcji etymologicznych pełnego artykułu Wikipedii.

    Tnie HTML po znacznikach <h2>/<h3>, zachowuje akapity tylko z sekcji,
    których nazwa zaczyna się od jednego z ETY_SECTION_PREFIX. Sekcje typu
    Popularność / Imieniny / Osoby / Przypisy są pomijane (część z nich
    odpadłaby i tak w wybierz_akapit, ale jawne odcięcie to taniej).
    """
    if not html_text:
        return []
    s = re.sub(r'<!--.*?-->', '', html_text, flags=re.S)
    s = RE_STYLE.sub('', s)
    s = re.sub(r'<table\b.*?</table>', '', s, flags=re.S)
    parts = re.split(r'(<h[23]\b[^>]*>.*?</h[23]>)', s, flags=re.S)
    out = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        h_text = html.unescape(re.sub(r'<[^>]+>', '', parts[i])).strip().lower()
        h_text = re.sub(r'\[edytuj.*', '', h_text).strip()
        if not any(h_text.startswith(k) for k in ETY_SECTION_PREFIX):
            continue
        for p in re.findall(r'<p\b[^>]*>(.*?)</p>', body, flags=re.S)[:5]:
            out.append(p[:8000])
        if len(out) >= 10:
            break
    return out


# Etykiety sekcji listowych zaplątujące się w treść akapitu (np. "Znane osoby
# noszące imię Daniela:") — odsiewamy je przy doklejaniu drugiego akapitu.
NOISE_PARAGRAPH_PREFIXES = (
    "znane osoby", "osoby nosz", "osoby o imie", "osoby z imie",
    "pozostali", "pozostałe", "postacie fikcyjne", "bohater",
    "imieniny obchodz", "imienniczki", "imiennicy",
    "władczynie", "święte", "święci", "patron", "odpowiedniki",
    "w innych jęz", "zobacz też", "przypisy", "bibliografia",
    "odpowiednik", "warianty",
)


def _wyglada_jak_etykieta(p):
    """Czy akapit to nagłówek sekcji listowej zamknięty w <p>?"""
    t = html.unescape(re.sub(r'<[^>]+>', '', p)).strip()
    low = t.lower()
    if t.endswith(':') and len(t) < 80:
        return True
    if any(low.startswith(pref) for pref in NOISE_PARAGRAPH_PREFIXES):
        return True
    return False


def zbuduj_opis(paras_lead, paras_ety=None):
    """Składa opis_html z lead'a + (opcjonalnie) sekcji etymologicznych.

    Domyślnie zachowanie jak `wyczysc_akapit(wybierz_akapit(paras_lead))`.
    Jeśli wynik jest krótki (<80 znaków tekstu), próbuje dokleić drugi
    najlepszy akapit (z lead'a lub z paras_ety) — w kolejności
    dokumentowej, bez duplikatów. Drugi akapit musi mieć ≥2 wskazówki
    znaczeniowe (imię/pochodz/oznacza/wywodz/odpowiednik/...) i nie
    wyglądać jak etykieta sekcji listowej.
    """
    paras_lead = paras_lead or []
    paras_ety = paras_ety or []
    primary = wybierz_akapit(paras_lead)
    primary_clean = wyczysc_akapit(primary)
    primary_text = re.sub(r'<[^>]+>', '', primary_clean).strip()
    if len(primary_text) >= 80:
        return primary_clean

    pool = [p for p in (list(paras_lead) + list(paras_ety))
            if p != primary and not _wyglada_jak_etykieta(p)]
    extra = wybierz_akapit(pool)
    if extra:
        # Bez <sup> (przypisy) — inaczej cyfry przypisów zaburzają próg digit-frac.
        no_sup = RE_SUP.sub('', extra)
        extra_text = html.unescape(re.sub(r'<[^>]+>', '', no_sup)).strip()
        extra_low = extra_text.lower()
        # 1) Twardy odsiew akapitów PESEL / imieninowych (Honorata, Krzysztofa).
        months = sum(1 for mn in MIESIACE_DOPELNIACZ if mn in extra_low)
        digits = sum(c.isdigit() for c in extra_text)
        if (any(h in extra_low for h in STATS_HINTS) or months >= 3
                or extra_low.startswith("imieniny")
                or (extra_text and digits > len(extra_text) * 0.10)):
            extra = ""
        # 2) Próg: drugi akapit musi mieć ≥2 wskazówki znaczeniowe.
        elif sum(1 for h in MEANING_HINTS if h in extra_low) < 2:
            extra = ""
    extra_clean = wyczysc_akapit(extra) if extra else ""
    extra_text = re.sub(r'<[^>]+>', '', extra_clean).strip()
    if not extra_text or extra_text == primary_text \
            or extra_text in primary_text or primary_text in extra_text:
        return primary_clean

    # Zachowaj kolejność dokumentową.
    if primary in paras_lead and extra in paras_lead:
        if paras_lead.index(extra) < paras_lead.index(primary):
            return extra_clean + " " + primary_clean
        return primary_clean + " " + extra_clean
    if primary in paras_lead:        # primary z lead, extra z ety
        return primary_clean + " " + extra_clean
    return extra_clean + " " + primary_clean  # rzadkie: primary z ety


def wyczysc_akapit(chosen):
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


def log_stats(rows, phase_label, counts_before=None):
    total = len(rows)
    cat = sum(1 for r in rows if r.get("pochodzenie"))
    new = cat - counts_before.get("cat", 0) if counts_before is not None else 0
    by_src = {}
    for r in rows:
        s = r.get("_zrodlo")
        if s:
            by_src[s] = by_src.get(s, 0) + 1
    src_txt = " ".join(f"{k}={v}" for k, v in sorted(by_src.items()))
    name_articles = sum(1 for r in rows if r.get("_name_article"))
    denom = max(name_articles, cat) if name_articles else total
    uncat = denom - cat
    prefix = f"+{new} skat.  " if new else ""
    print(f"  [{phase_label}] {prefix}{src_txt}  "
          f"brak={uncat}/{denom} ({uncat/denom*100:.1f}%)")


# --- Wiktionary ---

API_WIKT_EN = "https://en.wiktionary.org/w/api.php"
API_WIKT_PL = "https://pl.wiktionary.org/w/api.php"

# en.wiktionary: kategorie typu "Polish female given names from Latin"
WIKT_EN_NAME_RE = re.compile(r'given names', re.I)
WIKT_EN_FROM_RE = re.compile(r'given names from ([a-z\- ]+)', re.I)

# pl.wiktionary: skróty językowe w sekcji etymologii ("łac.", "gr.", "hebr.")
WIKT_PL_ABBREV = {
    "łac": "lacinskie", "lac": "lacinskie", "gr": "greckie", "stgr": "greckie",
    "hebr": "hebrajskie", "aram": "aramejskie", "niem": "germanskie",
    "germ": "germanskie", "goc": "germanskie", "ang": "angielskie",
    "stang": "anglosaskie", "fr": "francuskie", "franc": "francuskie",
    "prowans": "prowansalskie", "wł": "wloskie", "wl": "wloskie",
    "hiszp": "hiszpanskie", "port": "hiszpanskie", "katal": "hiszpanskie",
    "ros": "rosyjskie", "ukr": "ukrainskie", "błrus": "slowianskie",
    "czes": "slowianskie", "czesk": "slowianskie", "słowac": "slowianskie",
    "węg": "wegierskie", "weg": "wegierskie", "tur": "tureckie",
    "arab": "arabskie", "pers": "perskie", "sanskr": "sanskryckie",
    "hindi": "indyjskie", "skand": "skandynawskie", "szw": "skandynawskie",
    "norw": "skandynawskie", "duń": "skandynawskie", "isl": "skandynawskie",
    "stnord": "skandynawskie", "fiń": "finskie", "fin": "finskie",
    "est": "finskie", "lit": "litewskie", "łot": "litewskie",
    "celt": "celtyckie", "irl": "celtyckie", "szkoc": "celtyckie",
    "wal": "celtyckie", "stpol": "staropolskie", "prasłow": "slowianskie",
    "prasł": "slowianskie", "stczes": "slowianskie", "strus": "ruskie",
    "słow": "slowianskie", "scs": "slowianskie", "jap": "japonskie",
    "chiń": "chinskie", "kor": "koreanskie", "gruz": "gruzinskie",
    "orm": "ormianskie", "egip": "egipskie", "bask": "baskijskie",
}
WIKT_PL_TOKEN_RE = re.compile(r'\b([a-ząćęłńóśźż]{2,8})\.')
WIKT_PL_IS_NAME_RE = re.compile(r'imi[ęe]\s+(?:żeńskie|męskie|osobowe)|polskie\s+imi[ęe]', re.I)


def origin_from_wikt_en_cats(cats):
    """("is_name", "origin") z kategorii en.wiktionary."""
    is_name = any(WIKT_EN_NAME_RE.search(c) for c in cats)
    if not is_name:
        return False, ""
    for c in cats:
        m = WIKT_EN_FROM_RE.search(c)
        if not m:
            continue
        token = m.group(1).lower().strip()
        for kw, origin in EN_CATEGORY_ORIGINS:
            if kw in token:
                return True, origin
    return True, ""


def wikt_pl_etym_windows(text):
    """Okna tekstu wokół 'etymologia' z pełnego ekstraktu pl.wiktionary."""
    if not text:
        return ""
    out = []
    for m in re.finditer(r'etymolog', text, re.I):
        out.append(text[m.start():m.start() + 260])
        if len(out) >= 4:
            break
    return " | ".join(out)


def origin_from_wikt_pl(etym):
    """Pochodzenie ze skrótów ("łac.", "gr.") albo pełnych przymiotników."""
    if not etym:
        return ""
    low = etym.lower()
    for token in WIKT_PL_TOKEN_RE.findall(low):
        if token in WIKT_PL_ABBREV:
            return WIKT_PL_ABBREV[token]
    for frag, origin in ORIGIN_MAP:
        if frag in low:
            return origin
    return ""


# --- zaimki.pl (imiona niebinarne) ---

MIESIACE_DOPELNIACZ = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
                       "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

RE_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)$')


def md_links_to_html(text):
    """zaimki.pl trzyma 'znane osoby' jako linki Markdown rozdzielone '|'."""
    if not text:
        return ""
    parts = []
    for chunk in text.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = RE_MD_LINK.match(chunk)
        if m:
            label = html.escape(m.group(1))
            url = html.escape(m.group(2), quote=True)
            parts.append(f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>')
        else:
            parts.append(html.escape(chunk))
    return " · ".join(parts)


def format_imieniny(namedays):
    out = []
    for d in (namedays or "").split("|"):
        d = d.strip()
        m = re.match(r'(\d{2})-(\d{2})$', d)
        if m and 1 <= int(m.group(1)) <= 12:
            out.append(f"{int(m.group(2))} {MIESIACE_DOPELNIACZ[int(m.group(1)) - 1]}")
        elif d:
            out.append(d)
    return out


def origin_slug_pl(text):
    """Wolny tekst pochodzenia z zaimki.pl -> slug jak w PESEL-owych datasetach."""
    if not text:
        return ""
    first = re.split(r'[/,]', text.lower())[0]
    for source in (first, text.lower()):
        for frag, origin in ORIGIN_MAP:
            if frag in source:
                return origin
    return ""


def pobierz_zaimki(cache_mgr, session):
    try:
        r = session.get(ZAIMKI_API, timeout=60)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or not data:
            raise ValueError("nieoczekiwany format odpowiedzi")
        cache_mgr.save("zaimki.json", data)
        return data
    except Exception as e:
        print(f"      zaimki.pl niedostępne ({e}), próbuję z cache …")
        cached = cache_mgr.load("zaimki.json")
        return cached if isinstance(cached, list) else []


def przetworz_zaimki(raw):
    def s(v):
        return (v or "").strip()

    merged = {}
    order = []
    for e in raw:
        if e.get("locale") != "pl" or not e.get("approved") or e.get("deleted"):
            continue
        name = s(e.get("name"))
        if not name:
            continue
        key = name.casefold()
        if key not in merged:
            merged[key] = dict(e, name=name)
            order.append(key)
        else:
            # duplikaty: bierzemy pierwszą niepustą wartość każdego pola
            for f, v in e.items():
                if not merged[key].get(f) and v:
                    merged[key][f] = v

    rows = []
    for key in order:
        e = merged[key]
        name = s(e.get("name"))
        origin = s(e.get("origin"))
        rows.append({
            "imie": name,
            "warianty": [v.strip() for v in name.split("/") if v.strip()],
            "pochodzenie": origin_slug_pl(origin),
            "pochodzenie_opis": origin,
            "znaczenie": s(e.get("meaning")),
            "uzycie": s(e.get("usage")),
            "prawnie": s(e.get("legally")),
            "plusy": s(e.get("pros")),
            "minusy": s(e.get("cons")),
            "imieniny": format_imieniny(e.get("namedays")),
            "imieniny_kom": s(e.get("namedaysComment")),
            "znane_osoby_html": md_links_to_html(s(e.get("notablePeople"))),
            "linki": [u.strip() for u in s(e.get("links")).split("|")
                      if u.strip().startswith("http")],
        })
    rows.sort(key=lambda r: r["imie"].casefold())
    return rows


# --- Cache Manager ---

class CacheManager:
    def __init__(self, cache_dir=CACHE_DIR):
        self.dir = cache_dir

    def load(self, name):
        path = os.path.join(self.dir, name)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save(self, name, data):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def clear(self):
        import shutil
        if os.path.exists(self.dir):
            shutil.rmtree(self.dir)
            print(f"Usunieto {self.dir}/")


# --- Name Dataset ---

class NameDataset:
    def __init__(self, rows=None, gender=""):
        self.rows = rows or []
        self.gender = gender

    @classmethod
    def from_pesel(cls, first_path, second_path):
        first = wczytaj_liczby(first_path)
        second = wczytaj_liczby(second_path)
        rows = []
        for n in set(first) | set(second):
            rows.append({"imie": n, "wystapienia_pierwsze": first.get(n, 0),
                         "wystapienia_drugie": second.get(n, 0)})
        rows.sort(key=lambda r: -(r["wystapienia_pierwsze"] + r["wystapienia_drugie"]))
        return cls(rows)

    @property
    def names(self):
        return [r["imie"] for r in self.rows]

    def limit(self, n):
        if n:
            self.rows = self.rows[:n]

    def merge(self, old_rows):
        old_by_name = {r["imie"]: r for r in old_rows}
        for r in self.rows:
            old = old_by_name.get(r["imie"])
            if old:
                r["pochodzenie"] = old.get("pochodzenie", "")
                r["opis_html"] = old.get("opis_html", "")
                if old.get("zrodlo"):
                    r["zrodlo"] = old["zrodlo"]
                if old.get("zrodlo_baza"):
                    r["zrodlo_baza"] = old["zrodlo_baza"]

    def save(self, base):
        cols = ["imie", "wystapienia_pierwsze", "wystapienia_drugie", "pochodzenie", "opis_html"]
        with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in self.rows:
                w.writerow({k: r.get(k, "") for k in cols})
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(self.rows, f, ensure_ascii=False)

    def cleanup(self):
        for r in self.rows:
            r.setdefault("pochodzenie", "")
            r.setdefault("opis_html", "")
            zr = r.pop("_zrodlo", None)
            zb = r.pop("_zrodlo_baza", None)
            r.pop("zrodlo", None)
            r.pop("zrodlo_baza", None)
            if r["pochodzenie"] and zr:
                r["zrodlo"] = zr
                if zb:
                    r["zrodlo_baza"] = zb
            r.pop("_name_article", None)

    def count(self, key):
        return sum(1 for r in self.rows if r.get(key))


# --- Dataset Builder ---

class DatasetBuilder:
    def __init__(self):
        self.args = None
        self.cache = CacheManager()
        self.session = None
        self.client_pl = None
        self.client_en = None
        self.client_wikt_en = None
        self.client_wikt_pl = None
        self.wd_names = None
        self.wd_descs = None
        self.meskie = None
        self.zenskie = None
        self.niebinarne = []
        self.m_istniejace = None
        self.z_istniejace = None

    def run(self):
        self.args = self._parse_args()
        os.makedirs(RAW_DIR, exist_ok=True)
        self._handle_od_nowa()
        self._handle_no_sleep()
        self._load_existing()
        self._download_pesel()
        self._build_datasets()
        self._merge_existing()
        self._apply_limit()
        self._setup_api_clients()
        self._run_enrichment()
        self._inherit_origins()
        self._apply_morphology()
        self._link_bazowe()
        self._build_niebinarne()
        self._print_final_stats()
        self._cleanup_rows()
        self._save_all()

    def _parse_args(self):
        ap = argparse.ArgumentParser(
            description="Buduje i wzbogaca dataset imion polskich z PESEL + Wikipedii")
        ap.add_argument("--limit", type=int, default=LIMIT_NA_PLEC,
                        help="Wzbogac tylko N najpopularniejszych imion kazdej plci.")
        ap.add_argument("--incremental", "-i", action="store_true",
                        help="Tryb przyrostowy: wczytaj istniejace dane, "
                             "przetworz tylko imiona bez pochodzenia/opisu.")
        ap.add_argument("--shutdown", action="store_true",
                        help="Wylacz komputer po zakonczeniu.")
        ap.add_argument("--no-sleep", action="store_true",
                        help="Nie usypiaj komputera podczas budowania (systemd-inhibit).")
        ap.add_argument("--skip-pl", action="store_true",
                        help="Pomin polska Wikipedie.")
        ap.add_argument("--skip-en", action="store_true",
                        help="Pomin angielska Wikipedie.")
        ap.add_argument("--skip-wd", action="store_true",
                        help="Pomin Wikidane.")
        ap.add_argument("--skip-wikt", action="store_true",
                        help="Pomin Wikislowniki (en/pl Wiktionary).")
        ap.add_argument("--skip-zaimki", action="store_true",
                        help="Pomin pobieranie imion niebinarnych z zaimki.pl.")
        ap.add_argument("--od-nowa", action="store_true",
                        help="Usuwa cache Wikipedii i surowe pliki PESEL, buduje od nowa.")
        return ap.parse_args()

    def _handle_od_nowa(self):
        if not self.args.od_nowa:
            return
        import shutil
        self.cache.clear()
        if os.path.exists(RAW_DIR):
            shutil.rmtree(RAW_DIR)
            print(f"Usunieto {RAW_DIR}/")
            os.makedirs(RAW_DIR, exist_ok=True)

    def _handle_no_sleep(self):
        if not self.args.no_sleep or "SYSTEMD_INHIBIT" in os.environ:
            return
        import shutil
        if shutil.which("systemd-inhibit"):
            # PYTHONUNBUFFERED: po re-execu znika flaga -u, a bez niej
            # stdout do pliku buforuje się i log wygląda na martwy
            env = {**os.environ, "SYSTEMD_INHIBIT": "1", "PYTHONUNBUFFERED": "1"}
            os.execvpe("systemd-inhibit", [
                "systemd-inhibit", "--why=Buduje dataset imion",
                sys.executable, __file__
            ] + sys.argv[1:], env)

    def _load_existing(self):
        if not self.args.incremental:
            return
        print("[0/4] Tryb przyrostowy - laduje istniejace dane …")
        m, z = self._wczytaj_json_dataset("dataset_meskie.json"), \
               self._wczytaj_json_dataset("dataset_zenskie.json")
        if m is not None and z is not None:
            self.m_istniejace = m
            self.z_istniejace = z
            print(f"      Wczytano: meskie {len(m)}, zenskie {len(z)}")
        else:
            print("      Brak istniejacych danych, przechodze do normalnego trybu.")

    def _wczytaj_json_dataset(self, path):
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _download_pesel(self):
        print("[1/4] Pobieram liste zasobow z dane.gov.pl …")
        zasoby = pobierz_zasoby()
        wybor = wybierz_najnowsze(zasoby)
        if len(wybor) < 4:
            sys.exit(f"Nie znaleziono 4 plikow. Znaleziono: {list(wybor)}")
        self.pliki = {}
        for key, (date, url, title) in wybor.items():
            dest = os.path.join(RAW_DIR, key + ".xlsx")
            print(f"      {key}: {title} (stan {date})")
            sciagnij(url, dest)
            self.pliki[key] = dest

    def _build_datasets(self):
        print("[2/4] Buduje datasety …")
        self.meskie = NameDataset.from_pesel(self.pliki["m_pierwsze"], self.pliki["m_drugie"])
        self.zenskie = NameDataset.from_pesel(self.pliki["z_pierwsze"], self.pliki["z_drugie"])
        print(f"      meskie: {len(self.meskie.rows)} imion, "
              f"zenskie: {len(self.zenskie.rows)} imion")

    def _merge_existing(self):
        if self.m_istniejace is None or self.z_istniejace is None:
            return
        self.meskie.merge(self.m_istniejace)
        self.zenskie.merge(self.z_istniejace)
        n_zrodlo = sum(1 for r in self.meskie.rows + self.zenskie.rows
                       if r.get("pochodzenie") or r.get("opis_html"))
        print(f"      Z istniejacych danych: {n_zrodlo} imion ma pochodzenie/opis")

    def _apply_limit(self):
        if self.args.limit:
            print(f"      LIMIT: tylko {self.args.limit} najpopularniejszych kazdej plci")
            self.meskie.limit(self.args.limit)
            self.zenskie.limit(self.args.limit)

    def _setup_api_clients(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        ratelimiter_pl = RateLimiter(RATE_LIMIT_REQ, RATE_LIMIT_WIN)
        self.client_pl = WikiAPIClient(self.session, ratelimiter_pl, maxlag=MAXLAG)
        if not self.args.skip_en:
            ratelimiter_en = RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN)
            self.client_en = WikiAPIClient(self.session, ratelimiter_en,
                                           base_url=API_EN, maxlag=MAXLAG)
        if not self.args.skip_wikt:
            self.client_wikt_en = WikiAPIClient(self.session, RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN),
                                                base_url=API_WIKT_EN, maxlag=MAXLAG)
            self.client_wikt_pl = WikiAPIClient(self.session, RateLimiter(RATE_LIMIT_REQ, RATE_LIMIT_WIN),
                                                base_url=API_WIKT_PL, maxlag=MAXLAG)
        if not self.args.skip_wd:
            self.wd_names = fetch_wikidata_bulk(self.cache, self.session)
            self.wd_descs = fetch_wikidata_desc(self.cache, self.session)

    def _run_enrichment(self):
        if not self.args.skip_pl:
            for dataset, label in [(self.meskie, "meskie"), (self.zenskie, "zenskie")]:
                print(f"[3/4] Wzbogacam ({label}) …")
                self._enrich(dataset)
        else:
            print("[3/4] Pomijam PL Wikipedie (--skip-pl) …")
            self._enrich(NameDataset(self.meskie.rows + self.zenskie.rows),
                         skip_pl=True)

    def _enrich(self, dataset, skip_pl=False):
        rows = dataset.rows
        kept = []
        if self.args.incremental:
            do_process = [r for r in rows
                          if not r.get("pochodzenie") and not r.get("opis_html")]
            kept = [r for r in rows if r.get("pochodzenie") or r.get("opis_html")]
            print(f"  Tryb incremental: {len(do_process)} do przetworzenia, "
                  f"{len(kept)} juz gotowych")
            if not do_process:
                dataset.rows = kept
                return
            rows = do_process

        # Źródła w kolejności: najtańsze i najpewniejsze najpierw.
        if not skip_pl:
            names = [r["imie"] for r in rows]
            phase1 = self._faza1_istnienie(names)
            phase2 = self._faza2_opis(names, phase1)
            phase2b = self._faza2b_etymologia(names, phase1, phase2)
            before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
            self._enrich_pl(rows, phase1, phase2, phase2b)
            log_stats(rows, "PL", before)

        if self.wd_names is not None:
            need = [r for r in rows if not r.get("pochodzenie")]
            if need:
                before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
                self._apply_enrich_wd(need)
                log_stats(rows, "WD", before)

        if self.client_en:
            need = [r for r in rows if not r.get("pochodzenie")]
            if need:
                before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
                self._apply_enrich_en(need)
                log_stats(rows, "EN", before)

        if self.client_wikt_en:
            need = [r for r in rows if not r.get("pochodzenie")]
            if need:
                before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
                self._apply_enrich_wikt_en(need)
                log_stats(rows, "WIKT-EN", before)

        if self.client_wikt_pl:
            need = [r for r in rows if not r.get("pochodzenie")]
            if need:
                before = {"cat": sum(1 for r in rows if r.get("pochodzenie"))}
                self._apply_enrich_wikt_pl(need)
                log_stats(rows, "WIKT-PL", before)

        if self.args.incremental:
            dataset.rows = kept + rows

    def _faza1_istnienie(self, names):
        cache = self.cache.load("phase1.json")

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
            data = self.client_pl.get(params)
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
        total_names = len(names)
        print(f"  Faza 1 (istnienie/kategorie): {len(todo)} nowych z {total_names} "
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

            for n in batch:
                t = norm.get(n, n)
                info = ret.get(t) or ret.get(n) or {"exists": False, "plain": "", "cats": []}
                info["page_title"] = t
                cache[n] = info

            if (i // BATCH_SIZE) % 5 == 0:
                self.cache.save("phase1.json", cache)
                done = min(i+BATCH_SIZE, len(todo))
                print(f"    ...{done}/{len(todo)} ({len(cache)} lacznie w cache)")

        self.cache.save("phase1.json", cache)

        # Retry "X (imię)": strony ujednoznaczniające ORAZ artykuły istniejące,
        # ale nie o imieniu (Dominika = państwo, a "Dominika (imię)" istnieje).
        retry = [n for n in names
                 if n in cache and cache[n].get("exists")
                 and not cache[n].get("imie_retry")
                 and (_is_disambig(cache[n])
                      or is_name_article(cache[n].get("cats", [])) is False)]
        print(f"  Faza 1b (retry '(imię)'): {len(retry)} kandydatów")
        for i in range(0, len(retry), BATCH_SIZE):
            batch = retry[i:i+BATCH_SIZE]
            suffixed = [f"{n} (imi\u0119)" for n in batch]
            try:
                ret2, norm2 = _fetch(suffixed)
            except Exception as e:
                print(f"    blad retry (imię): {e}")
                continue
            for n, sfx in zip(batch, suffixed):
                t = norm2.get(sfx, sfx)
                info2 = ret2.get(t) or ret2.get(sfx) or {"exists": False}
                cache[n]["imie_retry"] = True
                if info2.get("exists") and not _is_disambig(info2):
                    info2["page_title"] = t
                    info2["imie_retry"] = True
                    cache[n] = info2
            if (i // BATCH_SIZE) % 5 == 0:
                self.cache.save("phase1.json", cache)
                print(f"    ...{min(i+BATCH_SIZE, len(retry))}/{len(retry)}")
        self.cache.save("phase1.json", cache)

        for n in cache:
            if cache[n].get("exists") and _is_disambig(cache[n]):
                cache[n]["disambig"] = True
            else:
                cache[n]["disambig"] = False
        self.cache.save("phase1.json", cache)
        return cache

    def _faza2_opis(self, names, phase1):
        cache = self.cache.load("phase2.json")
        def _needs(n, title):
            e = cache.get(n)
            # refetch: brak wpisu, stary format (bez "paras") albo artykuł
            # zmienił się po retry "(imię)" w fazie 1
            return e is None or "paras" not in e or e.get("src_title") != title
        kandydaci = [(n, phase1.get(n, {}).get("page_title", n))
                     for n in names if phase1.get(n, {}).get("exists")
                     and _needs(n, phase1.get(n, {}).get("page_title", n))]
        print(f"  Faza 2 (opis HTML): {len(kandydaci)} do pobrania (w cache: {len(cache)})")
        done = 0
        for n, page_title in kandydaci:
            params = {
                "action": "parse", "format": "json", "prop": "text",
                "section": 0, "redirects": 1, "formatversion": 2, "page": page_title,
            }
            try:
                data = self.client_pl.get(params)
                text = data.get("parse", {}).get("text", "")
                cache[n] = {"paras": wytnij_akapity(text), "src_title": page_title}
            except Exception:
                cache[n] = {"paras": [], "src_title": page_title}
            done += 1
            if done % 25 == 0:
                self.cache.save("phase2.json", cache)
                print(f"    ...{done}/{len(kandydaci)} ({len(cache)} lacznie w cache)")
        self.cache.save("phase2.json", cache)
        return cache

    def _faza2b_etymologia(self, names, phase1, phase2):
        """Dla imion z krótkim lead'em (Małgorzata, Mirosław…) dociąga akapity
        z sekcji 'Etymologia' / 'Pochodzenie' / 'Budowa' / itp. pełnego artykułu.

        Pobranie tylko dla rzeczywistych kandydatów (~kilkaset), wynik w
        oddzielnym cache `phase2b.json`, by nie inwalidować phase2.
        """
        cache = self.cache.load("phase2b.json")

        def _short_lead(n):
            paras = (phase2.get(n) or {}).get("paras") or []
            chosen = wybierz_akapit(paras)
            if not chosen:
                return False  # nic w lead'zie i tak nie naprawi etymologia
            clean = wyczysc_akapit(chosen)
            text = re.sub(r'<[^>]+>', '', clean).strip()
            return len(text) < 80

        kandydaci = []
        for n in names:
            if not phase1.get(n, {}).get("exists"):
                continue
            if not _short_lead(n):
                continue
            page_title = phase1.get(n, {}).get("page_title", n)
            e = cache.get(n)
            if e and e.get("src_title") == page_title and "paras_ety" in e:
                continue
            kandydaci.append((n, page_title))

        print(f"  Faza 2b (sekcje etymologii): {len(kandydaci)} do pobrania "
              f"(w cache: {len(cache)})")
        done = 0
        for n, page_title in kandydaci:
            params = {
                "action": "parse", "format": "json", "prop": "text",
                "redirects": 1, "formatversion": 2, "page": page_title,
            }
            try:
                data = self.client_pl.get(params)
                text = data.get("parse", {}).get("text", "")
                cache[n] = {"paras_ety": wytnij_akapity_etym(text),
                            "src_title": page_title}
            except Exception:
                cache[n] = {"paras_ety": [], "src_title": page_title}
            done += 1
            if done % 25 == 0:
                self.cache.save("phase2b.json", cache)
                print(f"    ...{done}/{len(kandydaci)} "
                      f"({len(cache)} lacznie w cache)")
        self.cache.save("phase2b.json", cache)
        return cache

    def _check_en_wikipedia(self, names):
        cache = self.cache.load("phase_en.json")
        # refetch wpisów z czasów, gdy nie pobieraliśmy intro (brak klucza "extract")
        todo = [n for n in names if n not in cache
                or (cache[n].get("exists") and "extract" not in cache[n])]
        total_names = len(names)
        print(f"  EN Wikipedia: {len(todo)} nowych z {total_names} (w cache: {len(cache)})")
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i:i+BATCH_SIZE]
            params = {
                "action": "query", "format": "json",
                "prop": "extracts|categories",
                "exintro": 1, "explaintext": 1, "exlimit": "max",
                "cllimit": "max", "clshow": "!hidden",
                "redirects": 1, "formatversion": 2,
                "titles": "|".join(batch),
            }
            try:
                data = self.client_en.get(params)
            except Exception as e:
                print(f"    blad EN batch: {e}")
                for n in batch:
                    cache[n] = {"exists": False, "is_name": False, "origin": "",
                                "cats": [], "extract": ""}
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
                extract = pg.get("extract", "") or ""
                is_name = is_name_article_en(cats)
                origin = ""
                if is_name:
                    origin = origin_from_en_categories(cats) or origin_from_en_text(extract)
                cache[n] = {"exists": (not missing), "is_name": is_name,
                            "origin": origin, "cats": cats, "extract": extract}
            if (i // BATCH_SIZE) % 5 == 0:
                self.cache.save("phase_en.json", cache)
                done = min(i+BATCH_SIZE, len(todo))
                print(f"    ...{done}/{len(todo)} ({len(cache)} lacznie w cache)")
        self.cache.save("phase_en.json", cache)
        return cache

    def _enrich_pl(self, rows, phase1, phase2, phase2b=None):
        phase2b = phase2b or {}
        for idx, r in enumerate(rows):
            n = r["imie"]
            p1 = phase1.get(n, {})
            is_name = is_name_article(p1.get("cats", []))
            is_disambig = (
                p1.get("disambig", False) or
                any("ujednoznaczn" in c.lower() for c in p1.get("cats", []))
            )
            opis = ""
            if p1.get("exists") and not is_disambig and is_name is not False:
                if is_name is True:
                    r["_name_article"] = True
                o = wykryj_pochodzenie(p1.get("plain", ""), p1.get("cats", []))
                if o:
                    r["pochodzenie"] = o
                    r["_zrodlo"] = "PL"
                    print(f"    PL: {n} -> {o}")
                e2 = phase2.get(n, {})
                paras = e2.get("paras")
                if paras is None:  # stary format cache
                    paras = [e2["opis_html"]] if e2.get("opis_html") else []
                paras_ety = (phase2b.get(n) or {}).get("paras_ety") or []
                opis = zbuduj_opis(paras, paras_ety)
            r["opis_html"] = opis
            if (idx + 1) % 500 == 0:
                processed = idx + 1
                na = sum(1 for rr in rows[:processed] if rr.get("_name_article"))
                cat = sum(1 for rr in rows[:processed] if rr.get("pochodzenie"))
                denom = na if na else processed
                print(f"  PL {processed}/{len(rows)}  skat={cat}/{denom} "
                      f"({cat/denom*100:.1f}%)")

    def _apply_enrich_en(self, need_en):
        if not need_en:
            return
        print(f"  EN Wikipedia (fallback): {len(need_en)} imion bez pochodzenia")
        en_cache = self._check_en_wikipedia([r["imie"] for r in need_en])
        for idx, r in enumerate(need_en):
            en = en_cache.get(r["imie"], {})
            if en.get("is_name"):
                r["_name_article"] = True
                origin = (origin_from_en_categories(en.get("cats", []))
                          or origin_from_en_text(en.get("extract", "")))
                if origin:
                    r["pochodzenie"] = origin
                    r["_zrodlo"] = "EN"
            if (idx + 1) % 500 == 0:
                processed = idx + 1
                na = sum(1 for rr in need_en[:processed] if rr.get("_name_article"))
                cat = sum(1 for rr in need_en[:processed] if rr.get("pochodzenie"))
                denom = na if na else processed
                print(f"  EN {processed}/{len(need_en)}  skat={cat}/{denom} "
                      f"({cat/denom*100:.1f}%)")

    def _apply_enrich_wd(self, need_wd):
        if not need_wd:
            return
        print(f"  Wikidane (lokalne dopasowanie): {len(need_wd)} imion bez pochodzenia")
        hits = hits_d = 0
        for r in need_wd:
            key = r["imie"].casefold()
            langs = self.wd_names.get(key)
            if langs:
                r["_name_article"] = True
                origin = origin_from_wd_langs(langs)
                if origin:
                    r["pochodzenie"] = origin
                    r["_zrodlo"] = "WD"
                    hits += 1
                    continue
            descs = (self.wd_descs or {}).get(key)
            if descs and wd_desc_is_name(descs):
                r["_name_article"] = True
                origin = origin_from_wd_descs(descs)
                if origin:
                    r["pochodzenie"] = origin
                    r["_zrodlo"] = "WDD"
                    hits_d += 1
        print(f"    WD: dopasowano {hits} (P407) + {hits_d} (opisy) / {len(need_wd)}")

    def _check_wikt_en(self, names):
        cache = self.cache.load("phase_wikt_en.json")
        todo = [n for n in names if n not in cache]
        print(f"  EN Wiktionary: {len(todo)} nowych z {len(names)} (w cache: {len(cache)})")
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i:i+BATCH_SIZE]
            params = {
                "action": "query", "format": "json",
                "prop": "categories", "cllimit": "max", "clshow": "!hidden",
                "redirects": 1, "formatversion": 2,
                "titles": "|".join(batch),
            }
            try:
                data = self.client_wikt_en.get(params)
            except Exception as e:
                print(f"    blad WIKT-EN batch: {e}")
                for n in batch:
                    cache[n] = {"cats": []}
                continue
            pages = data.get("query", {}).get("pages", [])
            norm = {}
            for rd in data.get("query", {}).get("redirects", []):
                norm[rd["from"]] = rd["to"]
            for nm in data.get("query", {}).get("normalized", []):
                norm[nm["from"]] = nm["to"]
            pg_by_title = {pg.get("title", ""): pg for pg in pages}
            for n in batch:
                t = norm.get(n, n)
                pg = pg_by_title.get(t) or pg_by_title.get(n) or {}
                cache[n] = {"cats": [c["title"] for c in pg.get("categories", [])]}
            if (i // BATCH_SIZE) % 25 == 0:
                self.cache.save("phase_wikt_en.json", cache)
                print(f"    ...{min(i+BATCH_SIZE, len(todo))}/{len(todo)}")
        self.cache.save("phase_wikt_en.json", cache)
        return cache

    def _apply_enrich_wikt_en(self, need):
        if not need:
            return
        print(f"  EN Wiktionary (fallback): {len(need)} imion bez pochodzenia")
        cache = self._check_wikt_en([r["imie"] for r in need])
        for r in need:
            cats = cache.get(r["imie"], {}).get("cats", [])
            is_name, origin = origin_from_wikt_en_cats(cats)
            if is_name:
                r["_name_article"] = True
                if origin:
                    r["pochodzenie"] = origin
                    r["_zrodlo"] = "WIKT-EN"

    def _check_wikt_pl(self, names):
        cache = self.cache.load("phase_wikt_pl.json")
        todo = [n for n in names if n not in cache]
        print(f"  PL Wikisłownik: {len(todo)} nowych z {len(names)} (w cache: {len(cache)})")
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i:i+BATCH_SIZE]
            params = {
                "action": "query", "format": "json",
                "prop": "extracts", "explaintext": 1, "exlimit": "max",
                "redirects": 1, "formatversion": 2,
                "titles": "|".join(batch),
            }
            try:
                data = self.client_wikt_pl.get(params)
            except Exception as e:
                print(f"    blad WIKT-PL batch: {e}")
                for n in batch:
                    cache[n] = {"etym": "", "is_name": False}
                continue
            pages = data.get("query", {}).get("pages", [])
            norm = {}
            for rd in data.get("query", {}).get("redirects", []):
                norm[rd["from"]] = rd["to"]
            for nm in data.get("query", {}).get("normalized", []):
                norm[nm["from"]] = nm["to"]
            pg_by_title = {pg.get("title", ""): pg for pg in pages}
            for n in batch:
                t = norm.get(n, n)
                pg = pg_by_title.get(t) or pg_by_title.get(n) or {}
                text = pg.get("extract", "") or ""
                cache[n] = {"etym": wikt_pl_etym_windows(text),
                            "is_name": bool(WIKT_PL_IS_NAME_RE.search(text))}
            if (i // BATCH_SIZE) % 25 == 0:
                self.cache.save("phase_wikt_pl.json", cache)
                print(f"    ...{min(i+BATCH_SIZE, len(todo))}/{len(todo)}")
        self.cache.save("phase_wikt_pl.json", cache)
        return cache

    def _apply_enrich_wikt_pl(self, need):
        if not need:
            return
        print(f"  PL Wikisłownik (fallback): {len(need)} imion bez pochodzenia")
        cache = self._check_wikt_pl([r["imie"] for r in need])
        for r in need:
            e = cache.get(r["imie"], {})
            if not e.get("is_name"):
                continue
            r["_name_article"] = True
            origin = origin_from_wikt_pl(e.get("etym", ""))
            if origin:
                r["pochodzenie"] = origin
                r["_zrodlo"] = "WIKT-PL"

    def _apply_morphology(self):
        """Żeńskie formy bez własnej etymologii dziedziczą po męskiej bazie.

        Heurystyka morfologiczna z walidacją: Karolina -> Karol tylko jeśli
        "Karol" istnieje w rejestrze i MA już ustalone pochodzenie.
        """
        all_rows = self.meskie.rows + self.zenskie.rows
        origin_by = {}
        for r in all_rows:
            if r.get("pochodzenie"):
                origin_by.setdefault(r["imie"].casefold(), r["pochodzenie"])
        hits = 0
        for r in self.zenskie.rows:
            if r.get("pochodzenie"):
                continue
            n = r["imie"]
            candidates = []
            if (n.endswith("ina") or n.endswith("yna")) and len(n) > 5:
                candidates.append(n[:-3])      # Karolina -> Karol
            if n.endswith("a") and len(n) > 3:
                candidates.append(n[:-1])      # Bogdana -> Bogdan
            for c in candidates:
                o = origin_by.get(c.casefold())
                if o:
                    r["pochodzenie"] = o
                    r["_zrodlo"] = "MORF"
                    r["_zrodlo_baza"] = c
                    hits += 1
                    break
        print(f"  [MORF] żeńskie formy od męskich baz: +{hits}")

    def _inherit_origins(self):
        """Imiona będące zdrobnieniem/wariantem dziedziczą pochodzenie bazy.

        "Ola — zdrobnienie imienia Aleksandra" nie ma własnej etymologii na
        Wikipedii, ale Aleksandra ma. Bazę bierzemy z intro PL Wikipedii
        (cache fazy 1), pochodzenie bazy z już wzbogaconych wierszy albo
        z hurtowego dumpu Wikidanych.
        """
        phase1 = self.cache.load("phase1.json")
        if not phase1:
            return
        all_rows = self.meskie.rows + self.zenskie.rows
        origin_by_name = {}
        for r in all_rows:
            if r.get("pochodzenie"):
                origin_by_name.setdefault(r["imie"].casefold(), r["pochodzenie"])

        def base_origin(base):
            o = origin_by_name.get(base.casefold())
            if o:
                return o
            if self.wd_names:
                langs = self.wd_names.get(base.casefold())
                if langs:
                    return origin_from_wd_langs(langs)
            return ""

        before = {"cat": sum(1 for r in all_rows if r.get("pochodzenie"))}
        for _ in range(3):  # bazy mogą same dziedziczyć — kilka przebiegów
            changed = 0
            for r in all_rows:
                if r.get("pochodzenie"):
                    continue
                p1 = phase1.get(r["imie"], {})
                candidates = extract_base_names(p1.get("plain", ""))
                # redirect "Gosia" -> "Małgorzata": cel przekierowania też jest bazą
                pt = re.sub(r'\s*\(imi[ęe]\)$', '', p1.get("page_title", "") or "")
                if pt and pt != r["imie"] and pt not in candidates:
                    candidates.append(pt)
                for base in candidates:
                    if base.casefold() == r["imie"].casefold():
                        continue
                    o = base_origin(base)
                    if o:
                        r["pochodzenie"] = o
                        r["_zrodlo"] = "ODZ"
                        r["_zrodlo_baza"] = base
                        origin_by_name.setdefault(r["imie"].casefold(), o)
                        changed += 1
                        break
            if not changed:
                break
        log_stats(all_rows, "ODZIEDZICZONE", before)

    def _link_bazowe(self):
        phase1 = self.cache.load("phase1.json")
        if not phase1:
            return
        print("[3c] Powiązania imion (bazowe/pochodne) …")
        link_bazowe(self.meskie.rows + self.zenskie.rows, phase1)

    def _build_niebinarne(self):
        if self.args.skip_zaimki:
            return
        print("[3b] Pobieram imiona niebinarne z zaimki.pl …")
        raw = pobierz_zaimki(self.cache, self.session)
        self.niebinarne = przetworz_zaimki(raw)
        n_o = sum(1 for r in self.niebinarne if r.get("pochodzenie_opis"))
        n_z = sum(1 for r in self.niebinarne if r.get("znaczenie"))
        print(f"      {len(self.niebinarne)} imion niebinarnych "
              f"(z pochodzeniem: {n_o}, ze znaczeniem: {n_z})")

    def _print_final_stats(self):
        print("\n  Podsumowanie kategoryzacji:")
        log_stats(self.meskie.rows, "MĘSKIE")
        log_stats(self.zenskie.rows, "ŻEŃSKIE")
        all_rows = self.meskie.rows + self.zenskie.rows
        log_stats(all_rows, "ŁĄCZNIE")

    def _cleanup_rows(self):
        self.meskie.cleanup()
        self.zenskie.cleanup()

    def _save_all(self):
        print("[4/4] Zapisuje pliki …")
        self.meskie.save("dataset_meskie")
        self.zenskie.save("dataset_zenskie")
        if self.niebinarne:
            with open("dataset_niebinarne.json", "w", encoding="utf-8") as f:
                json.dump(self.niebinarne, f, ensure_ascii=False)
        self._zapisz_dane_js()
        n_op = sum(1 for r in self.meskie.rows + self.zenskie.rows if r.get("opis_html"))
        n_po = sum(1 for r in self.meskie.rows + self.zenskie.rows if r.get("pochodzenie"))
        print(f"GOTOWE. Imion z opisem: {n_op}, z pochodzeniem: {n_po}, "
              f"niebinarnych: {len(self.niebinarne)}.")
        print("Pliki: dataset_*.csv/.json oraz dane.js")
        if self.args.shutdown:
            print("WYŁĄCZAM…")
            os.system("shutdown -h now")

    def _zapisz_dane_js(self):
        """dane.js = rdzeń (bez opisów), opisy/<litera>.js = leniwe shardy.

        Opisy to ~40% danych, a użytkownik czyta ich kilkanaście na sesję —
        strona dociąga shard dopiero przy rozwinięciu wiersza.
        """
        import shutil
        shards = {}

        def bez_opisow(rows):
            out = []
            for r in rows:
                opis = r.get("opis_html")
                if opis:
                    shards.setdefault(shard_opisow(r["imie"]), {})[r["imie"]] = opis
                out.append({k: v for k, v in r.items() if k != "opis_html"})
            return out

        m = bez_opisow(self.meskie.rows)
        z = bez_opisow(self.zenskie.rows)
        with open("dane.js", "w", encoding="utf-8") as f:
            f.write("// Wygenerowane przez zbuduj_dataset.py — dane dla strony.\n")
            f.write("window.DANE_MESKIE = ")
            json.dump(m, f, ensure_ascii=False)
            f.write(";\n window.DANE_ZENSKIE = ")
            json.dump(z, f, ensure_ascii=False)
            f.write(";\n window.DANE_NIEBINARNE = ")
            json.dump(self.niebinarne, f, ensure_ascii=False)
            f.write(";\n")
        if os.path.isdir("opisy"):
            shutil.rmtree("opisy")
        os.makedirs("opisy", exist_ok=True)
        for k, mapa in sorted(shards.items()):
            with open(f"opisy/{k}.js", "w", encoding="utf-8") as f:
                f.write("window.NZ_OPISY=window.NZ_OPISY||{};window.NZ_OPISY[")
                f.write(json.dumps(k))
                f.write("]=")
                json.dump(mapa, f, ensure_ascii=False)
                f.write(";\n")
        print(f"      dane.js (rdzeń) + opisy/: {len(shards)} shardów")


if __name__ == "__main__":
    DatasetBuilder().run()
