import ezdxf
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import unary_union, snap, polygonize

def analyze_topology_with_reports(input_file, output_dxf, report_file, tolerance=0.01):
    try:
        doc = ezdxf.readfile(input_file)
        msp = doc.modelspace()
    except Exception as e:
        print(f"Błąd pliku: {e}")
        return

    # --- Faza 1: Pobieranie geometrii i tekstów ---
    raw_segments = []
    texts = []
    
    for entity in msp:
        # Linie i polilinie
        if entity.dxftype() in ('LINE', 'LWPOLYLINE', 'POLYLINE'):
            if entity.dxftype() == 'LINE':
                raw_segments.append(LineString([entity.dxf.start, entity.dxf.end]))
            else:
                p = list(entity.get_points())
                for i in range(len(p) - 1):
                    raw_segments.append(LineString([p[i], p[i+1]]))
        
        # Teksty (TEXT i MTEXT)
        elif entity.dxftype() in ('TEXT', 'MTEXT'):
            insert_pt = entity.dxf.insert
            texts.append({'point': Point(insert_pt), 'content': entity.dxf.text})

    # --- Faza 2 & 3: Snapowanie i Przecinanie (Noding) ---
    combined = MultiLineString(raw_segments)
    snapped = snap(combined, combined, tolerance)
    noded = unary_union(snapped)

    # --- Faza 4: Usuwanie linii wiszących (Dangles) ---
    # Budujemy graf, by usunąć segmenty o stopniu węzła 1
    if isinstance(noded, MultiLineString):
        lines = list(noded.geoms)
    else:
        lines = [noded]

    endpoint_counts = {}
    for line in lines:
        for pt in [line.coords[0], line.coords[-1]]:
            p_idx = (round(pt[0], 4), round(pt[1], 4))
            endpoint_counts[p_idx] = endpoint_counts.get(p_idx, 0) + 1

    clean_lines = [
        l for l in lines 
        if endpoint_counts.get((round(l.coords[0][0], 4), round(l.coords[0][1], 4)), 0) > 1
        and endpoint_counts.get((round(l.coords[-1][0], 4), round(l.coords[-1][1], 4)), 0) > 1
    ]

    # --- Faza 5: Budowanie obszarów i kontrola tekstów ---
    polygons = list(polygonize(clean_lines))
    
    report_data = []
    new_doc = ezdxf.new(dxfversion='R2004')
    new_msp = new_doc.modelspace()

    # Zapisz linie do DXF
    for l in clean_lines:
        new_msp.add_line(l.coords[0], l.coords[-1])

    # Analiza obszarów
    for i, poly in enumerate(polygons):
        # Znajdź teksty wewnątrz tego poligonu
        contained_texts = [t['content'] for t in texts if poly.contains(t['point'])]
        
        count = len(contained_texts)
        centroid = poly.centroid
        
        if count == 0:
            report_data.append(f"Obszar {i} (Centroid: {centroid.x:.2f}, {centroid.y:.2f}): BRAK tekstu.")
        elif count > 1:
            report_data.append(f"Obszar {i} (Centroid: {centroid.x:.2f}, {centroid.y:.2f}): NADMIAR tekstów ({count}): {contained_texts}")

    # Zapis raportu
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"RAPORT TOPOLOGII OBSZARÓW\n")
        f.write(f"Liczba wykrytych obszarów zamkniętych: {len(polygons)}\n")
        f.write("-" * 50 + "\n")
        if not report_data:
            f.write("Wszystkie obszary posiadają poprawnie dokładnie jeden tekst.\n")
        else:
            f.writelines("\n".join(report_data))

    new_doc.saveas(output_dxf)
    print(f"Gotowe! Wykryto {len(polygons)} obszarów. Raport zapisano w: {report_file}")

# Uruchomienie
analyze_topology_with_reports('wejscie.dxf', 'topologia_final.dxf', 'raport.txt', tolerance=0.01)
