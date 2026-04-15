import tkinter as tk
from collections import OrderedDict
from importlib import import_module
from os.path import basename
from tkinter import filedialog, messagebox, Button, Tk
import numpy as np
from PIL import Image, ImageTk

from matplotlib import image
from traitement_image import invert, grayscale, threshold, noise_removal, thick_font, thin_font, remove_black_borders, convert_pdf_to_image


class ImageProcessingApp(Tk):
    def __init__ (self) :
        super().__init__()
        self.title("Image Processing App")
        self.geometry("1920x1080")
        self.image = None
        self.pdf_page_image = None
        self.tk_pdf_image = None
        self.pdf_path = "/Users/clementvenot/git/bauhin-pinax-data-extraction/pinax bsb-p49.pdf"

        # Configuration de la grille pour une disposition responsive
        # Rows
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)
        # Columns
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Création des conteneurs pour les différentes sections de l'interface
        # Le conteneur principal pour l'affichage de l'image PDF
        image_container = tk.Frame(self, bg="lightgray")
        image_container.grid(row=0, column=0,rowspan=2, sticky="nsew", padx=5, pady=5)
        # Le conteneur pour les boutons d'importation et de modification des fonctionnalités
        import_img_container = tk.Frame(self, bg="darkgray")
        import_img_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        # Le conteneur pour les fonctionnalités de modification de l'image
        features_mod_container = tk.Frame(self, bg="gray")
        features_mod_container.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # Configuration de la grille pour le conteneur d'affichage de l'image PDF
        image_container.grid_rowconfigure(0, weight=1)
        image_container.grid_rowconfigure(1, weight=1)
        image_container.grid_columnconfigure(0, weight=1)
        image_container.grid_columnconfigure(1, weight=1)
        image_container.grid_columnconfigure(2, weight=1)

        Button1 = Button(image_container, text="Button 1")
        Button1.grid(row=1, column=0,  sticky="nsew")

        self.imagePDF = self.show_pdf_image(image_container)
        self.imagePDF.bind("<Configure>", self.resize_pdf_image)

        Button3 = Button(image_container, text="Button 3")
        Button3.grid(row=1, column=2, sticky="nsew")

    def show_pdf_image(self, image_container):
        self.pdf_page_image = self.get_pdf_image_page(0)
        if self.pdf_page_image is not None:
            imagePDF = tk.Label(image_container, bg="white")
        else:
            imagePDF = tk.Label(image_container, text="Impossible de charger la page PDF", bg="white")
        imagePDF.grid(row=0, column=0,columnspan=3,  sticky="nsew")
        return imagePDF

    def resize_pdf_image(self, event=None):
        image_pdf = getattr(self, "imagePDF", None)
        if self.pdf_page_image is None or image_pdf is None:
            return

        available_width = image_pdf.winfo_width() if event is None else event.width
        available_height = image_pdf.winfo_height() if event is None else event.height

        if available_width <= 1 or available_height <= 1:
            return

        display_image = self.pdf_page_image.copy()
        display_image.thumbnail(
            (max(available_width - 10, 1), max(available_height - 10, 1)),
            Image.Resampling.LANCZOS,
        )
        self.tk_pdf_image = ImageTk.PhotoImage(display_image)
        image_pdf.configure(image=self.tk_pdf_image, text="")

    def import_pdf(self, pdfPath):
        self.pdf_path = pdfPath

    def get_pdf_path(self):
        return self.pdf_path

    def get_pdf_image_page(self, page_number):
        if self.pdf_path:
            return convert_pdf_to_image(self.pdf_path, page_number)
        messagebox.showerror("Error", "No PDF file selected.")
        return None

window = ImageProcessingApp()
window.mainloop()