import cv2
import numpy as np
import pypdfium2 as pdfium

# ============================================================
# FONCTION : DÉTECTION TRAIT NOIR VERTICAL AU CENTRE DU ROI
# ============================================================

def has_center_black_vertical_line(
    image_bgr,
    max_abs_angle_deg=6.0,
    min_points=300,
    center_tolerance_ratio=0.1,  # ±10 % de la largeur
):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 1) Binarisation
    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )

    # 2) Masque centré
    x1 = int((0.5 - center_tolerance_ratio) * w)
    x2 = int((0.5 + center_tolerance_ratio) * w)
    mask = np.zeros_like(bw)
    mask[:, x1:x2] = 255
    bw &= mask

    # 3) Morphologie verticale
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(30, h // 20))
    )
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    vertical = cv2.dilate(vertical, np.ones((3, 3), np.uint8))

    # 4) Pixels détectés
    ys, xs = np.where(vertical > 0)
    if len(xs) < min_points:
        return False

    # 5) Régression robuste
    a, b = np.polyfit(ys.astype(np.float32), xs.astype(np.float32), 1)
    angle = np.degrees(np.arctan(a))

    if abs(angle) > max_abs_angle_deg:
        return False

    x_mean = np.mean(xs)
    if abs(x_mean - w / 2) > center_tolerance_ratio * w:
        return False

    return True


# ============================================================
# OUTILS RECTANGLES (SUPPRESSION DES CHEVAUCHEMENTS)
# ============================================================

def rect_area(r):
    x, y, w, h = r
    return w * h


def rects_overlap(r1, r2, overlap_thresh=0.2):
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2

    xa = max(x1, x2)
    ya = max(y1, y2)
    xb = min(x1 + w1, x2 + w2)
    yb = min(y1 + h1, y2 + h2)

    inter_w = max(0, xb - xa)
    inter_h = max(0, yb - ya)
    inter_area = inter_w * inter_h

    if inter_area == 0:
        return False

    return inter_area / min(w1 * h1, w2 * h2) > overlap_thresh


# ============================================================
# CONFIG
# ============================================================

PDF_PATH = "pinax-bsb-p71.pdf"
PAGE_INDEX = 0
RENDER_SCALE = 4.17

# ============================================================
# RENDER PDF
# ============================================================

doc = pdfium.PdfDocument(PDF_PATH)
image = doc[PAGE_INDEX].render(scale=RENDER_SCALE).to_pil()
image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (91, 91), 0)
thresh = cv2.threshold(
    blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
)[1]

# Suppression cadres bord de page
thresh[:, :200] = 0
thresh[:, -200:] = 0
thresh[:200, :] = 0
thresh[-200:, :] = 0

# ============================================================
# DÉTECTION BLOCS
# ============================================================

kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (65, 15))
dilation = cv2.dilate(thresh, kernel, iterations=4)

cv2.imwrite("debug_paragraphs_dilation.png", dilation)

cnts = cv2.findContours(dilation, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = cnts[0] if len(cnts) == 2 else cnts[1]

# ============================================================
# EXTRACTION RECTANGLES CANDIDATS
# ============================================================

rects = []
for c in cnts:
    x, y, w, h = cv2.boundingRect(c)
    if w > 1000 or h > 1000:
        rects.append((x, y, w, h))

# Trier par taille décroissante
rects = sorted(rects, key=rect_area, reverse=True)

# Supprimer chevauchements (le plus grand gagne)
filtered_rects = []
for r in rects:
    keep = True
    for kept in filtered_rects:
        if rects_overlap(r, kept):
            keep = False
            break
    if keep:
        filtered_rects.append(r)

# ============================================================
# ANALYSE ROI + AFFICHAGE
# ============================================================

output = image_bgr.copy()

for x, y, w, h in filtered_rects:
    roi = image_bgr[y:y+h, x:x+w]
    has_sep = has_center_black_vertical_line(roi)

    color = (0, 255, 0) if has_sep else (0, 0, 255)

    cv2.rectangle(
        output,
        (x, y),
        (x + w, y + h),
        color,
        40
    )

cv2.imwrite("debug_paragraphs_with_separator_detection.png", output)