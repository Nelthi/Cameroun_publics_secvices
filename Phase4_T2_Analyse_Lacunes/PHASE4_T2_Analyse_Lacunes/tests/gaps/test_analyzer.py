import json
from datetime import datetime

import pytest

from gaps.analyzer import analyze
from gaps.models import AuditData, EvalData, Observation
from gaps.readers import read_audit_db, read_eval_report, read_questions
from gaps.report import validate_report

NOW = datetime(2026, 11, 12, 10, 0, 0)


@pytest.fixture
def report(mock_files):
    return analyze(read_audit_db(mock_files["audit_db"]), read_eval_report(mock_files["eval_report"]),
                   read_questions(mock_files["questions"]), now=NOW)


def by_topic(report):
    return {g["topic"]: g for g in report["gaps"]}


def test_report_is_valid_and_has_contract_keys(report):
    assert validate_report(report) == []
    assert report["report_date"] == "2026-11-12T10:00:00" and report["n_gaps"] == len(report["gaps"]) == 8
    assert list(report)[:3] == ["report_date", "n_gaps", "gaps"]
    for gap in report["gaps"]:
        assert {"gap_id", "topic", "domain", "occurrences", "source", "suggested_document",
                "suggested_institution"} <= set(gap)


def test_similar_topics_are_merged_and_ranked(report):
    gaps = report["gaps"]
    assert [g["gap_id"] for g in gaps] == [f"GAP-{i:03d}" for i in range(1, 9)]
    assert [g["occurrences"] for g in gaps] == [4, 3, 1, 1, 1, 1, 1, 1]
    cni, permis = gaps[0], gaps[1]
    # 4 libellés différents (« frais CNI » x3, « coût de la carte nationale d'identité ») -> une lacune
    assert (cni["topic"], cni["subdomain"], cni["source"]) == ("frais CNI", "national_identity_card", "audit+eval")
    assert cni["suggested_document"] == "barème des frais" and cni["suggested_institution"] == "DGSN (à confirmer)"
    assert cni["evidence"]["reasons"] == {"low_score": 1, "no_relevant_chunk": 3}
    # « coût du permis » + « frais du permis de conduire » + question d'évaluation Q15
    assert permis["occurrences"] == 3 and permis["subdomain"] == "driving_license"
    assert permis["evidence"]["audit_occurrences"] == 2 and permis["evidence"]["eval_occurrences"] == 1
    assert permis["suggested_institution"] == "à confirmer"


def test_eval_failure_on_same_request_is_not_counted_twice(report):
    cni = report["gaps"][0]
    assert cni["occurrences"] == 4  # 4 lignes d'audit ; Q03 (REQ-...-0003) confirme sans ajouter
    assert cni["evidence"]["eval_failures"] == 1 and cni["evidence"]["eval_occurrences"] == 0
    assert cni["evidence"]["failure_types"] == {"source_missing": 1} and cni["evidence"]["question_ids"] == ["Q03"]


def test_eval_only_gaps_use_question_text_and_inferred_subdomain(report):
    topics = by_topic(report)
    renew = topics["Quels documents pour le renouvellement de la CNI ?"]
    assert (renew["source"], renew["subdomain"], renew["occurrences"]) == ("eval", "national_identity_card", 1)
    assert renew["suggested_document"] == "liste officielle des pièces à fournir"
    assert renew["evidence"]["failure_types"] == {"wrong_source": 1}
    deposit = topics["Où déposer ma demande de passeport ?"]  # Q19 : aucun request_id
    assert deposit["subdomain"] == "passport" and deposit["suggested_document"].startswith("liste des centres")


def test_ignored_failures_are_reported_not_lost(report):
    ignored = {i["question_id"]: i for i in report["ignored_failures"]}
    assert set(ignored) == {"Q07", "Q22"}
    assert ignored["Q07"]["failure_type"] == "unexpected_answer" and "garde-fous" in ignored["Q07"]["reason"]
    assert "introuvable" in ignored["Q22"]["reason"]
    assert any("Q" not in w and "faute de texte" in w for w in report["warnings"])


def test_count_unexpected_answers_flag(mock_files):
    args = (read_audit_db(mock_files["audit_db"]), read_eval_report(mock_files["eval_report"]),
            read_questions(mock_files["questions"]))
    base = analyze(*args, now=NOW)
    # Q07 n'a pas de texte de question : même avec l'option, il reste écarté (sans texte, pas de sujet).
    assert analyze(*args, now=NOW, count_unexpected=True)["n_gaps"] == base["n_gaps"]
    audit = AuditData()
    ev = EvalData("R", [{"question_id": "Q07", "expected": "refused", "got": "approved", "request_id": "REQ-X",
                         "question": "Quel est le tarif du visa ?"}])
    assert analyze(audit, ev, now=NOW)["n_gaps"] == 0
    counted = analyze(audit, ev, now=NOW, count_unexpected=True)
    assert counted["n_gaps"] == 1 and counted["gaps"][0]["evidence"]["failure_types"] == {"unexpected_answer": 1}


def test_summary_and_inputs(report):
    assert report["summary"]["total_occurrences"] == 13
    assert report["summary"]["by_subdomain"]["national_identity_card"] == {"n_gaps": 2, "occurrences": 5}
    assert report["inputs"]["audit"]["rows"] == 10 and report["inputs"]["eval"]["run_id"] == "EVAL-20261112-01"
    assert report["ignored_failures"] and report["parameters"] == {}


def test_personal_data_never_leaves_the_report(report):
    assert "655123456" not in json.dumps(report, ensure_ascii=False)
    # Chemin « évaluation » : la question fournie par l'échec est masquée avant de devenir un sujet.
    ev = EvalData("R", [{"question_id": "Q1", "expected": {"d": 1}, "got": "refused",
                         "question": "Mon numéro 655123456 : combien coûte la CNI ?"}])
    rep = analyze(None, ev, now=NOW)
    dumped = json.dumps(rep, ensure_ascii=False)
    assert "655123456" not in dumped and "[NUMERO_MASQUE]" in rep["gaps"][0]["topic"]


def test_deterministic(mock_files):
    def once():
        return analyze(read_audit_db(mock_files["audit_db"]), read_eval_report(mock_files["eval_report"]),
                       read_questions(mock_files["questions"]), now=NOW)

    assert json.dumps(once(), sort_keys=True) == json.dumps(once(), sort_keys=True)


def test_subdomains_are_never_merged():
    audit = AuditData(observations=[
        Observation("frais CNI", "audit", subdomain="national_identity_card"),
        Observation("frais passeport", "audit", subdomain="passport"),
        Observation("frais", "audit", subdomain="general")])
    assert analyze(audit, None, now=NOW)["n_gaps"] == 3


def test_weights_from_aggregated_api_rows():
    audit = AuditData(observations=[Observation("frais CNI", "audit", weight=5), Observation("coût de la CNI", "audit", weight=2)],
                      info={"kind": "api"})
    rep = analyze(audit, None, now=NOW)
    assert rep["n_gaps"] == 1 and rep["gaps"][0]["occurrences"] == 7
    assert any("dédoublonnés" in w for w in rep["warnings"])


def test_tie_break_prefers_eval_confirmed_then_recent():
    t = datetime
    audit = AuditData(observations=[
        Observation("alpha délai", "audit", request_id="R1", timestamp=t(2026, 11, 1), subdomain="general"),
        Observation("beta frais", "audit", request_id="R2", timestamp=t(2026, 11, 5), subdomain="general"),
        Observation("gamma pièces", "audit", request_id="R3", timestamp=t(2026, 11, 3), subdomain="general")])
    ev = EvalData("R", [{"question_id": "Q1", "expected": {"d": 1}, "got": "refused", "request_id": "R1"}])
    topics = [g["topic"] for g in analyze(audit, ev, now=NOW)["gaps"]]
    assert topics == ["alpha délai", "beta frais", "gamma pièces"]  # confirmé, puis plus récent


def test_representative_topic_is_most_frequent_and_prefers_audit():
    audit = AuditData(observations=[Observation("coût CNI", "audit"), Observation("frais CNI", "audit"),
                                    Observation("frais CNI", "audit")])
    assert analyze(audit, None, now=NOW)["gaps"][0]["topic"] == "frais CNI"


def test_no_sources_or_no_gaps_gives_a_valid_empty_report():
    rep = analyze(None, None, now=NOW)
    assert rep["n_gaps"] == 0 and validate_report(rep) == [] and rep["warnings"]
    rep = analyze(AuditData(), EvalData("R", []), now=NOW)
    assert rep["n_gaps"] == 0 and rep["summary"]["total_occurrences"] == 0 and validate_report(rep) == []


def test_topic_without_meaningful_words_still_reported():
    rep = analyze(AuditData(observations=[Observation("???", "audit"), Observation("???", "audit")]), None, now=NOW)
    assert rep["n_gaps"] == 1 and rep["gaps"][0]["occurrences"] == 2
    assert rep["gaps"][0]["topic_key"] == "general:sans-sujet"
    assert validate_report(rep) == []


def test_threshold_controls_merging():
    audit = AuditData(observations=[Observation("coût du permis", "audit", subdomain="g"),
                                    Observation("Combien coûte le permis de conduire ?", "audit", subdomain="g")])
    assert analyze(audit, None, now=NOW, threshold=0.6)["n_gaps"] == 1
    assert analyze(audit, None, now=NOW, threshold=0.95)["n_gaps"] == 2
