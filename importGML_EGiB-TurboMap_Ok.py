import os
import logging
import time
import csv
from collections import defaultdict
from lxml import etree
import pandas as pd
from tqdm import tqdm

# ================== KONFIGURACJA ==================
# Plik wejściowy GML (możesz zmienić nazwę pliku tutaj)
GML_FILE = "dataTurbo.gml" 

OUT_DIR = "out"
OUT_DZIALKI = os.path.join(OUT_DIR, "zestawienie_dzialek.xlsx")
OUT_WLASCICIELE = os.path.join(OUT_DIR, "zestawienie_wlascicieli.xlsx")
OUT_BRAK_NR = os.path.join(OUT_DIR, "wlasciciele_bez_numeru_porzadkowego.csv")
LOG_FILE = os.path.join(OUT_DIR, "przetwarzanie.log")

os.makedirs(OUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ================== POMOCNICZE FUNKCJE ==================
def xp_txt(node, xp, ns):
    """Pobiera tekst z pierwszego elementu pasującego do XPath."""
    r = node.xpath(xp, namespaces=ns)
    return r[0].strip() if r else ""

def href_id(href):
    """Czyści identyfikator z referencji (usuwa znak #)."""
    return href.replace("#", "").strip()

def parse_address(addr, ns):
    """Pobiera dane adresowe z węzła adresu."""
    return {
        "ulica": xp_txt(addr, ".//egb:ulica/text()", ns),
        "numer": xp_txt(addr, ".//egb:numerPorzadkowy/text()", ns),
        "lokal": xp_txt(addr, ".//egb:numerLokalu/text()", ns),
        "kod": xp_txt(addr, ".//egb:kodPocztowy/text()", ns),
        "miejsc": xp_txt(addr, ".//egb:miejscowosc/text()", ns),
    }

def format_address(a):
    """Formatuje słownik adresu do czytelnego ciągu znaków."""
    if not a:
        return ""
    parts = []
    # Ulica i numer
    if a.get("ulica") or a.get("numer"):
        ul = a.get('ulica', '')
        nr = a.get('numer', '')
        p = f"{ul} {nr}".strip()
        if a.get("lokal"):
            p = f"{p}/{a['lokal']}"
        parts.append(p)
    
    # Kod i miejscowość
    kod_miejsc = f"{a.get('kod', '')} {a.get('miejsc', '')}".strip()
    if kod_miejsc:
        parts.append(kod_miejsc)
        
    return ", ".join(filter(None, parts))

# ================== GŁÓWNA LOGIKA ==================
def run():
    start = time.time()
    logging.info(f"START przetwarzania pliku: {GML_FILE}")

    try:
        # Parsowanie XML (może zająć chwilę przy dużych plikach)
        # Używamy recover=True, aby ignorować drobne błędy składni XML
        parser = etree.XMLParser(recover=True, huge_tree=True)
        tree = etree.parse(GML_FILE, parser)
        root = tree.getroot()
    except Exception as e:
        logging.error(f"Błąd otwierania pliku GML: {e}")
        return

    # Definicja przestrzeni nazw (dostosowana do EGiB)
    ns = {
        "gml": "http://www.opengis.net/gml/3.2",
        "egb": "ewidencjaGruntowIBudynkow:1.0",
        "xlink": "http://www.w3.org/1999/xlink"
    }

    # 1. Indeksowanie Podmiotów (Osoby, Instytucje, Małżeństwa)
    logging.info("Indeksowanie podmiotów...")
    
    # Słownik: ID_Podmiotu -> { "nazwa": "...", "adres": {...}, "dane_osobowe": {...} }
    podmioty_info = {}
    
    # a) Osoby Fizyczne
    for os_fiz in tqdm(root.xpath("//egb:EGB_OsobaFizyczna", namespaces=ns), desc="Osoby fizyczne"):
        pid = os_fiz.get(f"{{{ns['gml']}}}id")
        imie1 = xp_txt(os_fiz, "egb:pierwszeImie/text()", ns)
        imie2 = xp_txt(os_fiz, "egb:drugieImie/text()", ns)
        nazwisko = xp_txt(os_fiz, "egb:pierwszyCzlonNazwiska/text()", ns)
        
        full_name = f"{nazwisko} {imie1} {imie2}".strip()
        owner_small = f"{nazwisko} {imie1}".strip()
        
        # Dane osobowe do nowych kolumn
        dane_osobowe = {
            "właściciel_small": owner_small,
            "nazwisko": nazwisko,
            "imie1": imie1,
            "imie2": imie2
        }
        
        # Adres
        addr_node = os_fiz.xpath(".//egb:adresOsobyFizycznej", namespaces=ns)
        adres_dict = {}
        if addr_node:
            pass 
        
        podmioty_info[pid] = {
            "nazwa": full_name, 
            "adres": adres_dict,
            "dane_osobowe": dane_osobowe,
            "typ": "osoba_fizyczna"
        }

    # b) Instytucje
    for inst in tqdm(root.xpath("//egb:EGB_Instytucja", namespaces=ns), desc="Instytucje"):
        pid = inst.get(f"{{{ns['gml']}}}id")
        nazwa_pelna = xp_txt(inst, "egb:nazwaPelna/text()", ns)
        nazwa_skr = xp_txt(inst, "egb:nazwaSkrocona/text()", ns)
        full_name = nazwa_pelna if nazwa_pelna else nazwa_skr
        
        # Dla instytucji właściciel_small to pełna nazwa
        dane_osobowe = {
            "właściciel_small": full_name,
            "nazwisko": "",
            "imie1": "",
            "imie2": ""
        }
        
        podmioty_info[pid] = {
            "nazwa": full_name, 
            "adres": {},
            "dane_osobowe": dane_osobowe,
            "typ": "instytucja"
        }

    # c) Adresy (budujemy mapę adresów, żeby uzupełnić dane podmiotów)
    logging.info("Indeksowanie adresów...")
    adresy_map = {} # ID_Adresu -> dict
    for adr in root.xpath("//egb:EGB_AdresZameldowania | //egb:EGB_AdresNieruchomosci | //egb:EGB_AdresSiedziby", namespaces=ns):
        aid = adr.get(f"{{{ns['gml']}}}id")
        adresy_map[aid] = parse_address(adr, ns)

    # Uzupełnianie adresów w podmiotach (dla tych co mają referencje)
    for node_name in ["EGB_OsobaFizyczna", "EGB_Instytucja"]:
        tag_adr = "adresOsobyFizycznej" if node_name == "EGB_OsobaFizyczna" else "adresInstytucji"
        for node in root.xpath(f"//egb:{node_name}", namespaces=ns):
            pid = node.get(f"{{{ns['gml']}}}id")
            if pid not in podmioty_info: continue
            
            ref_node = node.xpath(f"egb:{tag_adr}", namespaces=ns)
            if ref_node:
                href = ref_node[0].get(f"{{{ns['xlink']}}}href")
                if href:
                    clean_id = href_id(href)
                    if clean_id in adresy_map:
                        podmioty_info[pid]["adres"] = adresy_map[clean_id]

    # d) Małżeństwa (wymaga referencji do osób fizycznych)
    for malz in tqdm(root.xpath("//egb:EGB_Malzenstwo", namespaces=ns), desc="Małżeństwa"):
        pid = malz.get(f"{{{ns['gml']}}}id")
        # Pobieramy ID małżonków
        names = []
        for i in range(1, 4):
             refs = malz.xpath(f"egb:osobaFizyczna{i}/@xlink:href", namespaces=ns)
             if refs:
                 os_id = href_id(refs[0])
                 if os_id in podmioty_info:
                     names.append(podmioty_info[os_id]["nazwa"])
        
        nazwa_malz = " i ".join(names) if names else "Małżeństwo (brak danych)"
        
        # Dla małżeństw właściciel_small to nazwa małżeństwa
        dane_osobowe = {
            "właściciel_small": nazwa_malz,
            "nazwisko": "",
            "imie1": "",
            "imie2": ""
        }
        
        # Adres bierzemy od pierwszej osoby
        adr = {}
        if names:
             refs = malz.xpath(f"egb:osobaFizyczna1/@xlink:href | egb:osobaFizyczna2/@xlink:href", namespaces=ns)
             if refs:
                 os_id = href_id(refs[0])
                 if os_id in podmioty_info:
                     adr = podmioty_info[os_id]["adres"]

        podmioty_info[pid] = {
            "nazwa": nazwa_malz, 
            "adres": adr,
            "dane_osobowe": dane_osobowe,
            "typ": "malzenstwo"
        }

    # 2. Relacja JRG -> Właściciele (Udzialy)
    logging.info("Przetwarzanie udziałów (JRG -> Podmioty)...")
    jrg_to_owners = defaultdict(list) # JRG_ID -> lista nazw właścicieli

    # Szukamy udziałów we własności (władaniu)
    xpath_udzialy = "//egb:EGB_UdzialWeWlasnosci | //egb:EGB_UdzialWeWladaniu"
    
    for u in tqdm(root.xpath(xpath_udzialy, namespaces=ns), desc="Udziały"):
        # A. Znajdź JRG (Jednostkę Rejestrową)
        jrg_id = None
        
        jrg_refs = u.xpath(".//egb:przedmiotUdzialuWlasnosci/@xlink:href | .//egb:przedmiotUdzialuWladania/@xlink:href", namespaces=ns)
        if jrg_refs:
            jrg_id = href_id(jrg_refs[0])
        else:
            jrg_inner_refs = u.xpath(".//egb:przedmiotUdzialuWlasnosci//egb:JRG/@xlink:href | .//egb:przedmiotUdzialuWladania//egb:JRG/@xlink:href", namespaces=ns)
            if jrg_inner_refs:
                jrg_id = href_id(jrg_inner_refs[0])
        
        if not jrg_id:
            continue

        # B. Znajdź Podmiot (Właściciela)
        podmiot_refs = u.xpath(".//egb:podmiotUdzialuWlasnosci/@xlink:href | .//egb:podmiotUdzialuWeWladaniu/@xlink:href", namespaces=ns)
        
        target_ids = []
        if podmiot_refs:
            target_ids = [href_id(r) for r in podmiot_refs]
        else:
            nested_podmioty = u.xpath(".//egb:podmiotUdzialuWlasnosci/egb:EGB_Podmiot | .//egb:podmiotUdzialuWeWladaniu/egb:EGB_Podmiot", namespaces=ns)
            for np in nested_podmioty:
                for child in np:
                    href = child.get(f"{{{ns['xlink']}}}href")
                    if href:
                        target_ids.append(href_id(href))

        # Przypisz nazwy do JRG
        for tid in target_ids:
            if tid in podmioty_info:
                info = podmioty_info[tid]
                # Format: "Nazwa (Adres)"
                adr_str = format_address(info['adres'])
                entry_str = info['nazwa']
                if adr_str:
                    entry_str += f" [{adr_str}]"
                jrg_to_owners[jrg_id].append(entry_str)
            else:
                # Jeśli nie znaleziono w mapie (np. brak definicji w tym pliku), dodaj sam ID
                jrg_to_owners[jrg_id].append(f"ID: {tid}")

    # 3. Przetwarzanie Działek
    logging.info("Generowanie raportu działek...")
    dzialki_rows = []
    
    # Mapa właściciel -> lista działek (do drugiego raportu)
    wlasciciel_to_dzialki = defaultdict(list)
    wlasciciel_details = {} # Klucz (Nazwa) -> szczegóły właściciela

    for dz in tqdm(root.xpath("//egb:EGB_DzialkaEwidencyjna", namespaces=ns), desc="Działki"):
        id_dz = xp_txt(dz, "egb:idDzialki/text()", ns)
        pow_dz = xp_txt(dz, "egb:poleEwidencyjne/text()", ns)
        nr_kw = xp_txt(dz, "egb:numerKW/text()", ns)
        
        # Pobierz JRG ID
        jrg_ref = dz.xpath("egb:JRG2/@xlink:href", namespaces=ns)
        owners_list = []
        if jrg_ref:
            jid = href_id(jrg_ref[0])
            owners_list = jrg_to_owners.get(jid, [])
            
        owners_str = " | ".join(owners_list)
        
        # Pobierz adres działki
        adres_dzialki = ""
        adr_ref = dz.xpath("egb:adresDzialki/@xlink:href", namespaces=ns)
        if adr_ref:
            aid = href_id(adr_ref[0])
            if aid in adresy_map:
                adres_dzialki = format_address(adresy_map[aid])

        dzialki_rows.append({
            "ID Działki": id_dz,
            "Powierzchnia [ha]": pow_dz,
            "KW": nr_kw,
            "Adres": adres_dzialki,
            "Właściciele": owners_str
        })

        # Do raportu właścicieli
        for own in owners_list:
            # Rozdzielamy nazwę od adresu
            if "[" in own:
                name_part = own.split("[")[0].strip()
                addr_part = own.split("[")[1].replace("]", "").strip()
            else:
                name_part = own
                addr_part = ""
            
            wlasciciel_to_dzialki[name_part].append(id_dz)
            if name_part not in wlasciciel_details:
                # Znajdź właściciela w podmioty_info po nazwie
                owner_info = None
                for pid, info in podmioty_info.items():
                    if info["nazwa"] == name_part:
                        owner_info = info
                        break
                
                wlasciciel_details[name_part] = {
                    "adres": addr_part,
                    "info": owner_info
                }

    # 4. Zapis wyników
    logging.info("Zapisywanie plików Excel...")
    
    # Raport 1: Działki
    df_dz = pd.DataFrame(dzialki_rows)
    df_dz.to_excel(OUT_DZIALKI, index=False)
    
    # Raport 2: Właściciele (rozbudowany o nowe kolumny)
    wl_rows = []
    lp = 1
    for nazwa, dzialki in sorted(wlasciciel_to_dzialki.items()):
        details = wlasciciel_details.get(nazwa, {})
        owner_info = details.get("info", {})
        
        # Pobierz dane osobowe
        dane_osobowe = owner_info.get("dane_osobowe", {}) if owner_info else {}
        wlasciciel_small = dane_osobowe.get("właściciel_small", nazwa)
        
        # Pobierz adres z podmioty_info (jeśli istnieje)
        adres_dict = owner_info.get("adres", {}) if owner_info else {}
        
        wl_rows.append({
            "Lp": lp,
            "Właściciel": nazwa,
            "właściciel_small": wlasciciel_small,
            "ulica": adres_dict.get("ulica", ""),
            "numer_porzadkowy": adres_dict.get("numer", ""),
            "numer_lokalu": adres_dict.get("lokal", ""),
            "miasto": adres_dict.get("miejsc", ""),
            "kod pocztowy": adres_dict.get("kod", ""),
            "Adres": details.get("adres", ""),  # Stary format adresu dla kompatybilności
            "Działki": ", ".join(sorted(dzialki))
        })
        lp += 1
        
    df_wl = pd.DataFrame(wl_rows)
    # Ustawienie kolejności kolumn
    columns_order = ["Lp", "Właściciel", "właściciel_small", "ulica", "numer_porzadkowy", 
                     "numer_lokalu", "miasto", "kod pocztowy", "Adres", "Działki"]
    df_wl = df_wl[columns_order]
    df_wl.to_excel(OUT_WLASCICIELE, index=False)

    # Raport 3: Brak numeru (opcjonalnie, z oryginalnego skryptu)
    
    logging.info(f"Gotowe! Pliki zapisano w katalogu {OUT_DIR}")
    logging.info(f"Czas wykonania: {round(time.time() - start, 2)}s")

if __name__ == "__main__":
    run()