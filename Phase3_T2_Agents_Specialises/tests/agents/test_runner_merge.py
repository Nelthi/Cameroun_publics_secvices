import pytest

from backend.agents import (canonical_agent_name, merge_drafts, run_agents, select_agents, validate_draft)
from backend.agents.exceptions import ContractError, LLMError, UnknownAgentError
from backend.agents.messages import NO_ANSWER
from backend.agents.mocks import FakeLLM, fake_search

Q = "Quels documents dois-je apporter pour ma première CNI ?"


def test_canonical_names():
    assert canonical_agent_name("Procédure") == "procedure"
    assert canonical_agent_name("Protection-des-données") == "donnees_personnelles"
    assert canonical_agent_name("anti-fraude") == "anti_fraude"
    assert canonical_agent_name(" ANTIFRAUDE ") == "anti_fraude"
    for bad in ("robot", "", None, 3):
        with pytest.raises(UnknownAgentError):
            canonical_agent_name(bad)


def test_select_agents_rules(plan):
    assert select_agents({**plan, "agents": ["procedure", "juridique", "procedure"]}) == ["procedure", "juridique"]
    assert select_agents({**plan, "agents": ["procedure", "robot", "coordinateur", "juridique"]}) == ["procedure", "juridique"]
    assert select_agents({**plan, "agents": ["procedure", "juridique", "anti_fraude", "donnees_personnelles"]}) \
        == ["procedure", "juridique", "anti_fraude"]
    assert select_agents({**plan, "needs_clarification": True}) == ["accueil"]
    assert select_agents({**plan, "intent": "hors_sujet", "agents": ["procedure"]}) == ["accueil"]
    assert select_agents({**plan, "intent": "accueil", "agents": []}) == ["accueil"]
    assert select_agents({**plan, "agents": []}) == []
    with pytest.raises(UnknownAgentError):
        select_agents({**plan, "agents": ["robot"]}, strict=True)


@pytest.mark.parametrize("bad", [None, [], {"intent": "procedure"}, {"request_id": " ", "intent": "x"},
                                 {"request_id": "R", "agents": []}, {"request_id": "R", "intent": "x", "agents": "procedure"}])
def test_invalid_plan(bad):
    with pytest.raises(ContractError):
        run_agents(Q, bad, search_fn=fake_search, llm_fn=FakeLLM())


def test_run_agents_one_draft_per_agent_in_plan_order(plan):
    plan["agents"] = ["juridique", "procedure"]
    drafts = run_agents(Q, plan, search_fn=fake_search, llm_fn=FakeLLM())
    assert [d["agent"] for d in drafts] == ["juridique", "procedure"]
    assert all(validate_draft(d) == [] and d["request_id"] == plan["request_id"] for d in drafts)


def test_search_is_shared_between_agents_with_same_query(plan):
    plan["agents"] = ["procedure", "juridique", "anti_fraude"]
    queries = []
    run_agents(Q, plan, search_fn=lambda q, k: queries.append(q) or fake_search(q, k), llm_fn=FakeLLM())
    assert len(queries) == 2  # procedure et juridique partagent la même requête ; anti_fraude a la sienne


def test_language_taken_from_argument_then_plan(plan):
    plan["language"] = "en"
    assert run_agents(Q, plan, search_fn=fake_search, llm_fn=FakeLLM())[0]["meta"]["language"] == "en"
    assert run_agents(Q, plan, language="fr", search_fn=fake_search, llm_fn=FakeLLM())[0]["meta"]["language"] == "fr"


def test_static_routes_use_accueil_only(plan):
    drafts = run_agents("Bonjour", {**plan, "intent": "accueil", "agents": ["accueil"]},
                        search_fn=lambda *a: pytest.fail("pas de recherche"), llm_fn=lambda p: pytest.fail("pas de LLM"))
    assert [d["agent"] for d in drafts] == ["accueil"]
    assert run_agents(Q, {**plan, "agents": []}, search_fn=fake_search, llm_fn=FakeLLM()) == []


def test_failing_agent_becomes_error_draft_but_others_survive(plan):
    plan["agents"] = ["procedure", "juridique"]
    answers = {"n": 0}

    def flaky(prompt):
        answers["n"] += 1
        if "Juridique" in prompt.split("\n")[0]:
            raise RuntimeError("quota")
        return "Il faut un acte de naissance [1]."

    drafts = run_agents(Q, plan, search_fn=fake_search, llm_fn=flaky)
    assert drafts[0]["meta"]["kind"] == "rag" and drafts[1]["meta"]["kind"] == "error"
    assert "quota" in drafts[1]["meta"]["error"] and drafts[1]["answer_draft"] == NO_ANSWER["fr"]
    assert all(validate_draft(d) == [] for d in drafts)
    with pytest.raises(LLMError):
        run_agents(Q, plan, search_fn=fake_search, llm_fn=flaky, strict=True)


def test_empty_question_is_a_caller_error_not_an_agent_failure(plan):
    with pytest.raises(ContractError):
        run_agents("  ", plan, search_fn=fake_search, llm_fn=FakeLLM())


# --- merge -------------------------------------------------------------------------------
def _two_drafts(plan):
    plan["agents"] = ["procedure", "juridique"]
    llm = FakeLLM(["Pièces : acte de naissance [2][3].", "Textes signés le 28 février 2025 [3][1]."])
    return run_agents("Quels textes et quelles pièces pour la CNI ?", plan, search_fn=fake_search, llm_fn=llm)


def test_merge_renumbers_and_dedupes(plan):
    drafts = _two_drafts(plan)
    merged = merge_drafts(drafts)
    assert validate_draft(merged) == []
    assert merged["agent"] == "merged" and merged["meta"]["agents"] == ["procedure", "juridique"]
    chunks = [c["chunk_id"] for c in merged["citations"]]
    assert len(chunks) == len(set(chunks)) == 3  # 3 passages distincts cités
    p1, p2 = drafts
    # Chaque renvoi pointe sur le même fragment avant et après fusion.
    assert merged["citations"][0] == p1["citations"][0] and merged["citations"][1] == p1["citations"][1]
    assert merged["citations"][2] == p2["citations"][1]
    assert merged["answer_draft"].startswith("Procédure :\nPièces : acte de naissance [1][2].")
    assert "Textes officiels :\nTextes signés le 28 février 2025 [2][3]." in merged["answer_draft"]
    assert merged["retrieval"]["top_score"] == max(d["retrieval"]["top_score"] for d in drafts)
    assert merged["retrieval"]["n_chunks"] == len(merged["retrieval"]["passages"])
    assert [p["rank"] for p in merged["retrieval"]["passages"]] == list(range(1, merged["retrieval"]["n_chunks"] + 1))


def test_merge_single_draft_is_unchanged_except_agents_meta(plan):
    (draft,) = run_agents(Q, plan, search_fn=fake_search, llm_fn=FakeLLM())
    merged = merge_drafts([draft])
    assert {k: v for k, v in merged.items() if k != "meta"} == {k: v for k, v in draft.items() if k != "meta"}
    assert merged["meta"]["agents"] == ["procedure"]


def test_merge_ignores_agents_without_answer_but_flags_gap(plan):
    plan["agents"] = ["procedure", "juridique"]
    llm = FakeLLM(["Il faut un acte de naissance [1].", NO_ANSWER["fr"]])
    merged = merge_drafts(run_agents(Q, plan, search_fn=fake_search, llm_fn=llm))
    assert "Textes officiels" not in merged["answer_draft"]
    assert merged["meta"]["admits_missing_info"] is True and validate_draft(merged) == []


def test_merge_when_nobody_answers(plan):
    plan["agents"] = ["procedure", "juridique"]
    merged = merge_drafts(run_agents(Q, plan, search_fn=lambda q, k: [], llm_fn=FakeLLM()))
    assert merged["meta"]["no_answer"] is True and merged["citations"] == []
    assert merged["answer_draft"] == NO_ANSWER["fr"]


def test_merge_static_and_errors(plan):
    (draft,) = run_agents("Bonjour", {**plan, "intent": "accueil"}, search_fn=fake_search, llm_fn=FakeLLM())
    assert merge_drafts([draft])["meta"]["kind"] == "static"
    with pytest.raises(ContractError):
        merge_drafts([])
    d1 = run_agents(Q, plan, search_fn=fake_search, llm_fn=FakeLLM())[0]
    d2 = {**d1, "request_id": "REQ-AUTRE"}
    with pytest.raises(ContractError, match="request_id"):
        merge_drafts([d1, d2])
    with pytest.raises(ContractError, match="invalide"):
        merge_drafts([{**d1, "citations": "x"}])


# --- validate_draft ----------------------------------------------------------------------
def test_validate_draft_detects_problems(plan):
    good = run_agents(Q, plan, search_fn=fake_search, llm_fn=FakeLLM())[0]
    assert validate_draft(good) == []
    assert validate_draft("x") and validate_draft({})
    assert any("renvois" in e for e in validate_draft({**good, "answer_draft": "Texte [5]."}))
    assert any("top_score" in e for e in validate_draft({**good, "retrieval": {**good["retrieval"], "top_score": 3}}))
    bad_cit = {**good, "citations": [{"chunk_id": "INCONNU", "document_id": "D", "source_page": 1}] * 2}
    assert any("absente des passages" in e for e in validate_draft(bad_cit))
    assert any("entier" in e for e in validate_draft({**good, "citations": [{"chunk_id": "a", "document_id": "d", "source_page": "1"}] * 2}))
