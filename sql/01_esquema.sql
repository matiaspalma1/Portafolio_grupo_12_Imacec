-- ==========================================
-- ESQUEMA RELACIONAL DEL PROYECTO
-- ==========================================

-- 1. Tabla Catálogo: Temas
CREATE TABLE IF NOT EXISTS temas (
    id_tema INTEGER PRIMARY KEY,
    tema TEXT NOT NULL,
    descripcion TEXT
);

-- 2. Tabla Catálogo: Series
CREATE TABLE IF NOT EXISTS series (
    id_serie TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    frecuencia TEXT NOT NULL,
    unidad TEXT,
    id_tema INTEGER REFERENCES temas(id_tema)
);

-- 3. Tabla de Hechos: Observaciones
CREATE TABLE IF NOT EXISTS observaciones (
    id_serie TEXT NOT NULL REFERENCES series(id_serie),
    fecha DATE NOT NULL,
    valor REAL,
    PRIMARY KEY (id_serie, fecha)
);

-- Insertar los 4 temas definidos en config.py
INSERT OR IGNORE INTO temas (id_tema, tema, descripcion) VALUES
(1, 'Actividad', 'Variables de actividad económica agregada y sectorial'),
(2, 'Sector Externo', 'Precios de commodities, tipo de cambio y comercio exterior'),
(3, 'Mercado Laboral', 'Indicadores de empleo y tasa de desocupación'),
(4, 'Expectativas', 'Expectativas del mercado sobre inflación y tipo de cambio');