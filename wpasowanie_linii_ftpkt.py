import numpy as np
from scipy.optimize import minimize
import ezdxf

# --- KONFIGURACJA I WAGI ---
WAGI = {
    'uzt': 1.0,
    'ogr': 1.5,
    'opr': 2.0
}

# Maksymalne dopuszczalne przesunięcie w metrach (zgodnie z życzeniem użytkownika)
LIMIT_PRZESUNIECIA = 2.0 

def wczytaj_dane():
    # 1. Miary bieżące [cite: 1]
    miary = np.loadtxt('linia_miary.txt')
    
    # 2. Hipotetyczna linia pomiarowa [cite: 2]
    lp_coords = np.loadtxt('linia_pomiarowa.txt')
    p1_hip = lp_coords[0, :2]
    p2_hip = lp_coords[1, :2]
    
    # 3. Stan dostosowania 
    linie_ref = []
    with open('stan_dostosowania.txt', 'r') as f:
        for line in f:
            parts = line.split()
            if not parts: continue
            typ = parts[0]
            coords = list(map(float, parts[1:]))
            linie_ref.append({
                'waga': WAGI.get(typ, 1.0),
                'p1': np.array([coords[0], coords[1]]),
                'p2': np.array([coords[2], coords[3]])
            })
    return miary, p1_hip, p2_hip, linie_ref

def get_transformed_points(params, miary, p1_init, p2_init):
    dx, dy, angle = params
    # Macierz rotacji
    c, s = np.cos(angle), np.sin(angle)
    R = np.array([[c, -s], [s, c]])
    
    # Kierunek linii bazowej
    vec_orig = p2_init - p1_init
    length = np.linalg.norm(vec_orig)
    unit_vec = vec_orig / length
    
    # Środek obrotu (początek linii)
    points = []
    for m in miary:
        # Punkt na linii oryginalnej
        p_on_line = p1_init + unit_vec * m
        # Przesunięcie do środka układu (p1_init), obrót, przesunięcie z powrotem + translacja
        p_rot = R @ (p_on_line - p1_init) + p1_init + np.array([dx, dy])
        points.append(p_rot)
    return np.array(points)

def dist_point_to_line(p, l1, l2):
    # Odległość punktu od nieskończonej prostej (przedłużenie)
    return np.abs(np.cross(l2-l1, l1-p)) / np.linalg.norm(l2-l1)

def objective(params, miary, p1_init, p2_init, linie_ref):
    pts = get_transformed_points(params, miary, p1_init, p2_init)
    total_error = 0
    for i, p_akt in enumerate(pts):
        # Znajdujemy najbliższą linię referencyjną dla każdego punktu pomiarowego
        dists = [dist_point_to_line(p_akt, l['p1'], l['p2']) * l['waga'] for l in linie_ref]
        total_error += min(dists)**2
    return total_error

def wykonaj_analize():
    miary, p1_hip, p2_hip, linie_ref = wczytaj_dane()
    
    # Optymalizacja: [dx, dy, obrót_rad]
    initial_guess = [0.0, 0.0, 0.0]
    bounds = [(-LIMIT_PRZESUNIECIA, LIMIT_PRZESUNIECIA), 
              (-LIMIT_PRZESUNIECIA, LIMIT_PRZESUNIECIA), 
              (-0.05, 0.05)] # ok. +/- 3 stopnie
    
    res = minimize(objective, initial_guess, args=(miary, p1_hip, p2_hip, linie_ref), 
                   method='L-BFGS-B', bounds=bounds)
    
    # Wyniki optymalizacji
    final_params = res.x
    pts_final = get_transformed_points(final_params, miary, p1_hip, p2_hip)
    
    # Przeliczenie końcowych współrzędnych końców linii
    p1_final = get_transformed_points(final_params, [0], p1_hip, p2_hip)[0]
    p2_final = get_transformed_points(final_params, [np.linalg.norm(p2_hip-p1_hip)], p1_hip, p2_hip)[0]

    # --- GENEROWANIE RAPORTU ---
    with open('raport.txt', 'w', encoding='utf-8') as f:
        f.write("RAPORT ANALIZY GEOMETRYCZNEJ\n")
        f.write("============================\n\n")
        
        errors = []
        for i, m in enumerate(miary):
            p_final = pts_final[i]
            d_list = [dist_point_to_line(p_final, l['p1'], l['p2']) for l in linie_ref]
            min_err = min(d_list)
            errors.append(min_err)
            f.write(f"Miara bieżąca: {m:8.2f} | Domiar do stanu: {min_err:6.3f} m\n")
            
        f.write("\nSTATYSTYKA:\n")
        f.write(f"Średni błąd wpasowania (m0): {np.sqrt(np.mean(np.square(errors))):.4f} m\n")
        f.write(f"Przesunięcie wypadkowe dX: {final_params[0]:.3f} m, dY: {final_params[1]:.3f} m\n")
        f.write(f"Obrót linii: {np.degrees(final_params[2]):.4f} stopni\n")

    # --- GENEROWANIE DXF ---
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Warstwy
    doc.layers.new('LINIA_POMIAROWA', dxfattribs={'color': 1})
    doc.layers.new('MIARY_PUNKTY', dxfattribs={'color': 3})
    doc.layers.new('OPISY', dxfattribs={'color': 7})

    # Narysowanie linii pomiarowej po dostosowaniu
    msp.add_line(p1_final, p2_final, dxfattribs={'layer': 'LINIA_POMIAROWA'})
    
    for i, m in enumerate(miary):
        p = pts_final[i]
        # Punkt
        msp.add_point(p, dxfattribs={'layer': 'MIARY_PUNKTY'})
        # Tekst (naprawiony błąd ezdxf.constants)
        txt = msp.add_text(f"{m:.2f}", 
                           dxfattribs={'layer': 'OPISY', 'height': 0.15})
        # 'CENTER' zamiast ezdxf.constants.RAST_CENTER
        txt.set_placement(p, align='CENTER')

    doc.saveas("wpasowanie_wynik.dxf")
    print("Sukces! Wygenerowano raport.txt i wpasowanie_wynik.dxf")

if __name__ == "__main__":
    wykonaj_analize()
