# Portafolio Grupo 12 — Monitor de Coyuntura e IMACEC

# Portafolio Grupo 12 — Monitor de Coyuntura e IMACEC

**Ciencia de Datos para Economía (ICO09425)**  
*Escuela de Ingeniería Comercial — Universidad Diego Portales*  
**Integrantes:** Alexander Guerra, Matias Palma
**Ciencia de Datos para Economía**  
*Universidad Diego Portales*

---

## 1. Descripción del Proyecto

Este repositorio contiene la infraestructura de datos y el análisis macroeconómico de coyuntura orientado a la proyección de la variación interanual del **Indicador Mensual de Actividad Económica (IMACEC)** en Chile.

El proyecto implementa un pipeline de datos completo y reproducible: extracción automatizada desde la API del Banco Central de Chile (BCCh) $\rightarrow$ almacenamiento en una base de datos relacional SQLite $\rightarrow$ consultas analíticas en SQL $\rightarrow$ modelación econométrica y evaluación fuera de muestra en Python $\rightarrow$ generación automatizada del dashboard ejecutivo en Python.

- **Variable Objetivo:** Variación interanual (%) del IMACEC empalmado.
- **Pregunta de Investigación:** ¿Es posible mejorar el pronóstico del crecimiento interanual del IMACEC utilizando indicadores sectoriales y macroeconómicos de Chile?
- **Fuente de Datos:** API de la Base de Datos Estadísticos del Banco Central de Chile (17 series oficiales).
- **Repositorio:** [github.com/matiaspalma1/Portafolio-grupo-12-Imacec](https://github.com/matiaspalma1/Portafolio-grupo-12-Imacec)

---

## 2. Estructura del Repositorio

```text
Portafolio_grupo_12_Imacec/
├── README.md                              <- Documentación principal del proyecto
├── requirements.txt                       <- Librerías de Python requeridas
├── .env.example                           <- Plantilla para credenciales de la API
├── .gitignore                             <- Exclusión de credenciales y base de datos local
├── data/
│   └── coyuntura.db                       <- Base de datos SQLite (generada por el pipeline)
├── sql/
│   ├── 01_esquema.sql                     <- DDL: Creación de tablas e índices (3 tablas relacionales)
│   └── 02_consultas.sql                   <- DML: Consultas analíticas (JOIN, GROUP BY, LAG, AVG OVER)
├── src/
│   ├── config.py                          <- Catálogo oficial de las 19 series y rutas del proyecto
│   ├── extraccion.py                      <- Extractor de la API SieteRestWS (BCCh) + Modo Demo
│   ├── carga_db.py                        <- Orquestador del pipeline ETL e ingesta a SQLite
│   └── dashboard.py                       <- Generación reproducible del dashboard ejecutivo en Python
├── notebooks/
│   ├── 01_pipeline_datos.ipynb            <- Validación del flujo ETL y consultas SQL
│   └── 02_coyuntura_y_modelos.ipynb       <- Diagnóstico, pruebas ADF, modelos y evaluación out-of-sample
└── outputs/
    └── dashboard_coyuntura_imacec.png     <- Dashboard ejecutivo generado desde SQLite
```

---

## 3. Requisitos y Credenciales

### Requisitos previos
Se requiere Python 3.10 o superior. Instala las dependencias ejecutando en la terminal:

```bash
pip install -r requirements.txt
```

### Configuración de credenciales
El acceso a la API del Banco Central de Chile requiere un usuario y contraseña gratuitos que se obtienen en el portal del [BCCh Siete API](https://si3.bcentral.cl/Siete/es/Siete/API).

1. Copia el archivo de plantilla `.env.example` para crear tu propio `.env`:

```bash
cp .env.example .env
```

2. Abre el archivo `.env` y completa tus credenciales:

```env
BCCH_USUARIO=tu_correo@ejemplo.cl
BCCH_PASSWORD=tu_contraseña
```

---

## 4. Reproducción del Pipeline

Para ejecutar el pipeline completo de datos de principio a fin, asegurar la reproducibilidad sin sesgo de anticipación (*look-ahead bias*) y regenerar el tablero ejecutivo, ejecuta los siguientes comandos en orden desde la raíz del repositorio:

### Paso 1: Extracción e ingesta a SQLite
Ejecuta la descarga con la fecha de corte oficial del proyecto (`2026-08-31`):

```bash
python src/carga_db.py --hasta 2026-08-31
```

*(Nota: Si deseas realizar una prueba técnica sin credenciales, puedes usar el modo sintético con `python src/carga_db.py --demo --hasta 2026-08-31`).*

### Paso 2: Generación del Dashboard Ejecutivo en Python
Consulta directamente `data/coyuntura.db`, evalúa el pronóstico fuera de muestra y exporta el tablero en `outputs/dashboard_coyuntura_imacec.png`:

```bash
python src/dashboard.py
```

### Paso 3: Cuadernos de Análisis y Modelación
Ejecuta los notebooks en orden para reproducir las tablas y gráficos del informe:

1. `notebooks/01_pipeline_datos.ipynb`: Verifica la consistencia del esquema relacional, cobertura temporal y consultas SQL.
2. `notebooks/02_coyuntura_y_modelos.ipynb`: Ejecuta el diagnóstico de coyuntura, pruebas de estacionariedad (ADF), estimación de modelos (SARIMA y modelos con variables explicativas domésticas vs. externas) y evaluación fuera de muestra frente al *benchmark* ingenuo.

---

## 5. Arquitectura de la Base de Datos y SQL

La base de datos relacional `data/coyuntura.db` consta de un diseño normalizado estructurado en 3 tablas:

- **`temas`**: Clasificación temática en 5 ejes (*Actividad*, *Sector Externo*, *Mercado Laboral*, *Expectativas* y *Política Monetaria*).
- **`series`**: Catálogo con las 19 series macroeconómicas, sus frecuencias y unidades de medida.
- **`observaciones`**: Tabla de hechos unificada (clave primaria compuesta: `id_serie`, `fecha`).

### Técnicas SQL Implementadas (`sql/02_consultas.sql`)
- **Agregación diaria a mensual:** Colapso de series diarias (ej. Tipo de Cambio Observado) a promedios mensuales mediante `GROUP BY strftime('%Y-%m', fecha)`.
- **Cruce Relacional (`JOIN`):** Unión multi-tabla para reportes de coyuntura con metadatos completos.
- **Funciones de Ventana:** Cálculo de variaciones interanuales a 12 meses utilizando `LAG(..., 12) OVER (PARTITION BY id_serie ORDER BY mes)` y promedios móviles con `AVG(...) OVER (...)`.

---

## 6. Consideraciones de Seguridad

- El archivo `.env` está estrictamente excluido del control de versiones mediante `.gitignore` para proteger las credenciales privadas.
- Las excepciones producidas durante la extracción aplican la función `enmascarar()` para evitar filtraciones accidentales de credenciales en los logs o tracebacks.
El archivo .env está estrictamente excluido del control de versiones mediante .gitignore para proteger las credenciales privadas.

Las excepciones producidas durante la extracción aplican la función enmascarar() para evitar filtraciones accidentales de credenciales en los logs o tracebacks.
