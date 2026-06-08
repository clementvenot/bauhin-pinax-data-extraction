import cv2
import numpy as np
import pypdfium2 as pdfium

# ============================================================
# OUTILS MASKS (UN MASK = UN OBJECTIF)
# ============================================================

def build_title_mask(image_bgr):
    """Mask pleine page – titres uniquement"""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (111, 111), 0)
    mask = cv2.threshold(
        blur, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    #cv2.imwrite("debug_title_mask.png", mask)
    return mask

def build_block_mask(image_bgr):
    """Mask blocs / paragraphes"""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (91, 91), 0)
    mask = cv2.threshold(
        blur, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    # suppression marges
    mask[:200, :] = mask[-200:, :] = 0
    mask[:, :200] = mask[:, -200:] = 0
    return mask

def build_bicolumn_mask(image_bgr):
    """Mask pour les colonnes bi-ou tri-vides"""
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
    mask = cv2.bitwise_not(erode)
    return mask
    
# ============================================================
# DÉTECTION TRAIT NOIR VERTICAL CENTRÉ (BLOCS)
# ============================================================

def has_center_black_vertical_line(image_bgr):
    
    # =========================
    # Prétraitement
    # =========================
    #cv2.imwrite("debug_block_mask.png",image_bgr)
    mask = build_bicolumn_mask(image_bgr)

    # =========================
    # Contours
    # =========================
    cnts = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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
                w < img_w * 0.05 and
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
    # Fusion et sélection du trait le plus centré
    # =========================
    best_center_x = None
    best_distance = None

    for group in groups:
        x_min = min(r[0] for r in group)
        y_min = min(r[1] for r in group)
        x_max = max(r[0] + r[2] for r in group)
        y_max = max(r[1] + r[3] for r in group)

        height = y_max - y_min
        group_center_x = (x_min + x_max) / 2

        if height > img_h * 0.6:  # filtrage par hauteur (0 % de l'image)
            distance = abs(group_center_x - (img_w / 2))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_center_x = int(round(group_center_x))

    return best_center_x

# ============================================================
# OUTILS RECTANGLES
# ============================================================

def rect_area(r):
    x, y, w, h = r
    return w * h


def rects_overlap(r1, r2, overlap_thresh=0.2):
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2

    xa, ya = max(x1, x2), max(y1, y2)
    xb, yb = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)

    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return False

    return inter / min(w1 * h1, w2 * h2) > overlap_thresh


def rects_intersect(r1, r2):
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    return not (
        x1 + w1 < x2 or
        x2 + w2 < x1 or
        y1 + h1 < y2 or
        y2 + h2 < y1
    )


def intersection_ratio(r_block, r_title):
    """Ratio de recouvrement du titre par le bloc"""
    x1, y1, w1, h1 = r_block
    x2, y2, w2, h2 = r_title

    xa = max(x1, x2)
    ya = max(y1, y2)
    xb = min(x1 + w1, x2 + w2)
    yb = min(y1 + h1, y2 + h2)

    inter = max(0, xb - xa) * max(0, yb - ya)
    area_title = w2 * h2

    return inter / area_title if area_title > 0 else 0.0


# ============================================================
# DÉTECTION TITRES INTER-COLONNES
# ============================================================

def merge_boxes_by_vertical_gap(boxes, max_gap=500):
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
            last[:] = [
                min(last[0], x),
                min(last[1], y),
                max(last[2], x2),
                max(last[3], y2)
            ]
        else:
            merged.append([x, y, x2, y2])

    return [(a, b, c - a, d - b) for a, b, c, d in merged]


def group_boxes_by_text_line(boxes, y_gap=12, min_y_overlap=0.35):
    if not boxes:
        return []

    b = [(x, y, x + w, y + h) for (x, y, w, h) in boxes]
    b.sort(key=lambda t: (t[1], t[0]))

    lines = []
    for x1, y1, x2, y2 in b:
        if not lines:
            lines.append([x1, y1, x2, y2])
            continue

        lx1, ly1, lx2, ly2 = lines[-1]
        inter = max(0, min(y2, ly2) - max(y1, ly1))
        hmin = max(1, min(y2 - y1, ly2 - ly1))
        overlap = inter / hmin

        if overlap >= min_y_overlap or y1 <= ly2 + y_gap:
            lines[-1] = [
                min(lx1, x1), min(ly1, y1),
                max(lx2, x2), max(ly2, y2)
            ]
        else:
            lines.append([x1, y1, x2, y2])

    return [(x1, y1, x2 - x1, y2 - y1) for x1, y1, x2, y2 in lines]


def detect_cross_column_titles(mask):
    h, w = mask.shape
    center_x = w // 2

    merged = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(25, w // 35), 3)
        ),
        iterations=3
    )
    merged = cv2.dilate(
        merged,
        cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(35, w // 28), 5)
        ),
        iterations=2
    )

    contours, _ = cv2.findContours(
        merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    min_h = max(8, int(0.006 * h))
    max_h = max(35, int(0.12 * h))
    min_piece_w = max(30, int(0.02 * w))
    min_title_w = max(120, int(0.18 * w))

    gutter = max(20, int(0.02 * w))
    center_tol = max(90, int(0.22 * w))

    pieces = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bh < min_h or bh > max_h:
            continue
        if bw < min_piece_w:
            continue
        pieces.append((x, y, bw, bh))

    lines = group_boxes_by_text_line(pieces)

    titles = []
    for x, y, bw, bh in lines:
        if bw < min_title_w:
            continue

        crosses = not (
            (x + bw) < center_x - gutter or
            x > center_x + gutter
        )
        centered = abs((x + bw / 2) - center_x) < center_tol

        if crosses or centered:
            titles.append((x, y, bw, bh))

    return merge_boxes_by_vertical_gap(titles)


# ============================================================
# FUSION DES RECTANGLES SUR LA MÊME LIGNE
# ============================================================

def same_text_row(r1, r2, y_tol_ratio=0.4):
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2

    c1 = y1 + h1 / 2
    c2 = y2 + h2 / 2

    max_h = max(h1, h2)

    return abs(c1 - c2) <= y_tol_ratio * max_h


def merge_rects(rects):
    merged = []
    rects = sorted(rects, key=lambda r: (r[1], r[0]))

    used = [False] * len(rects)

    for i, r in enumerate(rects):
        if used[i]:
            continue

        x, y, w, h = r
        x2 = x + w
        y2 = y + h

        used[i] = True

        for j in range(i + 1, len(rects)):
            if used[j]:
                continue

            if same_text_row((x, y, w, h), rects[j]):
                rx, ry, rw, rh = rects[j]

                x = min(x, rx)
                y = min(y, ry)
                x2 = max(x2, rx + rw)
                y2 = max(y2, ry + rh)

                w = x2 - x
                h = y2 - y

                used[j] = True

        merged.append((x, y, w, h))

    return merged

# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

import cv2
import numpy as np
import pypdfium2 as pdfium


def pipeline(pdf_path, page_index=0, render_scale=4.17):
    # ============================================================
    # RENDER PAGE
    # ============================================================
    doc = pdfium.PdfDocument(pdf_path)
    pil_img = doc[page_index].render(scale=render_scale).to_pil()
    image_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    PAGE_H, PAGE_W = image_bgr.shape[:2]

    # ============================================================
    # TITRES (BLEU)
    # ============================================================
    mask_titles = build_title_mask(image_bgr)
    titles_raw = detect_cross_column_titles(mask_titles)

    LEFT_MARGIN = int(PAGE_W * 0.02)
    RIGHT_MARGIN = int(PAGE_W * 0.02)

    titles = [
        {
            "x": LEFT_MARGIN,
            "y": y,
            "w": PAGE_W - LEFT_MARGIN - RIGHT_MARGIN,
            "h": h
        }
        for (_, y, _, h) in titles_raw
    ]

    title_rects = [(t["x"], t["y"], t["w"], t["h"]) for t in titles]

    # ============================================================
    # BLOCS (MASK + DILATION)
    # ============================================================
    mask_blocks = build_block_mask(image_bgr)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (65, 15))
    dilated = cv2.dilate(mask_blocks, kernel, iterations=2)

    cnts, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    rects = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w > 1000 or h > 1000:
            rects.append((x, y, w, h))

    # ============================================================
    # FUSION RECTANGLES SUR LA MÊME LIGNE
    # ============================================================
    rects = merge_rects(rects)

    rects = sorted(rects, key=rect_area, reverse=True)

    filtered_blocks = []
    for r in rects:
        if not any(rects_overlap(r, k) for k in filtered_blocks):
            filtered_blocks.append(r)

    # ============================================================
    # PRIORITÉ TITRES > BLOCS
    # ============================================================
    MAX_BLOCK_TITLE_AREA_RATIO = 1.35
    MIN_INTERSECTION_RATIO = 0.6

    final_blocks = []

    for block in filtered_blocks:
        block_area = rect_area(block)
        remove_block = False

        for title in title_rects:
            if not rects_intersect(block, title):
                continue

            title_area = rect_area(title)
            inter_ratio = intersection_ratio(block, title)
            area_ratio = block_area / title_area

            # Règle 1 : bloc plus petit que le titre
            if block_area < title_area:
                remove_block = True
                break

            # Règle 2 : bloc parasite légèrement plus grand
            if (
                inter_ratio >= MIN_INTERSECTION_RATIO and
                area_ratio <= MAX_BLOCK_TITLE_AREA_RATIO
            ):
                remove_block = True
                break

        if not remove_block:
            final_blocks.append(block)

    # ============================================================
    # CLASSIFICATION BLOCS
    # ============================================================
    bicolumn_text = []
    italic_text = []

    for i,(x, y, w, h) in enumerate(final_blocks):
        roi = image_bgr[y:y + h, x:x + w]

        block_json = {
            "x": x,
            "y": y,
            "w": w,
            "h": h
        }

        center_x = has_center_black_vertical_line(roi)

        if center_x is not None:
            block_json["center_x"] = x + center_x
            bicolumn_text.append(block_json)   # 🟢
        else:
            italic_text.append(block_json)     # 🔴

    # debug 
    #print(f"Page {page_index} - Titres: {len(titles)}, Blocs bicolumn: {len(bicolumn_text)}, Blocs italic: {len(italic_text)}")


    # ============================================================
    # JSON FINAL
    # ============================================================
    return {
        "titles": titles,                 # 🔵
        "bicolumn_text": bicolumn_text,   # 🟢
        "italic_text": italic_text        # 🔴
    }

if __name__ == "__main__":

    pdf_path = "ert.pdf"
    page_index = 100

    reslt = pipeline(pdf_path="ert.pdf",page_index=page_index,
        render_scale=4.17
    )

    print(reslt)

    """

    doc = pdfium.PdfDocument(pdf_path)
    pil_img = doc[page_index].render(scale=4.17).to_pil()
    image_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # afficher résultats
    for title in reslt["titles"]:
        x, y, w, h = title["x"], title["y"], title["w"], title["h"]
        cv2.rectangle(
            image_bgr,
            (x, y),
            (x + w, y + h),
            (255, 0, 0),
            10
        )
    for block in reslt["bicolumn_text"]:
        x, y, w, h = block["x"], block["y"], block["w"], block["h"]
        cv2.rectangle(
            image_bgr,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            10
        )
    for block in reslt["italic_text"]:
        x, y, w, h = block["x"], block["y"], block["w"], block["h"]
        cv2.rectangle(
            image_bgr,
            (x, y),
            (x + w, y + h),
            (0, 0, 255),
            10
        )
    cv2.imwrite("debug_pipeline.png", image_bgr)
    """