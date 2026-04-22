from pathlib import Path
import re

import pytesseract
import pypdfium2 as pdfium


# ==========================================================
# CONFIG TESSERACT (macOS Homebrew)
# ==========================================================
HOMEBREW_TESSERACT = "/opt/homebrew/bin/tesseract"
if Path(HOMEBREW_TESSERACT).exists():
    pytesseract.pytesseract.tesseract_cmd = HOMEBREW_TESSERACT


# ==========================================================
# NORMALISATION OCR
# ==========================================================

def normalize_basic(text: str) -> str:
    replacements = {
        "¢": "§",
        "$": "§",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "æ": "ae",
        "Æ": "AE",
    }
    for src, tgt in replacements.items():
        text = text.replace(src, tgt)

    text = re.sub(r"[ \t]+", " ", text)
    return text


def fix_hyphenation(text: str) -> str:
    text = re.sub(r"-\n\s*", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def remove_noise(text: str) -> str:
    return re.sub(r"[@_]", "", text)


def normalize_long_s(text: str) -> str:
    return re.sub(r"(?<=[a-z])f(?=[a-z])", "ſ", text)


def normalize_spica(text: str) -> str:
    return re.sub(r"\bfpic", "ſpic", text)


def normalize_taxon_ocr(text: str) -> str:
    replacements = {
        "Tuncus": "Juncus",
        "Junceus": "Juncus",
        "Junc ": "Juncus ",
        "Schenus": "Schoenus",
        "Holoschenos": "Holoschoenus",
        "Holoscheenos": "Holoschoenus",
        "Oxyscbarnos": "Oxyschoenos",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def normalize_for_matching(s: str) -> str:
    s = s.replace("ſ", "s")
    s = s.replace("æ", "ae").replace("Æ", "AE")
    s = re.sub(r"[^A-Za-z ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ==========================================================
# FILTRES TAXONOMIQUES
# ==========================================================

STOPWORDS = {
}

GENUS_HINTS = {
}


def is_valid_taxon(candidate: str) -> bool:
    norm = normalize_for_matching(candidate).lower()
    words = norm.split()

    if len(words) == 0 or len(words) > 3:
        return False

    if any(w in STOPWORDS for w in words):
        return False

    if not any(w in GENUS_HINTS for w in words):
        return False

    return True


# ==========================================================
# EXTRACTION
# ==========================================================

def extract_taxa(text: str, page: int):
    taxa = []

    for line in text.splitlines():

        matches = re.findall(
            r"\b([A-Z][a-zſ]{3,}(?:\s+[a-zſ]{3,}){0,2})",
            line
        )

        for m in matches:
            if not is_valid_taxon(m):
                continue

            taxa.append({
                "taxon_ocr": m,
                "taxon_normalized": normalize_for_matching(m),
                "page": page,
            })

    return taxa


def deduplicate_taxa(taxa):
    grouped = {}

    for t in taxa:
        key = t["taxon_normalized"].lower()

        if len(key) < 5:
            continue

        if key not in grouped:
            grouped[key] = {
                "canonical": t["taxon_normalized"],
                "variants": set(),
                "pages": set(),
            }

        grouped[key]["variants"].add(t["taxon_ocr"])
        grouped[key]["pages"].add(t["page"])

    return [
        {
            "taxon": v["canonical"],
            "variants": list(v["variants"]),
            "pages": sorted(v["pages"]),
        }
        for v in grouped.values()
    ]


# ==========================================================
# OCR PAR ZONES
# ==========================================================

def ocr_page(pdf_path: str, page_index: int = 0) -> str:
    document = pdfium.PdfDocument(pdf_path)
    page_image = document[page_index].render(scale=4.17).to_pil()

    width, height = page_image.size

    margin_x = int(width * 0.08)

    left_col = page_image.crop((margin_x, 0, width // 2, height))
    right_col = page_image.crop((width // 2, 0, width - margin_x, height))

    config = "--oem 1 --psm 6 -c preserve_interword_spaces=1"

    text_left = pytesseract.image_to_string(left_col, lang="lat", config=config)
    text_right = pytesseract.image_to_string(right_col, lang="lat", config=config)

    return text_left + "\n" + text_right


# ==========================================================
# PIPELINE COMPLET
# ==========================================================

def process_page(pdf_path: str, page_number: int):
    raw_text = ocr_page(pdf_path, page_index=0)

    text = normalize_basic(raw_text)
    text = fix_hyphenation(text)
    text = remove_noise(text)
    text = normalize_long_s(text)
    text = normalize_spica(text)
    text = normalize_taxon_ocr(text)

    taxa_raw = extract_taxa(text, page=page_number)
    taxa = deduplicate_taxa(taxa_raw)

    return taxa



# ==========================================================
# EXECUTION
# ==========================================================


pdf_path = "pg39.pdf"
page_number = 39

taxa = process_page(pdf_path, page_number)

for t in taxa:
    print("\nTAXON:", t["taxon"])
    print("  Variants OCR:", t["variants"])


# afficher toute la page pour vérification
print("\nTEXTE COMPLET DE LA PAGE:\n")
print(ocr_page(pdf_path, page_index=0))
        

    