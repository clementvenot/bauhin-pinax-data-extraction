from pathlib import Path
import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps
import cv2
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter

def invert(image):
    # Inversion des couleurs de l'image
    return ImageOps.invert(image.convert("RGB"))

def grayscale(image):
    # Conversion de l'image en niveaux de gris
    return image.convert("L")

def threshold(image, threshold):
    # Application d'un seuillage pour binariser l'image
    return image.point(lambda px: 255 if px > threshold else 0)

def noise_removal(image,kernel_size_dilatation=1, iterations_dilatation=1, kernel_size_erosion=1, iterations_erosion=1):
    # Suppression du bruit en utilisant des opérations morphologiques
    kernal = np.ones((kernel_size_dilatation, kernel_size_dilatation), np.uint8)
    image = cv2.dilate(image, kernal, iterations=iterations_dilatation)
    kernal = np.ones((kernel_size_erosion, kernel_size_erosion), np.uint8)
    image = cv2.erode(image, kernal, iterations=iterations_erosion)
    return image

def thick_font(image, kernel_size=1, iterations=1):
    # Épaississement des caractères pour améliorer la reconnaissance OCR
    image = cv2.bitwise_not(image)  # Inversion des couleurs 
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    image = cv2.dilate(image, kernel, iterations=iterations)  # Épaississement des caractères
    image = cv2.bitwise_not(image)  # Réinversion 
    return image

def thin_font(image, kernel_size=1, iterations=1):
    # Affinement des caractères pour améliorer la reconnaissance OCR
    image = cv2.bitwise_not(image)  # Inversion des couleurs 
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    image = cv2.erode(image, kernel, iterations=iterations)  # Affinement
    image = cv2.bitwise_not(image)  # Réinversion 
    return image

def remove_black_borders(image):
    # Suppression des bordures noires en trouvant les contours et en recadrant l'image
    # Conversion en niveaux de gris si necessaire (cv2.findContours ne supporte que CV_8UC1)
    if len(image.shape) == 3: # Si l'image a 3 canaux (BGR), la convertir en niveaux de gris
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        image_gray = image
    contours, hierarchy = cv2.findContours(image_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image  # Retourner l'image originale si aucun contour trouvé
    cntsSorted = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)
    cnt = cntsSorted[0] 
    x, y, w, h = cv2.boundingRect(cnt) 
    crop = image[y:y+h, x:x+w] # Recadrage de l'image pour supprimer les bordures noires
    return crop

def convert_pdf_to_image(pdf_path, page_number=0, scale=4.17):
    # Fonction pour convertir une page PDF en image PIL
    document = pdfium.PdfDocument(str(pdf_path))
    image = document[page_number].render(scale=scale).to_pil()
    return image

def merge_images_to_pdf(image_list, output_path=None, assembly_progress_callback=None):
    # Fonction pour assembler une liste d'images PIL en un seul PDF.
    # Retourne les bytes du PDF si output_path est None, sinon ecrit sur disque.
    if not image_list:
        return None

    writer = PdfWriter()
    total_images = len(image_list)

    # Convertir chaque image en PDF et l'ajouter au writer
    for index, img in enumerate(image_list, start=1):
        if img.mode != "RGB":
            img = img.convert("RGB")
        page_buffer = BytesIO()
        img.save(page_buffer, "PDF", quality=95)
        page_buffer.seek(0) 
        reader = PdfReader(page_buffer)
        writer.add_page(reader.pages[0])

        # Mettre à jour la progression de l'assemblage
        if assembly_progress_callback:
            assembly_progress_callback(index, total_images)
    
    # Sauvegarder sur disque si un chemin de sortie est fourni
    if output_path:
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        return output_path

    # Sauvegarder en mémoire dans un BytesIO
    pdf_buffer = BytesIO()
    writer.write(pdf_buffer)
    pdf_buffer.seek(0)  # Retourner au début du buffer
    return pdf_buffer.getvalue()  # Retourner les bytes

def pipeline(pdfPath, bw_bool, threshold_bool, threshold_value=None, noise_removal_bool=False, thick_font_bool=False, thin_font_bool=False, remove_black_borders_bool=False, kernel_size_dilatation=1, iterations_dilatation=1, kernel_size_erosion=1, iterations_erosion=1, kernel_size_thick_font=1, iterations_thick_font=1, kernel_size_thin_font=1, iterations_thin_font=1, progress_callback=None, treshhold_value=None, status_callback=None, output_path=None, assembly_progress_callback=None):
    # Traiter toutes les pages et assembler le PDF en mémoire
    if threshold_value is None:
        # Compatibilite avec l'ancien nom de parametre mal orthographie.
        threshold_value = treshhold_value

    nbpages = len(pdfium.PdfDocument(str(pdfPath)))
    images_list = []  # Garder les images en mémoire

    # Traiter chaque page du PDF
    for page in range(nbpages):
        image = convert_pdf_to_image(pdfPath, page_number=page)
        if bw_bool:
            image = grayscale(image)
        if threshold_bool:
            image = threshold(image, threshold_value)
        if noise_removal_bool:
            image = noise_removal(np.array(image), kernel_size_dilatation, iterations_dilatation, kernel_size_erosion, iterations_erosion)
            image = Image.fromarray(image)
        if thick_font_bool:
            image = thick_font(np.array(image), kernel_size_thick_font, iterations_thick_font)
            image = Image.fromarray(image)
        if thin_font_bool:
            image = thin_font(np.array(image), kernel_size_thin_font, iterations_thin_font)
            image = Image.fromarray(image)
        if remove_black_borders_bool:
            image = remove_black_borders(np.array(image))
            image = Image.fromarray(image)
        
        # Ajouter l'image traitée à la liste (en mémoire)
        images_list.append(image)

        # Mettre à jour la progression du traitement des pages
        if progress_callback:
            progress_callback(page + 1, nbpages)

    # Mettre à jour le statut avant l'assemblage du PDF
    if status_callback:
        status_callback("assembly")
    
    # Assembler toutes les images en un seul PDF 
    if images_list:
        # Mettre à jour le statut avant la sauvegarde du PDF
        if status_callback:
            status_callback("saving")
        # Assembler les images en PDF et retourner les bytes ou sauvegarder sur disque
        return merge_images_to_pdf(
            images_list,
            output_path=output_path,
            assembly_progress_callback=assembly_progress_callback,
        )
    return None

if __name__ == "__main__":

    """
    invert(image).show()
    grayscale(image).show()
    threshold(grayscale(image), 100).show()

    threshold_image = threshold(grayscale(image), 100)

    denoised = noise_removal(np.array(threshold_image), kernel_size_dilatation=2, iterations_dilatation=2, kernel_size_erosion=1, iterations_erosion=1)
    Image.fromarray(denoised).show()

    thick_font_image = thick_font(np.array(threshold_image), kernel_size=2, iterations=1)
    Image.fromarray(thick_font_image).show()
        
    remove_black_borders_image = remove_black_borders(np.array(threshold_image))
    Image.fromarray(remove_black_borders_image).show()"""

    # Chargement du PDF.
    pdf_path = Path("/Users/clementvenot/git/bauhin-pinax-data-extraction/Caspari Bauhini Viri Clariss. Pinax Theatri Botanici sive Index in Theophrasti Dioscoridis Plinii et botanicorum qui a seculo scripserunt opera.pdf")
    if pdf_path.exists():
        document = pdfium.PdfDocument(str(pdf_path))
        # 300 DPI environ (300 / 72) pour une meilleure lecture OCR.
        image = document[0].render(scale=4.17).to_pil()
    else:
        image = None

    # Exemple d'utilisation de la pipeline
    pdf_bytes = pipeline(pdf_path, bw_bool=True, threshold_bool=True, threshold_value=180, noise_removal_bool=True, thick_font_bool=False, thin_font_bool=False, remove_black_borders_bool=True, kernel_size_dilatation=2, iterations_dilatation=2, kernel_size_erosion=1, iterations_erosion=1)
    
    # Sauvegarder le PDF traité sur disque
    if pdf_bytes:
        with open("render.pdf", "wb") as f:
            f.write(pdf_bytes)