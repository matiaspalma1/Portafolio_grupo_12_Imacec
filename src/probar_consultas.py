import sqlite3
import pandas as pd
from pathlib import Path

# Rutas del proyecto
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "coyuntura.db"
SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "02_consultas.sql"

# 1. Consulta SQL oficial de la Etapa 4 (JOIN + GROUP BY + Función de ventana)
QUERY_COYUNTURA = """
WITH mensual AS (
    SELECT 
        o.id_serie,
        strftime('%Y-%m', o.fecha) AS mes,
        AVG(o.valor) AS valor_promedio
    FROM observaciones AS o
    GROUP BY o.id_serie, mes
),
variaciones AS (
    SELECT 
        m.id_serie,
        m.mes,
        m.valor_promedio,
        LAG(m.valor_promedio, 12) OVER (
            PARTITION BY m.id_serie 
            ORDER BY m.mes
        ) AS valor_hace_12m,
        100.0 * (m.valor_promedio / LAG(m.valor_promedio, 12) OVER (
            PARTITION BY m.id_serie 
            ORDER BY m.mes
        ) - 1.0) AS var_interanual_pct
    FROM mensual AS m
)
SELECT 
    t.tema,
    s.nombre AS serie,
    s.unidad,
    s.frecuencia,
    v.mes,
    ROUND(v.valor_promedio, 2) AS valor,
    ROUND(v.var_interanual_pct, 2) AS var_12m_pct
FROM variaciones AS v
JOIN series AS s ON s.id_serie = v.id_serie
JOIN temas AS t ON t.id_tema = s.id_tema
ORDER BY t.tema, s.nombre, v.mes;
"""

# 2. Asegurar que sql/02_consultas.sql quede guardado correctamente
SQL_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(SQL_FILE, "w", encoding="utf-8") as f:
    f.write("-- CONSULTA PRINCIPAL DE COYUNTURA MACROECONÓMICA\n")
    f.write(QUERY_COYUNTURA)

# 3. Ejecutar la consulta en la base de datos SQLite
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query(QUERY_COYUNTURA, conn)
conn.close()

print("\n--- PRIMERAS FILAS DE LA CONSULTA CON VARIACIÓN INTERANUAL ---")
print(df.dropna(subset=["var_12m_pct"]).head(15).to_string())

print("\n--- RESUMEN DE OBSERVACIONES PROCESADAS POR SERIE ---")
print(df.groupby("serie")["mes"].count().to_string())