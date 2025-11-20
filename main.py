# main.py
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import uuid, re, time, os
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup

# --- CONFIG ---
EXCEL_PATH = "Plantilla_Basedatos.xlsx"   # archivo que ya subiste al repo (Plantilla_Basedatos.xlsx)
SHEET_NAME = "Base tel"   # hoja con tu base de números

# Nota: en el entorno local del asistente el archivo estaba en:
# /mnt/data/81931a59-4f00-441e-86b2-da525397e987.xlsx
# Si por algún motivo tu servidor debe leer directamente esa ruta, cambia EXCEL_PATH a esa ruta.
# EXCEL_PATH = "/mnt/data/81931a59-4f00-441e-86b2-da525397e987.xlsx"

# --- Inicializar app ---
app = FastAPI(title="Cobros - Buscador MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # en producción limitar a tu dominio
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory stores (MVP) ---
SESSIONS: Dict[str, dict] = {}
HISTORY: List[dict] = []

# PINs predefinidos (PIN -> asesor_id)
PIN_MAP = {
 "482911":"asesor01","179034":"asesor02","305218":"asesor03","660401":"asesor04","993120":"asesor05",
 "127845":"asesor06","774532":"asesor07","508217":"asesor08","246901":"asesor09","831605":"asesor10",
 "412709":"asesor11","580333":"asesor12","999002":"asesor13","351776":"asesor14","613490":"asesor15"
}

# --- Load data ---
def load_data():
    if not os.path.exists(EXCEL_PATH):
        return pd.DataFrame()
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    df["search_text"] = (
        df.get("DPI","") + " " +
        df.get("NOMBRE_CLIENTE","") + " " +
        df.get("NIT","") + " " +
        df.get("EMAIL","") + " " +
        df.get("Tel_1","") + " " +
        df.get("Tel_2","") + " " +
        df.get("Tel_3","")
    ).str.lower()
    return df

DF = load_data()

# --- Models ---
class LoginIn(BaseModel):
    pin: str

# --- Auth dependency ---
def get_current_user(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key not in SESSIONS:
        raise HTTPException(status_code=401, detail="No autorizado")
    return SESSIONS[x_api_key]

# --- Endpoints ---
@app.get("/")
def root():
    return {"status": "ok", "rows_loaded": len(DF)}

@app.post("/login")
def login(payload: LoginIn):
    pin = payload.pin.strip()
    if pin not in PIN_MAP:
        raise HTTPException(status_code=401, detail="PIN inválido")
    asesor = PIN_MAP[pin]
    token = str(uuid.uuid4())
    SESSIONS[token] = {"asesor": asesor, "pin": pin, "created": time.time()}
    return {"token": token, "asesor": asesor}

# ---------- NUEVO: Endpoint GET /buscar ----------
@app.get("/buscar")
def buscar(
    nombre: Optional[str] = Query("", description="Nombre completo"),
    dpi: Optional[str] = Query("", description="DPI"),
    nit: Optional[str] = Query("", description="NIT"),
    valor: Optional[str] = Query("", description="Valor genérico (busqueda parcial)"),
    user = Depends(get_current_user)
):
    """
    Busca en la base interna (por campos separados: nombre, dpi, nit) y realiza búsqueda externa ligera.
    Retorna JSON { internal: [...], external: {...} }
    """
    global DF
    q_nombre = (nombre or "").strip()
    q_dpi = (dpi or "").strip()
    q_nit = (nit or "").strip()
    q_valor = (valor or "").strip().lower()

    results = []

    # Si se proporcionan nombre + dpi + nit, hacemos coincidencia exacta
    if q_nombre and q_dpi and q_nit:
        mask = (
            DF.get("NOMBRE_CLIENTE","").str.lower() == q_nombre.lower()
        ) & (
            DF.get("DPI","").str.strip() == q_dpi
        ) & (
            DF.get("NIT","").str.strip() == q_nit
        )
        matches = DF[mask]
    else:
        # construir consulta a partir de los campos
        if q_valor:
            query = q_valor
        else:
            query = " ".join([q_nombre, q_dpi, q_nit]).strip().lower()
        if query:
            matches = DF[DF["search_text"].str.contains(re.escape(query), na=False)]
        else:
            matches = pd.DataFrame()

    for _, row in matches.iterrows():
        phones = []
        for col in ["Tel_1","Tel_2","Tel_3","Tel_4","Tel_5"]:
            if col in row and str(row[col]).strip():
                phones.append(str(row[col]).strip())
        results.append({
            "ID": row.get("ID",""),
            "Nombre": row.get("NOMBRE_CLIENTE",""),
            "DPI": row.get("DPI",""),
            "NIT": row.get("NIT",""),
            "FechaNacimiento": row.get("fecha_nacimiento",""),
            "Email": row.get("EMAIL",""),
            "TelBase": phones
        })

    # registrar búsqueda en historial
    HISTORY.append({
        "asesor": user["asesor"],
        "timestamp": time.time(),
        "nombre": q_nombre,
        "dpi": q_dpi,
        "nit": q_nit,
        "valor": q_valor,
        "internal_found": len(results) > 0
    })

    # llamada externa ligera (scraping MVP)
    external = external_search(q_nombre or q_dpi or q_nit or q_valor)

    return {"internal": results, "external": external}
# --------------------------------------------------

@app.get("/numeros/full")
def get_numeros_full(limit: int = 50):
    global DF
    if DF.empty:
        return {"status": "empty", "message": "No se cargó ningún archivo Excel."}
    return {
        "status": "ok",
        "rows": DF.head(limit).to_dict(orient="records"),
        "total_rows": len(DF),
        "limit_used": limit
    }

@app.get("/history")
def history(user = Depends(get_current_user)):
    user_hist = [h for h in HISTORY if h["asesor"] == user["asesor"]]
    return {"history": user_hist[-200:]}

@app.get("/reload")
def reload_data(user = Depends(get_current_user)):
    """
    Recarga el Excel en memoria sin reiniciar el servidor.
    Requiere token (x-api-key).
    """
    global DF
    DF = load_data()
    return {"status": "ok", "rows_loaded": len(DF)}

@app.get("/export")
def export_latest(user = Depends(get_current_user)):
    user_hist = [h for h in HISTORY if h["asesor"] == user["asesor"]]
    if not user_hist:
        raise HTTPException(status_code=404, detail="No hay historial")
    last = user_hist[-1]
    # recrear búsqueda y retornar CSV
    nombre = last.get("nombre","")
    dpi = last.get("dpi","")
    nit = last.get("nit","")
    # reusar lógica de búsqueda
    # (llamamos internamente a buscar via Query construction)
    # Para simplicidad, reutilizamos la lógica aquí:
    matches = []
    query = " ".join([nombre, dpi, nit]).strip().lower()
    if query:
        matches_df = DF[DF["search_text"].str.contains(re.escape(query), na=False)]
    else:
        matches_df = pd.DataFrame()

    rows = []
    for _, row in matches_df.iterrows():
        phones = []
        for col in ["Tel_1","Tel_2","Tel_3","Tel_4","Tel_5"]:
            if col in row and str(row[col]).strip():
                phones.append(str(row[col]).strip())
        rows.append({
            "ID": row.get("ID",""),
            "Nombre": row.get("NOMBRE_CLIENTE",""),
            "DPI": row.get("DPI",""),
            "NIT": row.get("NIT",""),
            "Email": row.get("EMAIL",""),
            "FechaNacimiento": row.get("fecha_nacimiento",""),
            "TelBase": ";".join(phones)
        })
    df_out = pd.DataFrame(rows)
    return {"csv": df_out.to_csv(index=False)}

# --- External search (scraping básico) ---
PHONE_RE = re.compile(r'(\+?502[-\s]?\d{4}[-\s]?\d{4}|\d{8})')

def external_search(query: str, limit=5):
    if not query:
        return {}
    try:
        headers = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64)"}
        q = requests.utils.requote_uri(query + " site:facebook.com OR site:linkedin.com OR site:instagram.com OR site:tikok.com")
        url = f"https://www.google.com/search?q={q}&num={limit}"
        r = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        phones = set()
        emails = set()
        for a in soup.find_all("a"):
            href = a.get("href","")
            if href.startswith("/url?q="):
                link = href.split("/url?q=")[1].split("&")[0]
                links.append(link)
                try:
                    rr = requests.get(link, headers=headers, timeout=6)
                    text = rr.text
                    for m in PHONE_RE.findall(text):
                        phones.add(m)
                    for email in re.findall(r'[\w\.-]+@[\w\.-]+', text):
                        emails.add(email)
                except:
                    pass
        return {"query": query, "links": links[:10], "phones": list(phones), "emails": list(emails)}
    except Exception as e:
        return {"error": str(e)}
