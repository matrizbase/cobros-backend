import pandas as pd
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ================================
#   CORS
# ================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # para GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
#   Cargar Excel
# ================================
EXCEL_FILE = "Plantilla_Basedatos.xlsx"

df_base = pd.read_excel(EXCEL_FILE, sheet_name="Busqueda")
df_tel = pd.read_excel(EXCEL_FILE, sheet_name="Base tel")

# Limpieza de columnas
df_base.columns = df_base.columns.str.strip()
df_tel.columns = df_tel.columns.str.strip()

# ================================
#   Normalización fuerte DPI / NIT
# ================================
def normalizar_columna(df, col):
    df[col] = (
        df[col]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.replace(" ", "")
    )

normalizar_columna(df_base, "DPI")
normalizar_columna(df_base, "NIT")

normalizar_columna(df_tel, "DPI")
normalizar_columna(df_tel, "NIT")

# ================================
#   PINs válidos (los 15)
# ================================
VALID_PINS = {
    "482911", "551928", "844155", "663512", "190245",
    "310928", "992451", "155702", "431700", "920018",
    "118722", "700581", "611520", "801250", "319900"
}

# ================================
#   LOGIN
# ================================
@app.post("/login")
def login(data: dict):
    pin = data.get("pin", "").strip()

    if pin not in VALID_PINS:
        raise HTTPException(status_code=401, detail="PIN inválido")

    return {
        "token": pin[::-1],  # token simple (PIN invertido)
        "asesor": f"Asesor {pin}"
    }

# ================================
#   BÚSQUEDA + TELÉFONOS
# ================================
@app.post("/buscar")
def buscar(data: dict, x_api_key: str = Header(None)):
    # Validación de token
    if not x_api_key or x_api_key[::-1] not in VALID_PINS:
        raise HTTPException(status_code=403, detail="Token inválido")

    # Normalizar criterios de búsqueda
    nombre = str(data.get("nombre", "")).strip().lower()
    dpi = str(data.get("dpi", "")).strip().replace(" ", "")
    nit = str(data.get("nit", "")).strip().replace(" ", "")

    if not nombre and not dpi and not nit:
        raise HTTPException(status_code=400, detail="Debe ingresar algún criterio.")

    resultados = []

    # Búsqueda en hoja principal
    for idx, row in df_base.iterrows():

        nombre_base = str(row.get("NOMBRE_CLIENTE", "")).lower().strip()
        dpi_base = str(row.get("DPI", "")).strip().replace(" ", "")
        nit_base = str(row.get("NIT", "")).strip().replace(" ", "")

        match = False

        if nombre and nombre in nombre_base:
            match = True
        if dpi and dpi == dpi_base:
            match = True
        if nit and nit == nit_base:
            match = True

        if match:
            # Buscar teléfonos usando DPI o NIT
            tel_row = df_tel[
                (df_tel["DPI"] == dpi_base) |
                (df_tel["NIT"] == nit_base)
            ]

            telefonos = []
            if not tel_row.empty:
                t = tel_row.iloc[0]
                telefonos = [
                    t.get("Tel_1"),
                    t.get("Tel_2"),
                    t.get("Tel_3"),
                    t.get("Tel_4"),
                    t.get("Tel_5")
                ]
                telefonos = [str(x) for x in telefonos if pd.notna(x)]

            resultados.append({
                "Nombre": row.get("NOMBRE_CLIENTE", ""),
                "DPI": dpi_base,
                "NIT": nit_base,
                "Email": row.get("EMAIL", ""),
                "Telefonos": telefonos
            })

    return {"resultados": resultados}
