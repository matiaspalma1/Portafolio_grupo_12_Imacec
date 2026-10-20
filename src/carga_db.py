import argparse
import os
import sqlite3
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

from config import SERIES_BCCH
from extraccion import descargar_serie

# Cargar variables de entorno (.env) desde la raíz del proyecto
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

usuario = os.getenv("BCCH_USUARIO")
password = os.getenv("BCCH_PASSWORD")

# Ruta a la base de datos SQLite
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "coyuntura.db"


def inicializar_db(conn):
    """Asegura que las tres tablas existan con el esquema oficial del proyecto."""
    cursor = conn.cursor()

    # 1. Tabla catalog: temas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS temas (
        id_tema INTEGER PRIMARY KEY,
        tema TEXT NOT NULL,
        descripcion TEXT
    );
    """)

    # Insertar los 4 temas si no existen
    cursor.execute("""
    INSERT OR IGNORE INTO temas (id_tema, tema, descripcion) VALUES
    (1, 'Actividad', 'Variables de actividad económica agregada y sectorial'),
    (2, 'Sector Externo', 'Precios de commodities, tipo de cambio y comercio exterior'),
    (3, 'Mercado Laboral', 'Indicadores de empleo y tasa de desocupación'),
    (4, 'Expectativas', 'Expectativas del mercado sobre inflación y tipo de cambio');
    """)

    # 2. Tabla catálogo: series
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS series (
        id_serie TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        frecuencia TEXT NOT NULL,
        unidad TEXT,
        id_tema INTEGER REFERENCES temas(id_tema)
    );
    """)

    # 3. Tabla de hechos: observaciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS observaciones (
        id_serie TEXT NOT NULL REFERENCES series(id_serie),
        fecha DATE NOT NULL,
        valor REAL,
        PRIMARY KEY (id_serie, fecha)
    );
    """)
    conn.commit()


def guardar_en_db(conn, serie_metadata, df, hasta=None):
    """Guarda la metadata de la serie y sus observaciones en SQLite."""
    codigo, nombre, frecuencia, unidad, id_tema = serie_metadata
    cursor = conn.cursor()

    # 1. Insertar/Actualizar metadata en la tabla 'series'
    cursor.execute("""
    INSERT INTO series (id_serie, nombre, frecuencia, unidad, id_tema)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(id_serie) DO UPDATE SET
        nombre=excluded.nombre,
        frecuencia=excluded.frecuencia,
        unidad=excluded.unidad,
        id_tema=excluded.id_tema;
    """, (codigo, nombre, frecuencia, unidad, id_tema))

    # 2. Eliminar filas sin fecha válida si existieran
    df = df.dropna(subset=["fecha"])

    # 3. Filtrar por fecha de corte si se especificó --hasta
    if hasta:
        df = df[df["fecha"] <= pd.to_datetime(hasta)]

    # 4. Preparar registros manejando valores nulos para SQLite (NaN -> None)
    registros = [
        (
            codigo,
            row.fecha.strftime("%Y-%m-%d"),
            None if pd.isna(row.valor) else float(row.valor)
        )
        for row in df.itertuples()
    ]

    # 5. Carga idempotente a la tabla 'observaciones'
    cursor.executemany("""
    INSERT OR REPLACE INTO observaciones (id_serie, fecha, valor)
    VALUES (?, ?, ?);
    """, registros)

    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Descarga y carga de datos a SQLite")
    parser.add_argument("--hasta", type=str, help="Fecha de corte (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    print("\nINICIANDO DESCARGA Y CARGA A BASE DE DATOS...\n")

    # Crear la carpeta data/ si no existe en el disco
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    inicializar_db(conn)

    ok, error = 0, 0

    for serie in SERIES_BCCH:
        codigo, nombre = serie[0], serie[1]
        try:
            df = descargar_serie(codigo, usuario, password)
            guardar_en_db(conn, serie, df, hasta=args.hasta)
            
            # Conteo de registros válidos guardados
            if args.hasta:
                df_filtrado = df[df["fecha"] <= pd.to_datetime(args.hasta)]
                n_obs = len(df_filtrado.dropna(subset=["fecha"]))
            else:
                n_obs = len(df.dropna(subset=["fecha"]))

            print(f"[OK] {nombre} ({n_obs} observaciones guardadas)")
            ok += 1
        except Exception as e:
            print(f"[ERROR] {nombre}: {e}")
            error += 1

    conn.close()

    print(f"\nRESUMEN: {ok} cargadas correctamente, {error} errores.")
    print(f"Base de datos actualizada en: {DB_PATH}")


if __name__ == "__main__":
    main()