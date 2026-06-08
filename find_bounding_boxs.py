import cv2
import numpy as np
import pypdfium2 as pdfium


# ============================================================
# CONFIG
# ============================================================

pdfPath = "ert.pdf"
PAGE_INDEX = 355           # 0 = première page
RENDER_SCALE = 4.17      # ajuste la résolution de rendu

# Binarisation (layout)
GAUSSIAN_BLUR_KSIZE = (111, 111)

# Regroupement / fusion
MERGE_VERTICAL_GAP = 500   # fusion si petites séparations verticales entre segments

# Debug outputs
OUT_TITLES = "page_titles.png"
OUT_PIECES = "debug_pieces.png"
OUT_LINES  = "debug_line_boxes.png"


# ============================================================
# UTILS
# ============================================================

def merge_boxes_by_vertical_gap(boxes, max_gap=50):
    """
    Fusionne des rectangles (x,y,w,h) s'ils sont proches verticalement.
    Utile quand un titre est sur 2 lignes (ou fragments superposés).
    """
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


def group_boxes_by_text_line(boxes, y_gap=12, min_y_overlap=0.35):
    """
    Regroupe des boxes (x,y,w,h) appartenant à la même ligne de texte,
    via overlap vertical ou faible gap vertical.

    Retourne des bboxes union par ligne : (x,y,w,h)
    """
    if not boxes:
        return []

    # Convert to (x1,y1,x2,y2)
    b = [(x, y, x + w, y + h) for (x, y, w, h) in boxes]
    b.sort(key=lambda t: (t[1], t[0]))  # sort by y1 then x1

    lines = []
    for x1, y1, x2, y2 in b:
        if not lines:
            lines.append([x1, y1, x2, y2])
            continue

        lx1, ly1, lx2, ly2 = lines[-1]

        # overlap vertical ratio
        inter = max(0, min(y2, ly2) - max(y1, ly1))
        hmin = max(1, min(y2 - y1, ly2 - ly1))
        overlap_ratio = inter / hmin

        # same line if overlapping enough OR small vertical gap
        same_line = (overlap_ratio >= min_y_overlap) or (y1 <= ly2 + y_gap)

        if same_line:
            lines[-1] = [min(lx1, x1), min(ly1, y1), max(lx2, x2), max(ly2, y2)]
        else:
            lines.append([x1, y1, x2, y2])

    return [(x1, y1, x2 - x1, y2 - y1) for (x1, y1, x2, y2) in lines]


def detect_cross_column_titles(mask, image_bgr=None, debug_prefix=None):
    """
    Détection des titres traversants / centrés.
    - on extrait d'abord les "morceaux" de texte (pieces)
    - on regroupe ces morceaux par ligne (bbox union)
    - on applique le critère cross/center sur la bbox complète
    - on fusionne verticalement pour titres sur 2 lignes

    Si image_bgr + debug_prefix fournis => images debug.
    """
    h, w = mask.shape
    center_x = w // 2

    # 1) Morphologie pour regrouper les caractères en blocs
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, w // 35), 3))
    merged = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=3)

    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(35, w // 28), 5))
    merged = cv2.dilate(merged, dilate_kernel, iterations=2)

    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 2) Seuils adaptatifs
    min_h = max(8, int(0.006 * h))
    max_h = max(35, int(0.12 * h))

    # On garde des "morceaux" (pieces) pas trop petits
    min_piece_w = max(30, int(0.02 * w))

    # Largeur minimale du titre complet (après union)
    min_title_w = max(120, int(0.18 * w))

    # Critère "traverse la gouttière" / "centré"
    gutter_band = max(20, int(0.02 * w))
    center_tol  = max(90, int(0.22 * w))

    # 3) Récupération des morceaux (sans filtrage cross/center)
    pieces = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bh < min_h or bh > max_h:
            continue
        if bw < min_piece_w:
            continue
        pieces.append((x, y, bw, bh))

    # Debug: pièces
    if image_bgr is not None and debug_prefix is not None:
        dbg = image_bgr.copy()
        for x, y, bw, bh in pieces:
            cv2.rectangle(dbg, (x, y), (x + bw, y + bh), (0, 255, 255), 2)  # jaune
        cv2.imwrite(f"{debug_prefix}_pieces.png", dbg)

    # 4) Regroupement par ligne (union des morceaux)
    line_boxes = group_boxes_by_text_line(pieces, y_gap=12, min_y_overlap=0.35)

    # Debug: bboxes de ligne
    if image_bgr is not None and debug_prefix is not None:
        dbg = image_bgr.copy()
        for x, y, bw, bh in line_boxes:
            cv2.rectangle(dbg, (x, y), (x + bw, y + bh), (0, 165, 255), 2)  # orange
        cv2.imwrite(f"{debug_prefix}_lines.png", dbg)

    # 5) Filtre cross/center sur bbox union (titre complet)
    titles = []
    for x, y, bw, bh in line_boxes:
        if bw < min_title_w:
            continue

        crosses = not (
            (x + bw) < center_x - gutter_band or
            x > center_x + gutter_band
        )

        is_centered = abs((x + bw / 2) - center_x) < center_tol

        if crosses or is_centered:
            # padding pour éviter de couper accents / bords
            pad_x = int(0.01 * w)
            pad_y = int(0.002 * h)

            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w - 1, x + bw + pad_x)
            y2 = min(h - 1, y + bh + pad_y)

            titles.append((x1, y1, x2 - x1, y2 - y1))

    # 6) Fusion vertical (si un titre est sur deux lignes)
    titles = merge_boxes_by_vertical_gap(titles, max_gap=MERGE_VERTICAL_GAP)
    return titles


# ============================================================
# MAIN
# ============================================================

def main():
    # -------------------------
    # Chargement PDF & rendu
    # -------------------------
    document = pdfium.PdfDocument(pdfPath)
    pil_img = document[PAGE_INDEX].render(scale=RENDER_SCALE).to_pil()
    image_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # -------------------------
    # Binarisation layout
    # -------------------------
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, GAUSSIAN_BLUR_KSIZE, 0)
    mask = cv2.threshold(
        blur, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    # -------------------------
    # Détection titres
    # -------------------------
    title_boxes = detect_cross_column_titles(
        mask,
        image_bgr=image_bgr,
        debug_prefix="debug"  # générera debug_pieces + debug_lines
    )

    # -------------------------
    # Visualisation finale
    # -------------------------
    debug = image_bgr.copy()
    for x, y, w, h in title_boxes:
        cv2.rectangle(debug, (x, y), (x + w, y + h), (255, 0, 0), 3)  # bleu

    #cv2.imwrite(OUT_TITLES, debug)

    # Rename debug outputs according to your config names (optional convenience)
    # (The detect function outputs debug_pieces.png and debug_lines.png by default)
    # We'll also copy/alias them:
    try:
        # If you want exact file names as in config:
        import os
        if os.path.exists("debug_pieces.png"):
            os.replace("debug_pieces.png", OUT_PIECES)
        if os.path.exists("debug_lines.png"):
            os.replace("debug_lines.png", OUT_LINES)
    except Exception:
        pass

    print(f"[OK] Titres détectés : {len(title_boxes)}")
    print(f"[OK] Sortie titres : {OUT_TITLES}")
    print(f"[OK] Debug pièces : {OUT_PIECES}")
    print(f"[OK] Debug lignes : {OUT_LINES}")


if __name__ == "__main__":
    main()