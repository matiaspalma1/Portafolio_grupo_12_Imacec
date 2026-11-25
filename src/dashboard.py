"""
Generador del Dashboard Ejecutivo de Coyuntura y Proyección del IMACEC.

Reemplaza la capa de Power BI generando una figura compuesta de alta resolución
directamente desde la base de datos relacional SQLite (data/coyuntura.db).

Modelo principal reportado: Árbol de Decisión (CART) con proyección directa
multi-horizonte a 24 meses e intervalos de confianza al 95%, contrastado frente
a SARIMA univariado y al benchmark ingenuo en la ventana out-of-sample (H=12M).

Uso desde la raíz del repositorio:
    python src/dashboard.py
"""
from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor
from sqlalchemy import text
from statsmodels.tsa.statespace.sarimax import SARIMAX

try:
    import config
    from carga_db import obtener_engine
except ImportError:
    from src import config  # type: ignore
    from src.carga_db import obtener_engine  # type: ignore

warnings.filterwarnings("ignore")

FECHA_INICIO = "2010-01-01"
FECHA_FIN = "2026-08-01"
LIMITE_X_MIN = pd.Timestamp(FECHA_INICIO)
LIMITE_X_MAX = pd.Timestamp(FECHA_FIN)
RUTA_SALIDA = config.RAIZ / "outputs" / "dashboard_coyuntura_imacec.png"

ID_OBJETIVO = "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M"
ID_TPM = "F022.TPM.TIN.D001.NO.Z.D"

SERIES_SECTORIALES = [
    "F032.IMC.IND.Z.Z.EP18.03.Z.0.M",
    "F032.IMC.IND.Z.Z.EP18.04.Z.0.M",
    "F032.IMC.IND.Z.Z.EP18.RB.Z.0.M",
    "F032.IMC.IND.Z.Z.EP18.COM.Z.0.M",
    "F032.IMC.IND.Z.Z.EP18.SERV.Z.0.M",
    "F032.IMC.IND.Z.Z.EP18.IMP.Z.0.M",
]

SERIES_MACRO_PORCENTUAL = [
    "F019.PPB.PRE.40.M",
    "F073.TCO.PRE.Z.D",
    "F068.B1.FLU.A1.0.C.N.Z.Z.Z.Z.6.0.M",
    "F068.B1.FLU.A8.0.C.N.Z.Z.Z.Z.6.0.M",
    "F068.B1.FLU.B.0.C.N.Z.Z.Z.Z.6.0.M",
    "F068.B1.FLU.Z.0.M.N.A.Z.Z.Z.6.0.M",
    "F089.TCN.PRE.14.M",
]

SERIES_TASAS_PP = [
    "F049.DES.TAS.INE9.10.M",
    "F089.IPC.V12.14.M",
    ID_TPM,
]


def extraer_datos_dashboard(engine) -> pd.DataFrame:
    """
    Consulta SQLite aplicando filtro temporal oficial (2010-01-01 a 2026-08-01),
    agregación mensual, funciones de ventana (LAG y AVG OVER) y cruce con el catálogo.
    """
    query = text("""
    WITH mensual AS (
        SELECT
            o.id_serie,
            strftime('%Y-%m', o.fecha) AS mes,
            AVG(o.valor) AS valor_mensual
        FROM observaciones AS o
        WHERE o.fecha BETWEEN :inicio AND :fin
        GROUP BY o.id_serie, mes
    ),
    indicadores AS (
        SELECT
            m.id_serie,
            m.mes,
            m.valor_mensual,
            100.0 * (m.valor_mensual / LAG(m.valor_mensual, 12) OVER (
                PARTITION BY m.id_serie ORDER BY m.mes
            ) - 1.0) AS var_12m_pct,
            AVG(m.valor_mensual) OVER (
                PARTITION BY m.id_serie ORDER BY m.mes
                ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
            ) AS pm_12m
        FROM mensual AS m
    )
    SELECT
        i.id_serie,
        s.nombre,
        t.tema,
        s.unidad,
        i.mes || '-01' AS fecha,
        i.valor_mensual,
        i.var_12m_pct,
        i.pm_12m
    FROM indicadores AS i
    JOIN series AS s ON s.id_serie = i.id_serie
    JOIN temas AS t ON t.id_tema = s.id_tema
    ORDER BY i.id_serie, i.mes;
    """)
    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={"inicio": FECHA_INICIO, "fin": FECHA_FIN},
            parse_dates=["fecha"],
        )
    return df


def evaluar_y_proyectar_imacec(df_dash: pd.DataFrame, h_eval: int = 12, h_futuro: int = 24) -> dict:
    """
    Replica exactamente la especificación del modelo principal (Árbol de Decisión CART)
    del cuaderno 02_coyuntura_y_modelos.ipynb:
    - Evaluación expansiva fuera de muestra a H=12 meses sin look-ahead bias.
    - Contraste contra SARIMA(2,0,1)(1,0,0,12) y Benchmark Ingenuo.
    - Proyección directa multi-horizonte a H=24 meses con intervalos al 95% (z=1.96).
    """
    rango_mensual = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="MS")
    df_nivel = df_dash.pivot(index="fecha", columns="id_serie", values="valor_mensual").reindex(rango_mensual)
    df_var12m = df_dash.pivot(index="fecha", columns="id_serie", values="var_12m_pct").reindex(rango_mensual)

    # Transformaciones estacionarias idénticas al notebook
    df_trans = pd.DataFrame(index=rango_mensual)
    df_trans[ID_OBJETIVO] = df_var12m[ID_OBJETIVO]
    for cod in SERIES_SECTORIALES + SERIES_MACRO_PORCENTUAL:
        df_trans[cod] = df_var12m[cod]
    for cod in SERIES_TASAS_PP:
        df_trans[cod] = df_nivel[cod] - df_nivel[cod].shift(12)

    # Construcción de matriz supervisada estrictamente rezagada (k >= 1)
    df_sup = pd.DataFrame(index=rango_mensual)
    df_sup["y"] = df_trans[ID_OBJETIVO]

    cols_ar = []
    for lag in [1, 2, 3, 12]:
        c = f"imacec_lag{lag}"
        df_sup[c] = df_trans[ID_OBJETIVO].shift(lag)
        cols_ar.append(c)

    cols_sec = []
    for cod in SERIES_SECTORIALES:
        for lag in [1, 2]:
            c = f"{cod}_lag{lag}"
            df_sup[c] = df_trans[cod].shift(lag)
            cols_sec.append(c)

    cols_mac = []
    for cod in SERIES_MACRO_PORCENTUAL + SERIES_TASAS_PP:
        for lag in [1, 2, 3]:
            c = f"{cod}_lag{lag}"
            df_sup[c] = df_trans[cod].shift(lag)
            cols_mac.append(c)

    X_all_cols = cols_ar + cols_sec + cols_mac
    df_modelo = df_sup.dropna().copy()
    test_idx = df_modelo.index[-h_eval:]

    preds_dt = pd.Series(index=test_idx, dtype=float)
    preds_sarima = pd.Series(index=test_idx, dtype=float)
    bench_oos = df_modelo.loc[test_idx, "imacec_lag1"].copy()

    # 1. Validación expansiva 1-paso-adelante fuera de muestra (cero look-ahead bias)
    for fecha_t in test_idx:
        hist_df = df_modelo.loc[:fecha_t].iloc[:-1]
        y_tr = hist_df["y"]

        # Modelo principal: Árbol de Decisión (CART)
        dt = DecisionTreeRegressor(max_depth=3, min_samples_leaf=8, random_state=42)
        dt.fit(hist_df[X_all_cols], y_tr)
        preds_dt.loc[fecha_t] = float(dt.predict(df_modelo.loc[[fecha_t], X_all_cols])[0])

        # Modelo de contraste univariado: SARIMA(2,0,1)(1,0,0,12)
        mod_sar = SARIMAX(y_tr, order=(2, 0, 1), seasonal_order=(1, 0, 0, 12)).fit(disp=False)
        preds_sarima.loc[fecha_t] = float(mod_sar.forecast(1).iloc[0])

    # 2. Métricas de evaluación fuera de muestra
    y_real = df_modelo.loc[test_idx, "y"]
    mse_bench = float(np.mean((y_real - bench_oos) ** 2))

    rmse_dt = float(np.sqrt(np.mean((y_real - preds_dt) ** 2)))
    mae_dt = float(np.mean(np.abs(y_real - preds_dt)))
    r2_oos_dt = float(1.0 - np.mean((y_real - preds_dt) ** 2) / mse_bench)

    rmse_sar = float(np.sqrt(np.mean((y_real - preds_sarima) ** 2)))
    rmse_bench = float(np.sqrt(mse_bench))

    # 3. Proyección principal a 24 meses (Árbol de Decisión directo multi-horizonte, IC 95%)
    ultima_obs_fecha = df_modelo.index.max()
    fechas_futuras = pd.date_range(ultima_obs_fecha + pd.offsets.MonthBegin(1), periods=h_futuro, freq="MS")
    X_actual = df_modelo.loc[[ultima_obs_fecha], X_all_cols]

    fc_media, fc_inf, fc_sup = [], [], []
    for h in range(1, h_futuro + 1):
        y_target_h = df_modelo["y"].shift(-h)
        valid_h = y_target_h.notna()

        X_tr_h = df_modelo.loc[valid_h, X_all_cols]
        y_tr_h = y_target_h.loc[valid_h]

        mod_h = DecisionTreeRegressor(max_depth=3, min_samples_leaf=8, random_state=42)
        mod_h.fit(X_tr_h, y_tr_h)

        pred_h = float(mod_h.predict(X_actual)[0])
        residuos_h = y_tr_h - mod_h.predict(X_tr_h)
        se_h = float(np.std(residuos_h, ddof=1))

        fc_media.append(pred_h)
        fc_inf.append(pred_h - 1.96 * se_h)
        fc_sup.append(pred_h + 1.96 * se_h)

    return {
        "y": df_trans[ID_OBJETIVO].dropna(),
        "test": y_real,
        "preds_dt": preds_dt,
        "preds_sarima": preds_sarima,
        "bench_oos": bench_oos,
        "fc_media": pd.Series(fc_media, index=fechas_futuras),
        "fc_inf": pd.Series(fc_inf, index=fechas_futuras),
        "fc_sup": pd.Series(fc_sup, index=fechas_futuras),
        "metricas": {
            "rmse_dt": rmse_dt,
            "mae_dt": mae_dt,
            "r2_oos_dt": r2_oos_dt,
            "rmse_sar": rmse_sar,
            "rmse_bench": rmse_bench,
        },
    }


def construir_dashboard(df: pd.DataFrame, res_fc: dict, ruta_salida: Path = RUTA_SALIDA) -> None:
    """Construye y exporta el dashboard ejecutivo de 4 paneles en alta resolución."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    rango_mensual = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="MS")

    imacec = df[df["id_serie"] == ID_OBJETIVO].set_index("fecha").reindex(rango_mensual)
    cobre = df[df["id_serie"] == "F019.PPB.PRE.40.M"].set_index("fecha").reindex(rango_mensual)
    comercio = df[df["id_serie"] == "F032.IMC.IND.Z.Z.EP18.COM.Z.0.M"].set_index("fecha").reindex(rango_mensual)
    tpm = df[df["id_serie"] == ID_TPM].set_index("fecha").reindex(rango_mensual)

    ultimo_mes = LIMITE_X_MAX.strftime("%Y-%m")
    ultimo_nivel = imacec["valor_mensual"].loc[LIMITE_X_MAX]
    ultima_var = imacec["var_12m_pct"].loc[LIMITE_X_MAX]
    media_hist_var = imacec["var_12m_pct"].dropna().mean()

    fig, axes = plt.subplots(2, 2, figsize=(16.5, 9.8))
    fig.patch.set_facecolor("white")

    fig.suptitle(
        "MONITOR DE COYUNTURA MACROECONÓMICA Y PROYECCIÓN DEL IMACEC — CHILE",
        fontsize=15,
        fontweight="bold",
        color="#1b365d",
        y=0.97,
    )
    fig.text(
        0.5,
        0.935,
        f"Fuente: Banco Central de Chile (API SieteRestWS -> SQLite) | Período: {FECHA_INICIO} a {FECHA_FIN} | Modelo Principal: Árbol de Decisión (24M, IC 95%) | Grupo 12",
        ha="center",
        fontsize=9.8,
        color="#4a5568",
    )

    # -------------------------------------------------------------------------
    # PANEL 1: Serie principal en nivel + Promedio móvil 12M (2010-01 a 2026-08)
    # -------------------------------------------------------------------------
    ax1 = axes[0, 0]
    ax1.plot(imacec.index, imacec["valor_mensual"], color="#1f4e78", lw=1.7, label="IMACEC (Índice 2018=100)")
    ax1.plot(imacec.index, imacec["pm_12m"], color="#d95f02", lw=1.7, linestyle="--", label="Promedio móvil 12M")
    ax1.scatter(LIMITE_X_MAX, ultimo_nivel, color="#c00000", s=60, zorder=5)
    ax1.annotate(
        f"Último ({ultimo_mes}): {ultimo_nivel:.1f}",
        xy=(LIMITE_X_MAX, ultimo_nivel),
        xytext=(-125, -22),
        textcoords="offset points",
        fontsize=9.5,
        fontweight="bold",
        color="#c00000",
        arrowprops=dict(arrowstyle="->", color="#c00000", lw=1),
    )
    ax1.set_xlim(LIMITE_X_MIN, LIMITE_X_MAX)
    ax1.xaxis.set_major_locator(mdates.YearLocator(2))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.set_title("1. Trayectoria Histórica del IMACEC y Tendencia (2010-01 a 2026-08)", fontsize=11, fontweight="bold", color="#1b365d")
    ax1.set_ylabel("Índice 2018 = 100")
    ax1.legend(loc="upper left", frameon=True)

    # -------------------------------------------------------------------------
    # PANEL 2: Indicador derivado — Variación Interanual (%) (2010-01 a 2026-08)
    # -------------------------------------------------------------------------
    ax2 = axes[0, 1]
    var_s = imacec["var_12m_pct"].dropna()
    colores_barras = ["#2b6cb0" if v >= 0 else "#c53030" for v in var_s]
    ax2.bar(var_s.index, var_s, width=22, color=colores_barras, alpha=0.85, label="Var. Interanual (%)")
    ax2.axhline(0, color="black", lw=0.9)
    ax2.axhline(media_hist_var, color="#2f855a", linestyle="--", lw=1.4, label=f"Promedio histórico ({media_hist_var:.1f}%)")
    ax2.scatter(LIMITE_X_MAX, ultima_var, color="#c00000", s=60, zorder=5)
    ax2.annotate(
        f"{ultimo_mes}: {ultima_var:+.1f}%",
        xy=(LIMITE_X_MAX, ultima_var),
        xytext=(-85, 16 if ultima_var >= 0 else -22),
        textcoords="offset points",
        fontsize=9.5,
        fontweight="bold",
        color="#c00000",
    )
    ax2.set_xlim(LIMITE_X_MIN, LIMITE_X_MAX)
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.set_title("2. Dinámica Interanual del IMACEC (Var. % 12 Meses)", fontsize=11, fontweight="bold", color="#1b365d")
    ax2.set_ylabel("Variación % 12M")
    ax2.legend(loc="upper left", frameon=True)

    # -------------------------------------------------------------------------
    # PANEL 3: Drivers Sectoriales, Externos y TPM (2010-01 a 2026-08)
    # -------------------------------------------------------------------------
    ax3 = axes[1, 0]
    ax3.plot(comercio.index, comercio["var_12m_pct"], color="#2b6cb0", lw=1.5, label="Sectorial: IMACEC Comercio (Var. % 12M)")
    ax3.plot(cobre.index, cobre["var_12m_pct"], color="#dd6b20", lw=1.5, alpha=0.85, label="Externo: Precio Cobre (Var. % 12M)")
    ax3.axhline(0, color="black", lw=0.8, linestyle=":")

    if not tpm.dropna(how="all").empty:
        ax3_b = ax3.twinx()
        ax3_b.plot(tpm.index, tpm["valor_mensual"], color="#718096", lw=1.4, linestyle="--", label="TPM (%) [eje der.]")
        ax3_b.set_ylabel("TPM (%)", color="#718096")
        ax3_b.grid(False)
        lines_1, labels_1 = ax3.get_legend_handles_labels()
        lines_2, labels_2 = ax3_b.get_legend_handles_labels()
        ax3.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left", fontsize=8.5, frameon=True)
    else:
        ax3.legend(loc="upper left", fontsize=9, frameon=True)

    ax3.set_xlim(LIMITE_X_MIN, LIMITE_X_MAX)
    ax3.xaxis.set_major_locator(mdates.YearLocator(2))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.set_title("3. Indicadores Sectoriales, Externos y TPM (2010-01 a 2026-08)", fontsize=11, fontweight="bold", color="#1b365d")
    ax3.set_ylabel("Variación % 12M")

    # -------------------------------------------------------------------------
    # PANEL 4: Evaluación Out-of-Sample + Proyección Principal Árbol Decisión (24M)
    # -------------------------------------------------------------------------
    ax4 = axes[1, 1]
    y_hist = res_fc["y"].iloc[-36:]
    ax4.plot(y_hist.index, y_hist, color="black", lw=2, label="Observado (Var. % 12M)")
    ax4.plot(res_fc["preds_dt"].index, res_fc["preds_dt"], "--o", color="#1f4e78", ms=3.5, label="Árbol Decisión (Eval. OOS 12M)")
    ax4.plot(res_fc["preds_sarima"].index, res_fc["preds_sarima"], "--^", color="#dd6b20", ms=3.5, alpha=0.8, label="SARIMA (Contraste OOS)")
    ax4.plot(res_fc["bench_oos"].index, res_fc["bench_oos"], ":s", color="#718096", ms=3.5, label="Benchmark Ingenuo")

    fc_m = res_fc["fc_media"]
    ax4.plot(fc_m.index, fc_m, "-D", color="#2f855a", ms=3.5, lw=1.9, label="Proyección Principal: Árbol Decisión (24M)")
    ax4.fill_between(fc_m.index, res_fc["fc_inf"], res_fc["fc_sup"], color="#2f855a", alpha=0.18, label="IC 95%")

    m = res_fc["metricas"]
    texto_metricas = (
        f"Evaluación Out-of-Sample (H=12M)\n"
        f"• Árbol Decisión (Principal): RMSE={m['rmse_dt']:.2f} | MAE={m['mae_dt']:.2f}\n"
        f"• SARIMA: RMSE={m['rmse_sar']:.2f} | Bench: RMSE={m['rmse_bench']:.2f}\n"
        f"• R²_oos (Árbol vs Bench): {m['r2_oos_dt']:+.3f}"
    )
    ax4.text(
        0.02,
        0.04,
        texto_metricas,
        transform=ax4.transAxes,
        fontsize=8.2,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f7fafc", edgecolor="#cbd5e0"),
    )

    ax4.axhline(0, color="black", lw=0.8)
    ax4.set_title("4. Evaluación Fuera de Muestra y Proyección Principal (24 Meses)", fontsize=11, fontweight="bold", color="#1b365d")
    ax4.set_ylabel("Variación % 12M")
    ax4.xaxis.set_major_locator(mdates.YearLocator(1))
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax4.legend(loc="upper left", fontsize=7.8, frameon=True, ncol=2)

    plt.tight_layout(rect=[0, 0.01, 1, 0.92])
    plt.savefig(ruta_salida, dpi=300)
    plt.close()
    print(f"[OK] Dashboard generado exitosamente en: {ruta_salida}")


def main() -> None:
    engine = obtener_engine()
    df_dash = extraer_datos_dashboard(engine)
    resultados_fc = evaluar_y_proyectar_imacec(df_dash, h_eval=12, h_futuro=24)
    construir_dashboard(df_dash, resultados_fc)


if __name__ == "__main__":
    main()