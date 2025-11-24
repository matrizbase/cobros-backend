import pandas as pd
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Permitir CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================
# Cargar la base
# ================
df_base = pd.read_excel("Plantilla_Basedatos.xlsx")

# Normalizar columnas relevantes
def norm(x):
    if pd.isna(x):
        return ""
    return str(x).strip().upper()

df_base["NOMBRE_CLIENTE"] = df_base["NOMBRE_CLIENTE"].apply(norm)
df_base["DPI"] = df_base["DPI"].apply(norm)
df_base["NIT"] = df_base["NIT"].apply(norm)
df_base["EMAIL"] = df_base["EMAIL"].apply(norm)

tel_cols = ["Tel_1", "Tel_2", "Tel_3", "Tel_4", "Tel_5"]

for c in tel_cols:
    df_base[c] = df_base[c].apply(norm)

# ==========================
#   FILTRO DE BUSQUEDA
# ==========================
@app.post("/buscar")
async def buscar(req: Request):
    data = await req.json()

    nombre = str(data.get("nombre", "")).strip().upper()
    dpi = str(data.get("dpi", "")).strip().upper()
    nit = str(data.get("nit", "")).strip().upper()

    df = df_base.copy()

    # Filtrar por criterios ingresados
    if nombre:
        df = df[df["NOMBRE_CLIENTE"].str.contains(nombre, na=False)]

    if dpi:
        df = df[df["DPI"].astype(str).str.contains(dpi)]

    if nit:
        df = df[df["NIT"].astype(str).str.contains(nit)]

    # Si no hay resultados
    if df.empty:
        return {"resultados": []}

    # Construir salida
    resultados = []
    for _, row in df.iterrows():
        tels = [
            row[c] for c in tel_cols
            if pd.notna(row[c]) and row[c] != ""
        ]

        resultados.append({
            "Nombre": row["NOMBRE_CLIENTE"],
            "DPI": row["DPI"],
            "NIT": row["NIT"],
            "Email": row["EMAIL"],
            "Telefonos": tels
        })

    return {"resultados": resultados}
