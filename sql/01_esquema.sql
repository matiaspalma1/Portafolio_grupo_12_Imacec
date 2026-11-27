-- =============================================================================
-- ESQUEMA DE LA BASE DE DATOS RELACIONAL DEL PROYECTO (COYUNTURA IMACEC)
-- Motor: SQLite 3
-- Descripción: Define las 3 tablas normalizadas (temas, series, observaciones),
--              restricciones de integridad referencial, índices de consulta y
--              el poblamiento inicial idempotente de las 5 áreas temáticas.
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- 1. TABLA CATÁLOGO: TEMAS
-- Agrupa las 17 series macroeconómicas en 5 dimensiones analíticas.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS temas (
    id_tema     INTEGER PRIMARY KEY,
    tema        TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 2. TABLA CATÁLOGO: SERIES
-- Registra los metadatos de las 17 series extraídas desde la API SieteRestWS
-- del Banco Central de Chile (definidas en src/config.py).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS series (
    id_serie   TEXT PRIMARY KEY,
    nombre     TEXT NOT NULL,
    fuente     TEXT NOT NULL DEFAULT 'Banco Central de Chile',
    frecuencia TEXT NOT NULL CHECK (frecuencia IN ('D', 'M', 'T', 'A')),
    unidad     TEXT NOT NULL,
    id_tema    INTEGER NOT NULL REFERENCES temas(id_tema) ON UPDATE CASCADE
);

-- -----------------------------------------------------------------------------
-- 3. TABLA DE HECHOS: OBSERVACIONES
-- Almacena los registros históricos por serie y fecha (2010-01-01 a 2026-08-31).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS observaciones (
    id_serie TEXT NOT NULL REFERENCES series(id_serie) ON UPDATE CASCADE ON DELETE CASCADE,
    fecha    DATE NOT NULL,
    valor    REAL,
    PRIMARY KEY (id_serie, fecha)
);

-- -----------------------------------------------------------------------------
-- 4. ÍNDICES DE OPTIMIZACIÓN PARA CONSULTAS ANALÍTICAS Y JOINS
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_obs_fecha ON observaciones(fecha);
CREATE INDEX IF NOT EXISTS idx_series_tema ON series(id_tema);

-- -----------------------------------------------------------------------------
-- 5. POBLAMIENTO INICIAL IDEMPOTENTE DE LAS 5 ÁREAS TEMÁTICAS
-- -----------------------------------------------------------------------------
INSERT INTO temas (id_tema, tema, descripcion) VALUES
    (1, 'Actividad',          'IMACEC agregado (variable objetivo) y desagregación sectorial'),
    (2, 'Sector Externo',     'Precio del cobre, tipo de cambio observado y balanza comercial'),
    (3, 'Mercado Laboral',    'Indicadores de empleo y tasa de desocupación nacional (INE)'),
    (4, 'Expectativas',       'Expectativas de inflación y tipo de cambio a 11 meses (EEE)'),
    (5, 'Politica Monetaria', 'Tasa de Política Monetaria (TPM) y condiciones financieras')
ON CONFLICT(id_tema) DO UPDATE SET
    tema = excluded.tema,
    descripcion = excluded.descripcion;