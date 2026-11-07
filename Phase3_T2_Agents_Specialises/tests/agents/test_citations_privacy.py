import pytest

from backend.agents.citations import expand_groups, extract_indices, remap_citations
from backend.agents.privacy import EMAIL_MASK, MASK, mask_sensitive


def test_expand_groups():
    assert expand_groups("a [1, 2] b [3;4] c [5]") == "a [1][2] b [3][4] c [5]"


def test_extract_indices():
    assert extract_indices("x [2] y [1, 3] z [2]") == [2, 1, 3, 2]


def test_remap_renumbers_by_first_appearance():
    text, used, invalid = remap_citations("A [3]. B [1][3]. C [4].", 4)
    assert text == "A [1]. B [2][1]. C [3]."
    assert used == [3, 1, 4] and invalid == []


def test_remap_removes_invalid_and_reports_them():
    text, used, invalid = remap_citations("A [9]. B [0]. C [2].", 3)
    assert text == "A. B. C [1]."
    assert used == [2] and invalid == [9, 0]


def test_remap_dedupes_adjacent_duplicates_and_groups():
    text, used, _ = remap_citations("A [2, 2]. B [1] [1].", 2)
    assert text == "A [1]. B [2]."
    assert used == [2, 1]


def test_remap_leaves_non_numeric_brackets_alone():
    text, used, invalid = remap_citations("Voir [annexe] et [1].", 1)
    assert text == "Voir [annexe] et [1]." and used == [1] and invalid == []


def test_remap_without_citations():
    assert remap_citations("Texte sans renvoi.", 3) == ("Texte sans renvoi.", [], [])


@pytest.mark.parametrize("raw", [
    "Mon numéro est le 655123456",
    "Appelez le +237 655 12 34 56 svp",
    "Appelez le 6 55 12 34 56 svp",
    "mon cni 123456789012",
    "joignable au 00237655123456",
])
def test_phone_and_id_numbers_masked(raw):
    masked, changed = mask_sensitive(raw)
    assert changed and MASK in masked
    assert not any(ch.isdigit() for ch in masked.replace("[NUMERO_MASQUE]", ""))


def test_email_masked():
    masked, changed = mask_sensitive("écrivez à jean.dupont@mail.cm merci")
    assert changed and EMAIL_MASK in masked and "@" not in masked


@pytest.mark.parametrize("raw", [
    "Quelle est la date limite du 12/05/2025 ?",
    "Combien coûte la CNI à 10.000 FCFA ?",
    "Valable 10 ans, produite en 48 heures",
])
def test_normal_numbers_untouched(raw):
    assert mask_sensitive(raw) == (raw, False)


def test_remap_keeps_french_spacing_before_punctuation():
    text, used, _ = remap_citations("Pièces : acte [2] ; coût ? Oui !", 2)
    assert text == "Pièces : acte [1] ; coût ? Oui !" and used == [2]
    text, _, invalid = remap_citations("Voir [8] suite [1] fin.", 1)
    assert text == "Voir suite [1] fin." and invalid == [8]
