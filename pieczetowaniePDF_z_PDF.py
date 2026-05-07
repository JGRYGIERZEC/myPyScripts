import fitz

sample_pdf = "sample.pdf"
input_pdf = "wejscie.pdf"
output_pdf = "wynik.pdf"

TARGET_DPI = 300
scale = TARGET_DPI / 72
matrix = fitz.Matrix(scale, scale)

sample = fitz.open(sample_pdf)

graphics = []
annotations = []

# ---------------------------------
# pobranie komentarzy z sample.pdf
# ---------------------------------
for page in sample:

    annot = page.first_annot

    while annot:

        rect = annot.rect
        typ = annot.type[1]

        if typ in ["Stamp", "FreeText"]:

            # renderowanie w wysokiej rozdzielczości
            pix = annot.get_pixmap(matrix=matrix)

            graphics.append({
                "rect": rect,
                "pix": pix
            })

        else:

            annotations.append({
                "type": typ,
                "rect": rect,
                "content": annot.info.get("content", ""),
                "title": annot.info.get("title", ""),
                "opacity": annot.opacity
            })

        annot = annot.next

sample.close()

# ---------------------------------
# wstawienie do wejscie.pdf
# ---------------------------------
doc = fitz.open(input_pdf)

for page in doc:

    # grafiki (Stamp + FreeText)
    for g in graphics:

        page.insert_image(
            g["rect"],
            pixmap=g["pix"],
            overlay=True,
            keep_proportion=True
        )

    # inne komentarze
    for a in annotations:

        if a["type"] == "Text":

            annot = page.add_text_annot(
                a["rect"].tl,
                a["content"]
            )

        elif a["type"] == "Square":

            annot = page.add_rect_annot(a["rect"])

        elif a["type"] == "Highlight":

            annot = page.add_highlight_annot(a["rect"])

        else:
            continue

        annot.set_info(
            title=a["title"],
            content=a["content"]
        )

        if a["opacity"]:
            annot.set_opacity(a["opacity"])

        annot.update()

doc.save(output_pdf)
doc.close()

print("Gotowe:", output_pdf)
