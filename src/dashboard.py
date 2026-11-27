"""
Generador del Dashboard Ejecutivo de Coyuntura y Proyección del IMACEC.

Reemplaza la capa de Power BI generando una lámina compuesta de alta resolución (300 DPI)
conectada directamente a la base de datos relacional SQLite (data/coyuntura.db).

Componentes visuales generados:
1. Semáforo Macroeconómico (4 tarjetas KPI): Actividad (IMACEC), Impulso Externo (Cobre),
   Política Monetaria (TPM) y Proyección Central AR(10) a 12 meses.
2. Panel 1: Trayectoria histórica del IMACEC en nivel y promedio móvil de 12 meses.
3. Panel 2: Dinámica interanual del IMACEC (Var. % 12M) frente a su promedio histórico.
4. Panel 3: Drivers sectoriales (Comercio), externos (Precio del Cobre) y tasa rector (TPM).
5. Panel 4: Evaluación multi-horizonte fuera de muestra (K=24 cortes) y proyección a 24M
   con modelo ganador AR(10) e intervalos de confianza al 95% calibrados OOS.

Uso desde la raíz del repositorio:
    python src/dashboard.py
    python src/dashboard.py --salida outputs/mi_dashboard.png
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from sqlalchemy import text
from sqlalchemy.engine import Engine
from statsmodels.tsa.arima.model import ARIMA

try:
    import config
    from carga_db import obtener_engine
except ImportError:
    from src import config  # type: ignore
    from src.carga_db import obtener_engine  # type: ignore

warnings.filterwarnings("ignore")

# Parámetros centralizados desde config.py (con respaldo por compatibilidad)
FECHA_INICIO: str = getattr(config, "FECHA_INICIO", "2010-01-01")
FECHA_FIN: str = getattr(config, "FECHA_FIN", "2026-08-01")
FECHA_FIN_TRAIN: str = getattr(config, "FECHA_FIN_TRAIN", "2022-08-01")

LIMITE_X_MIN = pd.Timestamp(FECHA_INICIO)
LIMITE_X_MAX = pd.Timestamp(FECHA_FIN)

RUTA_OUTPUTS: Path = getattr(config, "RUTA_OUTPUTS", config.RAIZ / "outputs")
RUTA_SALIDA_DEFAULT: Path = RUTA_OUTPUTS / "dashboard_coyuntura_imacec.png"

ID_OBJETIVO: str = getattr(config, "ID_OBJETIVO", "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M")
ID_TPM: str = getattr(config, "ID_TPM", "F022.TPM.TIN.D001.NO.Z.D")
ID_COMERCIO: str = "F032.IMC.IND.Z.Z.EP18.COM.Z.0.M"
ID_COBRE: str = "F019.PPB.PRE.40.M"


def extraer_datos_dashboard(engine: Engine) -> pd.DataFrame:
    """
    Extrae y transforma las series desde SQLite mediante consulta SQL analítica:
    - Filtra la ventana oficial del estudio (2010-01-01 a 2026-08-01).
    - Homologa frecuencias diarias a mensuales mediante GROUP BY y AVG().
    - Calcula variaciones interanuales (LAG 12) y promedios móviles (AVG OVER 12M).
    - Cruza metadatos y categorías temáticas mediante JOIN con `series` y `temas`.
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

    if df.empty:
        raise RuntimeError(
            f"La base de datos ({config.RUTA_DB}) no contiene observaciones en el rango "
            f"{FECHA_INICIO} a {FECHA_FIN}.\n"
            "Ejecuta primero el pipeline de ingesta con:\n"
            "    python src/carga_db.py        (con credenciales en .env)\n"
            "    python src/carga_db.py --demo (con datos sintéticos de prueba)"
        )
    return df


def evaluar_y_proyectar_imacec(
    df_dash: pd.DataFrame,
    n_cortes: int = 24,
    h_futuro: int = 24,
) -> dict:
    """
    Replica la evaluación multi-horizonte y proyección del Bloque 6 del notebook:
    - Especificación del orden p* mediante AIC exclusivamente en entrenamiento (hasta 2022-08-01).
    - Backtesting sobre K=24 cortes históricos sin sesgo de anticipación (look-ahead bias).
    - Bandas al 95% calibradas con desviación estándar de errores fuera de muestra sigma_oos(h).
    """
    rango_mensual = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="MS")
    df_var12m = df_dash.pivot(index="fecha", columns="id_serie", values="var_12m_pct").reindex(rango_mensual)
    y_imacec = df_var12m[ID_OBJETIVO].dropna().asfreq("MS")

    # 1. Selección del orden óptimo p* por AIC en muestra efectiva de entrenamiento
    y_train_aic = y_imacec.loc["2011-02-01":FECHA_FIN_TRAIN]
    aic_por_p = {
        p: float(ARIMA(y_train_aic, order=(p, 0, 0)).fit().aic)
        for p in range(1, 13)
    }
    p_optimo = min(aic_por_p, key=aic_por_p.get)

    fecha_corte_final = y_imacec.index.max()
    fecha_ultimo_corte_eval = fecha_corte_final - pd.DateOffset(months=h_futuro)
    cortes_eval = pd.date_range(end=fecha_ultimo_corte_eval, periods=n_cortes, freq="MS")

    errores_ar = np.zeros((n_cortes, h_futuro))
    errores_ingenuo = np.zeros((n_cortes, h_futuro))
    preds_h1_oos: list[float] = []
    bench_h1_oos: list[float] = []
    fechas_h1_oos: list[pd.Timestamp] = []

    # 2. Backtesting multi-horizonte fuera de muestra (cero look-ahead bias)
    for i, fecha_corte in enumerate(cortes_eval):
        y_tr = y_imacec.loc[:fecha_corte]
        y_corte_ingenuo = float(y_tr.iloc[-1])

        mod_ar_corte = ARIMA(y_tr, order=(p_optimo, 0, 0)).fit()
        fc_corte = mod_ar_corte.forecast(h_futuro).values

        fechas_obj = pd.date_range(fecha_corte + pd.DateOffset(months=1), periods=h_futuro, freq="MS")
        y_real_vec = y_imacec.loc[fechas_obj].values

        errores_ar[i, :] = y_real_vec - fc_corte
        errores_ingenuo[i, :] = y_real_vec - y_corte_ingenuo

        preds_h1_oos.append(float(fc_corte[0]))
        bench_h1_oos.append(y_corte_ingenuo)
        fechas_h1_oos.append(fechas_obj[0])

    rmse_ar_h = np.sqrt(np.mean(errores_ar ** 2, axis=0))
    rmse_ing_h = np.sqrt(np.mean(errores_ingenuo ** 2, axis=0))

    # 3. Verificación de cobertura empírica fuera de muestra (leave-one-cutoff-out)
    dentro_banda = np.zeros((n_cortes, h_futuro), dtype=bool)
    for i in range(n_cortes):
        mask_otros = np.arange(n_cortes) != i
        sigma_loo_h = np.std(errores_ar[mask_otros, :], axis=0, ddof=1)
        dentro_banda[i, :] = np.abs(errores_ar[i, :]) <= (1.96 * sigma_loo_h)

    cobertura_pct = float(np.mean(dentro_banda) * 100.0)

    # 4. Proyección final desde el corte oficial hacia adelante (h_futuro meses)
    mod_ar_final = ARIMA(y_imacec, order=(p_optimo, 0, 0)).fit()
    fc_media_vals = mod_ar_final.forecast(h_futuro).values
    sigma_oos_h = np.std(errores_ar, axis=0, ddof=1)

    fechas_futuras = pd.date_range(fecha_corte_final + pd.offsets.MonthBegin(1), periods=h_futuro, freq="MS")

    return {
        "p_optimo": p_optimo,
        "y": y_imacec,
        "preds_h1": pd.Series(preds_h1_oos, index=fechas_h1_oos),
        "bench_h1": pd.Series(bench_h1_oos, index=fechas_h1_oos),
        "fc_media": pd.Series(fc_media_vals, index=fechas_futuras),
        "fc_inf": pd.Series(fc_media_vals - 1.96 * sigma_oos_h, index=fechas_futuras),
        "fc_sup": pd.Series(fc_media_vals + 1.96 * sigma_oos_h, index=fechas_futuras),
        "metricas": {
            "rmse_h1": float(rmse_ar_h[0]),
            "rmse_h6": float(rmse_ar_h[min(5, h_futuro - 1)]),
            "rmse_h12": float(rmse_ar_h[min(11, h_futuro - 1)]),
            "rmse_h24": float(rmse_ar_h[-1]),
            "ing_h1": float(rmse_ing_h[0]),
            "ing_h12": float(rmse_ing_h[min(11, h_futuro - 1)]),
            "ing_h24": float(rmse_ing_h[-1]),
            "cobertura_pct": cobertura_pct,
        },
    }


def _dibujar_tarjeta_semaforo(
    ax: plt.Axes,
    titulo: str,
    valor_principal: str,
    subtitulo: str,
    estado_texto: str,
    color_semaforo: str,
    color_fondo: str,
) -> None:
    """Dibuja una tarjeta KPI ejecutiva con luz de semáforo (Verde / Ámbar / Rojo)."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    tarjeta = FancyBboxPatch(
        (0.01, 0.04),
        0.98,
        0.92,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor=color_fondo,
        edgecolor=color_semaforo,
        linewidth=1.8,
    )
    ax.add_patch(tarjeta)

    ax.scatter([0.08], [0.78], s=140, color=color_semaforo, zorder=4, edgecolors="white", linewidth=1.2)
    ax.text(
        0.14,
        0.78,
        titulo,
        fontsize=9.2,
        fontweight="bold",
        color="#1b365d",
        va="center",
        ha="left",
    )
    ax.text(
        0.95,
        0.78,
        estado_texto,
        fontsize=7.8,
        fontweight="bold",
        color="white",
        va="center",
        ha="right",
        bbox=dict(boxstyle="round,pad=0.22", facecolor=color_semaforo, edgecolor="none"),
    )
    ax.text(
        0.06,
        0.43,
        valor_principal,
        fontsize=15.5,
        fontweight="bold",
        color="#1a202c",
        va="center",
        ha="left",
    )
    ax.text(
        0.06,
        0.15,
        subtitulo,
        fontsize=8.1,
        color="#4a5568",
        va="center",
        ha="left",
    )


def construir_dashboard(
    df: pd.DataFrame,
    res_fc: dict,
    ruta_salida: Path = RUTA_SALIDA_DEFAULT,
) -> None:
    """Construye y exporta el dashboard ejecutivo con semáforo y 4 paneles."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    rango_mensual = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="MS")
    p_opt = res_fc["p_optimo"]

    imacec = df[df["id_serie"] == ID_OBJETIVO].set_index("fecha").reindex(rango_mensual)
    cobre = df[df["id_serie"] == ID_COBRE].set_index("fecha").reindex(rango_mensual)
    comercio = df[df["id_serie"] == ID_COMERCIO].set_index("fecha").reindex(rango_mensual)
    tpm = df[df["id_serie"] == ID_TPM].set_index("fecha").reindex(rango_mensual)

    serie_nivel_valida = imacec["valor_mensual"].dropna()
    ts_ultimo_nivel = serie_nivel_valida.index.max()
    ultimo_nivel = float(serie_nivel_valida.iloc[-1])

    var_s = imacec["var_12m_pct"].dropna()
    ts_ultima_var = var_s.index.max()
    ultima_var = float(var_s.iloc[-1])
    media_hist_var = float(var_s.mean())

    # Cálculo de estados para el Semáforo Macroeconómico (4 tarjetas)
    # 1. Actividad (IMACEC Var. 12M)
    if ultima_var >= media_hist_var:
        sem_act = ("EXPANSIÓN", "#2f855a", "#f0fff4")
    elif ultima_var >= 0.0:
        sem_act = ("MODERADO", "#d69e2e", "#fffff0")
    else:
        sem_act = ("CONTRACCIÓN", "#c53030", "#fff5f5")

    # 2. Impulso Externo (Precio del Cobre Var. 12M)
    cobre_var_s = cobre["var_12m_pct"].dropna()
    ultima_var_cobre = float(cobre_var_s.iloc[-1])
    ts_cobre = cobre_var_s.index.max().strftime("%Y-%m")
    if ultima_var_cobre > 0.0:
        sem_cob = ("FAVORABLE", "#2f855a", "#f0fff4")
    elif ultima_var_cobre >= -5.0:
        sem_cob = ("NEUTRAL", "#d69e2e", "#fffff0")
    else:
        sem_cob = ("ADVERSO", "#c53030", "#fff5f5")

    # 3. Postura Monetaria (TPM nivel y variación 12M en pp)
    tpm_s = tpm["valor_mensual"].dropna()
    ultima_tpm = float(tpm_s.iloc[-1])
    ts_tpm = tpm_s.index.max().strftime("%Y-%m")
    delta_tpm_12m = float(tpm_s.iloc[-1] - tpm_s.iloc[-13]) if len(tpm_s) >= 13 else 0.0
    if delta_tpm_12m < -0.25:
        sem_tpm = ("EXPANSIVA", "#2f855a", "#f0fff4")
    elif delta_tpm_12m <= 0.25:
        sem_tpm = ("NEUTRAL", "#d69e2e", "#fffff0")
    else:
        sem_tpm = ("CONTRACTIVA", "#c53030", "#fff5f5")

    # 4. Proyección Central AR(p*) a 12 meses (h=12)
    idx_12m = min(11, len(res_fc["fc_media"]) - 1)
    fc_12m = float(res_fc["fc_media"].iloc[idx_12m])
    fc_12m_inf = float(res_fc["fc_inf"].iloc[idx_12m])
    fc_12m_sup = float(res_fc["fc_sup"].iloc[idx_12m])
    fecha_fc_12m = res_fc["fc_media"].index[idx_12m].strftime("%Y-%m")
    if fc_12m >= media_hist_var:
        sem_fc = ("SOBRE TENDENCIA", "#2f855a", "#f0fff4")
    elif fc_12m >= 0.0:
        sem_fc = ("CONVERGENCIA", "#d69e2e", "#fffff0")
    else:
        sem_fc = ("RIESGO BAJA", "#c53030", "#fff5f5")

    # Grilla compuesta: Fila 0 (Semáforo 4 tarjetas) + Filas 1 y 2 (4 gráficos)
    fig = plt.figure(figsize=(16.5, 11.4))
    fig.patch.set_facecolor("white")

    fig.suptitle(
        "MONITOR DE COYUNTURA MACROECONÓMICA Y PROYECCIÓN DEL IMACEC — CHILE",
        fontsize=15.5,
        fontweight="bold",
        color="#1b365d",
        y=0.975,
    )
    fig.text(
        0.5,
        0.945,
        f"Fuente: Banco Central de Chile (API SieteRestWS -> SQLite) | Período: {FECHA_INICIO} a {FECHA_FIN} | Modelo Principal: AR({p_opt}) [AIC Train] ({len(res_fc['fc_media'])}M, IC 95% OOS) | Grupo 12",
        ha="center",
        fontsize=9.6,
        color="#4a5568",
    )

    gs = fig.add_gridspec(
        3,
        4,
        height_ratios=[0.62, 1.55, 1.55],
        hspace=0.38,
        wspace=0.25,
        top=0.915,
        bottom=0.055,
        left=0.055,
        right=0.955,
    )

    # -------------------------------------------------------------------------
    # FILA 0: SEMÁFORO MACROECONÓMICO DE COYUNTURA (4 TARJETAS KPI)
    # -------------------------------------------------------------------------
    _dibujar_tarjeta_semaforo(
        fig.add_subplot(gs[0, 0]),
        titulo="ACTIVIDAD (IMACEC)",
        valor_principal=f"{ultima_var:+.2f}%",
        subtitulo=f"Corte {ts_ultima_var.strftime('%Y-%m')} | Prom. hist.: {media_hist_var:+.2f}%",
        estado_texto=sem_act[0],
        color_semaforo=sem_act[1],
        color_fondo=sem_act[2],
    )
    _dibujar_tarjeta_semaforo(
        fig.add_subplot(gs[0, 1]),
        titulo="IMPULSO EXTERNO (COBRE)",
        valor_principal=f"{ultima_var_cobre:+.2f}%",
        subtitulo=f"Var. 12M a {ts_cobre} | Términos intercambio",
        estado_texto=sem_cob[0],
        color_semaforo=sem_cob[1],
        color_fondo=sem_cob[2],
    )
    _dibujar_tarjeta_semaforo(
        fig.add_subplot(gs[0, 2]),
        titulo="POLÍTICA MONETARIA (TPM)",
        valor_principal=f"{ultima_tpm:.2f}%",
        subtitulo=f"Nivel a {ts_tpm} | Var. 12M: {delta_tpm_12m:+.2f} pp",
        estado_texto=sem_tpm[0],
        color_semaforo=sem_tpm[1],
        color_fondo=sem_tpm[2],
    )
    _dibujar_tarjeta_semaforo(
        fig.add_subplot(gs[0, 3]),
        titulo=f"PROYECCIÓN AR({p_opt}) ({idx_12m + 1}M)",
        valor_principal=f"{fc_12m:+.2f}%",
        subtitulo=f"Horizonte {fecha_fc_12m} | IC 95%: [{fc_12m_inf:+.1f}%, {fc_12m_sup:+.1f}%]",
        estado_texto=sem_fc[0],
        color_semaforo=sem_fc[1],
        color_fondo=sem_fc[2],
    )

    # -------------------------------------------------------------------------
    # PANEL 1: Serie principal en nivel + Promedio móvil 12M (2010-01 a 2026-08)
    # -------------------------------------------------------------------------
    ax1 = fig.add_subplot(gs[1, 0:2])
    ax1.plot(imacec.index, imacec["valor_mensual"], color="#1f4e78", lw=1.7, label="IMACEC (Índice 2018=100)")
    ax1.plot(imacec.index, imacec["pm_12m"], color="#d95f02", lw=1.7, linestyle="--", label="Promedio móvil 12M")
    ax1.scatter(ts_ultimo_nivel, ultimo_nivel, color="#c00000", s=60, zorder=5)
    ax1.annotate(
        f"Último ({ts_ultimo_nivel.strftime('%Y-%m')}): {ultimo_nivel:.1f}",
        xy=(ts_ultimo_nivel, ultimo_nivel),
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
    ax2 = fig.add_subplot(gs[1, 2:4])
    colores_barras = ["#2b6cb0" if v >= 0 else "#c53030" for v in var_s]
    ax2.bar(var_s.index, var_s, width=22, color=colores_barras, alpha=0.85, label="Var. Interanual (%)")
    ax2.axhline(0, color="black", lw=0.9)
    ax2.axhline(media_hist_var, color="#2f855a", linestyle="--", lw=1.4, label=f"Promedio histórico ({media_hist_var:.1f}%)")
    ax2.scatter(ts_ultima_var, ultima_var, color="#c00000", s=60, zorder=5)
    ax2.annotate(
        f"{ts_ultima_var.strftime('%Y-%m')}: {ultima_var:+.1f}%",
        xy=(ts_ultima_var, ultima_var),
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
    ax3 = fig.add_subplot(gs[2, 0:2])
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
    # PANEL 4: Backtesting Multi-Horizonte + Proyección Principal AR(p*) (24M)
    # -------------------------------------------------------------------------
    ax4 = fig.add_subplot(gs[2, 2:4])
    y_hist = res_fc["y"].iloc[-48:]
    ax4.plot(y_hist.index, y_hist, color="black", lw=2, label="Observado (Var. % 12M)")
    ax4.plot(res_fc["preds_h1"].index, res_fc["preds_h1"], "--o", color="#1f4e78", ms=3, alpha=0.85, label=f"AR({p_opt}) Eval. OOS (h=1, {len(res_fc['preds_h1'])} cortes)")
    ax4.plot(res_fc["bench_h1"].index, res_fc["bench_h1"], ":s", color="#718096", ms=3, alpha=0.8, label="Benchmark Ingenuo (h=1)")

    fc_m = res_fc["fc_media"]
    m = res_fc["metricas"]
    h_tot = len(fc_m)
    ax4.plot(fc_m.index, fc_m, "-D", color="#2f855a", ms=3.5, lw=1.9, label=f"Proyección Principal: AR({p_opt}) ({h_tot}M)")
    ax4.fill_between(
        fc_m.index,
        res_fc["fc_inf"],
        res_fc["fc_sup"],
        color="#2f855a",
        alpha=0.18,
        label=f"IC 95% OOS (Cob. empírica: {m['cobertura_pct']:.1f}%)",
    )

    texto_metricas = (
        f"RMSE Out-of-Sample Multi-Horizonte (K={len(res_fc['preds_h1'])} cortes)\n"
        f"• h=1M:  AR({p_opt})={m['rmse_h1']:.2f} vs Ingenuo={m['ing_h1']:.2f}\n"
        f"• h=12M: AR({p_opt})={m['rmse_h12']:.2f} vs Ingenuo={m['ing_h12']:.2f}\n"
        f"• h={h_tot}M: AR({p_opt})={m['rmse_h24']:.2f} vs Ingenuo={m['ing_h24']:.2f}"
    )
    ax4.text(
        0.02,
        0.04,
        texto_metricas,
        transform=ax4.transAxes,
        fontsize=8.1,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f7fafc", edgecolor="#cbd5e0"),
    )

    ax4.axhline(0, color="black", lw=0.8)
    ax4.set_title(f"4. Evaluación Multi-Horizonte y Proyección Principal AR({p_opt}) ({h_tot} Meses)", fontsize=11, fontweight="bold", color="#1b365d")
    ax4.set_ylabel("Variación % 12M")
    ax4.xaxis.set_major_locator(mdates.YearLocator(1))
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax4.legend(loc="upper left", fontsize=7.6, frameon=True, ncol=2)

    plt.savefig(ruta_salida, dpi=300)
    plt.close()
    print(f"[OK] Dashboard generado exitosamente en: {ruta_salida}")


def main(
    ruta_salida: Path = RUTA_SALIDA_DEFAULT,
    n_cortes: int = 24,
    h_futuro: int = 24,
) -> None:
    """Orquesta la consulta SQL, evaluación fuera de muestra y exportación gráfica."""
    print("======================================================")
    print(" GENERADOR DE DASHBOARD EJECUTIVO — IMACEC CHILE")
    print("======================================================")

    if not config.RUTA_DB.exists():
        raise FileNotFoundError(
            f"No se encontró la base de datos SQLite en: {config.RUTA_DB}.\n"
            "Ejecuta primero 'python src/carga_db.py' para crear y poblar la base."
        )

    print("[1/3] Extrayendo indicadores y transformaciones desde SQLite...")
    engine = obtener_engine()
    df_dash = extraer_datos_dashboard(engine)

    print(f"[2/3] Ejecutando backtesting OOS ({n_cortes} cortes) y proyección a {h_futuro}M...")
    resultados_fc = evaluar_y_proyectar_imacec(df_dash, n_cortes=n_cortes, h_futuro=h_futuro)

    print("[3/3] Renderizando semáforo macroeconómico y paneles analíticos...")
    construir_dashboard(df_dash, resultados_fc, ruta_salida=ruta_salida)


def _parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera el monitor ejecutivo de coyuntura y proyección del IMACEC."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=RUTA_SALIDA_DEFAULT,
        metavar="RUTA_PNG",
        help=f"Ruta de exportación de la imagen PNG (por defecto: {RUTA_SALIDA_DEFAULT}).",
    )
    parser.add_argument(
        "--cortes",
        type=int,
        default=24,
        metavar="N",
        help="Número de cortes históricos para evaluación OOS (por defecto: 24).",
    )
    parser.add_argument(
        "--horizonte",
        type=int,
        default=24,
        metavar="MESES",
        help="Horizonte de proyección futura en meses (por defecto: 24).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = _parsear_argumentos()
        main(ruta_salida=args.salida, n_cortes=args.cortes, h_futuro=args.horizonte)
    except Exception as exc:
        print(f"\n[ERROR] Falló la generación del dashboard: {exc}", file=sys.stderr)
        sys.exit(1)