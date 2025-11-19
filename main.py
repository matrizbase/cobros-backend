# main.py
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import uuid, re, time, os
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup

# --- CONFIG ---
EXCEL_PATH = "Plantilla_Basedatos.xlsx"
SHEET_NAME = "Base tel"   # hoja con tu base de números

# --- Inicializar app ---
app = FastAPI(title="Cobros - Buscador MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # en producción limita a tu dominio
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

# --- Cargar Excel al inicio (si existe) ---
def load_data():
    if not os.path.exists(EXCEL_PATH):
        return pd.DataFrame()
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str).fillna("")
    # normalizar nombres de columnas y proveer columna de búsqueda
    df.columns = [str(c).strip() for c in df.columns]
    df["search_text"] = (df.get("DPI","") + " " + df.get("NOMBRE_CLIENTE","") + " " + df.get("NIT","") + " " +
                         df.get("EMAIL","") + " " + df.get("Tel_1","") + " " + df.get("Tel_2","") + " " +
                         df.get("Tel_3","")).str.lower()
    return df

DF = load_data()

# --- Pydantic models ---
class LoginIn(BaseModel):
    pin: str

class SearchIn(BaseModel):
    nombre: Optional[str] = ""
    dpi: Optional[str] = ""
    nit: Optional[str] = ""

# --- Auth dependency ---
def get_current_user(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key not in SESSIONS:
        raise HTTPException(status_code=401, detail="No autorizado")
    return SESSIONS[x_api_key]

# --- Endpoints ---

@app.get("/")
def root():
    return {"status":"ok", "rows_loaded": len(DF)}

@app.post("/login")
def login(payload: LoginIn):
    pin = payload.pin.strip()
    if pin not in PIN_MAP:
        raise HTTPException(status_code=401, detail="PIN inválido")
    asesor = PIN_MAP[pin]
    token = str(uuid.uuid4())
    # token in-memory: {token: {asesor, pin, created}}
    SESSIONS[token] = {"asesor": asesor, "pin": pin, "created": time.time()}
    return {"token": token, "asesor": asesor}

@app.post("/search")
def search(payload: SearchIn, user = Depends(get_current_user)):
    nombre = (payload.nombre or "").strip()
    dpi = (payload.dpi or "").strip()
    nit = (payload.nit or "").strip()

    # Reusar DF cargado
    global DF
    results = []

    if nombre and dpi and nit:
        mask = (DF.get("NOMBRE_CLIENTE","").str.lower() == nombre.lower()) & (DF.get("DPI","").str.strip() == dpi) & (DF.get("NIT","").str.strip() == nit)
        matches = DF[mask]
    else:
        queries = " ".join([nombre, dpi, nit]).strip().lower()
        if queries:
            # usar contains para parcial (Opción 1: mostrar todas coincidencias)
            matches = DF[DF["search_text"].str.contains(re.escape(queries), na=False)]
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

    # registrar búsqueda
    HISTORY.append({
        "asesor": user["asesor"],
        "timestamp": time.time(),
        "nombre": nombre,
        "dpi": dpi,
        "nit": nit,
        "internal_found": len(results) > 0
    })

    # búsqueda externa ligera (scraping MVP)
    external = external_search(nombre or dpi or nit)

    return {"internal": results, "external": external}

@app.get("/history")
def history(user = Depends(get_current_user)):
    user_hist = [h for h in HISTORY if h["asesor"] == user["asesor"]]
    return {"history": user_hist[-200:]}

@app.get("/export")
def export_latest(user = Depends(get_current_user)):
    user_hist = [h for h in HISTORY if h["asesor"] == user["asesor"]]
    if not user_hist:
        raise HTTPException(status_code=404, detail="No hay historial")
    last = user_hist[-1]
    payload = SearchIn(nombre=last["nombre"], dpi=last["dpi"], nit=last["nit"])
    res = search(payload, user)
    rows = []
    for r in res["internal"]:
        rows.append({
            "ID": r["ID"],
            "Nombre": r["Nombre"],
            "DPI": r["DPI"],
            "NIT": r["NIT"],
            "Email": r["Email"],
            "FechaNacimiento": r["FechaNacimiento"],
            "TelBase": ";".join(r["TelBase"])
        })
    df_out = pd.DataFrame(rows)
    return {"csv": df_out.to_csv(index=False)}

# --- External search (scraping muy básico) ---
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
                # intentar extraer phone/email de la página destino (ligero)
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
