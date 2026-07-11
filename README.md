# 📊 Market Daily — Agente de Búsqueda Financiera

Agente automatizado que scrapea fuentes financieras reales (Yahoo Finance, Finviz, Investing, Bloomberg, Forex Factory), analiza las noticias con un LLM (Hermes 4, DeepSeek, Gemini, etc.), predice el sentimiento y el impacto en activos, y envía reportes diarios a tu canal de Telegram.

## Funcionalidades

- **Reporte diario automático (8:00 AM)** — noticias de 2-3 estrellas con sentimiento, contexto, puntos clave, activos beneficiados/perjudicados
- **Alertas de última hora** — solo noticias de alto impacto que pueden mover el mercado (Trump habla, mega-acuerdos, Fed, etc.)
- **Scraping real** — lee hora y noticias publicadas en las páginas ANTES de analizar
- **Multi-proveedor** — usa cualquier modelo: OpenRouter, OpenAI, Anthropic, Gemini, Groq, DeepSeek, Ollama local...
- **Dashboard interactivo** — configurar todo desde una interfaz web (buscar proveedor, pegar API key, elegir modelo, ver noticias, chatear)
- **Filtro inteligente de 2 pasos** — relevancia → impacto. Solo lo que realmente importa.

---

## Instalación rápida

### 1. Requisitos

- **Python 3.10+** (recomendado 3.11+)
- **Windows** (también funciona en Mac/Linux)

### 2. Entorno virtual

```bash
cd "C:\VANIER\AGENTE DE BUSQUEDA"

# Crear entorno virtual
python -m venv venv

# Activarlo (Windows)
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Crear tu bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot`
3. Sigue las instrucciones: ponle un nombre y un username
4. **Copia el token** que BotFather te da (algo como `123456789:ABCdefGHI...`)
5. Para obtener tu **chat_id**:
   - Manda un mensaje a tu bot recién creado
   - Busca **@userinfobot** en Telegram y mándale `/start`
   - Te dirá tu `chat_id` (un número, ej. `123456789`)
   - Si es un canal, el chat_id empieza con `-100` (ej. `-1001234567890`)

### 4. Configurar el .env

```bash
# Copia la plantilla
copy .env.example .env

# Edita .env y pon tus claves:
# TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
# TELEGRAM_CHAT_ID=123456789

# Y al menos un proveedor LLM:
# OPENROUTER_API_KEY=sk-or-...
```

### 5. Abrir el dashboard

```bash
streamlit run app.py
```

Se abre en **http://localhost:8501**. Desde ahí:

1. **Pestaña Proveedores** → busca tu proveedor → pega la API key → elige modelo → activar
2. **Pestaña Configuración** → ajusta fuentes, estrellas mínimas, horario
3. **Pestaña Noticias** → scrapear para ver qué extrae el agente
4. **Pestaña Reporte** → generar reporte → enviar a Telegram
5. **Pestaña Chat** → consultas ad-hoc

---

## Reporte automático (Windows Task Scheduler)

Para que el reporte se envíe solo cada día a las 8:00 AM (aunque no abras el dashboard):

### Método 1: Task Scheduler de Windows

1. Abre **Programador de tareas** (Task Scheduler)
2. **Crear tarea básica**
3. Nombre: `Market Daily Report`
4. Desencadenador: **Diariamente** a las **08:00**
5. Acción: **Iniciar un programa**
   - Programa: `C:\VANIER\AGENTE DE BUSQUEDA\venv\Scripts\python.exe`
   - Argumentos: `run_report.py`
   - Directorio: `C:\VANIER\AGENTE DE BUSQUEDA`

### Método 2: Acceso directo en el inicio (alternativa)

Crea un archivo `iniciar_agente.bat`:

```bat
@echo off
cd /d "C:\VANIER\AGENTE DE BUSQUEDA"
call venv\Scripts\activate
python run_report.py
pause
```

Y ponlo en `Inicio → Programas → Inicio` si quieres que corra al encender.

---

## Probar manualmente

```bash
# Reporte completo (scrapea + analiza + envía a Telegram)
python run_report.py

# Solo generar, NO enviar (para pruebas)
python run_report.py --no-send

# Sin razonamiento profundo (más rápido)
python run_report.py --no-reasoning
```

---

## Estructura del proyecto

```
├── app.py                # Dashboard Streamlit
├── run_report.py         # Reporte automático (Task Scheduler 8am)
├── config.yaml           # Configuración (puente dashboard ↔ agente)
├── .env                  # API keys (NUNCA subir a git)
├── .env.example          # Plantilla de variables
├── requirements.txt      # Dependencias Python
├── README.md             # Este archivo
├── mockup_telegram.html  # Preview visual del formato de Telegram
├── src/
│   ├── config.py         # Lee/escribe config.yaml + .env
│   ├── llm.py            # Fábrica del proveedor LLM activo
│   ├── analyzer.py      # Razonamiento + filtro 2 pasos
│   ├── formatter.py      # Formato Estilo C para Telegram
│   ├── notifier.py       # Envío a Telegram
│   ├── report.py         # Orquestador del pipeline
│   ├── providers/        # Capa multi-proveedor
│   │   ├── catalog.py    # Catálogo preconfigurado + modelos recomendados
│   │   ├── base.py       # Interfaz común
│   │   ├── openai_compat.py  # OpenRouter, OpenAI, Groq, DeepSeek, Ollama...
│   │   ├── anthropic.py      # Claude
│   │   └── gemini.py         # Gemini
│   └── sources/          # Scrapers
│       ├── base.py       # Interfaz común + NewsItem
│       ├── forex_factory.py   # Calendario con estrellas (JSON)
│       ├── investing.py       # Calendario económico
│       ├── yahoo_finance.py   # Noticias RSS
│       ├── finviz.py          # Noticias mercado
│       └── bloomberg_rss.py   # Noticias RSS (esquiva paywall)
├── ui/                   # Pestañas del dashboard
│   ├── tab_providers.py  # Buscador + API key + elegir modelo
│   ├── tab_config.py     # Fuentes, estrellas, horario
│   ├── tab_news.py       # Noticias scrapeadas en vivo
│   ├── tab_report.py     # Generar + enviar + historial
│   └── tab_chat.py       # Chat ad-hoc
└── data/
    ├── cache/            # Caché (no repetir análisis)
    └── history/          # Reportes guardados (JSON + texto)
```

---

## Proveedores soportados

| Proveedor | Tipo | Coste | Modelos notables |
|---|---|---|---|
| OpenRouter | OpenAI-compat | Free + pago | Hermes 4, DeepSeek R1, Llama 3.3, Gemini Flash |
| OpenAI | OpenAI | Pago | GPT-4o, o1, o3 |
| Anthropic | Anthropic | Pago | Claude 3.5 Sonnet, Opus |
| Google Gemini | Gemini | Free + pago | Gemini 2.0 Flash, Pro |
| Groq | OpenAI-compat | Free | Llama, Mixtral (ultra rápido) |
| Together AI | OpenAI-compat | Free crédito | Llama, Qwen, DeepSeek |
| DeepSeek | OpenAI-compat | Barato | DeepSeek V3/R1 |
| Mistral | OpenAI-compat | Free + pago | Mistral Large |
| Fireworks | OpenAI-compat | Barato | Modelos open-source |
| Cerebras | OpenAI-compat | Barato | Llama (inferencia rápida) |
| Ollama | OpenAI-compat | Gratis (local) | Cualquiera (requiere Ollama) |
| LM Studio | OpenAI-compat | Gratis (local) | Cualquiera (requiere LM Studio) |

---

## Formato del mensaje en Telegram (Estilo C)

Cada noticia incluye:
- 📊 Encabezado con número, ⭐ estrellas, etiqueta de impacto, nombre del evento
- 🕐 Hora + bandera + sentimiento (🟢/📉/➡️/⚠️) con % de confianza
- 📝 Contexto (1-2 líneas para entender sin salir de Telegram)
- 📋 Puntos clave (forecast, previo, riesgo, impacto)
- 📊 Impacto en activos: beneficiados 🟢 / perjudicados 🔴 con tickers
- 🔗 Enlace clickeable a la fuente original

Para ver un preview visual, abre `mockup_telegram.html` en tu navegador.

---

## Limitaciones conocidas

- **Bloomberg**: paywall en HTML → solo vía RSS. Si el feed no aporta, se deshabilita y se priorizan las demás fuentes.
- **Investing.com**: puede bloquear scraping → headers realistas + reintentos. Forex Factory es el fallback más estable.
- **Rate limits de modelos gratuitos**: el código reintenta con backoff. Si un modelo falla, puedes cambiar en el dashboard en 2 clics.
- **Modelos locales (Ollama/LM Studio)**: requieren tener el servidor corriendo antes de usar el agente.

---

## Licencia

Uso personal. No redistribuir sin permiso.
