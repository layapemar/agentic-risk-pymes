import pandas as pd


def calcular_ratios(df: pd.DataFrame) -> dict:
    """
    Recibe el histórico de estados financieros de una empresa
    y devuelve ratios, fortalezas, debilidades y tendencia.
    """
    df = df.sort_values("ano")
    if df.empty:
        raise ValueError("El dataframe de estados financieros está vacío.")

    ultima = df.iloc[-1]

    activos_corrientes = ultima["caja"] + ultima["cuentas_cobrar"] + ultima["inventario"]
    ratio_liquidez = activos_corrientes / (ultima["cuentas_pagar"] + 1e-6)
    ratio_apalancamiento = ultima["pasivos_totales"] / (ultima["patrimonio"] + 1e-6)
    margen_ebitda = ultima["ebitda"] / (ultima["ingresos"] + 1e-6)
    cobertura_intereses = ultima["ebitda"] / (ultima["gastos_intereses"] + 1e-6)

    if len(df) >= 2:
        crecimiento_ingresos = df.iloc[-1]["ingresos"] / (df.iloc[-2]["ingresos"] + 1e-6) - 1
        margen_prev = df.iloc[-2]["ebitda"] / (df.iloc[-2]["ingresos"] + 1e-6)
        tendencia_margen = "mejorando" if margen_ebitda > margen_prev else "empeorando"
    else:
        crecimiento_ingresos = None
        tendencia_margen = "sin histórico suficiente"

    fortalezas, debilidades = [], []

    if ratio_liquidez >= 1.2:
        fortalezas.append("Buena liquidez de corto plazo.")
    else:
        debilidades.append("Liquidez ajustada: current ratio bajo.")

    if ratio_apalancamiento <= 3:
        fortalezas.append("Apalancamiento razonable.")
    else:
        debilidades.append("Apalancamiento elevado.")

    if margen_ebitda > 0.10:
        fortalezas.append("Margen operativo saludable.")
    else:
        debilidades.append("Margen operativo reducido.")

    if cobertura_intereses > 3:
        fortalezas.append("Buena cobertura de intereses.")
    else:
        debilidades.append("Cobertura de intereses limitada.")

    if crecimiento_ingresos is not None:
        if crecimiento_ingresos > 0:
            fortalezas.append("Ingresos en crecimiento.")
        else:
            debilidades.append("Ingresos en contracción.")

    return {
        "ratios": {
            "ratio_liquidez": float(ratio_liquidez),
            "ratio_apalancamiento": float(ratio_apalancamiento),
            "margen_ebitda": float(margen_ebitda),
            "cobertura_intereses": float(cobertura_intereses),
            "crecimiento_ingresos_ultimo": float(crecimiento_ingresos) if crecimiento_ingresos is not None else None,
        },
        "fortalezas": fortalezas,
        "debilidades": debilidades,
        "tendencia_margen": tendencia_margen,
        "anos_disponibles": list(df["ano"].astype(int)),
    }
