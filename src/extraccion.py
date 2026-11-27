"""
Extracción programática de series económicas desde la API oficial del Banco Central de Chile (BCCh).

Fuente soportada:
- Banco Central de Chile (Base de Datos Estadísticos, API SieteRestWS).

Incluye además un MODO DEMO (--demo) que genera series sintéticas con la misma
estructura temporal y frecuencia, permitiendo ejecutar y validar todo el pipeline
(SQLite, consultas SQL, notebooks y dashboard.py) sin requerir credenciales API.

Uso desde la raíz del repositorio:
    python src/extraccion.py                      # extrae ventana oficial (2010-01 a 2026-08)
    python src/extraccion.py --demo               # genera datos sintéticos de prueba
    python src/extraccion.py --hasta 2026-12-31   # fija una fecha de corte personalizada
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np
import pandas as pd
import requests

try:
    import config
except ImportError:  # permite ejecutar directamente desde la raíz del repositorio
    from src import config  # type: ignore

URL_BCCH = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
FECHA_INICIO_DEFAULT: str = getattr(config, "FECHA_INICIO", "2010-01-01")
FECHA_FIN_DEFAULT: str = "2026-08-31"


# ==============================================================================
# 1. SEGURIDAD Y MANEJO DE PETICIONES HTTP
# ==============================================================================
def enmascarar(texto: str) -> str:
    """Reemplaza por '***' cualquier credencial del BCCh que aparezca en un mensaje."""
    for secreto in (config.BCCH_PASSWORD, config.BCCH_USUARIO):
        if secreto:
            texto = texto.replace(secreto, "***")
    return texto


def pedir_json(url: str, params: dict, session: requests.Session | None = None) -> dict:
    """Ejecuta la petición GET a SieteRestWS y devuelve el JSON sin filtrar credenciales."""
    cliente = session or requests
    try:
        respuesta = cliente.get(url, params=params, timeout=60)
        respuesta.raise_for_status()
        contenido = respuesta.json()
    except requests.RequestException as exc:
        # 'from None' evita encadenar la excepción original cuya URL contiene usuario y clave
        raise RuntimeError(enmascarar(str(exc))) from None
    except ValueError:
        raise RuntimeError("La API del BCCh devolvió una respuesta no válida (no es JSON).") from None

    # SieteRestWS puede responder HTTP 200 con Codigo != 0 ante credenciales o parámetros inválidos
    codigo_api = contenido.get("Codigo")
    if codigo_api is not None and int(codigo_api) != 0:
        descripcion = enmascarar(str(contenido.get("Descripcion", "Error desconocido en SieteRestWS")))
        raise RuntimeError(f"API BCCh rechazó la solicitud (Codigo {codigo_api}): {descripcion}")

    return contenido


def _verificar_credenciales() -> None:
    """Valida la presencia de credenciales delegando en config.py si está disponible."""
    if hasattr(config, "validar_credenciales"):
        config.validar_credenciales()
    elif not (config.BCCH_USUARIO and config.BCCH_PASSWORD):
        raise EnvironmentError(
            "Faltan credenciales del BCCh. Copia '.env.example' a '.env' y completa "
            "BCCH_USUARIO y BCCH_PASSWORD (registro gratuito en https://si3.bcentral.cl/Siete/es/Siete/API)."
        )


# ==============================================================================
# 2. EXTRACCIÓN DESDE BANCO CENTRAL DE CHILE (SieteRestWS)
# ==============================================================================
def extraer_serie_bcch(
    codigo: str,
    desde: str = FECHA_INICIO_DEFAULT,
    hasta: str | None = FECHA_FIN_DEFAULT,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Descarga una serie desde la API del BCCh y la devuelve como DataFrame (fecha, valor)."""
    _verificar_credenciales()

    fecha_fin = hasta or date.today().isoformat()
    params = {
        "user": config.BCCH_USUARIO,
        "pass": config.BCCH_PASSWORD,
        "timeseries": codigo,
        "firstdate": desde,
        "lastdate": fecha_fin,
        "function": "GetSeries",
    }

    contenido = pedir_json(URL_BCCH, params, session=session)
    obs = contenido.get("Series", {}).get("Obs", [])
    if not obs:
        raise ValueError(
            f"La API del BCCh no devolvió observaciones para '{codigo}' entre {desde} y {fecha_fin}."
        )

    df = pd.DataFrame(obs)
    # La API entrega fechas dd-mm-YYYY y valores como texto; 'NaN' representa dato no disponible
    df["fecha"] = pd.to_datetime(df["indexDateString"], format="%d-%m-%Y")
    df["valor"] = pd.to_numeric(df["value"], errors="coerce")
    return df[["fecha", "valor"]].dropna().sort_values("fecha").reset_index(drop=True)


def descargar_serie(
    codigo: str,
    usuario: str | None = None,
    password: str | None = None,
    desde: str = FECHA_INICIO_DEFAULT,
    hasta: str | None = FECHA_FIN_DEFAULT,
) -> pd.DataFrame:
    """Alias de compatibilidad para llamadas desde scripts externos."""
    return extraer_serie_bcch(codigo, desde=desde, hasta=hasta)


# ==============================================================================
# 3. MODO DEMO (SERIES SINTÉTICAS PARA PRUEBAS SIN CREDENCIALES)
# ==============================================================================
def generar_serie_demo(
    codigo: str,
    frecuencia: str,
    semilla: int,
    desde: str = FECHA_INICIO_DEFAULT,
    hasta: str | None = FECHA_FIN_DEFAULT,
) -> pd.DataFrame:
    """Genera una serie sintética reproducible (sin significado económico) para pruebas técnicas."""
    fin = hasta or date.today().isoformat()
    rng = np.random.default_rng(semilla)

    if frecuencia == "D":
        fechas = pd.date_range(desde, fin, freq="B")  # días hábiles
        paso_tendencia = 0.002
        periodo_estacional = 252
    else:
        fechas = pd.date_range(desde, fin, freq="MS")  # inicio de mes
        paso_tendencia = 0.05
        periodo_estacional = 12

    n = len(fechas)
    t = np.arange(n)
    tendencia = 100.0 + paso_tendencia * t
    estacionalidad = 3.0 * np.sin(2.0 * np.pi * t / periodo_estacional)
    ruido = rng.normal(0.0, 1.5, n).cumsum() * 0.25

    # Se asegura positividad estricta para evitar divisiones anómalas en variaciones % 12M
    valores = np.maximum(tendencia + estacionalidad + ruido, 5.0)
    return pd.DataFrame({"fecha": fechas, "valor": np.round(valores, 3)})


# ==============================================================================
# 4. ORQUESTACIÓN DEL CATÁLOGO COMPLETO
# ==============================================================================
def extraer_todo(
    demo: bool = False,
    desde: str = FECHA_INICIO_DEFAULT,
    hasta: str | None = FECHA_FIN_DEFAULT,
) -> dict[str, pd.DataFrame]:
    """Extrae todas las series registradas en config.SERIES_BCCH."""
    if not demo:
        _verificar_credenciales()

    resultados: dict[str, pd.DataFrame] = {}
    catalogo = config.SERIES_BCCH
    fallidas: list[str] = []

    with requests.Session() as session:
        for i, (codigo, nombre, frecuencia, _unidad, _tema) in enumerate(catalogo):
            try:
                if demo:
                    df = generar_serie_demo(
                        codigo, frecuencia, semilla=i, desde=desde, hasta=hasta
                    )
                else:
                    df = extraer_serie_bcch(
                        codigo, desde=desde, hasta=hasta, session=session
                    )
                resultados[codigo] = df
                ultima = df["fecha"].max().strftime("%Y-%m-%d") if not df.empty else "sin datos"
                print(f"  [OK] {nombre:<32} | {len(df):>5} obs. | hasta {ultima}")
            except Exception as exc:
                fallidas.append(f"{nombre} ({codigo})")
                print(f"  [ERROR] {nombre} ({codigo}): {enmascarar(str(exc))}")

    if fallidas:
        print(
            f"\n[ADVERTENCIA] {len(fallidas)} de {len(catalogo)} series fallaron:\n  - "
            + "\n  - ".join(fallidas)
        )
    return resultados


def _parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extracción de series macroeconómicas del Banco Central de Chile (SieteRestWS)."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Genera datos sintéticos reproducibles sin requerir credenciales en .env.",
    )
    parser.add_argument(
        "--desde",
        default=FECHA_INICIO_DEFAULT,
        metavar="AAAA-MM-DD",
        help=f"Fecha inicial de extracción (por defecto: {FECHA_INICIO_DEFAULT}).",
    )
    parser.add_argument(
        "--hasta",
        default=FECHA_FIN_DEFAULT,
        metavar="AAAA-MM-DD",
        help=f"Fecha de corte final para reproducibilidad (por defecto: {FECHA_FIN_DEFAULT}).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = _parsear_argumentos()
        modo = "DEMO (datos sintéticos)" if args.demo else "API Banco Central de Chile (SieteRestWS)"
        corte = args.hasta or f"{date.today().isoformat()} (hoy)"

        print(f"Extrayendo series | Modo: {modo} | Ventana: {args.desde} a {corte}\n")
        series_extraidas = extraer_todo(demo=args.demo, desde=args.desde, hasta=args.hasta)

        if not series_extraidas:
            print("\n[ERROR] No se extrajo ninguna serie. Revisa credenciales y conexión.", file=sys.stderr)
            sys.exit(1)

        print(f"\n[OK] Extracción finalizada: {len(series_extraidas)}/{len(config.SERIES_BCCH)} series disponibles.")
    except Exception as exc:
        print(f"\n[ERROR] Falló la extracción: {enmascarar(str(exc))}", file=sys.stderr)
        sys.exit(1)