import math
import sys
import time

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
    points = []
    with open(filename, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            # pomiń puste linie i komentarze
            if not line or line.startswith("#"):
                continue

            parts = line.split()

            if len(parts) < 3:
                print(f"Ostrzeżenie: pominięto linię {line_no} w {filename}")
                continue

            try:
                number = parts[0]
                x = float(parts[1])
                y = float(parts[2])
                points.append((number, x, y))
            except ValueError:
                print(f"Błąd danych w linii {line_no} w {filename}")

    return points


# ---------- Odległość ----------
def distance(p1, p2):
    dx = p2[1] - p1[1]
    dy = p2[2] - p1[2]
    return dx, dy, math.sqrt(dx*dx + dy*dy)

# ---------- Główna logika ----------
def main():
    radius = float(input("Podaj zakres wyszukiwania (promień): "))

    points1 = load_points("POINTS1.txt")
    points2 = load_points("POINTS2.txt")

    total = len(points1)

    with open("RESULT.txt", "w", encoding="utf-8") as out:
        out.write(
            "number1 x1 y1 number2 x2 y2 delta_x delta_y distance count_in_range\n"
        )

        for i, p1 in enumerate(points1, start=1):
            min_dist = float("inf")
            nearest = None
            count_in_range = 0

            for p2 in points2:
                dx, dy, dist = distance(p1, p2)

                if dist <= radius:
                    count_in_range += 1

                if dist < min_dist:
                    min_dist = dist
                    nearest = (p2, dx, dy, dist)

            if nearest:
                p2, dx, dy, dist = nearest
                out.write(
                    f"{p1[0]} {p1[1]} {p1[2]} "
                    f"{p2[0]} {p2[1]} {p2[2]} "
                    f"{dx:.3f} {dy:.3f} {dist:.3f} {count_in_range}\n"
                )

            loader(i, total)
            time.sleep(0.01)  # tylko dla widocznego loadera

    print("Zakończono. Wynik zapisany w RESULT.txt")

# ---------- Uruchomienie ----------
if __name__ == "__main__":
    main()
