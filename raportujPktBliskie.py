import pandas as pd
import math
from openpyxl import Workbook

# ==============================
# Funkcja obliczania odległości
# ==============================
def distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


# ==============================
# Wczytanie danych
# ==============================
def load_points(filename):
    data = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 3:
                nr = parts[0]
                x = float(parts[1])
                y = float(parts[2])
                data.append((nr, x, y))
    return data


# ==============================
# Główna część programu
# ==============================
def main():

    radius = float(input("Podaj promień wyszukiwania: "))

    points_main = load_points("in.txt")
    points_near = load_points("in2.txt")

    detailed_rows = []
    summary_rows = []

    for nr1, x1, y1 in points_main:
        near_list = []

        for nr2, x2, y2 in points_near:
            dist = distance(x1, y1, x2, y2)
            if dist <= radius:
                near_list.append((nr2, x2, y2, dist))

        # sortowanie od najbliższych
        near_list.sort(key=lambda x: x[3])

        # zapis do raportu szczegółowego
        if near_list:
            for nr2, x2, y2, dist in near_list:
                detailed_rows.append([
                    nr1, x1, y1,
                    nr2, x2, y2,
                    round(dist, 4)
                ])
        else:
            detailed_rows.append([nr1, x1, y1, "-", "-", "-", "-"])

        # zapis do podsumowania
        summary_rows.append([nr1, x1, y1, len(near_list)])

    # ==============================
    # Zapis do XLSX
    # ==============================
    with pd.ExcelWriter("raport.xlsx", engine="openpyxl") as writer:

        df_detailed = pd.DataFrame(
            detailed_rows,
            columns=[
                "Nr_punktu_in",
                "X_in",
                "Y_in",
                "Nr_punktu_in2",
                "X_in2",
                "Y_in2",
                "Odleglosc"
            ]
        )

        df_summary = pd.DataFrame(
            summary_rows,
            columns=[
                "Nr_punktu_in",
                "X_in",
                "Y_in",
                "Liczba_punktow_bliskich"
            ]
        )

        df_detailed.to_excel(writer, sheet_name="Szczegoly", index=False)
        df_summary.to_excel(writer, sheet_name="Podsumowanie", index=False)

    print("Raport zapisany jako raport.xlsx")


if __name__ == "__main__":
    main()