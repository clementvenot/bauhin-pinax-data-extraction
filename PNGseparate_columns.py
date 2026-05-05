import cv2
import numpy as np

# =========================
# Chargement image PNG
# =========================
imagePath = "aroi_5.png"
image_bgr = cv2.imread(imagePath)

if image_bgr is None:
    raise FileNotFoundError(f"Impossible de charger l'image : {imagePath}")

# =========================
# Prétraitement
# =========================
gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (1, 1), 0)

thresh = cv2.threshold(
    blur, 0, 255,
    cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
)[1]

kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
dilated = cv2.dilate(thresh, kernel, iterations=1)

invert = cv2.bitwise_not(dilated)
erode = cv2.erode(invert, kernel, iterations=10)
binary = cv2.bitwise_not(erode)

# =========================
# Contours
# =========================
cnts = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = cnts[0] if len(cnts) == 2 else cnts[1]
cnts = sorted(cnts, key=lambda x: cv2.boundingRect(x)[0])

img_h, img_w = image_bgr.shape[:2]

# =========================
# Zone centrale (25 %)
# =========================
center_zone_width = int(img_w * 0.25)
center_start = (img_w - center_zone_width) // 2
center_end = center_start + center_zone_width

# =========================
# Filtrage des rectangles
# =========================
valid_rects = []

for c in cnts:
    x, y, w, h = cv2.boundingRect(c)
    cx = x + w // 2

    if img_h > 1300:
        condition = (
            w < img_w * 0.03 and
            h > img_h * 0.1 and
            w <= h / 2 and
            center_start <= cx <= center_end 
        )
    else:
        condition = (
            w < img_w * 0.05 and
            h > img_h * 0.3 and
            w <= h / 2 and
            center_start <= cx <= center_end
        )

    if condition:
        valid_rects.append((x, y, w, h, cx))
        cv2.rectangle(
            image_bgr,
            (x, y),
            (x + w, y + h),
            (255, 0, 0),
            3
        )

# =========================
# Regroupement par axe vertical
# =========================
x_threshold = int(img_w * 0.01)  # tolérance X (0.5 % largeur)
groups = []

for rect in valid_rects:
    x, y, w, h, cx = rect
    added = False

    for group in groups:
        group_cx = np.mean([r[4] for r in group])
        if abs(cx - group_cx) < x_threshold:
            group.append(rect)
            added = True
            break

    if not added:
        groups.append([rect])

# =========================
# Fusion et dessin
# =========================
for group in groups:
    x_min = min(r[0] for r in group)
    y_min = min(r[1] for r in group)
    x_max = max(r[0] + r[2] for r in group)
    y_max = max(r[1] + r[3] for r in group)

    height = y_max - y_min

    if height > img_h * 0.6:  # filtrage par hauteur (0 % de l'image)
        cv2.rectangle(
            image_bgr,
            (x_min, y_min),
            (x_max, y_max),
            (0, 255, 0),
            20
            )

# =========================
# Sauvegarde
# =========================
cv2.imwrite("123.png", image_bgr)