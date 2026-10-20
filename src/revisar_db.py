import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "coyuntura.db"
conn = sqlite3.connect(DB_PATH)

query = """
SELECT 
    t.tema,
    s.nombre,
    COUNT(o.valor) AS n_obs,
    MIN(o.fecha) AS desde,
    MAX(o.fecha) AS hasta
FROM temas AS t
LEFT JOIN series AS s ON s.id_tema = t.id_tema
LEFT JOIN observaciones AS o ON o.id_serie = s.id_serie
GROUP BY t.tema, s.nombre
ORDER BY t.tema, n_obs;
"""

df = pd.read_sql(query, conn)
print(df.to_string())
conn.close()