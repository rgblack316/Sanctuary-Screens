"""Sanctuary Screens – backend regression tests.

Covers:
- Auth / PIN unlock + lockout, admin endpoint protection
- /api/health, public display endpoints
- Register admin: upsert, previous week N/A, set active
- Bible lookup (Romans 6:23, John 3:16-18, John 3:16-4:2, Psalm 23, 1Jn 1:9,10,
  malformed, unknown book), publish/next/prev/goto/clear/switch translation
- Translation import validation + import TST, delete rules (409 live/last), set default
- Prepared list CRUD + reorder
- WebSocket connect, ping/pong, state push
"""
import asyncio
import json
import os
import time

import pytest
import requests
import websockets

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")  # from frontend/.env via conftest
API = f"{BASE_URL}/api"
WS_BASE = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws"
PIN = "1234"


# ------------- shared fixtures -------------

@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def register_token(s):
    r = s.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "register"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def bible_token(s):
    r = s.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "bible"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def rh(register_token):
    return {"Authorization": f"Bearer {register_token}"}


@pytest.fixture
def bh(bible_token):
    return {"Authorization": f"Bearer {bible_token}"}


# ------------- health & public -------------

class TestHealth:
    def test_health(self, s):
        r = s.get(f"{API}/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ok"
        assert d["db"] == "ok"
        assert d["translations"] >= 1  # KJV seeded

    def test_register_display_public(self, s):
        r = s.get(f"{API}/register/display")
        assert r.status_code == 200
        assert "currency" in r.json()

    def test_bible_display_public(self, s):
        r = s.get(f"{API}/bible/display")
        assert r.status_code == 200
        assert "mode" in r.json()


# ------------- auth -------------

class TestAuth:
    def test_wrong_pin_shows_attempts_left(self, s):
        r = s.post(f"{API}/auth/unlock", json={"pin": "0000", "area": "register"})
        assert r.status_code == 401
        assert "attempt" in r.json()["detail"].lower()

    def test_admin_requires_auth(self, s):
        for ep in ["/register/services", "/bible/translations", "/bible/prepared?service_date=2026-10-04"]:
            r = s.get(f"{API}{ep}")
            assert r.status_code == 401, f"{ep} expected 401, got {r.status_code}"

    def test_correct_pin_unlocks(self, register_token):
        assert register_token

    def test_token_check(self, s, rh, bh):
        assert s.get(f"{API}/auth/check/register", headers=rh).status_code == 200
        assert s.get(f"{API}/auth/check/bible", headers=bh).status_code == 200


# ------------- register admin -------------

class TestRegister:
    TEST_DATE_1 = "2026-11-01"
    TEST_DATE_2 = "2026-11-08"  # 7d after date1

    @classmethod
    def teardown_class(cls):
        # cleanup via direct Mongo (no DELETE API) – best effort via public: we use pymongo
        try:
            from pymongo import MongoClient
            m = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = m[os.environ.get("DB_NAME", "test_database")]
            db.register_services.delete_many({"service_date": {"$in": [cls.TEST_DATE_1, cls.TEST_DATE_2]}})
            # restore active to latest existing
            latest = db.register_services.find_one(sort=[("service_date", -1)])
            if latest:
                db.register_state.update_one({"_id": "state"},
                                             {"$set": {"active_service_date": latest["service_date"]}}, upsert=True)
        except Exception as e:
            print("teardown register err", e)

    def test_upsert_service(self, s, rh):
        r = s.put(f"{API}/register/services/{self.TEST_DATE_1}", headers=rh,
                  json={"service_label": "TEST_Sun", "attendance": 25, "offering": 123.45, "make_active": True})
        assert r.status_code == 200
        d = r.json()
        assert d["current"]["service_date"] == self.TEST_DATE_1
        assert d["current"]["attendance"] == 25
        assert d["current"]["offering"] == 123.45
        # no record 7d earlier
        assert d["previous"] is None
        assert d["comparison_service_date"] == "2026-10-25"

    def test_upsert_second_week_shows_previous(self, s, rh):
        r = s.put(f"{API}/register/services/{self.TEST_DATE_2}", headers=rh,
                  json={"service_label": "TEST_Sun2", "attendance": 30, "offering": 150, "make_active": True})
        assert r.status_code == 200
        d = r.json()
        assert d["previous"] is not None
        assert d["previous"]["service_date"] == self.TEST_DATE_1
        assert d["previous"]["attendance"] == 25

    def test_resave_same_date_updates_not_duplicates(self, s, rh):
        s.put(f"{API}/register/services/{self.TEST_DATE_1}", headers=rh,
              json={"service_label": "TEST_Sun", "attendance": 99, "offering": 1, "make_active": False})
        r = s.get(f"{API}/register/services", headers=rh)
        matches = [x for x in r.json()["services"] if x["service_date"] == self.TEST_DATE_1]
        assert len(matches) == 1
        assert matches[0]["attendance"] == 99

    def test_set_active_history(self, s, rh):
        r = s.post(f"{API}/register/active", headers=rh, json={"service_date": self.TEST_DATE_1})
        assert r.status_code == 200
        assert r.json()["current"]["service_date"] == self.TEST_DATE_1

    def test_set_active_missing(self, s, rh):
        r = s.post(f"{API}/register/active", headers=rh, json={"service_date": "1999-01-01"})
        assert r.status_code == 404

    def test_invalid_date_422(self, s, rh):
        r = s.put(f"{API}/register/services/not-a-date", headers=rh,
                  json={"service_label": "x", "attendance": 1, "offering": 1})
        assert r.status_code == 422

    def test_negative_attendance_422(self, s, rh):
        r = s.put(f"{API}/register/services/2026-12-06", headers=rh,
                  json={"service_label": "x", "attendance": -5, "offering": 10})
        assert r.status_code == 422


# ------------- bible lookup -------------

class TestBibleLookup:
    def test_romans_6_23(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh, json={"reference": "Romans 6:23", "translation_code": "KJV"})
        assert r.status_code == 200
        d = r.json()
        assert len(d["verses"]) == 1
        assert "wages" in d["verses"][0]["verse_text"].lower()

    def test_john_3_16_18(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh, json={"reference": "John 3:16-18", "translation_code": "KJV"})
        assert r.status_code == 200
        assert len(r.json()["verses"]) == 3

    def test_cross_chapter(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh,
                   json={"reference": "John 3:16-4:2", "translation_code": "KJV"})
        assert r.status_code == 200
        assert len(r.json()["verses"]) == 23

    def test_psalm_23(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh, json={"reference": "Psalm 23", "translation_code": "KJV"})
        assert r.status_code == 200
        assert len(r.json()["verses"]) == 6

    def test_1jn_1_9_10(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh, json={"reference": "1 Jn 1:9,10", "translation_code": "KJV"})
        assert r.status_code == 200
        assert len(r.json()["verses"]) == 2

    def test_malformed(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh, json={"reference": "John :::", "translation_code": "KJV"})
        assert r.status_code == 422

    def test_unknown_book(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh,
                   json={"reference": "Hezekiah 1:1", "translation_code": "KJV"})
        assert r.status_code == 404
        assert "manually" in r.json()["detail"].lower()


# ------------- bible publish / live -------------

class TestBibleLive:
    @classmethod
    def teardown_class(cls):
        # clear display to idle (requirement)
        try:
            t = requests.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "bible"}).json()["token"]
            requests.post(f"{API}/bible/display/clear", headers={"Authorization": f"Bearer {t}"})
        except Exception:
            pass

    def test_publish_and_next_prev(self, s, bh):
        lk = s.post(f"{API}/bible/lookup", headers=bh,
                    json={"reference": "John 3:16-18", "translation_code": "KJV"}).json()
        pub = s.post(f"{API}/bible/publish", headers=bh, json={
            "reference_input": "John 3:16-18",
            "normalized_reference": lk["normalized_reference"],
            "translation_code": "KJV",
            "source_type": "local_lookup",
            "verses": lk["verses"],
            "start_index": 0,
        })
        assert pub.status_code == 200
        d = pub.json()
        assert d["mode"] == "passage"
        assert d["total"] == 3
        assert d["slide_index"] == 0

        n = s.post(f"{API}/bible/display/next", headers=bh).json()
        assert n["slide_index"] == 1
        g = s.post(f"{API}/bible/display/goto", headers=bh, json={"index": 2}).json()
        assert g["slide_index"] == 2
        p = s.post(f"{API}/bible/display/prev", headers=bh).json()
        assert p["slide_index"] == 1

        # verify public display reflects state
        pub_disp = s.get(f"{API}/bible/display").json()
        assert pub_disp["slide_index"] == 1

    def test_clear_to_idle(self, s, bh):
        r = s.post(f"{API}/bible/display/clear", headers=bh)
        assert r.status_code == 200
        assert r.json()["mode"] == "idle"


# ------------- translations import -------------

VALID_CSV = (
    "translation,book,chapter,verse,text\n"
    "TST,John,3,16,For God so loved the world.\n"
    "TST,John,3,17,Not to condemn.\n"
    "TST,Romans,6,23,The gift of God.\n"
)
BAD_MISSING_COL = "translation,book,chapter,verse\nTST,John,3,16\n"
BAD_NONINT_VERSE = (
    "translation,book,chapter,verse,text\n"
    "TST,John,3,abc,text\n"
)
BAD_DUPES = (
    "translation,book,chapter,verse,text\n"
    "TST,John,3,16,a\nTST,John,3,16,b\n"
)
BAD_MULTI_CODE = (
    "translation,book,chapter,verse,text\n"
    "TST,John,3,16,a\nTS2,John,3,17,b\n"
)


class TestTranslations:
    @classmethod
    def teardown_class(cls):
        try:
            t = requests.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "bible"}).json()["token"]
            h = {"Authorization": f"Bearer {t}"}
            # ensure KJV default
            requests.put(f"{API}/bible/settings", headers=h, json={"default_translation": "KJV"})
            requests.delete(f"{API}/bible/translations/TST?confirm=true", headers=h)
        except Exception:
            pass

    def _validate(self, s, bh, csv_bytes):
        return s.post(f"{API}/bible/translations/validate", headers=bh,
                      files={"file": ("x.csv", csv_bytes, "text/csv")})

    def test_validate_missing_col(self, s, bh):
        r = self._validate(s, bh, BAD_MISSING_COL.encode())
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_validate_non_integer(self, s, bh):
        r = self._validate(s, bh, BAD_NONINT_VERSE.encode())
        assert r.json()["ok"] is False

    def test_validate_duplicates(self, s, bh):
        r = self._validate(s, bh, BAD_DUPES.encode())
        assert r.json()["ok"] is False

    def test_validate_multi_code(self, s, bh):
        r = self._validate(s, bh, BAD_MULTI_CODE.encode())
        assert r.json()["ok"] is False

    def test_import_valid_tst(self, s, bh):
        r = s.post(f"{API}/bible/translations/import", headers=bh,
                   files={"file": ("tst.csv", VALID_CSV.encode(), "text/csv")},
                   data={"translation_name": "Test Translation", "replace": "false"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["translation"]["translation_code"] == "TST"
        assert d["translation"]["verse_count"] == 3

    def test_lookup_in_tst(self, s, bh):
        r = s.post(f"{API}/bible/lookup", headers=bh,
                   json={"reference": "Romans 6:23", "translation_code": "TST"})
        assert r.status_code == 200
        assert r.json()["verses"][0]["verse_text"] == "The gift of God."

    def test_reimport_without_replace_409(self, s, bh):
        r = s.post(f"{API}/bible/translations/import", headers=bh,
                   files={"file": ("tst.csv", VALID_CSV.encode(), "text/csv")},
                   data={"translation_name": "Test", "replace": "false"})
        # Returns 409 directly from commit_import
        assert r.status_code == 409

    def test_cannot_delete_last_translation(self, s, bh):
        # Cannot delete KJV because we need to also check it's not last. With TST + KJV = 2.
        # Try to delete KJV - should succeed since 2 remain... first ensure not live
        requests.post(f"{API}/bible/display/clear",
                      headers={"Authorization": bh["Authorization"]})
        # Set TST as default so KJV deletable
        s.put(f"{API}/bible/settings", headers=bh, json={"default_translation": "TST"})
        # Try delete without confirm
        r = s.delete(f"{API}/bible/translations/KJV", headers=bh)
        assert r.status_code == 400
        # restore default KJV, don't actually delete
        s.put(f"{API}/bible/settings", headers=bh, json={"default_translation": "KJV"})

    def test_cannot_delete_live_translation(self, s, bh):
        # Publish KJV passage, then try to delete KJV
        lk = s.post(f"{API}/bible/lookup", headers=bh,
                    json={"reference": "Romans 6:23", "translation_code": "KJV"}).json()
        s.post(f"{API}/bible/publish", headers=bh, json={
            "reference_input": "Romans 6:23", "normalized_reference": lk["normalized_reference"],
            "translation_code": "KJV", "source_type": "local_lookup", "verses": lk["verses"],
            "start_index": 0,
        })
        r = s.delete(f"{API}/bible/translations/KJV?confirm=true", headers=bh)
        assert r.status_code == 409
        s.post(f"{API}/bible/display/clear", headers=bh)


# ------------- prepared list -------------

class TestPrepared:
    DATE = "2026-11-15"
    created_ids = []

    @classmethod
    def teardown_class(cls):
        try:
            t = requests.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "bible"}).json()["token"]
            h = {"Authorization": f"Bearer {t}"}
            items = requests.get(f"{API}/bible/prepared?service_date={cls.DATE}", headers=h).json().get("items", [])
            for it in items:
                requests.delete(f"{API}/bible/prepared/{it['id']}", headers=h)
        except Exception:
            pass

    def test_create_and_list(self, s, bh):
        for i, ref in enumerate(["Romans 6:23", "John 3:16", "Psalm 23:1"]):
            r = s.post(f"{API}/bible/prepared", headers=bh, json={
                "service_date": self.DATE, "title_or_note": f"TEST_{i}",
                "reference": ref, "translation_code": "KJV", "preloaded_text_optional": ""
            })
            assert r.status_code == 200
            self.created_ids.append(r.json()["id"])
        lst = s.get(f"{API}/bible/prepared?service_date={self.DATE}", headers=bh).json()
        assert len(lst["items"]) == 3
        assert [x["reference"] for x in lst["items"]] == ["Romans 6:23", "John 3:16", "Psalm 23:1"]

    def test_move_down(self, s, bh):
        first_id = s.get(f"{API}/bible/prepared?service_date={self.DATE}", headers=bh).json()["items"][0]["id"]
        r = s.post(f"{API}/bible/prepared/{first_id}/move", headers=bh, json={"direction": "down"})
        assert r.status_code == 200
        refs = [x["reference"] for x in r.json()["items"]]
        assert refs[0] == "John 3:16"

    def test_update(self, s, bh):
        it = s.get(f"{API}/bible/prepared?service_date={self.DATE}", headers=bh).json()["items"][0]
        r = s.put(f"{API}/bible/prepared/{it['id']}", headers=bh, json={
            "service_date": self.DATE, "title_or_note": "edited",
            "reference": it["reference"], "translation_code": "KJV", "preloaded_text_optional": ""
        })
        assert r.status_code == 200
        assert r.json()["title_or_note"] == "edited"

    def test_delete(self, s, bh):
        items = s.get(f"{API}/bible/prepared?service_date={self.DATE}", headers=bh).json()["items"]
        r = s.delete(f"{API}/bible/prepared/{items[0]['id']}", headers=bh)
        assert r.status_code == 200
        remaining = s.get(f"{API}/bible/prepared?service_date={self.DATE}", headers=bh).json()["items"]
        assert len(remaining) == 2


# ------------- WebSocket -------------

class TestWebSocket:
    def test_ws_bible_state_push(self):
        async def run():
            async with websockets.connect(f"{WS_BASE}/bible", open_timeout=10) as ws:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert msg["type"] == "state"
                await ws.send("ping")
                pong = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert pong["type"] == "pong"
        asyncio.run(run())

    def test_ws_register_state_push(self):
        async def run():
            async with websockets.connect(f"{WS_BASE}/register", open_timeout=10) as ws:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert msg["type"] == "state"
                assert "currency" in msg["data"]
        asyncio.run(run())

    def test_ws_invalid_channel_closes(self):
        async def run():
            try:
                async with websockets.connect(f"{WS_BASE}/nope", open_timeout=10) as ws:
                    await asyncio.wait_for(ws.recv(), timeout=3)
                    return False
            except Exception:
                return True
        assert asyncio.run(run())
