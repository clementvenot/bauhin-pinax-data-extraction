import cv2
import numpy as np

# =========================
# Chargement image PNG
# =========================
imagePath = "roi_0.png"   # ← image PNG
image_bgr = cv2.imread(imagePath)

if image_bgr is None:
    raise FileNotFoundError(f"Impossible de charger l'image : {imagePath}")

# =========================
# Détection rectangles 
# =========================

gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (1, 111), 0)
tresh = cv2.threshold(
    blur, 0, 255,
    cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
)[1]

kernal = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 113))

dilated = cv2.dilate(tresh, kernal, iterations=1)

#cv2.imwrite("123.png", dilated)

cnts = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = cnts[0] if len(cnts) == 2 else cnts[1]
cnts = sorted(cnts, key=lambda x: cv2.boundingRect(x)[0])

img_h, img_w = image_bgr.shape[:2]

# Zone centrale 10 %
center_zone_width = int(img_w * 0.25)
center_start = (img_w - center_zone_width) // 2
center_end = center_start + center_zone_width

candidates = []
min_total_height = img_h * 0.5
x_tolerance = 30  # tolérance pour considérer "même verticale"

for c in cnts:
    x, y, w, h = cv2.boundingRect(c)
    rect_center_x = x + w // 2

    if (w < 200
        and h > img_h * 0.15
        and center_start <= rect_center_x <= center_end
    ):
        candidates.append((x, y, w, h))

validated_rects = []

groups = []

for rect in candidates:
    x, y, w, h = rect
    placed = False

    for group in groups:
        gx, _, gw, _ = group[0]
        if abs(x - gx) <= x_tolerance:
            group.append(rect)
            placed = True
            break

    if not placed:
        groups.append([rect])

for group in groups:
    total_height = sum(r[3] for r in group)

    if total_height >= min_total_height:
        for (x, y, w, h) in group:
            cv2.rectangle(
                image_bgr,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                20
            )

# show 10% central zone
cv2.rectangle(image_bgr, (center_start, 0), (center_end, img_h), (255, 0, 0), 5)

cv2.imwrite("123.png", image_bgr)