# =====================================================
#   main.py — Versión SIMPLE, FUNCIONAL y ESTABLE
# =====================================================

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

# ============================
# CONFIGURACIÓN
# ============================
EXCEL_PATH = "Plantilla_Basedatos.xlsx"   # tu archivo
SHEET_NAME = "Base tel"                   # nombre de la hoja

# ============================
# LOGIN — PINs permitidos
# ============================
PIN_MAP = {
 "482911":"asesor01","179034":"asesor02","305218":"asesor03","660401":"asesor04","993120":"asesor05",
 "127845":"asesor06","774532":"asesor07","508217":"asesor08","246901":"asesor09","831605":"asesor10",
 "412709":"asesor11","580333":"asesor12","999002":"asesor13","351776":"asesor14","613490":"asesor15"
}

SESSIONS = {}

# ============================
# CARGA DEL EXCEL
# ============================
def load_excel():
    if not os.path.exists(EXCEL_PATH):
        print("⚠ Excel no encontrado en el servidor")
        return pd.DataFrame()

    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    # columna de búsqueda rápida
    df["search_text"] = (
        df.get("NOMBRE_CLIENTE", "") + " " +
        df.get("DPI", "") + " " +
        df.get("NIT", "")
    ).str.lower()

    return df

DF = load_excel()

# ============================
# INICIALIZAR FASTAPI
# ============================
app = FastAPI(title="Buscador Interno - Excel")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# DEPENDENCIA DE AUTENTICACIÓN
# ============================
def require_login(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key not in SESSIONS:
        raise HTTPException(401, "No autorizado — inicia sesión")
    return SESSIONS[x_api_key]

# ============================
# ENDPOINT: TEST
# ============================
@app.get("/")
def root():
    return {"status": "ok", "rows_loaded": len(DF)}

# ============================
# LOGIN
# ============================
@app.post("/login")
def login(data: dict):
    pin = str(data.get("pin", "")).strip()

    if pin not in PIN_MAP:
        raise HTTPException(status_code=401, detail="PIN inválido")

    # crear token muy simple
    token = f"token_{pin}"
    SESSIONS[token] = {"asesor": PIN_MAP[pin]}

    return {"token": token, "asesor": PIN_MAP[pin]}

# ============================
# BUSCAR (solo en Excel)
# ============================
@app.post("/buscar")
def buscar(data: dict, user=Depends(require_login)):

    nombre = (data.get("nombre") or "").strip().lower()
    dpi    = (data.get("dpi") or "").strip()
    nit    = (data.get("nit") or "").strip()

    if not nombre and not dpi and not nit:
        raise HTTPException(400, "Ingresa nombre, DPI o NIT")

    query = f"{nombre} {dpi} {nit}".lower()
    results = DF[DF["search_text"].str.contains(query, na=False)]

    salida = []
    for _, row in results.iterrows():
        salida.append({
            "Nombre": row.get("NOMBRE_CLIENTE", ""),
            "DPI": row.get("DPI", ""),
            "NIT": row.get("NIT", ""),
            "Email": row.get("EMAIL", ""),
            "Telefonos": [
                row.get("Tel_1", ""),
                row.get("Tel_2", ""),
                row.get("Tel_3", ""),
                row.get("Tel_4", ""),
                row.get("Tel_5", "")
            ]
        })

    return {"resultados": salida}
