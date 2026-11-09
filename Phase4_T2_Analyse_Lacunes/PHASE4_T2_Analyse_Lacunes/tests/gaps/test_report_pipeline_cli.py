import json
import shutil
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from gaps import run, validate_report, write_report
from gaps.cli import main
from gaps.errors import GapAnalysisError, ReportError, SourceError
from gaps.mocks import write_mock_files

EXAMPLES = Path(__file__).resolve().parents[2] / "gaps" / "examples"
NOW = datetime(2026, 11, 12, 10, 0, 0)


def valid_report():
    return {"report_date": "2026-11-12T10:00:00", "n_gaps": 2, "gaps": [
        {"gap_id": "GAP-001", "topic": "a", "domain": "d", "occurrences": 4, "source": "audit",
         "suggested_document": "x", "suggested_institution": "à confirmer"},
        {"gap_id": "GAP-002", "topic": "b", "domain": "d", "occurrences": 4, "source": "audit+eval",
         "suggested_document": "x", "suggested_institution": "à confirmer"}]}


def test_validate_report_accepts_contract_example():
    assert validate_report(valid_report()) == []
    assert validate_report({"report_date": "2026-11-12T10:00:00", "n_gaps": 0, "gaps": []}) == []


def test_validate_report_detects_problems():
    def errors_for(**changes):
        report = valid_report()
        gap_changes = changes.pop("gap", {})
        report["gaps"][1].update(gap_changes)
        report.update(changes)
        return validate_report(report)

    assert validate_report("x") and validate_report({}) and validate_report({"report_date": "2026-11-12", "gaps": 3})
    assert any("ISO" in e for e in errors_for(report_date="hier"))
    assert any("n_gaps" in e for e in errors_for(n_gaps=5))
    assert any("gap_id" in e for e in errors_for(gap={"gap_id": "G1"}))
    assert any("double" in e for e in errors_for(gap={"gap_id": "GAP-001"}))
    assert any("occurrences" in e for e in errors_for(gap={"occurrences": 0}))
    assert any("occurrences" in e for e in errors_for(gap={"occurrences": True}))
    assert any("décroissantes" in e for e in errors_for(gap={"occurrences": 9}))
    assert any("source" in e for e in errors_for(gap={"source": "web"}))
    assert any("suggested_document" in e for e in errors_for(gap={"suggested_document": " "}))
    assert any("pas un objet" in e for e in errors_for(gaps=[1, 2], n_gaps=2))


def test_write_report_atomic_and_valid(tmp_path):
    out = tmp_path / "data" / "reports" / "gap_report.json"
    assert write_report(valid_report(), out) == out
    assert json.loads(out.read_text(encoding="utf-8"))["n_gaps"] == 2
    assert [p.name for p in out.parent.iterdir()] == ["gap_report.json"]  # pas de fichier temporaire résiduel
    bad = valid_report()
    bad["n_gaps"] = 9
    with pytest.raises(ReportError):
        write_report(bad, out)
    assert json.loads(out.read_text(encoding="utf-8"))["n_gaps"] == 2  # l'ancien rapport n'est pas écrasé


def test_run_with_explicit_paths(mock_files, tmp_path):
    out = tmp_path / "gap_report.json"
    report, written = run(audit_db=mock_files["audit_db"], eval_report=mock_files["eval_report"],
                          questions=mock_files["questions"], out=out, now=NOW)
    assert written == out and json.loads(out.read_text(encoding="utf-8")) == report
    assert report["n_gaps"] == 8 and report["parameters"]["similarity"] == 0.6
    assert validate_report(report) == []


def test_run_since_and_options(mock_files):
    report, written = run(audit_db=mock_files["audit_db"], eval_report=mock_files["eval_report"],
                          questions=mock_files["questions"], out=None, since="2026-11-10T13:00:00", now=NOW)
    assert written is None and report["parameters"]["since"] == "2026-11-10T13:00:00"
    assert report["inputs"]["audit"]["observations"] == 2
    for kwargs in ({"since": "hier"}, {"similarity": 0}, {"similarity": 1.5}, {"source": "web"}):
        with pytest.raises(GapAnalysisError):
            run(audit_db=mock_files["audit_db"], out=None, **kwargs)


def test_run_audit_only_when_eval_report_missing(mock_files, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # aucun data/reports/eval_report.json par défaut
    report, _ = run(audit_db=mock_files["audit_db"], out=None, now=NOW)
    assert report["n_gaps"] == 6 and report["inputs"]["eval"] is None
    assert any("eval_report.json absent" in w for w in report["warnings"])


def test_run_eval_only_when_no_audit(mock_files, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report, _ = run(eval_report=mock_files["eval_report"], questions=mock_files["questions"], out=None, now=NOW)
    assert report["inputs"]["audit"] is None and any("aucune source d'audit" in w for w in report["warnings"])
    assert {g["source"] for g in report["gaps"]} == {"eval"} and report["n_gaps"] == 3


def test_run_discovers_default_locations(mock_files, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "reports").mkdir(parents=True)
    (tmp_path / "data" / "eval").mkdir(parents=True)
    shutil.copy(mock_files["audit_db"], tmp_path / "data" / "audit.db")
    shutil.copy(mock_files["eval_report"], tmp_path / "data" / "reports" / "eval_report.json")
    shutil.copy(mock_files["questions"], tmp_path / "data" / "eval" / "questions.json")
    report, written = run(now=NOW)
    assert written == Path("data/reports/gap_report.json") and written.is_file() and report["n_gaps"] == 8


def test_run_errors(mock_files, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SourceError, match="aucune source exploitable"):
        run(out=None)
    with pytest.raises(SourceError, match="introuvable"):
        run(audit_db=tmp_path / "absent.db", out=None)
    with pytest.raises(SourceError, match="introuvable"):
        run(audit_db=mock_files["audit_db"], eval_report=tmp_path / "absent.json", out=None)
    with pytest.raises(SourceError, match="--api-url"):
        run(source="api", out=None)
    with pytest.raises(SourceError, match="audit.db introuvable"):
        run(source="audit", out=None)


def test_run_falls_back_to_api_when_audit_db_unusable(tmp_path, monkeypatch):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"x" * 600)
    monkeypatch.setattr(httpx, "get", lambda url, timeout: httpx.Response(
        200, json=[{"topic": "frais CNI", "count": 3}], request=httpx.Request("GET", url)))
    report, _ = run(audit_db=bad, api_url="http://api", out=None, now=NOW)
    assert report["gaps"][0]["occurrences"] == 3 and report["inputs"]["audit"]["kind"] == "api"
    assert any("repli sur GET /gaps" in w for w in report["warnings"])
    with pytest.raises(SourceError):  # --source audit ne se replie jamais
        run(audit_db=bad, api_url="http://api", source="audit", out=None)
    report, _ = run(api_url="http://api", source="api", out=None, now=NOW)
    assert report["n_gaps"] == 1


# --- CLI ---------------------------------------------------------------------------------
def test_cli_mock_writes_valid_report(capsys, tmp_path):
    out = tmp_path / "r.json"
    assert main(["--mock", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "8 lacune(s), 13 occurrence(s)" in printed and "GAP-001" in printed and f"Écrit : {out}" in printed
    assert validate_report(json.loads(out.read_text(encoding="utf-8"))) == []


def test_cli_no_write_and_errors(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["--mock", "--no-write"]) == 0
    assert "non écrit" in capsys.readouterr().out and not (tmp_path / "data").exists()
    assert main([]) == 1 and "Erreur" in capsys.readouterr().err
    assert main(["--mock", "--since", "hier"]) == 1
    assert main(["--mock", "--similarity", "2"]) == 1


def test_cli_explicit_files(capsys, mock_files, tmp_path):
    out = tmp_path / "x" / "r.json"
    assert main(["--audit-db", str(mock_files["audit_db"]), "--eval-report", str(mock_files["eval_report"]),
                 "--questions", str(mock_files["questions"]), "--out", str(out),
                 "--similarity", "0.9", "--count-unexpected-answers"]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["parameters"]["similarity"] == 0.9 and report["parameters"]["count_unexpected_answers"] is True


# --- Fichiers livrés -----------------------------------------------------------------------
def test_shipped_examples_are_valid_and_up_to_date(tmp_path):
    fresh = write_mock_files(tmp_path / "fresh")
    for key, name in (("eval_report", "mock_eval_report.json"), ("questions", "mock_questions.json")):
        assert (EXAMPLES / name).read_text(encoding="utf-8") == fresh[key].read_text(encoding="utf-8")
    report, _ = run(audit_db=EXAMPLES / "mock_audit.db", eval_report=EXAMPLES / "mock_eval_report.json",
                    questions=EXAMPLES / "mock_questions.json", out=None, now=NOW)
    example = json.loads((EXAMPLES / "gap_report_example.json").read_text(encoding="utf-8"))
    fresh_report = json.loads(json.dumps(report, ensure_ascii=False))
    for doc in (example, fresh_report):  # les chemins dépendent de l'endroit où on lance les tests
        for source in doc["inputs"].values():
            source.pop("path", None)
    assert validate_report(example) == [] and example == fresh_report
