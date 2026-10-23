# Portafolio Grupo 12 — Monitor de Coyuntura e IMACEC

**Ciencia de Datos para Economía (ICO09425)**  
*Universidad Diego Portales*

---

## 1. Descripción del Proyecto

Este repositorio contiene la infraestructura de datos y el análisis macroeconómico de coyuntura orientado a la proyección del **Indicador Mensual de Actividad Económica (IMACEC)** en Chile. 

El proyecto implementa un pipeline de datos completo y reproducible: extracción automatizada desde la API del Banco Central de Chile (BCCh) $\rightarrow$ almacenamiento en una base de datos relacional SQLite $\rightarrow$ consultas analíticas avanzadas en SQL $\rightarrow$ modelación econométrica en Python $\rightarrow$ integración con Power BI.

* **Variable Objetivo:** IMACEC (Índice general de actividad económica).
* **Pregunta de Investigación:** ¿Qué grupo de variables económicas, domésticas o vinculadas al sector externo, posee mayor capacidad explicativa y predictiva sobre la evolución del IMACEC en Chile?
* **Fuente de Datos:** API SieteRestWS de la Base de Datos Estadísticos del Banco Central de Chile.
* **Canasta Seleccionada:** [Canasta Oficial BCCh (18 series)](https://si3.bcentral.cl/siete/ES/Siete/Canasta?idCanasta=HYHXA1175267)
* **Repositorio:** [github.com/matiaspalma1/Portafolio-grupo-12-Imacec](https://github.com/matiaspalma1/Portafolio-grupo-12-Imacec)

---

## 2. Estructura del Repositorio

```text
Portafolio_grupo_12_Imacec/
├── README.md                 <- Documentación principal del proyecto
├── requirements.txt          <- Librerías de Python requeridas
├── .env.example              <- Plantilla para credenciales de la API
├── .gitignore                <- Exclusión de credenciales y base de datos local
├── data/
│   └── coyuntura.db          <- Base de datos SQLite (generada por el pipeline)
├── sql/
│   ├── 01_esquema.sql        <- DDL: Creación de tablas e índices (3 tablas relacionales)
│   └── 02_consultas.sql      <- DML: Consultas analíticas (JOIN, GROUP BY, LAG, AVG OVER)
├── src/
│   ├── config.py             <- Catálogo oficial de las 18 series y rutas del proyecto
│   ├── extraccion.py         <- Extractor de la API SieteRestWS (BCCh) + Modo Demo
│   ├── carga_db.py           <- Orquestador del pipeline ETL e ingesta a SQLite
│   └── exportar_powerbi.py   <- Exportación de vistas/CSVs para el tablero interactivo
└── notebooks/
    ├── 01_pipeline_datos.ipynb   <- Validación del flujo ETL y consultas SQL
    └── 02_analisis_ejemplo.ipynb <- Análisis coyuntural, SARIMA y evaluación fuori di muestra
```    
---

## 3. Requisitos y Credenciales

Requisitos previos

Se requiere Python 3.10 o superior. Instala las dependencias ejecutando en la terminal:

```text
pip install -r requirements.txt
```

Configuración de credenciales

El acceso a la API del Banco Central de Chile requiere un usuario y contraseña gratuitos que se obtienen en el portal del BCCh Siete API.

Copia el archivo de plantilla .env.example para crear tu propio .env:

```text
cp .env.example .env
```

Abre el archivo .env y completa tus credenciales:

```text
BCCH_USUARIO=tu_correo@ejemplo.cl
BCCH_PASSWORD=tu_contraseña
```
---
## 4. Reproduccion de pipeline

Para ejecutar el pipeline completo de datos, asegurar la reproducibilidad sin sesgo de anticipación (look-ahead bias) y actualizar la base de datos local, sigue estos pasos desde la raíz del repositorio:

- Paso 1: Extracción e ingesta a SQLiteEjecuta la descarga con la fecha de corte oficial del proyecto (2026-08-31):Bashpython src/carga_db.py --hasta 2026-08-31
Nota: Si deseas realizar una prueba rápida sin credenciales, puedes usar el modo sintético:Bashpython src/carga_db.py --demo --hasta 2026-08-31

- Paso 2: Exportación de datos para Power BIGenera los archivos tabulares necesarios para la capa de visualización:Bashpython src/exportar_powerbi.py

- Paso 3: Cuadernos de Análisis y Modelación

Abre VS Code y ejecuta los cuadernos en orden:

1. notebooks/01_pipeline_datos.ipynb: 
Verifica la consistencia del esquema relacional y las consultas SQL.

2. notebooks/02_analisis_ejemplo.ipynb: 
Realiza la exploración coyuntural del IMACEC, ajusta el modelo SARIMA y calcula las métricas de precisión fuera de muestra ($RMSE$ / $MAE$) frente al benchmark ingenuo.
---

## 5. Arquitectura de la Base de Datos y SQL

La base de datos relacional coyuntura.db consta de un diseño normalizado estructurado en 3 tablas:

- temas: Clasificación temática en 4 ejes (Actividad, Sector Externo, Mercado Laboral, Expectativas).
- series: Catálogo con las 18 series macroeconómicas, sus frecuencias y unidades de medida.
- observaciones: Tabla de hechos unificada (clave primaria compuesta: id_serie, fecha).

Técnicas SQL Implementadas (sql/02_consultas.sql)

- Agregación diaria a mensual: Colapso de series financieras/diarias (ej. Tipo de Cambio) a promedios mensuales con GROUP BY strftime('%Y-%m', fecha).
- Cruce Relacional (JOINs): Unión multi-tabla para reportes de coyuntura con metadatos completos.
- Funciones de Ventana: Cálculo de variaciones interanuales a 12 meses utilizando LAG(..., 12) OVER (PARTITION BY id_serie ORDER BY mes) y promedios móviles de 3 meses para suavizamiento de volatilidad.
---

## 6. Consideraciones de Seguridad

El archivo .env está estrictamente excluido del control de versiones mediante .gitignore para proteger las credenciales privadas.

Las excepciones producidas durante la extracción aplican la función enmascarar() para evitar filtraciones accidentales de credenciales en los logs o tracebacks.