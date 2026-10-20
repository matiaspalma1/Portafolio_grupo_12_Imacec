from dotenv import load_dotenv
import os

from config import SERIES_BCCH
from extraccion import descargar_serie


from pathlib import Path

load_dotenv(
    Path(__file__).resolve().parent.parent / ".env"
)

usuario = os.getenv("BCCH_USUARIO")
password = os.getenv("BCCH_PASSWORD")

print("\nINICIANDO DESCARGA...\n")

ok = 0
error = 0

for serie in SERIES_BCCH:

    codigo = serie[0]
    nombre = serie[1]

    try:

        df = descargar_serie(
            codigo,
            usuario,
            password
        )

        print(
            f"[OK] {nombre} ({len(df)} observaciones)"
        )

        ok += 1

    except Exception as e:

        print(
            f"[ERROR] {nombre}"
        )

        print(e)

        error += 1

print("\nRESUMEN")

print(f"OK: {ok}")
print(f"ERROR: {error}")