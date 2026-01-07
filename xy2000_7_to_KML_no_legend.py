from pyproj import Transformer
import simplekml

INPUT_FILE = "dane.txt"
OUTPUT_FILE = "punkty.kml"

# Transformacja: Poland 2000 / zone 7 -> WGS84
transformer = Transformer.from_crs(
    "EPSG:2178",
    "EPSG:4326",
    always_xy=True
)

kml = simplekml.Kml()

# =========================
# DEFINICJE STYLÓW
# =========================
styles = {
    # 18–20 lutego 2026
    "2026-02-18": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-02-19": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/pink-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-02-20": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/ltblu-circle.png"
            ),
            scale=1.1
        )
    ),

    # 25–27 lutego 2026
    "2026-02-25": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/blu-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-02-26": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/wht-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-02-27": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png"
            ),
            scale=1.1
        )
    ),

    # 4–6 marca 2026
    "2026-03-04": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-03-05": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/ltgrn-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-03-06": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/grn-stars.png"
            ),
            scale=1.1
        )
    ),

    # 11–13 marca 2026
    "2026-03-11": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/purple-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-03-12": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/purple-stars.png"
            ),
            scale=1.1
        )
    ),
    "2026-03-13": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/purple-square.png"
            ),
            scale=1.1
        )
    ),

    # 18–20 marca 2026
    "2026-03-18": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/orange-circle.png"
            ),
            scale=1.1
        )
    ),
    "2026-03-19": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/orange-stars.png"
            ),
            scale=1.1
        )
    ),
    "2026-03-20": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/orange-square.png"
            ),
            scale=1.1
        )
    ),

    # domyślny
    "default": simplekml.Style(
        iconstyle=simplekml.IconStyle(
            icon=simplekml.Icon(
                href="http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
            ),
            scale=1.0
        )
    )
}

# =========================
# PRZETWARZANIE PLIKU
# =========================
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line_number, line in enumerate(f, start=1):
        line = line.strip()
        if not line:
            continue

        try:
            name, y, x = line.split()
            x = float(x)
            y = float(y)

            # data = pierwszy człon przed '/'
            date_part = name.split("/")[0]

            lon, lat = transformer.transform(x, y)

            point = kml.newpoint(
                name=name,
                coords=[(lon, lat)]
            )

            point.style = styles.get(date_part, styles["default"])

        except ValueError:
            raise ValueError(
                f"Błąd w linii {line_number}: '{line}' "
                "Oczekiwany format: [name] [x] [y]"
            )

# =========================
# ZAPIS KML
# =========================
kml.save(OUTPUT_FILE)
print(f"Plik KML zapisany: {OUTPUT_FILE}")
