"""
Generador del Dashboard Ejecutivo de Coyuntura y Proyección del IMACEC.

Reemplaza la capa de Power BI generando una figura compuesta de alta resolución
directamente desde la base de datos relacional SQLite (data/coyuntura.db),
fijando el período oficial 2010-01-01 a 2026-08-01 y un horizonte de proyección de 24 meses.

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


def evaluar_y_proyectar_imacec(serie_var_12m: pd.Series, h_eval: int = 12, h_futuro: int = 24) -> dict:
    """
    Evalúa fuera de muestra (sin look-ahead bias) la variación interanual del Imacec
    frente al benchmark ingenuo y genera la proyección a 24 meses con intervalos al 95%.
    """
    y = serie_var_12m.dropna().asfreq("MS")
    train, test = y.iloc[:-h_eval], y.iloc[-h_eval:]

    # 1. Validación recursiva 1-paso-adelante fuera de muestra
    preds_oos = []
    historia = train.copy()
    for fecha in test.index:
        mod = SARIMAX(historia, order=(2, 0, 1), seasonal_order=(1, 0, 0, 12))
        res = mod.fit(disp=False)
        preds_oos.append(res.forecast(1).iloc[0])
        historia = pd.concat([historia, test.loc[[fecha]]])

    preds_oos = pd.Series(preds_oos, index=test.index)
    bench_oos = y.shift(1).loc[test.index]

    # 2. Métricas de evaluación fuera de muestra
    rmse_mod = float(np.sqrt(np.mean((test - preds_oos) ** 2)))
    mae_mod = float(np.mean(np.abs(test - preds_oos)))
    rmse_bench = float(np.sqrt(np.mean((test - bench_oos) ** 2)))
    mae_bench = float(np.mean(np.abs(test - bench_oos)))
    r2_oos = float(1.0 - np.sum((test - preds_oos) ** 2) / np.sum((test - bench_oos) ** 2))

    # 3. Proyección hacia adelante a 24 meses usando toda la muestra disponible
    mod_full = SARIMAX(y, order=(2, 0, 1), seasonal_order=(1, 0, 0, 12)).fit(disp=False)
    fc_obj = mod_full.get_forecast(steps=h_futuro)
    fc_media = fc_obj.predicted_mean
    fc_ic = fc_obj.conf_int(alpha=0.05)

    return {
        "y": y,
        "test": test,
        "preds_oos": preds_oos,
        "bench_oos": bench_oos,
        "fc_media": fc_media,
        "fc_ic": fc_ic,
        "metricas": {
            "rmse_mod": rmse_mod,
            "mae_mod": mae_mod,
            "rmse_bench": rmse_bench,
            "mae_bench": mae_bench,
            "r2_oos": r2_oos,
        },
    }


def construir_dashboard(df: pd.DataFrame, res_fc: dict, ruta_salida: Path = RUTA_SALIDA) -> None:
    """Construye y exporta el dashboard ejecutivo de 4 paneles en alta resolución."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    rango_mensual = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="MS")

    imacec = df[df["id_serie"] == "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M"].set_index("fecha").reindex(rango_mensual)
    cobre = df[df["id_serie"] == "F019.PPB.PRE.40.M"].set_index("fecha").reindex(rango_mensual)
    comercio = df[df["id_serie"] == "F032.IMC.IND.Z.Z.EP18.COM.Z.0.M"].set_index("fecha").reindex(rango_mensual)
    tpm = df[df["id_serie"] == "F022.TPM.TIN.D001.NO.Z.M"].set_index("fecha").reindex(rango_mensual)

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
        f"Fuente: Banco Central de Chile (API SieteRestWS -> SQLite) | Período: {FECHA_INICIO} a {FECHA_FIN} | Proyección: 24 meses | Grupo 12",
        ha="center",
        fontsize=10,
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
    # PANEL 4: Evaluación Out-of-Sample + Proyección a 24 Meses (IC 95%)
    # -------------------------------------------------------------------------
    ax4 = axes[1, 1]
    y_hist = res_fc["y"].iloc[-36:]
    ax4.plot(y_hist.index, y_hist, color="black", lw=2, label="Observado (Var. % 12M)")
    ax4.plot(res_fc["preds_oos"].index, res_fc["preds_oos"], "--o", color="#1f77b4", ms=3.5, label="Modelo (Eval. Out-of-Sample 12M)")
    ax4.plot(res_fc["bench_oos"].index, res_fc["bench_oos"], ":s", color="#ff7f0e", ms=3.5, label="Benchmark Ingenuo")

    fc_m = res_fc["fc_media"]
    fc_ic = res_fc["fc_ic"]
    ax4.plot(fc_m.index, fc_m, "-D", color="#2f855a", ms=3.5, lw=1.8, label="Proyección 24M (2026-09 a 2028-08)")
    ax4.fill_between(fc_ic.index, fc_ic.iloc[:, 0], fc_ic.iloc[:, 1], color="#2f855a", alpha=0.18, label="IC 95%")

    m = res_fc["metricas"]
    texto_metricas = (
        f"Evaluación Out-of-Sample (H=12M)\n"
        f"• RMSE Modelo: {m['rmse_mod']:.2f} vs Bench: {m['rmse_bench']:.2f}\n"
        f"• MAE Modelo:  {m['mae_mod']:.2f} vs Bench: {m['mae_bench']:.2f}\n"
        f"• R²_oos: {m['r2_oos']:+.3f}"
    )
    ax4.text(
        0.02,
        0.04,
        texto_metricas,
        transform=ax4.transAxes,
        fontsize=8.5,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f7fafc", edgecolor="#cbd5e0"),
    )

    ax4.axhline(0, color="black", lw=0.8)
    ax4.set_title("4. Evaluación Fuera de Muestra y Proyección a 24 Meses", fontsize=11, fontweight="bold", color="#1b365d")
    ax4.set_ylabel("Variación % 12M")
    ax4.xaxis.set_major_locator(mdates.YearLocator(1))
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax4.legend(loc="upper left", fontsize=8, frameon=True)

    plt.tight_layout(rect=[0, 0.01, 1, 0.92])
    plt.savefig(ruta_salida, dpi=300)
    plt.close()
    print(f"[OK] Dashboard generado exitosamente en: {ruta_salida}")


def main() -> None:
    engine = obtener_engine()
    df_dash = extraer_datos_dashboard(engine)
    imacec_var = (
        df_dash[df_dash["id_serie"] == "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M"]
        .set_index("fecha")["var_12m_pct"]
    )
    resultados_fc = evaluar_y_proyectar_imacec(imacec_var, h_eval=12, h_futuro=24)
    construir_dashboard(df_dash, resultados_fc)


if __name__ == "__main__":
    main()