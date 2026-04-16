import tkinter as tk
from tkinter import messagebox, Tk, ttk
from PIL import Image, ImageTk
import pypdfium2 as pdfium

from matplotlib import image
from traitement_image import invert, grayscale, threshold, noise_removal, thick_font, thin_font, remove_black_borders, convert_pdf_to_image


class ImageProcessingApp(Tk):
    # ---------------------------------------------------------------------------------
    # ------- Classe principale de l'application GUI pour le traitement d'image -------
    # ---------------------------------------------------------------------------------

    def __init__ (self) :
        # ------- Initialisation de la classe Tk pour créer une application GUI -------
        super().__init__()

        self.title("Traitement d'image pour OCR")
        self.geometry("1920x1080")

        self.pdf_page = None # Image PIL de la page PDF actuellement affichée
        self.image_page = None # Image Tkinter pour l'affichage de la page PDF
        self.pdf_path = "/Users/clementvenot/git/bauhin-pinax-data-extraction/Caspari Bauhini Viri Clariss. Pinax Theatri Botanici sive Index in Theophrasti Dioscoridis Plinii et botanicorum qui a seculo scripserunt opera.pdf"
        
        # Initialisation de la page courante et du nombre total de pages du PDF
        self.current_page = 0
        self.page_count = self.get_pdf_page_count()

        # ------- Configuration de la grille pour une disposition responsive ---------
        # Rows
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)
        # Columns
        self.grid_columnconfigure(0, weight=2, uniform="layout")
        self.grid_columnconfigure(1, weight=1, uniform="layout")

        # --- Création des conteneurs pour les différentes sections de l'interface ---
        # Le conteneur principal pour l'affichage de l'image PDF
        image_container = ttk.Frame(self)
        image_container.grid(row=0, column=0,rowspan=2, sticky="nsew", padx=5, pady=5)
        image_container.grid_propagate(False) # Empêche de redimensionner en fonction de son contenu
        # Le conteneur pour les boutons d'importation et de modification des fonctionnalités
        import_img_container = ttk.Frame(self)
        import_img_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        import_img_container.grid_propagate(False)
        # Le conteneur pour les fonctionnalités de modification de l'image
        features_mod_container = ttk.Frame(self)
        features_mod_container.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        features_mod_container.grid_propagate(False)

        # ----------------------------------------------------------------------------
        # Conteneur pour les boutons de navigation et affichage des pages du PDF
        # ----------------------------------------------------------------------------

        # -- Configuration de la grille pour le conteneur d'affichage de l'image PDF -
        # Rows
        image_container.grid_rowconfigure(0, weight=1)
        image_container.grid_rowconfigure(1, weight=0) 
        # Columns
        image_container.grid_columnconfigure(0, weight=1)
        image_container.grid_columnconfigure(1, weight=1)
        image_container.grid_columnconfigure(2, weight=1)
        image_container.grid_columnconfigure(3, weight=1)

        # Zone  PDF sur toute la largeur (4 colonnes) pour le centrage de l'image PDF
        self.image_area = ttk.Frame(image_container)
        self.image_area.grid(row=0, column=0, columnspan=4, sticky="nsew")
        self.image_area.grid_rowconfigure(0, weight=1)
        self.image_area.grid_columnconfigure(0, weight=1)

        # ------------------------- Boutons de navigation ----------------------------
        # Bouton précédent
        self.button_previous_page = ttk.Button(image_container, text="<", command=lambda: self.go_to_page(self.current_page - 1))
        self.button_previous_page.grid(row=1, column=0, sticky="ews" , pady=(0, 3))
        # Bouton suivant
        self.button_next_page = ttk.Button(image_container, text=">", command=lambda: self.go_to_page(self.current_page + 1))
        self.button_next_page.grid(row=1, column=3, sticky="wes", pady=(0, 3))
        # Saisie du numero de page et validation par "Entrée"
        self.page_entry_var = tk.StringVar(value=str(self.current_page + 1 if self.page_count else 0))
        self.page_entry = ttk.Entry(image_container, textvariable=self.page_entry_var, justify="right")
        # Validation de la saisie du numero de page par "Entrée"
        self.page_entry.grid(row=1, column=1, sticky="es")
        self.page_entry.bind("<Return>", self.go_to_page_from_entry)
        # Affichage nombre de page total
        self.page_count_label = ttk.Label(
            image_container,
            text=f"/ {self.page_count} page{('s' if self.page_count != 1 else '')}",
            anchor="w",
        )
        self.page_count_label.grid(row=1, column=2,pady=(0, 4), sticky="sw")
        # Affichage de la page PDF
        self.imagePDF = self.show_pdf_image(self.image_area)
        self.image_area.bind("<Configure>", self.resize_pdf_image)
        self.update_navigation_buttons()

    
    # --------------------------------------------------------------------------------
    # ------- Fonctions pour l'affichage et la navigation dans les pages du PDF ------
    # --------------------------------------------------------------------------------

    def show_pdf_image(self, image_container):
        # ----- Affichage de la page PDF dans le conteneur dédié ---------------------
        # ----- Gestion du cas où la page ne peut pas être chargée -------------------
        self.pdf_page = self.get_pdf_image_page()
        if self.pdf_page is not None:
            self.imagePDF = ttk.Label(image_container) # Création d'un label pour afficher l'image PDF
        else:
            self.imagePDF = ttk.Label(image_container, text="Pas de PDF disponible")
        self.imagePDF.grid(row=0, column=0)
        if self.pdf_page is not None:
            # Redimensionnement de l'image après son affichage pour s'adapter à la taille du conteneur
            self.imagePDF.after_idle(self.resize_pdf_image)
        return self.imagePDF

    def resize_pdf_image(self, event=None):
        image_pdf = getattr(self, "imagePDF", None) 
        # S'il n'y a pas de PDF : on ne fait rien
        if self.pdf_page is None or image_pdf is None:
            return
        # Calcul de la taille disponible pour afficher l'image 
        available_width = self.image_area.winfo_width() if event is None else event.width
        available_height = self.image_area.winfo_height() if event is None else event.height
        # Si la taille disponible est trop petite, on ne fait rien
        if available_width <= 1 or available_height <= 1:
            return
        # Redimensionnement de l'image PDF pour s'adapter à la taille disponible tout en conservant les proportions
        display_image = self.pdf_page.copy()
        display_image.thumbnail(
            (max(available_width - 10, 1), max(available_height - 10, 1)),
            Image.Resampling.LANCZOS,
        )
        # Mise à jour de l'image affichée dans le label + suppr text si présent
        self.image_page = ImageTk.PhotoImage(display_image)
        image_pdf.configure(image=self.image_page, text="")

    def import_pdf(self, pdfPath):
        # --- Fonction pour importer un PDF et mettre à jour le chemin du PDF dans l'application -----
        self.pdf_path = pdfPath

    def get_pdf_image_page(self):
        # --- Fonction pour obtenir l'image PIL de la page PDF courante, avec gestion des erreurs ----
        if self.pdf_path:
            try:
                return convert_pdf_to_image(self.pdf_path, self.current_page) # Conversion de la page PDF en image PIL
            except Exception:
                return None
        return None

    def get_pdf_page_count(self):
        # --- Fonction pour obtenir le nombre de pages du PDF, avec gestion des erreurs --------------
        if not self.pdf_path:
            return 0
        try:
            document = pdfium.PdfDocument(str(self.pdf_path)) # Ouverture du PDF pour compter le nombre de pages
            return len(document)
        except Exception:
            return 0
    
    def go_to_page(self, page_number):
        # --- page_number est un index interne 0-based -----------------------------------------------
        if self.page_count and 0 <= page_number < self.page_count:
            self.current_page = page_number
            self.pdf_page = self.get_pdf_image_page()
            self.resize_pdf_image()
            self.page_entry_var.set(str(self.current_page + 1))
            self.update_navigation_buttons()
            return

    def update_navigation_buttons(self):
        # --- Mise à jour de l'état des boutons de navigation en fonction de la page courante et du nombre total de pages ---
        has_pages = bool(self.page_count)
        previous_state = "normal" if has_pages and self.current_page > 0 else "disabled"
        next_state = "normal" if has_pages and self.current_page < self.page_count - 1 else "disabled"
        self.button_previous_page.config(state=previous_state)
        self.button_next_page.config(state=next_state)

    def go_to_page_from_entry(self, event=None):
        # --- Validation de la saisie du numero de page et navigation vers la page correspondante ---
        try:
            page_number = int(self.page_entry_var.get().strip()) # Conversion de la saisie en entier
        except ValueError:
            messagebox.showerror("Erreur", "Entrez un numero de page valide.")
            self.page_entry_var.set(str(self.current_page + 1 if self.page_count else 0)) # Restauration de la saisie précédente en cas d'erreur
            return
        if not self.page_count or not (1 <= page_number <= self.page_count): # Validation du numero de page saisi par l'utilisateur
            messagebox.showerror("Erreur", f"Entrez un numero entre 1 et {self.page_count}.") # Affichage d'un message d'erreur si le numero de page est invalide
            self.page_entry_var.set(str(self.current_page + 1 if self.page_count else 0)) # Restauration de la saisie précédente en cas d'erreur
            return
        # Conversion numero utilisateur (1-based) -> index interne (0-based)
        self.go_to_page(page_number - 1)

window = ImageProcessingApp()
window.mainloop()