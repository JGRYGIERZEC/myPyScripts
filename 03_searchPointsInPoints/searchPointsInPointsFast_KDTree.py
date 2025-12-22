import math
import sys
import time
from scipy.spatial import cKDTree

# ---------- Loader ----------
def loader(current, total, bar_length=30):
    percent = current / total
    filled = int(bar_length * percent)
    bar = "#" * filled + "-" * (bar_length - filled)
    sys.stdout.write(f"\rPrzetwarzanie: [{bar}] {int(percent*100)}%")
    sys.stdout.flush()
    if current == total:
        print()

# ---------- Wczytywanie punktów ----------
def load_points(filename):
    numbers = []
    coords = []

    with open(filename, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            try:
                numbers.append(parts[0])
                coords.append((float(parts[1]), float(parts[2])))
            except ValueError:
                print(f"Błąd danych w linii {line_no} w {filename}")

    return numbers, coords

# ---------- MAIN ----------
def main():
    radius = float(input("Podaj zakres wyszukiwania (promień): "))

    nums1, coords1 = load_points("POINTS1.txt")
    nums2, coords2 = load_points("POINTS2.txt")

    # budowa KDTree (POINTS2)
    tree = cKDTree(coords2)

    total = len(coords1)

    with open("RESULT.txt", "w", encoding="utf-8") as out:
        out.write(
            "number1 x1 y1 number2 x2 y2 delta_x delta_y distance count_in_range\n"
        )

        for i, (n1, (x1, y1)) in enumerate(zip(nums1, coords1), start=1):

            # najbliższy punkt
            dist, idx = tree.query((x1, y1), k=1)

            x2, y2 = coords2[idx]
            n2 = nums2[idx]

            dx = x2 - x1
            dy = y2 - y1

            # ilość punktów w zakresie
            count_in_range = len(tree.query_ball_point((x1, y1), radius))

            out.write(
                f"{n1} {x1} {y1} "
                f"{n2} {x2} {y2} "
                f"{dx:.3f} {dy:.3f} {dist:.3f} {count_in_range}\n"
            )

            loader(i, total)

    print("Zakończono. Wynik zapisany w RESULT.txt")

# ---------- RUN ----------
if __name__ == "__main__":
    main()
