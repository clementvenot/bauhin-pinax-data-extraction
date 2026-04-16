import tkinter as tk
from tkinter import filedialog, messagebox, Tk, ttk
from PIL import Image, ImageTk
import pypdfium2 as pdfium
from matplotlib import image
from traitement_image import invert, grayscale, threshold, noise_removal, thick_font, thin_font, remove_black_borders, convert_pdf_to_image

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BaseTk = TkinterDnD.Tk
    HAS_DND = True
except ImportError:
    BaseTk = Tk
    HAS_DND = False

class ImageProcessingApp(BaseTk):
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
        self.pdf_path = "" # Chemin du PDF actuellement chargé dans l'application
        
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
        image_container = ttk.Frame(self, borderwidth=2, relief="solid")
        image_container.grid(row=0, column=0,rowspan=2, sticky="nsew")
        image_container.grid_propagate(False) # Empêche de redimensionner en fonction de son contenu
        # Le conteneur pour les boutons d'importation et de modification des fonctionnalités
        import_img_container = ttk.Frame(self, borderwidth=2, relief="solid")
        import_img_container.grid(row=0, column=1, sticky="nsew")
        import_img_container.grid_propagate(False)
        # Le conteneur pour les fonctionnalités de modification de l'image
        features_mod_container = ttk.Frame(self, borderwidth=2, relief="solid")
        features_mod_container.grid(row=1, column=1, sticky="nsew")
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

        # ----------------------------------------------------------------------------
        # ------------- Conteneur pour les boutons d'importation du PDF --------------
        # ----------------------------------------------------------------------------

        # grille pour le conteneur d'importation du PDF
        # Rows
        import_img_container.grid_rowconfigure(0, weight=1)
        import_img_container.grid_rowconfigure(1, weight=1)
        import_img_container.grid_rowconfigure(2, weight=1)
        # Columns
        import_img_container.grid_columnconfigure(0, weight=1)
        import_img_container.grid_columnconfigure(1, weight=1) 

        # Bouton d'importation du PDF
        self.import_pdf_button = ttk.Button(import_img_container, text="Importer un PDF", command=self.open_pdf_dialog)
        self.import_pdf_button.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        # Bouton de suppression du PDF
        self.delete_pdf_button = ttk.Button(import_img_container, text="Supprimer le PDF", command=self.delete_pdf)
        self.delete_pdf_button.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        # Affichage du chemin du PDF actuellement chargé
        self.pdf_path_label = ttk.Label(
            import_img_container,
            text=f"PDF actuel : {self.pdf_path}" if self.pdf_path else "Aucun PDF chargé.",
            justify="left",
            anchor="w",
        )
        self.pdf_path_label.grid(row=0, column=0,columnspan=2, sticky="ew", padx=5, pady=5) 
        self.pdf_path_label.bind("<Configure>", lambda event: self.pdf_path_label.configure(wraplength=max(event.width, 1)))
        # position du label drag and drop 
        self.drag_drop_label = ttk.Label(import_img_container, text="Ou glissez-déposez un PDF ici", anchor="center", border=2, relief="groove")
        self.drag_drop_label.grid(row=1, column=1,rowspan=2, sticky="ewsn", padx=5, pady=5)
        self.drag_drop_label.bind("<Configure>", lambda event: self.drag_drop_label.configure(wraplength=max(event.width, 1)))
        # Configuration du drag and drop si la dependance est disponible, sinon affichage d'un message d'indisponibilité
        if HAS_DND:
            self.drag_drop_label.drop_target_register(DND_FILES)
            self.drag_drop_label.dnd_bind("<<Drop>>", self.drag_and_drop_pdf)
        else:
            self.drag_drop_label.config(text="Glisser-déposer indisponible (installez tkinterdnd2)")
        self.update_pdf_buttons()



    # --------------------------------------------------------------------------------
    # -------------------- Fonctions pour l'importation du PDF -----------------------
    # --------------------------------------------------------------------------------

    def open_pdf_dialog(self):
        # --- Fonction pour ouvrir une boîte de dialogue de sélection de fichier PDF et importer le PDF sélectionné ---
        pdf_path = filedialog.askopenfilename(
            title="Choisir un PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if pdf_path:
            self.import_pdf(pdf_path)

    def import_pdf(self, pdfPath):
        # --- Fonction pour importer un PDF et mettre à jour le chemin du PDF dans l'application -----
        # (recuperer le chemin, le nombre de pages, la page courante, afficher la page, update les boutons de navigation et d'importation, update les labels)
        self.pdf_path = pdfPath
        self.page_count = self.get_pdf_page_count()
        self.current_page = 0
        self.go_to_page(self.current_page)
        self.update_navigation_buttons()
        if self.pdf_path.lower().endswith(".pdf"):
            self.pdf_path_label.config(text=f"PDF actuel : {self.pdf_path}")
        self.update_pdf_buttons()
        self.page_entry_var.set(str(self.current_page + 1 if self.page_count else 0))
        self.page_count_label.config(text=f"/ {self.page_count} page{('s' if self.page_count != 1 else '')}")
    
    def drag_and_drop_pdf(self, event):
        # --- Fonction pour gérer le drag and drop d'un fichier PDF dans l'application ---
        if event.data:
            # Extraction du premier chemin depose (gestion des espaces et multi-fichiers)
            dropped_items = self.tk.splitlist(event.data)
            if not dropped_items:
                return
            pdf_path = dropped_items[0].strip() # Prendre le premier élément et supprimer les espaces superflus
            if pdf_path.startswith("file://"): # Gestion du cas où le chemin commence par "file://"
                pdf_path = pdf_path[7:]
            if not pdf_path.lower().endswith(".pdf"): # Validation de l'extension du fichier déposé
                messagebox.showerror("Erreur", "Le fichier déposé doit être un PDF.")
                return
            self.import_pdf(pdf_path)  # Importation du PDF
    
    def delete_pdf(self):
        # --- Fonction pour supprimer le PDF actuellement chargé dans l'application ---
        # (reset des variables liées au PDF, mise à jour de l'affichage, des boutons et des labels, navigation vers la page 0, update du nombre de pages, update des boutons de navigation, update du label de chemin du PDF, update du label de nombre de pages, reset des labels.)
        self.pdf_path = ""
        self.page_count = 0
        self.current_page = 0
        self.pdf_page = None
        self.image_page = None
        self.imagePDF.configure(image="", text="Aucune page PDF à afficher") 
        self.go_to_page(self.current_page)
        self.pdf_path_label.config(text='Aucun PDF chargé. Cliquez sur "Importer un PDF" pour commencer.')
        self.update_pdf_buttons()
        self.update_navigation_buttons()
        self.page_entry_var.set(str(self.current_page + 1 if self.page_count else 0))
        self.page_count_label.config(text=f"/ {self.page_count} page{('s' if self.page_count != 1 else '')}")

    def update_pdf_buttons(self):
        # --- Active/desactive les boutons lies au PDF selon l'etat de chargement ---
        delete_state = "normal" if self.pdf_path else "disabled"
        self.delete_pdf_button.config(state=delete_state)



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
            self.imagePDF = ttk.Label(image_container, text="Aucune page PDF à afficher", anchor="center") 
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