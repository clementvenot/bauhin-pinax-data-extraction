import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from PIL import Image, ImageTk
import pypdfium2 as pdfium

from pipeline import pipeline as detect_page_regions

RECT_COLORS = {
    "titles": "#2d7ff9",
    "localisation": "#ffd900",
    "bicolumn_text": "#2ca02c",
    "italic_text": "#d62728",
}

RECT_STROKE_WIDTH = 3

RECT_LABELS_TO_DISPLAY = {
    "titles": "titre",
    "localisation": "localisation",
    "italic_text": "italique",
    "bicolumn_text": "bi-colonne",
}

RECT_LABELS_TO_INTERNAL = {display: internal for internal, display in RECT_LABELS_TO_DISPLAY.items()}


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def label_to_display(label):
    return RECT_LABELS_TO_DISPLAY.get(label, label)


def label_to_internal(label):
    return RECT_LABELS_TO_INTERNAL.get(label, label)


def rect_color(label):
    return RECT_COLORS.get(label_to_internal(label), RECT_COLORS["titles"])


class RectangleEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Editeur de rectangles PDF")
        self.geometry("1600x1000")

        self.pdf_path = ""
        self.document = None
        self.page_count = 0
        self.current_page = 0
        self.render_scale = 4.17

        self.page_annotations = []
        self.page_cache = {}
        self.loading_pages = set()
        self.load_queue = queue.Queue()
        self._poll_after_id = None

        self.current_image = None
        self.current_photo = None
        self.source_image_size = None
        self.display_image_size = None
        self.current_page_data = []

        self.canvas_image_id = None
        self.rect_items = {}
        self.handle_items = {}
        self.delete_cross_items = {}
        self.separator_items = {}
        self.temp_rect_id = None
        self.active_rect_uid = None
        self.action_mode = None
        self.drag_start_image = None
        self.drag_anchor_rect = None
        self.new_rect_label = tk.StringVar(value=label_to_display("titles"))
        self._next_rect_uid = 1

        self.gallery_window = None
        self.gallery_export_items = []

        self.view_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.canvas_placeholder_text = "Aucune page à afficher"

        self._build_ui()
        self.bind("<Delete>", self._delete_selected_rectangle)
        self.bind("<Escape>", self._cancel_action)

        self.after(100, self._poll_load_queue)
        self.after(100, self._prompt_for_pdf)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        main = ttk.Frame(self, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=7)
        main.rowconfigure(1, weight=1)
        main.rowconfigure(2, weight=0)

        toolbar = ttk.Frame(main)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=0)
        toolbar.columnconfigure(1, weight=1)

        toolbar_left = ttk.Frame(toolbar)
        toolbar_left.grid(row=0, column=0, sticky="w")

        toolbar_right = ttk.Frame(toolbar)
        toolbar_right.grid(row=0, column=1, sticky="e")

        ttk.Button(toolbar_left, text="Ouvrir PDF", command=self._prompt_for_pdf).grid(row=0, column=0, padx=(0, 6))

        ttk.Button(toolbar_right, text="<", command=self.prev_page).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(toolbar_right, text=">", command=self.next_page).grid(row=0, column=1, padx=(0, 12))

        self.page_label = ttk.Label(toolbar_right, text="Page 0 / 0")
        self.page_label.grid(row=0, column=2, padx=(0, 12))

        ttk.Label(toolbar_right, text="Aller à la page:").grid(row=0, column=3, padx=(0, 4))
        self.page_jump_var = tk.StringVar(value="1")
        self.page_jump_entry = ttk.Entry(toolbar_right, textvariable=self.page_jump_var, width=8, justify="right")
        self.page_jump_entry.grid(row=0, column=4, padx=(0, 4))
        self.page_jump_entry.bind("<Return>", self.go_to_page_from_entry)

        canvas_frame = ttk.Frame(main, borderwidth=1, relief="solid")
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, bg="#1f2328", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        right_panel = ttk.Frame(main, padding=(12, 0, 0, 0))
        right_panel.grid(row=0, column=1, rowspan=3, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        ttk.Button(right_panel, text="OCR", command=lambda: None).grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Label(
            right_panel,
            text="Panneau droit vide pour plus tard",
            foreground="#6b7280",
            anchor="center",
            justify="center",
        ).grid(row=1, column=0, sticky="nsew")

        bottom_bar = ttk.Frame(main)
        bottom_bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        bottom_bar.columnconfigure(7, weight=1)

        ttk.Label(bottom_bar, text="Type:").grid(row=0, column=0, padx=(0, 4))
        self.label_selector = ttk.Combobox(
            bottom_bar,
            textvariable=self.new_rect_label,
            values=["titre", "localisation", "italique", "bi-colonne"],
            state="readonly",
            width=16,
        )
        self.label_selector.grid(row=0, column=1, padx=(0, 12))
        self.label_selector.bind("<<ComboboxSelected>>", self._on_label_selector_change)

        ttk.Button(bottom_bar, text="Ajouter un rectangle", command=self.start_add_rectangle).grid(row=0, column=2, padx=(0, 6))

        self.validate_border_button_text = tk.StringVar(value="Valider bordure page 0")
        ttk.Button(bottom_bar, textvariable=self.validate_border_button_text, command=self.validate_current_page_borders).grid(row=0, column=3, padx=(0, 6))

        self.status_label = ttk.Label(bottom_bar, text="Ouvrez un PDF pour commencer.", width=34, anchor="e")
        self.status_label.grid(row=0, column=7, sticky="e")

    def _prompt_for_pdf(self):
        pdf_path = filedialog.askopenfilename(
            title="Choisir un PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if pdf_path:
            self.load_pdf(pdf_path)

    def load_pdf(self, pdf_path):
        try:
            self.document = pdfium.PdfDocument(pdf_path)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le PDF:\n{exc}")
            return

        self.pdf_path = pdf_path
        self.page_count = len(self.document)
        self.current_page = 0
        self.page_annotations = [None] * self.page_count
        self.page_cache = {}
        self.loading_pages = set()

        self._clear_interaction_state()
        self.current_image = None
        self.current_page_data = []
        self._redraw_canvas()
        self._update_page_label()
        self._request_page_load(0, show_when_ready=True)

    def _request_page_load(self, page_index, show_when_ready=False):
        if not self.pdf_path or not (0 <= page_index < self.page_count):
            return

        if page_index in self.page_cache:
            if show_when_ready:
                self._apply_loaded_page(page_index)
            return

        if page_index in self.loading_pages:
            return

        self.loading_pages.add(page_index)

        worker = threading.Thread(
            target=self._load_page_worker,
            args=(page_index,),
            daemon=True,
        )
        worker.start()

        if show_when_ready and page_index == self.current_page:
            self.current_image = None
            self.current_page_data = []
            self.canvas_placeholder_text = f"Chargement de la page {page_index + 1}"
            self._redraw_canvas()

    def _load_page_worker(self, page_index):
        try:
            document = pdfium.PdfDocument(self.pdf_path)
            image = document[page_index].render(scale=self.render_scale).to_pil().convert("RGB")
            page_result = detect_page_regions(self.pdf_path, page_index=page_index, render_scale=self.render_scale)

            annotations = []
            for label in ("titles", "bicolumn_text", "italic_text"):
                for rect_index, rect in enumerate(page_result.get(label, [])):
                    rect_label = "localisation" if label == "titles" and rect_index == 0 else label
                    annotation = {
                        "x": int(rect["x"]),
                        "y": int(rect["y"]),
                        "w": int(rect["w"]),
                        "h": int(rect["h"]),
                        "label": rect_label,
                    }

                    if label == "bicolumn_text" and "center_x" in rect:
                        annotation["center_x"] = int(rect["center_x"])

                    annotations.append(annotation)

            self.load_queue.put(("page_loaded", page_index, image, image.size, annotations))
        except Exception as exc:
            self.load_queue.put(("page_error", page_index, str(exc)))

    def _poll_load_queue(self):
        try:
            while True:
                message = self.load_queue.get_nowait()
                event = message[0]

                if event == "page_loaded":
                    _, page_index, image, source_size, annotations = message
                    self.page_cache[page_index] = {
                        "image": image,
                        "source_size": source_size,
                        "annotations": annotations,
                    }
                    self.page_annotations[page_index] = annotations
                    self.loading_pages.discard(page_index)

                    if page_index == self.current_page:
                        self._apply_loaded_page(page_index)

                elif event == "page_error":
                    _, page_index, error_message = message
                    self.loading_pages.discard(page_index)
                    if page_index == self.current_page:
                        self.current_image = None
                        self.current_page_data = []
                        self.canvas_placeholder_text = "Aucune page à afficher"
                        self._redraw_canvas()
                        self.status_label.config(text=f"Erreur page {page_index + 1}")
                    messagebox.showerror("Erreur", f"Impossible de charger la page {page_index + 1}:\n{error_message}")
        except queue.Empty:
            pass

        self._poll_after_id = self.after(100, self._poll_load_queue)

    def _apply_loaded_page(self, page_index):
        cached = self.page_cache.get(page_index)
        if not cached:
            return

        self.current_page = page_index
        self.page_jump_var.set(str(page_index + 1))
        self.source_image_size = cached.get("source_size", cached["image"].size)
        self.current_image = cached["image"]
        self.current_page_data = self._ensure_rect_uids(cached["annotations"])
        cached["annotations"] = self.current_page_data
        self.page_annotations[page_index] = self.current_page_data
        self.canvas_placeholder_text = "Aucune page à afficher"
        self._clear_interaction_state()
        self._redraw_canvas()
        self._update_page_label()

    def _new_rect_uid(self):
        uid = self._next_rect_uid
        self._next_rect_uid += 1
        return uid

    def _ensure_rect_uids(self, rectangles):
        normalized = []
        for rect in rectangles:
            item = rect.copy()
            if not item.get("uid"):
                item["uid"] = self._new_rect_uid()
            else:
                self._next_rect_uid = max(self._next_rect_uid, int(item["uid"]) + 1)
            normalized.append(item)
        return normalized

    def _load_page_annotations(self):
        # Conservé pour compatibilité, mais le chargement réel est désormais asynchrone.
        return None

    def _show_page(self, page_index):
        if not self.document or not (0 <= page_index < self.page_count):
            return

        self._save_current_page_state()
        self.current_page = page_index
        self.page_jump_var.set(str(page_index + 1))
        self._update_page_label()

        if page_index in self.page_cache:
            self._apply_loaded_page(page_index)
        else:
            self.current_image = None
            self.current_page_data = []
            self._clear_interaction_state()
            self.canvas_placeholder_text = f"Chargement de la page {page_index + 1}..."
            self._redraw_canvas()
            self._request_page_load(page_index, show_when_ready=True)

    def _save_current_page_state(self):
        if self.page_annotations and 0 <= self.current_page < len(self.page_annotations):
            self.page_annotations[self.current_page] = [rect.copy() for rect in self.current_page_data]
            if self.current_page in self.page_cache:
                self.page_cache[self.current_page]["annotations"] = self.page_annotations[self.current_page]

    def _update_page_label(self):
        self.page_label.config(text=f"Page {self.current_page + 1 if self.page_count else 0} / {self.page_count}")
        self.validate_border_button_text.set(f"Valider bordure page {self.current_page + 1 if self.page_count else 0}")
        self.status_label.config(text=f"{len(self.current_page_data)} rectangles sur cette page")

    def _make_export_display_name(self, rect_label, count, variant=None):
        display_label = label_to_display(rect_label)

        if rect_label == "localisation":
            return display_label if count == 1 else f"{display_label} {count}"

        if rect_label == "bicolumn_text" and variant:
            return f"{display_label} {count} {variant}"

        return f"{display_label} {count}"

    def _export_current_page_rectangles(self):
        if self.current_image is None:
            messagebox.showerror("Debug", "Aucune page affichée à enregistrer.")
            return []

        rectangles = self.current_page_data or []
        if not rectangles:
            messagebox.showerror("Debug", "Aucun rectangle à enregistrer sur cette page.")
            return []

        if self.pdf_path:
            debug_dir = Path(self.pdf_path).with_name(f"{Path(self.pdf_path).stem}_page_{self.current_page + 1}_rectangles")
        else:
            debug_dir = Path.cwd() / f"page_{self.current_page + 1}_rectangles"

        debug_dir.mkdir(parents=True, exist_ok=True)

        saved_items = []
        image_width, image_height = self.current_image.size
        label_counts = {"titles": 0, "localisation": 0, "italic_text": 0, "bicolumn_text": 0}

        ordered_rectangles = sorted(rectangles, key=lambda rect: (rect["y"], rect["x"]))

        for index, rect in enumerate(ordered_rectangles, start=1):
            x1 = int(clamp(rect["x"], 0, image_width))
            y1 = int(clamp(rect["y"], 0, image_height))
            x2 = int(clamp(rect["x"] + rect["w"], 0, image_width))
            y2 = int(clamp(rect["y"] + rect["h"], 0, image_height))

            if x2 <= x1 or y2 <= y1:
                continue

            rect_uid = rect.get("uid", index)
            rect_label = rect.get("label", "manual")

            if rect_label == "bicolumn_text":
                label_counts[rect_label] += 1
                rect_count = label_counts[rect_label]
                separator_x = int(clamp(rect.get("center_x", x1 + (x2 - x1) // 2), x1, x2))

                if separator_x > x1:
                    left_name = self._make_export_display_name(rect_label, rect_count, "gauche")
                    left_path = debug_dir / f"{left_name.lower().replace(' ', '_')}.png"
                    self.current_image.crop((x1, y1, separator_x, y2)).save(left_path)
                    saved_items.append({"path": left_path, "name": left_name})

                if x2 > separator_x:
                    right_name = self._make_export_display_name(rect_label, rect_count, "droite")
                    right_path = debug_dir / f"{right_name.lower().replace(' ', '_')}.png"
                    self.current_image.crop((separator_x, y1, x2, y2)).save(right_path)
                    saved_items.append({"path": right_path, "name": right_name})
                continue

            label_counts[rect_label] = label_counts.get(rect_label, 0) + 1
            rect_count = label_counts[rect_label]
            display_name = self._make_export_display_name(rect_label, rect_count)
            export_path = debug_dir / f"{display_name.lower().replace(' ', '_')}.png"
            self.current_image.crop((x1, y1, x2, y2)).save(export_path)
            saved_items.append({"path": export_path, "name": display_name})

        if not saved_items:
            messagebox.showerror("Debug", "Aucun rectangle valide n'a pu être enregistré.")
            return []

        return saved_items

    def _open_rectangles_gallery(self, exported_items):
        if self.gallery_window is not None and self.gallery_window.winfo_exists():
            self.gallery_window.destroy()

        gallery_window = tk.Toplevel(self)
        self.gallery_window = gallery_window
        gallery_window.title(f"PNG générés - page {self.current_page + 1}")
        gallery_window.geometry("1600x900")
        gallery_window.columnconfigure(0, weight=1)
        gallery_window.columnconfigure(1, weight=1)
        gallery_window.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(gallery_window, padding=12)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)

        ttk.Label(left_panel, text="Images générées", font=("Helvetica", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))

        scroll_container = ttk.Frame(left_panel)
        scroll_container.grid(row=1, column=0, sticky="nsew")
        scroll_container.columnconfigure(0, weight=1)
        scroll_container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_container, bg="#f8fafc", highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content_frame = ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")

        def _update_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _resize_content(event):
            canvas.itemconfigure(content_window, width=event.width)

        content_frame.bind("<Configure>", _update_scrollregion)
        canvas.bind("<Configure>", _resize_content)

        photo_refs = []
        for item in exported_items:
            card = ttk.Frame(content_frame, padding=10, relief="solid")
            card.pack(fill="x", pady=(0, 10))

            ttk.Label(card, text=item["name"], anchor="w", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 6))

            with Image.open(item["path"]) as image:
                preview = image.convert("RGB")
                preview.thumbnail((760, 240), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(preview)

            photo_refs.append(photo)
            ttk.Label(card, image=photo).pack(anchor="w")

        gallery_window._photo_refs = photo_refs

        right_panel = ttk.Frame(gallery_window, padding=12)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)

        ttk.Frame(right_panel).grid(row=0, column=0, sticky="nsew")

    def validate_current_page_borders(self):
        exported_items = self._export_current_page_rectangles()
        if not exported_items:
            return

        self.gallery_export_items = exported_items
        self._open_rectangles_gallery(exported_items)
        self.status_label.config(text=f"{len(exported_items)} PNG générés")

    def prev_page(self):
        if self.page_count and self.current_page > 0:
            self._show_page(self.current_page - 1)

    def next_page(self):
        if self.page_count and self.current_page < self.page_count - 1:
            self._show_page(self.current_page + 1)

    def go_to_page_from_entry(self, event=None):
        if not self.page_count:
            return

        try:
            page_number = int(self.page_jump_var.get().strip())
        except ValueError:
            messagebox.showerror("Erreur", "Entrez un numero de page valide.")
            self.page_jump_var.set(str(self.current_page + 1))
            return

        if not (1 <= page_number <= self.page_count):
            messagebox.showerror("Erreur", f"Entrez un numero entre 1 et {self.page_count}.")
            self.page_jump_var.set(str(self.current_page + 1))
            return

        self._show_page(page_number - 1)

    def _fit_image_to_canvas(self):
        if self.current_image is None:
            return None

        canvas_width = max(self.canvas.winfo_width(), 1)
        canvas_height = max(self.canvas.winfo_height(), 1)
        image_width, image_height = self.current_image.size
        scale = min(canvas_width / image_width, canvas_height / image_height)
        scale = min(scale, 1.0) if image_width and image_height else 1.0

        display_width = max(int(image_width * scale), 1)
        display_height = max(int(image_height * scale), 1)
        offset_x = (canvas_width - display_width) // 2
        offset_y = (canvas_height - display_height) // 2

        self.view_scale = scale
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.display_image_size = (display_width, display_height)

        return self.current_image.resize((display_width, display_height), Image.Resampling.LANCZOS)

    def _redraw_canvas(self):
        self.canvas.delete("all")
        self.rect_items.clear()
        self.handle_items.clear()
        self.delete_cross_items.clear()
        self.separator_items.clear()

        if self.current_image is None:
            message = self.canvas_placeholder_text
            if self.current_page not in self.loading_pages:
                message = "Aucune page à afficher"
            self.canvas.create_text(
                self.canvas.winfo_width() // 2,
                self.canvas.winfo_height() // 2,
                text=message,
                fill="white",
                font=("Helvetica", 18),
            )
            return

        display_image = self._fit_image_to_canvas()
        if display_image is None:
            return

        self.current_photo = ImageTk.PhotoImage(display_image)
        self.canvas.create_image(
            self.offset_x,
            self.offset_y,
            anchor="nw",
            image=self.current_photo,
        )

        for rect in self.current_page_data:
            self._draw_rectangle(rect)

    def _image_to_canvas(self, x, y):
        return self.offset_x + x * self.view_scale, self.offset_y + y * self.view_scale

    def _canvas_to_image(self, x, y):
        image_x = (x - self.offset_x) / self.view_scale if self.view_scale else x
        image_y = (y - self.offset_y) / self.view_scale if self.view_scale else y
        if self.current_image is None:
            return image_x, image_y
        image_width, image_height = self.current_image.size
        return (
            clamp(image_x, 0, image_width),
            clamp(image_y, 0, image_height),
        )

    def _draw_rectangle(self, rect):
        if not rect.get("uid"):
            rect["uid"] = self._new_rect_uid()
        else:
            self._next_rect_uid = max(self._next_rect_uid, int(rect["uid"]) + 1)

        canvas_x1, canvas_y1 = self._image_to_canvas(rect["x"], rect["y"])
        canvas_x2, canvas_y2 = self._image_to_canvas(rect["x"] + rect["w"], rect["y"] + rect["h"])
        color = rect_color(rect.get("label", "manual"))
        width = RECT_STROKE_WIDTH

        rect_id = self.canvas.create_rectangle(
            canvas_x1,
            canvas_y1,
            canvas_x2,
            canvas_y2,
            outline=color,
            width=width,
            tags=("rect",),
        )
        self.canvas.tag_bind(rect_id, "<ButtonPress-1>", self._on_canvas_press)
        self.canvas.tag_bind(rect_id, "<B1-Motion>", self._on_canvas_drag)
        self.canvas.tag_bind(rect_id, "<ButtonRelease-1>", self._on_canvas_release)

        rect["canvas_id"] = rect_id
        self.rect_items[rect_id] = rect

        self._draw_separator(rect)
        self._draw_handles(rect)
        self._draw_delete_cross(rect)

    def _get_separator_x(self, rect):
        separator_x = rect.get("center_x")
        if separator_x is None:
            separator_x = rect["x"] + rect["w"] // 2
        return int(clamp(separator_x, rect["x"], rect["x"] + rect["w"]))

    def _draw_separator(self, rect):
        if rect.get("label") != "bicolumn_text":
            return

        separator_x = self._get_separator_x(rect)
        canvas_x = self._image_to_canvas(separator_x, 0)[0]
        x1, y1 = self._image_to_canvas(separator_x, rect["y"])
        x2, y2 = self._image_to_canvas(separator_x, rect["y"] + rect["h"])

        separator_id = self.canvas.create_line(
            canvas_x,
            y1,
            canvas_x,
            y2,
            fill="#111111",
            width=4,
            tags=("separator",),
        )
        self.separator_items[separator_id] = rect["uid"]

    def _find_separator_at_canvas_point(self, canvas_x, canvas_y):
        hits = self.canvas.find_overlapping(canvas_x - 6, canvas_y - 6, canvas_x + 6, canvas_y + 6)
        for item_id in reversed(hits):
            if item_id in self.separator_items:
                return self._get_rect_by_uid(self.separator_items[item_id])
        return None

    def _draw_handles(self, rect):
        if rect.get("uid") != self.active_rect_uid:
            return

        x1, y1 = self._image_to_canvas(rect["x"], rect["y"])
        x2, y2 = self._image_to_canvas(rect["x"] + rect["w"], rect["y"] + rect["h"])
        x_mid = (x1 + x2) / 2
        y_mid = (y1 + y2) / 2
        handle_size = 6

        for hx, hy, name in (
            (x1, y1, "nw"),
            (x_mid, y1, "n"),
            (x2, y1, "ne"),
            (x2, y_mid, "e"),
            (x2, y2, "se"),
            (x_mid, y2, "s"),
            (x1, y2, "sw"),
            (x1, y_mid, "w"),
        ):
            handle = self.canvas.create_rectangle(
                hx - handle_size,
                hy - handle_size,
                hx + handle_size,
                hy + handle_size,
                fill="#ffffff",
                outline="#111111",
                width=1,
                tags=("handle", name),
            )
            self.handle_items[handle] = {"rect_uid": rect["uid"], "handle": name}

    def _draw_delete_cross(self, rect):
        if rect.get("uid") != self.active_rect_uid:
            return

        x2, y_mid = self._image_to_canvas(rect["x"] + rect["w"], rect["y"] + rect["h"] / 2)
        cross_center_x = min(x2 + 14, max(self.canvas.winfo_width() - 14, 14))
        cross_center_y = y_mid
        cross_size = 10

        background = self.canvas.create_oval(
            cross_center_x - cross_size,
            cross_center_y - cross_size,
            cross_center_x + cross_size,
            cross_center_y + cross_size,
            fill="#d9534f",
            outline="#8c2d2a",
            width=1,
            tags=("delete_cross",),
        )
        line1 = self.canvas.create_line(
            cross_center_x - 4,
            cross_center_y - 4,
            cross_center_x + 4,
            cross_center_y + 4,
            fill="white",
            width=2,
            tags=("delete_cross",),
        )
        line2 = self.canvas.create_line(
            cross_center_x - 4,
            cross_center_y + 4,
            cross_center_x + 4,
            cross_center_y - 4,
            fill="white",
            width=2,
            tags=("delete_cross",),
        )

        for item_id in (background, line1, line2):
            self.delete_cross_items[item_id] = rect["uid"]
            self.canvas.tag_bind(item_id, "<ButtonPress-1>", self._on_delete_cross_press)

    def _refresh_active_rectangle_display(self):
        for separator_id, rect_uid in list(self.separator_items.items()):
            if rect_uid == self.active_rect_uid:
                self.canvas.delete(separator_id)
                del self.separator_items[separator_id]

        for handle_id in list(self.handle_items):
            self.canvas.delete(handle_id)
        self.handle_items.clear()

        for cross_id in list(self.delete_cross_items):
            self.canvas.delete(cross_id)
        self.delete_cross_items.clear()

        rect = self._get_rect_by_uid(self.active_rect_uid)
        if rect is None:
            return

        rect_id = rect.get("canvas_id")
        if rect_id is None or rect_id not in self.rect_items:
            self._redraw_canvas()
            return

        for handle_id, handle_data in list(self.handle_items.items()):
            if handle_data["rect_uid"] == rect["uid"]:
                self.canvas.delete(handle_id)
                del self.handle_items[handle_id]

        canvas_x1, canvas_y1 = self._image_to_canvas(rect["x"], rect["y"])
        canvas_x2, canvas_y2 = self._image_to_canvas(rect["x"] + rect["w"], rect["y"] + rect["h"])
        self.canvas.coords(rect_id, canvas_x1, canvas_y1, canvas_x2, canvas_y2)
        self.canvas.itemconfig(
            rect_id,
            outline=rect_color(rect.get("label", "manual")),
            width=RECT_STROKE_WIDTH,
        )

        self._draw_separator(rect)
        self._draw_handles(rect)
        self._draw_delete_cross(rect)

    def _set_active_rectangle(self, rect_uid):
        previous_uid = self.active_rect_uid
        if previous_uid == rect_uid:
            rect = self._get_rect_by_uid(rect_uid)
            self._sync_label_selector_to_rect(rect)
            self._refresh_active_rectangle_display()
            return

        if previous_uid is not None:
            previous_rect = self._get_rect_by_uid(previous_uid)
            if previous_rect is not None:
                previous_canvas_id = previous_rect.get("canvas_id")
                if previous_canvas_id in self.rect_items:
                        self.canvas.itemconfig(previous_canvas_id, width=RECT_STROKE_WIDTH)

        self.active_rect_uid = rect_uid

        if rect_uid is None:
            self._refresh_active_rectangle_display()
            return

        rect = self._get_rect_by_uid(rect_uid)
        self._sync_label_selector_to_rect(rect)
        self._refresh_active_rectangle_display()

    def _sync_label_selector_to_rect(self, rect):
        if rect is None:
            return

        label = label_to_display(label_to_internal(rect.get("label", "manual")))
        if label not in self.label_selector["values"]:
            label = self.label_selector["values"][0]

        if self.new_rect_label.get() != label:
            self.new_rect_label.set(label)

    def _set_rect_label(self, rect_uid, label):
        rect = self._get_rect_by_uid(rect_uid)
        if rect is None:
            return

        label = label_to_internal(label)
        if label_to_display(label) not in self.label_selector["values"]:
            label = label_to_internal(self.label_selector["values"][0])

        rect["label"] = label
        self._save_current_page_state()
        if rect_uid == self.active_rect_uid:
            self._refresh_active_rectangle_display()
        else:
            self._redraw_canvas()

    def _on_label_selector_change(self, event=None):
        label = label_to_internal(self.new_rect_label.get())

        if self.active_rect_uid is not None:
            self._set_rect_label(self.active_rect_uid, label)
            return

        if self.new_rect_label.get() not in self.label_selector["values"]:
            self.new_rect_label.set(self.label_selector["values"][0])

    def _get_rect_by_uid(self, rect_uid):
        for rect in self.current_page_data:
            if rect.get("uid") == rect_uid:
                return rect
        return None

    def _find_rect_at_canvas_point(self, canvas_x, canvas_y):
        image_x, image_y = self._canvas_to_image(canvas_x, canvas_y)

        for rect in reversed(self.current_page_data):
            if (
                rect["x"] <= image_x <= rect["x"] + rect["w"] and
                rect["y"] <= image_y <= rect["y"] + rect["h"]
            ):
                return rect
        return None

    def _find_handle_at_canvas_point(self, canvas_x, canvas_y):
        hits = self.canvas.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)
        for item_id in reversed(hits):
            if item_id in self.handle_items:
                return self.handle_items[item_id]
        return None

    def _find_delete_cross_at_canvas_point(self, canvas_x, canvas_y):
        hits = self.canvas.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)
        for item_id in reversed(hits):
            if item_id in self.delete_cross_items:
                return self.delete_cross_items[item_id]
        return None

    def _on_delete_cross_press(self, event):
        delete_cross_uid = self._find_delete_cross_at_canvas_point(event.x, event.y)
        if delete_cross_uid is None:
            return "break"

        self._set_active_rectangle(delete_cross_uid)
        self._delete_selected_rectangle()
        return "break"

    def _clear_interaction_state(self, keep_selection=False):
        self.action_mode = None
        self.drag_start_image = None
        self.drag_anchor_rect = None
        if not keep_selection:
            self.active_rect_uid = None
        self.temp_rect_id = None

    def _on_canvas_resize(self, event):
        if self.current_image is not None:
            self._redraw_canvas()

    def start_add_rectangle(self):
        if self.current_image is None:
            return
        self._clear_interaction_state()
        self.action_mode = "add"
        self.status_label.config(text="Cliquez et glissez pour dessiner un rectangle")

    def _cancel_action(self, event=None):
        if self.action_mode == "add" and self.temp_rect_id is not None:
            self.canvas.delete(self.temp_rect_id)
            self.temp_rect_id = None
        self._clear_interaction_state()
        self._redraw_canvas()

    def _on_canvas_press(self, event):
        if self.current_image is None:
            return

        canvas_x, canvas_y = event.x, event.y
        image_x, image_y = self._canvas_to_image(canvas_x, canvas_y)

        if self.action_mode == "add":
            self.drag_start_image = (image_x, image_y)
            self.temp_rect_id = self.canvas.create_rectangle(
                canvas_x,
                canvas_y,
                canvas_x,
                canvas_y,
                outline=rect_color(label_to_internal(self.new_rect_label.get())),
                width=RECT_STROKE_WIDTH,
                dash=(4, 2),
            )
            return

        delete_cross_uid = self._find_delete_cross_at_canvas_point(canvas_x, canvas_y)
        if delete_cross_uid is not None:
            self._set_active_rectangle(delete_cross_uid)
            self._delete_selected_rectangle()
            return

        handle = self._find_handle_at_canvas_point(canvas_x, canvas_y)
        if handle:
            self._set_active_rectangle(handle["rect_uid"])
            self.action_mode = f"resize:{handle['handle']}"
            self.drag_start_image = (image_x, image_y)
            self.drag_anchor_rect = self._get_rect_by_uid(self.active_rect_uid).copy()
            return

        separator_rect = self._find_separator_at_canvas_point(canvas_x, canvas_y)
        if separator_rect:
            self._set_active_rectangle(separator_rect["uid"])
            self.action_mode = "separator"
            self.drag_start_image = (image_x, image_y)
            self.drag_anchor_rect = separator_rect.copy()
            self.status_label.config(text="Glissez le trait pour corriger la séparation")
            return

        rect = self._find_rect_at_canvas_point(canvas_x, canvas_y)
        if rect:
            self._set_active_rectangle(rect["uid"])
            self.action_mode = "move"
            self.drag_start_image = (image_x, image_y)
            self.drag_anchor_rect = rect.copy()
            return

        self._clear_interaction_state()
        self._redraw_canvas()

    def _on_canvas_drag(self, event):
        if self.current_image is None or self.action_mode is None:
            return

        canvas_x, canvas_y = event.x, event.y
        image_x, image_y = self._canvas_to_image(canvas_x, canvas_y)

        if self.action_mode == "add" and self.temp_rect_id is not None and self.drag_start_image:
            x0, y0 = self.drag_start_image
            x1 = clamp(min(x0, image_x), 0, self.current_image.size[0])
            y1 = clamp(min(y0, image_y), 0, self.current_image.size[1])
            x2 = clamp(max(x0, image_x), 0, self.current_image.size[0])
            y2 = clamp(max(y0, image_y), 0, self.current_image.size[1])

            self.canvas.coords(
                self.temp_rect_id,
                *self._image_to_canvas(x1, y1),
                *self._image_to_canvas(x2, y2),
            )
            return

        rect = self._get_rect_by_uid(self.active_rect_uid)
        if rect is None or self.drag_anchor_rect is None or self.drag_start_image is None:
            return

        dx = image_x - self.drag_start_image[0]
        dy = image_y - self.drag_start_image[1]
        base = self.drag_anchor_rect

        if self.action_mode == "move":
            rect["x"] = int(clamp(base["x"] + dx, 0, self.current_image.size[0] - 1))
            rect["y"] = int(clamp(base["y"] + dy, 0, self.current_image.size[1] - 1))
            if rect.get("label") == "bicolumn_text":
                separator_x = base.get("center_x", base["x"] + base["w"] // 2) + dx
                rect["center_x"] = int(clamp(separator_x, rect["x"], rect["x"] + rect["w"]))
        elif self.action_mode == "separator":
            if rect.get("label") == "bicolumn_text":
                separator_x = base.get("center_x", base["x"] + base["w"] // 2) + dx
                rect["center_x"] = int(clamp(separator_x, rect["x"], rect["x"] + rect["w"]))
        elif self.action_mode.startswith("resize:"):
            handle = self.action_mode.split(":", 1)[1]
            x1 = base["x"]
            y1 = base["y"]
            x2 = base["x"] + base["w"]
            y2 = base["y"] + base["h"]

            if "w" in handle:
                x1 = clamp(image_x, 0, x2 - 1)
            if "e" in handle:
                x2 = clamp(image_x, x1 + 1, self.current_image.size[0])
            if "n" in handle:
                y1 = clamp(image_y, 0, y2 - 1)
            if "s" in handle:
                y2 = clamp(image_y, y1 + 1, self.current_image.size[1])

            rect["x"] = int(x1)
            rect["y"] = int(y1)
            rect["w"] = max(1, int(x2 - x1))
            rect["h"] = max(1, int(y2 - y1))
            if rect.get("label") == "bicolumn_text":
                separator_x = base.get("center_x", base["x"] + base["w"] // 2)
                rect["center_x"] = int(clamp(separator_x, rect["x"], rect["x"] + rect["w"]))

        self._refresh_active_rectangle_display()

    def _on_canvas_release(self, event):
        if self.current_image is None or self.action_mode is None:
            return

        if self.action_mode == "add" and self.temp_rect_id is not None and self.drag_start_image:
            start_x, start_y = self.drag_start_image
            end_x, end_y = self._canvas_to_image(event.x, event.y)

            x1 = int(clamp(min(start_x, end_x), 0, self.current_image.size[0]))
            y1 = int(clamp(min(start_y, end_y), 0, self.current_image.size[1]))
            x2 = int(clamp(max(start_x, end_x), 0, self.current_image.size[0]))
            y2 = int(clamp(max(start_y, end_y), 0, self.current_image.size[1]))

            self.canvas.delete(self.temp_rect_id)
            self.temp_rect_id = None

            if (x2 - x1) > 4 and (y2 - y1) > 4:
                new_rect = {
                    "uid": self._new_rect_uid(),
                    "x": x1,
                    "y": y1,
                    "w": x2 - x1,
                    "h": y2 - y1,
                    "label": label_to_internal(self.new_rect_label.get()),
                }
                if new_rect["label"] == "bicolumn_text":
                    new_rect["center_x"] = x1 + (x2 - x1) // 2
                self.current_page_data.append(new_rect)
                self._set_active_rectangle(new_rect["uid"])

            self._clear_interaction_state(keep_selection=True)
            self._redraw_canvas()
            return

        self._clear_interaction_state(keep_selection=True)
        self._refresh_active_rectangle_display()

    def _delete_selected_rectangle(self, event=None):
        if self.active_rect_uid is None:
            return

        rect = self._get_rect_by_uid(self.active_rect_uid)
        if rect in self.current_page_data:
            self.current_page_data.remove(rect)

        self._save_current_page_state()
        self._clear_interaction_state()
        self._redraw_canvas()

    def _build_rectangle_payload(self):
        self._save_current_page_state()

        return {
            "pdf_path": self.pdf_path,
            "pages": [
                {
                    "page_index": index,
                    "page_number": index + 1,
                    "rectangles": [
                        {
                            "x": rect["x"],
                            "y": rect["y"],
                            "w": rect["w"],
                            "h": rect["h"],
                            "label": rect.get("label", "manual"),
                            **({"center_x": rect["center_x"]} if rect.get("label") == "bicolumn_text" and "center_x" in rect else {}),
                        }
                        for rect in (page_rects or [])
                    ],
                }
                for index, page_rects in enumerate(self.page_annotations)
            ],
        }

    def validate_and_print_json(self):
        payload = self._build_rectangle_payload()
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        messagebox.showinfo("Validation", "JSON imprimé dans la console.")

    def save_rectangles_debug(self):
        exported_items = self._export_current_page_rectangles()
        if not exported_items:
            return

        messagebox.showinfo("Debug", "Rectangles enregistrés dans:\n" + "\n".join(str(item["path"]) for item in exported_items))


if __name__ == "__main__":
    app = RectangleEditorApp()
    app.mainloop()