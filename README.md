# uPoints Dashboard

Dashboard en tiempo real para uPoints — clientes, cajeros y puntos de fidelización.

## Stack
- **Streamlit** — UI interactiva
- **PostgreSQL** — conexión directa a la base de datos
- **Pandas** — procesamiento de datos

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

Define la variable de entorno `DB_URI` con la conexión a PostgreSQL:

```bash
export DB_URI="postgresql://user:pass@host:port/dbname"
```

O crea un archivo `~/.hermes/scripts/.pg_uri` con la URI.

## Ejecutar

```bash
streamlit run app.py --server.port 8501
```

## Features

- 📈 Clientes nuevos por marca (diario) con tasa de push notifications
- 🏪 Actividad de cajeros: puntos entregados, ranking, inactivos
- 📅 Filtros por fecha y marca
- 🔄 Datos en tiempo real desde PostgreSQL
- 📋 Vista de datos crudos para análisis detallado
