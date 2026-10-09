"""Iteration 6 - translation label API tests for /bible appearance."""
import os
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PIN = os.environ.get("ADMIN_PIN", "1234")


@pytest.fixture(scope="module")
def token():
    # reset lockouts just in case
    from pymongo import MongoClient
    MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].pin_attempts.delete_many({})
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN, "area": "settings"}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def saved_state(token):
    h = {"Authorization": f"Bearer {token}"}
    bible = requests.get(f"{BASE_URL}/api/appearance/bible", headers=h, timeout=10).json()
    reg = requests.get(f"{BASE_URL}/api/appearance/register", headers=h, timeout=10).json()
    yield bible, reg
    # restore
    for display, snap in (("bible", bible), ("register", reg)):
        body = {k: v for k, v in snap["appearance"].items() if k != "image_url"}
        requests.put(f"{BASE_URL}/api/appearance/{display}", headers=h, json=body, timeout=10)
    # ensure idle
    requests.post(f"{BASE_URL}/api/bible/display/clear", headers=h, timeout=10)


def test_defaults_present(saved_state):
    bible, _ = saved_state
    a = bible["appearance"]
    assert "translation_show" in a
    assert "translation_position" in a
    # defaults declared in appearance.py
    d = bible["defaults"]
    assert d["translation_show"] is True
    assert d["translation_position"] == "bottom-right"


def _put_bible(token, body):
    h = {"Authorization": f"Bearer {token}"}
    return requests.put(f"{BASE_URL}/api/appearance/bible", headers=h, json=body, timeout=10)


def test_put_valid_translation(token, saved_state):
    bible, _ = saved_state
    body = {k: v for k, v in bible["appearance"].items() if k != "image_url"}
    body["translation_show"] = False
    body["translation_position"] = "top-left"
    r = _put_bible(token, body)
    assert r.status_code == 200, r.text
    a = r.json()["appearance"]
    assert a["translation_show"] is False
    assert a["translation_position"] == "top-left"
    # Persist check via GET
    h = {"Authorization": f"Bearer {token}"}
    g = requests.get(f"{BASE_URL}/api/appearance/bible", headers=h, timeout=10).json()["appearance"]
    assert g["translation_show"] is False
    assert g["translation_position"] == "top-left"


def test_put_invalid_position_422(token, saved_state):
    bible, _ = saved_state
    body = {k: v for k, v in bible["appearance"].items() if k != "image_url"}
    body["translation_position"] = "middle-middle"
    r = _put_bible(token, body)
    assert r.status_code == 422, r.text


def test_put_invalid_show_type_422(token, saved_state):
    bible, _ = saved_state
    body = {k: v for k, v in bible["appearance"].items() if k != "image_url"}
    body["translation_show"] = "nope"
    r = _put_bible(token, body)
    assert r.status_code == 422, r.text


def test_register_appearance_also_has_translation_keys(saved_state):
    # Pydantic model is shared, so register also has the fields (UI must hide them). This is informational.
    _, reg = saved_state
    assert "translation_show" in reg["appearance"]
