from pathlib import Path
from collections import Counter, defaultdict
import json
import re
import statistics
import pytesseract
from PIL import Image, ImageDraw

# ==========================================================
# CONFIG TESSERACT (macOS Homebrew)
# ==========================================================
HOMEBREW_TESSERACT = "/opt/homebrew/bin/tesseract"
if Path(HOMEBREW_TESSERACT).exists():
    pytesseract.pytesseract.tesseract_cmd = HOMEBREW_TESSERACT

# configure tesseract to use the Latin language
pytesseract.pytesseract.lang = "lat"

REMAINING_COLOR = "red"
INDENT_COLOR = "blue"
ROMAN_BULLET_COLOR = "green"
SPECIES_TITLE_COLOR = "orange"
ROMAN_CHARS = set("IVXLCDM")
ROMAN_CONFUSION_MAP = str.maketrans({"H": "I", "J": "I", "Y": "I", "1": "I", "|": "I", "l": "I"})


def compute_right_gap_reference(right_gap_values):
    # utiliser la moyenne des plus petits gaps pour estimer la marge de droite, 
    # en limitant l'influence des valeurs aberrantes

    sorted_values = sorted(right_gap_values)
    if not sorted_values:
        return 0, 0

    subset_size = max(1, round(len(sorted_values) * 0.2))
    smallest_gaps = sorted_values[:subset_size]

    median_right_gap = statistics.mean(smallest_gaps)
    spread_right_gap = statistics.pstdev(smallest_gaps) if len(smallest_gaps) > 1 else 0
    spread_right_gap = min(spread_right_gap, 120)
    return median_right_gap, spread_right_gap


def compute_roman_bullet_score(line_items, right_gap_px=0, right_gap_reference=0, right_gap_spread=0):
    # évaluer la probabilité que le premier token d'une ligne soit une puce romaine, 
    # en se basant sur sa forme, sa ponctuation, sa casse, sa proximité avec la marge de droite, 
    # et la présence de caractères romains

    if not line_items:
        return 0, "", [], ""

    first_token = line_items[0]["text"].strip()
    normalized_token = first_token.upper().translate(ROMAN_CONFUSION_MAP)
    normalized_core = normalized_token.strip(".,;:()[]{}")
    if not normalized_core:
        return 0, first_token, [], normalized_core

    roman_core = "".join(char for char in normalized_core if char in ROMAN_CHARS)
    invalid_chars = [char for char in normalized_core if char.isalpha() and char not in ROMAN_CHARS]
    has_punctuation = any(char in first_token for char in ".,;:")
    is_short_token = len(normalized_core) <= 4
    is_very_short = len(normalized_core) <= 3
    has_roman_evidence = len(roman_core) >= 1
    has_strong_roman_evidence = len(roman_core) >= 2

    score = 0
    reasons = []

    if is_short_token:
        score += 20
        reasons.append("court")

    if is_very_short:
        score += 10
        reasons.append("tres_court")

    if is_short_token and has_punctuation:
        score += 35
        reasons.append("petit_avec_ponctuation")

    if normalized_core[0] in ROMAN_CHARS:
        score += 15
        reasons.append("debute_romain")

    if first_token[:1].isupper():
        score += 15
        reasons.append("majuscule")

    if is_short_token and first_token[:1].isupper():
        score += 10
        reasons.append("majuscule_courte")

    if first_token.isupper():
        score += 10
        reasons.append("tout_en_capitales")

    if first_token.endswith((".", ")", ":")):
        score += 10
        reasons.append("ponctuation")

    if has_roman_evidence:
        score += 15
        reasons.append("evidence_romaine")

    if has_strong_roman_evidence:
        score += 10
        reasons.append("evidence_romaine_forte")

    if has_roman_evidence and is_short_token and has_punctuation:
        score += 10
        reasons.append("evidence_roman_courte")

    if not has_roman_evidence:
        score -= 50
        reasons.append("pas_de_noyau_romain")

    if invalid_chars:
        score -= 15 if has_roman_evidence else 20
        reasons.append("lettres_non_romaines")

        if len(normalized_core) <= 4 and roman_core:
            roman_ratio = len(roman_core) / len(normalized_core)
            if roman_ratio < 0.85:
                score = min(score, 60)
                reasons.append("purete_insuffisante")

    if has_roman_evidence and len(normalized_core) <= 4 and has_punctuation:
        score += 10
        reasons.append("ponctuation_courte")

    right_gap_bonus_threshold = right_gap_reference + max(50, right_gap_spread)
    right_gap_penalty_threshold = max(0, right_gap_reference - max(40, 0.75 * right_gap_spread))

    if right_gap_px >= right_gap_bonus_threshold:
        score += 15
        reasons.append("fin_de_ligne_haute")
    elif right_gap_px <= right_gap_penalty_threshold:
        score -= 20
        reasons.append("ligne_trop_longue")

    if re.fullmatch(r"[IVXLCDM]+", normalized_core):
        score += 20
        reasons.append("pattern_strict")

    return max(0, min(score, 100)), first_token, reasons, normalized_core


def compute_species_title_score(indent_px=0, right_gap_px=0, right_gap_reference=0, right_gap_spread=0):
    # évaluer la probabilité qu'une ligne soit un titre d'espèce, en se basant sur son indentation, 
    # sa proximité avec la marge de droite, et l'équilibre entre les deux
    
    right_gap_threshold = right_gap_reference + max(90, right_gap_spread)
    balance_limit = max(30, int(0.25 * max(1, indent_px, right_gap_px, right_gap_reference)))
    balance_gap = abs(indent_px - right_gap_px)

    score = 0
    reasons = []

    if right_gap_px > right_gap_threshold:
        score += 50
        reasons.append("hors_seuil_droit")
    else:
        score -= 40
        reasons.append("dans_seuil_droit")

    if balance_gap <= balance_limit:
        score += 50
        reasons.append("marges_equilibrees")
    else:
        score -= 20
        reasons.append("marges_desequilibrees")

    return max(0, min(score, 100)), reasons


def classify_block_type(indent_group, roman_is_bullet, species_title_is_title):
    # classer les lignes en types "espece", "variete", "commentaire" 
    # ou "taxon" en fonction de leur indentation,
    # de la probabilité qu'elles soient des puces romaines, 
    # et de la probabilité qu'elles soient des titres d'espèce
    
    if species_title_is_title:
        return "espece", SPECIES_TITLE_COLOR
    if roman_is_bullet:
        return "variete", ROMAN_BULLET_COLOR
    if indent_group > 0:
        return "commentaire", INDENT_COLOR
    return "taxon", REMAINING_COLOR


def compute_indent_breakpoints(indent_values):
    # identifier les seuils d'indentation qui permettent de différencier les groupes de lignes,
    # en se basant sur la distribution des indentations et en limitant l'influence des valeurs aberrantes

    sorted_values = sorted(indent_values)
    if len(sorted_values) < 2:
        return []

    lower_half_size = max(2, len(sorted_values) // 2)
    lower_half = sorted_values[:lower_half_size]

    lower_mean = statistics.mean(lower_half)
    lower_spread = statistics.pstdev(lower_half) if len(lower_half) > 1 else 0

    gap_threshold = max(60, lower_mean + max(20, 2 * lower_spread))

    counts = Counter(sorted_values)
    unique_values = sorted(counts)
    total_count = len(sorted_values)
    breakpoints = []

    left_count = 0
    for left_value, right_value in zip(unique_values, unique_values[1:]):
        left_count += counts[left_value]
        right_count = total_count - left_count
        gap = right_value - left_value

        if gap >= gap_threshold and left_count >= 2 and right_count >= 1:
            breakpoints.append((left_value + right_value) / 2)

    return breakpoints


def get_indent_group(indent_px, indent_breakpoints):
    # déterminer le groupe d'indentation d'une ligne 
    # en fonction de ses pixels d'indentation et des seuils identifiés

    if not indent_breakpoints:
        return 0

    return sum(1 for breakpoint in indent_breakpoints if indent_px > breakpoint)


def strip_edge_bars(text):
    # supprimer les barres verticales en début et fin de ligne, qui sont souvent des artefacts d'OCR

    stripped_text = text.strip()
    if stripped_text.startswith("|"):
        stripped_text = stripped_text[1:].lstrip()
    if stripped_text.endswith("|"):
        stripped_text = stripped_text[:-1].rstrip()
    return stripped_text


def remove_bar_tokens(line_items):
    # supprimer les tokens qui ne contiennent que des barres verticales, 
    # qui sont souvent des artefacts d'OCR

    return [item for item in line_items if item["text"] != "|"]


def draw_right_gap_tube(debug_img, page_right_edge, right_gap_reference, right_gap_spread):
    # dessiner un tube vertical indiquant la zone de la marge de droite, 
    # pour aider à visualiser l'analyse

    if right_gap_reference <= 0 and right_gap_spread <= 0:
        return debug_img

    tube_half_width = max(30, min(110, int(max(45, right_gap_spread))))
    tube_center_x = int(page_right_edge - right_gap_reference)
    tube_left = max(0, tube_center_x - tube_half_width)
    tube_right = min(debug_img.width, tube_center_x + tube_half_width)

    overlay = Image.new("RGBA", debug_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [tube_left, 0, tube_right, debug_img.height],
        fill=(0, 255, 0, 35),
        outline=(0, 180, 0, 140),
        width=3,
    )
    overlay_draw.line(
        [(tube_center_x, 0), (tube_center_x, debug_img.height)],
        fill=(0, 150, 0, 220),
        width=4,
    )
    return Image.alpha_composite(debug_img.convert("RGBA"), overlay)


def merge_wrapped_lines(visual_lines, page_left_margin, indent_breakpoints, page_right_edge, right_gap_reference, right_gap_spread):
    # fusionner les lignes qui semblent être des lignes de texte enroulées,
    # en se basant sur leur proximité verticale, leur indentation, 
    # et leur proximité avec la marge de droite, tout en limitant les fusions abusives grâce à des seuils adaptatifs
    
    if not visual_lines:
        return []

    right_gap_threshold = right_gap_reference + max(90, right_gap_spread)
    merged_blocks = []
    i = 0

    while i < len(visual_lines):
        visual_line = visual_lines[i]
        line_items = remove_bar_tokens(visual_line["items"])
        i += 1

        if not line_items:
            continue

        line_left = min(item["left"] for item in line_items)
        line_top = min(item["top"] for item in line_items)
        line_right = max(item["left"] + item.get("width", 0) for item in line_items)
        line_bottom = max(item["top"] + item.get("height", 0) for item in line_items)
        indent_px = line_left - page_left_margin
        indent_group = get_indent_group(indent_px, indent_breakpoints)
        right_gap_px = page_right_edge - line_right
        line_reaches_end = right_gap_px <= right_gap_threshold

        block_items = list(line_items)
        block_left = line_left
        block_top = line_top
        block_right = line_right
        block_bottom = line_bottom
        block_start_items = list(line_items)
        block_start_left = line_left
        block_start_top = line_top
        block_start_right = line_right
        block_start_bottom = line_bottom
        block_start_indent_group = indent_group
        block_start_right_gap = right_gap_px

        if not line_reaches_end:
            merged_blocks.append(
                {
                    "items": block_items,
                    "left": block_left,
                    "top": block_top,
                    "right": block_right,
                    "bottom": block_bottom,
                    "indent_group": indent_group,
                    "start_items": block_start_items,
                    "start_left": block_start_left,
                    "start_top": block_start_top,
                    "start_right": block_start_right,
                    "start_bottom": block_start_bottom,
                    "start_indent_group": block_start_indent_group,
                    "start_right_gap": block_start_right_gap,
                }
            )
            continue

        j = i
        while j < len(visual_lines):
            next_visual_line = visual_lines[j]
            next_items = remove_bar_tokens(next_visual_line["items"])
            j += 1

            if not next_items:
                continue

            next_left = min(item["left"] for item in next_items)
            next_top = min(item["top"] for item in next_items)
            next_right = max(item["left"] + item.get("width", 0) for item in next_items)
            next_bottom = max(item["top"] + item.get("height", 0) for item in next_items)
            next_right_gap = page_right_edge - next_right
            vertical_gap = next_top - block_bottom
            close_vertical_gap = vertical_gap <= max(24, int(0.25 * max(1, next_bottom - next_top)))
            next_indent_px = next_left - page_left_margin
            next_indent_group = get_indent_group(next_indent_px, indent_breakpoints)

            if next_indent_group > 0 or not close_vertical_gap:
                j -= 1
                break

            block_items.extend(next_items)
            block_left = min(block_left, next_left)
            block_top = min(block_top, next_top)
            block_right = max(block_right, next_right)
            block_bottom = max(block_bottom, next_bottom)

            if next_right_gap > right_gap_threshold:
                break

        merged_blocks.append(
            {
                "items": block_items,
                "left": block_left,
                "top": block_top,
                "right": block_right,
                "bottom": block_bottom,
                "indent_group": indent_group,
                "start_items": block_start_items,
                "start_left": block_start_left,
                "start_top": block_start_top,
                "start_right": block_start_right,
                "start_bottom": block_start_bottom,
                "start_indent_group": block_start_indent_group,
                "start_right_gap": block_start_right_gap,
            }
        )
        i = j

    return merged_blocks


def merge_visual_lines(grouped_lines):
    # fusionner les lignes détectées par tesseract qui sont très proches verticalement,
    # pour compenser les erreurs de segmentation, 
    # tout en limitant les fusions abusives grâce à des seuils adaptatifs basés sur la taille des lignes
    line_boxes = []

    for key, line_items in grouped_lines.items():
        line_left = min(item["left"] for item in line_items)
        line_top = min(item["top"] for item in line_items)
        line_right = max(item["left"] + item.get("width", 0) for item in line_items)
        line_bottom = max(item["top"] + item.get("height", 0) for item in line_items)
        line_height = line_bottom - line_top

        line_boxes.append(
            {
                "key": key,
                "items": list(line_items),
                "left": line_left,
                "top": line_top,
                "right": line_right,
                "bottom": line_bottom,
                "center_y": (line_top + line_bottom) / 2,
                "height": line_height,
            }
        )

    line_boxes.sort(key=lambda box: (box["top"], box["left"]))

    merged_lines = []
    for box in line_boxes:
        if not merged_lines:
            merged_lines.append(box)
            continue

        previous = merged_lines[-1]
        vertical_overlap = min(previous["bottom"], box["bottom"]) - max(previous["top"], box["top"])
        overlap_ratio = vertical_overlap / max(1, min(previous["height"], box["height"]))
        center_gap = abs(previous["center_y"] - box["center_y"])
        max_height = max(previous["height"], box["height"])
        horizontal_gap = box["left"] - previous["right"]

        should_merge = (
            overlap_ratio >= 0.55
            and center_gap <= max(18, 0.25 * max_height)
            and horizontal_gap <= max(80, 0.35 * max(previous["right"] - previous["left"], box["right"] - box["left"]))
        )

        if should_merge:
            previous["items"].extend(box["items"])
            previous["left"] = min(previous["left"], box["left"])
            previous["top"] = min(previous["top"], box["top"])
            previous["right"] = max(previous["right"], box["right"])
            previous["bottom"] = max(previous["bottom"], box["bottom"])
            previous["center_y"] = (previous["top"] + previous["bottom"]) / 2
            previous["height"] = previous["bottom"] - previous["top"]
            continue

        merged_lines.append(box)

    return merged_lines


def extract_line_indentation(img):
    # extraire les lignes de texte d'une image avec tesseract,
    # analyser leur indentation, leur proximité avec la marge de droite,
    # et les fusionner pour compenser les erreurs d'OCR,
    # tout en limitant les fusions abusives grâce à des seuils adaptatifs basés sur la distribution des indentations et des gaps de droite, 
    # puis classer les lignes en types "espece", "variete", "commentaire" ou "taxon" en fonction de ces analyses
    
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    grouped_lines = defaultdict(list)

    for index, text in enumerate(data["text"]):
        cleaned_text = text.strip()
        if not cleaned_text:
            continue

        key = (
            data["page_num"][index],
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        grouped_lines[key].append(
            {
                "text": cleaned_text,
                "left": data["left"][index],
                "top": data["top"][index],
                "width": data["width"][index],
                "height": data["height"][index],
            }
        )
    if not grouped_lines:
        print("Aucun texte détecté")
        return

    page_left_margin = min(item["left"] for line in grouped_lines.values() for item in line)
    page_right_edge = img.width
    indent_values = [min(item["left"] for item in line) - page_left_margin for line in grouped_lines.values()]
    indent_breakpoints = compute_indent_breakpoints(indent_values)
    visual_lines = merge_visual_lines(grouped_lines)
    right_gap_values = [page_right_edge - line_box["right"] for line_box in visual_lines]
    right_gap_reference, right_gap_spread = compute_right_gap_reference(right_gap_values)
    merged_blocks = merge_wrapped_lines(
        visual_lines,
        page_left_margin,
        indent_breakpoints,
        page_right_edge,
        right_gap_reference,
        right_gap_spread,
    )

    analyzed_blocks = []
    for merged_block in merged_blocks:
        line_items = merged_block["items"]
        if not line_items:
            continue

        line_text = " ".join(item["text"] for item in line_items)
        line_left = merged_block["left"]
        line_top = merged_block["top"]
        line_right = merged_block["right"]
        line_bottom = merged_block["bottom"]
        start_items = merged_block.get("start_items", line_items)
        start_left = merged_block.get("start_left", line_left)
        start_top = merged_block.get("start_top", line_top)
        start_right = merged_block.get("start_right", line_right)
        start_bottom = merged_block.get("start_bottom", line_bottom)
        indent_px = start_left - page_left_margin
        right_gap_px = merged_block.get("start_right_gap", page_right_edge - start_right)
        indent_group = merged_block.get("start_indent_group", get_indent_group(indent_px, indent_breakpoints))
        species_title_score = 0
        species_title_reasons = []
        species_title_is_title = False
        if indent_group > 0:
            roman_score, roman_token, roman_reasons, roman_core = compute_roman_bullet_score(
                start_items,
                right_gap_px=right_gap_px,
                right_gap_reference=right_gap_reference,
                right_gap_spread=right_gap_spread,
            )
            roman_is_bullet = roman_score >= 70
            species_title_score, species_title_reasons = compute_species_title_score(
                indent_px=indent_px,
                right_gap_px=right_gap_px,
                right_gap_reference=right_gap_reference,
                right_gap_spread=right_gap_spread,
            )
            species_title_is_title = species_title_score >= 70 and not roman_is_bullet
        else:
            roman_score, roman_token, roman_reasons, roman_core = 0, "", [], ""
            roman_is_bullet = False
            species_title_score, species_title_reasons = 0, []
        block_type, debug_color = classify_block_type(indent_group, roman_is_bullet, species_title_is_title)
        display_line_text = strip_edge_bars(line_text)
        analyzed_blocks.append(
            {
                "type": block_type,
                "color": debug_color,
                "text": display_line_text,
                "raw_text": line_text,
                "indent_group": indent_group,
                "indent_px": indent_px,
                "right_gap_px": right_gap_px,
                "roman_score": roman_score,
                "species_title_score": species_title_score,
                "roman_is_bullet": roman_is_bullet,
                "species_title_is_title": species_title_is_title,
                "line_left": line_left,
                "line_top": line_top,
                "line_right": line_right,
                "line_bottom": line_bottom,
                "start_left": start_left,
                "start_top": start_top,
                "start_right": start_right,
                "start_bottom": start_bottom,
                "start_items": start_items,
                "debug_label": f"g{indent_group} | {indent_px}px | {right_gap_px}px | R{roman_score}% | T{species_title_score}%",
            }
        )

    return {
        "blocks": analyzed_blocks,
        "indent_breakpoints": indent_breakpoints,
        "right_gap_reference": right_gap_reference,
        "right_gap_spread": right_gap_spread,
        "page_right_edge": page_right_edge,
    }


def format_pipeline_result(analysis):
    # formater les résultats de l'analyse pour affichage, 
    # en associant des couleurs et des labels aux types de blocs détectés 
    # pour faciliter la lecture et la compréhension des résultats 

    display_colors = {
        "espece": "vert",
        "taxon": "rouge",
        "variete": "orange",
        "commentaire": "bleu",
    }
    display_labels = {
        "variete": "variété",
    }

    formatted_lines = []
    for block in analysis["blocks"]:
        block_type = block["type"]
        label = display_labels.get(block_type, block_type)
        color = display_colors.get(block_type, "inconnu")
        formatted_lines.append(f'{label} ({color}) : {json.dumps(block["text"], ensure_ascii=False)}')

    return formatted_lines


def render_debug_image(img, analysis, output_path="ocr_debug.png"):
    # créer une image de debug avec des indicateurs visuels pour les blocs détectés,
    # les seuils d'indentation, et la marge de droite, pour aider à comprendre et vérifier l'analyse effectuée sur l'image, 
    # en sauvegardant cette image dans un fichier pour consultation
    debug_img = draw_right_gap_tube(
        img.convert("RGBA"),
        analysis["page_right_edge"],
        analysis["right_gap_reference"],
        analysis["right_gap_spread"],
    )
    draw = ImageDraw.Draw(debug_img)

    for block in analysis["blocks"]:
        if block["indent_group"] > 0:
            indent_strip_right = min(block["start_left"] + 10, block["line_right"])
            draw.rectangle(
                [block["start_left"], block["start_top"], indent_strip_right, block["start_bottom"]],
                fill=(0, 255, 0, 85)
                if block["roman_is_bullet"]
                else ((255, 165, 0, 85) if block["species_title_is_title"] else (0, 0, 255, 85)),
            )
        draw.rectangle(
            [block["line_left"], block["line_top"], block["line_right"], block["line_bottom"]],
            outline=block["color"],
            width=10,
        )
        draw.text(
            (block["start_left"], max(0, block["start_top"] - 12)),
            block["debug_label"],
            fill=block["color"],
        )

    print(f"Indent breakpoints: {analysis['indent_breakpoints'] if analysis['indent_breakpoints'] else 'none'}")
    print(
        f"Right gap reference: {analysis['right_gap_reference']}px | spread: {analysis['right_gap_spread']}px"
    )

    debug_img.save(output_path)
    print(f"Image debug save dans {output_path}")


def analyze_image(img):
    # analyser une image PIL en extrayant les lignes de texte avec tesseract.
    # pipeline complète d'analyse de l'image, de l'extraction des lignes, à l'identification des types de blocs.

    analysis = extract_line_indentation(img)
    return format_pipeline_result(analysis)


def delete_bars(ocr_result):
    # supprimer les barres verticales en début et fin de ligne dans le résultat brut de l'OCR,
    # pour nettoyer les artefacts courants d'OCR avant toute autre analyse ou affichage
    return "\n".join(strip_edge_bars(line) for line in ocr_result.splitlines())

if __name__ == "__main__":
    # exemple d'utilisation de la pipeline d'analyse sur une image spécifique,
    img = Image.open("rect_003_uid_3_bicolumn_text_left.png")

    analysis = extract_line_indentation(img) # extract indentation and classify lines

    render_debug_image(img, analysis) # debug image with visual indicators
    
    for line in analyze_image(img):
        print(line)

    #for line in format_pipeline_result(analysis): # print formatted results
    #    print(line)