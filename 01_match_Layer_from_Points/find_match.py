import math
import sys

LAYER_FILE = "LAYER.txt"
POINT_FILE = "POINT.txt"
RESULT_FILE = "RESULT.txt"

STEP = 0.1
MAX_RADIUS = 1.0


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def read_layer(file_path):
    segments = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) < 4 or not all(is_float(p) for p in parts[:4]):
                continue
            x1, y1, x2, y2 = map(float, parts[:4])
            segments.append((x1, y1, x2, y2))
    return segments


def read_points(file_path):
    points = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) < 3 or not is_float(parts[1]) or not is_float(parts[2]):
                continue
            points.append((parts[0], float(parts[1]), float(parts[2])))
    return points


def distance(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)


def find_matching_point(x, y, points):
    radius = 0.0
    while radius <= MAX_RADIUS:
        best_dist = float("inf")
        best_number = None
        for number, px, py in points:
            d = distance(x, y, px, py)
            if d <= radius and d < best_dist:
                best_dist = d
                best_number = number
        if best_number is not None:
            return best_number, f"{radius:.2f}"
        radius += STEP
    return "BRAK", "-"


def print_progress(current, total):
    percent = (current / total) * 100
    sys.stdout.write(
        f"\rPrzetwarzanie: {percent:6.2f}% ({current} / {total})"
    )
    sys.stdout.flush()


def main():
    segments = read_layer(LAYER_FILE)
    points = read_points(POINT_FILE)

    total = len(segments)

    with open(RESULT_FILE, "w", encoding="utf-8") as out:
        for idx, (x1, y1, x2, y2) in enumerate(segments, start=1):
            num1, rad1 = find_matching_point(x1, y1, points)
            num2, rad2 = find_matching_point(x2, y2, points)

            out.write(
                f"{num1}\t{x1:.2f}\t{y1:.2f}\t{rad1}\t"
                f"{num2}\t{x2:.2f}\t{y2:.2f}\t{rad2}\n"
            )

            print_progress(idx, total)

    print("\nGotowe.")


if __name__ == "__main__":
    main()
