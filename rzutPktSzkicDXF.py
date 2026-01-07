import ezdxf
import math
import csv


# ======================================================
# PARAMETRY SKALI I WYGLĄDU
# ======================================================

TEXT_H = 1.8
TEXT_H_SMALL = 1.4
OFFSET_PIKIET = 3.0
OFFSET_POINT_NR = 2.0
ARROW_SIZE = 1.2
POINT_RADIUS = 0.35


# ======================================================
# FUNKCJE POMOCNICZE
# ======================================================

def read_points_with_id(path):
    pts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            pid, x, y = line.split()
            pts.append((pid, float(x), float(y)))
    return pts


def dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def angle(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def project_point_on_segment(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = p[0] - a[0], p[1] - a[1]
    c1 = vx * wx + vy * wy
    c2 = vx * vx + vy * vy
    t = max(0.0, min(1.0, c1 / c2))
    return (a[0] + t * vx, a[1] + t * vy), t


def left_right(a, b, p):
    cross = (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])
    return "L" if cross > 0 else "P"


def arrow(msp, base, tip, size):
    ang = math.atan2(tip[1] - base[1], tip[0] - base[0])
    for s in (-1, 1):
        a = ang + s * math.radians(150)
        msp.add_line(
            tip,
            (tip[0] + size * math.cos(a), tip[1] + size * math.sin(a)),
            dxfattribs={"layer": "DOMIARY"},
        )


# ======================================================
# WCZYTANIE DANYCH
# ======================================================

base_pts_raw = read_points_with_id("LINE_IN.txt")
point_pts_raw = read_points_with_id("POINT_IN.txt")

base_pts = [(x, y) for _, x, y in base_pts_raw]

# Pikietaż narastająco po osi
pikiety = [0.0]
for i in range(1, len(base_pts)):
    pikiety.append(pikiety[-1] + dist(base_pts[i - 1], base_pts[i]))


# ======================================================
# DXF – AutoCAD 2004
# ======================================================

doc = ezdxf.new("R2004")
msp = doc.modelspace()

layers = {
    "BAZA": 1,
    "DOMIARY": 3,
    "OPISY": 7,
    "PUNKTY": 5,
}

for name, color in layers.items():
    doc.layers.new(name=name, dxfattribs={"color": color})

# Linia bazowa
msp.add_lwpolyline(base_pts, dxfattribs={"layer": "BAZA"})


# ======================================================
# OPIS DŁUGOŚCI SEGMENTÓW OSI
# ======================================================

for i in range(len(base_pts) - 1):
    A = base_pts[i]
    B = base_pts[i + 1]
    mid = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
    seg_len = dist(A, B)
    ang = angle(A, B)

    msp.add_text(
        f"{seg_len:.2f}",
        dxfattribs={
            "height": TEXT_H_SMALL,
            "rotation": ang,
            "layer": "OPISY",
        },
    ).set_placement(
        mid,
        align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
    )


# ======================================================
# NUMERY PUNKTÓW LINII BAZOWEJ
# ======================================================

for pid, x, y in base_pts_raw:
    msp.add_circle((x, y), POINT_RADIUS, dxfattribs={"layer": "PUNKTY"})
    msp.add_text(
        pid,
        dxfattribs={"height": TEXT_H_SMALL, "layer": "OPISY"},
    ).set_placement(
        (x, y + OFFSET_POINT_NR),
        align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
    )


# ======================================================
# RZUTOWANIE PUNKTÓW + ZBIERANIE DOMIARÓW
# ======================================================

domiary_csv = []

for pid, px, py in point_pts_raw:

    best = None

    for i in range(len(base_pts) - 1):
        proj, t = project_point_on_segment((px, py), base_pts[i], base_pts[i + 1])
        d = dist((px, py), proj)
        if best is None or d < best[0]:
            best = (d, proj, i, t)

    domiar, Pp, idx, t = best
    A = base_pts[idx]
    B = base_pts[idx + 1]

    pik = pikiety[idx] + t * dist(A, B)
    side = left_right(A, B, (px, py))

    # Linia domiaru + strzałki
    msp.add_line((px, py), Pp, dxfattribs={"layer": "DOMIARY"})
    arrow(msp, Pp, (px, py), ARROW_SIZE)

    # Punkt rzutu
    msp.add_circle(Pp, POINT_RADIUS, dxfattribs={"layer": "PUNKTY"})

    # Numer punktu terenowego
    msp.add_text(
        pid,
        dxfattribs={"height": TEXT_H_SMALL, "layer": "OPISY"},
    ).set_placement(
        (px, py + OFFSET_POINT_NR),
        align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
    )

    # Opis domiaru
    ang_d = angle(Pp, (px, py))
    msp.add_text(
        f"{domiar:.2f} {side}",
        dxfattribs={
            "height": TEXT_H,
            "rotation": ang_d,
            "layer": "OPISY",
        },
    ).set_placement(
        ((Pp[0] + px) / 2, (Pp[1] + py) / 2),
        align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
    )

    # Opis pikietażu
    ang_b = angle(A, B)
    nx = -math.sin(math.radians(ang_b))
    ny = math.cos(math.radians(ang_b))

    msp.add_text(
        f"{pik:.2f}",
        dxfattribs={
            "height": TEXT_H,
            "rotation": ang_b,
            "layer": "OPISY",
        },
    ).set_placement(
        (Pp[0] + nx * OFFSET_PIKIET, Pp[1] + ny * OFFSET_PIKIET),
        align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
    )

    # Dane do CSV
    domiary_csv.append({
        "NR_PUNKTU": pid,
        "PIKIETAZ": pik,
        "DOMIAR": domiar,
        "STRONA": side,
        "ODCINEK_OD": base_pts_raw[idx][0],
        "ODCINEK_DO": base_pts_raw[idx + 1][0],
        "X_PUNKTU": px,
        "Y_PUNKTU": py,
        "X_RZUTU": Pp[0],
        "Y_RZUTU": Pp[1],
    })


# ======================================================
# ZAPIS PLIKÓW
# ======================================================

doc.saveas("SZKIC_POLOWY_2004.dxf")

with open("DOMIARY.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow([
        "NR_PUNKTU",
        "PIKIETAZ",
        "DOMIAR",
        "STRONA",
        "ODCINEK_OD",
        "ODCINEK_DO",
        "X_PUNKTU",
        "Y_PUNKTU",
        "X_RZUTU",
        "Y_RZUTU",
    ])

    for d in domiary_csv:
        writer.writerow([
            d["NR_PUNKTU"],
            f"{d['PIKIETAZ']:.2f}",
            f"{d['DOMIAR']:.2f}",
            d["STRONA"],
            d["ODCINEK_OD"],
            d["ODCINEK_DO"],
            f"{d['X_PUNKTU']:.3f}",
            f"{d['Y_PUNKTU']:.3f}",
            f"{d['X_RZUTU']:.3f}",
            f"{d['Y_RZUTU']:.3f}",
        ])
