
import os
import joblib
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ruta_base = os.path.dirname(__file__)
ruta_datos = os.path.join(ruta_base, "datos")
ruta_artefactos = os.path.join(ruta_base, "artefactos")

artefacto = joblib.load(os.path.join(ruta_artefactos, "modelo_pd.pkl"))

modelo = artefacto["modelo"]
escalador = artefacto["escalador"]
columnas_caracteristicas = artefacto["columnas_caracteristicas"]

df_validacion = pd.read_csv(os.path.join(ruta_datos, "pd_validacion.csv"))

app = FastAPI(title="API Demo Probabilidad de Default PYMEs")


class SolicitudPD(BaseModel):
    id_empresa: int


class RespuestaPD(BaseModel):
    id_empresa: int
    pd_12m: float
    banda_score: str


def pd_a_banda(pd_12m: float) -> str:
    if pd_12m <= 0.005:
        return "A"
    elif pd_12m <= 0.015:
        return "BBB"
    elif pd_12m <= 0.03:
        return "BB"
    elif pd_12m <= 0.07:
        return "B"
    else:
        return "CCC"


def calcular_pd_empresa(id_empresa: int) -> Optional[RespuestaPD]:
    filas = df_validacion[df_validacion["id_empresa"] == id_empresa]
    if filas.empty:
        return None

    fila = filas.iloc[-1]
    X = fila[columnas_caracteristicas].values.reshape(1, -1)
    X_esc = escalador.transform(X)
    pd_estimado = float(modelo.predict_proba(X_esc)[0, 1])
    banda = pd_a_banda(pd_estimado)

    return RespuestaPD(
        id_empresa=id_empresa,
        pd_12m=pd_estimado,
        banda_score=banda
    )


@app.post("/calcular_pd", response_model=RespuestaPD)
def endpoint_calcular_pd(solicitud: SolicitudPD):
    resultado = calcular_pd_empresa(solicitud.id_empresa)
    if resultado is None:
        raise HTTPException(status_code=404, detail="id_empresa no encontrado en el conjunto de validación.")
    return resultado
