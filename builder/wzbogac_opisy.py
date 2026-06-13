#!/usr/bin/env python3
"""
Wzbogacanie datasetu Nazwozbioru:
  Faza 1 – kategorie en.Wiktionary → pochodzenie (WIKT-CAT)
  Faza 2 – lokalne warianty pisowni → dziedziczenie pochodzenia (WAR)
  Faza 3 – tłumaczenie EN wiki extractów → opisy + detekcja pochodzenia (MinT)
  Faza 4 – świeże extracty UK/RU/VI wiki + tłumaczenie → opisy + pochodzenie

Wyniki zapisywane do dataset_meskie.json / dataset_zenskie.json.
Cache w .cache_wiki/ (wznawialne).
"""

import json, os, sys, re, time, hashlib, unicodedata, collections
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

sys.path.insert(0, os.path.dirname(__file__))
from zbuduj_dataset import (
    CacheManager, RateLimiter, WikiAPIClient, wykryj_pochodzenie,
    EN_CATEGORY_ORIGINS, shard_opisow,
    API_UK, API_RU, API_VI, USER_AGENT, MAXLAG,
    EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN, BATCH_SIZE,
)

MINT_URL = "https://translate.wmcloud.org/api/translate"
MINT_WORKERS = 4
MINT_SLEEP = 0.15   # per-worker

# ---- Wiktionary term → origin slug map -----------------------------------
# Exact matching for category text extracted from "terms derived from X"
# patterns.  Broader matches fall through to EN_CATEGORY_ORIGINS substring.
WIKT_TERM_MAP = {
    "Ancient Greek":        "greckie",
    "Koine Greek":          "greckie",
    "Latin":                "lacinskie",
    "Late Latin":           "lacinskie",
    "Medieval Latin":       "lacinskie",
    "Hebrew":               "hebrajskie",
    "Biblical Hebrew":      "hebrajskie",
    "Germanic":             "germanskie",
    "German":               "germanskie",
    "Old High German":      "germanskie",
    "Proto-Germanic":       "germanskie",
    "Old Norse":            "skandynawskie",
    "Old English":          "anglosaskie",
    "English":              "angielskie",
    "Celtic":               "celtyckie",
    "Scottish Gaelic":      "celtyckie",
    "Arabic":               "arabskie",
    "Persian":              "perskie",
    "Turkish":              "tureckie",
    "Proto-Slavic":         "slowianskie",
    "Old Church Slavonic":  "slowianskie",
    "Slavic":               "slowianskie",
    "Old Czech":            "slowianskie",
    "Czech":                "slowianskie",
    "Russian":              "rosyjskie",
    "Ukrainian":            "ukrainskie",
    "French":               "francuskie",
    "Italian":              "wloskie",
    "Spanish":              "hiszpanskie",
    "Hungarian":            "wegierskie",
    "Finnish":              "finskie",
    "Estonian":             "finskie",
    "Sanskrit":             "sanskryckie",
    "Japanese":             "japonskie",
    "Chinese":              "chinskie",
    "Aramaic":              "aramejskie",
    "Armenian":             "ormianskie",
    "Georgian":             "gruzinskie",
    "Egyptian":             "egipskie",
    "Etruscan":             "etruskie",
    "Lithuanian":           "litewskie",
}

_WIKT_PATTERNS = [
    re.compile(r'terms (?:derived|borrowed|inherited) from (.+)$', re.I),
    re.compile(r'given names from (.+)$', re.I),
]


def _wikt_cat_to_origin(categories):
    """Extract origin slug from a list of en.Wiktionary category titles.
    Prefers Polish-language categories first, then falls back to others."""
    polish = [c for c in categories if c.lower().startswith("polish")]
    other = [c for c in categories if not c.lower().startswith("polish")]
    for cat in polish + other:
        for pat in _WIKT_PATTERNS:
            m = pat.search(cat)
            if not m:
                continue
            term = m.group(1).strip()
            if term in WIKT_TERM_MAP:
                return WIKT_TERM_MAP[term]
            low = term.lower()
            for kw, origin in EN_CATEGORY_ORIGINS:
                if kw in low:
                    return origin
    return ""


# ---- helpers ------------------------------------------------------------

def tot(r):
    return r["wystapienia_pierwsze"] + r["wystapienia_drugie"]


def fold(s):
    s = s.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def trim_extract(text):
    """Przytnij extract do 1-2 zdań, max 450 znaków.  Usuwa IPA/wymowę."""
    text = re.sub(r'\([^)]*(?:pronounced|IPA|listen|\[ˈ)[^)]*\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    sents = re.split(r'(?<=[.!?])\s+', text)
    result = " ".join(sents[:2]).strip()
    if len(result) > 450:
        result = result[:447].rsplit(' ', 1)[0] + "…"
    return result


def html_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nf(n):
    return f"{n:,}".replace(",", "\u00a0")


# =========================================================================
# Faza 1: Wiktionary categories → pochodzenie
# =========================================================================

WIKT_BATCH = 20

def faza_wikt_categories(cache_mgr, session, rows_without_origin):
    """Batch-query en.Wiktionary categories for each name in the dataset.
    Parse category titles like 'Polish terms derived from Latin' to extract
    the origin language, map it to a slug via WIKT_TERM_MAP + EN_CATEGORY_ORIGINS."""
    print("=" * 60)
    print("FAZA 1: Kategorie en.Wiktionary → pochodzenie")
    print("=" * 60)

    cat_cache = cache_mgr.load("wikt_categories.json") or {}
    api = "https://en.wiktionary.org/w/api.php"
    rl = RateLimiter(95, 60)

    need = [r for r in rows_without_origin if r["imie"] not in cat_cache]
    print(f"  Imion bez pochodzenia: {len(rows_without_origin)} "
          f"(w cache: {len(rows_without_origin) - len(need)}, "
          f"do pobrania: {len(need)})")

    if need:
        for i in range(0, len(need), WIKT_BATCH):
            batch = need[i:i + WIKT_BATCH]
            names = [r["imie"] for r in batch]
            rl.wait_if_needed()
            try:
                resp = session.get(api, params={
                    "action": "query", "format": "json",
                    "formatversion": 2,
                    "prop": "categories", "clshow": "!hidden",
                    "cllimit": "max", "redirects": 1,
                    "titles": "|".join(names),
                }, timeout=30)
                data = resp.json()
            except Exception as e:
                print(f"    błąd batch {i // WIKT_BATCH}: {e}")
                for r in batch:
                    cat_cache.setdefault(r["imie"], [])
                continue

            for pg in data.get("query", {}).get("pages", []):
                title = pg.get("title", "")
                cats = [c["title"] for c in pg.get("categories", [])]
                cat_cache[title] = cats
            for r in batch:
                cat_cache.setdefault(r["imie"], [])

            if (i // WIKT_BATCH) % 10 == 0:
                cache_mgr.save("wikt_categories.json", cat_cache)
                done = min(i + WIKT_BATCH, len(need))
                print(f"    ...{done}/{len(need)}")

        cache_mgr.save("wikt_categories.json", cat_cache)

    applied = 0
    for r in rows_without_origin:
        cats = cat_cache.get(r["imie"], [])
        origin = _wikt_cat_to_origin(cats)
        if origin:
            r["pochodzenie"] = origin
            r["zrodlo"] = "WIKT-CAT"
            applied += 1

    print(f"  ✓ Wiktionary categories: +{applied} nowych pochodzeń\n")
    return applied


# =========================================================================
# Faza 2: Warianty lokalne → dziedziczenie pochodzenia
# =========================================================================

def faza_warianty(all_rows):
    """Dziedziczenie pochodzenia po znanych imionach przez warianty pisowni."""
    print("=" * 60)
    print("FAZA 2: Warianty lokalne → pochodzenie")
    print("=" * 60)

    known = {}
    for r in all_rows:
        if r.get("pochodzenie"):
            known.setdefault(fold(r["imie"]), (r["pochodzenie"], r["imie"]))

    def variants(name):
        f = fold(name)
        out = {f}
        out.add(re.sub(r'(.)\1', r'\1', f))            # Anna→Ana
        for src, dst in [
            ("y", "i"), ("i", "y"), ("v", "w"), ("w", "v"),
            ("x", "ks"), ("ks", "x"), ("ph", "f"), ("f", "ph"),
            ("th", "t"), ("c", "k"), ("k", "c"),
            ("sz", "sh"), ("sh", "sz"), ("cz", "ch"), ("ch", "cz"),
            ("ij", "i"), ("ii", "i"), ("iya", "ia"), ("iy", "i"),
        ]:
            out.add(f.replace(src, dst))
        # trailing vowel
        if len(f) > 3 and f[-1] in "aeio":
            out.add(f[:-1])
        if len(f) > 3 and f[-1] not in "aeiouy":
            for v in "aei":
                out.add(f + v)
        return out - {f}

    applied = 0
    for _pass in range(3):
        changed = 0
        for r in all_rows:
            if r.get("pochodzenie"):
                continue
            if len(r["imie"]) < 3:
                continue
            for v in variants(r["imie"]):
                if v in known:
                    origin, base = known[v]
                    r["pochodzenie"] = origin
                    r["zrodlo"] = "WAR"
                    r["zrodlo_baza"] = base
                    known.setdefault(fold(r["imie"]), (origin, r["imie"]))
                    changed += 1
                    applied += 1
                    break
            if not changed:
                break
        if not changed:
            break

    print(f"  ✓ Warianty lokalne: +{applied} nowych pochodzeń\n")
    return applied


# =========================================================================
# Faza 3: Tłumaczenia EN wiki extractów → opisy + pochodzenie
# =========================================================================

def faza_tlumaczenia_en(cache_mgr, session, all_rows):
    """Tłumaczy EN Wikipedia extracty na PL przez MinT."""
    print("=" * 60)
    print("FAZA 3: Tłumaczenia EN→PL (MinT)")
    print("=" * 60)

    en_cache = cache_mgr.load("phase_en.json") or {}
    tl_cache = cache_mgr.load("tlumaczenia_en.json") or {}

    # Kandydaci: brak opisu, EN is_name z extractem
    candidates = []
    for r in all_rows:
        if r.get("opis_html"):
            continue
        en = en_cache.get(r["imie"], {})
        if en.get("is_name") and en.get("extract") and len(en["extract"]) >= 30:
            trimmed = trim_extract(en["extract"])
            if len(trimmed) >= 20:
                candidates.append((r, trimmed))

    already = sum(1 for _, t in candidates
                  if hashlib.md5(("en:" + t).encode()).hexdigest() in tl_cache)
    print(f"  Kandydatów: {len(candidates)} ({already} już w cache tłumaczeń)")

    if not candidates:
        print("  Nic do tłumaczenia.\n")
        return 0, 0

    save_lock = __import__("threading").Lock()
    counter = {"opis": 0, "origin": 0, "done": 0, "errs": 0}

    def translate_one(args):
        r, trimmed = args
        key = hashlib.md5(("en:" + trimmed).encode()).hexdigest()
        with save_lock:
            cached = tl_cache.get(key)
        if cached:
            translated = cached
        else:
            time.sleep(MINT_SLEEP)
            try:
                resp = session.post(MINT_URL, json={
                    "source_language": "en", "target_language": "pl",
                    "format": "text", "content": trimmed,
                }, timeout=90)
                resp.raise_for_status()
                translated = resp.json().get("translation", "")
            except Exception as e:
                counter["errs"] += 1
                return
            with save_lock:
                tl_cache[key] = translated

        if not translated or len(translated) < 15:
            return

        r["opis_html"] = f"<p>{html_escape(translated)}</p>"
        r["opis_zrodlo"] = "EN"
        counter["opis"] += 1

        if not r.get("pochodzenie"):
            origin = wykryj_pochodzenie(translated)
            if origin:
                r["pochodzenie"] = origin
                r["zrodlo"] = "EN-TL"
                counter["origin"] += 1

    # Concurrent MinT
    with ThreadPoolExecutor(max_workers=MINT_WORKERS) as pool:
        futures = {pool.submit(translate_one, c): i for i, c in enumerate(candidates)}
        for future in as_completed(futures):
            idx = futures[future]
            counter["done"] += 1
            try:
                future.result()
            except Exception:
                counter["errs"] += 1
            d = counter["done"]
            if d % 200 == 0 or d == len(candidates):
                with save_lock:
                    cache_mgr.save("tlumaczenia_en.json", tl_cache)
                print(f"    ...{d}/{len(candidates)}  "
                      f"opisy:+{counter['opis']}  poch:+{counter['origin']}  "
                      f"err:{counter['errs']}")

    cache_mgr.save("tlumaczenia_en.json", tl_cache)
    print(f"  ✓ Tłumaczenia EN: +{counter['opis']} opisów, "
          f"+{counter['origin']} pochodzeń\n")
    return counter["opis"], counter["origin"]


# =========================================================================
# Faza 4: Świeże extracty UK/RU/VI + tłumaczenie
# =========================================================================

def faza_foreign_wikis(cache_mgr, session, all_rows):
    """Pobiera extracty z UK/RU/VI Wikipedia, tłumaczy na PL."""
    print("=" * 60)
    print("FAZA 4: UK/RU/VI Wikipedia + tłumaczenie MinT")
    print("=" * 60)

    tl_cache = cache_mgr.load("tlumaczenia_foreign.json") or {}
    total_opis = 0
    total_origin = 0

    configs = [
        ("uk", API_UK, "phase_uk_opisy.json"),
        ("ru", API_RU, "phase_ru_opisy.json"),
        ("vi", API_VI, "phase_vi_opisy.json"),
    ]

    for lang, api_url, cache_name in configs:
        wiki_cache = cache_mgr.load(cache_name) or {}

        # Imiona bez opisu, ≥10 wystąpień, nie sprawdzone jeszcze
        need = [r for r in all_rows
                if not r.get("opis_html")
                and r["imie"] not in wiki_cache
                and tot(r) >= 10]

        print(f"\n  {lang.upper()} Wikipedia: {len(need)} imion do sprawdzenia "
              f"(w cache: {len(wiki_cache)})")
        if not need:
            continue

        client = WikiAPIClient(
            session,
            RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN),
            base_url=api_url, maxlag=MAXLAG,
        )

        # Batch fetch extractów
        for i in range(0, len(need), BATCH_SIZE):
            batch = need[i:i + BATCH_SIZE]
            batch_names = [r["imie"] for r in batch]
            params = {
                "action": "query", "format": "json", "formatversion": 2,
                "prop": "extracts", "exintro": 1, "explaintext": 1,
                "exlimit": "max", "redirects": 1,
                "titles": "|".join(batch_names),
            }
            try:
                data = client.get(params)
            except Exception as e:
                print(f"    błąd {lang.upper()} batch: {e}")
                for n in batch_names:
                    wiki_cache[n] = ""
                continue
            pages = data.get("query", {}).get("pages", [])
            norm = {}
            for rd in data.get("query", {}).get("redirects", []):
                norm[rd["from"]] = rd["to"]
            for nm in data.get("query", {}).get("normalized", []):
                norm[nm["from"]] = nm["to"]
            pg_by_title = {pg.get("title", ""): pg for pg in pages}
            for n in batch_names:
                t = norm.get(n, n)
                pg = pg_by_title.get(t) or pg_by_title.get(n) or {}
                wiki_cache[n] = pg.get("extract", "") or ""

            if (i // BATCH_SIZE) % 20 == 0:
                cache_mgr.save(cache_name, wiki_cache)
                done = min(i + BATCH_SIZE, len(need))
                print(f"    ...{done}/{len(need)}")

        cache_mgr.save(cache_name, wiki_cache)

        # Tłumacz extracty dla imion nadal bez opisu
        to_translate = []
        for r in all_rows:
            if r.get("opis_html"):
                continue
            ext = wiki_cache.get(r["imie"], "")
            if ext and len(ext) >= 30:
                trimmed = trim_extract(ext)
                if len(trimmed) >= 20:
                    to_translate.append((r, trimmed))

        print(f"  {lang.upper()}→PL tłumaczenie: {len(to_translate)} kandydatów")
        opis_n = 0
        origin_n = 0

        for j, (r, trimmed) in enumerate(to_translate):
            key = hashlib.md5((lang + ":" + trimmed).encode()).hexdigest()
            if key in tl_cache:
                translated = tl_cache[key]
            else:
                try:
                    resp = session.post(MINT_URL, json={
                        "source_language": lang, "target_language": "pl",
                        "format": "text", "content": trimmed,
                    }, timeout=90)
                    resp.raise_for_status()
                    translated = resp.json().get("translation", "")
                    tl_cache[key] = translated
                except Exception as e:
                    print(f"    MinT {lang}→pl error: {e}")
                    continue
                time.sleep(MINT_SLEEP)

            if translated and len(translated) >= 15:
                r["opis_html"] = f"<p>{html_escape(translated)}</p>"
                r["opis_zrodlo"] = lang.upper()
                opis_n += 1
                if not r.get("pochodzenie"):
                    origin = wykryj_pochodzenie(translated)
                    if origin:
                        r["pochodzenie"] = origin
                        r["zrodlo"] = f"{lang.upper()}-TL"
                        origin_n += 1

            if (j + 1) % 100 == 0:
                cache_mgr.save("tlumaczenia_foreign.json", tl_cache)
                print(f"    ...{j+1}/{len(to_translate)}")

        cache_mgr.save("tlumaczenia_foreign.json", tl_cache)
        total_opis += opis_n
        total_origin += origin_n
        print(f"  ✓ {lang.upper()}: +{opis_n} opisów, +{origin_n} pochodzeń")

    print(f"\n  ✓ Foreign wikis łącznie: +{total_opis} opisów, "
          f"+{total_origin} pochodzeń\n")
    return total_opis, total_origin


# =========================================================================
# Regeneracja dane.js + opisy/ z mapą źródeł
# =========================================================================

def regeneruj_dane_js(meskie, zenskie, niebinarne_path="dataset_niebinarne.json"):
    """Regeneruje dane.js i opisy/*.js z mapą źródeł NZ_OPISY_SRC."""
    import shutil

    print("=" * 60)
    print("REGENERACJA dane.js + opisy/")
    print("=" * 60)

    niebinarne = []
    if os.path.exists(niebinarne_path):
        with open(niebinarne_path, encoding="utf-8") as f:
            niebinarne = json.load(f)

    shards = {}    # litera → {imie: opis_html}
    shard_src = {} # litera → {imie: zrodlo_code}

    def bez_opisow(rows):
        out = []
        for r in rows:
            opis = r.get("opis_html")
            opis_src = r.get("opis_zrodlo", "")
            if opis:
                k = shard_opisow(r["imie"])
                shards.setdefault(k, {})[r["imie"]] = opis
                if opis_src:
                    shard_src.setdefault(k, {})[r["imie"]] = opis_src
            # Usuń pola wewnętrzne z eksportu
            out.append({k: v for k, v in r.items()
                        if k not in ("opis_html", "opis_zrodlo")})
        return out

    m = bez_opisow(meskie)
    z = bez_opisow(zenskie)

    with open("dane.js", "w", encoding="utf-8") as f:
        f.write("// Wygenerowane przez wzbogac_opisy.py — dane dla strony.\n")
        f.write("window.DANE_MESKIE = ")
        json.dump(m, f, ensure_ascii=False)
        f.write(";\n window.DANE_ZENSKIE = ")
        json.dump(z, f, ensure_ascii=False)
        f.write(";\n window.DANE_NIEBINARNE = ")
        json.dump(niebinarne, f, ensure_ascii=False)
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
            # Dopisz mapę źródeł (tylko jeśli są wpisy spoza PL)
            src = shard_src.get(k, {})
            if src:
                f.write("window.NZ_OPISY_SRC=window.NZ_OPISY_SRC||{};window.NZ_OPISY_SRC[")
                f.write(json.dumps(k))
                f.write("]=")
                json.dump(src, f, ensure_ascii=False)
                f.write(";\n")

    print(f"  dane.js + opisy/: {len(shards)} shardów "
          f"({sum(len(v) for v in shards.values())} opisów, "
          f"{sum(len(v) for v in shard_src.values())} z oznaczonym źródłem)\n")


# =========================================================================
# main
# =========================================================================

def main():
    cache_mgr = CacheManager()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    print("Wczytuję datasety…")
    with open("dataset_meskie.json", encoding="utf-8") as f:
        meskie = json.load(f)
    with open("dataset_zenskie.json", encoding="utf-8") as f:
        zenskie = json.load(f)
    all_rows = meskie + zenskie
    print(f"  {len(meskie)} męskich + {len(zenskie)} żeńskich = {len(all_rows)}\n")

    # Snapshot PRZED
    snap_before = {
        "pochodzenie": sum(1 for r in all_rows if r.get("pochodzenie")),
        "opis": sum(1 for r in all_rows if r.get("opis_html")),
    }
    for p in [10, 100, 1000]:
        sub = [r for r in all_rows if tot(r) >= p]
        snap_before[f"poch_{p}"] = sum(1 for r in sub if r.get("pochodzenie"))
        snap_before[f"opis_{p}"] = sum(1 for r in sub if r.get("opis_html"))
        snap_before[f"n_{p}"] = len(sub)
    snap_before["n"] = len(all_rows)

    # Fazy
    need_origin = [r for r in all_rows if not r.get("pochodzenie")]
    faza_wikt_categories(cache_mgr, session, need_origin)
    faza_warianty(all_rows)
    faza_tlumaczenia_en(cache_mgr, session, all_rows)
    faza_foreign_wikis(cache_mgr, session, all_rows)

    # Zapisz JSONy
    print("=" * 60)
    print("ZAPISYWANIE DATASETÓW")
    print("=" * 60)
    with open("dataset_meskie.json", "w", encoding="utf-8") as f:
        json.dump(meskie, f, ensure_ascii=False)
    with open("dataset_zenskie.json", "w", encoding="utf-8") as f:
        json.dump(zenskie, f, ensure_ascii=False)
    print("  ✓ dataset_meskie.json + dataset_zenskie.json\n")

    # Regeneruj dane.js + opisy/
    regeneruj_dane_js(meskie, zenskie)

    # ---- Statystyki PO vs PRZED ----
    snap_after = {
        "pochodzenie": sum(1 for r in all_rows if r.get("pochodzenie")),
        "opis": sum(1 for r in all_rows if r.get("opis_html")),
    }
    for p in [10, 100, 1000]:
        sub = [r for r in all_rows if tot(r) >= p]
        snap_after[f"poch_{p}"] = sum(1 for r in sub if r.get("pochodzenie"))
        snap_after[f"opis_{p}"] = sum(1 for r in sub if r.get("opis_html"))
        snap_after[f"n_{p}"] = len(sub)
    snap_after["n"] = len(all_rows)

    zrodla = collections.Counter(r.get("zrodlo", "") for r in all_rows if r.get("pochodzenie"))
    opis_src = collections.Counter(r.get("opis_zrodlo", "PL") for r in all_rows if r.get("opis_html"))

    print("=" * 60)
    print("PODSUMOWANIE: PRZED → PO")
    print("=" * 60)
    fmt = "  {:30s} {:>8s} → {:>8s}  ({:+d})"
    n = snap_before["n"]
    print(fmt.format("Pochodzenie (wszystkie)",
          f"{snap_before['pochodzenie']}/{n}",
          f"{snap_after['pochodzenie']}/{n}",
          snap_after['pochodzenie'] - snap_before['pochodzenie']))
    print(fmt.format("Opis (wszystkie)",
          f"{snap_before['opis']}/{n}",
          f"{snap_after['opis']}/{n}",
          snap_after['opis'] - snap_before['opis']))
    for p in [10, 100, 1000]:
        nn = snap_before[f"n_{p}"]
        print(fmt.format(f"Pochodzenie (≥{p} wyst.)",
              f"{snap_before[f'poch_{p}']}/{nn}",
              f"{snap_after[f'poch_{p}']}/{nn}",
              snap_after[f"poch_{p}"] - snap_before[f"poch_{p}"]))
        print(fmt.format(f"Opis (≥{p} wyst.)",
              f"{snap_before[f'opis_{p}']}/{nn}",
              f"{snap_after[f'opis_{p}']}/{nn}",
              snap_after[f"opis_{p}"] - snap_before[f"opis_{p}"]))

    print(f"\n  Źródła pochodzenia: {dict(zrodla)}")
    print(f"  Źródła opisów: {dict(opis_src)}")
    print("\nGOTOWE.")


if __name__ == "__main__":
    main()
