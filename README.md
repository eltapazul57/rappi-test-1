# Rappi Operations Intelligence

Sistema de analisis conversacional para datos operacionales de Rappi. Permite a equipos no tecnicos hacer preguntas en lenguaje natural y obtener respuestas respaldadas por SQL, ademas de generar automaticamente un reporte semanal de insights.

---

## Requisitos previos

| Herramienta | Version minima | Instalacion |
|---|---|---|
| Python | 3.11 | [python.org](https://www.python.org/downloads/) |
| Poetry | 1.8+ | `curl -sSL https://install.python-poetry.org \| python3 -` |
| Node.js | 18 | [nodejs.org](https://nodejs.org/) |
| OpenAI API key | — | [platform.openai.com](https://platform.openai.com/) |

---

## Instalacion y ejecucion

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd rappi-test-1
```

### 2. Configurar variables de entorno

```bash
cp backend/.env.example backend/.env
```

Edita `backend/.env` y completa tu API key de OpenAI:

```
OPENAI_API_KEY=sk-...
```

El resto de variables tienen valores por defecto adecuados para desarrollo local.

### 3. Instalar y arrancar el backend

```bash
cd backend
poetry install
poetry run uvicorn app:app --reload
```

El backend corre en **http://localhost:8000**.

Al iniciar, verifica en los logs que la base de datos se cargo correctamente:

```
Database ready — 12573 metric rows, 1242 order rows.
```

Si ves `Startup data load failed`, el archivo Excel no esta en `data/rappi_data.xlsx`.

El archivo `data/rappi_data.xlsx` esta incluido en el repositorio. La base de datos SQLite (`data/rappi.db`) no se commitea — el backend la genera automaticamente desde el Excel la primera vez que arranca. No hay ningun paso manual para crearla.

Si en algun momento eliminas o pierdes `data/rappi.db`, simplemente reinicia el backend y lo regenerara desde el Excel. Si actualizas el Excel, elimina `data/rappi.db` y reinicia el backend para que tome los nuevos datos.

### 4. Instalar y arrancar el frontend

Abre una segunda terminal:

```bash
cd frontend
npm install
npm run dev
```

El frontend corre en **http://localhost:5173**.

### Diferencias por sistema operativo

En **macOS y Linux** los comandos anteriores funcionan sin modificaciones.

En **Windows**, si usas PowerShell o CMD, reemplaza la instalacion de Poetry por:

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

Y asegurate de que Poetry este en el PATH reiniciando la terminal o agregando manualmente `%APPDATA%\Python\Scripts` a la variable de entorno `Path`.

---

## Variables de entorno

Todas las variables viven en `backend/.env`. Unicamente `OPENAI_API_KEY` es obligatoria.

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `OPENAI_API_KEY` | *(requerida)* | Clave de la API de OpenAI |
| `OPENAI_MODEL` | `gpt-4o` | Modelo usado para generacion de SQL y respuestas |
| `MAX_TOKENS` | `1000` | Tokens maximos por respuesta del LLM |
| `MAX_RETRIES` | `2` | Reintentos de generacion SQL ante errores |
| `MAX_CONVERSATION_HISTORY` | `10` | Turnos de historial enviados al LLM en cada request |
| `ANOMALY_THRESHOLD` | `0.10` | Cambio minimo semana a semana para marcar una anomalia (10%) |
| `TREND_MIN_WEEKS` | `3` | Semanas consecutivas en declive para marcar una tendencia |
| `BENCHMARK_STD_THRESHOLD` | `1.0` | Desviaciones estandar minimas para marcar en benchmarking |
| `CORRELATION_MIN_ABS` | `0.3` | Correlacion absoluta minima para reportar |
| `CORS_ORIGINS` | `http://localhost:5173` | Origenes permitidos del frontend (separados por coma) |

---

## Arquitectura

### Estructura del repositorio

```
/
├── backend/
│   ├── app.py                   # FastAPI — endpoints /chat, /insights, /health
│   ├── graph/
│   │   ├── __init__.py          # Ensamblado y compilacion del grafo LangGraph
│   │   ├── state.py             # ChatState TypedDict compartido entre nodos
│   │   ├── intent_classifier.py # Nodo: clasifica la intencion del mensaje
│   │   ├── sql_generator.py     # Nodo: genera SQL a partir del lenguaje natural
│   │   ├── sql_executor.py      # Nodo: ejecuta el SQL contra SQLite
│   │   ├── error_handler.py     # Nodo: maneja errores y controla reintentos
│   │   ├── response_formatter.py# Nodo: convierte resultados a lenguaje de negocio
│   │   └── routing.py           # Funciones de enrutamiento condicional
│   ├── insights.py              # Motor de insights (pandas puro, sin LLM)
│   ├── db.py                    # Carga Excel a SQLite, crea vista orders_enriched
│   ├── prompts.py               # System prompt para generacion de SQL
│   ├── config.py                # Configuracion centralizada desde .env
│   ├── pyproject.toml           # Dependencias (Poetry)
│   └── .env.example             # Plantilla de variables de entorno
├── frontend/
│   └── src/
│       ├── App.jsx              # Componente raiz — navegacion por pestanas
│       ├── api.js               # Cliente fetch para /chat e /insights
│       └── components/
│           ├── Chat.jsx         # Interfaz de chat conversacional
│           └── Insights.jsx     # Interfaz del reporte semanal
├── data/
│   └── rappi_data.xlsx          # Datos operacionales (incluido en el repositorio)
└── README.md
```

### Stack tecnologico

| Capa | Tecnologia | Razon |
|---|---|---|
| Frontend | React 19 + Vite | Servidor de desarrollo rapido, bundle minimo |
| Backend | FastAPI | Asincrono, documentacion automatica en `/docs`, bajo boilerplate |
| Orquestacion LLM | LangGraph | Flujo de grafo explicito con logica de reintento sin codigo espagueti |
| LLM | GPT-4o | Mejor precision en generacion de SQL en la practica |
| Base de datos | SQLite | Cero infraestructura, se carga desde Excel al arrancar |
| Motor de insights | pandas | Deterministico, rapido, sin costo de API para el analisis |
| Gestion de dependencias | Poetry | Lockfile reproducible, entornos aislados |

---

## Bot conversacional

### Por que LangGraph

El flujo del bot requiere ramificacion condicional (segun la intencion del usuario), reintento ante errores SQL con contexto del error anterior, y pasos secuenciales con estado compartido. Implementar esto con llamadas directas al LLM produce codigo dificil de mantener. LangGraph modela cada paso como un nodo con responsabilidad unica y define el flujo mediante aristas, lo que hace el comportamiento auditabie y facil de extender.

### Flujo del grafo

```
Mensaje del usuario
        |
        v
intent_classifier          <- GPT-4o, temperatura=0, max_tokens=5
        |
        +-- "data_query" --> sql_generator --> sql_executor
        |                         ^                 |
        |                         |    error        v
        |                    error_handler <--------+  (max 2 reintentos)
        |                                           | exito
        |                                           v
        +-- "general" ------------------------> response_formatter
                                                    |
                                                    v
                                          respuesta + datos + sql
```

### Nodos

**`intent_classifier`**
Clasifica si el mensaje requiere consulta SQL (`data_query`) o es una pregunta conversacional (`general`). Usa un prompt de eleccion forzada de una sola palabra a temperatura 0 para garantizar determinismo.

**`sql_generator`**
Recibe el esquema completo de la base de datos, las definiciones de metricas y los mapeos de terminos de negocio. Genera una consulta SQLite valida. En un reintento, el error anterior se adjunta al mensaje para que el modelo se autocorrija.

**`sql_executor`**
Ejecuta el SQL contra SQLite. Devuelve filas serializadas en JSON o una cadena de error para ser procesada por el `error_handler`.

**`error_handler`**
Registra el fallo e incrementa `retry_count`. El enrutamiento condicional en `route_retry` redirige al `sql_generator` si no se alcanzo `MAX_RETRIES`, o al `response_formatter` con un mensaje de fallback si se agoto.

**`response_formatter`**
Recibe los resultados (o el fallback) y produce una respuesta en lenguaje de negocio de 3 a 6 oraciones. Siempre incluye una sugerencia de analisis proactivo. Responde en el idioma del usuario.

### Memoria conversacional

Cada sesion tiene un `session_id` generado en el servidor en el primer request y almacenado en el cliente. El servidor mantiene los ultimos `MAX_CONVERSATION_HISTORY` turnos por sesion en memoria y los adjunta a cada llamada al LLM, habilitando contexto multi-turno.

---

## Motor de insights

Corre enteramente en pandas, sin LLM ni costo de API. Las cinco funciones de analisis producen un reporte Markdown ejecutivo.

**`detect_anomalies`**
Cambio semana a semana entre `L1W_ROLL` y `L0W_ROLL`. Marca zona+metrica donde `|cambio| > 10%`. Usa delta absoluto cuando el denominador es cercano a cero para evitar porcentajes sin sentido. Invierte la logica de mejora/deterioro para metricas donde menor es mejor (`Restaurants Markdowns / GMV`).

**`detect_concerning_trends`**
Recorre las columnas de semanas hacia atras desde `L0W_ROLL` y cuenta semanas consecutivas en declive. Marca si la racha es mayor o igual a `TREND_MIN_WEEKS`. Estos son problemas estructurales, no fluctuaciones puntuales.

**`benchmark_zones`**
Agrupa zonas por `COUNTRY + ZONE_TYPE + METRIC`. Calcula el z-score de cada zona respecto a su grupo de pares. Marca las zonas con `|z| > 1.0` como alto o bajo rendimiento. Requiere minimo 3 zonas en el grupo para ser estadisticamente significativo.

**`compute_correlations`**
Pivota `input_metrics` a una matriz zona x metrica usando `L0W_ROLL`. Calcula correlaciones de Pearson entre pares de metricas. Reporta los pares con `|r| > 0.3`.

**`detect_opportunities`**
Cruza zonas con crecimiento fuerte en pedidos (>=10% en 5 semanas) contra zonas con bajo rendimiento vs sus pares en al menos una metrica. Estas zonas tienen demanda llegando pero brechas operacionales que arriesgan el crecimiento.

### Estructura del reporte

```
## Zonas de Alta Prioridad        <- zonas marcadas en ZONE_PRIORITIZATION
## Resumen Ejecutivo              <- 1 hallazgo por tipo de analisis, paises distintos
## Acciones Recomendadas          <- top 3 por urgencia x impacto
## Oportunidades                  <- zonas con crecimiento y brecha operacional
## Anomalias                      <- deterioros y mejoras significativos
## Tendencias Preocupantes        <- declives estructurales multi-semana
## Benchmarking                   <- zonas bajo y alto rendimiento vs pares
## Relaciones Clave entre Metricas <- pares de metricas correlacionados
```

---

## API

### `POST /chat`

```json
Request:  { "message": "string", "session_id": "string | null" }
Response: { "answer": "string", "data": [...], "sql": "string | null", "session_id": "string" }
```

`data` contiene las filas del resultado SQL como array JSON. `sql` contiene la consulta generada. Si `session_id` es null, se crea una nueva sesion y se devuelve su ID.

### `POST /insights`

```json
Response: { "report": "string (Markdown)" }
```

Ejecuta las 5 funciones de analisis y devuelve el reporte ejecutivo completo.

### `GET /health`

```json
Response: { "status": "ok", "database": "cargada | no cargada" }
```

### Endpoints de debug (solo desarrollo)

| Endpoint | Descripcion |
|---|---|
| `GET /debug/tables` | Tablas y vistas con conteo de filas |
| `GET /debug/preview/{tabla}` | Primeras N filas de `input_metrics`, `orders` u `orders_enriched` |
| `GET /debug/metrics` | Nombres de metricas distintos en la base de datos |
| `GET /debug/insights/anomalies` | Salida cruda de deteccion de anomalias |
| `GET /debug/insights/trends` | Salida cruda de deteccion de tendencias |
| `GET /debug/insights/benchmarks` | Salida cruda de benchmarking |
| `GET /debug/insights/correlations` | Salida cruda de correlaciones |
| `GET /debug/insights/opportunities` | Salida cruda de oportunidades |

Documentacion interactiva disponible en **http://localhost:8000/docs**.

---

## Estimacion de costos (OpenAI)

El sistema usa GPT-4o. Los precios de referencia son $2.50 / 1M tokens de entrada y $10.00 / 1M tokens de salida.

Cada request al chat implica entre 2 y 4 llamadas al LLM segun el flujo:

| Llamada | Tokens de entrada aprox. | Tokens de salida aprox. |
|---|---|---|
| `intent_classifier` | ~500 | ~5 |
| `sql_generator` | ~2,000 | ~150 |
| `response_formatter` | ~3,000 | ~200 |

Un request tipico consume alrededor de **5,500 tokens de entrada y 355 de salida**, lo que equivale a aproximadamente **$0.017 por mensaje** con GPT-4o.

El reporte de insights no usa el LLM, tiene costo cero.

| Escenario de uso | Costo estimado |
|---|---|
| 10 mensajes/dia, 1 usuario | ~$0.17/dia, ~$5/mes |
| 50 mensajes/dia, equipo pequeno | ~$0.85/dia, ~$25/mes |
| 200 mensajes/dia, uso intensivo | ~$3.40/dia, ~$100/mes |

Estos valores asumen requests simples. Preguntas que activan reintentos SQL (hasta 2 intentos adicionales) pueden duplicar el costo por request. Puedes reducir costos ajustando `MAX_TOKENS` y `MAX_CONVERSATION_HISTORY` en el `.env`.
