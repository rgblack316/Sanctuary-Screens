import re

_HEAD = re.compile(
    r"^\s*((?:[1-3]\s*|(?:iii|ii|i|first|second|third)\s+)?[a-z][a-z .']*?)\s*(\d[\d\s:.,;\-\u2013\u2014]*)\s*$",
    re.I,
)
HELP = "Use a format like Romans 6:23, John 3:16-18, Psalm 23 or John 3:16-4:2."


class RefError(ValueError):
    pass


def _point(s: str):
    if s.count(":") > 1:
        raise RefError(f"Invalid reference part '{s}'. {HELP}")
    if ":" in s:
        c, v = s.split(":")
        if not (c.isdigit() and v.isdigit()):
            raise RefError(f"Invalid reference part '{s}'. {HELP}")
        return int(c), int(v), True
    if not s.isdigit():
        raise RefError(f"Invalid reference part '{s}'. {HELP}")
    return int(s), None, False


def parse_reference(text: str):
    """Parse a reference into (book_text, spans). Span = (start_ch, start_v|None, end_ch, end_v|None)."""
    m = _HEAD.match(text or "")
    if not m:
        raise RefError(f"Could not read that reference. {HELP}")
    book = m.group(1).strip()
    rest = re.sub(r"[\u2013\u2014]", "-", m.group(2)).replace(".", ":").replace(" ", "")
    spans, cur, verse_ctx = [], None, False
    for part in re.split(r"[,;]", rest):
        if not part:
            continue
        bits = part.split("-")
        if len(bits) > 2 or not all(bits):
            raise RefError(f"Invalid range '{part}'. {HELP}")
        a = _point(bits[0])
        if a[2]:
            sc, sv = a[0], a[1]
            verse_ctx = True
        elif verse_ctx:
            sc, sv = cur, a[0]
        else:
            sc, sv = a[0], None
        if len(bits) == 1:
            ec, ev = sc, sv
        else:
            b = _point(bits[1])
            if b[2]:
                ec, ev = b[0], b[1]
                sv = 1 if sv is None else sv
                verse_ctx = True
            elif sv is None:
                ec, ev = b[0], None
            else:
                ec, ev = sc, b[0]
        cur = ec
        if min(x for x in (sc, sv, ec, ev) if x is not None) < 1:
            raise RefError("Chapter and verse numbers start at 1.")
        if (ec, ev if ev is not None else 10**6) < (sc, sv or 0):
            raise RefError(f"Range '{part}' ends before it starts.")
        spans.append((sc, sv, ec, ev))
    if not spans:
        raise RefError(f"No chapter or verse found. {HELP}")
    return book, spans


def format_span(sc, sv, ec, ev) -> str:
    if sv is None:
        return f"{sc}" if sc == ec else f"{sc}-{ec}"
    if sc == ec:
        return f"{sc}:{sv}" if sv == ev else f"{sc}:{sv}-{ev}"
    return f"{sc}:{sv}-{ec}:{ev}"


def format_reference(book_display: str, spans) -> str:
    return f"{book_display} " + "; ".join(format_span(*s) for s in spans)
