# Portafolio Grupo 12 - IMACEC

## 1. Descripcion


## Monitor de Coyuntura y Proyección Macroeconómica

Proyecto correspondiente al curso Ciencia de Datos para Economía.

### Variable objetivo

La variable objetivo del proyecto es el Indicador Mensual de Actividad Económica (IMACEC) de Chile.

### Pregunta de investigación

¿Qué grupo de variables económicas, domésticas o vinculadas al sector externo, posee mayor capacidad explicativa sobre la evolución del IMACEC en Chile?

### Fuente de datos

Las series económicas utilizadas en este proyecto serán obtenidas desde la Base de Datos Estadísticos del Banco Central de Chile.

### Base de datos seleccionada

[Ver selección de series en el Banco Central de Chile](https://si3.bcentral.cl/siete/ES/Siete/Canasta?idCanasta=HYHXA1175267)

### Repositorio

https://github.com/matiaspalma1/Portafolio-grupo-12-Imacec

## 2. Requisitos


Asegúrate de contar con Python 3.11 o superior. Instala las dependencias requeridas ejecutando:

pip install -r requirements.txt

## 3. Credenciales


Completa tu correo y clave del Banco Central de Chile en el archivo, usando el ejemplo de .env.example

BCCH_USUARIO=tu_correo@ejemplo.cl

BCCH_PASSWORD=tu_password

## 4. Reproduccion


Para descargar las 18 series desde la API del Banco Central, generar la base de datos relacional SQLite y ejecutar las consultas de coyuntura con fecha de corte oficial (2026-08-31), ejecuta:

1. Carga a la base SQLite
python src/carga_db.py --hasta 2026-08-31

2. Verificación del estado de la base de datos
python src/revisar_db.py

3. Ejecución de consultas SQL de coyuntura (JOIN + GROUP BY + Ventana)
python src/probar_consultas.py

## 5. Estructura


data/: Contiene la base de datos relacional coyuntura.db (excluida de Git por .gitignore).

sql/: Archivos .sql con el esquema relacional (01_esquema.sql) y las consultas de agregación y variaciones (02_consultas.sql).

src/: Scripts del pipeline (config.py, extraccion.py, carga_db.py).

notebooks/: Notebooks de análisis y exploración de coyuntura.
