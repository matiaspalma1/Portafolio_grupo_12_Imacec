-- CONSULTA PRINCIPAL DE COYUNTURA MACROECONÓMICA

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
