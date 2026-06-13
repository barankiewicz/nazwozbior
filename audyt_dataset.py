#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audyt_dataset.py — kontrola jakości zbudowanego datasetu.

Reguły (każda flaguje wiersze do raportu, sortowane po popularności):
  R1  opis = statystyki PESEL ("osób w Polsce", "miejsce wśród", dużo cyfr)
  R2  opis = lista imienin (≥3 nazwy miesięcy / zaczyna się od "imieniny")
  R3  artykuł nie jest o imieniu (kategorie z cache fazy 1: państwo, rzeka,
      film…), a mimo to wiersz ma opis lub pochodzenie z PL Wikipedii
  R4  opis podejrzanie krótki (<60 znaków)
  R5  opis nie wspomina o imieniu ani o samym imieniu

Użycie: python3 audyt_dataset.py [--raport AUDYT.md] [--limit-przyklady 15]
"""
import json, re, html, argparse, os, sys

from zbuduj_dataset import is_name_article, MIESIACE_DOPELNIACZ

RE_TAG = re.compile(r'<[^>]+>')

def txt(opis_html):
    return html.unescape(RE_TAG.sub('', opis_html or '')).strip()

def pop(r):
    return (r.get('wystapienia_pierwsze', 0) or 0) + (r.get('wystapienia_drugie', 0) or 0)

def audytuj(rows, phase1):
    flagi = {k: [] for k in ('R1', 'R2', 'R3', 'R4', 'R5')}
    for r in rows:
        o = txt(r.get('opis_html', ''))
        low = o.lower()
        if o:
            digits = sum(c.isdigit() for c in o)
            if ('osób w polsce' in low or 'miejsce wśród' in low
                    or 'rejestrze pesel' in low or digits > len(o) * 0.15):
                flagi['R1'].append(r)
            months = sum(1 for mn in MIESIACE_DOPELNIACZ if mn in low)
            if months >= 3 or low.startswith('imieniny'):
                flagi['R2'].append(r)
            if len(o) < 60:
                flagi['R4'].append(r)
            imie_low = r['imie'].lower()
            if ('imi' not in low and 'form' not in low and 'zdrobnien' not in low
                    and imie_low not in low):
                flagi['R5'].append(r)
        p1 = phase1.get(r['imie'], {})
        if p1.get('exists') and is_name_article(p1.get('cats', [])) is False:
            if r.get('opis_html') or r.get('_zrodlo') == 'PL':
                flagi['R3'].append(r)
    return flagi

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raport', default='AUDYT.md')
    ap.add_argument('--limit-przyklady', type=int, default=15)
    args = ap.parse_args()

    m = json.load(open('dataset_meskie.json', encoding='utf-8'))
    z = json.load(open('dataset_zenskie.json', encoding='utf-8'))
    rows = m + z
    phase1 = {}
    if os.path.exists('.cache_wiki/phase1.json'):
        phase1 = json.load(open('.cache_wiki/phase1.json', encoding='utf-8'))

    flagi = audytuj(rows, phase1)
    opisy = OPIS = ['R1', 'R2', 'R4', 'R5']
    n_opis = sum(1 for r in rows if r.get('opis_html'))

    out = ['# Audyt datasetu', '']
    nazwy = {
        'R1': 'opis to statystyki PESEL',
        'R2': 'opis to lista imienin',
        'R3': 'artykuł nie o imieniu (złe dopasowanie)',
        'R4': 'opis podejrzanie krótki',
        'R5': 'opis bez wzmianki o imieniu',
    }
    print(f"Wierszy: {len(rows)}, z opisem: {n_opis}\n")
    for k, lst in flagi.items():
        lst.sort(key=lambda r: -pop(r))
        base = n_opis if k != 'R3' else len(rows)
        print(f"{k} {nazwy[k]}: {len(lst)} ({len(lst)/max(base,1)*100:.1f}%)")
        out.append(f"## {k}: {nazwy[k]} — {len(lst)}")
        out.append('')
        for r in lst[:args.limit_przyklady]:
            out.append(f"- **{r['imie']}** ({pop(r):,} os.): {txt(r.get('opis_html',''))[:140]}")
        out.append('')
    with open(args.raport, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"\nRaport: {args.raport}")

if __name__ == '__main__':
    main()
