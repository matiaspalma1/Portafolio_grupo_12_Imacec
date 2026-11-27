-- =============================================================================
-- CONSULTAS ANALÍTICAS DE COYUNTURA MACROECONÓMICA (PROYECCIÓN DEL IMACEC)
-- Motor: SQLite 3 | Base de datos: data/coyuntura.db
--
-- Requisitos técnicos cubiertos:
--  1. Cruces relacionales (JOIN) entre observaciones, series y temas.
--  2. Agregaciones temporales con GROUP BY (colapso diario->mensual y anual).
--  3. Funciones de ventana (LAG 12M para variación interanual y AVG OVER para
--     promedios móviles de 12 meses y 3 meses).
-- =============================================================================


-- =============================================================================
-- CONSULTA 1 (PRINCIPAL): PANEL CONSOLIDADO MENSUAL (VAR. % 12M Y PROM. MÓVIL 12M)
-- Replica la extracción analítica utilizada por los notebooks y src/dashboard.py
-- =============================================================================
WITH mensual AS (
    SELECT
        o.id_serie,
        strftime('%Y-%m', o.fecha) AS mes,
        AVG(o.valor) AS valor_mensual
    FROM observaciones AS o
    WHERE o.fecha BETWEEN '2010-01-01' AND '2026-08-31'
    GROUP BY o.id_serie, mes
),
indicadores AS (
    SELECT
        m.id_serie,
        m.mes,
        m.valor_mensual,
        LAG(m.valor_mensual, 12) OVER (
            PARTITION BY m.id_serie
            ORDER BY m.mes
        ) AS valor_hace_12m,
        100.0 * (
            m.valor_mensual / NULLIF(
                LAG(m.valor_mensual, 12) OVER (
                    PARTITION BY m.id_serie
                    ORDER BY m.mes
                ),
                0
            ) - 1.0
        ) AS var_12m_pct,
        AVG(m.valor_mensual) OVER (
            PARTITION BY m.id_serie
            ORDER BY m.mes
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS pm_12m
    FROM mensual AS m
)
SELECT
    t.tema,
    i.id_serie,
    s.nombre AS serie,
    s.frecuencia,
    s.unidad,
    i.mes || '-01' AS fecha,
    ROUND(i.valor_mensual, 3) AS valor_mensual,
    ROUND(i.var_12m_pct, 2) AS var_12m_pct,
    ROUND(i.pm_12m, 3) AS pm_12m
FROM indicadores AS i
JOIN series AS s ON s.id_serie = i.id_serie
JOIN temas AS t ON t.id_tema = s.id_tema
ORDER BY t.id_tema, s.nombre, i.mes;


-- =============================================================================
-- CONSULTA 2 (JOIN + SUBCONSULTA): ÚLTIMO DATO DISPONIBLE POR INDICADOR
-- Entrega la fotografía más reciente de las 17 series al cierre del estudio
-- =============================================================================
SELECT
    t.tema,
    s.id_serie,
    s.nombre AS serie,
    o.fecha AS ultima_fecha,
    ROUND(o.valor, 3) AS ultimo_valor,
    s.unidad
FROM observaciones AS o
JOIN series AS s ON s.id_serie = o.id_serie
JOIN temas AS t ON t.id_tema = s.id_tema
WHERE o.fecha = (
    SELECT MAX(o2.fecha)
    FROM observaciones AS o2
    WHERE o2.id_serie = o.id_serie
      AND o2.fecha BETWEEN '2010-01-01' AND '2026-08-31'
)
ORDER BY t.id_tema, s.nombre;


-- =============================================================================
-- CONSULTA 3 (GROUP BY): RESUMEN ANUAL POR SERIE MACROECONÓMICA
-- Consolida promedios anuales y conteo de observaciones válidas por año
-- =============================================================================
SELECT
    t.tema,
    s.nombre AS serie,
    strftime('%Y', o.fecha) AS anio,
    ROUND(AVG(o.valor), 2) AS promedio_anual,
    COUNT(o.valor) AS n_observaciones,
    s.unidad
FROM observaciones AS o
JOIN series AS s ON s.id_serie = o.id_serie
JOIN temas AS t ON t.id_tema = s.id_tema
WHERE o.fecha BETWEEN '2010-01-01' AND '2026-08-31'
GROUP BY t.tema, s.nombre, anio, s.unidad
ORDER BY t.tema, s.nombre, anio;


-- =============================================================================
-- CONSULTA 4 (FUNCIÓN DE VENTANA): PROMEDIO MÓVIL DE 3 MESES (TENDENCIA CORTA)
-- Suaviza fluctuaciones de alta frecuencia para análisis de impulso trimestral
-- =============================================================================
WITH mensual AS (
    SELECT
        o.id_serie,
        strftime('%Y-%m', o.fecha) AS mes,
        AVG(o.valor) AS valor_mensual
    FROM observaciones AS o
    WHERE o.fecha BETWEEN '2010-01-01' AND '2026-08-31'
    GROUP BY o.id_serie, mes
)
SELECT
    t.tema,
    s.nombre AS serie,
    m.mes,
    ROUND(m.valor_mensual, 2) AS valor_mensual,
    ROUND(
        AVG(m.valor_mensual) OVER (
            PARTITION BY m.id_serie
            ORDER BY m.mes
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS promedio_movil_3m
FROM mensual AS m
JOIN series AS s ON s.id_serie = m.id_serie
JOIN temas AS t ON t.id_tema = s.id_tema
ORDER BY t.id_tema, s.nombre, m.mes;