import cv2
import pypdfium2 as pdfium
import numpy as np


# =========================
# Chargement PDF
# =========================

pdfPath = "pinax-bsb-p71.pdf"
document = pdfium.PdfDocument(pdfPath)

image = document[0].render(scale=4.17).to_pil()
image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


# =========================
# Binarisation layout
# =========================

gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (71, 71), 0)
mask = cv2.threshold(
    blur, 0, 255,
    cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
)[1]


# =========================
# Détection séparateur central
# =========================

def find_separator_x(mask):
    h, w = mask.shape
    col_sum = np.sum(mask > 0, axis=0).astype(np.float32)

    window = 31
    kernel = np.ones(window, dtype=np.float32) / window
    col_sum_smooth = np.convolve(col_sum, kernel, mode="same")

    mid = w // 2
    search_half = int(0.2 * w)
    start = max(0, mid - search_half)
    end = min(w, mid + search_half)

    return int(start + np.argmin(col_sum_smooth[start:end]))


separator_x = find_separator_x(mask)


# =========================
# Colonnes pleine hauteur (✅ ALGO DU 1ER SCRIPT)
# =========================

def build_full_height_columns(mask_shape, separator_x, gutter):
    h, w = mask_shape

    columns = []

    left_x1 = max(1, separator_x - gutter)
    right_x0 = min(w - 1, separator_x + gutter)

    if left_x1 > 0:
        columns.append(("left", 0, 0, left_x1, h))

    if right_x0 < w:
        columns.append(("right", right_x0, 0, w - right_x0, h))

    return columns


gutter = 20
columns = build_full_height_columns(mask.shape, separator_x, gutter)


# =========================
# Détection titres traversants (inchangé)
# =========================

def merge_boxes_by_vertical_gap(boxes, max_gap=12):
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: b[1])
    merged = []

    for x, y, w, h in boxes:
        x2, y2 = x + w, y + h
        if not merged:
            merged.append([x, y, x2, y2])
            continue

        last = merged[-1]
        if y <= last[3] + max_gap:
            last[0] = min(last[0], x)
            last[1] = min(last[1], y)
            last[2] = max(last[2], x2)
            last[3] = max(last[3], y2)
        else:
            merged.append([x, y, x2, y2])

    return [(a, b, c - a, d - b) for a, b, c, d in merged]


def vertical_distance(a, b):
    return max(0, max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3])))


def detect_cross_column_titles(mask, separator_x):
    h, w = mask.shape

    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, w // 35), 3))
    merged = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=3)

    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(35, w // 28), 5))
    merged = cv2.dilate(merged, dilate_kernel, iterations=2)

    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_w = max(120, int(0.18 * w))
    min_h = max(8, int(0.006 * h))
    max_h = max(35, int(0.12 * h))
    gutter_band = max(20, int(0.02 * w))
    center_tol = max(90, int(0.22 * w))

    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bh < min_h or bh > max_h:
            continue
        if bw < min_w:
            continue

        crosses = not (
            (x + bw) < separator_x - gutter_band or
            x > separator_x + gutter_band
        )

        if crosses or abs((x + bw / 2) - separator_x) < center_tol:
            boxes.append((x, y, bw, bh))

    return merge_boxes_by_vertical_gap(boxes)


title_boxes = detect_cross_column_titles(mask, separator_x)


# =========================
# Visualisation
# =========================

debug = image_bgr.copy()
h, w, _ = image_bgr.shape

# Séparateur
cv2.line(debug, (separator_x, 0), (separator_x, h - 1), (0, 0, 255), 2)

# Colonnes
for name, x, y, w, h in columns:
    cv2.rectangle(debug, (x, y), (x + w, y + h), (36, 255, 12), 3)

# Titres
for x, y, w, h in title_boxes:
    cv2.rectangle(debug, (x, y), (x + w, y + h), (255, 0, 0), 3)

cv2.imwrite("page39_columns_titles.png", debug)

