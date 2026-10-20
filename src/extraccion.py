import requests
import pandas as pd


def descargar_serie(codigo, usuario, password):

    url = (
        "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx?"
        f"user={usuario}"
        f"&pass={password}"
        "&function=GetSeries"
        f"&timeseries={codigo}"
    )

    respuesta = requests.get(url)

    datos = respuesta.json()

    obs = datos["Series"]["Obs"]

    df = pd.DataFrame(obs)

    df = df[["indexDateString", "value"]]

    df.columns = ["fecha", "valor"]

    df["fecha"] = pd.to_datetime(
        df["fecha"],
        dayfirst=True
    )

    df["valor"] = pd.to_numeric(
        df["valor"],
        errors="coerce"
    )

    return df