import cv2
import numpy as np
import pypdfium2 as pdfium

# ============================================================
# CONFIG
# ============================================================

PDF_PATH = "pinax-bsb-p71.pdf"
PAGE_INDEX = 0
RENDER_SCALE = 4.17
OUT_IMAGE = "title_and_separator.png"

document = pdfium.PdfDocument(PDF_PATH)

image = document[PAGE_INDEX].render(scale=RENDER_SCALE).to_pil()
image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

blur = cv2.GaussianBlur(gray, (91, 91), 0)

treshold = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]  

# remove white pixel border
# carde noir autour de la page
treshold[:, :200] = 0 # remove left border
treshold[:, -200:] = 0 # remove right border
treshold[:200, :] = 0 # remove top border
treshold[-200:, :] = 0 # remove bottom border


kernal = cv2.getStructuringElement(cv2.MORPH_RECT, (65, 15))
dilation = cv2.dilate(treshold, kernal, iterations=4)

cv2.imwrite("debug_paragraphs_dilation.png", dilation)

cnts = cv2.findContours(dilation, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = cnts[0] if len(cnts) == 2 else cnts[1]
cnts = sorted(cnts, key=lambda x: cv2.boundingRect(x)[0])


for c in cnts:
    x,y,w,h = cv2.boundingRect(c)
    if w > 1000 or h > 1000:
        cv2.rectangle(image_bgr, (x,y), (x+w, y+h), (36,255,12), 40)

cv2.imwrite("debug_paragraphs.png", image_bgr)




































"""

import cv2
import numpy as np
import pypdfium2 as pdfium

from detect_titles import get_cross_column_titles_from_pdf

# ============================================================
# CONFIG
# ============================================================

PDF_PATH = "pinax bsb-p42.pdf"
PAGE_INDEX = 0
RENDER_SCALE = 4.17

OUT_RESULT = "debug_italic_blocks.png"
OUT_BLOCKS = "debug2_blocks.png"

# ============================================================
# RÈGLES ÉDITORIALES / TYPOGRAPHIQUES
# ============================================================

def is_list_block(gray, box):

    #Détecte les listes romaines :
    #- colonnes denses
    #- forte verticalité
    #- jamais de l’italique explicatif
    
    x, y, w, h = box
    roi = gray[y:y+h, x:x+w]

    bw = cv2.threshold(
        roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    vert = np.sum(bw, axis=0)
    hori = np.sum(bw, axis=1)

    return vert.mean() > 1.5 * hori.mean()


def is_editorial_italic(box, title_boxes):
    
    #Italique éditorial :
    #- bloc immédiatement sous un titre centré
    #(GLADIOLUS, HYACINTHUS)
    x, y, w, h = box

    for tx, ty, tw, th in title_boxes:
        if 0 < (y - (ty + th)) < 260 and w > 2000:
            return True

    return False


def is_glyph_italic(gray, box):
    
    #Italique explicatif long :
    #- paragraphes continus
    #- glyphes globalement plus inclinés

    x, y, w, h = box
    roi = gray[y:y+h, x:x+w]

    bw = cv2.threshold(
        roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    n, _, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    ratios = []

    for i in range(1, n):
        _, _, gw, gh, area = stats[i]
        if area < 50 or gh < 12 or gw < 4:
            continue
        ratios.append(gh / gw)

    if len(ratios) < 20:
        return False

    return np.median(ratios) > 1.6


# ============================================================
# MAIN
# ============================================================

def main():

    # -------------------------
    # Chargement PDF
    # -------------------------
    document = pdfium.PdfDocument(PDF_PATH)
    pil_img = document[PAGE_INDEX].render(scale=RENDER_SCALE).to_pil()

    image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # -------------------------
    # Binarisation
    # -------------------------
    blur = cv2.GaussianBlur(gray, (111, 111), 0)
    mask = cv2.threshold(
        blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    mask[:, :200] = 0
    mask[:, -200:] = 0
    mask[:200, :] = 0
    mask[-200:, :] = 0

    # -------------------------
    # Titres
    # -------------------------
    _, title_boxes = get_cross_column_titles_from_pdf(
        PDF_PATH,
        page_index=PAGE_INDEX,
        render_scale=RENDER_SCALE
    )

    print(f"[INFO] {len(title_boxes)} titres détectés")

    # -------------------------
    # Segmentation des blocs
    # -------------------------
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (65, 15))
    dilated = cv2.dilate(mask, kernel, iterations=4)

    contours, _ = cv2.findContours(
        dilated,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    # -------------------------
    # DEBUG blocs bruts
    # -------------------------
    dbg_blocks = image.copy()
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        cv2.rectangle(dbg_blocks, (x, y), (x+w, y+h), (255, 0, 255), 4)
    cv2.imwrite(OUT_BLOCKS, dbg_blocks)

    print("[DEBUG] Blocs bruts écrits :", OUT_BLOCKS)

    # -------------------------
    # Classification finale
    # -------------------------
    result = image.copy()
    italic_blocks = []

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)

        if w < 1800 or h < 100:
            continue

        if is_list_block(gray, (x,y,w,h)):
            cv2.rectangle(result, (x,y), (x+w,y+h), (0,255,0), 20)
            continue

        italic = (
            is_editorial_italic((x,y,w,h), title_boxes) or
            is_glyph_italic(gray, (x,y,w,h))
        )

        if italic:
            italic_blocks.append((x,y,w,h))
            cv2.rectangle(result, (x,y), (x+w,y+h), (0,0,255), 40)
        else:
            cv2.rectangle(result, (x,y), (x+w,y+h), (0,255,0), 20)

    # -------------------------
    # Sortie
    # -------------------------
    print(f"[RESULT] {len(italic_blocks)} blocs italiques détectés")
    for b in italic_blocks:
        print(" Italique:", b)

    cv2.imwrite(OUT_RESULT, result)
    print("[OK] Résultat écrit :", OUT_RESULT)


if __name__ == "__main__":
    main()
"""