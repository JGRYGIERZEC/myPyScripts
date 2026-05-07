import laspy
import ezdxf
import numpy as np
import os
import logging
from glob import glob
from tqdm import tqdm
from shapely.geometry import Polygon, Point

# --- KONFIGURACJA LOGOWANIA ---
logging.basicConfig(
    filename='processing_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

def get_polygons_from_dxf(filename):
    """Pobiera poligony z pliku DXF i zwraca listę obiektów Shapely."""
    try:
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
        polygons = []
        # Obsługa polilinii zamkniętych
        for entity in msp.query('LWPOLYLINE POLYLINE'):
            points = [(p[0], p[1]) for p in entity.points()]
            if len(points) >= 3:
                polygons.append(Polygon(points))
        return polygons
    except Exception as e:
        logging.error(f"Błąd podczas odczytu {filename}: {e}")
        return []

def create_overview_dxf(polygons, start_id, output_name):
    """Tworzy plik przegladowka.dxf z numeracją poligonów."""
    doc = ezdxf.new('R2004')
    msp = doc.modelspace()
    
    for i, poly in enumerate(polygons):
        poly_id = start_id + i
        # Rysowanie obrysu
        coords = list(poly.exterior.coords)
        msp.add_lwpolyline(coords, dxfattribs={'layer': 'ZAKRESY', 'color': 7})
        
        # Dodawanie numeru ID
        centroid = poly.centroid
        msp.add_text(
            str(poly_id), 
            dxfattribs={'height': 2.0, 'layer': 'ID_POLIGONOW', 'color': 2}
        ).set_placement((centroid.x, centroid.y))
        
    doc.saveas(output_name)
    logging.info(f"Utworzono plik przeglądowy: {output_name} (Suma poligonów: {len(polygons)})")

def process_las_files():
    # 1. Inicjalizacja i weryfikacja plików
    las_files = glob("*.las")
    if not las_files:
        print("Błąd: Nie znaleziono plików LAS w bieżącym katalogu.")
        return

    if not os.path.exists("zakres.dxf"):
        print("Błąd: Brak pliku 'zakres.dxf' w katalogu.")
        return

    try:
        user_input = input("Podaj początkowy numer ID dla poligonów (np. 1): ")
        start_id = int(user_input)
    except ValueError:
        print("Błędna wartość. Ustawiam ID początkowe na 1.")
        start_id = 1

    # 2. Wczytanie poligonów i generowanie przeglądówki
    polygons = get_polygons_from_dxf("zakres.dxf")
    if not polygons:
        print("Błąd: Nie znaleziono poprawnych poligonów w zakres.dxf.")
        return
    
    create_overview_dxf(polygons, start_id, "przegladowka.dxf")
    print(f"Wczytano {len(polygons)} poligonów. Rozpoczynam przetwarzanie chmur...")

    # Kolory AutoCAD dla kolejnych cięć (Czerwony, Żółty, Zielony, Błękitny, Niebieski, Magenta)
    aci_colors = [1, 2, 3, 4, 5, 6]

    # 3. Przetwarzanie plików LAS
    for las_path in las_files:
        las_name_clean = os.path.splitext(os.path.basename(las_path))[0]
        
        try:
            # Odczyt pliku LAS (Poprawka: laspy.read bezpośrednio ładuje dane)
            las = laspy.read(las_path)
            l_x = np.array(las.x)
            l_y = np.array(las.y)
            l_z = np.array(las.z)
            
            logging.info(f"Otwarto plik: {las_path} (Liczba punktów: {len(l_x)})")

            for i, poly in enumerate(tqdm(polygons, desc=f"Plik: {las_name_clean}")):
                current_id = start_id + i
                
                # Szybkie filtrowanie po Bounding Boxie poligonu
                minx, miny, maxx, maxy = poly.bounds
                in_bbox = (l_x >= minx) & (l_x <= maxx) & (l_y >= miny) & (l_y <= maxy)
                
                if not np.any(in_bbox):
                    continue

                # Precyzyjne wycięcie punktów wewnątrz poligonu
                # Wybieramy tylko indeksy, które przeszły test bbox
                indices_in_bbox = np.where(in_bbox)[0]
                points_in_poly_mask = []
                for idx in indices_in_bbox:
                    points_in_poly_mask.append(poly.contains(Point(l_x[idx], l_y[idx])))
                
                final_indices = indices_in_bbox[points_in_poly_mask]
                
                if len(final_indices) == 0:
                    continue

                # Parametry wysokościowe dla danego poligonu
                z_subset = l_z[final_indices]
                z_min = np.min(z_subset)
                logging.info(f"Plik: {las_name_clean} | Poligon: {current_id} | Z_min: {z_min:.3f}")

                # Tworzenie wynikowego DXF
                out_doc = ezdxf.new('R2004')
                out_msp = out_doc.modelspace()
                
                # Definiowanie cięć
                offsets = np.arange(0, 4.3, 0.3)  # od 0 do 4m co 0.3m
                buffer = 0.05

                for j, h in enumerate(offsets):
                    target_z = z_min + h
                    layer_name = f"ID{current_id}_H{h:.2f}_{las_name_clean}"
                    color = aci_colors[j % len(aci_colors)]
                    
                    # Filtrowanie punktów w buforze cięcia
                    slice_mask = (z_subset >= target_z - buffer) & (z_subset <= target_z + buffer)
                    slice_indices = final_indices[slice_mask]

                    if len(slice_indices) > 0:
                        # Dodanie warstwy z kolorem
                        if layer_name not in out_doc.layers:
                            out_doc.layers.new(name=layer_name, dxfattribs={'color': color})

                        # Wstawianie punktów rzutowanych na płaszczyznę cięcia
                        for pt_idx in slice_indices:
                            out_msp.add_point(
                                (l_x[pt_idx], l_y[pt_idx], target_z),
                                dxfattribs={'layer': layer_name}
                            )

                # Zapis pliku dla danego poligonu
                output_filename = f"Wynik_{current_id}_{las_name_clean}.dxf"
                out_doc.saveas(output_filename)
                
        except Exception as e:
            logging.error(f"Krytyczny błąd podczas przetwarzania {las_path}: {e}")
            print(f"Błąd przy pliku {las_path}. Szczegóły w logu.")

if __name__ == "__main__":
    print("--- LAS Building Contour Extractor ---")
    process_las_files()
    print("\nGotowe. Wyniki zapisano w bieżącym katalogu.")