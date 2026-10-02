#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка FB2 из исходных текстовых файлов книги
«Кыргызский язык с нуля. Самоучитель для русскоговорящих».

Разметка исходников (своя, минимальная):
  # Заголовок      -> секция 1-го уровня
  ## Заголовок     -> секция 2-го уровня (вложена в текущую секцию 1-го уровня)
  ### Заголовок    -> <subtitle> внутри текущей секции
  #### Заголовок   -> абзац с полужирным текстом
  пустая строка    -> разделитель абзацев (каждая непустая строка = отдельный <p>)
  | a | b |        -> строка таблицы (первая строка таблицы = заголовок, строки |---| пропускаются)
  > текст          -> абзац внутри блока <cite>
  ---              -> <empty-line/>
  **текст**        -> <strong>, *текст* -> <emphasis>
  %%VOCAB_KY_RU%% / %%VOCAB_RU_KY%% -> автоматически собранные словари из vocab.tsv
"""
import os, re, sys, uuid, datetime, json
from xml.dom import minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "out")
BOOK_FILENAME = "Кыргызский язык с нуля. Самоучитель для русскоговорящих.fb2"

ORDER = [
    "00_front.txt",
    "01_intro_language.txt",
    "02_alphabet.txt",
    "03_course_head.txt",
    *[f"lesson_{i:02d}.txt" for i in range(1, 7)],
    "review_1.txt",
    *[f"lesson_{i:02d}.txt" for i in range(7, 13)],
    "review_2.txt",
    *[f"lesson_{i:02d}.txt" for i in range(13, 19)],
    "review_3.txt",
    *[f"lesson_{i:02d}.txt" for i in range(19, 25)],
    "review_4.txt",
    "final_test.txt",
    "phrases_100.txt",
    "keys_head.txt",
    "keys_alphabet.txt",
    *[f"keys_{i:02d}.txt" for i in range(1, 7)],
    "keys_review_1.txt",
    *[f"keys_{i:02d}.txt" for i in range(7, 13)],
    "keys_review_2.txt",
    *[f"keys_{i:02d}.txt" for i in range(13, 19)],
    "keys_review_3.txt",
    *[f"keys_{i:02d}.txt" for i in range(19, 25)],
    "keys_review_4.txt",
    "keys_final_test.txt",
    "dict_ky_ru.txt",
    "dict_ru_ky.txt",
    "appendices.txt",
    "sources.txt",
]

KY_ALPHABET = "АБВГДЕЁЖЗИЙКЛМНҢОӨПРСТУҮФХЦЧШЩЪЫЬЭЮЯ"
KY_ORDER = {ch: i for i, ch in enumerate(KY_ALPHABET)}
RU_ALPHABET = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
RU_ORDER = {ch: i for i, ch in enumerate(RU_ALPHABET)}

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

INLINE_STRONG = re.compile(r"\*\*(.+?)\*\*")
INLINE_EM = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")

def inline(s):
    s = esc(s)
    s = INLINE_STRONG.sub(r"<strong>\1</strong>", s)
    s = INLINE_EM.sub(r"<emphasis>\1</emphasis>", s)
    return s

def sort_key_ky(word):
    w = word.upper()
    return [KY_ORDER.get(ch, 100 + ord(ch)) for ch in w]

def sort_key_ru(word):
    w = word.upper().replace("Ё", "Е")
    return [RU_ORDER.get(ch, 100 + ord(ch)) for ch in w]

def load_vocab():
    path = os.path.join(SRC, "vocab.tsv")
    entries = []
    seen = set()
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln.strip() or ln.startswith("#"):
                continue
            parts = ln.split("\t")
            while len(parts) < 4:
                parts.append("")
            ky, ru, lesson, ru_head = [p.strip() for p in parts[:4]]
            if not ky or not ru:
                continue
            key = (ky.lower(), ru.lower())
            if key in seen:
                continue
            seen.add(key)
            entries.append({"ky": ky, "ru": ru, "lesson": lesson, "ru_head": ru_head})
    return entries

def head_for_sort(ky):
    # для сортировки убираем дефис основы глагола, скобки, лишние знаки
    w = re.sub(r"\(.*?\)", "", ky)
    w = w.replace("-", "").replace("!", "").replace("?", "").strip()
    return w

def vocab_ky_ru_lines(entries):
    es = sorted(entries, key=lambda e: (sort_key_ky(head_for_sort(e["ky"])), e["ky"]))
    lines = []
    letter = None
    for e in es:
        first = head_for_sort(e["ky"])[:1].upper()
        if first != letter:
            letter = first
            lines.append("### " + letter)
        lesson = f" (урок {e['lesson']})" if e["lesson"] and e["lesson"].isdigit() else (f" ({e['lesson']})" if e["lesson"] else "")
        lines.append(f"**{e['ky']}** — {e['ru']}{lesson}")
    return lines

def vocab_ru_ky_lines(entries):
    rev = {}
    for e in entries:
        head = e["ru_head"] or re.sub(r"\(.*?\)", "", e["ru"]).split(",")[0].split(";")[0].strip()
        head = head.strip(" .")
        if not head:
            continue
        rev.setdefault(head, [])
        if e["ky"] not in rev[head]:
            rev[head].append(e["ky"])
    heads = sorted(rev.keys(), key=lambda h: (sort_key_ru(h), h))
    lines = []
    letter = None
    for h in heads:
        first = h[:1].upper()
        if first != letter:
            letter = first
            lines.append("### " + letter)
        lines.append(f"**{h}** — " + ", ".join(rev[h]))
    return lines

class Section:
    def __init__(self, title, level):
        self.title = title
        self.level = level
        self.content = []   # list of xml strings (p, subtitle, table, cite, empty-line)
        self.children = []  # Section

    def to_xml(self, indent=1):
        pad = "  " * indent
        out = [f"{pad}<section>"]
        if self.title:
            out.append(f"{pad}  <title><p>{inline(self.title)}</p></title>")
        if self.children:
            if self.content:
                # прямое содержимое перед вложенными секциями допустимо только как annotation
                out.append(f"{pad}  <annotation>")
                for c in self.content:
                    if c.startswith("<subtitle>"):
                        c = "<p><strong>" + c[len("<subtitle>"):-len("</subtitle>")] + "</strong></p>"
                    out.append(f"{pad}    {c}")
                out.append(f"{pad}  </annotation>")
            for ch in self.children:
                out.append(ch.to_xml(indent + 1))
        else:
            if not self.content:
                out.append(f"{pad}  <empty-line/>")
            for c in self.content:
                out.append(f"{pad}  {c}")
        out.append(f"{pad}</section>")
        return "\n".join(out)

def parse_lines(lines, sections):
    """sections: list of top-level Section objects (level 1). Appends into it."""
    cur1 = sections[-1] if sections else None
    cur2 = None
    table_rows = None
    cite_rows = None

    def target():
        return cur2 if cur2 is not None else cur1

    def flush_table():
        nonlocal table_rows
        if table_rows:
            rows = []
            header_done = False
            for r in table_rows:
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                if all(re.fullmatch(r"-{2,}:?|:?-{2,}:?", c) for c in cells if c):
                    continue
                tag = "th" if not header_done else "td"
                header_done = True
                rows.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            target().content.append("<table>" + "".join(rows) + "</table>")
        table_rows = None

    def flush_cite():
        nonlocal cite_rows
        if cite_rows:
            target().content.append("<cite>" + "".join(f"<p>{inline(c)}</p>" for c in cite_rows) + "</cite>")
        cite_rows = None

    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("|"):
            flush_cite()
            if table_rows is None:
                table_rows = []
            table_rows.append(line)
            continue
        else:
            flush_table()
        if line.startswith("> "):
            if cite_rows is None:
                cite_rows = []
            cite_rows.append(line[2:])
            continue
        elif line.strip() == ">":
            if cite_rows is None:
                cite_rows = []
            continue
        else:
            flush_cite()
        if not line.strip():
            continue
        if line.startswith("#### "):
            target().content.append(f"<p><strong>{inline(line[5:].strip())}</strong></p>")
        elif line.startswith("### "):
            target().content.append(f"<subtitle>{inline(line[4:].strip())}</subtitle>")
        elif line.startswith("## "):
            cur2 = Section(line[3:].strip(), 2)
            cur1.children.append(cur2)
        elif line.startswith("# "):
            cur1 = Section(line[2:].strip(), 1)
            cur2 = None
            sections.append(cur1)
        elif line.strip() == "---":
            target().content.append("<empty-line/>")
        else:
            target().content.append(f"<p>{inline(line.strip())}</p>")
    flush_table()
    flush_cite()

def build():
    entries = load_vocab()
    sections = []
    annotation_lines = []
    global missing
    missing = []
    for name in ORDER:
        path = os.path.join(SRC, name)
        if not os.path.exists(path):
            print("ОТСУТСТВУЕТ ФАЙЛ (пропущен):", name, file=sys.stderr)
            missing.append(name)
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if "%%VOCAB_KY_RU%%" in text:
            text = text.replace("%%VOCAB_KY_RU%%", "\n".join(vocab_ky_ru_lines(entries)))
        if "%%VOCAB_RU_KY%%" in text:
            text = text.replace("%%VOCAB_RU_KY%%", "\n".join(vocab_ru_ky_lines(entries)))
        lines = text.split("\n")
        if name == "00_front.txt":
            # вытащить аннотацию для description
            m = re.search(r"^# Аннотация\n(.*?)(?=^# |\Z)", text, re.S | re.M)
            if m:
                annotation_lines = [l.strip() for l in m.group(1).split("\n") if l.strip()]
        parse_lines(lines, sections)

    body = ["<body>",
            "  <title><p>Кыргызский язык с нуля</p><p>Самоучитель для русскоговорящих</p></title>"]
    for s in sections:
        body.append(s.to_xml(1))
    body.append("</body>")

    ann = "\n".join(f"      <p>{inline(l)}</p>" for l in annotation_lines) or "      <p>Самоучитель кыргызского языка для русскоговорящих.</p>"
    today = datetime.date.today().isoformat()
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "kyrgyz-self-study-book-ru"))
    header = f"""<?xml version="1.0" encoding="UTF-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:l="http://www.w3.org/1999/xlink">
  <description>
    <title-info>
      <genre>sci_linguistic</genre>
      <genre>ref_guide</genre>
      <author>
        <nickname>Автор-составитель</nickname>
      </author>
      <book-title>Кыргызский язык с нуля. Самоучитель для русскоговорящих</book-title>
      <annotation>
{ann}
      </annotation>
      <keywords>кыргызский язык, киргизский язык, самоучитель, учебник, для начинающих, A1, A2, грамматика, разговорник</keywords>
      <date value="{today}">{today[:4]}</date>
      <lang>ru</lang>
      <src-lang>ru</src-lang>
    </title-info>
    <document-info>
      <author>
        <nickname>Автор-составитель</nickname>
      </author>
      <program-used>build_fb2.py (собственный конвертер)</program-used>
      <date value="{today}">{today}</date>
      <id>{doc_id}</id>
      <version>1.0</version>
    </document-info>
  </description>
"""
    xml = header + "\n".join(body) + "\n</FictionBook>\n"
    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, BOOK_FILENAME)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml)
    return out_path, xml, entries

def check(out_path, xml, entries):
    report = {}
    # 1. well-formedness
    try:
        dom = minidom.parseString(xml.encode("utf-8"))
        report["xml_well_formed"] = True
    except Exception as e:
        report["xml_well_formed"] = False
        report["xml_error"] = str(e)
        print("XML ERROR:", e)
        return report
    # 2. structure rules: section must not mix <p> and <section>
    def walk(node, path):
        bad = []
        for ch in node.childNodes:
            if ch.nodeType != ch.ELEMENT_NODE:
                continue
            if ch.tagName == "section":
                kids = [k.tagName for k in ch.childNodes if k.nodeType == k.ELEMENT_NODE]
                has_sec = "section" in kids
                has_text = any(k in ("p", "subtitle", "table", "cite", "empty-line") for k in kids)
                if has_sec and has_text:
                    bad.append(path + "/section")
                bad += walk(ch, path + "/section")
        return bad
    body = dom.getElementsByTagName("body")[0]
    report["mixed_sections"] = walk(body, "body")
    # 3. forbidden leftovers
    text_only = re.sub(r"<[^>]+>", "", xml)
    leftovers = {}
    for pat, label in [(r"\*\*", "**"), (r"(?<!\S)#{1,4} ", "# заголовок markdown"), (r"^\|", "| таблица markdown"),
                       (r"продолжение следует", "продолжение следует"), (r"здесь будет", "здесь будет"),
                       (r"и так далее", "и так далее"), (r"аналогично предыдущему", "аналогично предыдущему"),
                       (r"далее добавьте", "далее добавьте"), (r"\[\.\.\.\]", "[...]"), (r"TODO", "TODO"),
                       (r"\bи т\. д\.", "и т. д."), (r"и т\.д\.", "и т.д.")]:
        n = len(re.findall(pat, text_only, re.M | re.I))
        if n:
            leftovers[label] = n
    report["leftovers"] = leftovers
    mixed = sorted(set(w for w in re.findall(r"[A-Za-zА-Яа-яЁёҢңӨөҮү]+", text_only)
                       if re.search(r"[A-Za-z]", w) and re.search(r"[А-Яа-яЁёҢңӨөҮү]", w)))
    report["mixed_script_words"] = mixed[:50]
    # 4. required parts
    titles = re.findall(r"<title><p>(.*?)</p></title>", xml)
    titles_plain = [re.sub(r"<[^>]+>", "", t) for t in titles]
    report["lessons_found"] = sorted({int(m.group(1)) for t in titles_plain for m in [re.match(r"Урок (\d+)\.", t)] if m})
    report["reviews_found"] = [t for t in titles_plain if t.startswith("Повторение")]
    report["has_final_test"] = any(t.startswith("Итоговая проверочная работа") for t in titles_plain)
    report["has_keys"] = any(t.startswith("Ключи к упражнениям") for t in titles_plain)
    report["has_dict_ky_ru"] = any(t.startswith("Кыргызско-русский словарь") for t in titles_plain)
    report["has_dict_ru_ky"] = any(t.startswith("Русско-кыргызский словарь") for t in titles_plain)
    report["has_appendices"] = any(t.startswith("Приложени") for t in titles_plain)
    report["needs_check_marks"] = len(re.findall(r"ТРЕБУЕТ ПРОВЕРКИ", text_only))
    # 5. counts
    words = re.findall(r"[\w’'-]+", text_only)
    report["word_count"] = len(words)
    report["chars"] = len(text_only)
    report["exercise_count"] = len(re.findall(r"<p><strong>Упражнение \d+", xml))
    report["selfcheck_tasks"] = len(re.findall(r"<p><strong>Проверьте себя", xml))
    report["vocab_entries"] = len(entries)
    report["kyrgyz_letters_present"] = all(ch in xml for ch in "ңөүҢӨҮ")
    report["missing_files"] = missing
    report["file"] = out_path
    report["size_bytes"] = os.path.getsize(out_path)
    report["pages_estimate_1800_chars"] = round(len(text_only) / 1800)
    return report

if __name__ == "__main__":
    out_path, xml, entries = build()
    rep = check(out_path, xml, entries)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    with open(os.path.join(OUT, "build_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
