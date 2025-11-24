# ============================
#  main.py  — Versión CORREGIDA
# ============================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os, re, requests
from bs4 import BeautifulSoup

# ------------------------------
# CARGAR EXCEL
# ------------------------------
EXCEL_PATH = "Plantilla_Basedatos.xlsx"
SHEET_NAME = "Base tel"

def load_excel():
    if not os.path.exists(EXCEL_PATH):
        print("⚠ Excel no encontrado")
        return pd.DataFrame()

    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str)
    df = df.fillna("")

    # Normalizar
    df.columns = [str(c).strip() for c in df.columns]

    # Crear columna de texto para búsqueda parcial
    df["search_text"] = (
        df.get("NOMBRE_CLIENTE", "") + " " +
        df.get("DPI", "") + " " +
        df.get("NIT", "") + " " +
        df.get("EMAIL", "")
    ).str.lower()

    return df


DF = load_excel()

# ------------------------------
# FASTAPI APP
# ------------------------------
app = FastAPI(title="Buscador de Clientes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"]
)

# ------------------------------
# ENDPOINT: TEST
# ------------------------------
@app.get("/")
def root():
    return {"status": "ok", "rows_loaded": len(DF)}

# ------------------------------
# ENDPOINT PRINCIPAL /buscar
# ------------------------------
@app.post("/buscar")
def buscar(payload: dict):

    nombre = (payload.get("nombre") or "").strip().lower()
    dpi    = (payload.get("dpi") or "").strip()
    nit    = (payload.get("nit") or "").strip()

    if not nombre and not dpi and not nit:
        raise HTTPException(400, "Debe ingresar nombre, DPI o NIT")

    # --------------------------
    # BÚSQUEDA INTERNA
    # --------------------------
    query = f"{nombre} {dpi} {nit}".strip().lower()

    internos = DF[DF["search_text"].str.contains(query, na=False)]

    internal_results = []
    for _, row in internos.iterrows():
        internal_results.append({
            "Nombre": row.get("NOMBRE_CLIENTE", ""),
            "DPI": row.get("DPI", ""),
            "NIT": row.get("NIT", ""),
            "Email": row.get("EMAIL", ""),
            "Telefonos": [
                row.get("Tel_1", ""), row.get("Tel_2", ""),
                row.get("Tel_3", ""), row.get("Tel_4", ""),
                row.get("Tel_5", "")
            ]
        })

    # --------------------------
    # BÚSQUEDA EXTERNA (Google)
    # --------------------------
    externo = buscar_google(query)

    return {
        "internal": internal_results,
        "external": externo
    }

# ------------------------------
# BUSQUEDA LIGERA GOOGLE
# ------------------------------
def buscar_google(q):
    try:
        url = f"https://www.google.com/search?q={q}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=7)
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        phones = set()
        emails = set()

        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href.startswith("/url?q="):
                u = href.split("/url?q=")[1].split("&")[0]
                links.append(u)

        return {
            "links": links[:5],
            "phones": list(phones),
            "emails": list(emails)
        }

    except Exception as e:
        return {"error": str(e)}
