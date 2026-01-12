import os
import logging
import time
import csv
from collections import defaultdict
from lxml import etree
import pandas as pd
from tqdm import tqdm

# ================== KONFIG ==================
GML_FILE = "data.gml"
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

# ================== HELPERS ==================
def xp_txt(node, xp, ns):
    r = node.xpath(xp, namespaces=ns)
    return r[0].strip() if r else ""

def href_id(href):
    return href.replace("#", "").strip()

def parse_address(addr, ns):
    return {
        "ulica": xp_txt(addr, ".//egb:ulica/text()", ns),
        "numer": xp_txt(addr, ".//egb:numerPorzadkowy/text()", ns),
        "lokal": xp_txt(addr, ".//egb:numerLokalu/text()", ns),
        "kod": xp_txt(addr, ".//egb:kodPocztowy/text()", ns),
        "miejsc": xp_txt(addr, ".//egb:miejscowosc/text()", ns),
    }

def format_address(a):
    if not a:
        return ""
    parts = []
    if a.get("ulica") or a.get("numer"):
        p = f"{a.get('ulica','')} {a.get('numer','')}".strip()
        if a.get("lokal"):
            p = f"{p}/{a['lokal']}"
        parts.append(p)
    if a.get("kod"):
        parts.append(a["kod"])
    if a.get("miejsc"):
        parts.append(a["miejsc"])
    return " ".join(parts)

# ================== MAIN ==================
def run():
    start = time.time()
    logging.info("START przetwarzania")

    tree = etree.parse(GML_FILE)
    root = tree.getroot()

    ns = {
        "gml": "http://www.opengis.net/gml/3.2",
        "egb": "ewidencjaGruntowIBudynkow:1.0",
        "xlink": "http://www.w3.org/1999/xlink"
    }

    # ---------- ADRESY ----------
    adresy = {
        a.get("{http://www.opengis.net/gml/3.2}id"): parse_address(a, ns)
        for a in root.xpath("//egb:EGB_AdresPodmiotu", namespaces=ns)
        if a.get("{http://www.opengis.net/gml/3.2}id")
    }

    # ---------- PODMIOTY ----------
    osoby = {}
    instytucje = {}
    malzenstwa = {}
    wlasciciel_info = {}
    brak_numeru = []

    # Osoby fizyczne
    for p in root.xpath("//egb:EGB_OsobaFizyczna", namespaces=ns):
        pid = p.get("{http://www.opengis.net/gml/3.2}id")
        imie = xp_txt(p, ".//egb:pierwszeImie/text()", ns)
        nazw = xp_txt(p, ".//egb:pierwszyCzlonNazwiska/text()", ns)
        nazwa = f"{imie} {nazw}".strip() or pid

        addr_ref = p.xpath(".//egb:adresZameldowania/@xlink:href", namespaces=ns)
        addr = adresy.get(href_id(addr_ref[0])) if addr_ref else None

        osoby[pid] = f"{nazwa} {format_address(addr)}".strip()
        wlasciciel_info[pid] = (nazwa, addr)

        numer = addr.get("numer", "").strip() if addr else ""
        if numer == "":
            brak_numeru.append(pid)

    # Instytucje
    for i in root.xpath("//egb:EGB_Instytucja", namespaces=ns):
        iid = i.get("{http://www.opengis.net/gml/3.2}id")
        nazwa = xp_txt(i, ".//egb:nazwaPelna/text()", ns) or iid

        addr_ref = i.xpath(".//egb:adresSiedziby/@xlink:href", namespaces=ns)
        addr = adresy.get(href_id(addr_ref[0])) if addr_ref else None

        instytucje[iid] = f"{nazwa} {format_address(addr)}".strip()
        wlasciciel_info[nazwa] = (nazwa, addr)

        numer = addr.get("numer", "").strip() if addr else ""
        if numer == "":
            brak_numeru.append(nazwa)

    # Małżeństwa
    for m in root.xpath("//egb:EGB_Malzenstwo", namespaces=ns):
        mid = m.get("{http://www.opengis.net/gml/3.2}id")
        malzenstwa[mid] = [
            href_id(h) for h in
            m.xpath(".//egb:osobaFizyczna2/@xlink:href | .//egb:osobaFizyczna3/@xlink:href", namespaces=ns)
        ]

    # ---------- JRG ----------
    jrg_numery = {
        j.get("{http://www.opengis.net/gml/3.2}id"):
        xp_txt(j, ".//egb:idJednostkiRejestrowej//text()", ns)
        for j in root.xpath("//egb:EGB_JednostkaRejestrowaGruntow", namespaces=ns)
    }

    # ---------- UDZIAŁY ----------
    jrg_to_podmioty = defaultdict(list)
    for u in root.xpath("//egb:EGB_UdzialWeWlasnosci", namespaces=ns):
        jrg_ref = u.xpath(".//egb:przedmiotUdzialuWlasnosci/@xlink:href", namespaces=ns)
        if not jrg_ref:
            continue
        jrg_id = href_id(jrg_ref[0])
        for p in u.xpath(".//egb:podmiotUdzialuWlasnosci/@xlink:href", namespaces=ns):
            jrg_to_podmioty[jrg_id].append(href_id(p))

    # ---------- DZIAŁKI ----------
    rows = []
    wlasciciel_dzialki = defaultdict(set)

    for d in tqdm(root.xpath("//egb:EGB_DzialkaEwidencyjna", namespaces=ns)):
        dzialka = xp_txt(d, ".//egb:idDzialki//text()", ns)
        jrg_ref = d.xpath(".//egb:JRG2/@xlink:href", namespaces=ns)
        jrg_id = href_id(jrg_ref[0]) if jrg_ref else ""

        owners_txt = []

        for pid in jrg_to_podmioty.get(jrg_id, []):
            if pid in osoby:
                owners_txt.append(osoby[pid])
                wlasciciel_dzialki[pid].add(dzialka)
            elif pid in instytucje:
                name = xp_txt(root.xpath(f"//egb:EGB_Instytucja[@gml:id='{pid}']", namespaces=ns)[0],
                              ".//egb:nazwaPelna/text()", ns)
                owners_txt.append(instytucje[pid])
                wlasciciel_dzialki[name].add(dzialka)
            elif pid in malzenstwa:
                for oid in malzenstwa[pid]:
                    if oid in osoby:
                        owners_txt.append(osoby[oid])
                        wlasciciel_dzialki[oid].add(dzialka)

        rows.append({
            "Działka": dzialka,
            "Powierzchnia [m2]": xp_txt(d, ".//egb:poleEwidencyjne/text()", ns),
            "Dokument": xp_txt(d, ".//egb:numerKW/text()", ns),
            "JRG": jrg_numery.get(jrg_id, ""),
            "wlasciciele_z_adresem": "; ".join(dict.fromkeys(owners_txt))
        })

    pd.DataFrame(rows).to_excel(OUT_DZIALKI, index=False)

    # ---------- CSV: brak numeru + ID DZIAŁEK ----------
    with open(OUT_BRAK_NR, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["wlasciciel", "ulica", "kod_pocztowy", "miejscowosc", "id_dzialki"])

        for key in brak_numeru:
            nazwa, addr = wlasciciel_info.get(key, (key, None))
            writer.writerow([
                nazwa,
                addr.get("ulica", "") if addr else "",
                addr.get("kod", "") if addr else "",
                addr.get("miejsc", "") if addr else "",
                ", ".join(sorted(wlasciciel_dzialki.get(key, [])))
            ])

    # ---------- XLSX: zestawienie właścicieli ----------
    wl_rows = []
    lp = 1
    for key, (nazwa, addr) in wlasciciel_info.items():
        wl_rows.append({
            "lp": lp,
            "wlasciciel": nazwa,
            "kod_pocztowy": addr.get("kod", "") if addr else "",
            "miejscowosc": addr.get("miejsc", "") if addr else "",
            "ulica": addr.get("ulica", "") if addr else "",
            "numer_porzadkowy": addr.get("numer", "") if addr else "",
            "numer_lokalu": addr.get("lokal", "") if addr else "",
            "dzialki": ", ".join(sorted(wlasciciel_dzialki.get(key, [])))
        })
        lp += 1

    pd.DataFrame(wl_rows).to_excel(OUT_WLASCICIELE, index=False)

    elapsed = round(time.time() - start, 2)
    logging.info(f"KONIEC. Czas realizacji: {elapsed}s")
    logging.info(f"Wykryte właściciele: {len(wlasciciel_info)}")
    logging.info(f"Wykryte JRG: {len(jrg_numery)}")
    logging.info(f"Wykryte działki: {len(rows)}")

# ================== START ==================
if __name__ == "__main__":
    run()
