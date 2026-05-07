def filtruj_linie(plik_wejsciowy, plik_wzorcowy, plik_wyjsciowy):
    try:
        # Wczytujemy linie z drugiego pliku do zbioru (usuwamy białe znaki)
        with open(plik_wzorcowy, 'r', encoding='utf-8') as f2:
            linie_do_wykluczenia = {line.strip() for line in f2}

        # Otwieramy plik wejściowy i tworzymy plik wynikowy
        with open(plik_wejsciowy, 'r', encoding='utf-8') as f1, \
             open(plik_wyjsciowy, 'w', encoding='utf-8') as out:
            
            for line in f1:
                # Sprawdzamy, czy linia (bez znaków nowej linii) jest w zbiorze
                if line.strip() not in linie_do_wykluczenia:
                    out.write(line)
        
        print(f"Przetwarzanie zakończone. Wynik zapisano w {plik_wyjsciowy}")

    except FileNotFoundError as e:
        print(f"Błąd: Nie znaleziono pliku - {e}")

# Uruchomienie skryptu
filtruj_linie('in.txt', 'in2.txt', 'out.txt')