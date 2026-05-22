from pathlib import Path
from collections import Counter, defaultdict
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

INDENT_COLORS = ["red", "blue", "green", "orange", "purple", "cyan", "brown", "magenta"]
ROMAN_BULLET_COLOR = "magenta"
ROMAN_CHARS = set("IVXLCDM")
ROMAN_CONFUSION_MAP = str.maketrans({"H": "I", "J": "I", "Y": "I", "1": "I", "|": "I", "l": "I"})


def compute_roman_bullet_score(line_items):
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

    if re.fullmatch(r"[IVXLCDM]+", normalized_core):
        score += 20
        reasons.append("pattern_strict")

    return max(0, min(score, 100)), first_token, reasons, normalized_core


def compute_indent_breakpoints(indent_values):
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
    if not indent_breakpoints:
        return 0

    return sum(1 for breakpoint in indent_breakpoints if indent_px > breakpoint)


def merge_visual_lines(grouped_lines):
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


def print_line_indentation(img):

    # extraire les données de tesseract avec les positions des mots
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    grouped_lines = defaultdict(list) 

    # parcourir les mots extraits et les regrouper par ligne
    for index, text in enumerate(data["text"]):
        cleaned_text = text.strip() # retirer les espaces superflus
        if not cleaned_text: # ignorer les lignes vides
            continue

        key = ( # identifier unique de la ligne
            data["page_num"][index],
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        grouped_lines[key].append( # ajouter le mot à la ligne correspondante
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

    debug_img = img.convert("RGB")
    draw = ImageDraw.Draw(debug_img)

    for visual_line in visual_lines:
        line_items = visual_line["items"]
        line_text = " ".join(item["text"] for item in line_items)
        line_left = visual_line["left"]
        line_top = visual_line["top"]
        line_right = visual_line["right"]
        line_bottom = visual_line["bottom"]
        indent_px = line_left - page_left_margin
        right_gap_px = page_right_edge - line_right
        indent_group = get_indent_group(indent_px, indent_breakpoints)
        group_color = INDENT_COLORS[indent_group]
        if indent_group > 0:
            roman_score, roman_token, roman_reasons, roman_core = compute_roman_bullet_score(line_items)
            roman_is_bullet = roman_score >= 70
        else:
            roman_score, roman_token, roman_reasons, roman_core = 0, "", [], ""
            roman_is_bullet = False
        debug_color = ROMAN_BULLET_COLOR if roman_is_bullet else group_color
        draw.rectangle(
            [line_left, line_top, line_right, line_bottom],
            outline=debug_color,
            width=10,
        )
        draw.text(
            (line_left, max(0, line_top - 12)),
            f"g{indent_group} | {indent_px}px | {right_gap_px}px | R{roman_score}%",
            fill=debug_color,
        )
        print(
            f"indent={indent_px:>4}px | group={indent_group} | R={roman_score:>3}% | bullet={'oui' if roman_is_bullet else 'non'} | token={roman_token!r} | core={roman_core!r} | left={line_left:>4}px | right_gap={right_gap_px:>4}px | {line_text}"
        )

    print(f"Indent breakpoints: {indent_breakpoints if indent_breakpoints else 'none'}")

    debug_img.save("ocr_debug.png")
    print("Image debug save dans ocr_debug.png")

img = Image.open("rect_002_uid_42_bicolumn_text_right.png")

print_line_indentation(img)

def delete_bars(ocr_result):
    lines = ocr_result.splitlines()
    lines_without_bars = [line.replace("|", "") for line in lines]
    return "\n".join(lines_without_bars)
#print("bicolumn text left (without bars)")
#print(delete_bars(ocr_result))
