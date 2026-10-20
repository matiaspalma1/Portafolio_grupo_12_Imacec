# ==========================================
# CATALOGO DE SERIES
# Proyecto: Proyección del IMACEC
#
# id_tema:
# 1 = Actividad
# 2 = Sector Externo
# 3 = Mercado Laboral
# 4 = Expectativas
# ==========================================

SERIES_BCCH = [

    # ==========================================
    # ACTIVIDAD ECONÓMICA
    # ==========================================

    # Variable objetivo del proyecto.
    # Mide la evolución agregada de la actividad económica chilena.
    (
        "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M",
        "Imacec empalmado",
        "M",
        "Indice 2018=100",
        1
    ),

    # Permite identificar el aporte del sector minero al IMACEC.
    # La minería representa una parte importante de las exportaciones chilenas.
    (
        "F032.IMC.IND.Z.Z.EP18.03.Z.0.M",
        "Imacec minero",
        "M",
        "Indice 2018=100",
        1
    ),

    # Mide la actividad manufacturera.
    # La producción industrial suele reflejar cambios en el ciclo económico.
    (
        "F032.IMC.IND.Z.Z.EP18.04.Z.0.M",
        "Imacec industria",
        "M",
        "Indice 2018=100",
        1
    ),

    # Captura actividades productivas distintas de minería e industria.
    # Ayuda a entender la composición sectorial del crecimiento.
    (
        "F032.IMC.IND.Z.Z.EP18.RB.Z.0.M",
        "Imacec resto bienes",
        "M",
        "Indice 2018=100",
        1
    ),

    # Aproxima el comportamiento del consumo privado.
    # El comercio suele expandirse en periodos de mayor actividad económica.
    (
        "F032.IMC.IND.Z.Z.EP18.COM.Z.0.M",
        "Imacec comercio",
        "M",
        "Indice 2018=100",
        1
    ),

    # Representa una proporción importante de la economía chilena.
    # Su evolución impacta directamente la dinámica del IMACEC.
    (
        "F032.IMC.IND.Z.Z.EP18.SERV.Z.0.M",
        "Imacec servicios",
        "M",
        "Indice 2018=100",
        1
    ),

    # Refleja impuestos asociados a la producción y al consumo.
    # Permite contextualizar parte del crecimiento agregado.
    (
        "F032.IMC.IND.Z.Z.EP18.IMP.Z.0.M",
        "Imacec impuestos",
        "M",
        "Indice 2018=100",
        1
    ),

    # ==========================================
    # SECTOR EXTERNO
    # ==========================================

    # El cobre es la principal exportación chilena.
    # Variaciones en su precio afectan ingresos externos, inversión y crecimiento.
    (
        "F019.PPB.PRE.40.M",
        "Precio cobre",
        "M",
        "USD/libra",
        2
    ),

    # Influye sobre la competitividad de exportaciones e importaciones.
    # Además afecta expectativas e inversión.
    (
        "F073.TCO.PRE.Z.D",
        "Tipo cambio observado",
        "D",
        "CLP/USD",
        2
    ),

    # Mide los ingresos provenientes del principal producto exportado por Chile.
    # Mayores exportaciones suelen asociarse a mayor actividad económica.
    (
        "F068.B1.FLU.A1.0.C.N.Z.Z.Z.Z.6.0.M",
        "Exportaciones cobre",
        "M",
        "Millones USD",
        2
    ),

    # Captura la evolución de una industria estratégica para Chile.
    # El auge del litio puede impulsar exportaciones y crecimiento.
    (
        "F068.B1.FLU.A8.0.C.N.Z.Z.Z.Z.6.0.M",
        "Exportaciones litio",
        "M",
        "Millones USD",
        2
    ),

    # Permite observar la evolución de exportaciones no mineras.
    # Aporta diversificación al análisis externo.
    (
        "F068.B1.FLU.B.0.C.N.Z.Z.Z.Z.6.0.M",
        "Exportaciones agropecuarias",
        "M",
        "Millones USD",
        2
    ),

    # Sector exportador relevante para varias regiones del país.
    # Ayuda a evaluar la situación del sector agrícola.
    (
        "F068.B1.FLU.B1.0.C.N.Z.Z.Z.Z.6.0.M",
        "Exportaciones fruticolas",
        "M",
        "Millones USD",
        2
    ),

    # Las importaciones suelen aumentar cuando crece la demanda interna.
    # Funcionan como indicador complementario de actividad económica.
    (
        "F068.B1.FLU.Z.0.M.N.0.Z.Z.Z.6.0.M",
        "Importaciones CIF",
        "M",
        "Millones USD",
        2
    ),

    # Aproxima el comportamiento del consumo de bienes importados.
    # Puede anticipar expansiones o desaceleraciones de la demanda interna.
    (
        "F068.B1.FLU.Z.0.M.N.A.Z.Z.Z.6.0.M",
        "Importaciones consumo",
        "M",
        "Millones USD",
        2
    ),

    # ==========================================
    # MERCADO LABORAL
    # ==========================================

    # Existe una relación inversa entre desempleo y actividad económica.
    # Un aumento de la desocupación suele reflejar debilitamiento del ciclo.
    (
        "F049.DES.TAS.INE9.10.M",
        "Tasa desocupacion",
        "M",
        "Porcentaje",
        3
    ),

    # ==========================================
    # EXPECTATIVAS
    # ==========================================

    # Refleja las expectativas de los agentes económicos sobre el valor
    # futuro del dólar. Puede afectar decisiones de inversión y comercio.
    (
        "F089.TCN.PRE.14.M",
        "Expectativa tipo cambio 11 meses",
        "M",
        "CLP/USD",
        4
    ),

    # Captura las expectativas inflacionarias del mercado.
    # Anticipa decisiones de consumo, inversión y política monetaria.
    (
        "F089.IPC.V12.14.M",
        "Expectativa inflacion 11 meses",
        "M",
        "Porcentaje",
        4
    ),

]

