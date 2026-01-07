import fitz  # PyMuPDF
from tqdm import tqdm
from pathlib import Path


def remove_empty_pages(input_pdf: str, output_pdf: str):
    doc = fitz.open(input_pdf)
    pages_to_remove = []

    total_pages = len(doc)

    for page_number in tqdm(
        range(total_pages),
        desc="Analiza stron",
        unit="strona"
    ):
        page = doc[page_number]
        if not page.get_text().strip():
            pages_to_remove.append(page_number)

    # Usuwanie od końca, aby nie zmieniać indeksów
    for page_number in reversed(pages_to_remove):
        doc.delete_page(page_number)

    doc.save(output_pdf)
    doc.close()

    print(f"Usunięto {len(pages_to_remove)} pustych stron.")
    print(f"Zapisano plik: {output_pdf}")


if __name__ == "__main__":
    input_pdf = "wejscie.pdf"
    output_pdf = "wyjscie_bez_pustych_stron.pdf"

    remove_empty_pages(input_pdf, output_pdf)
