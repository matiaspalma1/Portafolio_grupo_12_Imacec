-- ============================================================
-- Esquema de la base de datos relacional del proyecto
-- Motor: SQLite
-- ============================================================

-- 1. Tabla Catálogo: Temas
-- Define las 4 áreas temáticas del Banco Central de Chile usadas en el proyecto
CREATE TABLE IF NOT EXISTS temas (
    id_tema     INTEGER PRIMARY KEY,
    tema        TEXT NOT NULL,
    descripcion TEXT
);

-- 2. Tabla Catálogo: Series
-- Registra las 18 series macroeconómicas extraídas del BCCh
CREATE TABLE IF NOT EXISTS series (
    id_serie   TEXT PRIMARY KEY,
    nombre     TEXT NOT NULL,
    frecuencia TEXT NOT NULL,
    unidad     TEXT,
    id_tema    INTEGER REFERENCES temas(id_tema)
);

-- 3. Tabla de Hechos: Observaciones
-- Almacena las mediciones históricas por fecha y serie
CREATE TABLE IF NOT EXISTS observaciones (
    id_serie TEXT NOT NULL REFERENCES series(id_serie),
    fecha    DATE NOT NULL,
    valor    REAL,
    PRIMARY KEY (id_serie, fecha)
);

-- 4. Optimización: Índice para acelerar agregaciones y funciones de ventana por fecha
CREATE INDEX IF NOT EXISTS idx_obs_fecha ON observaciones(fecha);

-- 5. Poblamiento inicial idempotente de los 4 temas del proyecto
INSERT OR IGNORE INTO temas (id_tema, tema, descripcion) VALUES
    (1, 'Actividad',       'Variables de actividad económica agregada y sectorial'),
    (2, 'Sector Externo',  'Precios de commodities, tipo de cambio y comercio exterior'),
    (3, 'Mercado Laboral', 'Indicadores de empleo y tasa de desocupación'),
    (4, 'Expectativas',   'Expectativas del mercado sobre inflación y tipo de cambio');