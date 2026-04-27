import pypdfium2 as pdfium
import cv2
import numpy as np


# ============================================================
# CORE DETECTION (LOGIQUE MÉTIER INCHANGÉE)
# ============================================================

def detect_center_separator_line(image_bgr, max_abs_angle_deg=6.0):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 1) binarisation (encre noire uniquement)
    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )

    # 2) ne garder que la zone centrale (évite marges & décor)
    center_margin = int(0.25 * w)
    mask = np.zeros_like(bw)
    mask[:, center_margin:w - center_margin] = 255
    bw &= mask

    # 3) morphologie pour lignes verticales fines
    kernel_vert = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(40, h // 25))
    )
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel_vert)

    # Nettoyage léger
    vertical = cv2.morphologyEx(
        vertical, cv2.MORPH_DILATE, np.ones((3, 3), np.uint8)
    )

    # 4) récupérer tous les pixels de la ligne
    ys, xs = np.where(vertical > 0)
    if len(xs) < 500:
        return None

    # 5) ajustement robuste (x = a*y + b)
    ys = ys.astype(np.float32)
    xs = xs.astype(np.float32)
    a, b = np.polyfit(ys, xs, 1)

    angle = np.degrees(np.arctan(a))
    if abs(angle) > max_abs_angle_deg:
        return None

    x_top = a * 0 + b
    x_bottom = a * (h - 1) + b

    return {
        "x1": float(x_top),
        "y1": 0.0,
        "x2": float(x_bottom),
        "y2": float(h - 1),
        "angle_from_vertical_deg": float(angle),
        "points_count": int(len(xs)),
    }


def find_separator_x_from_image(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (111, 111), 0)
    mask = cv2.threshold(
        blur, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    h, w = mask.shape
    col_sum = np.sum(mask > 0, axis=0).astype(np.float32)

    kernel = np.ones(31, dtype=np.float32) / 31
    col_sum_smooth = np.convolve(col_sum, kernel, mode="same")

    mid = w // 2
    search_half = int(0.2 * w)
    start = max(0, mid - search_half)
    end = min(w, mid + search_half)

    if end <= start:
        return mid

    return int(start + np.argmin(col_sum_smooth[start:end]))


# ============================================================
# PIPELINE ENTRYPOINT
# ============================================================

def get_column_separator_from_pdf(
    pdf_path,
    page_index=0,
    render_scale=4.17
):
    document = pdfium.PdfDocument(pdf_path)
    pil_img = document[page_index].render(scale=render_scale).to_pil()
    image_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    line = detect_center_separator_line(image_bgr)

    if line is not None:
        return {
            "detected": True,
            "x1": line["x1"],
            "y1": line["y1"],
            "x2": line["x2"],
            "y2": line["y2"],
            "angle_from_vertical_deg": line["angle_from_vertical_deg"],
        }

    # fallback : séparation verticale simple
    sep_x = find_separator_x_from_image(image_bgr)
    return {
        "detected": False,
        "x": sep_x
    }

if __name__ == "__main__":
    result = get_column_separator_from_pdf("pinax-bsb-p39.pdf")
    if result["detected"]:
        print(f"Detected separator line: x1={result['x1']:.2f}, y1={result['y1']:.2f}, "
              f"x2={result['x2']:.2f}, y2={result['y2']:.2f}, "
              f"angle_from_vertical_deg={result['angle_from_vertical_deg']:.2f}")
    else:
        print(f"No clear separator line detected. Estimated vertical separator at x={result['x']}")