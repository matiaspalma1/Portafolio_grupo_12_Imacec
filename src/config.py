"""
Configuración central y catálogo macroeconómico del proyecto (Proyección del IMACEC).

Centraliza:
1. Rutas del proyecto (base de datos SQLite, scripts SQL y carpeta de salidas).
2. Lectura y validación de credenciales de la API SieteRestWS del Banco Central de Chile.
3. Parámetros temporales oficiales del estudio (ventana histórica y corte train/test).
4. Clasificación temática y catálogo documentado de las 17 series económicas.

Instrucciones para uso externo:
    Copiar `.env.example` a `.env` en la raíz del repositorio y completar
    `BCCH_USUARIO` y `BCCH_PASSWORD` (registro gratuito en https://si3.bcentral.cl/Siete/es/Siete/API).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ==============================================================================
# 1. RUTAS DEL PROYECTO
# ==============================================================================
RAIZ = Path(__file__).resolve().parents[1]
RUTA_DATOS = RAIZ / "data"
RUTA_DB = RUTA_DATOS / "coyuntura.db"
RUTA_SQL = RAIZ / "sql"
RUTA_OUTPUTS = RAIZ / "outputs"

# ==============================================================================
# 2. CREDENCIALES API BANCO CENTRAL DE CHILE (SieteRestWS)
# ==============================================================================
load_dotenv(RAIZ / ".env")

BCCH_USUARIO: str = os.getenv("BCCH_USUARIO") or os.getenv("BCCH_USER", "")
BCCH_PASSWORD: str = os.getenv("BCCH_PASSWORD") or os.getenv("BCCH_PASS", "")


def validar_credenciales() -> None:
    """Verifica que las credenciales de la API del BCCh estén configuradas en .env."""
    if not BCCH_USUARIO.strip() or not BCCH_PASSWORD.strip():
        raise EnvironmentError(
            "Credenciales del Banco Central de Chile no encontradas.\n"
            "Por favor, copia '.env.example' a '.env' en la raíz del proyecto y completa "
            "BCCH_USUARIO y BCCH_PASSWORD, o ejecuta el pipeline en modo prueba con: "
            "python src/carga_db.py --demo"
        )


# ==============================================================================
# 3. PARÁMETROS TEMPORALES Y SERIES CLAVE DEL ESTUDIO
# ==============================================================================
FECHA_INICIO = "2010-01-01"
FECHA_FIN = "2026-08-01"
FECHA_FIN_TRAIN = "2022-08-01"

ID_OBJETIVO = "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M"  # IMACEC empalmado (Índice 2018=100)
ID_TPM = "F022.TPM.TIN.D001.NO.Z.D"            # Tasa de Política Monetaria (%)

# ==============================================================================
# 4. CLASIFICACIÓN TEMÁTICA Y CATÁLOGO OFICIAL (17 SERIES BCCh)
#    Estructura de cada tupla: (id_serie, nombre, frecuencia, unidad, id_tema)
# ==============================================================================
TEMAS_BCCH: dict[int, str] = {
    1: "Actividad",
    2: "Sector Externo",
    3: "Mercado Laboral",
    4: "Expectativas",
    5: "Politica Monetaria",
}

SERIES_BCCH: list[tuple[str, str, str, str, int]] = [
    # --------------------------------------------------------------------------
    # TEMA 1: ACTIVIDAD ECONÓMICA (Variable objetivo y desagregación sectorial)
    # --------------------------------------------------------------------------
    # Variable objetivo del proyecto: mide la evolución agregada de la actividad
    # económica mensual de Chile (se transforma a variación interanual % 12M).
    (
        "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M",
        "Imacec empalmado",
        "M",
        "Indice 2018=100",
        1,
    ),
    # Aporte del sector minero al IMACEC; captura choques de oferta y ciclos
    # asociados a la principal industria exportadora del país.
    (
        "F032.IMC.IND.Z.Z.EP18.03.Z.0.M",
        "Imacec minero",
        "M",
        "Indice 2018=100",
        1,
    ),
    # Actividad de la industria manufacturera; refleja con sensibilidad los
    # puntos de giro en el ciclo económico e inversión.
    (
        "F032.IMC.IND.Z.Z.EP18.04.Z.0.M",
        "Imacec industria",
        "M",
        "Indice 2018=100",
        1,
    ),
    # Actividades productivas distintas de minería e industria (agropecuario,
    # electricidad, gas, agua y construcción); complementa la composición sectorial.
    (
        "F032.IMC.IND.Z.Z.EP18.RB.Z.0.M",
        "Imacec resto bienes",
        "M",
        "Indice 2018=100",
        1,
    ),
    # Aproxima el dinamismo del consumo privado y la demanda interna; suele
    # reaccionar rápidamente ante cambios en tasas e ingresos.
    (
        "F032.IMC.IND.Z.Z.EP18.COM.Z.0.M",
        "Imacec comercio",
        "M",
        "Indice 2018=100",
        1,
    ),
    # Representa la mayor ponderación dentro del producto chileno; aporta
    # persistencia y estabilidad a la trayectoria agregada del IMACEC.
    (
        "F032.IMC.IND.Z.Z.EP18.SERV.Z.0.M",
        "Imacec servicios",
        "M",
        "Indice 2018=100",
        1,
    ),
    # Impuestos netos sobre los productos asociados a la producción y el consumo;
    # permite conciliar la suma sectorial con el índice agregado.
    (
        "F032.IMC.IND.Z.Z.EP18.IMP.Z.0.M",
        "Imacec impuestos",
        "M",
        "Indice 2018=100",
        1,
    ),

    # --------------------------------------------------------------------------
    # TEMA 2: SECTOR EXTERNO (Términos de intercambio, divisas y comercio)
    # --------------------------------------------------------------------------
    # Cotización internacional del cobre; principal determinante de los términos
    # de intercambio, ingresos fiscales e inversión minera en Chile.
    (
        "F019.PPB.PRE.40.M",
        "Precio cobre",
        "M",
        "USD/libra",
        2,
    ),
    # Paridad peso/dólar observada (frecuencia diaria, promediada a mensual en SQL);
    # incide en competitividad externa, inflación transable y expectativas.
    (
        "F073.TCO.PRE.Z.D",
        "Tipo cambio observado",
        "D",
        "CLP/USD",
        2,
    ),
    # Ingresos nominales por envíos de cobre; captura el efecto combinado de
    # precio internacional y volumen embarcado.
    (
        "F068.B1.FLU.A1.0.C.N.Z.Z.Z.Z.6.0.M",
        "Exportaciones cobre",
        "M",
        "Millones USD",
        2,
    ),
    # Envío de carbonato e hidróxido de litio; captura el impulso de un sector
    # estratégico no tradicional en la balanza comercial chilena.
    (
        "F068.B1.FLU.A8.0.C.N.Z.Z.Z.Z.6.0.M",
        "Exportaciones litio",
        "M",
        "Millones USD",
        2,
    ),
    # Exportaciones silvoagropecuarias; aporta señal sobre el desempeño del
    # sector exportador no minero y empleo regional.
    (
        "F068.B1.FLU.B.0.C.N.Z.Z.Z.Z.6.0.M",
        "Exportaciones agropecuarias",
        "M",
        "Millones USD",
        2,
    ),
    # Internaciones de bienes de consumo; indicador adelantado de la fortaleza
    # del gasto privado y reposición de inventarios en el comercio.
    (
        "F068.B1.FLU.Z.0.M.N.A.Z.Z.Z.6.0.M",
        "Importaciones consumo",
        "M",
        "Millones USD",
        2,
    ),

    # --------------------------------------------------------------------------
    # TEMA 3: MERCADO LABORAL
    # --------------------------------------------------------------------------
    # Tasa de desocupación nacional (trimestre móvil INE); captura la holgura
    # del mercado del trabajo y su relación inversa (ley de Okun) con la actividad.
    (
        "F049.DES.TAS.INE9.10.M",
        "Tasa desocupacion",
        "M",
        "Porcentaje",
        3,
    ),

    # --------------------------------------------------------------------------
    # TEMA 4: EXPECTATIVAS MACROECONÓMICAS (Encuesta de Expectativas Económicas)
    # --------------------------------------------------------------------------
    # Expectativa del tipo de cambio a 11 meses; incorpora información prospectiva
    # del mercado sobre condiciones financieras externas y locales.
    (
        "F089.TCN.PRE.14.M",
        "Expectativa tipo cambio 11 meses",
        "M",
        "CLP/USD",
        4,
    ),
    # Expectativa de inflación interanual a 11 meses; resume el anclaje nominal
    # y anticipa el espacio de acción de la política monetaria.
    (
        "F089.IPC.V12.14.M",
        "Expectativa inflacion 11 meses",
        "M",
        "Porcentaje",
        4,
    ),

    # --------------------------------------------------------------------------
    # TEMA 5: POLÍTICA MONETARIA
    # --------------------------------------------------------------------------
    # Tasa de Política Monetaria (frecuencia diaria, promediada a mensual en SQL);
    # instrumento rector del BCCh que transmite impulsos al crédito y gasto con rezago.
    (
        "F022.TPM.TIN.D001.NO.Z.D",
        "Tasa de Politica Monetaria",
        "D",
        "Porcentaje",
        5,
    ),
]