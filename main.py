import pandas as pd
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ================================
#   CORS
# ================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
#   BÚSQUEDA
# ================================
@app.post("/buscar")
def buscar(data: dict, x_api_key: str = Header(None)):
    # Validar token
    if not x_api_key or x_api_key[::-1] not in VALID_PINS:
        raise HTTPException(status_code=403, detail="Token inválido")

    nombre = str(data.get("nombre", "")).strip()
    dpi = str(data.get("dpi", "")).strip()
    nit = str(data.get("nit", "")).strip()

    if not nombre and not dpi and not nit:
        raise HTTPException(status_code=400, detail="Debe ingresar algún criterio.")

    resultados = []

    # Buscar dentro de hoja principal "Busqueda"
    for idx, row in df_base.iterrows():

        match = False

        if nombre and nombre.lower() in str(row["NOMBRE_CLIENTE"]).lower():
            match = True
        if dpi and dpi == str(row["DPI"]):
            match = True
        if nit and nit == str(row["NIT"]):
            match = True

        if match:
            # Buscar teléfonos en hoja Base tel
            tel_row = df_tel[
                (df_tel["DPI"] == row["DPI"]) |
                (df_tel["NIT"] == row["NIT"])
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
                "Nombre": row["NOMBRE_CLIENTE"],
                "DPI": str(row["DPI"]),
                "NIT": str(row["NIT"]),
                "Email": row.get("EMAIL", ""),
                "Telefonos": telefonos
            })

    return {"resultados": resultados}
