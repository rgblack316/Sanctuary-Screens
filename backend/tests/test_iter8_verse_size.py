"""Iteration 8 - Verse text size on Bible appearance.

Non-destructive. Snapshots /api/appearance/bible, exercises verse_size validation,
and restores exactly. Admin PIN 1234.
"""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PIN = "1234"
KEYS = [
    "background_color", "text_color", "accent_color", "muted_color", "panel_color",
    "panel_opacity", "image_blur", "image_dim", "image_motion", "motion_speed",
    "church_name_show", "church_name_position", "church_name_size", "church_name_color",
    "church_name_uppercase", "church_logo_show", "church_logo_size",
    "translation_show", "translation_position", "reference_size", "verse_size",
]


@pytest.fixture(scope="module")
def hdr():
    r = requests.post(f"{BASE}/api/auth/unlock", json={"pin": PIN, "area": "settings"}, timeout=10)
    if r.status_code != 200:
        pytest.skip(f"settings unlock failed: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module", autouse=True)
def snapshot_and_restore(hdr):
    s = requests.get(f"{BASE}/api/appearance/bible", headers=hdr, timeout=10)
    assert s.status_code == 200
    snap = s.json()["appearance"]
    yield snap
    body = {k: snap[k] for k in KEYS if k in snap}
    r = requests.put(f"{BASE}/api/appearance/bible", headers=hdr, json=body, timeout=10)
    assert r.status_code == 200, f"restore failed: {r.text}"


def _body(snap, **over):
    b = {k: snap[k] for k in KEYS if k in snap}
    b.update(over)
    return b


def test_defaults_include_verse_size_5(hdr):
    r = requests.get(f"{BASE}/api/appearance/bible", headers=hdr, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["defaults"]["verse_size"] == 5
    assert "verse_size" in data["appearance"]


@pytest.mark.parametrize("size", [1, 5, 10])
def test_put_valid_verse_size(hdr, snapshot_and_restore, size):
    r = requests.put(
        f"{BASE}/api/appearance/bible",
        headers=hdr,
        json=_body(snapshot_and_restore, verse_size=size),
        timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json()["appearance"]["verse_size"] == size
    g = requests.get(f"{BASE}/api/appearance/bible", headers=hdr, timeout=10).json()
    assert g["appearance"]["verse_size"] == size


@pytest.mark.parametrize("bad", [0, 11, -1, 100])
def test_put_invalid_verse_size_422(hdr, snapshot_and_restore, bad):
    r = requests.put(
        f"{BASE}/api/appearance/bible",
        headers=hdr,
        json=_body(snapshot_and_restore, verse_size=bad),
        timeout=10,
    )
    assert r.status_code == 422, f"expected 422 for {bad}, got {r.status_code} {r.text}"


def test_verse_size_independent_of_reference_size(hdr, snapshot_and_restore):
    """Changing verse_size should not alter reference_size or color fields."""
    before = snapshot_and_restore
    r = requests.put(
        f"{BASE}/api/appearance/bible",
        headers=hdr,
        json=_body(before, verse_size=9),
        timeout=10,
    )
    assert r.status_code == 200
    after = r.json()["appearance"]
    for k in ("reference_size", "text_color", "muted_color", "background_color", "panel_color", "accent_color"):
        assert after[k] == before[k], f"{k} changed unexpectedly"
    assert after["verse_size"] == 9


def test_register_appearance_also_has_verse_size_default(hdr):
    """Model is shared so register appearance also exposes verse_size default 5."""
    r = requests.get(f"{BASE}/api/appearance/register", headers=hdr, timeout=10)
    assert r.status_code == 200
    assert r.json()["defaults"]["verse_size"] == 5
