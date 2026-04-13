from pathlib import Path

import pytesseract
import pypdfium2 as pdfium

HOMEBREW_TESSERACT = "/opt/homebrew/bin/tesseract"
if Path(HOMEBREW_TESSERACT).exists():
	pytesseract.pytesseract.tesseract_cmd = HOMEBREW_TESSERACT

#pdf_path = "pinax bsb.pdf"
pdf_path ="Caspari Bauhini Viri Clariss. Pinax Theatri Botanici sive Index in Theophrasti Dioscoridis Plinii et botanicorum qui a seculo scripserunt opera.pdf"
document = pdfium.PdfDocument(pdf_path)

# 300 DPI environ (300 / 72) pour une meilleure lecture OCR.
print(pytesseract.image_to_string(document[52].render(scale=4.17).to_pil()))