import ezdxf
from pathlib import Path
from ezdxf.lldxf.const import DXFStructureError
import re
import shutil

# ---------------- KONFIGURACJA ----------------
CLEAN_SUFFIX = "_clean"
OUTPUT_SUFFIX = "_z_przedrostkiem"
# ----------------------------------------------

def clean_dxf_group_codes(src: Path, dst: Path):
    """
    Naprawia błędne kody grup DXF:
    np. '  9.0' -> '9'
    """
    with src.open("r", encoding="utf-8", errors="ignore") as fin, \
         dst.open("w", encoding="utf-8") as fout:

        lines = fin.readlines()

        for i in range(0, len(lines), 2):
            code = lines[i].strip()

            # jeżeli kod grupy jest floatem (np. 9.0)
            if re.fullmatch(r"-?\d+\.0+", code):
                code = str(int(float(code)))

            fout.write(code + "\n")

            if i + 1 < len(lines):
                fout.write(lines[i + 1])

def process_dxf_files():
    base_dir = Path(__file__).resolve().parent

    for dxf_path in base_dir.glob("*.dxf"):
        if dxf_path.stem.endswith(OUTPUT_SUFFIX):
            continue

        print(f"\nPrzetwarzanie: {dxf_path.name}")

        clean_path = dxf_path.with_name(dxf_path.stem + CLEAN_SUFFIX + ".dxf")
        output_path = dxf_path.with_name(dxf_path.stem + OUTPUT_SUFFIX + ".dxf")

        try:
            # 1️⃣ PRE-CLEAN (naprawa 9.0 → 9)
            clean_dxf_group_codes(dxf_path, clean_path)

            # 2️⃣ Wczytanie CZYSTEGO DXF (bez recover)
            doc = ezdxf.readfile(clean_path)

            auditor = doc.audit()
            if auditor.has_errors:
                print(f"  [!] Wykryto {len(auditor.errors)} drobnych błędów")

            # Wymuszenie DXF 2004
            doc.dxfversion = ezdxf.DXF2004

        except DXFStructureError as e:
            print("  [✗] DXF nadal niepoprawny – plik pominięty")
            print(f"      {e}")
            clean_path.unlink(missing_ok=True)
            continue

        msp = doc.modelspace()
        layer_map = {}

        prefix = dxf_path.stem

        # 3️⃣ Tworzenie warstw z prefiksem
        for layer in list(doc.layers):
            old_name = layer.dxf.name
            new_name = f"{prefix}_{old_name}"

            if new_name not in doc.layers:
                doc.layers.new(
                    name=new_name,
                    dxfattribs=layer.dxfattribs(),
                )

            layer_map[old_name] = new_name

        # 4️⃣ Przepięcie encji
        for entity in msp:
            if entity.dxf.layer in layer_map:
                entity.dxf.layer = layer_map[entity.dxf.layer]

        # 5️⃣ Zapis pliku wynikowego
        doc.saveas(output_path)
        print(f"  ✓ Zapisano: {output_path.name}")

        # 6️⃣ Sprzątanie
        clean_path.unlink(missing_ok=True)

    print("\nZakończono przetwarzanie.")

if __name__ == "__main__":
    process_dxf_files()
