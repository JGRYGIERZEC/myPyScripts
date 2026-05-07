import os
import laspy
import pandas as pd
import numpy as np
import ezdxf
from shapely.geometry import Point, Polygon
from tqdm import tqdm
import logging

# Konfiguracja logowania
logging.basicConfig(
    filename='processing_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def fix_columns(df):
    """Usuwa białe znaki i ukryte symbole z nazw kolumn."""
    df.columns = df.columns.str.strip().str.replace('^\\ufeff', '', regex=True)
    return df

def process_point_cloud():
    # Definicja cięć: od 0 do 4m ze skokiem 0.3m
    offsets = [round(x, 1) for x in np.arange(0.0, 4.1, 0.3)]
    buffer_z = 0.05
    # Standardowa paleta kolorów AutoCAD (pętla kolorów dla warstw)
    layer_colors = [1, 2, 3, 4, 5, 6, 40, 80, 120, 160, 200, 240]

    # 1. Wczytanie granic
    csv_file = 'zakresXYH.xlsx - sheet1.csv'
    try:
        df = pd.read_csv(csv_file, sep=None, engine='python')
        df = fix_columns(df)
        if 'Name' not in df.columns:
            df.rename(columns={df.columns[0]: 'Name'}, inplace=True)
    except Exception as e:
        print(f"Błąd krytyczny pliku {csv_file}: {e}")
        return

    # Parsowanie ID i grupowanie
    try:
        df['ID_Granica'] = df['Name'].apply(lambda x: str(x).rsplit('-', 1)[0])
        df['Kolejnosc'] = pd.to_numeric(df['Name'].apply(lambda x: str(x).rsplit('-', 1)[1]))
    except Exception as e:
        logging.error(f"Błąd struktury nazw w kolumnie Name: {e}")
        return

    boundaries = {}
    for gid, group in df.groupby('ID_Granica'):
        sorted_group = group.sort_values('Kolejnosc')
        coords_xyz = sorted_group[['X/E', 'Y/N', 'Z/U']].values
        
        # NOWA LOGIKA: Wysokość bazowa to MINIMUM z obrysu
        base_z_min = coords_xyz[:, 2].min()
        
        boundaries[gid] = {
            'polygon': Polygon(coords_xyz[:, :2]),
            'base_z': base_z_min,
            'coords_xyz': coords_xyz,
            'bbox': [coords_xyz[:,0].min(), coords_xyz[:,0].max(), 
                     coords_xyz[:,1].min(), coords_xyz[:,1].max()]
        }
        logging.info(f"Granica {gid}: Wyznaczona wysokość bazowa (min Z): {base_z_min:.3f} m")

    # 2. Przetwarzanie plików LAS
    las_files = [f for f in os.listdir('.') if f.lower().endswith('.las')]
    
    for las_file in las_files:
        las_name = os.path.splitext(las_file)[0]
        
        try:
            with laspy.open(las_file) as f:
                las = f.read()
            points_all = np.array(las.xyz) 
        except Exception as e:
            logging.error(f"Nie udało się odczytać {las_file}: {e}")
            continue

        for b_id, b_data in tqdm(boundaries.items(), desc=f"Plik: {las_file}"):
            poly = b_data['polygon']
            base_z = b_data['base_z']
            bbox = b_data['bbox']
            
            # Wstępne filtrowanie po Bounding Box
            mask = (points_all[:, 0] >= bbox[0]) & (points_all[:, 0] <= bbox[1]) & \
                   (points_all[:, 1] >= bbox[2]) & (points_all[:, 1] <= bbox[3])
            
            candidates = points_all[mask]
            if len(candidates) == 0: continue

            # Dokładne sprawdzanie poligonu
            inside_mask = [poly.contains(Point(p[0], p[1])) for p in candidates]
            pts_inside = candidates[inside_mask]
            
            if len(pts_inside) == 0: continue

            # Tworzenie dokumentu DXF
            doc = ezdxf.new('R2004')
            msp = doc.modelspace()
            
            # Warstwa granicy
            layer_boundary = f"{las_name}_{b_id}_GRANICA"
            doc.layers.add(name=layer_boundary, color=7)
            pts_3d = b_data['coords_xyz'].tolist()
            if pts_3d[0] != pts_3d[-1]: pts_3d.append(pts_3d[0])
            msp.add_polyline3d(pts_3d, dxfattribs={'layer': layer_boundary})

            # Generowanie cięć co 0.3 m
            for i, offset in enumerate(offsets):
                target_z = base_z + offset
                layer_name = f"{las_name}_{b_id}_{str(offset).replace('.','_')}m"
                
                # Przypisanie koloru z puli
                color_idx = layer_colors[i % len(layer_colors)]
                doc.layers.add(name=layer_name, color=color_idx)
                
                # Wybieranie punktów w buforze
                z_mask = np.abs(pts_inside[:, 2] - target_z) <= buffer_z
                slice_points = pts_inside[z_mask]
                
                for p in slice_points:
                    # Rzutowanie na płaszczyznę dla czystości rysunku
                    msp.add_point((p[0], p[1], target_z), dxfattribs={'layer': layer_name})

            output_dxf = f"{las_name}_{b_id}.dxf"
            doc.saveas(output_dxf)
            logging.info(f"Zapisano plik: {output_dxf} (ID: {b_id}, Z_base: {base_z})")

    print("\nGotowe. Przetworzono wszystkie pliki.")

if __name__ == "__main__":
    process_point_cloud()