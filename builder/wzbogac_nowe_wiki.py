#!/usr/bin/env python3
"""Szybkie wzbogacenie: tylko UK/RU/VI/RMY Wikipedia na istniejących JSON-ach."""

import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from zbuduj_dataset import (
    CacheManager, RateLimiter, WikiAPIClient, DatasetBuilder,
    API_UK, API_RU, API_VI, API_RMY, USER_AGENT, MAXLAG,
    EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN
)
import requests

def main():
    print("Wczytuję istniejące JSON-y...")
    with open("dataset_meskie.json", encoding="utf-8") as f:
        meskie = json.load(f)
    with open("dataset_zenskie.json", encoding="utf-8") as f:
        zenskie = json.load(f)

    m_before = sum(1 for r in meskie if r.get("pochodzenie"))
    z_before = sum(1 for r in zenskie if r.get("pochodzenie"))
    print(f"  Męskie: {len(meskie)} ({m_before} z pochodzeniem)")
    print(f"  Żeńskie: {len(zenskie)} ({z_before} z pochodzeniem)")

    # Ustaw klienta
    builder = DatasetBuilder()
    builder.cache = CacheManager()
    builder.session = requests.Session()
    builder.session.headers.update({"User-Agent": USER_AGENT})

    rows = meskie + zenskie
    # Tylko imiona z >=10 wystąpieniami
    need = [r for r in rows if not r.get("pochodzenie") and (r["wystapienia_pierwsze"]+r["wystapienia_drugie"])>=10]
    print(f"\n{len(need)} imion bez pochodzenia (>=10 wystąpień) do sprawdzenia\n")

    # UK
    print("=" * 60)
    print("UKRAIŃSKA WIKIPEDIA")
    print("=" * 60)
    builder.client_uk = WikiAPIClient(
        builder.session,
        RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN),
        base_url=API_UK, maxlag=MAXLAG
    )
    need_uk = [r for r in rows if not r.get("pochodzenie") and (r["wystapienia_pierwsze"]+r["wystapienia_drugie"])>=10]
    builder._apply_enrich_uk(need_uk)
    uk_hits = sum(1 for r in need_uk if r.get("pochodzenie"))
    print(f"  UK: +{uk_hits} nowych pochodzeń\n")

    # RU
    print("=" * 60)
    print("ROSYJSKA WIKIPEDIA")
    print("=" * 60)
    builder.client_ru = WikiAPIClient(
        builder.session,
        RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN),
        base_url=API_RU, maxlag=MAXLAG
    )
    need_ru = [r for r in rows if not r.get("pochodzenie") and (r["wystapienia_pierwsze"]+r["wystapienia_drugie"])>=10]
    builder._apply_enrich_ru(need_ru)
    ru_hits = sum(1 for r in need_ru if r.get("pochodzenie"))
    print(f"  RU: +{ru_hits} nowych pochodzeń\n")

    # VI
    print("=" * 60)
    print("WIETNAMSKA WIKIPEDIA")
    print("=" * 60)
    builder.client_vi = WikiAPIClient(
        builder.session,
        RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN),
        base_url=API_VI, maxlag=MAXLAG
    )
    need_vi = [r for r in rows if not r.get("pochodzenie") and (r["wystapienia_pierwsze"]+r["wystapienia_drugie"])>=10]
    builder._apply_enrich_vi(need_vi)
    vi_hits = sum(1 for r in need_vi if r.get("pochodzenie"))
    print(f"  VI: +{vi_hits} nowych pochodzeń\n")

    # RMY
    print("=" * 60)
    print("ROMSKA WIKIPEDIA")
    print("=" * 60)
    builder.client_rmy = WikiAPIClient(
        builder.session,
        RateLimiter(EN_RATE_LIMIT_REQ, EN_RATE_LIMIT_WIN),
        base_url=API_RMY, maxlag=MAXLAG
    )
    need_rmy = [r for r in rows if not r.get("pochodzenie") and (r["wystapienia_pierwsze"]+r["wystapienia_drugie"])>=10]
    builder._apply_enrich_rmy(need_rmy)
    rmy_hits = sum(1 for r in need_rmy if r.get("pochodzenie"))
    print(f"  RMY: +{rmy_hits} nowych pochodzeń\n")

    # Stats
    m_after = sum(1 for r in meskie if r.get("pochodzenie"))
    z_after = sum(1 for r in zenskie if r.get("pochodzenie"))

    print("=" * 60)
    print("PODSUMOWANIE")
    print("=" * 60)
    print(f"  Męskie: {m_before} -> {m_after} ({m_after/len(meskie)*100:.1f}%)")
    print(f"  Żeńskie: {z_before} -> {z_after} ({z_after/len(zenskie)*100:.1f}%)")
    print(f"  Łącznie nowych: +{m_after - m_before + z_after - z_before}")

    # Zapisz
    print("\nZapisuję zaktualizowane JSON-y...")
    with open("dataset_meskie.json", "w", encoding="utf-8") as f:
        json.dump(meskie, f, ensure_ascii=False)
    with open("dataset_zenskie.json", "w", encoding="utf-8") as f:
        json.dump(zenskie, f, ensure_ascii=False)
    print("GOTOWE")

if __name__ == "__main__":
    main()
