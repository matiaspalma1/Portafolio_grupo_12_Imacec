"""
Generador del Dashboard Ejecutivo de Coyuntura y Proyección del IMACEC.

Reemplaza la capa de Power BI generando una figura compuesta de alta resolución
directamente desde la base de datos relacional SQLite (data/coyuntura.db).

Modelo principal reportado: Árbol de Decisión (CART) directo multi-horizonte (24M),
evaluado fuera de muestra sobre K=24 cortes históricos sin look-ahead bias y con
bandas de confianza al 95% calibradas con errores fuera de muestra.

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
    "F032.IMC.IND.Z.Z.EP18.03.Z.0.M",   # Minería
    "F032.IMC.IND.Z.Z.EP18.04.Z.0.M",   # Industria
    "F032.IMC.IND.Z.Z.EP18.RB.Z.0.M",   # Resto de bienes
    "F032.IMC.IND.Z.Z.EP18.COM.Z.0.M",  # Comercio
    "F032.IMC.IND.Z.Z.EP18.SERV.Z.0.M", # Servicios
    "F032.IMC.IND.Z.Z.EP18.IMP.Z.0.M",  # Impuestos
]

SERIES_MACRO_PORCENTUAL = [
    "F019.PPB.PRE.40.M",                    # Precio cobre
    "F073.TCO.PRE.Z.D",                     # Tipo cambio observado
    "F068.B1.FLU.A1.0.C.N.Z.Z.Z.Z.6.0.M",   # Exportaciones cobre
    "F068.B1.FLU.A8.0.C.N.Z.Z.Z.Z.6.0.M",   # Exportaciones litio
    "F068.B1.FLU.B.0.C.N.Z.Z.Z.Z.6.0.M",    # Exportaciones agropecuarias
    "F068.B1.FLU.Z.0.M.N.A.Z.Z.Z.6.0.M",    # Importaciones consumo
    "F089.TCN.PRE.14.M",                    # Expectativa tipo cambio 11m
]

SERIES_TASAS_PP = [
    "F049.DES.TAS.INE9.10.M",   # Tasa desocupación (%)
    "F089.IPC.V12.14.M",        # Expectativa inflación 11m (%)
    ID_TPM,                     # Tasa de Política Monetaria (%)
]


def extraer_datos_dashboard(engine) -> pd.DataFrame:
    """
    Consulta SQLite aplicando filtro temporal oficial (2010-01-01 a 2026-08-01),
    agregación diaria a mensual (GROUP BY), funciones de ventana (LAG y AVG OVER)
    y cruce relacional con catálogo y temas (JOIN).
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


def evaluar_y_proyectar_imacec(df_dash: pd.DataFrame, n_cortes: int = 24, h_futuro: int = 24) -> dict:
    """
    Replica exactamente la evaluación multi-horizonte y proyección del Bloque 6 del notebook:
    - Tratamiento de borde irregular (ragged edge) mediante ffill(limit=1) sin look-ahead bias.
    - Vector de estado Z_t observado hasta el corte t inclusive (sin desfase de 1 mes).
    - Backtesting sobre K=24 cortes históricos (2022-09 a 2024-08) para h=1..24 vs Benchmark Ingenuo.
    - Bandas al 95% calibradas con desviación estándar de errores fuera de muestra sigma_oos(h).
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

    # Propagar máximo 1 mes para series con rezago de publicación en 2026-08-01
    df_trans_ragged = df_trans.ffill(limit=1)

    # Matriz de estado Z_t con información disponible hasta el corte t inclusive
    df_Z = pd.DataFrame(index=rango_mensual)
    cols_Z = []
    for lag in [0, 1, 2, 11]:
        c = f"imacec_t_menos_{lag}"
        df_Z[c] = df_trans_ragged[ID_OBJETIVO].shift(lag)
        cols_Z.append(c)

    for cod in SERIES_SECTORIALES:
        for lag in [0, 1]:
            c = f"{cod}_t_menos_{lag}"
            df_Z[c] = df_trans_ragged[cod].shift(lag)
            cols_Z.append(c)

    for cod in SERIES_MACRO_PORCENTUAL + SERIES_TASAS_PP:
        for lag in [0, 1, 2]:
            c = f"{cod}_t_menos_{lag}"
            df_Z[c] = df_trans_ragged[cod].shift(lag)
            cols_Z.append(c)

    df_Z_limpio = df_Z.dropna().copy()
    y_objetivo_serie = df_trans_ragged[ID_OBJETIVO]
    fecha_corte_final = df_Z_limpio.index.max()

    fecha_ultimo_corte_eval = fecha_corte_final - pd.DateOffset(months=h_futuro)
    cortes_eval = pd.date_range(end=fecha_ultimo_corte_eval, periods=n_cortes, freq="MS")

    errores_cart = np.zeros((n_cortes, h_futuro))
    errores_ingenuo = np.zeros((n_cortes, h_futuro))
    preds_h1_oos = []
    bench_h1_oos = []
    fechas_h1_oos = []

    # 1. Backtesting multi-horizonte fuera de muestra (cero look-ahead bias)
    for i, fecha_corte in enumerate(cortes_eval):
        Z_corte = df_Z_limpio.loc[[fecha_corte], cols_Z]
        y_corte_ingenuo = float(y_objetivo_serie.loc[fecha_corte])

        for h in range(1, h_futuro + 1):
            fecha_objetivo = fecha_corte + pd.DateOffset(months=h)
            y_real_h = float(y_objetivo_serie.loc[fecha_objetivo])

            fechas_s_validas = df_Z_limpio.index[
                (df_Z_limpio.index + pd.DateOffset(months=h)) <= fecha_corte
            ]
            X_tr_h = df_Z_limpio.loc[fechas_s_validas, cols_Z]
            y_tr_h = y_objetivo_serie.loc[fechas_s_validas + pd.DateOffset(months=h)].values

            cart_h = DecisionTreeRegressor(max_depth=3, min_samples_leaf=8, random_state=42)
            cart_h.fit(X_tr_h, y_tr_h)
            pred_cart_h = float(cart_h.predict(Z_corte)[0])

            errores_cart[i, h - 1] = y_real_h - pred_cart_h
            errores_ingenuo[i, h - 1] = y_real_h - y_corte_ingenuo

            if h == 1:
                preds_h1_oos.append(pred_cart_h)
                bench_h1_oos.append(y_corte_ingenuo)
                fechas_h1_oos.append(fecha_objetivo)

    rmse_cart_h = np.sqrt(np.mean(errores_cart ** 2, axis=0))
    rmse_ing_h = np.sqrt(np.mean(errores_ingenuo ** 2, axis=0))

    # 2. Verificación de cobertura empírica fuera de muestra (leave-one-cutoff-out)
    dentro_banda = np.zeros((n_cortes, h_futuro), dtype=bool)
    for i in range(n_cortes):
        mask_otros = np.arange(n_cortes) != i
        sigma_loo_h = np.std(errores_cart[mask_otros, :], axis=0, ddof=1)
        dentro_banda[i, :] = np.abs(errores_cart[i, :]) <= (1.96 * sigma_loo_h)

    cobertura_pct = float(np.mean(dentro_banda) * 100.0)

    # 3. Proyección final desde el corte oficial hacia adelante (24 meses)
    Z_final = df_Z_limpio.loc[[fecha_corte_final], cols_Z]
    fechas_futuras = pd.date_range(fecha_corte_final + pd.offsets.MonthBegin(1), periods=h_futuro, freq="MS")
    sigma_oos_h = np.std(errores_cart, axis=0, ddof=1)

    fc_media, fc_inf, fc_sup = [], [], []
    for h in range(1, h_futuro + 1):
        fechas_s_full = df_Z_limpio.index[
            (df_Z_limpio.index + pd.DateOffset(months=h)) <= fecha_corte_final
        ]
        X_tr_full = df_Z_limpio.loc[fechas_s_full, cols_Z]
        y_tr_full = y_objetivo_serie.loc[fechas_s_full + pd.DateOffset(months=h)].values

        mod_h = DecisionTreeRegressor(max_depth=3, min_samples_leaf=8, random_state=42)
        mod_h.fit(X_tr_full, y_tr_full)

        pred_h = float(mod_h.predict(Z_final)[0])
        se_oos_h = float(sigma_oos_h[h - 1])

        fc_media.append(pred_h)
        fc_inf.append(pred_h - 1.96 * se_oos_h)
        fc_sup.append(pred_h + 1.96 * se_oos_h)

    return {
        "y": df_trans[ID_OBJETIVO].dropna(),
        "preds_h1": pd.Series(preds_h1_oos, index=fechas_h1_oos),
        "bench_h1": pd.Series(bench_h1_oos, index=fechas_h1_oos),
        "fc_media": pd.Series(fc_media, index=fechas_futuras),
        "fc_inf": pd.Series(fc_inf, index=fechas_futuras),
        "fc_sup": pd.Series(fc_sup, index=fechas_futuras),
        "metricas": {
            "rmse_h1": float(rmse_cart_h[0]),
            "rmse_h6": float(rmse_cart_h[5]),
            "rmse_h12": float(rmse_cart_h[11]),
            "rmse_h24": float(rmse_cart_h[23]),
            "ing_h1": float(rmse_ing_h[0]),
            "ing_h12": float(rmse_ing_h[11]),
            "ing_h24": float(rmse_ing_h[23]),
            "cobertura_pct": cobertura_pct,
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

    serie_nivel_valida = imacec["valor_mensual"].dropna()
    ts_ultimo_nivel = serie_nivel_valida.index.max()
    ultimo_nivel = float(serie_nivel_valida.iloc[-1])

    var_s = imacec["var_12m_pct"].dropna()
    ts_ultima_var = var_s.index.max()
    ultima_var = float(var_s.iloc[-1])
    media_hist_var = float(var_s.mean())

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
        f"Fuente: Banco Central de Chile (API SieteRestWS -> SQLite) | Período: {FECHA_INICIO} a {FECHA_FIN} | Modelo Principal: Árbol CART (24M, IC 95% OOS) | Grupo 12",
        ha="center",
        fontsize=9.6,
        color="#4a5568",
    )

    # -------------------------------------------------------------------------
    # PANEL 1: Serie principal en nivel + Promedio móvil 12M (2010-01 a 2026-08)
    # -------------------------------------------------------------------------
    ax1 = axes[0, 0]
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
    ax2 = axes[0, 1]
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
    # PANEL 4: Backtesting Multi-Horizonte + Proyección Principal CART (24M)
    # -------------------------------------------------------------------------
    ax4 = axes[1, 1]
    y_hist = res_fc["y"].iloc[-48:]
    ax4.plot(y_hist.index, y_hist, color="black", lw=2, label="Observado (Var. % 12M)")
    ax4.plot(res_fc["preds_h1"].index, res_fc["preds_h1"], "--o", color="#1f4e78", ms=3, alpha=0.85, label="CART Eval. OOS (h=1, 24 cortes)")
    ax4.plot(res_fc["bench_h1"].index, res_fc["bench_h1"], ":s", color="#718096", ms=3, alpha=0.8, label="Benchmark Ingenuo (h=1)")

    fc_m = res_fc["fc_media"]
    m = res_fc["metricas"]
    ax4.plot(fc_m.index, fc_m, "-D", color="#2f855a", ms=3.5, lw=1.9, label="Proyección Principal: CART (24M)")
    ax4.fill_between(
        fc_m.index,
        res_fc["fc_inf"],
        res_fc["fc_sup"],
        color="#2f855a",
        alpha=0.18,
        label=f"IC 95% OOS (Cob. empírica: {m['cobertura_pct']:.1f}%)",
    )

    texto_metricas = (
        f"RMSE Out-of-Sample Multi-Horizonte (K=24 cortes)\n"
        f"• h=1M:  CART={m['rmse_h1']:.2f} vs Ingenuo={m['ing_h1']:.2f}\n"
        f"• h=12M: CART={m['rmse_h12']:.2f} vs Ingenuo={m['ing_h12']:.2f}\n"
        f"• h=24M: CART={m['rmse_h24']:.2f} vs Ingenuo={m['ing_h24']:.2f}"
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
    ax4.set_title("4. Evaluación Multi-Horizonte y Proyección Principal (24 Meses)", fontsize=11, fontweight="bold", color="#1b365d")
    ax4.set_ylabel("Variación % 12M")
    ax4.xaxis.set_major_locator(mdates.YearLocator(1))
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax4.legend(loc="upper left", fontsize=7.6, frameon=True, ncol=2)

    plt.tight_layout(rect=[0, 0.01, 1, 0.92])
    plt.savefig(ruta_salida, dpi=300)
    plt.close()
    print(f"[OK] Dashboard generado exitosamente en: {ruta_salida}")


def main() -> None:
    engine = obtener_engine()
    df_dash = extraer_datos_dashboard(engine)
    resultados_fc = evaluar_y_proyectar_imacec(df_dash, n_cortes=24, h_futuro=24)
    construir_dashboard(df_dash, resultados_fc)


if __name__ == "__main__":
    main()