import pandas as pd
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ======================================
#   🔥 CORS — FUNCIONANDO CON GITHUB PAGES
# ======================================
origins = [
    "https://matrizbase.github.io",
    "https://matrizbase.github.io/cobros-web",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ======================================
#   📄 Cargar Excel
# ======================================
EXCEL_FILE = "Plantilla_Basedatos.xlsx"

df_base = pd.read_excel(EXCEL_FILE, sheet_name="Busqueda")
df_tel = pd.read_excel(EXCEL_FILE, sheet_name="Base tel")

df_base.columns = df_base.columns.str.strip()
df_tel.columns = df_tel.columns.str.strip()

# ======================================
#   🔐 PINs válidos
# ======================================
VALID_PINS = {
    "482911", "551928", "844155", "663512", "190245",
    "310928", "992451", "155702", "431700", "920018",
    "118722", "700581", "611520", "801250", "319900"
}

# ======================================
#   🔐 LOGIN
# ======================================
@app.post("/login")
def login(data: dict):
    pin = data.get("pin", "").strip()

    if pin not in VALID_PINS:
        raise HTTPException(status_code=401, detail="PIN inválido")

    return {
        "token": pin[::-1],    # token = PIN invertido
        "asesor": f"Asesor {pin}"
    }

# ======================================
#   🔍 BUSCAR
# ======================================
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

    # =================================================
    #   Buscar coincidencias en hoja "Busqueda"
    # =================================================
    for idx, row in df_base.iterrows():

        nombre_row = str(row.get("NOMBRE_CLIENTE", "")).strip()
        dpi_row = str(row.get("DPI", "")).strip()
        nit_row = str(row.get("NIT", "")).strip()

        coincide = False

        if nombre and nombre.lower() in nombre_row.lower():
            coincide = True
        if dpi and dpi == dpi_row:
            coincide = True
        if nit and nit == nit_row:
            coincide = True

        if coincide:
            # ------------------------------------------
            #   Buscar teléfonos en segunda hoja
            # ------------------------------------------
            tel_row = df_tel[
                (df_tel["DPI"].astype(str) == dpi_row) |
                (df_tel["NIT"].astype(str) == nit_row)
            ]

            telefonos = []
            if not tel_row.empty:
                r = tel_row.iloc[0]
                telefonos = [
                    r.get("Tel_1"),
                    r.get("Tel_2"),
                    r.get("Tel_3"),
                    r.get("Tel_4"),
                    r.get("Tel_5")
                ]
                telefonos = [str(t) for t in telefonos if pd.notna(t)]

            resultados.append({
                "Nombre": nombre_row,
                "DPI": dpi_row,
                "NIT": nit_row,
                "Email": str(row.get("EMAIL", "")),
                "Telefonos": telefonos
            })

    return {"resultados": resultados}
