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
from ezdxf.enums import TextEntityAlignment

# --- KONFIGURACJA LOGOWANIA (z wersji 25.3) ---
def write_summary_log(all_results):
    sorted_results = sorted(all_results, key=lambda x: x['timestamp'])
    with open("raport_zbiorczy.log", "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"ZBIORCZY RAPORT PRZETWARZANIA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        f.write(f"{'CZAS POWSTANIA':<20} | {'PLIK DXF':<40} | {'Z_MIN (CLEAN)':<15}\n")
        f.write("-"*80 + "\n")
        for res in sorted_results:
            if res['status'] == 'SUCCESS':
                f.write(f"{res['time_str']:<20} | {res['filename']:<40} | {res['z_min']:<15.3f}\n")
            else:
                f.write(f"{res['time_str']:<20} | BŁĄD: {res['error']}\n")
        f.write("\n" + "="*80 + "\n")
        f.write(f"Suma przetworzonych obiektów: {len(sorted_results)}\n")

# --- GENEROWANIE PRZEGLĄDÓWKI (z wersji 25.3) ---
def generate_overview_dxf(polygons, start_id, output_name="przegladowka.dxf"):
    doc = ezdxf.new('R2004')
    msp = doc.modelspace()
    for i, poly in enumerate(polygons):
        current_id = start_id + i
        vertices = list(poly.exterior.coords)
        msp.add_lwpolyline(vertices, dxfattribs={'layer': 'ZAKRESY', 'color': 7})
        
        # ID wewnątrz poligonu
        label_pt = poly.representative_point()
        txt_entity = msp.add_text(str(current_id), dxfattribs={'height': 1.5, 'color': 2, 'layer': 'ID_POLIGONOW'})
        txt_entity.set_placement((label_pt.x, label_pt.y), align=TextEntityAlignment.MIDDLE_CENTER)
    
    doc.saveas(output_name)
    print(f"Utworzono plik przeglądowy: {output_name}")

# --- PROCESOR ROBOCZY (Noise Reduct + 6m Range z wersji 25.3) ---
def worker_process_polygon(poly_data):
    poly, poly_id, las_name_clean, l_x, l_y, l_z = poly_data
    report = {
        'poly_id': poly_id, 'status': 'EMPTY', 'timestamp': time.time(),
        'time_str': '', 'filename': f"Wynik_{poly_id}_{las_name_clean}.dxf",
        'z_min': 0.0, 'error': ''
    }

    try:
        minx, miny, maxx, maxy = poly.bounds
        mask_bbox = (l_x >= minx) & (l_x <= maxx) & (l_y >= miny) & (l_y <= maxy)
        if not np.any(mask_bbox): return report

        idx_bbox = np.where(mask_bbox)[0]
        subset_x, subset_y, subset_z = l_x[idx_bbox], l_y[idx_bbox], l_z[idx_bbox]
        
        prepared_poly = prep(poly)
        final_mask = [prepared_poly.contains(Point(x, y)) for x, y in zip(subset_x, subset_y)]
        
        x_raw, y_raw, z_raw = subset_x[final_mask], subset_y[final_mask], subset_z[final_mask]
        if len(z_raw) < 10: return report 

        # Redukcja szumów (z wersji 25.3)
        z_mean = np.mean(z_raw)
        z_std = np.std(z_raw)
        z_low, z_high = np.percentile(z_raw, [0.5, 99.5])
        noise_mask = (np.abs(z_raw - z_mean) <= 3 * z_std) & (z_raw >= z_low) & (z_raw <= z_high)
        
        x_clean, y_clean, z_clean = x_raw[noise_mask], y_raw[noise_mask], z_raw[noise_mask]
        if len(z_clean) == 0: return report
        
        z_min_clean = np.min(z_clean)
        report['z_min'] = z_min_clean

        out_doc = ezdxf.new('R2004')
        out_msp = out_doc.modelspace()
        
        # Zakres cięcia do 6 metrów (z wersji 25.3)
        offsets = np.arange(0, 6.1, 0.3) 
        buffer = 0.05
        points_added = 0

        for j, h in enumerate(offsets):
            target_z = z_min_clean + h
            layer_name = f"ID{poly_id}_H{h:.2f}"
            slice_mask = (z_clean >= target_z - buffer) & (z_clean <= target_z + buffer)
            
            if np.any(slice_mask):
                out_doc.layers.new(name=layer_name, dxfattribs={'color': (j % 6) + 1})
                pts_x, pts_y = x_clean[slice_mask], y_clean[slice_mask]
                for px, py in zip(pts_x, pts_y):
                    out_msp.add_point((px, py, target_z), dxfattribs={'layer': layer_name})
                points_added += len(pts_x)

        if points_added == 0: return report
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
    las_files = glob("*.las")
    if not os.path.exists("zakres.dxf"):
        print("Błąd: Brak pliku zakres.dxf"); return

    try:
        doc_in = ezdxf.readfile("zakres.dxf")
        msp_in = doc_in.modelspace()
    except Exception as e:
        print(f"Błąd odczytu DXF: {e}"); return

    polygons = []
    # --- PRZYWRÓCONA LOGIKA Z PLIKU 25_Turbo ---
    # Ta metoda poprawnie odczytuje wierzchołki z Twojego pliku DXF R12
    for e in msp_in.query('LWPOLYLINE POLYLINE'):
        try:
            # Użycie e.points() zgodnie z rozwiązaniem Turbo
            pts = [(p[0], p[1]) for p in e.points()]
            if len(pts) >= 3:
                polygons.append(Polygon(pts))
        except Exception:
            continue

    if not polygons:
        print("Błąd: Nie znaleziono poprawnych obiektów geometrycznych w pliku zakres.dxf.")
        return

    try:
        start_id = int(input("Podaj ID początkowe dla numeracji: "))
    except ValueError:
        start_id = 1

    # Wygenerowanie przeglądówki przed procesem LAS
    generate_overview_dxf(polygons, start_id)

    all_process_reports = []
    for las_path in las_files:
        las_name = os.path.splitext(os.path.basename(las_path))[0]
        print(f"\n--- Przetwarzanie LAS: {las_name} (Noise Reduct + Range 6m) ---")
        try:
            las = laspy.read(las_path)
            l_x, l_y, l_z = np.array(las.x), np.array(las.y), np.array(las.z)
        except Exception as e:
            print(f"Błąd pliku {las_path}: {e}"); continue

        tasks = [(p, start_id + i, las_name, l_x, l_y, l_z) for i, p in enumerate(polygons)]

        with ProcessPoolExecutor() as executor:
            futures = [executor.submit(worker_process_polygon, t) for t in tasks]
            for future in tqdm(as_completed(futures), total=len(tasks), desc="Analiza budynków"):
                res = future.result()
                if res['status'] != 'EMPTY': 
                    all_process_reports.append(res)

    if all_process_reports:
        write_summary_log(all_process_reports)
        print(f"\nProces zakończony. Sprawdź plik: raport_zbiorczy.log")

if __name__ == "__main__":
    main()