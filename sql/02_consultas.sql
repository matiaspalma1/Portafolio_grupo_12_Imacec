-- ============================================================
-- CONSULTAS DE COYUNTURA MACROECONÓMICA
-- Monitor de Coyuntura y Proyección Macroeconómica (ICO09425)
--
-- Requisitos cumplidos en este archivo:
--  1. JOINs entre tablas de catálogo y hechos.
--  2. Agregaciones con GROUP BY (colapso diario-mensual y anual).
--  3. Funciones de ventana (LAG para variación 12M y AVG OVER para promedio móvil 3M).
-- ============================================================


-- ============================================================
-- CONSULTA 1 (PRINCIPAL): REPORTE CONSOLIDADO CON VARIACIÓN INTERANUAL
-- Combina GROUP BY (diario a mensual), JOIN y Función de Ventana (LAG)
-- ============================================================
WITH mensual AS (
    -- Agrupa series diarias a nivel mensual mediante promedio
    SELECT 
        o.id_serie,
        strftime('%Y-%m', o.fecha) AS mes,
        AVG(o.valor) AS valor_promedio
    FROM observaciones AS o
    GROUP BY o.id_serie, mes
),
variaciones AS (
    -- Calcula la variación interanual (%) comparando contra hace 12 meses
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


-- ============================================================
-- CONSULTA 2 (JOIN): ÚLTIMO DATO DISPONIBLE POR CADA INDICADOR
-- Muestra la foto más reciente de la coyuntura
-- ============================================================
SELECT 
    t.tema,
    s.nombre AS serie,
    o.fecha AS ultima_fecha,
    ROUND(o.valor, 2) AS ultimo_valor,
    s.unidad
FROM observaciones AS o
JOIN series AS s ON s.id_serie = o.id_serie
JOIN temas AS t ON t.id_tema = s.id_tema
WHERE o.fecha = (
    SELECT MAX(o2.fecha) 
    FROM observaciones AS o2 
    WHERE o2.id_serie = o.id_serie
)
ORDER BY t.tema, s.nombre;


-- ============================================================
-- CONSULTA 3 (GROUP BY): PROMEDIO ANUAL POR SERIE
-- Resumen ejecutivo anual para tablas de síntesis
-- ============================================================
SELECT 
    s.nombre AS serie,
    strftime('%Y', o.fecha) AS anio,
    ROUND(AVG(o.valor), 2) AS promedio_anual,
    COUNT(*) AS n_observaciones
FROM observaciones AS o
JOIN series AS s ON s.id_serie = o.id_serie
GROUP BY s.nombre, anio
ORDER BY s.nombre, anio;


-- ============================================================
-- CONSULTA 4 (FUNCIÓN DE VENTANA): PROMEDIO MÓVIL DE 3 MESES
-- Suavizamiento para series volátiles antes de graficar
-- ============================================================
WITH mensual AS (
    SELECT 
        id_serie,
        strftime('%Y-%m', fecha) AS mes,
        AVG(valor) AS valor_mensual
    FROM observaciones
    GROUP BY id_serie, mes
)
SELECT 
    id_serie,
    mes,
    ROUND(valor_mensual, 2) AS valor_mensual,
    ROUND(AVG(valor_mensual) OVER (
        PARTITION BY id_serie
        ORDER BY mes
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS promedio_movil_3m
FROM mensual
ORDER BY id_serie, mes;