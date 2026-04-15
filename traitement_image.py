from pathlib import Path
import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps
import cv2

# Chargement du PDF.
pdf_path = Path(__file__).with_name("pinax bsb-p46.pdf")
document = pdfium.PdfDocument(str(pdf_path))

# 300 DPI environ (300 / 72) pour une meilleure lecture OCR.
image = document[0].render(scale=4.17).to_pil()
#image.show()

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
    contours, hierarchy = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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

if __name__ == "__main__":

    invert(image).show()
    grayscale(image).show()
    threshold(grayscale(image), 100).show()

    threshold_image = threshold(grayscale(image), 100)

    denoised = noise_removal(np.array(threshold_image), kernel_size_dilatation=2, iterations_dilatation=2, kernel_size_erosion=1, iterations_erosion=1)
    Image.fromarray(denoised).show()

    thick_font_image = thick_font(np.array(threshold_image), kernel_size=2, iterations=1)
    Image.fromarray(thick_font_image).show()
        
    remove_black_borders_image = remove_black_borders(np.array(threshold_image))
    Image.fromarray(remove_black_borders_image).show()