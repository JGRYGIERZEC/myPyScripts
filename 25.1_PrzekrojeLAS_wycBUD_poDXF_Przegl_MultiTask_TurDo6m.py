import laspy
import ezdxf
import numpy as np
import os
import time
from datetime import datetime
from glob import glob
from tqdm import tqdm
from shapely.geometry import Polygon, Point
from shapely.prepared import prep
from concurrent.futures import ProcessPoolExecutor, as_completed
# Dodano import dla wyrównania tekstu
from ezdxf.enums import TextEntityAlignment

# --- KONFIGURACJA LOGOWANIA ---
def write_summary_log(all_results):
    """Tworzy zbiorczy raport chronologiczny."""
    sorted_results = sorted(all_results, key=lambda x: x['timestamp'])
    
    with open("raport_zbiorczy.log", "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"ZBIORCZY RAPORT PRZETWARZANIA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        f.write(f"{'CZAS POWSTANIA':<20} | {'PLIK DXF':<40} | {'Z_MIN':<10}\n")
        f.write("-"*80 + "\n")
        
        for res in sorted_results:
            if res['status'] == 'SUCCESS':
                f.write(f"{res['time_str']:<20} | {res['filename']:<40} | {res['z_min']:<10.3f}\n")
            else:
                f.write(f"{res['time_str']:<20} | BŁĄD: {res['error']}\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write(f"Suma przetworzonych obiektów: {len(sorted_results)}\n")

# --- NOWA FUNKCJA: GENEROWANIE PRZEGLĄDÓWKI ---
def generate_overview_dxf(polygons, start_id, output_name="przegladowka.dxf"):
    """Tworzy plik DXF z poligonami i ich numeracją ID."""
    print(f"Generowanie pliku przeglądowego: {output_name}...")
    doc = ezdxf.new('R2004')
    msp = doc.modelspace()

    for i, poly in enumerate(polygons):
        current_id = start_id + i
        
        # 1. Dodanie poligonu (zewnętrzna granica)
        vertices = list(poly.exterior.coords)
        msp.add_lwpolyline(vertices, dxfattribs={'layer': 'ZAKRESY', 'color': 7})

        # 2. Obliczenie środka poligonu dla etykiety
        centroid = poly.centroid
        
        # 3. Dodanie tekstu ID
        text_id = str(current_id)
        txt_entity = msp.add_text(
            text=text_id,
            dxfattribs={
                'height': 2,
                'color': 2,
                'layer': 'ID_POLIGONOW'
            }
        )
        txt_entity.set_placement(
            (centroid.x, centroid.y), 
            align=TextEntityAlignment.MIDDLE_CENTER
        )

    doc.saveas(output_name)

def worker_process_polygon(poly_data):
    """Przetwarza jeden poligon i zwraca raport."""
    poly, poly_id, las_name_clean, l_x, l_y, l_z = poly_data
    report = {
        'poly_id': poly_id,
        'status': 'EMPTY',
        'timestamp': time.time(),
        'time_str': '',
        'filename': f"Wynik_{poly_id}_{las_name_clean}.dxf",
        'z_min': 0.0,
        'error': ''
    }

    try:
        # 1. Filtrowanie wstępne
        minx, miny, maxx, maxy = poly.bounds
        mask_bbox = (l_x >= minx) & (l_x <= maxx) & (l_y >= miny) & (l_y <= maxy)
        
        if not np.any(mask_bbox):
            return report

        # 2. Precyzyjne wycięcie (Prepared Geometry)
        idx_bbox = np.where(mask_bbox)[0]
        subset_x, subset_y, subset_z = l_x[idx_bbox], l_y[idx_bbox], l_z[idx_bbox]
        
        prepared_poly = prep(poly)
        final_mask = [prepared_poly.contains(Point(x, y)) for x, y in zip(subset_x, subset_y)]
        
        z_final = subset_z[final_mask]
        x_final = subset_x[final_mask]
        y_final = subset_y[final_mask]

        if len(z_final) == 0:
            return report

        z_min = np.min(z_final)
        report['z_min'] = z_min

        # 3. Tworzenie DXF
        out_doc = ezdxf.new('R2004')
        out_msp = out_doc.modelspace()
        aci_colors = [1, 2, 3, 4, 5, 6] # Podstawowe kolory CAD (Czerwony, Żółty, Zielony, Cyjan, Niebieski, Magenta)
        
        # MODYFIKACJA: Zakres od 0 do 6 metrów co 0.3 metra
        offsets = np.arange(0, 6.1, 0.3) 
        buffer = 0.05

        for j, h in enumerate(offsets):
            target_z = z_min + h
            layer_name = f"ID{poly_id}_H{h:.2f}_{las_name_clean}"
            slice_mask = (z_final >= target_z - buffer) & (z_final <= target_z + buffer)
            
            if np.any(slice_mask):
                # Automatyczne przypisanie koloru z palety (j % 6)
                out_doc.layers.new(name=layer_name, dxfattribs={'color': aci_colors[j % 6]})
                pts_x, pts_y = x_final[slice_mask], y_final[slice_mask]
                for px, py in zip(pts_x, pts_y):
                    out_msp.add_point((px, py, target_z), dxfattribs={'layer': layer_name})

        # Zapis i aktualizacja raportu
        out_doc.saveas(report['filename'])
        report['status'] = 'SUCCESS'
        report['timestamp'] = time.time()
        report['time_str'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        report['status'] = 'ERROR'
        report['error'] = str(e)
        report['time_str'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return report

def main():
    # Inicjalizacja
    las_files = glob("*.las")
    if not os.path.exists("zakres.dxf"):
        print("Błąd: Brak pliku zakres.dxf")
        return

    # Wczytanie poligonów
    try:
        doc_in = ezdxf.readfile("zakres.dxf")
    except Exception as e:
        print(f"Błąd podczas wczytywania pliku DXF: {e}")
        return

    polygons = []
    # Zapytanie o polilinie (zarówno LWPOLYLINE jak i starsze POLYLINE)
    for e in doc_in.modelspace().query('LWPOLYLINE POLYLINE'):
        # POPRAWKA: Używamy metody .get_points(), która zwraca iterator z wierzchołkami
        # i jest bezpieczna dla różnych typów polilinii w ezdxf.
        pts = [(p[0], p[1]) for p in e.get_points()]
        if len(pts) >= 3: 
            polygons.append(Polygon(pts))

    try:
        start_id = int(input("Podaj ID początkowe: "))
    except: start_id = 1

    if polygons:
        generate_overview_dxf(polygons, start_id)
    else:
        print("Błąd: Nie znaleziono poprawnych poligonów w pliku zakres.dxf")
        return

    all_process_reports = []

    for las_path in las_files:
        las_name = os.path.splitext(os.path.basename(las_path))[0]
        print(f"\n--- Przetwarzanie: {las_name} ---")
        
        try:
            las = laspy.read(las_path)
            l_x, l_y, l_z = np.array(las.x), np.array(las.y), np.array(las.z)
        except Exception as e:
            print(f"Błąd podczas wczytywania pliku LAS {las_path}: {e}")
            continue

        tasks = []
        for i, poly in enumerate(polygons):
            tasks.append((poly, start_id + i, las_name, l_x, l_y, l_z))

        # Równoległe przetwarzanie
        with ProcessPoolExecutor() as executor:
            futures = [executor.submit(worker_process_polygon, t) for t in tasks]
            
            for future in tqdm(as_completed(futures), total=len(tasks), desc="Budynki"):
                res = future.result()
                if res['status'] != 'EMPTY':
                    all_process_reports.append(res)

    # Generowanie raportu końcowego
    if all_process_reports:
        write_summary_log(all_process_reports)
        print(f"\nProces zakończony. Wygenerowano raport zbiorczy: raport_zbiorczy.log")
    else:
        print("\nNie wygenerowano żadnych plików DXF (brak punktów w zakresach).")

if __name__ == "__main__":
    main()