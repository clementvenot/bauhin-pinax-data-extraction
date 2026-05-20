from pathlib import Path
from collections import defaultdict
import pytesseract
from PIL import Image, ImageDraw

# ==========================================================
# CONFIG TESSERACT (macOS Homebrew)
# ==========================================================
HOMEBREW_TESSERACT = "/opt/homebrew/bin/tesseract"
if Path(HOMEBREW_TESSERACT).exists():
    pytesseract.pytesseract.tesseract_cmd = HOMEBREW_TESSERACT

# configure tesseract to use the Latin language
pytesseract.pytesseract.lang = "lat"


def print_line_indentation(img):

    # extraire les données de tesseract avec les positions des mots
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    grouped_lines = defaultdict(list) 

    # parcourir les mots extraits et les regrouper par ligne
    for index, text in enumerate(data["text"]):
        cleaned_text = text.strip() # retirer les espaces superflus
        if not cleaned_text: # ignorer les lignes vides
            continue

        key = ( # identifier unique de la ligne
            data["page_num"][index],
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        grouped_lines[key].append( # ajouter le mot à la ligne correspondante
            {
                "text": cleaned_text,
                "left": data["left"][index],
                "top": data["top"][index],
                "width": data["width"][index],
                "height": data["height"][index],
            }
        )
    if not grouped_lines:
        print("Aucun texte détecté")
        return

    page_left_margin = min(item["left"] for line in grouped_lines.values() for item in line)
    page_right_edge = img.width

    debug_img = img.convert("RGB")
    draw = ImageDraw.Draw(debug_img)

    for key in sorted(grouped_lines):
        line_items = grouped_lines[key]
        line_text = " ".join(item["text"] for item in line_items)
        line_left = min(item["left"] for item in line_items)
        line_top = min(item["top"] for item in line_items)
        line_right = max(item["left"] + item.get("width", 0) for item in line_items)
        line_bottom = max(item["top"] + item.get("height", 0) for item in line_items)
        indent_px = line_left - page_left_margin
        right_gap_px = page_right_edge - line_right
        draw.rectangle(
            [line_left, line_top, line_right, line_bottom],
            outline="red",
            width=2,
        )
        draw.text(
            (line_left, max(0, line_top - 12)),
            f"{indent_px}px | {right_gap_px}px",
            fill="blue",
        )
        print(
            f"indent={indent_px:>4}px | left={line_left:>4}px | right_gap={right_gap_px:>4}px | {line_text}"
        )

    debug_img.save("ocr_debug.png")
    print("Image debug sauvée dans ocr_debug.png")

img = Image.open("rect_003_uid_3_bicolumn_text_right.png")

print_line_indentation(img)

def delete_bars(ocr_result):
    lines = ocr_result.splitlines()
    lines_without_bars = [line.replace("|", "") for line in lines]
    return "\n".join(lines_without_bars)
#print("bicolumn text left (without bars)")
#print(delete_bars(ocr_result))

"""
img = Image.open("rect_003_uid_3_bicolumn_text_right.png")
ocr_result = pytesseract.image_to_string(img)
print("bicolumn text right")
#print(ocr_result)

img = Image.open("rect_004_uid_4_bicolumn_text_left.png")
ocr_result = pytesseract.image_to_string(img)
print("bicolumn text left")
#print(ocr_result)

img = Image.open("rect_004_uid_4_bicolumn_text_right.png")
ocr_result = pytesseract.image_to_string(img)
print("bicolumn text right")
#print(ocr_result)

img = Image.open("rect_005_uid_5_italic_text.png")
ocr_result = pytesseract.image_to_string(img)
print("italic text")
print(ocr_result)

img = Image.open("rect_001_uid_1_titles.png")
ocr_result = pytesseract.image_to_string(img)
print("=== OCR RESULT ===")
print("titre 1")
print(ocr_result)

img = Image.open("rect_002_uid_2_titles.png")
ocr_result = pytesseract.image_to_string(img)
print("titre 2")
print(ocr_result)
"""