import pypdfium2 as pdfium
import cv2
import numpy as np

# =========================
# Chargement PDF
# =========================
pdfPath = "pinax bsb-p46.pdf"
document = pdfium.PdfDocument(pdfPath)

image = document[0].render(scale=4.17).to_pil()
image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

# =========================
# Détection ligne centrale
# =========================

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
    mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

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


# =========================
# Dessin de la ligne rouge
# =========================

def draw_separator_overlay(image_bgr, color=(0, 0, 255), thickness=3):
    out = image_bgr.copy()
    h, w = out.shape[:2]

    best_line = detect_center_separator_line(out)

    if best_line is not None:
        x1, y1 = float(best_line["x1"]), float(best_line["y1"])
        x2, y2 = float(best_line["x2"]), float(best_line["y2"])
        dy = y2 - y1

        # étendre la ligne détectée sur toute la hauteur de l'image
        if abs(dy) > 1e-6:
            t_top = (0.0 - y1) / dy
            t_bottom = ((h - 1) - y1) / dy
            x_top = int(np.clip(round(x1 + t_top * (x2 - x1)), 0, w - 1))
            x_bottom = int(np.clip(round(x1 + t_bottom * (x2 - x1)), 0, w - 1))

            cv2.line(out, (x_top, 0), (x_bottom, h - 1), color, thickness)
            return out, True, best_line["angle_from_vertical_deg"]

    # fallback : ligne verticale au x estimé
    sep_x = find_separator_x_from_image(out)
    cv2.line(out, (sep_x, 0), (sep_x, h - 1), color, thickness)
    return out, False, 0.0


overlay, detection_ok, angle = draw_separator_overlay(image_bgr)

cv2.imwrite("separate-columns.png", overlay)
print(f"Ligne détectée: {detection_ok} | angle (si détectée): {angle:+.3f} deg")