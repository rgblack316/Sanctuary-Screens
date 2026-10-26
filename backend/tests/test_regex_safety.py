import time

from books import normalize
from reference import RefError, parse_reference


def test_reference_parsing_unchanged():
    assert parse_reference("1 Jn 1:9,10") == ("1 Jn", [(1, 9, 1, 9), (1, 10, 1, 10)])
    assert parse_reference("John 3:16–4:2")[1] == [(3, 16, 4, 2)]
    assert parse_reference("Psalm 23")[1] == [(23, None, 23, None)]
    assert normalize("First John") == "1john" and normalize("Isaiah") == "isaiah"


def test_pathological_input_is_fast():
    for bad in ["i " + " " * 200000 + "x", "a" + " " * 200000 + "!", "a9" + "\t" * 200000 + "x"]:
        t = time.time()
        normalize(bad)
        try:
            parse_reference(bad)
        except RefError:
            pass
        assert time.time() - t < 1
