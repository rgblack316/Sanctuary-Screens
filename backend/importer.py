import csv
import io
import re

from books import canonical_for_import

REQUIRED = ["translation", "book", "chapter", "verse", "text"]
OPTIONAL = ["book_abbrev", "testament", "reference"]
CODE_RE = re.compile(r"^[A-Z0-9_\-]{1,16}$")
MAX_ERRORS = 50


def validate_csv(raw: bytes):
    """Staging pass: validate a translation CSV fully in memory. Returns (report, rows)."""
    errors, total = [], 0

    def err(row, msg):
        nonlocal total
        total += 1
        if len(errors) < MAX_ERRORS:
            errors.append({"row": row, "error": msg})

    report = {"ok": False, "translation_code": None, "row_count": 0, "book_count": 0,
              "chapter_count": 0, "columns": [], "errors": errors, "error_count": 0}
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        err(0, "File is not UTF-8 encoded text.")
        report["error_count"] = total
        return report, []

    reader = csv.DictReader(io.StringIO(text))
    headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    report["columns"] = headers
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        err(1, f"Missing required column(s): {', '.join(missing)}. Required: {', '.join(REQUIRED)}.")
        report["error_count"] = total
        return report, []
    reader.fieldnames = headers

    rows, codes, seen, chapters = [], set(), {}, set()
    for line, r in enumerate(reader, start=2):
        if None in r:
            err(line, "Row has more fields than the header.")
            continue
        vals = {k: (v or "").strip() for k, v in r.items()}
        code, book, ch, vs, txt = (vals.get("translation", "").upper(), vals.get("book", ""),
                                   vals.get("chapter", ""), vals.get("verse", ""), vals.get("text", ""))
        problems = []
        if not code:
            problems.append("translation is empty")
        if not book:
            problems.append("book is empty")
        if not ch.isdigit() or int(ch) < 1:
            problems.append(f"chapter '{ch}' is not a positive integer")
        if not vs.isdigit() or int(vs) < 1:
            problems.append(f"verse '{vs}' is not a positive integer")
        if not txt:
            problems.append("text is empty")
        if problems:
            err(line, "; ".join(problems))
            continue
        codes.add(code)
        name, norm, order = canonical_for_import(book)
        key = (norm, int(ch), int(vs))
        if key in seen:
            err(line, f"Duplicate verse {name} {ch}:{vs} (first seen on row {seen[key]}).")
            continue
        seen[key] = line
        chapters.add((norm, int(ch)))
        row = {"translation_code": code, "book_name": name, "book_normalized": norm, "book_order": order,
               "chapter": int(ch), "verse": int(vs), "text": txt, "reference_key": f"{norm}.{ch}.{vs}"}
        for opt in OPTIONAL:
            if vals.get(opt):
                row[opt] = vals[opt]
        rows.append(row)

    if len(codes) > 1:
        err(0, f"File contains multiple translation codes ({', '.join(sorted(codes))}). Import one translation per file.")
    code = next(iter(codes)) if len(codes) == 1 else None
    if code and not CODE_RE.match(code):
        err(0, f"Translation code '{code}' must be 1-16 letters, digits, '-' or '_'.")
    if not rows and total == 0:
        err(0, "File contains no verse rows.")

    report.update(ok=total == 0, translation_code=code, row_count=len(rows),
                  book_count=len({c[0] for c in chapters}), chapter_count=len(chapters), error_count=total)
    return report, rows
