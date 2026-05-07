import cv2
import numpy as np


def split_bicolumn_roi(
    image_bgr,
    center_ratio=0.25,
    min_height_ratio=0.5,
    x_tolerance=30,
    save=False,
    output_prefix="roi"
):
    """
    Sépare une image bi‑colonne en deux ROI (gauche / droite)
    
    Paramètres
    ----------
    image_bgr : np.ndarray
        Image OpenCV (BGR) correspondant à une page ou ROI bi-colonne
    center_ratio : float
        Largeur relative de la zone centrale de recherche (par défaut 25%)
    min_height_ratio : float
        Hauteur minimale cumulée d’une ligne verticale (par défaut 50%)
    x_tolerance : int
        Tolérance en pixels pour grouper les rectangles verticaux
    save : bool
        Sauvegarde les ROI sur disque si True
    output_prefix : str
        Préfixe des fichiers sauvegardés
    
    Retour
    ------
    roi_left : np.ndarray
    roi_right : np.ndarray
    x_split : int  (position X de séparation)
    """

    image_original = image_bgr.copy()
    img_h, img_w = image_bgr.shape[:2]

    # =========================
    # Prétraitement
    # =========================
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (1, 111), 0)
    thresh = cv2.threshold(
        blur, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 113))
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # =========================
    # Contours
    # =========================
    cnts = cv2.findContours(
        dilated,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]
    cnts = sorted(cnts, key=lambda c: cv2.boundingRect(c)[0])

    # =========================
    # Zone centrale
    # =========================
    center_width = int(img_w * center_ratio)
    center_start = (img_w - center_width) // 2
    center_end = center_start + center_width

    candidates = []
    min_total_height = img_h * min_height_ratio

    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        cx = x + w // 2

        if (
            w < 200 and
            h > img_h * 0.15 and
            center_start <= cx <= center_end
        ):
            candidates.append((x, y, w, h))

    # =========================
    # Groupement vertical
    # =========================
    groups = []

    for rect in candidates:
        x, y, w, h = rect
        placed = False

        for group in groups:
            gx, _, _, _ = group[0]
            if abs(x - gx) <= x_tolerance:
                group.append(rect)
                placed = True
                break

        if not placed:
            groups.append([rect])

    # =========================
    # Détection de la ligne centrale
    # =========================
    detected_lines = []

    for group in groups:
        total_height = sum(r[3] for r in group)

        if total_height >= min_total_height:
            xs = [r[0] for r in group]
            ws = [r[2] for r in group]

            x_center = int(np.median(xs))
            w_mean = int(np.mean(ws))

            x1 = x_center
            x2 = x_center + w_mean

            detected_lines.append((x1, x2))

    if not detected_lines:
        raise RuntimeError("Aucune séparation bi-colonne détectée")

    # Ligne la plus centrale
    detected_lines.sort(key=lambda l: abs((l[0] + l[1]) // 2 - img_w // 2))
    x1, x2 = detected_lines[0]

    # =========================
    # Découpage ROI
    # =========================
    roi_left = image_original[:, :x1]
    roi_right = image_original[:, x2:]

    if save:
        cv2.imwrite(f"{output_prefix}_left.png", roi_left)
        cv2.imwrite(f"{output_prefix}_right.png", roi_right)

    return roi_left, roi_right, (x1 + x2) // 2


def main():
    # =========================
    # Chargement image
    # =========================
    image_path = "roi_3.png"
    image = cv2.imread(image_path)

    if image is None:
        raise FileNotFoundError(f"Impossible de charger l'image : {image_path}")

    # =========================
    # Séparation bi-colonne
    # =========================
    try:
        roi_left, roi_right, x_split = split_bicolumn_roi(
            image,
            save=True,
            output_prefix="page_01"
        )

        print(f"Séparation détectée à X = {x_split}")

    except RuntimeError as e:
        print("Erreur :", e)
        return

    # =========================
    # Affichage (debug optionnel)
    # =========================
    cv2.imshow("ROI gauche", roi_left)
    cv2.imshow("ROI droite", roi_right)

    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()