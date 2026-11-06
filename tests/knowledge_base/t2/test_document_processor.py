import json
from pathlib import Path

import pytest
from docx import Document as WordDocument

from backend.knowledge_base.collectors_t2 import DocumentCollector, DocumentMetadata
from backend.knowledge_base.processors import DocumentProcessor, DocumentNotFoundError


@pytest.fixture
def setup_kb(tmp_path):
    data_root = tmp_path / "data"
    collector = DocumentCollector(data_root=data_root)
    processor = DocumentProcessor(data_root=data_root)
    metadata = DocumentMetadata(
        title="Test procédure CNI",
        domain="public_services",
        subdomain="national_identity_card",
        institution="DGSN",
        document_type="procedure",
        reliability="official",
    )
    return tmp_path, data_root, collector, processor, metadata


def test_process_txt_and_save_json(setup_kb):
    tmp_path, data_root, collector, processor, metadata = setup_kb
    source = tmp_path / "procedure.txt"
    source.write_text("  Première ligne  \r\n\r\n\r\n Deuxième   ligne ", encoding="utf-8")
    imported = collector.import_document(source, metadata)

    result = processor.process_document(imported.document_id)

    assert result.status == "processed"
    assert result.segment_count == 1
    assert result.character_count == len("Première ligne\n\nDeuxième ligne")
    output = data_root / result.output_path
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["content"]["text"] == "Première ligne\n\nDeuxième ligne"
    assert payload["source"]["sha256"] == imported.sha256
    assert (data_root / imported.stored_path).exists()  # l'original est conservé


def test_process_docx_including_table(setup_kb):
    tmp_path, _, collector, processor, metadata = setup_kb
    source = tmp_path / "procedure.docx"
    doc = WordDocument()
    doc.add_paragraph("Pièces à fournir")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Acte de naissance"
    table.cell(0, 1).text = "Copie certifiée"
    doc.save(source)
    imported = collector.import_document(source, metadata)

    result = processor.process_document(imported.document_id)
    payload = json.loads((tmp_path / "data" / result.output_path).read_text(encoding="utf-8"))
    assert "Pièces à fournir" in payload["content"]["text"]
    assert "Acte de naissance | Copie certifiée" in payload["content"]["text"]


def test_unknown_document_id(setup_kb):
    _, _, _, processor, _ = setup_kb
    with pytest.raises(DocumentNotFoundError):
        processor.process_document("DOC-DOESNOTEXIST")


def test_blank_pdf_is_flagged_for_ocr(setup_kb):
    from pypdf import PdfWriter

    tmp_path, _, collector, processor, metadata = setup_kb
    source = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with source.open("wb") as file:
        writer.write(file)
    imported = collector.import_document(source, metadata)

    result = processor.process_document(imported.document_id)
    assert result.status == "needs_ocr_or_review"
    assert any("OCR" in warning for warning in result.warnings)


def test_process_all_by_domain(setup_kb):
    tmp_path, _, collector, processor, metadata = setup_kb
    source = tmp_path / "guide.txt"
    source.write_text("Guide officiel", encoding="utf-8")
    collector.import_document(source, metadata)

    results = processor.process_all(domain="public_services")
    assert len(results) == 1
    assert results[0].status == "processed"
