import re

BOOKS = [
    ("Genesis", "gen ge gn"), ("Exodus", "exod exo ex"), ("Leviticus", "lev le lv"),
    ("Numbers", "num nu nm nb"), ("Deuteronomy", "deut de dt"), ("Joshua", "josh jos"),
    ("Judges", "judg jdg"), ("Ruth", "rut ru"), ("1 Samuel", "1sam 1sa 1sm"),
    ("2 Samuel", "2sam 2sa 2sm"), ("1 Kings", "1kgs 1ki 1kin"), ("2 Kings", "2kgs 2ki 2kin"),
    ("1 Chronicles", "1chr 1ch 1chron"), ("2 Chronicles", "2chr 2ch 2chron"), ("Ezra", "ezr"),
    ("Nehemiah", "neh ne"), ("Esther", "esth est es"), ("Job", "jb"),
    ("Psalms", "psalm ps psa psm pss"), ("Proverbs", "prov pro prv pr"),
    ("Ecclesiastes", "eccl ecc ec qoh"), ("Song of Solomon", "song sos songofsongs canticles canticle"),
    ("Isaiah", "isa is"), ("Jeremiah", "jer je jr"), ("Lamentations", "lam la"),
    ("Ezekiel", "ezek eze ezk"), ("Daniel", "dan da dn"), ("Hosea", "hos ho"), ("Joel", "jl"),
    ("Amos", "am"), ("Obadiah", "obad ob"), ("Jonah", "jon jnh"), ("Micah", "mic mc"),
    ("Nahum", "nah na"), ("Habakkuk", "hab hb"), ("Zephaniah", "zeph zep zp"), ("Haggai", "hag hg"),
    ("Zechariah", "zech zec zc"), ("Malachi", "mal ml"), ("Matthew", "matt mat mt"),
    ("Mark", "mrk mar mk mr"), ("Luke", "luk lk"), ("John", "joh jhn jn"),
    ("Acts", "act ac actsoftheapostles"), ("Romans", "rom ro rm"), ("1 Corinthians", "1cor 1co"),
    ("2 Corinthians", "2cor 2co"), ("Galatians", "gal ga"), ("Ephesians", "eph ephes"),
    ("Philippians", "phil php pp"), ("Colossians", "col"), ("1 Thessalonians", "1thess 1th 1thes"),
    ("2 Thessalonians", "2thess 2th 2thes"), ("1 Timothy", "1tim 1ti"), ("2 Timothy", "2tim 2ti"),
    ("Titus", "tit"), ("Philemon", "philem phm phlm"), ("Hebrews", "heb"), ("James", "jas jm"),
    ("1 Peter", "1pet 1pe 1pt"), ("2 Peter", "2pet 2pe 2pt"), ("1 John", "1jn 1jhn 1joh"),
    ("2 John", "2jn 2jhn 2joh"), ("3 John", "3jn 3jhn 3joh"), ("Jude", "jud jd"),
    ("Revelation", "rev re revelations revelationofjohn apocalypse"),
]

_ORD = {"first": "1", "second": "2", "third": "3", "1st": "1", "2nd": "2", "3rd": "3", "iii": "3", "ii": "2", "i": "1"}
_ORD_RE = re.compile(r"^(first|second|third|1st|2nd|3rd|iii|ii|i)\s+(.*)$")


def normalize(name: str) -> str:
    s = (name or "").strip().lower().replace(".", " ")
    m = _ORD_RE.match(s)
    if m:
        s = _ORD[m.group(1)] + m.group(2)
    return re.sub(r"[^a-z0-9]", "", s)


ALIAS, BOOK_NAMES, BOOK_ORDER = {}, {}, {}
for _i, (_name, _abbr) in enumerate(BOOKS):
    _key = normalize(_name)
    BOOK_NAMES[_key], BOOK_ORDER[_key], ALIAS[_key] = _name, _i + 1, _key
    for _a in _abbr.split():
        ALIAS[_a] = _key


def canonical_for_import(book: str):
    """Return (book_name, book_normalized, book_order) for an imported row."""
    key = normalize(book)
    canon = ALIAS.get(key)
    if canon:
        return BOOK_NAMES[canon], canon, BOOK_ORDER[canon]
    return book.strip(), key, 1000


def resolve_query_book(raw: str, available: dict):
    """Resolve user-typed book to a book_normalized key present in `available`."""
    key = normalize(raw)
    if not key:
        return None
    if ALIAS.get(key) in available:
        return ALIAS[key]
    if key in available:
        return key
    cands = [k for k in available if k.startswith(key)]
    return cands[0] if len(cands) == 1 else None


def display_name(book_name: str) -> str:
    return "Psalm" if book_name == "Psalms" else book_name
