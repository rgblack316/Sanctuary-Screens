"""Offline tests: separate prepared lists, library search/match, songbook import + lookup, preview channel."""
import pytest

from offline import auth, client, db, run  # noqa: F401


@pytest.fixture(autouse=True)
def clean(client):
    for c in ("bible_library", "bible_prepared", "hymnal_songs", "bible_hymnals", "bible_preview",
              "bible_translations", "bible_verses", "pin_attempts"):
        run(client, db[c].delete_many, {})
    yield


@pytest.fixture
def h(client):
    return auth(client, "bible")


def lib(client, h, name, kind="scripture", ref=None, tr="KJV", text=""):
    r = client.post("/api/bible/library", headers=h, json={
        "name": name, "kind": kind, "reference": ref or name, "preloaded_text_optional": text,
        "translation_code": tr if kind == "scripture" else None})
    assert r.status_code == 200, r.text
    return r.json()


def seed_john(client):
    run(client, db.bible_translations.insert_one, {
        "translation_code": "KJV", "translation_name": "King James", "import_status": "ready", "verse_count": 1,
        "book_count": 1, "import_version": 1, "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"})
    run(client, db.bible_verses.insert_one, {
        "translation_code": "KJV", "book_name": "John", "book_normalized": "john", "book_order": 43,
        "chapter": 3, "verse": 16, "text": "For God so loved the world", "reference_key": "john.3.16"})
    import bible_routes
    bible_routes._books_cache.clear()


# ---------- prepared lists ----------

def prep(client, h, ref, kind, date="2026-11-01"):
    r = client.post("/api/bible/prepared", headers=h, json={"service_date": date, "reference": ref, "kind": kind,
                                                            "translation_code": "KJV" if kind == "scripture" else None})
    assert r.status_code == 200, r.text
    return r.json()


def order(client, h, kind, date="2026-11-01"):
    items = client.get("/api/bible/prepared", headers=h, params={"service_date": date}).json()["items"]
    return [i["reference"] for i in items if i["kind"] == kind]


def test_hymn_kind_accepted_and_each_list_reorders_on_its_own(client, h):
    s1, h1, s2, h2 = (prep(client, h, "S1", "scripture"), prep(client, h, "H1", "hymn"),
                      prep(client, h, "S2", "scripture"), prep(client, h, "H2", "hymn"))
    assert order(client, h, "hymn") == ["H1", "H2"]
    client.post(f"/api/bible/prepared/{s2['id']}/move", headers=h, json={"direction": "up"})
    assert order(client, h, "scripture") == ["S2", "S1"]      # swapped with S1, not with the hymn between them
    assert order(client, h, "hymn") == ["H1", "H2"]           # hymn list untouched
    client.post(f"/api/bible/prepared/{h2['id']}/move", headers=h, json={"direction": "up"})
    assert order(client, h, "hymn") == ["H2", "H1"]
    client.post(f"/api/bible/prepared/{h2['id']}/move", headers=h, json={"direction": "up"})  # already first: no-op
    assert order(client, h, "hymn") == ["H2", "H1"]


def test_unknown_kind_rejected(client, h):
    r = client.post("/api/bible/prepared", headers=h, json={"service_date": "2026-11-01", "reference": "x", "kind": "bogus"})
    assert r.status_code == 422


# ---------- library list / search / match ----------

def test_library_paging_filter_and_counts(client, h):
    for i in range(7):
        lib(client, h, f"Verse {i:02d}", ref=f"Psalm {i + 1}")
    lib(client, h, "Amazing Grace", kind="hymn", text="Hymn 45 · Page 112")
    lib(client, h, "Welcome", kind="custom", text="Good morning")
    r = client.get("/api/bible/library", headers=h, params={"limit": 3, "offset": 0}).json()
    assert len(r["items"]) == 3 and r["total"] == 9 and r["counts"] == {"scripture": 7, "hymn": 1, "custom": 1}
    page2 = client.get("/api/bible/library", headers=h, params={"limit": 3, "offset": 3}).json()["items"]
    assert not {i["id"] for i in r["items"]} & {i["id"] for i in page2}
    hy = client.get("/api/bible/library", headers=h, params={"kind": "hymn"}).json()
    assert [i["name"] for i in hy["items"]] == ["Amazing Grace"] and hy["total"] == 1
    srch = client.get("/api/bible/library", headers=h, params={"q": "page 112"}).json()   # matches slide text, any case
    assert [i["name"] for i in srch["items"]] == ["Amazing Grace"]
    assert client.get("/api/bible/library", headers=h, params={"q": ".*"}).json()["total"] == 0   # regex chars are literal


def test_match_finds_same_passage_however_it_is_typed(client, h):
    seed_john(client)
    lib(client, h, "John 3:16 (KJV)", ref="John 3:16", tr="KJV")
    m = client.get("/api/bible/library/match", headers=h, params={"text": "jn 3:16", "translation_code": "KJV"}).json()
    assert m["normalized"] == "John 3:16" and m["items"][0]["exact"] is True
    other = client.get("/api/bible/library/match", headers=h, params={"text": "jn 3:16", "translation_code": "ESV"}).json()
    assert [i["exact"] for i in other["items"]] == [False]   # same passage but saved in another translation: suggested, not a duplicate
    none = client.get("/api/bible/library/match", headers=h, params={"text": "Romans 8:1"}).json()
    assert none["items"] == []


def test_match_for_titles_flags_exact_and_partial(client, h):
    lib(client, h, "Amazing Grace", kind="hymn", text="Page 112")
    lib(client, h, "Amazing Love", kind="hymn")
    items = client.get("/api/bible/library/match", headers=h, params={"text": "Amazing Grace", "kind": "hymn"}).json()["items"]
    assert [(i["name"], i["exact"]) for i in items] == [("Amazing Grace", True)]
    items = client.get("/api/bible/library/match", headers=h, params={"text": "amazing", "kind": "hymn"}).json()["items"]
    assert {i["name"] for i in items} == {"Amazing Grace", "Amazing Love"} and not any(i["exact"] for i in items)
    assert client.get("/api/bible/library/match", headers=h, params={"text": "a"}).json()["items"] == []


def test_library_endpoints_need_the_pin(client):
    assert client.get("/api/bible/library").status_code == 401
    assert client.get("/api/bible/library/match", params={"text": "ab"}).status_code == 401


# ---------- songbooks ----------

CSV = ("songbook,title,page,number\n"
       "Baptist Hymnal,Amazing Grace,112,45\n"
       "Baptist Hymnal,Blessed Assurance,112,46\n"
       "Baptist Hymnal,Holy Holy Holy,9,\n"
       "Praise Songs,Great Is Thy Faithfulness,112,\n").encode()


def imp(client, h, raw=CSV, replace=True):
    return client.post("/api/bible/songs/import", headers=h, files={"file": ("s.csv", raw, "text/csv")},
                       data={"replace": str(replace).lower()})


def test_import_then_page_lookup_returns_every_song_on_that_page(client, h):
    r = imp(client, h).json()
    assert r["ok"] and r["imported"] == 4 and r["songbooks"] == {"Baptist Hymnal": 3, "Praise Songs": 1}
    hits = client.get("/api/bible/songs/search", headers=h, params={"q": "112"}).json()
    assert hits["total"] == 3 and {i["title"] for i in hits["items"]} == {"Amazing Grace", "Blessed Assurance", "Great Is Thy Faithfulness"}
    one = client.get("/api/bible/songs/search", headers=h, params={"q": "112", "songbook": "baptist hymnal"}).json()
    assert {i["title"] for i in one["items"]} == {"Amazing Grace", "Blessed Assurance"}   # songbook filter, any case
    assert all(i["matched_on"] == ["page"] for i in one["items"])


def test_number_and_leading_zero_and_title_search(client, h):
    imp(client, h)
    by_num = client.get("/api/bible/songs/search", headers=h, params={"q": "046"}).json()["items"]
    assert [(i["title"], i["matched_on"]) for i in by_num] == [("Blessed Assurance", ["number"])]
    by_title = client.get("/api/bible/songs/search", headers=h, params={"q": "holy"}).json()["items"]
    assert [i["title"] for i in by_title] == ["Holy Holy Holy"] and "matched_on" not in by_title[0]
    assert client.get("/api/bible/songs/search", headers=h, params={"q": ""}).json()["items"] == []


def test_import_adds_songbook_to_hymnal_list_and_reuses_spelling(client, h):
    imp(client, h)
    names = [x["name"] for x in client.get("/api/bible/hymnals", headers=h).json()["hymnals"]]
    assert "Baptist Hymnal" in names and "Praise Songs" in names
    raw = b"Songbook,Title,Page\nBAPTIST HYMNAL,Great Is Thy Faithfulness,200\n"
    imp(client, h, raw, replace=False)
    assert [b["name"] for b in client.get("/api/bible/songs/books", headers=h).json()["songbooks"]] == ["Baptist Hymnal", "Praise Songs"]
    assert len([n for n in [x["name"] for x in client.get("/api/bible/hymnals", headers=h).json()["hymnals"]] if n.lower() == "baptist hymnal"]) == 1


def test_replace_versus_add_and_duplicates(client, h):
    imp(client, h)
    extra = b"songbook,title,page\nBaptist Hymnal,Amazing Grace,112\nBaptist Hymnal,New Song,300\n"
    assert imp(client, h, extra, replace=False).json()["imported"] == 1      # the existing Amazing Grace is skipped
    assert client.get("/api/bible/songs/search", headers=h, params={"q": "300"}).json()["total"] == 1
    assert imp(client, h, extra, replace=True).json()["imported"] == 2       # replaces the whole Baptist Hymnal
    books = {b["name"]: b["count"] for b in client.get("/api/bible/songs/books", headers=h).json()["songbooks"]}
    assert books == {"Baptist Hymnal": 2, "Praise Songs": 1}
    dup = b"songbook,title,page\nA,T,1\nA,t,01\n"
    r = imp(client, h, dup).json()
    assert r["imported"] == 1 and r["report"]["duplicates"] == 1


def test_validation_reports_problems_without_importing(client, h):
    bad = client.post("/api/bible/songs/validate", headers=h, files={"file": ("s.csv", b"songbook,title\nA,B\n")}).json()
    assert bad["ok"] is False and "Missing required column" in bad["errors"][0]["error"]
    rows = b"songbook,title,page\nA,,5\n,B,6\nA,C,\nA,D,7\n"
    r = client.post("/api/bible/songs/validate", headers=h, files={"file": ("s.csv", rows)}).json()
    assert r["ok"] is False and r["error_count"] == 3 and r["row_count"] == 1
    out = imp(client, h, rows).json()
    assert out["ok"] is False
    assert client.get("/api/bible/songs/books", headers=h).json()["songbooks"] == []
    assert imp(client, h, b"\xff\xfe\x00bad").json()["ok"] is False


def test_other_header_names_and_semicolons_are_understood(client, h):
    raw = "Hymnal;Song Title;Page Number;Hymn Number\nTrinity Hymnal;Be Thou My Vision;5;7\n".encode()
    assert imp(client, h, raw).json()["imported"] == 1
    assert client.get("/api/bible/songs/search", headers=h, params={"q": "7"}).json()["items"][0]["title"] == "Be Thou My Vision"


def test_delete_songbook_needs_confirmation(client, h):
    imp(client, h)
    assert client.delete("/api/bible/songs/books/Praise Songs", headers=h).status_code == 400
    r = client.delete("/api/bible/songs/books/praise songs", headers=h, params={"confirm": "true"}).json()
    assert r["songs_removed"] == 1
    assert client.delete("/api/bible/songs/books/nothing", headers=h, params={"confirm": "true"}).status_code == 404


def test_songs_need_the_pin_and_sample_downloads(client, h):
    assert client.get("/api/bible/songs/search", params={"q": "1"}).status_code == 401
    assert client.post("/api/bible/songs/import", files={"file": ("s.csv", CSV)}).status_code == 401
    assert "songbook,title,page" in client.get("/api/bible/songs/sample.csv", headers=h).text


# ---------- preview channel ----------

PASSAGE = {"normalized_reference": "John 3:16", "translation_code": "KJV", "source_type": "local_lookup",
           "verses": [{"reference_label": "John 3:16", "verse_text": "For God so loved"},
                      {"reference_label": "John 3:17", "verse_text": "For God sent not"}]}


def test_preview_is_public_to_read_and_pin_protected_to_write(client, h):
    assert client.get("/api/preview/display").json()["mode"] == "idle"
    assert client.put("/api/preview", json=PASSAGE).status_code == 401
    assert client.delete("/api/preview").status_code == 401
    assert client.post("/api/preview/index", json={"index": 1}).status_code == 401


def test_preview_state_index_and_clear(client, h):
    s = client.put("/api/preview", headers=h, json=PASSAGE).json()
    assert s["mode"] == "passage" and s["total"] == 2 and s["slide"]["verse_text"] == "For God so loved" and s["preview"] is True
    assert client.post("/api/preview/index", headers=h, json={"index": 1}).json()["slide"]["verse_text"] == "For God sent not"
    assert client.post("/api/preview/index", headers=h, json={"index": 99}).json()["slide_index"] == 1   # clamped
    assert client.get("/api/preview/display").json()["slide_index"] == 1
    assert client.delete("/api/preview", headers=h).json()["mode"] == "idle"


def test_preview_does_not_touch_the_live_display(client, h):
    client.put("/api/preview", headers=h, json=PASSAGE)
    assert client.get("/api/bible/display").json()["mode"] == "idle"


def test_preview_is_pushed_over_the_websocket(client, h):
    with client.websocket_connect("/api/ws/preview") as ws:
        assert ws.receive_json()["data"]["mode"] == "idle"
        client.put("/api/preview", headers=h, json=PASSAGE)
        msg = ws.receive_json()
        assert msg["type"] == "state" and msg["data"]["reference"] == "John 3:16"


def test_preview_validation(client, h):
    assert client.put("/api/preview", headers=h, json={**PASSAGE, "verses": []}).status_code == 422
    assert client.put("/api/preview", headers=h, json={**PASSAGE, "source_type": "bogus"}).status_code == 422
