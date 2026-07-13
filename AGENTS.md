# AGENTS.md — Contexto Compartido del Proyecto

> **Este archivo es la "mente compartida" del proyecto.**
> Todo sub-agente que trabaje en este proyecto DEBE leer este archivo primero.
> Contiene la identidad, estructura, reglas, preferencias del usuario y criterios
> de diseño para que cualquier agente sepa cómo actuar en cada situación.

---

## 1. IDENTIDAD DEL PROYECTO

**Nombre:** Agente de Búsqueda Financiera
**Ubicación:** `C:\VANIER\AGENTE DE BUSQUEDA`
**Propósito:** Bot de noticias financieras especializado en el **mercado de valores de EE.UU.** (NYSE, NASDAQ).
Recopila, filtra, analiza y envía noticias que afectan a la economía americana, sus acciones e índices.

**Idioma de salida:** Español (tono profesional, conciso).
**Idioma de comunicación con el usuario:** Español.

### Dos sistemas separados:

| Sistema | Nombre | Función | Horario | Fuentes |
|---------|--------|---------|---------|---------|
| **1** | Sector Económico del Día | Reporte diario de eventos macro programados (calendario) | 7-8 AM NY | **SOLO Finviz Calendar** |
| **2** | Último Minuto | Alertas en tiempo real, **solo de la watchlist** | Cada 15 min (nube) / al instante (local) | Investing, Yahoo Finance, Finviz, Bloomberg RSS |

> **Cambios 13 jul 2026:** Sistema 1 = solo Finviz (sin filtro de país; se eliminó `_is_us_relevant` del pipeline diario porque borraba eventos válidos). Sistema 2 = modo `watchlist.only` (solo noticias de la lista) + dedup entre fuentes por similitud de tokens con prioridad de fuente. Anti-mensajes-viejos en `fetch_updates` (filtro de antigüedad + confirmación server-side). `bot_local.py` corre ambos sistemas. Cron Sistema 2 cada 15 min. Watchlist reemplazada por 40 tickers del usuario.

---

## 2. ESTRUCTURA DE CARPETAS Y ARCHIVOS

```
C:\VANIER\AGENTE DE BUSQUEDA\
│
├── AGENTS.md                  ← ESTE ARCHIVO (contexto compartido)
├── MANUAL.md                  ← Manual de instrucciones del usuario
├── README.md                  ← Documentación general
├── config.yaml                ← Configuración del agente (proveedor, fuentes, watchlist, failover)
├── .env                       ← API keys (NO commitear)
├── .env.example               ← Template de API keys
├── requirements.txt           ← Dependencias Python
├── run_report.py              ← Entry point principal (ejecuta ambos sistemas)
├── app.py                     ← Dashboard Streamlit
├── test_formats.py            ← Pruebas de formato para Telegram
├── install_tasks.bat          ← Instalación de tareas programadas (Windows)
│
├── src/                       ← Código fuente del agente
│   ├── __init__.py
│   ├── config.py              ← Gestión de configuración + .env + rutas
│   ├── llm.py                 ← Fábrica de proveedores LLM + failover multi-provider
│   ├── analyzer.py            ← Análisis de noticias con LLM (JSON output)
│   ├── formatter.py           ← Formatea mensajes de Telegram (Sección 1 y 2)
│   ├── notifier.py            ← Envío a Telegram (split 4096, sanitize markdown)
│   ├── report.py              ← Orquestador: scrapea → filtra → analiza → envía
│   ├── watchlist.py           ← Gestión de empresas seguidas + matching
│   ├── telegram_bot.py        ← Bot interactivo (comandos, lenguaje natural, audios)
│   ├── backup.py              ← Backup automático de todo lo generado
│   ├── chat.py                ← Chat LLM para el dashboard
│   ├── system_prompt.md       ← Prompt del sistema para el LLM analizador
│   │
│   ├── providers/             ← Implementaciones de proveedores LLM
│   │   ├── __init__.py
│   │   ├── base.py            ← Clase abstracta LLMProvider
│   │   ├── catalog.py         ← Catálogo de proveedores disponibles
│   │   ├── openai_compat.py   ← Groq, Cerebras, OpenRouter (API OpenAI-compatible)
│   │   ├── gemini.py          ← Google Gemini (SDK nativo de Google)
│   │   └── anthropic.py       ← Anthropic Claude (no usado actualmente)
│   │
│   └── sources/               ← Scrapers de fuentes de noticias
│       ├── __init__.py
│       ├── base.py            ← NewsItem dataclass + BaseSource ABC
│       ├── forex_factory.py   ← Forex Factory (calendario macro, JSON API)
│       ├── yahoo_calendar.py  ← Yahoo Finance (calendario, HTML table)
│       ├── finviz_calendar.py ← Finviz (calendario, JSON embebido)
│       ├── investing.py       ← Investing.com (noticias, RSS)
│       ├── yahoo_finance.py   ← Yahoo Finance (noticias, RSS)
│       ├── finviz.py          ← Finviz (noticias, HTML)
│       └── bloomberg_rss.py   ← Bloomberg (noticias, RSS)
│
├── data/                      ← Datos generados (NO commitear excepto config)
│   ├── cache/                 ← Caches diarios (se resetean a medianoche NY)
│   │   ├── sent_alerts_YYYY-MM-DD.json    ← Hashes de alertas ya enviadas
│   │   ├── analyzed_YYYY-MM-DD.json       ← Cache de noticias ya analizadas (ahorra tokens)
│   │   └── telegram_offset.txt            ← Offset de Telegram (no procesar mismo mensaje 2x)
│   ├── history/               ← Historial de reportes diarios
│   │   ├── report_YYYY-MM-DD_HH-MM.json
│   │   └── report_YYYY-MM-DD_HH-MM.txt
│   └── backup/                ← Backup automático de TODO
│       ├── report_YYYY-MM-DD_HH-MM-SS.txt/json
│       ├── alert_YYYY-MM-DD_HH-MM-SS.txt/json
│       ├── telegram_log_YYYY-MM-DD.txt
│       ├── execution_YYYY-MM-DD.log
│       └── config_backup_YYYY-MM-DD_HH-MM-SS.yaml
│
├── ui/                        ← Pestañas del dashboard Streamlit
│   ├── __init__.py
│   ├── tab_news.py
│   ├── tab_report.py
│   ├── tab_config.py
│   ├── tab_providers.py
│   └── tab_chat.py
│
└── .github/workflows/         ← GitHub Actions (ejecución automática)
    ├── system1-daily.yml      ← Cron 7 AM NY (reporte diario)
    └── system2-breaking.yml   ← Cron cada hora 24/7 (alertas)
```

---

## 3. DÓNDE GUARDAR CADA COSA

| Tipo de contenido | Carpeta/archivo | Formato |
|-------------------|-----------------|---------|
| Reporte diario generado | `data/backup/report_TS.txt` + `.json` | Automático vía `backup.save_report_backup()` |
| Alerta enviada a Telegram | `data/backup/alert_TS.txt` + `.json` | Automático vía `backup.save_alert_backup()` |
| Log de comandos Telegram | `data/backup/telegram_log_DATE.txt` | Automático vía `backup.save_telegram_log()` |
| Log de ejecución | `data/backup/execution_DATE.log` | Automático vía `backup.save_execution_log()` |
| Historial de reportes | `data/history/report_TS.txt` + `.json` | Automático vía `report._save_history()` |
| Cache de enviadas | `data/cache/sent_alerts_DATE.json` | Automático |
| Cache de analizadas | `data/cache/analyzed_DATE.json` | Automático |
| Offset de Telegram | `data/cache/telegram_offset.txt` | Automático |
| Configuración del usuario | `config.yaml` | Vía `config.save_config()` |
| API keys | `.env` | Vía `config.set_env_var()` |
| Watchlist (empresas seguidas) | `config.yaml` sección `watchlist` | Vía `watchlist._save_watchlist()` |

**REGLA:** Todo lo que el agente genera se guarda automáticamente en `data/backup/`.
Nunca escribir archivos sueltos en la raíz del proyecto. Si necesitas guardar algo nuevo,
usar `data/` con la subcarpeta apropiada.

---

## 4. ARQUITECTURA — PROVEEDORES LLM

### Cadena de failover (3 proveedores nativos, NO OpenRouter)

```
Groq (primario) → Cerebras (failover 1) → Gemini (failover 2)
```

| Proveedor | Modelo | API Key env | Protocolo |
|-----------|--------|-------------|-----------|
| Groq | `llama-3.3-70b-versatile` | `GROQ_API_KEY` | OpenAI-compatible |
| Cerebras | `gpt-oss-120b` | `CEREBRAS_API_KEY` | OpenAI-compatible |
| Google Gemini | `gemini-flash-lite-latest` | `GEMINI_API_KEY` | Google genai SDK nativo |

**Lógica de failover** (`src/llm.py` → `chat()`):
1. Construye cadena `[groq, cerebras, gemini]` — solo los que tienen API key
2. Prueba cada uno en orden
3. Si falla (429, rate limit, timeout, connection, 503, overloaded, capacity) → prueba el siguiente
4. Si todos fallan → RuntimeError

**Transcripción de audios:** Groq Whisper (`whisper-large-v3`, language="es")

### Configuración (`config.yaml`)
```yaml
active:
  provider: Groq
  model: llama-3.3-70b-versatile
  temperature: 0.3
  max_tokens: 1500
  reasoning: true
failover:
  enabled: true
  providers:
    - provider: Cerebras
      model: gpt-oss-120b
    - provider: Google Gemini
      model: gemini-flash-lite-latest
```

---

## 5. ARQUITECTURA — PIPELINE DE NOTICIAS

### Sistema 1: Reporte Diario (Sector Económico del Día)
```
fetch_calendar_sources()  → Forex Factory + Yahoo Calendar + Finviz Calendar
        ↓
_is_us_relevant()         → Filtra eventos que NO afectan a USA (PIB UK, tasa Japón, etc.)
        ↓
Filtro estrellas ≥ 2      → Solo eventos con 2+ estrellas
        ↓
analyze_batch()            → LLM analiza todo el lote, devuelve JSON con sentimiento, confianza, etc.
        ↓
format_daily_report()      → Formatea mensaje de Telegram
        ↓
send_to_telegram()         → Envía
        ↓
save_report_backup()       → Guarda en data/backup/
```

### Sistema 2: Alertas en Tiempo Real (Último Minuto)
```
fetch_news_sources()       → Investing + Yahoo Finance + Finviz + Bloomberg RSS
        ↓
deduplicate()              → Quita duplicados por título
        ↓
Priorizar watchlist        → Noticias que mencionan empresas seguidas van primero
        ↓
Por cada noticia:
  ├─ ¿Ya enviada?          → skip (sent_alerts cache)
  ├─ ¿Ya analizada?        → usar cache (NO gastar tokens)
  ├─ Analizar con LLM      → analyze_single() → JSON
  ├─ ¿Puede mover mercado? → Si no, descartar
  ├─ Umbral dinámico       → 55% si es watchlist, 70% si no
  └─ Enviar + backup       → send_to_telegram() + save_alert_backup()
```

### Cache de tokens (CRÍTICO para ahorro)
- `data/cache/analyzed_DATE.json`: guarda TODAS las noticias analizadas (enviadas o no)
- Si una noticia ya está en cache → NO se llama al LLM (ahorro ~80% tokens)
- Se resetea a medianoche NY (no UTC)
- Función `_ny_today()` usa `dateutil.tz.gettz("America/New_York")`

---

## 6. BOT DE TELEGRAM INTERACTIVO

### Capacidades
- **Comandos slash:** `/add`, `/remove`, `/list`, `/report`, `/breaking`, `/publica`, `/status`, `/help`
- **Lenguaje natural:** "agrega Apple", "quita Tesla", "genera el reporte", "busca noticias"
- **Audios (voice messages):** Transcripción automática con Groq Whisper
- **Publicar en canal:** El bot es asistente de administración del canal — publica texto, fotos, documentos, videos
- **Procesamiento:** NLP rápido sin LLM para patrones comunes; LLM solo para casos ambiguos

### Comandos disponibles

| Comando | Acción | ¿Usa LLM? |
|---------|--------|-----------|
| `/add AAPL` o `/add Apple` | Añade empresa a watchlist | No |
| `/remove TSLA` o `/remove Tesla` | Quita empresa | No |
| `/list` | Muestra watchlist | No |
| `/report` | Genera reporte diario AHORA | Sí (1 llamada batch) |
| `/breaking` | Busca noticias AHORA | Sí (N llamadas) |
| `/publica <texto>` | Publica mensaje en el canal | No |
| `/status` | Estado del agente | No |
| `/help` | Lista de comandos | No |

### Publicar en el canal (asistente de administración)
El bot publica lo que el usuario le diga, de 3 formas:
1. **Texto:** `publica: <mensaje>` o `/publica <mensaje>` (también: publicar, posta, comparte, anuncia, envía al canal)
2. **Audio:** decir "publica, <mensaje>" — Whisper transcribe, se detecta la orden (insensible a acentos: "Pública" = "publica"), se extrae el resto y se publica
3. **Multimedia:** foto, documento, video o animación → se auto-publica vía `copyMessage` con formato AlphaBot

**Detección de publicación insensible a acentos:** función `_extract_publish_text()` en `telegram_bot.py`:
- Regex normaliza acentos antes del match (`_strip_accents`)
- Acepta cualquier puntuación después de la palabra clave (`:`, `,`, `.`, `;`, espacio)
- Preserva acentos del mensaje a publicar (no los destruye al normalizar)
- Auto-desplegable (`<blockquote expandable>`) si el texto > 300 caracteres

### Seguridad
- Responde a ambos: `TELEGRAM_CHAT_ID` (canal) y `TELEGRAM_USER_ID` (chat privado del usuario)
- `authorized_chats` set en `fetch_updates()` acepta ambos
- Ignora mensajes de otros chats

### Bug conocido y resuelto
- `parse_mode=None` causa error 400 en Telegram → usar `payload.pop("parse_mode", None)` (omitir la clave, NO poner None)

---

## 7. WATCHLIST — EMPRESAS SEGUIDAS

### Gestión
- Se guarda en `config.yaml` sección `watchlist.companies`
- Se gestiona por Telegram: acepta ticker (AAPL) o nombre (Apple)
- Diccionario `NAME_TO_TICKER` en `watchlist.py` con 50+ empresas para resolución automática
- En GitHub Actions, los cambios se commitean al repo automáticamente

### Impacto en el análisis
- Noticias que mencionan empresas de la watchlist → **prioridad** (se analizan primero)
- Umbral reducido: **55%** (vs 70% normal) → más sensible a estas empresas
- El LLM recibe contexto: "El usuario sigue de cerca: AAPL (Apple), TSLA (Tesla)..."

### Empresas por defecto (config.yaml)
AAPL, NVDA, MSFT, AMZN, META, GOOGL, TSLA, JPM, NFLX, PLTR

---

## 8. FORMATOS DE TELEGRAM (HTML + BLOCKQUOTE EXPANDABLE)

> **IMPORTANTE:** Los mensajes se envían en formato **HTML** (no Markdown).
> `parse_mode="HTML"` en notifier.py.
> Se usan `<blockquote expandable>` (Bot API 7.4, mayo 2024) para contenido colapsable.
> `disable_web_page_preview=True` para evitar previews de enlaces.

### Footer estándar (TODAS las secciones)
```
🤖 AlphaBot · {saludo}
```
- 5-12 AM NY → "buen día"
- 12-19 AM NY → "buenas tardes"
- else → "buenas noches"
- **NO** incluir enlaces ni disclaimers en el footer. Solo AlphaBot + saludo.

### Sección 1 — Sector Económico del Día

- Encabezado: `📊 SECTOR ECONÓMICO DEL DÍA` + día + fecha
- Cada noticia: titular visible + detalle en `<blockquote expandable>` (plegable)
- Dentro del desplegable: 📝 Resumen, 📈 Análisis, 🟢 Beneficiados, 🔴 Perjudicados, 🔗 Enlace
- **Estrellas:** las que pone el calendario web (`item.stars`) — el LLM NO las inventa
- **Enlace:** siempre dentro del desplegable (no filtrar URLs de Forex Factory)
- Footer: `🤖 AlphaBot · {saludo}`

### Sección 2 — Último Minuto

- Encabezado: `🚨 ÚLTIMO MINUTO` + día + fecha
- Estrellas 1-5 **direccional** asignadas por el LLM:
  - Positivas: más estrellas = mejor noticia
  - Negativas: más estrellas = más grave
  - Volátiles: magnitud del movimiento esperado
- Importancia mostrada por **porcentaje** Y por **estrellas 1-5**
- Detalle en `<blockquote expandable>`
- Footer: `🤖 AlphaBot · {saludo}`

### Seguimiento de resultados (results followup)
- También usa `<blockquote expandable>` para el análisis
- Muestra: Forecast vs Anterior vs Actual
- ✅ BEAT / ❌ MISS / ➡️ EN LÍNEA
- Footer: `🤖 AlphaBot · {saludo}`

---

## 9. PREFERENCIAS DEL USUARIO Y REGLAS DE COMPORTAMIENTO

### Comunicación
- **Siempre responder en español**
- Tono cercano pero profesional
- Explicar qué se hizo, qué faltó, sin adornos innecesarios

### Diseño
- **APIs nativas/directas** (no OpenRouter) — el usuario las prefiere por velocidad
- **Ahorro de tokens es prioridad** — usar cache, no re-analizar, no re-enviar
- **Backup automático de todo** — nunca perder contenido generado
- **Gestión por Telegram** — el usuario controla todo desde su móvil
- **Add/remove de watchlist por ticker O nombre** — facilitar al máximo

### Scheduling
- Sistema 1: SOLO 7-8 AM Nueva York (no gastar tokens todo el día)
- Sistema 2: Cada hora, 24/7
- Timezone: `America/New_York` SIEMPRE (no UTC del servidor)

### Errores conocidos a evitar
1. **NUNCA** poner `parse_mode: None` en payload de Telegram → omitir la clave con `.pop()`
2. **NUNCA** reportar el fallback a texto plano como fallo si el reintento funcionó
3. Verificar que los nombres de modelos existen en cada proveedor antes de configurar
4. En Windows, `zoneinfo` necesita `tzdata` instalado (en requirements.txt)

### Tareas completadas (10 julio 2026)
1. ✅ **Sección 1 noticias colapsables:** Implementado con `<blockquote expandable>` (HTML)
2. ✅ **Sección 1 seguimiento de resultados:** Implementado en `src/results_tracker.py`
   (track_events_from_report → check_pending_results → fetch_actual_results → reanalyze → send followup)
3. ✅ **Sección 2 estrellas 1-5 direccional:** Escala 1-5 implementada (positivas/negativas/volátiles)
4. ✅ **Metodología de inversión Buffett/Graham/Lynch:** Integrada en `src/system_prompt.md` y `src/analyzer.py`
5. ✅ **Footer AlphaBot + saludo:** Sin enlaces ni disclaimers, solo "🤖 AlphaBot · {saludo}"
6. ✅ **Estrellas Sección 1 del calendario web:** Usa `item.stars` (NO las inventa el LLM)
7. ✅ **Enlaces dentro del desplegable:** Siempre incluye el enlace, no filtra Forex Factory
8. ✅ **Link preview desactivado:** `disable_web_page_preview=True`
9. ✅ **Bot como asistente de canal:** Publica texto, fotos, documentos, videos
10. ✅ **Publicación por audio insensible a acentos:** "Pública" = "publica" (regex con `_strip_accents`)

---

## 10. CONVENCIONES DE CÓDIGO

- Python 3.12
- Type hints en todas las funciones (`from __future__ import annotations`)
- Docstrings en español, concisos
- Comentarios explicativos solo donde no es obvio
- Imports: stdlib → third-party → local (relativos con `.`)
- NewsItem es la estructura de datos central (`src/sources/base.py`)
- El LLM siempre devuelve JSON — función `_parse_json()` en analyzer.py lo extrae
- **Formato Telegram: HTML** (no Markdown) — `parse_mode="HTML"`
- Tags HTML usadas: `<b>`, `<i>`, `<blockquote expandable>`, `<code>`, `<a href="...">`
- Sanitizar HTML antes de enviar (`notifier._sanitize_html()`)
- `disable_web_page_preview=True` en todos los envíos
- Split de mensajes a 4096 chars sin cortar palabras (`notifier._split_message()`)

### Cómo ejecutar
```bash
# Reporte diario (Sistema 1)
python run_report.py --daily --no-reasoning

# Alertas tiempo real (Sistema 2)
python run_report.py --breaking --no-reasoning

# Ambos
python run_report.py --all --no-reasoning

# Dry-run (no envía a Telegram, solo muestra)
python run_report.py --breaking --no-send

# Dashboard
streamlit run app.py
```

### Variables de entorno necesarias (.env)
```
GROQ_API_KEY=...
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_USER_ID=...
```

---

## 11. INSTRUCCIONES PARA SUB-AGENTES

Si eres un sub-agente trabajando en este proyecto:

1. **Lee este archivo completo** antes de hacer cualquier cosa
2. **Respeta la estructura de carpetas** — guarda en `data/` lo que sea dato
3. **Escribe código que encaje con el existente** — mismo estilo, mismas convenciones
4. **No rompas lo que funciona** — si modificas algo existente, entiende primero cómo funciona
5. **El ahorro de tokens es sagrado** — no llames al LLM innecesariamente
6. **El backup es automático** — no necesitas guardarlo manualmente, las funciones de `backup.py` lo hacen
7. **Responde en español** al agente principal que te invocó
8. **Si investigas algo (web), devuelve hallazgos estructurados y accionables**
9. **Si escribes código, prueba que funcione** antes de reportar completado
10. **Cita `file_path:line_number` cuando referencies código existente**
