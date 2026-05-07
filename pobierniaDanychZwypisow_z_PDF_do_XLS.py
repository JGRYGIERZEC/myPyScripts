import pdfplumber
import pandas as pd
import os

def extract_table_data(pdf_path):
    extracted_entries = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                
                # Szukamy indeksu kolumny "Podmiot"
                header = [str(cell).replace('\n', ' ') if cell else "" for cell in table[0]]
                try:
                    podmiot_idx = next(i for i, name in enumerate(header) if "Podmiot" in name)
                except StopIteration:
                    continue # Jeśli w tej tabeli nie ma kolumny Podmiot, idź dalej

                for row_idx in range(len(table)):
                    cell_content = str(table[row_idx][podmiot_idx]) if table[row_idx][podmiot_idx] else ""
                    
                    if "Adres:" in cell_content:
                        # 1. Pobieramy komórkę NAD (Pełny Podmiot)
                        podmiot_val = ""
                        if row_idx > 0:
                            podmiot_val = str(table[row_idx - 1][podmiot_idx]) if table[row_idx - 1][podmiot_idx] else ""
                        
                        # 2. Pobieramy komórkę Z ADRESEM (oraz ewentualne linie pod nią)
                        adres_val = cell_content
                        
                        # Sprawdzamy, czy wiersze poniżej to kontynuacja adresu (puste inne kolumny)
                        next_row = row_idx + 1
                        while next_row < len(table):
                            # Jeśli inne komórki w tym wierszu są puste, a kolumna podmiotu ma tekst -> to kontynuacja
                            other_cols_empty = all(not table[next_row][c] for c in range(len(table[next_row])) if c != podmiot_idx)
                            if other_cols_empty and table[next_row][podmiot_idx]:
                                adres_val += " " + str(table[next_row][podmiot_idx])
                                next_row += 1
                            else:
                                break
                        
                        # Czyszczenie tekstu z niepotrzebnych znaków nowej linii
                        extracted_entries.append({
                            "Plik PDF": os.path.basename(pdf_path),
                            "Podmiot": podmiot_val.replace('\n', ' ').strip(),
                            "Adres": adres_val.replace('\n', ' ').strip()
                        })
    
    return extracted_entries

def main():
    folder_path = "." # Ścieżka do folderu z PDF
    final_data = []
    
    for file in os.listdir(folder_path):
        if file.lower().endswith(".pdf"):
            print(f"Przetwarzanie: {file}")
            data = extract_table_data(os.path.join(folder_path, file))
            final_data.extend(data)
    
    if final_data:
        df = pd.DataFrame(final_data)
        # Usuwamy duplikaty, jeśli ten sam podmiot został wykryty wielokrotnie w jednym pliku
        df.drop_duplicates(inplace=True)
        df.to_excel("wynik_egib.xlsx", index=False)
        print("\nSukces! Dane zapisane w 'wynik_egib.xlsx'")
    else:
        print("Nie znaleziono danych.")

if __name__ == "__main__":
    main()
