"""OCR (Tesseract) pour les PDF scannés, et extraction complète d'un document au format T2 de la Phase 2.

Le plus petit branchement possible dans l'extraction de la Phase 2 (boucle sur les pages d'un PDF) :

    from kb_update.ocr import needs_ocr, ocr_pdf_page
    texte = page.get_text()
    if needs_ocr(texte):
        texte, confiance = ocr_pdf_page(page)
"""
import io
import os
import re
from datetime import datetime

import pymupdf
import pytesseract
from PIL import Image

LANG = os.environ.get("OCR_LANG", "fra")
DPI = int(os.environ.get("OCR_DPI", "300"))
MIN_CHARS = 30      # en dessous, une page est considérée comme une image (scan)
CONF_MIN = 60.0     # confiance moyenne Tesseract en dessous de laquelle on avertit

if os.environ.get("TESSERACT_CMD"):  # chemin explicite (utile sous Windows)
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]


class OcrIndisponible(RuntimeError):
    pass


def verifier_tesseract(lang=LANG):
    """Échoue avec un message clair si Tesseract ou sa langue est absent."""
    try:
        langues = pytesseract.get_languages(config="")
    except pytesseract.TesseractNotFoundError:
        raise OcrIndisponible(
            "Tesseract est introuvable. Installation : Ubuntu/Debian `sudo apt install tesseract-ocr tesseract-ocr-fra` ; "
            "macOS `brew install tesseract tesseract-lang` ; Windows : installeur UB Mannheim, puis variable TESSERACT_CMD."
        )
    if lang not in langues:
        raise OcrIndisponible(f"Langue OCR '{lang}' absente (disponibles : {', '.join(langues)}). "
                              "Ubuntu/Debian : `sudo apt install tesseract-ocr-fra`.")


def needs_ocr(texte, min_chars=MIN_CHARS):
    return len((texte or "").strip()) < min_chars


def nettoyer(texte):
    """Même nettoyage que T2 : caractères de contrôle, mots coupés en fin de ligne, espaces, sauts de ligne."""
    texte = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", texte or "")
    texte = re.sub(r"(\w)-\n(\w)", r"\1\2", texte)      # « identi-\ntaire » -> « identitaire »
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r" *\n *", "\n", texte)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip()


def ocr_image(image, lang=LANG):
    """OCR d'une image PIL. Retourne (texte, confiance_moyenne_sur_100)."""
    d = pytesseract.image_to_data(image, lang=lang, config="--psm 6", output_type=pytesseract.Output.DICT)
    confs = [float(c) for c, t in zip(d["conf"], d["text"]) if t.strip() and float(c) >= 0]
    texte = pytesseract.image_to_string(image, lang=lang, config="--psm 6")
    return texte, (sum(confs) / len(confs) if confs else 0.0)


def ocr_pdf_page(page, lang=LANG, dpi=DPI):
    """OCR d'une page PyMuPDF. Retourne (texte_nettoyé, confiance_moyenne)."""
    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), colorspace=pymupdf.csGRAY)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    texte, conf = ocr_image(image, lang)
    return nettoyer(texte), conf


def extract_pdf(path, lang=LANG, dpi=DPI):
    """Extrait un PDF page par page, avec OCR automatique des pages sans texte.

    Retourne (pages, warnings, pages_ocr) ; pages = [{"page_number", "text"}].
    """
    pages, warnings, pages_ocr, verifie = [], [], [], False
    with pymupdf.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            texte = nettoyer(page.get_text())
            if needs_ocr(texte):
                if not verifie:
                    verifier_tesseract(lang)
                    verifie = True
                texte, conf = ocr_pdf_page(page, lang, dpi)
                pages_ocr.append(i)
                if not texte.strip():
                    warnings.append(f"page {i} : aucun texte, même après OCR")
                elif conf < CONF_MIN:
                    warnings.append(f"page {i} : OCR peu fiable (confiance moyenne {conf:.0f}/100), à relire")
            pages.append({"page_number": i, "text": texte})
    return pages, warnings, pages_ocr


def _extract_docx(path):
    import docx
    d = docx.Document(path)
    blocs = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            blocs.append(" | ".join(c.text.strip() for c in row.cells))
    return [{"page_number": 1, "text": nettoyer("\n".join(blocs))}], [], []


def _extract_txt(path):
    import chardet
    brut = open(path, "rb").read()
    enc = chardet.detect(brut)["encoding"] or "utf-8"
    return [{"page_number": 1, "text": nettoyer(brut.decode(enc, errors="replace"))}], [], []


def extract_document(document_id, path, lang=LANG, dpi=DPI):
    """Extraction complète au format de sortie T2 (Phase 2). Retourne (dict_t2, ocr_utilise)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        pages, warnings, pages_ocr = extract_pdf(path, lang, dpi)
    elif ext == ".docx":
        pages, warnings, pages_ocr = _extract_docx(path)
    elif ext == ".txt":
        pages, warnings, pages_ocr = _extract_txt(path)
    else:
        raise ValueError(f"extension non prise en charge : {ext}")
    t2 = {
        "document_id": document_id,
        "extraction_date": datetime.now().replace(microsecond=0).isoformat(),
        "pages": pages,
        "full_text": "\n\n".join(p["text"] for p in pages if p["text"]),
        "warnings": warnings,
        "status": "extracted",
    }
    return t2, bool(pages_ocr)
