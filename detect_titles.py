import cv2
import numpy as np
import pypdfium2 as pdfium

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
            last[0] = min(last[0], x)
            last[1] = min(last[1], y)
            last[2] = max(last[2], x2)
            last[3] = max(last[3], y2)
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
        overlap_ratio = inter / hmin

        same_line = (overlap_ratio >= min_y_overlap) or (y1 <= ly2 + y_gap)

        if same_line:
            lines[-1] = [
                min(lx1, x1),
                min(ly1, y1),
                max(lx2, x2),
                max(ly2, y2)
            ]
        else:
            lines.append([x1, y1, x2, y2])

    return [(x1, y1, x2 - x1, y2 - y1) for (x1, y1, x2, y2) in lines]


# ============================================================
# CORE DETECTION (LOGIQUE MÉTIER INCHANGÉE)
# ============================================================

def detect_cross_column_titles(mask):
    h, w = mask.shape
    center_x = w // 2

    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(25, w // 35), 3)
    )
    merged = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=3)

    dilate_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(35, w // 28), 5)
    )
    merged = cv2.dilate(merged, dilate_kernel, iterations=2)

    contours, _ = cv2.findContours(
        merged,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    min_h = max(8, int(0.006 * h))
    max_h = max(35, int(0.12 * h))
    min_piece_w = max(30, int(0.02 * w))
    min_title_w = max(120, int(0.18 * w))

    gutter_band = max(20, int(0.02 * w))
    center_tol  = max(90, int(0.22 * w))

    pieces = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bh < min_h or bh > max_h:
            continue
        if bw < min_piece_w:
            continue
        pieces.append((x, y, bw, bh))

    line_boxes = group_boxes_by_text_line(pieces)

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
            pad_x = int(0.01 * w)
            pad_y = int(0.002 * h)

            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w - 1, x + bw + pad_x)
            y2 = min(h - 1, y + bh + pad_y)

            titles.append((x1, y1, x2 - x1, y2 - y1))

    return merge_boxes_by_vertical_gap(titles)


# ============================================================
# PIPELINE ENTRYPOINT
# ============================================================

def get_cross_column_titles_from_pdf(
    pdf_path,
    page_index=0,
    render_scale=4.17,
    gaussian_blur_ksize=(111, 111)
):
    document = pdfium.PdfDocument(pdf_path)
    pil_img = document[page_index].render(scale=render_scale).to_pil()

    image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)

    blur = cv2.GaussianBlur(image, gaussian_blur_ksize, 0)
    mask = cv2.threshold(
        blur, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    boxes = detect_cross_column_titles(mask)
    return len(boxes), boxes


count, boxes = get_cross_column_titles_from_pdf("pinax-bsb-p39.pdf")

if __name__ == "__main__":
    print(f"Found {count} title(s):")
    for i, (x, y, w, h) in enumerate(boxes):
        print(f"  Title {i+1}: x={x}, y={y}, w={w}, h={h}")