import json
import sqlite3
from datetime import datetime

import httpx
import pytest

from gaps import readers
from gaps.errors import SourceError
from gaps.readers import (parse_gaps_payload, parse_timestamp, read_audit_db, read_eval_report,
                          read_gaps_api, read_questions)


def make_db(path, create_sql, rows_sql=()):
    conn = sqlite3.connect(path)
    for sql in (*create_sql, *rows_sql):
        conn.execute(sql)
    conn.commit()
    conn.close()
    return path


def test_read_mock_audit_db(mock_files):
    data = read_audit_db(mock_files["audit_db"])
    assert len(data.observations) == 10 and data.info["rows"] == 10 and data.info["audit_log_requests"] == 10
    first = data.observations[0]
    assert (first.topic, first.reason, first.request_id, first.origin, first.weight) == \
        ("coût du permis", "no_relevant_chunk", "REQ-20261110-0001", "audit", 1)
    assert first.timestamp == datetime(2026, 11, 10, 9, 0, 0)
    ctx = data.contexts["REQ-20261110-0001"]
    assert ctx.question == "Combien coûte le permis de conduire ?" and ctx.subdomain == "driving_license"
    assert data.contexts["REQ-20261110-0002"].subdomain is None  # routage sans sous-domaine
    assert "655123456" not in data.contexts["REQ-20261110-0010"].question  # masqué dès la lecture


def test_audit_db_is_opened_read_only(mock_files):
    path = mock_files["audit_db"]
    before = (path.stat().st_size, path.read_bytes())
    read_audit_db(path)
    assert (path.stat().st_size, path.read_bytes()) == before


def test_audit_db_alternative_columns_count_and_epoch(tmp_path):
    db = make_db(tmp_path / "a.db",
                 ["CREATE TABLE gaps (sujet TEXT, raison TEXT, nb INTEGER, ts REAL, domaine TEXT)"],
                 ["INSERT INTO gaps VALUES ('frais cni', 'low_score', 4, 1783000000, 'public_services')",
                  "INSERT INTO gaps VALUES ('', 'x', 1, NULL, NULL)",
                  "INSERT INTO gaps VALUES ('délai passeport', NULL, 'abc', 'pas une date', NULL)",
                  "INSERT INTO gaps VALUES ('zéro', NULL, 0, NULL, NULL)"])
    data = read_audit_db(db)
    obs = {o.topic: o for o in data.observations}
    assert set(obs) == {"frais cni", "délai passeport", "zéro"} and data.info["skipped_empty_topic"] == 1
    assert obs["frais cni"].weight == 4 and obs["frais cni"].domain == "public_services"
    assert obs["frais cni"].timestamp is not None
    assert obs["délai passeport"].weight == 1 and obs["délai passeport"].timestamp is None  # valeurs invalides -> défauts
    assert obs["zéro"].weight == 1


def test_audit_db_since_filter(mock_files):
    data = read_audit_db(mock_files["audit_db"], since=datetime(2026, 11, 10, 12, 0, 0))
    assert [o.request_id[-4:] for o in data.observations] == ["0007", "0008", "0009", "0010"]
    assert data.info["skipped_before_since"] == 6


def test_audit_db_without_audit_log_table_still_works(tmp_path):
    db = make_db(tmp_path / "a.db", ["CREATE TABLE gaps (topic TEXT)"], ["INSERT INTO gaps VALUES ('x y')"])
    data = read_audit_db(db)
    assert len(data.observations) == 1 and data.contexts == {}


@pytest.mark.parametrize("sql,message", [
    (["CREATE TABLE autre (a TEXT)"], "table 'gaps' absente"),
    (["CREATE TABLE gaps (reason TEXT, request_id TEXT)"], "sans colonne de sujet"),
])
def test_audit_db_schema_errors_are_explicit(tmp_path, sql, message):
    with pytest.raises(SourceError, match=message):
        read_audit_db(make_db(tmp_path / "a.db", sql))


def test_audit_db_missing_or_corrupt(tmp_path):
    with pytest.raises(SourceError, match="introuvable"):
        read_audit_db(tmp_path / "absent.db")
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"ce n'est pas une base sqlite" * 50)
    with pytest.raises(SourceError):
        read_audit_db(bad)


def test_parse_timestamp_variants():
    assert parse_timestamp("2026-11-10T09:00:00") == datetime(2026, 11, 10, 9)
    assert parse_timestamp("2026-11-10") == datetime(2026, 11, 10)
    assert parse_timestamp("2026-11-10T09:00:00Z") == datetime(2026, 11, 10, 9)
    assert parse_timestamp("2026-11-10T10:00:00+01:00") == datetime(2026, 11, 10, 9)
    assert parse_timestamp(0) == datetime(1970, 1, 1)
    for bad in (None, "", "hier", True and "n/a"):
        assert parse_timestamp(bad) is None


@pytest.mark.parametrize("payload", [
    [{"topic": "frais cni", "count": 3}, "délai passeport", {"sujet": "x", "occurrences": "2"}],
    {"gaps": [{"topic": "frais cni", "count": 3}, {"topic": "délai passeport"}, {"topic": "x", "n": 2}]},
    {"items": [{"topic": "frais cni", "count": 3}, {"topic": "délai passeport"}, {"topic": "x", "total": 2}]},
])
def test_parse_gaps_payload_shapes(payload):
    data = parse_gaps_payload(payload)
    assert [(o.topic, o.weight) for o in data.observations] == [("frais cni", 3), ("délai passeport", 1), ("x", 2)]
    assert data.info["kind"] == "api"


def test_parse_gaps_payload_rejects_unknown_shape():
    for bad in ({"oops": 1}, "texte", 3):
        with pytest.raises(SourceError, match="liste de lacunes"):
            parse_gaps_payload(bad)
    assert parse_gaps_payload([{"pas_de_sujet": 1}, 5, {"topic": " "}]).observations == []


def test_read_gaps_api(monkeypatch):
    seen = {}

    def fake_get(url, timeout):
        seen["url"] = url
        return httpx.Response(200, json=[{"topic": "frais cni", "count": 2}], request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    data = read_gaps_api("http://127.0.0.1:8000/")
    assert seen["url"] == "http://127.0.0.1:8000/gaps" and data.observations[0].weight == 2


def test_read_gaps_api_errors(monkeypatch):
    def down(url, timeout):
        raise httpx.ConnectError("refusé")

    monkeypatch.setattr(httpx, "get", down)
    with pytest.raises(SourceError, match="impossible"):
        read_gaps_api("http://x")
    monkeypatch.setattr(httpx, "get", lambda url, timeout: httpx.Response(500, request=httpx.Request("GET", url)))
    with pytest.raises(SourceError, match="impossible"):
        read_gaps_api("http://x")
    monkeypatch.setattr(httpx, "get", lambda url, timeout: httpx.Response(200, text="pas du json", request=httpx.Request("GET", url)))
    with pytest.raises(SourceError, match="JSON invalide"):
        read_gaps_api("http://x")


def test_read_eval_report(mock_files, tmp_path):
    data = read_eval_report(mock_files["eval_report"])
    assert data.run_id == "EVAL-20261112-01" and len(data.failures) == 6
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"run_id": "R", "failures": [{"question_id": "Q1"}, {"x": 1}, "texte"]}), encoding="utf-8")
    data = read_eval_report(p)
    assert len(data.failures) == 1 and data.info["n_malformed_failures"] == 2
    p.write_text(json.dumps({"run_id": "R"}), encoding="utf-8")
    assert read_eval_report(p).failures == []  # aucun échec : rapport valide


@pytest.mark.parametrize("content,message", [("pas json", "illisible"), ("[]", "objet JSON"),
                                             ('{"failures": 3}', "liste")])
def test_read_eval_report_errors(tmp_path, content, message):
    p = tmp_path / "e.json"
    p.write_text(content, encoding="utf-8")
    with pytest.raises(SourceError, match=message):
        read_eval_report(p)
    with pytest.raises(SourceError, match="introuvable"):
        read_eval_report(tmp_path / "absent.json")


def test_read_questions_shapes(mock_files, tmp_path):
    assert read_questions(mock_files["questions"])["Q11"].startswith("Quels documents")
    p = tmp_path / "q.json"
    p.write_text(json.dumps({"questions": [{"question_id": "Q1", "text": "Bonjour ?"}, {"id": "Q2"}, 3]}), encoding="utf-8")
    assert read_questions(p) == {"Q1": "Bonjour ?"}
    assert read_questions(None) == {} and read_questions(tmp_path / "absent.json") == {}
    p.write_text("pas json", encoding="utf-8")
    assert read_questions(p) == {}


def test_column_aliases_resolve_case_insensitively():
    assert readers._resolve(["ID", "Topic", "CREATED_AT"], "topic") == "Topic"
    assert readers._resolve(["ID"], "topic") is None
