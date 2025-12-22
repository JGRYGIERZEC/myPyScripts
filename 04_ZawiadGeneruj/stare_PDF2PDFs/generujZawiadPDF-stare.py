import shlex
import io
import os
from collections import defaultdict
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader, PdfWriter

TEMPLATE = "SZABLON.pdf"
DATA_FILE = "DANE.txt"
OUTPUT_DIR = "OUTPUT"

HEADER_POSITIONS = {
    "ID_ZAWIAD": (420, 770),
    "PODMIOT":   (80, 610),
    "ADRES":     (80, 580),
    "OBREB":     (300, 445),
}

TABLE_START_Y = 415
ROW_HEIGHT = 14

COL_X = {
    "DZIALKA": 120,
    "GODZINA": 260,
    "DATA":    350,
}

os.makedirs(OUTPUT_DIR, exist_ok=True)


def parse_line(headers, line):
    values = shlex.split(line)
    return dict(zip(headers, values))


def load_and_group_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]

    # USUWAMY [ ] z nagłówków
    raw_headers = lines[0].split()
    headers = [h.strip("[]") for h in raw_headers]

    groups = defaultdict(list)

    for line in lines[1:]:
        values = shlex.split(line)
        record = dict(zip(headers, values))

        groups[record["ID_ZAWIAD"]].append(record)

    return groups



def create_overlay(records):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica", 10)

    base = records[0]

    # --- nagłówek (raz) ---
    for field, (x, y) in HEADER_POSITIONS.items():
        c.drawString(x, y, base[field])

    # --- tabela działek ---
    y = TABLE_START_Y
    for r in records:
        c.drawString(COL_X["DZIALKA"], y, r["DZIALKA"])
        c.drawString(COL_X["GODZINA"], y, r["GODZINA"])
        c.drawString(COL_X["DATA"],    y, r["DATA"])
        y -= ROW_HEIGHT

    c.save()
    buffer.seek(0)
    return PdfReader(buffer)


def generate_pdf(id_zawiad, records):
    template = PdfReader(TEMPLATE)
    overlay = create_overlay(records)

    writer = PdfWriter()
    page = template.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    output_path = os.path.join(
        OUTPUT_DIR,
        f"ZAWIADOMIENIE_{id_zawiad}.pdf"
    )

    with open(output_path, "wb") as f:
        writer.write(f)


def main():
    groups = load_and_group_data()

    for id_zawiad, records in groups.items():
        generate_pdf(id_zawiad, records)

    print("Zakończono – wygenerowano PDF-y zbiorcze.")


if __name__ == "__main__":
    main()
