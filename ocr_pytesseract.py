from pathlib import Path
import pytesseract
from PIL import Image

# ==========================================================
# CONFIG TESSERACT (macOS Homebrew)
# ==========================================================
HOMEBREW_TESSERACT = "/opt/homebrew/bin/tesseract"
if Path(HOMEBREW_TESSERACT).exists():
    pytesseract.pytesseract.tesseract_cmd = HOMEBREW_TESSERACT

# configure tesseract to use the Latin language
pytesseract.pytesseract.lang = "lat"

img = Image.open("rect_001_uid_1_titles.png")
ocr_result = pytesseract.image_to_string(img)
print("=== OCR RESULT ===")
print("titre 1")
#print(ocr_result)

img = Image.open("rect_002_uid_2_titles.png")
ocr_result = pytesseract.image_to_string(img)
print("titre 2")
#print(ocr_result)

img = Image.open("rect_003_uid_3_bicolumn_text_left.png")
ocr_result = pytesseract.image_to_string(img)
print("bicolumn text left")
#print(ocr_result)

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