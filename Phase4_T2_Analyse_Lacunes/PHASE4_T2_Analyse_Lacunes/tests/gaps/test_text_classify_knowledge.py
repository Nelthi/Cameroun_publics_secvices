import pytest

from gaps.classify import classify_failure, expects_refusal
from gaps.knowledge import (infer_subdomain, suggest_document, suggest_institution)
from gaps.text import clean_text, concepts, fold, mask_sensitive, similarity, tokens, topic_key


def test_fold():
    assert fold("  Où déposer l’acte d'État-civil ?? ") == "ou deposer l acte d etat civil"


def test_tokens_drop_stopwords_and_map_synonyms():
    assert tokens("Combien coûte le permis de conduire ?") == tokens("frais du permis de conduire")
    assert tokens("coût de la carte nationale d'identité") == frozenset({"FRAIS", "CNI"})
    assert tokens("Quels sont les frais de la carte d’identité ?") == frozenset({"FRAIS", "CNI"})
    assert "FRAIS" in tokens("tarifs") and "FRAIS" in tokens("prix") and "FRAIS" in tokens("montant à payer")
    assert concepts("délai de retrait de la CNI") == frozenset({"DELAI", "RETRAIT", "CNI"})


def test_plural_and_singular_match():
    assert tokens("passeports") == tokens("passeport")
    assert tokens("les centres d'enrôlement") == tokens("centre enrôlement")


@pytest.mark.parametrize("a,b,merged", [
    ("coût du permis", "frais du permis de conduire", True),
    ("coût du permis", "Combien coûte le permis de conduire pour un étudiant ?", True),
    ("frais CNI", "coût de la carte nationale d'identité", True),
    ("frais CNI", "délai CNI", False),
    ("frais CNI", "frais passeport", False),
    ("délai de délivrance du passeport", "Où déposer ma demande de passeport ?", False),
    ("cni", "frais cni", False),
])
def test_similarity_decisions(a, b, merged):
    assert (similarity(tokens(a), tokens(b)) >= 0.6) is merged


def test_similarity_edge_cases():
    assert similarity(frozenset(), tokens("cni")) == 0.0
    assert similarity(tokens("cni"), tokens("cni")) == 1.0


def test_topic_key_is_order_independent_and_has_fallback():
    assert topic_key(tokens("permis coût")) == topic_key(tokens("coût permis"))
    assert topic_key(frozenset(), "?!") == ""
    assert topic_key(frozenset(), "Quoi ?") == "quoi"


def test_mask_and_clean():
    assert "655123456" not in mask_sensitive("mon numéro 655123456")
    assert "@" not in mask_sensitive("jean@mail.cm")
    assert mask_sensitive("10.000 FCFA en 48 heures") == "10.000 FCFA en 48 heures"
    assert clean_text("  a \n b  ", 10) == "a b"
    out = clean_text("x" * 50, 10)
    assert len(out) == 10 and out.endswith("…")


@pytest.mark.parametrize("expected,got,result", [
    ({"document_id": "D", "page": 1}, "refused", "source_missing"),
    ("DOC-1#p2", "refused", "source_missing"),
    ({"document_id": "D"}, "partial", "partial_answer"),
    ({"document_id": "D"}, "approved", "wrong_source"),
    ({"document_id": "D"}, "DOC-AUTRE", "wrong_source"),
    ("refused", "approved", "unexpected_answer"),
    ("refused", "partial", "unexpected_answer"),
    ("refused", "refused", None),
    ("Refusé", "Refused", None),
    ({"status": "refused"}, {"status": "approved"}, "unexpected_answer"),
    (None, "approved", None),
    ("", "refused", None),
])
def test_classify_failure(expected, got, result):
    assert classify_failure(expected, got) == result


def test_expects_refusal():
    assert expects_refusal("refused") and expects_refusal({"status": "refus"})
    assert not expects_refusal({"document_id": "D"}) and not expects_refusal(None)


@pytest.mark.parametrize("text,sub", [
    ("frais de la CNI", "national_identity_card"),
    ("acte de naissance pour la CNI", "national_identity_card"),
    ("passeport biométrique", "passport"),
    ("coût du permis", "driving_license"),
    ("copie d'acte de naissance", "civil_status"),
    ("impôt sur le revenu", "taxes"),
    ("paiement via TresorPay", "public_treasury"),
    ("loi sur les données personnelles", "personal_data_protection"),
    ("horaires d'ouverture", "general"),
])
def test_infer_subdomain(text, sub):
    assert infer_subdomain(text) == sub


def test_suggestions():
    assert suggest_document(["coût du permis"]) == "barème des frais"
    assert suggest_document(["délai CNI", "frais CNI"]) == "barème des frais"  # FRAIS prioritaire
    assert suggest_document(["loi sur les données personnelles"]) == "texte sur la protection des données personnelles"
    assert suggest_document(["acte de naissance"]) == "fiche officielle décrivant la procédure"
    assert suggest_document([]) == "fiche officielle décrivant la procédure"
    assert suggest_institution("national_identity_card") == "DGSN (à confirmer)"
    assert suggest_institution("general") == "à confirmer" == suggest_institution("inconnu")
