import cv2
import numpy as np
import pypdfium2 as pdfium

from detect_separation import get_column_separator_from_pdf
from detect_titles import get_cross_column_titles_from_pdf



# ============================================================
# CONFIG
# ============================================================

PDF_PATH = "pinax bsb-p68.pdf"
PAGE_INDEX = 0
RENDER_SCALE = 4.17
OUT_IMAGE = "title_and_separator.png"


# ============================================================
# MAIN
# ============================================================

def main():
    # -------- Chargement image PDF --------
    document = pdfium.PdfDocument(PDF_PATH)
    pil_img = document[PAGE_INDEX].render(scale=RENDER_SCALE).to_pil()
    image_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    h, w = image_bgr.shape[:2]

    # -------- Détection séparation --------
    separator = get_column_separator_from_pdf(
        pdf_path=PDF_PATH,
        page_index=PAGE_INDEX,
        render_scale=RENDER_SCALE
    )

    # -------- Détection titres --------
    title_count, title_boxes = get_cross_column_titles_from_pdf(
        pdf_path=PDF_PATH,
        page_index=PAGE_INDEX,
        render_scale=RENDER_SCALE
    )



    # -------- Overlay --------
    overlay = image_bgr.copy()

    # Titres (bleu)
    for x, y, bw, bh in title_boxes:
        cv2.rectangle(
            overlay,
            (x, y),
            (x + bw, y + bh),
            (255, 0, 0),
            3
        )

    # Séparation (rouge)
    if separator["detected"]:
        cv2.line(
            overlay,
            (int(separator["x1"]), int(separator["y1"])),
            (int(separator["x2"]), int(separator["y2"])),
            (0, 0, 255),
            3
        )
    else:
        x = int(separator["x"])
        cv2.line(
            overlay,
            (x, 0),
            (x, h - 1),
            (0, 0, 255),
            3
        )

    # -------- Sauvegarde --------
    cv2.imwrite(OUT_IMAGE, overlay)

    print(f"[OK] Titres détectés : {title_count}")
    print(f"[OK] Image exportée : {OUT_IMAGE}")

if __name__ == "__main__":
    main()