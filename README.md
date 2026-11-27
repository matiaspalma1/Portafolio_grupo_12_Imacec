# Portafolio Grupo 12 — Monitor de Coyuntura e IMACEC

**Ciencia de Datos para Economía**  
*Ingeniería Comercial — Universidad Diego Portales*  
**Integrantes:** Alexander Guerra, Matías Palma

---

## 1. Descripción del Proyecto

Este repositorio implementa una infraestructura reproducible de ingeniería de datos, econometría y aprendizaje automático orientada al monitoreo coyuntural y la proyección de la variación interanual del **Indicador Mensual de Actividad Económica (IMACEC)** de Chile.

El flujo integra de extremo a extremo: extracción automatizada desde la API oficial del Banco Central de Chile (**SieteRestWS**) $\rightarrow$ almacenamiento relacional normalizado en **SQLite** $\rightarrow$ transformaciones analíticas mediante **SQL** (`JOIN`, `GROUP BY`, `LAG`, `AVG OVER`) $\rightarrow$ evaluación fuera de muestra (*out-of-sample*) sin sesgo de anticipación en **Python** $\rightarrow$ generación automatizada de un **dashboard ejecutivo**.

- **Variable Objetivo:** Variación porcentual interanual (12 meses) del IMACEC empalmado (`F032.IMC.IND.Z.Z.EP18.Z.Z.0.M`).
- **Pregunta de Investigación:** *¿Es posible mejorar el pronóstico del crecimiento interanual del IMACEC incorporando indicadores sectoriales, externos, laborales, monetarios y de expectativas de Chile?*
- **Fuente Oficial:** Base de Datos Estadísticos (BDE) del Banco Central de Chile — **17 series macroeconómicas** (`2010-01-01` a `2026-08-31`).
- **Repositorio:** [github.com/matiaspalma1/Portafolio-grupo-12-Imacec](https://github.com/matiaspalma1/Portafolio-grupo-12-Imacec)

---

## 2. Estructura del Repositorio

```text
Portafolio-grupo-12-Imacec/
├── README.md                                <- Documentación técnica y guía de reproducción
├── requirements.txt                         <- Dependencias de Python fijadas para compatibilidad
├── .env.example                             <- Plantilla para credenciales de la API BCCh
├── .gitignore                               <- Exclusión de .env, bases locales y temporales
├── data/
│   └── coyuntura.db                         <- Base de datos SQLite (generada por el pipeline)
├── sql/
│   ├── 01_esquema.sql                       <- DDL: Creación de las 3 tablas relacionales e índices
│   └── 02_consulta.sql                      <- DML: Agregación mensual, JOIN y funciones de ventana
├── src/
│   ├── config.py                            <- Catálogo oficial de 17 series, 5 temas y rutas
│   ├── extraccion.py                        <- Cliente API SieteRestWS (BCCh) + generador --demo
│   ├── carga_db.py                          <- Orquestador ETL idempotente hacia SQLite
│   └── dashboard.py                         <- Generador reproducible del monitor visual ejecutivo
├── notebooks/
│   ├── 01_pipeline_datos.ipynb              <- Auditoría del flujo ETL, esquema SQLite y consultas SQL
│   ├── 02_analisis_ejemplo.ipynb            <- Anexo didáctico: plantilla base univariada en nivel
│   └── 03_analisis_coyuntura_y_modelos.ipynb<- Estudio principal: ADF, Horse Race OOS y proyección 24M
└── outputs/
    └── dashboard_coyuntura_imacec.png       <- Lámina ejecutiva generada desde SQLite

```

---

## 3. Requisitos y Configuración de Credenciales

### Requisitos previos

Se requiere **Python 3.10 o superior**. Desde la raíz del repositorio, crea un entorno virtual e instala las dependencias:

```bash

pip install -r requirements.txt

```

### Configuración de credenciales (API Banco Central de Chile)

El acceso a la API **BDE** requiere una cuenta gratuita en la [Base de Datos Estadísticos del BCCh](https://si3.bcentral.cl/Siete).

1. Copia la plantilla `.env.example` para crear tu archivo privado `.env`:

```bash

copy .env.example .env

```

2. Abre `.env` y completa tus credenciales:

```env
BCCH_USUARIO=tu_correo@ejemplo.cl
BCCH_PASSWORD=tu_contrasena_bde

```

---

## 4. Reproducción del Pipeline (Paso a Paso)

Para garantizar la reproducibilidad exacta de las tablas, métricas fuera de muestra y gráficos del estudio sin sesgo de anticipación (*zero look-ahead bias*), ejecuta los siguientes pasos desde la raíz del repositorio:

### Paso 1: Extracción e ingesta relacional en SQLite

Ejecuta la carga fijando la ventana histórica oficial del proyecto (`2010-01-01` a `2026-08-31`):

```bash
python src/carga_db.py --desde 2010-01-01 --hasta 2026-08-31

```

> **Modo Demo (sin credenciales API):** Si deseas verificar el funcionamiento técnico del pipeline sin configurar `.env`, ejecuta:
> ```bash
> python src/carga_db.py --demo --desde 2010-01-01 --hasta 2026-08-31
> 
> ```
> 
> 
> *Nota:* Si posteriormente deseas reemplazar los datos sintéticos por los oficiales del BCCh, elimina primero `data/coyuntura.db` (`rm data/coyuntura.db`) para evitar mezclar días hábiles sintéticos con feriados reales de Chile, y vuelve a ejecutar `python src/carga_db.py --desde 2010-01-01 --hasta 2026-08-31`.

### Paso 2: Generación del Dashboard Ejecutivo

Consulta directamente `data/coyuntura.db`, ejecuta el *backtesting* multi-horizonte del modelo principal `AR(10)` y exporta la lámina en `outputs/dashboard_coyuntura_imacec.png`:

```bash
python src/dashboard.py

```

### Paso 3: Ejecución de los Cuadernos de Investigación

Abre y ejecuta los cuadernos en orden secuencial:

1. **`notebooks/01_pipeline_datos.ipynb`**: Audita la estructura relacional en `coyuntura.db`, verifica la completitud temporal de las 17 series y ejecuta las consultas analíticas con `JOIN`, `GROUP BY`, `LAG` y `AVG OVER`.
2. **`notebooks/02_analisis_ejemplo.ipynb`**: Plantilla didáctica complementaria de modelación univariada base en nivel.
3. **`notebooks/02_analisis_coyuntura_y_modelos.ipynb`**: Desarrolla el estudio empírico completo:
* Diagnóstico visual de coyuntura (nivel, variación 12M y dinámica sectorial/TPM).
* Transformaciones estacionarias (`Var. % 12M` y `Cambio 12M en pp`) y pruebas **ADF** aplicadas exclusivamente sobre entrenamiento (`hasta 2022-08-01`).
* Competencia fuera de muestra (*Out-of-Sample Horse Race*) sobre **48 meses** (`2022-09` a `2026-08`) en esquema mensual ($h=1$) y bloques anuales ($12\text{M}$), evaluando **7 modelos** (`Ridge`, `Elastic Net`, `CART`, `Random Forest`, `AR(10)` óptimo por AIC en *train*, `ARIMA(2,0,1)` y `SARIMA(2,0,1)(1,0,0,12)`) frente a **3 benchmarks formales** (*Benchmark Ingenuo*, *Media Histórica Expansiva* y *Benchmark Cero 0.0%*).
* Proyección multi-horizonte a **24 meses** (`2026-09` a `2028-08`) con `AR(10)` e intervalos de confianza al 95% calibrados empíricamente sobre $K=24$ cortes OOS.



---

## 5. Arquitectura de Base de Datos y Cobertura Temática

La base de datos `data/coyuntura.db` sigue un esquema relacional normalizado en **3 tablas** (`sql/01_esquema.sql`):

* **`temas`**: Catálogo de los **5 ejes macroeconómicos** del estudio.
* **`series`**: Metadatos de las **17 series oficiales** (código BCCh, nombre, fuente institucional, frecuencia original `M`/`D` y unidad de medida).
* **`observaciones`**: Tabla de hechos unificada con clave primaria compuesta `(id_serie, fecha)` e índice temporal `idx_obs_fecha`.

### Cobertura del Catálogo Macroeconómico (17 Series)

| Eje Temático | Cantidad | Indicadores Incluidos | Frecuencia |
| --- | --- | --- | --- |
| **1. Actividad** | 7 | IMACEC Empalmado (objetivo) + 6 desagregaciones: Minería, Industria, Resto de Bienes, Comercio, Servicios e Impuestos | Mensual (`M`) |
| **2. Sector Externo** | 6 | Precio del Cobre, Tipo de Cambio Observado (`D`), Exportaciones (Cobre, Litio, Agropecuarias) e Importaciones de Consumo | `M` y `D` |
| **3. Mercado Laboral** | 1 | Tasa de Desocupación Nacional (INE) | Mensual (`M`) |
| **4. Expectativas** | 2 | Expectativas de Inflación a 11 meses y Tipo de Cambio Nominal a 11 meses (EEE) | Mensual (`M`) |
| **5. Política Monetaria** | 1 | Tasa de Política Monetaria (TPM) | Diaria (`D`) |

### Técnicas SQL Implementadas (`sql/02_consulta.sql`)

* **Homologación de frecuencias (`GROUP BY`):** Convierte las series diarias (TPM y Tipo de Cambio Observado) en promedios mensuales consistentes mediante `GROUP BY o.id_serie, strftime('%Y-%m', o.fecha)`.
* **Cruce relacional (`JOIN`):** Integra `observaciones`, `series` y `temas` en un panel analítico listo para consumo en Python.
* **Funciones de ventana (`LAG` y `AVG OVER`):** Calcula directamente en SQL la variación interanual a 12 meses (`LAG(..., 12) OVER (PARTITION BY id_serie ORDER BY mes)`) y el promedio móvil de 12 meses (`ROWS BETWEEN 11 PRECEDING AND CURRENT ROW`).

---

## 6. Consideraciones de Seguridad e Integridad

* **Protección de credenciales:** El archivo `.env` y cualquier variante `.env.*` están excluidos del control de versiones mediante `.gitignore`, dejando visible únicamente `.env.example`.
* **Enmascaramiento en registros y errores:** Todas las excepciones de red o autenticación durante la consulta a la API aplican la función `enmascarar()` (`src/extraccion.py`) para impedir que el usuario o contraseña aparezcan en consola o *tracebacks*.
* **Consultas parametrizadas:** Todas las interacciones SQL en `src/` y `notebooks/` utilizan consultas parametrizadas (`sqlalchemy.text` con parámetros enlazados `:inicio`, `:fin`, `:id`) e integridad referencial activa (`PRAGMA foreign_keys = ON`).
