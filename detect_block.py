import cv2
import numpy as np
import pypdfium2 as pdfium

# =========================
# Chargement image PNG
# =========================
image_path = "ert.pdf"
page_index = 357
render_scale = 4.17

document = pdfium.PdfDocument(image_path)
image_pil = document[page_index].render(scale=render_scale).to_pil()

if image_pil is None:
    raise FileNotFoundError(f"Impossible de charger l'image : {image_path}")

# Convert PIL image to NumPy array
image_bgr = np.array(image_pil)

gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (11, 1), 0)
tresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
kernal = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
dilated = cv2.dilate(tresh, kernal, iterations=1)

ctns = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = ctns[0] if len(ctns) == 2 else ctns[1]
cnts = sorted(cnts, key=lambda x: cv2.boundingRect(x)[0])
height, width = image_bgr.shape[:2]
#print(0.1 * width)

for c in cnts:
    x, y, w, h = cv2.boundingRect(c)
    if (True):
        cv2.rectangle(image_bgr, (x, y), (x + w, y + h), (0, 255, 0), 20)
cv2.imwrite("123.png", image_bgr)