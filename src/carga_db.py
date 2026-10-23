"""
Carga de las series extraídas desde la API del Banco Central a la base de datos relacional (SQLite).

Flujo:
  1. Crea el esquema ejecutando sql/01_esquema.sql (si las tablas no existen).
  2. Registra el catálogo de series del BCCh en la tabla `series`.
  3. Inserta/actualiza las observaciones en la tabla `observaciones`.

Uso desde la raíz del repositorio:
    python src/carga_db.py                      # extrae desde API y carga
    python src/carga_db.py --demo               # carga datos sintéticos de prueba
    python src/carga_db.py --hasta 2026-08-31   # fija la fecha de corte
"""
from __future__ import annotations

import argparse
import pandas as pd
from sqlalchemy import create_engine, text

try:
    import config
    from extraccion import extraer_todo
except ImportError:
    from src import config  # type: ignore
    from src.extraccion import extraer_todo  # type: ignore


def obtener_engine():
    """Crea la conexión a la base de datos SQLite utilizando SQLAlchemy."""
    config.RUTA_DATOS.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{config.RUTA_DB}")


def crear_esquema(engine) -> None:
    """Ejecuta el script DDL del esquema sql/01_esquema.sql de forma idempotente."""
    script_path = config.RUTA_SQL / "01_esquema.sql"
    if script_path.exists():
        script = script_path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            for sentencia in script.split(";"):
                if sentencia.strip():
                    conn.execute(text(sentencia))
        print("[OK] Esquema SQL verificado / creado.")
    else:
        print(f"[ADVERTENCIA] No se encontró {script_path}. Se asume esquema previo.")


def cargar_catalogo(engine) -> None:
    """Inserta/actualiza el catálogo de series del Banco Central definido en config.py."""
    catalogo = config.SERIES_BCCH
    df = pd.DataFrame(
        [
            {
                "id_serie": codigo,
                "nombre": nombre,
                "frecuencia": frecuencia,
                "unidad": unidad,
                "id_tema": id_tema,
            }
            for (codigo, nombre, frecuencia, unidad, id_tema) in catalogo
        ]
    )
    with engine.begin() as conn:
        for _, fila in df.iterrows():
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO series (id_serie, nombre, frecuencia, unidad, id_tema) "
                    "VALUES (:id_serie, :nombre, :frecuencia, :unidad, :id_tema)"
                ),
                fila.to_dict(),
            )
    print(f"[OK] Catálogo cargado: {len(df)} series del BCCh.")


def cargar_observaciones(engine, series: dict[str, pd.DataFrame]) -> None:
    """Inserta/actualiza las observaciones de cada serie en la base de datos."""
    total = 0
    with engine.begin() as conn:
        for codigo, df in series.items():
            if df.empty:
                continue
            registros = [
                {
                    "id_serie": codigo,
                    "fecha": fila.fecha.strftime("%Y-%m-%d"),
                    "valor": None if pd.isna(fila.valor) else float(fila.valor),
                }
                for fila in df.itertuples()
            ]
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO observaciones (id_serie, fecha, valor) "
                    "VALUES (:id_serie, :fecha, :valor)"
                ),
                registros,
            )
            total += len(registros)
    print(f"[OK] Observaciones cargadas/actualizadas: {total} registros en total.")


def main(demo: bool = False, desde: str = "2010-01-01", hasta: str | None = None) -> None:
    engine = obtener_engine()
    crear_esquema(engine)
    cargar_catalogo(engine)
    
    modo = "DEMO (datos sintéticos)" if demo else "API Banco Central de Chile"
    corte = hasta or "hoy"
    print(f"\nIniciando pipeline | Modo: {modo} | Desde {desde} hasta {corte}\n")
    
    series = extraer_todo(demo=demo, desde=desde, hasta=hasta)
    cargar_observaciones(engine, series)
    print(f"\nBase de datos lista y actualizada en: {config.RUTA_DB}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga de series a la base de datos SQLite")
    parser.add_argument("--demo", action="store_true",
                        help="Usar datos sintéticos de prueba sin credenciales")
    parser.add_argument("--desde", default="2010-01-01", metavar="AAAA-MM-DD",
                        help="Primera fecha a solicitar (por defecto 2010-01-01)")
    parser.add_argument("--hasta", default=None, metavar="AAAA-MM-DD",
                        help="Fecha de corte. Fijarla hace la carga reproducible.")
    args = parser.parse_args()
    
    main(demo=args.demo, desde=args.desde, hasta=args.hasta)