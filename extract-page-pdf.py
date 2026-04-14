from PyPDF2 import PdfReader, PdfWriter

# Extraire une page d'un pdf et la sauvegarder en pdf pour l'OCR.
def extract_page_as_pdf(pdf_path, page_number, output_path):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.add_page(reader.pages[page_number]) # Extraire la page demandée.
    with open(output_path, "wb") as f:
        writer.write(f)

if __name__ == "__main__":
    pdf_input_path = "Caspari Bauhini Viri Clariss. Pinax Theatri Botanici sive Index in Theophrasti Dioscoridis Plinii et botanicorum qui a seculo scripserunt opera.pdf"
    page_to_extract = int(input("Numéro de page à extraire : "))
    pdf_output_path = f"pinax bsb-p{page_to_extract}.pdf"
    extract_page_as_pdf(pdf_input_path, page_to_extract, pdf_output_path)