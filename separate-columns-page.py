import pypdfium2 as pdfium
import cv2
import numpy as np

# =========================
# Chargement PDF
# =========================
pdfPath = "pinax bsb-p71.pdf"
document = pdfium.PdfDocument(pdfPath)

image = document[0].render(scale=4.17).to_pil()
image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

# =========================
# Détection ligne centrale
# =========================

def detect_center_separator_line(image_bgr, center_strip_ratio=0.24, max_abs_angle_deg=8.0):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    strip_half = max(25, int((w * center_strip_ratio) / 2.0))
    x0 = max(0, (w // 2) - strip_half)
    x1 = min(w, (w // 2) + strip_half)

    # Mettre en évidence les encres sombres verticales autour du centre
    inv_strip = 255 - gray[:, x0:x1]
    binary = cv2.threshold(inv_strip, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    vertical_kernel_h = max(80, h // 30)
    vertical = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_kernel_h)),
    )
    vertical = cv2.dilate(vertical, np.ones((3, 3), np.uint8), iterations=1)

    col_strength = np.sum(vertical > 0, axis=0).astype(np.float32)
    if col_strength.size == 0:
        return None

    seed_local_x = int(np.argmax(col_strength))
    seed_strength = float(col_strength[seed_local_x])
    if seed_strength < max(20.0, 0.02 * h):
        return None

    band_h = max(120, h // 70)
    search_radius = max(30, (x1 - x0) // 20)
    min_peak_per_band = max(10, int(0.14 * band_h))

    points = []
    local_x = seed_local_x

    for y in range(0, h - band_h + 1, band_h):
        band = np.sum(vertical[y:y + band_h, :] > 0, axis=0)

        start = max(0, local_x - search_radius)
        end = min(vertical.shape[1], local_x + search_radius + 1)
        if end <= start:
            continue

        local_band = band[start:end]
        candidate_local_x = int(start + np.argmax(local_band))
        peak = int(band[candidate_local_x])

        if peak < min_peak_per_band:
            continue

        local_x = candidate_local_x
        points.append((float(x0 + local_x), float(y + (band_h / 2.0))))

    if len(points) < 6:
        return None

    ys = np.array([p[1] for p in points], dtype=np.float32)
    xs = np.array([p[0] for p in points], dtype=np.float32)
    slope_dx_dy, intercept = np.polyfit(ys, xs, 1)
    angle_from_vertical_deg = float(np.degrees(np.arctan(slope_dx_dy)))

    if abs(angle_from_vertical_deg) > max_abs_angle_deg:
        return None

    x_top = float((slope_dx_dy * 0.0) + intercept)
    x_bottom = float((slope_dx_dy * float(h - 1)) + intercept)

    x_top = float(np.clip(x_top, 0, w - 1))
    x_bottom = float(np.clip(x_bottom, 0, w - 1))

    return {
        "x1": x_top,
        "y1": 0.0,
        "x2": x_bottom,
        "y2": float(h - 1),
        "angle_from_vertical_deg": angle_from_vertical_deg,
        "points_count": len(points),
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

cv2.imwrite("page39_overlay_line.png", overlay)
print(f"Ligne détectée: {detection_ok} | angle (si détectée): {angle:+.3f} deg")