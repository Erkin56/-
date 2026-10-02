#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Эвристическая проверка гармонии гласных в кыргызских словоформах исходников книги.
Выводит подозрительные словоформы: файл:строка:слово (ожидаемый вариант окончания).
Ложные срабатывания возможны (русские слова, заимствования, имена) — список предназначен для ручной проверки."""
import re, glob, os, sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
VOW = "аеэиоөуүыАЕЭИОӨУҮЫ"
BACK_A = set("аы"); FRONT_E = set("еэи"); O = set("о"); U = set("у"); OE = set("өү")

def last_vowel(stem):
    for ch in reversed(stem):
        if ch.lower() in "аеэиоөуүыёюя":
            c = ch.lower()
            if c == "ё": return "о"
            if c == "ю": return "у"
            if c == "я": return "а"
            return c
    return None

def low_expected(v):   # широкий гласный окончания
    if v in BACK_A or v in U: return "а"
    if v in FRONT_E: return "е"
    if v in O: return "о"
    if v in OE: return "ө"
    return None

def high_expected(v):  # узкий гласный окончания
    if v in BACK_A: return "ы"
    if v in FRONT_E: return "и"
    if v in O or v in U: return "у"
    if v in OE: return "ү"
    return None

# (regex суффикса с группами: согласный(ые), гласный, остаток; тип гласного)
RULES = [
    (re.compile(r"^(.+?)([дт])([аеоө])$"), "low", "loc"),            # -да
    (re.compile(r"^(.+?)([дтн])([аеоө])н$"), "low", "abl"),          # -дан
    (re.compile(r"^(.+?)([лдт])([аеоө])р$"), "low", "pl"),           # -лар
    (re.compile(r"^(.+?)([гк])([аеоө])н$"), "low", "gan"),           # -ган
    (re.compile(r"^(.+?)(м)([ыиуү])н$"), "high", "1sg"),             # -мын
    (re.compile(r"^(.+?)(с)([ыиуү])з$"), "high", "2pol"),            # -сыз
    (re.compile(r"^(.+?)(с)([ыиуү])ң$"), "high", "2sg"),             # -сың
    (re.compile(r"^(.+?)([дт])([ыиуү])(м|ң|к|ңыз|ңиз|ңуз|ңүз)$"), "high", "past"),  # -дым
    (re.compile(r"^(.+?)([дтн])([ыиуү])н$"), "high", "gen"),         # -нын
    (re.compile(r"^(.+?)([бп])([ыиуү])з$"), "high", "1pl"),          # -быз
]

RU_SKIP = set("""когда тогда всегда иногда никогда где везде нигде куда сюда туда откуда оттуда отсюда года годы люди
дети один одна одно они сами теми ними вами нами ими ту та те то это эти эта этот после ради года два дни""".split())

def check_token(tok):
    t = tok.lower()
    if len(t) < 4 or t in RU_SKIP: return None
    if not re.fullmatch(r"[а-яёңөү\-]+", t): return None
    for rx, typ, name in RULES:
        m = rx.match(t)
        if not m: continue
        stem = m.group(1)
        v = last_vowel(stem)
        if v is None: continue
        exp = low_expected(v) if typ == "low" else high_expected(v)
        got = m.group(3)
        if exp and got != exp:
            return f"{name}: ожидалось «{exp}», в слове «{tok}»"
    return None

def load_kyrgyz_prefixes():
    pref = set()
    path = os.path.join(SRC, "vocab.tsv")
    for ln in open(path, encoding="utf-8"):
        if ln.startswith("#") or "\t" not in ln: continue
        ky = ln.split("\t")[0]
        for tok in re.findall(r"[А-Яа-яЁёҢңӨөҮү]+", ky):
            if len(tok) >= 4: pref.add(tok[:4].lower())
    return pref

RU_SHAPES = re.compile(r"(йте|ите|ете|ьте|ость|ния|ние|ого|его|ему|ами|ями|ешь|ишь|ует|ают|яют|ция|ский|ская|ское|ный|ная|ное|ные|тся|ться|ых|ий|ой|ая|ую|ее|ие)$")

def is_kyrgyz(tok, pref, strong):
    t = tok.lower()
    if re.search(r"[ьъщц]", t): return False
    if re.search(r"[ңөү]", t): return True
    if RU_SHAPES.search(t): return False
    if strong: return True
    return t[:4] in pref

def main():
    pref = load_kyrgyz_prefixes()
    hits = []
    for p in sorted(glob.glob(os.path.join(SRC, "*.txt"))):
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            # проверяем только кыргызские фрагменты: жирный текст, цитаты, реплики диалогов, строки с ң/ө/ү
            strong = line.startswith("> ") or bool(re.match(r"^\*\*[А-ЯЁ][\w ]+:\*\*", line))
            segs = re.findall(r"\*\*(.+?)\*\*", line)
            if strong: segs.append(line)
            seen = set()
            for seg in segs:
                for tok in re.findall(r"[А-Яа-яЁёҢңӨөҮү]+", seg):
                    if tok in seen: continue
                    seen.add(tok)
                    if not is_kyrgyz(tok, pref, strong): continue
                    r = check_token(tok)
                    if r: hits.append(f"{os.path.basename(p)}:{i}: {r}")
    for h in hits: print(h)
    print(f"ВСЕГО ПОДОЗРИТЕЛЬНЫХ: {len(hits)}", file=sys.stderr)

if __name__ == "__main__":
    main()
