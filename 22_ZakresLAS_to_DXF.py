import os
import logging
import laspy
import numpy as np
import ezdxf
from shapely.geometry import MultiPoint
from shapely.ops import unary_union
from tqdm import tqdm

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("processing_log.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def process_las_to_dxf(las_path, tolerance=1.0):
    file_name = os.path.splitext(os.path.basename(las_path))[0]
    output_dxf = f"{file_name}.dxf"
    
    try:
        # 1. Wczytywanie pliku LAS
        with laspy.open(las_path) as fh:
            las = fh.read()
            # Pobieramy tylko współrzędne X i Y (zredukowane dla wydajności)
            points = np.vstack((las.x, las.y)).transpose()

        # Opcjonalne: Proste odchudzenie chmury do celów obrysu (co 10-ty punkt), 
        # aby przyspieszyć obliczenia przy gigantycznych zbiorach
        if len(points) > 500000:
            points = points[::100]

# 2. Generowanie geometrii
        multi_point = MultiPoint(points)
        
        try:
            # Próba użycia nowej metody
            boundary = multi_point.concave_hull(ratio=0.1)
        except AttributeError:
            # Fallback dla starszych wersji Shapely:
            # Tworzymy otoczkę wypukłą, ale "nadmuchaną" i "ściągniętą" 
            # (działa gorzej niż concave_hull, ale nie wywala błędu)
            logging.warning("Stara wersja Shapely. Używam convex_hull zamiast concave_hull.")
            boundary = multi_point.convex_hull

        # 3. Generalizacja kształtu (Douglas-Peucker)
        simplified_boundary = boundary.simplify(tolerance, preserve_topology=True)

        # 4. Tworzenie pliku DXF
        doc = ezdxf.new(dxfversion='R2004')
        msp = doc.modelspace()
        
        # Tworzenie warstwy o nazwie pliku
        layer_name = file_name.replace(" ", "_")
        doc.layers.add(name=layer_name, color=7)

        # Wyciąganie współrzędnych z poligonu
        if simplified_boundary.geom_type == 'Polygon':
            coords = list(simplified_boundary.exterior.coords)
            msp.add_lwpolyline(coords, dxfattribs={'layer': layer_name, 'closed': True})
        elif simplified_boundary.geom_type == 'MultiPolygon':
            for poly in simplified_boundary.geoms:
                coords = list(poly.exterior.coords)
                msp.add_lwpolyline(coords, dxfattribs={'layer': layer_name, 'closed': True})

        doc.saveas(output_dxf)
        return True

    except Exception as e:
        logging.error(f"Błąd podczas przetwarzania {file_name}: {str(e)}")
        return False

def main():
    # Pobranie listy plików LAS/LAZ w katalogu skryptu
    directory = os.path.dirname(os.path.abspath(__file__))
    las_files = [f for f in os.listdir(directory) if f.lower().endswith(('.las', '.laz'))]

    if not las_files:
        logging.warning("Nie znaleziono plików LAS/LAZ w katalogu.")
        return

    logging.info(f"Znaleziono {len(las_files)} plików do przetworzenia.")

    # Pasek postępu
    for las_file in tqdm(las_files, desc="Przetwarzanie chmur punktów", unit="plik"):
        full_path = os.path.join(directory, las_file)
        success = process_las_to_dxf(full_path)
        if success:
            logging.info(f"Zakończono sukcesem: {las_file}")

if __name__ == "__main__":
    main()