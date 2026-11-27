"""
Carga de las series extraídas desde la API del Banco Central de Chile (SieteRestWS)
hacia la base de datos relacional SQLite (data/coyuntura.db).

Flujo de ejecución:
1. Inicializa la conexión SQLite activando integridad referencial (PRAGMA foreign_keys).
2. Ejecuta el DDL en sql/01_esquema.sql para crear tablas e índices de forma idempotente.
3. Registra o actualiza el catálogo de 17 series macroeconómicas en `series`.
4. Extrae las observaciones (desde API oficial o modo --demo) y las inserta en `observaciones`.
5. Emite un reporte de auditoría verificando conteos y cobertura temporal en la base.

Uso desde la raíz del repositorio:
    python src/carga_db.py                      # reproduce el corte oficial (2010-01 a 2026-08)
    python src/carga_db.py --demo               # carga datos sintéticos sin credenciales API
    python src/carga_db.py --hasta 2026-12-31   # actualiza hasta una fecha personalizada
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

try:
    import config
    from extraccion import extraer_todo
except ImportError:
    from src import config  # type: ignore
    from src.extraccion import extraer_todo  # type: ignore

FECHA_INICIO_DEFAULT = "2010-01-01"
FECHA_FIN_DEFAULT = "2026-08-31"


@event.listens_for(Engine, "connect")
def _activar_foreign_keys_sqlite(dbapi_connection, _connection_record) -> None:
    """Garantiza que SQLite haga cumplir las claves foráneas en cada conexión."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()


def obtener_engine(ruta_db: Path = config.RUTA_DB) -> Engine:
    """Crea y retorna el motor SQLAlchemy conectado a la base SQLite del proyecto."""
    ruta_db.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{ruta_db}")


def crear_esquema(engine: Engine, ruta_sql: Path = config.RUTA_SQL / "01_esquema.sql") -> None:
    """Ejecuta el script DDL sql/01_esquema.sql de forma idempotente."""
    if not ruta_sql.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de esquema SQL en: {ruta_sql}. "
            "Verifica que estás ejecutando el script desde la raíz del repositorio."
        )

    script = ruta_sql.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for sentencia in script.split(";"):
            sentencia_limpia = sentencia.strip()
            if sentencia_limpia:
                conn.execute(text(sentencia_limpia))
    print("[OK] Esquema relacional SQL verificado / creado.")


def cargar_catalogo(engine: Engine) -> None:
    """Inserta o actualiza el catálogo oficial de series definido en src/config.py."""
    registros_catalogo = [
        {
            "id_serie": codigo,
            "nombre": nombre,
            "frecuencia": frecuencia,
            "unidad": unidad,
            "id_tema": id_tema,
        }
        for (codigo, nombre, frecuencia, unidad, id_tema) in config.SERIES_BCCH
    ]

    sql_upsert_catalogo = text("""
        INSERT INTO series (id_serie, nombre, frecuencia, unidad, id_tema)
        VALUES (:id_serie, :nombre, :frecuencia, :unidad, :id_tema)
        ON CONFLICT(id_serie) DO UPDATE SET
            nombre = excluded.nombre,
            frecuencia = excluded.frecuencia,
            unidad = excluded.unidad,
            id_tema = excluded.id_tema;
    """)

    with engine.begin() as conn:
        conn.execute(sql_upsert_catalogo, registros_catalogo)
    print(f"[OK] Catálogo sincronizado: {len(registros_catalogo)} series registradas.")


def cargar_observaciones(engine: Engine, series: dict[str, pd.DataFrame]) -> int:
    """
    Inserta o actualiza las observaciones históricas por serie mediante UPSERT.

    Returns:
        Número total de registros procesados e insertados en `observaciones`.
    """
    sql_upsert_obs = text("""
        INSERT INTO observaciones (id_serie, fecha, valor)
        VALUES (:id_serie, :fecha, :valor)
        ON CONFLICT(id_serie, fecha) DO UPDATE SET
            valor = excluded.valor;
    """)

    total_registros = 0
    series_vacias: list[str] = []

    with engine.begin() as conn:
        for codigo, df in series.items():
            if df is None or df.empty:
                series_vacias.append(codigo)
                continue

            fechas_str = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
            valores_limpios = [None if pd.isna(v) else float(v) for v in df["valor"]]

            registros = [
                {"id_serie": codigo, "fecha": f_str, "valor": val}
                for f_str, val in zip(fechas_str, valores_limpios)
            ]
            conn.execute(sql_upsert_obs, registros)
            total_registros += len(registros)

    if series_vacias:
        print(f"[ADVERTENCIA] Series sin datos nuevos en el rango: {', '.join(series_vacias)}")
    print(f"[OK] Observaciones cargadas/actualizadas: {total_registros:,} registros.")
    return total_registros


def auditar_base_datos(engine: Engine) -> None:
    """Imprime un resumen de verificación con conteos y cobertura temporal en SQLite."""
    query_resumen = text("""
        SELECT
            (SELECT COUNT(*) FROM temas) AS total_temas,
            (SELECT COUNT(*) FROM series) AS total_series,
            COUNT(*) AS total_observaciones,
            MIN(fecha) AS fecha_minima,
            MAX(fecha) AS fecha_maxima
        FROM observaciones;
    """)
    with engine.connect() as conn:
        res = conn.execute(query_resumen).mappings().one()

    print("\n--- Auditoría de Base de Datos (data/coyuntura.db) ---")
    print(f"  • Temas registrados      : {res['total_temas']}")
    print(f"  • Series en catálogo     : {res['total_series']}")
    print(f"  • Observaciones totales  : {res['total_observaciones']:,}")
    print(f"  • Cobertura temporal     : {res['fecha_minima']} a {res['fecha_maxima']}")
    print("------------------------------------------------------\n")


def main(
    demo: bool = False,
    desde: str = FECHA_INICIO_DEFAULT,
    hasta: str | None = FECHA_FIN_DEFAULT,
) -> None:
    """Orquesta el pipeline completo de creación de esquema, extracción y carga."""
    modo = "DEMO (datos sintéticos)" if demo else "API Banco Central de Chile (SieteRestWS)"
    corte_label = hasta if hasta else "último dato disponible"

    print("======================================================")
    print(" PIPELINE DE INGESTA MACROECONÓMICA -> SQLITE")
    print("======================================================")
    print(f"  • Fuente  : {modo}")
    print(f"  • Ventana : {desde} hasta {corte_label}\n")

    engine = obtener_engine()
    crear_esquema(engine)
    cargar_catalogo(engine)

    series = extraer_todo(demo=demo, desde=desde, hasta=hasta)
    cargar_observaciones(engine, series)
    auditar_base_datos(engine)
    print(f"[LISTO] Base de datos disponible en: {config.RUTA_DB}")


def _parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extracción y carga de series macroeconómicas del BCCh a SQLite."
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
        main(demo=args.demo, desde=args.desde, hasta=args.hasta)
    except Exception as exc:
        print(f"\n[ERROR] Falló la ejecución de carga_db.py: {exc}", file=sys.stderr)
        sys.exit(1)