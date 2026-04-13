import ssl
import numpy as np
import easyocr
import pypdfium2 as pdfium

# Contourne la verification SSL pour le telechargement des modeles EasyOCR.
ssl._create_default_https_context = ssl._create_unverified_context

pdf_path = "pinax bsb-p45.pdf"
document = pdfium.PdfDocument(pdf_path)

# 300 DPI environ (300 / 72) pour une meilleure lecture OCR.
image = document[0].render(scale=4.17).to_pil()

# EasyOCR fonctionne sur image numpy.
reader = easyocr.Reader(["en"], gpu=False)
# detail=0 pour n'avoir que le texte, paragraph=True pour regrouper les lignes.
lines = reader.readtext(np.array(image), detail=0, paragraph=True) 
print("\n".join(lines)) # Affiche le texte reconnu, ligne par ligne.