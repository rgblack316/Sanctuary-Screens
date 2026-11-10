from datetime import datetime

from offline import auth, client, db, run  # noqa: F401

CSV = ("songbook,title,page,number\nBaptist Hymnal,Amazing Grace,112,45\nBaptist Hymnal,Blessed Assurance,112,46\n"
       "Praise Songs,Great Is Thy Faithfulness,9,\n")


def _token(client):
    r = client.post("/api/hooks/token", headers=auth(client, "settings"))
    assert r.status_code == 200
    return r.json()["token"]


def _hook(client, tok, **body):
    return client.post("/api/hooks/bible", json=body, headers={"Authorization": f"Bearer {tok}"})


def test_token_lifecycle_and_auth(client):
    assert _hook(client, "x", action="next").status_code == 403          # off until a token exists
    assert client.get("/api/hooks/config").status_code == 401            # settings PIN required
    tok = _token(client)
    assert tok.startswith("ssw_")
    cfg = client.get("/api/hooks/config", headers=auth(client, "settings")).json()
    assert cfg["enabled"] and cfg["token_hint"] == tok[-4:] and "token" not in cfg
    assert run(client, db.admin_config.find_one, {"_id": "webhook"})["token_hash"] != tok
    assert _hook(client, "wrong", action="next").status_code == 401
    assert client.post("/api/hooks/bible", json={"action": "clear"}, headers={"X-Webhook-Token": tok}).status_code == 200
    new = _token(client)                                                  # regenerating invalidates the old token
    assert _hook(client, tok, action="clear").status_code == 401
    assert _hook(client, new, action="clear").status_code == 200


def test_hymn_builds_slide_and_logs_once(client):
    h = auth(client)
    client.post("/api/bible/songs/import", headers=h, files={"file": ("s.csv", CSV, "text/csv")}, data={"replace": "true"})
    tok = _token(client)
    r = _hook(client, tok, action="hymn", songbook="baptist hymnal", title="amazing grace", page="112")
    assert r.status_code == 200, r.text
    assert r.json()["song"]["title"] == "Amazing Grace" and r.json()["logged"] is True
    live = client.get("/api/bible/display").json()
    assert live["mode"] == "passage" and live["slide"]["reference_label"] == "Amazing Grace"
    assert live["slide"]["verse_text"] == "Page 112\nBaptist Hymnal"
    today = datetime.now().strftime("%Y-%m-%d")
    items = client.get(f"/api/bible/prepared?service_date={today}", headers=h).json()["items"]
    assert [(i["reference"], i["kind"], i["played"]) for i in items] == [("Amazing Grace", "hymn", True)]
    again = _hook(client, tok, action="hymn", title="Amazing Grace", page="112").json()
    assert again["logged"] is False
    assert len(client.get(f"/api/bible/prepared?service_date={today}", headers=h).json()["items"]) == 1


def test_page_only_ambiguity_and_unknown(client):
    tok = _token(client)
    amb = _hook(client, tok, action="hymn", page="112", songbook="Baptist Hymnal")
    assert amb.status_code == 409 and len(amb.json()["detail"]["matches"]) == 2
    assert _hook(client, tok, action="hymn", page="112", title="Blessed").json()["song"]["title"] == "Blessed Assurance"
    assert _hook(client, tok, action="hymn", page="999", songbook="Baptist Hymnal").status_code == 404
    assert _hook(client, tok, action="hymn").status_code == 422
    r = _hook(client, tok, action="hymn", title="Unlisted Song", page="5", songbook="Other Book")   # not in any songbook
    assert r.status_code == 200 and r.json()["song"] is None
    assert client.get("/api/bible/display").json()["slide"]["verse_text"] == "Page 5\nOther Book"


def test_logging_can_be_turned_off_and_navigation(client):
    h = auth(client, "settings")
    tok = _token(client)
    client.put("/api/hooks/config", json={"log_played": False}, headers=h)
    today = datetime.now().strftime("%Y-%m-%d")
    before = len(client.get(f"/api/bible/prepared?service_date={today}", headers=auth(client)).json()["items"])
    assert _hook(client, tok, action="hymn", title="Brand New Song").json()["logged"] is False
    assert len(client.get(f"/api/bible/prepared?service_date={today}", headers=auth(client)).json()["items"]) == before
    client.post("/api/bible/publish", headers=auth(client), json={
        "normalized_reference": "Test", "source_type": "custom",
        "verses": [{"reference_label": "A", "verse_text": "1"}, {"reference_label": "B", "verse_text": "2"}]})
    assert _hook(client, tok, action="next").json()["state"]["slide_index"] == 1
    assert _hook(client, tok, action="prev").json()["state"]["slide_index"] == 0
    assert _hook(client, tok, action="goto", index=1).json()["state"]["slide_index"] == 1
    assert _hook(client, tok, action="goto").status_code == 422
    assert _hook(client, tok, action="clear").json()["state"]["mode"] == "idle"
    assert _hook(client, tok, action="next").status_code == 409
    client.delete("/api/hooks/token", headers=h)
    assert _hook(client, tok, action="clear").status_code == 403
