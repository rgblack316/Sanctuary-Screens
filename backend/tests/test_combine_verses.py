"""Offline tests: the whole reference on one slide."""
import pytest

from offline import auth, client, db, run  # noqa: F401


def _seed(client, code, texts):
    now = "2026-01-01T00:00:00+00:00"
    run(client, db.bible_translations.insert_one, {
        "translation_code": code, "translation_name": code, "import_status": "ready", "verse_count": len(texts),
        "book_count": 1, "import_version": 1, "created_at": now, "updated_at": now})
    run(client, db.bible_verses.insert_many, [{
        "translation_code": code, "book_name": "John", "book_normalized": "john", "book_order": 43,
        "chapter": 3, "verse": 16 + i, "text": t, "reference_key": f"john.3.{16 + i}"} for i, t in enumerate(texts)])


@pytest.fixture(autouse=True)
def seeded(client):
    for c in ("bible_translations", "bible_verses", "bible_prepared", "bible_library", "bible_passages", "bible_display"):
        run(client, db[c].delete_many, {})
    _seed(client, "KJV", ["For God so loved", "For God sent not", "He that believeth"])
    _seed(client, "NIV", ["God loved", "God did not send", "Whoever believes"])
    import bible_routes
    bible_routes._books_cache.clear()
    yield


def lookup(client, **extra):
    return client.post("/api/bible/lookup", headers=auth(client), json={"reference": "John 3:16-18", "translation_code": "KJV", **extra})


def test_default_is_one_slide_per_verse(client):
    d = lookup(client).json()
    assert len(d["verses"]) == 3 and d["combined"] is False


def test_combine_builds_one_slide(client):
    d = lookup(client, combine=True).json()
    assert d["combined"] is True and len(d["verses"]) == 1
    assert d["verses"][0]["reference_label"] == "John 3:16-18"
    assert d["verses"][0]["verse_text"] == "¹⁶For God so loved ¹⁷For God sent not ¹⁸He that believeth"
    plain = lookup(client, combine=True, verse_numbers=False).json()
    assert plain["verses"][0]["verse_text"] == "For God so loved For God sent not He that believeth" and plain["verse_numbers"] is False
    one = lookup(client, combine=True).json()
    assert d["normalized_reference"] == one["normalized_reference"]


def test_too_long_for_one_slide(client):
    run(client, db.bible_verses.update_many, {"translation_code": "KJV"}, {"$set": {"text": "x" * 2000}})
    r = lookup(client, combine=True)
    assert r.status_code == 422 and "too long" in r.json()["detail"]
    assert lookup(client).status_code == 200     # still fine one verse at a time


def test_publish_keeps_combined_and_translation_switch_stays_one_slide(client):
    h = auth(client)
    d = lookup(client, combine=True).json()
    r = client.post("/api/bible/publish", headers=h, json={
        "reference_input": d["reference_input"], "normalized_reference": d["normalized_reference"],
        "translation_code": "KJV", "source_type": "local_lookup", "verses": d["verses"], "combined": True})
    assert r.status_code == 200 and r.json()["total"] == 1
    r = client.post("/api/bible/display/translation", headers=h, json={"translation_code": "NIV"})
    assert r.status_code == 200
    state = r.json()
    assert state["total"] == 1 and state["slide"]["verse_text"] == "¹⁶God loved ¹⁷God did not send ¹⁸Whoever believes"
    # a split passage is not combined by a translation switch
    d = lookup(client).json()
    client.post("/api/bible/publish", headers=h, json={
        "reference_input": d["reference_input"], "normalized_reference": d["normalized_reference"],
        "translation_code": "KJV", "source_type": "local_lookup", "verses": d["verses"]})
    assert client.post("/api/bible/display/translation", headers=h, json={"translation_code": "NIV"}).json()["total"] == 3


def test_prepared_and_library_remember_the_option(client):
    h = auth(client)
    p = client.post("/api/bible/prepared", headers=h, json={
        "service_date": "2026-11-23", "reference": "John 3:16-18", "translation_code": "KJV", "combined": True}).json()
    assert p["combined"] is True
    items = client.get("/api/bible/prepared?service_date=2026-11-23", headers=h).json()["items"]
    assert items[0]["combined"] is True
    lib = client.post("/api/bible/library", headers=h, json={
        "name": "John 3:16-18 (KJV, one slide)", "reference": "John 3:16-18", "translation_code": "KJV", "combined": True})
    assert lib.status_code == 200 and lib.json()["combined"] is True
    assert client.post("/api/bible/prepared", headers=h, json={
        "service_date": "2026-11-23", "reference": "John 3:16", "translation_code": "KJV"}).json()["combined"] is False


def test_switch_keeps_no_verse_numbers_choice(client):
    h = auth(client)
    d = lookup(client, combine=True, verse_numbers=False).json()
    client.post("/api/bible/publish", headers=h, json={
        "reference_input": d["reference_input"], "normalized_reference": d["normalized_reference"], "translation_code": "KJV",
        "source_type": "local_lookup", "verses": d["verses"], "combined": True, "verse_numbers": False})
    r = client.post("/api/bible/display/translation", headers=h, json={"translation_code": "NIV"}).json()
    assert r["slide"]["verse_text"] == "God loved God did not send Whoever believes"
    p = client.post("/api/bible/prepared", headers=h, json={"service_date": "2026-11-23", "reference": "John 3:16-18",
                                                          "combined": True, "verse_numbers": False}).json()
    assert p["verse_numbers"] is False
