# 📖 Manual de Instrucciones — AlphaBot (Agente de Búsqueda Financiera)

> **Última actualización:** 14 de julio, 2026
> **Ubicación del proyecto:** `C:\VANIER\AGENTE DE BUSQUEDA`

> **📌 Novedades (14 jul 2026, tarde) — Seguimiento de resultados consolidado:**
> - Cuando en una misma corrida hay **2 o más** eventos del Sistema 1 con
>   resultados reales listos, el seguimiento llega en **UN solo mensaje**: un
>   encabezado "📊 SEGUIMIENTO DE RESULTADOS" y **cada evento en su propio
>   desplegable** (`<blockquote expandable>`), con el footer AlphaBot una sola
>   vez. Si solo hay 1 evento, se envía como mensaje individual (igual que antes).
> - Cada evento sigue mostrando Forecast vs Anterior vs Actual y ✅ BEAT /
>   ❌ MISS / ➡️ EN LÍNEA, y se respalda por separado (backup por evento).
>
> **📌 Novedades (14 jul 2026) — MODO CLOUD-ONLY:**
> - **La NUBE es el único emisor de alertas.** El bot local (`bot_local.py`) ya
>   NO envía alertas automáticas: solo atiende comandos y publicaciones de
>   Telegram. Así se eliminan de raíz las repeticiones (antes emitían PC + nube).
> - **Flag `LOCAL_SEND_ALERTS`** (env) o `coordination.local_send_alerts` (config),
>   **default `false`**. Ponlo en `true` si quieres que el local vuelva a emitir.
> - **Bajo demanda:** `/report` y `/breaking` por Telegram siguen funcionando en
>   local (es acción explícita tuya).
> - **Agrupación de fuentes:** si una noticia sale en varias webs, la alerta
>   muestra "📰 N fuentes: A, B, C".
> - **Finviz fuera del Sistema 2** (noticias); el Sistema 1 sigue con Finviz
>   Calendar.
> - **Fix Sistema 1:** el reporte diario vuelve a salir completo (análisis por
>   lotes) y **una sola vez al día** aunque el cron dispare varias veces (guard en
>   `data/state/daily_report.json`). El cron ahora usa minutos desfasados
>   (15/35/55) para que GitHub no lo salte.
>
> **📌 Cambios anteriores (13 jul 2026):**
> - **Sistema 1** ahora usa **SOLO el calendario de Finviz** (se quitó el filtro de "relevancia USA" que borraba eventos válidos; todos los eventos de Finviz ya son de EE.UU.).
> - **Sistema 2** trabaja en modo **solo watchlist**: envía únicamente noticias de tu lista de empresas (flag `watchlist.only`).
> - **Deduplicación mejorada**: si la misma noticia sale en varias webs, se publica una sola vez (la fuente de mayor prioridad).
> - **Mensajes viejos**: el bot ya no republica mensajes antiguos (filtro de antigüedad + confirmación de Telegram).
> - **Bot local** (`bot_local.py`) ahora corre **ambos sistemas** en tiempo real, no solo comandos.
> - **Nube**: Sistema 2 pasó de cada hora a **cada 15 minutos** (configurable).
> - **Terminal**: se recomienda **PowerShell 7** (ya configurado como predeterminado del proyecto).

---

## 📋 Tabla de contenidos

1. [¿Qué es AlphaBot?](#1-qué-es-alphabot)
2. [Requisitos previos](#2-requisitos-previos)
3. [Instalación paso a paso (Windows)](#3-instalación-paso-a-paso-windows)
4. [Configurar las API keys](#4-configurar-las-api-keys)
5. [Los dos sistemas y sus formatos](#5-los-dos-sistemas-y-sus-formatos)
6. [Análisis profundo (Buffett / Graham / Lynch)](#6-análisis-profundo-buffett--graham--lynch)
7. [Control por Telegram](#7-control-por-telegram)
8. [Publicar en el canal (texto, audio y multimedia)](#8-publicar-en-el-canal-texto-audio-y-multimedia)
9. [Failover multi-provider](#9-failover-multi-provider)
10. [Watchlist de empresas](#10-watchlist-de-empresas)
11. [Seguimiento de resultados](#11-seguimiento-de-resultados)
12. [Backup automático](#12-backup-automático)
13. [Ejecutar en la nube (GitHub Actions)](#13-ejecutar-en-la-nube-github-actions)
13.5. [Bot local en tiempo real (publicar al instante)](#135-bot-local-en-tiempo-real-publicar-al-instante)
14. [Cómo hacer cambios en el futuro](#14-cómo-hacer-cambios-en-el-futuro)
15. [Comandos útiles](#15-comandos-útiles)
16. [Estructura de config.yaml](#16-estructura-de-configyaml)
17. [Solución de problemas](#17-solución-de-problemas)
18. [Resumen rápido](#18-resumen-rápido)

---

## 1. ¿Qué es AlphaBot?

AlphaBot es un **agente de noticias financieras** especializado en el mercado de valores de EE.UU. (NYSE, NASDAQ) que:

- 📊 **Genera un reporte diario entre 7-8 AM** (hora NY) con eventos macro del calendario económico
- 🚨 **Envía alertas cada hora** de noticias de alto impacto (24/7)
- 🧠 **Analiza con 3 proveedores de IA** con failover automático (Groq → Cerebras → Gemini)
- 💬 **Se controla por Telegram** con comandos, lenguaje natural o audios de voz
- 🎯 **Mantiene una watchlist** de empresas que prioriza en las búsquedas
- 📤 **Publica en tu canal** lo que le digas (texto, fotos, documentos, videos, audios)
- 📈 **Hace seguimiento de resultados**: cuando un evento ocurre, re-analiza con datos reales
- 🧠 **Análisis profundo** basado en Buffett, Graham y Lynch
- ⭐ **Importancia por porcentaje Y estrellas 1-5** en cada noticia
- 📂 **Noticias colapsables** en Telegram (`<blockquote expandable>`)
- 💾 **Backup automático** de todo lo que genera
- ☁️ **Funciona en local (tu PC) y en la nube (GitHub Actions gratis)**
- ⚡ **Bot local en tiempo real**: publica en el canal al instante cuando le mandas algo (no espera a la próxima hora)

---

## 2. Requisitos previos

| Requisito | Versión | Dónde conseguirlo |
|-----------|---------|-------------------|
| Python | 3.10+ | https://www.python.org/downloads/ |
| API key de Groq | Gratis | https://console.groq.com/keys |
| API key de Cerebras | Gratis | https://cerebras.ai |
| API key de Gemini | Gratis | https://aistudio.google.com |
| Bot de Telegram | Gratis | Ver sección 4 |
| GitHub account | Gratis | https://github.com (para la nube) |
| Conexión a internet | — | Para scraping y LLM |

> **¿Por qué 3 API keys?** El sistema tiene failover automático: si Groq agota sus tokens
> diarios, pasa a Cerebras, y si ese también falla, a Gemini. Nunca pierdes una ejecución.

---

## 3. Instalación paso a paso (Windows)

### PASO 1 — Tener la carpeta del proyecto

La carpeta del proyecto debe estar en:
```
C:\VANIER\AGENTE DE BUSQUEDA
```

Estructura:
```
C:\VANIER\AGENTE DE BUSQUEDA\
├── AGENTS.md              ← Contexto compartido para sub-agentes
├── MANUAL.md              ← Este archivo
├── app.py                 ← Dashboard (Streamlit)
├── run_report.py          ← Ejecuta los reportes (entrada principal)
├── bot_local.py           ← Bot local en tiempo real (publica al instante)
├── config.yaml            ← Configuración del agente
├── .env                   ← Tus API keys (crear en paso 4)
├── requirements.txt       ← Dependencias de Python
├── test_formats.py        ← Pruebas de formato de Telegram
├── install_tasks.bat      ← Instalador de tareas programadas (Windows)
├── mockup_telegram.html   ← Vista previa del formato
├── src/                   ← Código del agente
│   ├── system_prompt.md   ← Prompt del sistema (Buffett/Graham/Lynch)
│   ├── analyzer.py        ← Análisis con LLM
│   ├── backup.py          ← Backup automático
│   ├── chat.py            ← Chat en lenguaje natural (dashboard)
│   ├── config.py          ← Gestión de configuración
│   ├── formatter.py       ← Formato de mensajes (HTML + blockquote)
│   ├── llm.py             ← Failover multi-provider
│   ├── notifier.py        ← Envío a Telegram
│   ├── report.py          ← Orquestador (Sistema 1 + Sistema 2)
│   ├── results_tracker.py ← Seguimiento de resultados reales
│   ├── telegram_bot.py    ← Bot interactivo de Telegram
│   ├── watchlist.py       ← Gestión de watchlist
│   ├── providers/         ← Implementaciones de proveedores LLM
│   └── sources/           ← Scrapers (Finviz, Yahoo, CNBC, Bloomberg, Forex Factory)
├── ui/                    ← Pestañas del dashboard Streamlit
├── .github/workflows/     ← GitHub Actions (automatización en la nube)
│   ├── system1-daily.yml  ← Reporte diario 7-8 AM NY
│   └── system2-breaking.yml ← Alertas cada hora 24/7
└── data/                  ← Cache, historial y backups
    ├── cache/             ← Cache de noticias + eventos tracked + audios
    ├── history/           ← Historial de reportes
    └── backup/            ← Backup automático de todo
```

### PASO 2 — Crear entorno virtual

```bash
cd "C:\VANIER\AGENTE DE BUSQUEDA"
python -m venv venv
```

### PASO 3 — Instalar dependencias

```bash
# Git Bash:
source venv/Scripts/activate

# PowerShell:
# .\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

> Se instalan: openai, anthropic, google-genai, streamlit, httpx, beautifulsoup4,
> feedparser, python-dateutil, tzdata, pyyaml, python-dotenv, requests, etc.
>
> ¿Error con lxml? Ejecuta: `pip install lxml --only-binary :all:`

### PASO 4 — Configurar tus API keys

Crea un archivo `.env` (con el punto al inicio) en la carpeta raíz:

```env
# === Telegram ===
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
TELEGRAM_CHAT_ID=tu_chat_id_del_canal
TELEGRAM_USER_ID=tu_chat_id_privado

# === IA — 3 proveedores con failover automático ===
GROQ_API_KEY=tu_key_de_groq
CEREBRAS_API_KEY=tu_key_de_cerebras
GEMINI_API_KEY=tu_key_de_gemini
```

#### Cómo conseguir cada key:

**Groq** (primario — https://console.groq.com/keys)
1. Entra con tu cuenta de Google o GitHub
2. Click "Create API Key"
3. Copia la key (empieza con `gsk_`)

**Cerebras** (failover 1 — https://cerebras.ai)
1. Regístrate
2. Ve a API Keys
3. Crea una key (empieza con `csk-`)

**Gemini** (failover 2 — https://aistudio.google.com)
1. Entra con tu cuenta de Google
2. Click "Get API Key"
3. Crea una key

**Bot de Telegram:**
1. Abre Telegram y busca `@BotFather`
2. Envía `/newbot`
3. Dale un nombre (ej: "AlphaBot") y un username (ej: "alphabot_finance_bot")
4. BotFather te da el token (cópialo en `TELEGRAM_BOT_TOKEN`)
5. Para obtener el `TELEGRAM_CHAT_ID` (tu canal):
   - Añade el bot como administrador de tu canal
   - Envía un mensaje al canal
   - Abre `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` en el navegador
   - Busca `"chat":{"id": -100xxxxxxx}` — ese es tu `TELEGRAM_CHAT_ID`
6. Para obtener el `TELEGRAM_USER_ID` (tu chat privado):
   - Busca `@userinfobot` en Telegram y envíale cualquier mensaje
   - Te responde con tu ID numérico
   - Ese es tu `TELEGRAM_USER_ID`

### PASO 5 — Verificar la instalación

```bash
# Verificar que los 3 proveedores están activos:
python -c "from src.llm import get_failover_chain; chain = get_failover_chain(); print(f'{len(chain)} proveedores activos')"

# Verificar que el scraping funciona:
python -c "from src.report import fetch_all_sources; items = fetch_all_sources(); print(f'{len(items)} noticias scrapeadas')"
```

### PASO 6 — Abrir el dashboard (opcional)

```bash
streamlit run app.py
```
Se abre en http://localhost:8501 con 5 pestañas:
- 🧠 Proveedores — cambiar el proveedor activo
- ⚙️ Configuración — ajustar filtros, watchlist, fuentes
- 📰 Noticias en vivo — ver noticias scrapeadas en tiempo real
- 📊 Reporte — generar y ver reportes
- 💬 Chat — conversar con el agente en lenguaje natural

---

## 5. Los dos sistemas y sus formatos

### SISTEMA 1 — Sector Económico del Día (reporte diario)

| Aspecto | Detalle |
|---------|---------|
| **Qué hace** | Scrapea **solo el calendario económico de Finviz** |
| **Filtra** | Eventos de hoy con **2+ estrellas** (NO filtra por país: el calendario de Finviz ya es de EE.UU.) |
| **Cuándo corre** | Entre 7:00 y 8:59 AM hora de Nueva York, una vez al día |
| **Token saving** | Una sola llamada al LLM (batch de hasta 10 eventos) |
| **Estrellas** | Las que pone el calendario web (NO las inventa el LLM) |

> **Importante:** la "relevancia para EE.UU." es peculiaridad del **Sistema 2** (donde llegan noticias de cualquier tema y hay que filtrar las que mueven el mercado americano). El **Sistema 1** NO filtra por país porque el calendario de Finviz ya trae únicamente eventos de EE.UU. Antes había un filtro que exigía moneda "USD" y, como Finviz no rellena ese campo en discursos de la Fed, borraba todos los eventos y el reporte salía vacío. Ese filtro se eliminó.

**Formato "Modelo A" con noticias colapsables:**
- Cada noticia se muestra como titular visible + detalle plegado ("Mostrar más")
- Dentro del desplegable: 📝 Resumen, 📈 Análisis, 🟢 Beneficiados, 🔴 Perjudicados, 🔗 Enlace
- Footer: `🤖 AlphaBot · {saludo}` (buen día / buenas tardes / buenas noches según la hora)

### SISTEMA 2 — Último Minuto (alertas en tiempo real)

| Aspecto | Detalle |
|---------|---------|
| **Qué hace** | Scrapea 4 fuentes (CNBC/MarketWatch, Yahoo Finance, Finviz, Bloomberg RSS) |
| **Filtra** | Solo noticias que pueden mover el mercado USA con confianza ≥ 70% |
| **Cuándo corre** | Cada hora, 24/7 |
| **Watchlist** | Empresas en watchlist tienen umbral reducido (55%) y prioridad |
| **Token saving** | Cache de noticias analizadas — no re-analiza noticias ya vistas |

**Escala de estrellas 1-5 direccional (Sección 2):**

| Estrellas | Noticias positivas | Noticias negativas |
|-----------|-------------------|-------------------|
| ⭐⭐⭐⭐⭐ | Muy bullish — mueve índices >2% al alza | Muy grave — colapso >2% |
| ⭐⭐⭐⭐ | Bullish fuerte — subida 1-2% | Grave — caída 1-2% |
| ⭐⭐⭐ | Algo positivo — 0.5-1% | Algo negativo — 0.5-1% |
| ⭐⭐ | Levemente positivo | Levemente negativo |
| ⭐ | Impacto mínimo positivo | Impacto mínimo negativo |

La importancia se muestra **por porcentaje** (confianza 0-100%) **Y por estrellas** 1-5.

---

## 6. Análisis profundo (Buffett / Graham / Lynch)

Cada noticia se analiza aplicando 3 frameworks de inversión:

- **Warren Buffett — Foso Competitivo:** ¿La noticia afecta la ventaja competitiva de la empresa? ROE, consistencia de ganancias, valor intrínseco
- **Benjamin Graham — Factor Sorpresa:** ¿Hay diferencia entre lo real y lo esperado? Margen de seguridad, comportamiento de Mr. Market
- **Peter Lynch — Crecimiento:** ¿Cómo afecta el crecimiento? Tasa de crecimiento, tipo de empresa (slow grower / stalwart / fast grower), PEG ratio
- **Análisis Event-Driven:** Beat/Miss de EPS y revenue, guidance, revisiones de analistas, contagio sectorial

---

## 7. Control por Telegram

El agente revisa Telegram al inicio de cada ejecución horaria. Tres formas de comunicación:

### 7.1 Comandos directos (sin gastar tokens de LLM)

| Comando | Acción |
|---------|--------|
| `/add AAPL` o `/add Apple` | Añade empresa a la watchlist |
| `/add AAPL Apple,iPhone` | Añade con aliases |
| `/remove TSLA` | Quita empresa de la watchlist |
| `/list` | Muestra la watchlist actual |
| `/report` | Genera y envía el reporte diario AHORA |
| `/breaking` | Busca noticias de última hora AHORA |
| `/publica <texto>` | Publica un mensaje en el canal |
| `/status` | Estado del agente (proveedor activo, failover) |
| `/help` | Lista de comandos |

Aliases de `/publica`: `/pub`, `/post`, `/publicar`

### 7.2 Lenguaje natural (usa LLM si los patrones rápidos no coinciden)

Ejemplos:
- "agrega Apple a mi lista"
- "quita Tesla"
- "muéstrame mi lista"
- "genera el reporte"
- "qué hay de nuevo"
- "en qué proveedor estás"

### 7.3 Audios de voz

1. El bot descarga el audio
2. Lo transcribe con Groq Whisper (whisper-large-v3, español)
3. Procesa el texto transcrito como comando o lenguaje natural
4. Responde en Telegram

---

## 8. Publicar en el canal (texto, audio y multimedia)

AlphaBot funciona como **asistente de administración del canal**. Le dices qué publicar y lo publica.

### 8.1 Palabras exactas para publicar

El bot detecta la orden de publicar con la palabra **"publica"** (o sinónimos) al inicio del mensaje. Funciona con cualquier puntuación después (`:`, `,`, `.`, espacio) y es **insensible a acentos** ("Pública" = "publica").

#### 📝 Escrito (texto al bot):

Cualquiera de estas funciona:
```
publica: buen día comunidad
publica, buen día comunidad
publica buen día comunidad
/publica buen día comunidad
```

Palabras clave aceptadas: `publica`, `publicar`, `posta`, `comparte`, `anuncia`, `envía al canal`

#### 🎤 Audio (voz):

Di cualquiera de estas:
> "publica, buen día comunidad"
> "publicar: reunión a las 3pm"
> "posta: recuerden earnings de NVDA hoy"

El bot transcribe con Whisper, detecta la palabra clave (incluso con acento: "Pública"), extrae el resto y lo publica en el canal.

#### Ejemplos:

| Dices / escribes | Se publica en el canal |
|-----------------|----------------------|
| `publica: buen día comunidad` | buen día comunidad |
| `/publica reunión a las 3pm` | reunión a las 3pm |
| `publicar: recuerden earnings de NVDA hoy` | recuerden earnings de NVDA hoy |
| Audio: "publica, el mercado abre al alza hoy" | el mercado abre al alza hoy |
| Audio: "Pública. Buen día Michael..." | Buen día Michael... |

### 8.2 Multimedia (fotos, documentos, videos)

Si le envías una **foto, documento, video o animación** al bot, la **reenvía automáticamente** al canal usando la API `copyMessage` de Telegram, con formato AlphaBot (encabezado + footer).

- Puedes añadir un **caption** (texto descriptivo) al enviar la foto/documento
- No necesitas decir "publica" — los medios se auto-publican

### 8.3 Auto-desplegable

Si el texto a publicar tiene **más de 300 caracteres**, el bot automáticamente lo envía dentro de un `<blockquote expandable>` (mensaje colapsable) para que no ocupe toda la pantalla.

---

## 9. Failover multi-provider

```
Groq (primario) → Cerebras (failover 1) → Gemini (failover 2)
```

| Proveedor | Modelo | API Key | Protocolo |
|-----------|--------|---------|-----------|
| Groq | llama-3.3-70b-versatile | `GROQ_API_KEY` | OpenAI-compatible |
| Cerebras | gpt-oss-120b | `CEREBRAS_API_KEY` | OpenAI-compatible |
| Gemini | gemini-flash-lite-latest | `GEMINI_API_KEY` | Google genai SDK nativo |

- Si Groq da error 429 (rate limit), prueba Cerebras. Si falla, Gemini. Si todos fallan → error.
- Cada proveedor es **API nativa directa** (no OpenRouter) → máxima velocidad.
- Transcripción de audios: Groq Whisper (whisper-large-v3, `language="es"`)

---

## 10. Watchlist de empresas

- Se guarda en `config.yaml` (sección `watchlist.companies`)
- Acepta ticker (`AAPL`) o nombre (`Apple`) — diccionario con 50+ empresas para resolución automática
- Noticias que mencionan empresas de la watchlist → **prioridad + umbral 55%** (vs 70% normal)
- El LLM recibe contexto: "El usuario sigue de cerca: AAPL (Apple), TSLA (Tesla)..."
- Empresas actuales: AAPL, NVDA, MSFT, AMZN, META, GOOGL, TSLA, JPM, NFLX, PLTR, UNH
- En GitHub Actions, los cambios se commitean al repo automáticamente

---

## 11. Seguimiento de resultados

Después de que el Sistema 1 envía el reporte diario, cada evento se guarda para seguimiento:

1. **Mañana (7-8 AM):** envía eventos programados → guarda en `data/cache/tracked_events_DATE.json`
2. **Cada hora (Sistema 2):** revisa si cada evento ya ocurrió (+15 min de margen)
3. Si ya ocurrió: re-scrapea la fuente del calendario para obtener el valor real
4. Re-analiza con el LLM usando los datos reales (beat / miss / en línea)
5. Envía un mensaje de seguimiento a Telegram con: Forecast vs Anterior vs Actual · ✅ BEAT / ❌ MISS / ➡️ EN LÍNEA · análisis actualizado
6. Marca el evento como `followed=True` para no repetir

---

## 12. Backup automático

Todo se guarda en `data/backup/`:

| Tipo | Archivo |
|------|---------|
| Reportes diarios | `report_TIMESTAMP.txt` + `.json` |
| Alertas enviadas | `alert_TIMESTAMP.txt` + `.json` |
| Log de Telegram | `telegram_log_DATE.txt` |
| Log de ejecución | `execution_DATE.log` |

Los backups de más de 30 días se borran automáticamente.

---

## 13. Ejecutar en la nube (GitHub Actions)

GitHub Actions ejecuta el agente automáticamente en la nube **gratis** (2,000 min/mes en repo privado; ilimitado en público).

### PASO 1 — Crear un repositorio en GitHub

1. Entra a https://github.com/new
2. Nombre: `alphabot` (o el que prefieras)
3. **Privado** (recomendado) o Público
4. **NO** inicializar con README ni .gitignore (ya los tienes)
5. Click "Create repository"

### PASO 2 — Conectar tu carpeta local con GitHub

Abre Git Bash en la carpeta del proyecto:

```bash
cd "C:\VANIER\AGENTE DE BUSQUEDA"

# Inicializar git
git init

# Añadir todos los archivos (el .gitignore excluye .env, cache, backups)
git add .

# Primer commit
git commit -m "AlphaBot — agente de búsqueda financiera"

# Conectar con tu repo de GitHub (cambia TU_USUARIO por tu username)
git remote add origin https://github.com/TU_USUARIO/alphabot.git

# Subir todo
git branch -M main
git push -u origin main
```

> Si te pide credenciales, usa un Personal Access Token (GitHub → Settings → Developer settings → Personal access tokens → Generate new token con permiso `repo`)

### PASO 3 — Configurar los Secrets

Entra a tu repo en GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Añade estos **6 secrets**:

| Nombre del secret | Valor |
|-------------------|-------|
| `GROQ_API_KEY` | Tu key de Groq (gsk_...) |
| `CEREBRAS_API_KEY` | Tu key de Cerebras (csk-...) |
| `GEMINI_API_KEY` | Tu key de Gemini |
| `TELEGRAM_BOT_TOKEN` | El token de tu bot |
| `TELEGRAM_CHAT_ID` | El ID de tu canal (-100...) |
| `TELEGRAM_USER_ID` | Tu ID de chat privado |

### PASO 4 — Verificar que los workflows están activos

1. Entra a tu repo → pestaña **Actions**
2. Deberías ver 2 workflows:
   - "Sistema 1 — Reporte diario" (cron 7 AM NY)
   - "Sistema 2 — Alertas horarias" (cada hora 24/7)
3. Si no aparecen, espera unos minutos o haz push de nuevo

### PASO 5 — Probar manualmente

En Actions → "Sistema 2 — Alertas horarias" → **Run workflow** → Click "Run workflow"

Ve la ejecución en tiempo real. Si termina en verde ✅, el agente está funcionando en la nube.

### Horarios de la nube

| Workflow | Cron | Horario NY | Frecuencia |
|----------|------|-----------|------------|
| Sistema 1 | `0 11 * * *` y `0 12 * * *` | 7 AM EDT / 7 AM EST | 1 vez al día |
| Sistema 2 | `0 * * * *` | Cada hora | 24/7 |

> El Sistema 1 tiene un guard en Python: solo ejecuta si la hora de NY está entre 7:00 y 8:59 AM. Los dos crons (11 y 12 UTC) cubren el cambio de horario de verano/invierno.

### Límites de GitHub Actions (gratis)

- Repo privado: 2,000 min/mes
- Sistema 2: 24 runs/día × ~2 min = ~1,440 min/mes → cabe
- Sistema 1: 1 run/día × ~3 min = ~90 min/mes → despreciable
- Repo público: minutos ilimitados

---

## 13.5 Bot local en tiempo real (publicar al instante)

### El problema de la nube
GitHub Actions despierta el bot cada hora en el minuto 0. Si le mandas un mensaje a las 8:05 AM, el bot no lo procesa hasta las 9:00 AM (+ 2-3 min de setup). **Puede tardar hasta 1 hora.**

### La solución: bot local
`bot_local.py` corre en tu PC y revisa Telegram cada **30 segundos**. Cuando le mandas algo, lo procesa y publica en el canal **al instante** (menos de 30 segundos de espera).

### Cómo usarlo

```bash
cd "C:\VANIER\AGENTE DE BUSQUEDA"
source venv/Scripts/activate
python bot_local.py
```

El bot empieza a correr y muestra:
```
=======================================================
🤖 AlphaBot — Bot Local (tiempo real)
=======================================================
   Revisando Telegram cada 30 segundos
   Publica al instante cuando le mandas algo
   Detén con Ctrl+C
=======================================================
```

- **Mándale un mensaje al bot** por Telegram (texto, audio, foto, documento)
- El bot lo procesa en **menos de 30 segundos**
- Para detenerlo: **Ctrl+C** en la consola

### Qué hace el bot local
| Recibe | Acción | ¿Usa LLM? |
|--------|--------|-----------|
| `publica: hola` | Publica "hola" en el canal | No (instantáneo) |
| Audio: "publica, hola" | Transcribe + publica | Sí (Whisper) |
| Foto/documento/video | Reenvía al canal | No |
| `/add AAPL` | Añade a watchlist | No |
| `/list` | Muestra watchlist | No |
| Lenguaje natural | Interpreta con LLM | Sí |

### Importante: convivencia nube + local
- El **offset de Telegram** se comparte (`data/cache/telegram_offset.txt`)
- Si la nube procesó un mensaje → el bot local **no lo repite**
- Si el bot local procesó un mensaje → la nube **no lo repite**
- **Cuando tu PC está apagada**, la nube sigue funcionando cada hora
- **Cuando tu PC está encendida**, el bot local responde al instante

### Dejar el bot corriendo en segundo plano
Si quieres que el bot corra siempre que la PC esté encendida (sin tener una consola abierta):

**Opción A — Ventana minimizada:**
Crea un archivo `iniciar_bot.bat` en el Escritorio:
```bat
@echo off
cd /d "C:\VANIER\AGENTE DE BUSQUEDA"
call venv\Scripts\activate.bat
python bot_local.py
```
Doble click para iniciar. Minimiza la ventana.

**Opción B — Inicio automático con Windows:**
1. Presiona `Win+R`, escribe `shell:startup`
2. Crea ahí un acceso directo a `iniciar_bot.bat`
3. El bot arrancará automáticamente al encender la PC

---

## 14. Cómo hacer cambios en el futuro

Esta sección explica exactamente qué hacer si quieres modificar algo del agente.

### 14.1 Si tienes todo en la carpeta local (`C:\VANIER\AGENTE DE BUSQUEDA`)

**Flujo recomendado:**

```bash
cd "C:\VANIER\AGENTE DE BUSQUEDA"

# 1. Haz los cambios en los archivos que necesites
#    (puedes editar con cualquier editor: VS Code, Notepad++, etc.)

# 2. Verifica que todo funciona en local antes de subir:
python run_report.py --daily --no-send      # probar Sistema 1 sin enviar
python run_report.py --breaking --no-send   # probar Sistema 2 sin enviar
streamlit run app.py                         # abrir dashboard

# 3. Sube los cambios a GitHub:
git add .
git commit -m "Descripción del cambio que hiciste"
git push
```

**Eso es todo.** GitHub Actions usará automáticamente la nueva versión en la siguiente ejecución programada.

### 14.2 Qué archivo editar para cada cambio

| Si quieres cambiar... | Edita este archivo |
|----------------------|-------------------|
| El prompt del LLM (cómo analiza noticias) | `src/system_prompt.md` |
| El análisis con LLM (qué pide al modelo) | `src/analyzer.py` |
| El formato de los mensajes de Telegram | `src/formatter.py` |
| El envío a Telegram (parse_mode, splits) | `src/notifier.py` |
| El pipeline (qué scrapea, filtros, umbrales) | `src/report.py` |
| Los comandos del bot de Telegram | `src/telegram_bot.py` |
| La watchlist (empresas, umbrales) | `config.yaml` |
| Los proveedores de IA | `config.yaml` + `src/llm.py` |
| Las fuentes de noticias | `src/sources/` + `config.yaml` |
| El seguimiento de resultados | `src/results_tracker.py` |
| Los horarios de la nube | `.github/workflows/*.yml` |
| El backup automático | `src/backup.py` |
| El dashboard web | `app.py` + `ui/` |
| El bot local en tiempo real | `bot_local.py` |

### 14.3 Si solo quieres cambiar la watchlist

**Opción A — Por Telegram (sin tocar código):**
```
/add NVDA
/remove TSLA
/list
```

**Opción B — Editando config.yaml directamente:**
```yaml
watchlist:
  companies:
    - ticker: "AAPL"
      name: "Apple"
      aliases: ["iPhone", "Tim Cook"]
```
Luego: `git add . && git commit -m "Actualicé watchlist" && git push`

### 14.4 Si quieres cambiar los horarios de la nube

Edita `.github/workflows/system1-daily.yml` o `system2-breaking.yml`:

```yaml
on:
  schedule:
    - cron: '0 13 * * *'   # cambias el número para cambiar la hora UTC
```

Conversión: UTC = NY + 4 (verano) o NY + 5 (invierno). Ejemplo: 9 AM NY verano = 13 UTC.

### 14.5 Si quieres añadir una nueva fuente de noticias

1. Crea un archivo en `src/sources/` (ej: `mi_fuente.py`)
2. Hereda de `BaseSource` e implementa `fetch()` devolviendo `NewsItem`s
3. Añádelo en `config.yaml` bajo `sources:`
4. Añádelo en `src/report.py` en la función `fetch_news_sources()` o `fetch_calendar_sources()`
5. Prueba: `python -c "from src.sources.mi_fuente import *; ..."`
6. `git add . && git commit && git push`

### 14.6 Reglas de oro al hacer cambios

1. **NUNCA subas el `.env`** — está en `.gitignore` pero verifica siempre
2. **Prueba en local antes de subir** — usa `--no-send` para no enviar a Telegram de prueba
3. **Un commit = un cambio** — no mezcles 5 cambios en un solo commit
4. **Mensajes de commit claros** — "Añadí fuente de Reuters" no "cambios"
5. **Si rompes algo** — `git log --oneline` para ver el último commit bueno, luego `git checkout <commit> -- .` para revertir
6. **El `.env` solo existe en local** — en la nube los secrets están en GitHub Settings

---

## 15. Comandos útiles

### Ejecutar el agente

```bash
# Sistema 1 (reporte diario) — enviar a Telegram
python run_report.py --daily --no-reasoning

# Sistema 1 — solo ver, sin enviar
python run_report.py --daily --no-send

# Sistema 2 (alertas) — enviar a Telegram
python run_report.py --breaking --no-reasoning

# Sistema 2 — solo ver, sin enviar
python run_report.py --breaking --no-send

# Ambos sistemas
python run_report.py --all --no-reasoning

# Dashboard
streamlit run app.py

# Bot local en tiempo real (publica al instante)
python bot_local.py
```

### Mantenimiento

```bash
# Ver proveedores activos
python -c "from src.llm import get_failover_chain; print(get_failover_chain())"

# Ver backups
python -c "from src.backup import list_backups; [print(b['name']) for b in list_backups()]"

# Limpiar cache (forzar re-análisis de todas las noticias)
python -c "import shutil; shutil.rmtree('data/cache', ignore_errors=True); print('Cache limpio')"

# Ver historial de reportes
ls data/history/

# Probar formatos de Telegram
python test_formats.py
```

### Git

```bash
git status              # ver qué cambió
git add .               # preparar todos los cambios
git commit -m "mensaje" # guardar cambios
git push                # subir a GitHub
git log --oneline -10   # ver últimos commits
git pull                # bajar cambios de GitHub
```

---

## 16. Estructura de config.yaml

```yaml
active:
  provider: Groq                    # proveedor primario
  model: llama-3.3-70b-versatile
  temperature: 0.3
  max_tokens: 1500
  reasoning: true

sources:
  forex_factory:   { enabled: true }   # calendario macro
  yahoo_calendar:  { enabled: true }   # calendario macro
  finviz_calendar: { enabled: true }   # calendario macro
  investing:       { enabled: true }   # noticias (CNBC + MarketWatch)
  yahoo_finance:   { enabled: true }   # noticias
  finviz:          { enabled: true }   # noticias
  bloomberg_rss:   { enabled: true }   # noticias

filter:
  min_stars: 2              # Sistema 1: solo eventos 2+ estrellas
  breaking_min_score: 70    # Sistema 2: umbral normal de alertas

failover:
  enabled: true
  providers:
    - { provider: Cerebras, model: gpt-oss-120b }
    - { provider: Google Gemini, model: gemini-flash-lite-latest }

watchlist:
  enabled: true
  min_score_watchlist: 55   # umbral reducido para empresas seguidas
  companies:
    - { ticker: AAPL, name: Apple, aliases: [Apple Inc, iPhone, Tim Cook] }
    - { ticker: NVDA, name: Nvidia, aliases: [] }
    # ... más empresas

schedule:
  report_time: 08:00
  timezone: America/New_York

telegram:
  parse_mode: HTML           # formato de mensajes (HTML para blockquote expandable)

language: es
```

---

## 17. Solución de problemas

| Problema | Solución |
|----------|---------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` con el venv activado |
| Telegram no envía mensajes | Verifica `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env` |
| Error 429 (rate limit) | El failover debería saltar al siguiente proveedor. Si todos fallan, espera 1 hora |
| 0 noticias scrapeadas | Verifica conexión a internet. Algunas fuentes pueden estar caídas |
| Bot no responde en Telegram | El bot revisa mensajes cada hora (no es tiempo real). Para probar ya: `python run_report.py --breaking` |
| Audios no se transcriben | Verifica `GROQ_API_KEY` en `.env`. Whisper necesita la key de Groq |
| El bot dice "chat no autorizado" | Añade tu `TELEGRAM_USER_ID` en `.env` y en los secrets de GitHub |
| Streamlit no abre | `pip install streamlit` y verifica Python 3.10+ |
| Error lxml | `pip install lxml --only-binary :all:` |
| `cannot import name 'genai'` | `pip install google-genai` (no `google-generativeai`) |
| GitHub Actions no ejecuta | Verifica que los 6 secrets están configurados. Revisa el log en Actions |
| GitHub Actions no commitea watchlist | Verifica `permissions: contents: write` en el workflow (ya está) |
| blockquote no se ve colapsado | Actualiza la app de Telegram (Bot API 7.4+ requerido, mayo 2024) |
| El bot no publica mi audio | Di "publica" al inicio del audio. Funciona con o sin acento ("Pública" = "publica") |
| Telegram 409 conflict | Hay otro proceso consumiendo getUpdates. Cierra otros Python: `taskkill //F //IM python.exe` |
| Offset avanzó y no procesa | El offset se guarda en `data/cache/telegram_offset.txt`. El mensaje ya fue consumido por Telegram |

---

## 18. Resumen rápido

```bash
# 1. Instalar
cd "C:\VANIER\AGENTE DE BUSQUEDA"
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt

# 2. Configurar .env con 6 variables:
#    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_USER_ID
#    GROQ_API_KEY, CEREBRAS_API_KEY, GEMINI_API_KEY

# 3. Verificar
python -c "from src.llm import get_failover_chain; print(get_failover_chain())"

# 4. Probar
python run_report.py --daily --no-send      # ver reporte sin enviar
python run_report.py --breaking --no-send   # ver alertas sin enviar

# 5. Subir a la nube
git init
git add .
git commit -m "AlphaBot"
git remote add origin https://github.com/TU_USUARIO/alphabot.git
git branch -M main
git push -u origin main

# 6. Configurar 6 secrets en GitHub Settings → Actions
# 7. Probar: Actions → Run workflow
# 8. Controlar por Telegram: /help, /add AAPL, "publica: hola", audios
```

¡Listo! AlphaBot está funcionando. 🎉


---

## 19. Novedades (13 julio 2026)

### 19.1 Fuentes del Sistema 2
- Se añadió **Reuters + Associated Press** (`src/sources/reuters.py`) vía Google News RSS. Máxima prioridad en el dedup (Reuters/AP > Investing/CNBC/MarketWatch > Yahoo > Finviz > Bloomberg).

### 19.2 Sin repeticiones (fix definitivo — estado compartido)
- Antes la nube repetía noticias porque olvidaba su memoria en cada ejecución (la cache no se sube a GitHub).
- Ahora hay **una sola fuente de verdad**: `data/state/sent_alerts.json` (rastreado por git, ventana 48h). El bot local y la nube lo comparten (`git pull` al inicio, `commit + push` al final). Ninguno repite, corran juntos o por separado.
- Extras anti-repetición: dedup entre fuentes por similitud de tokens, **máximo 1 alerta por ticker por ejecución** (la de mayor confianza), y matching **solo por título** con palabra completa (evita falsos positivos tipo SpaceX/Paramount).

### 19.3 Alertas de PRECIO (nuevo, Sistema 2b)
- Avisa cuando un ticker de la watchlist se mueve **≥ `filter.price_move_pct`** (5%) en el día, aunque no haya noticia. Vía **yfinance**.
- Se envía como **IMAGEN profesional** (gráfico de barras tema oscuro, `src/price_chart.py` con matplotlib) mediante `notifier.send_photo_to_telegram`; si falla, cae a texto.
- Un solo mensaje consolidado, dedup por día y dirección, solo con datos frescos del día.

### 19.4 Reporte diario enriquecido (Sistema 1)
- **Panorama de mercado** al inicio (`src/market_snapshot.py`): S&P 500, Nasdaq 100, Dow, Russell 2000, VIX, Petróleo WTI, Oro, Bono 10Y, Dólar DXY (sin cripto), con etiquetas descriptivas.
- **Earnings próximos** (`src/earnings_calendar.py`): empresas de la watchlist que reportan en 7 días (marca 🔔 HOY). ETFs omitidos.

### 19.5 Eficiencia
- Cache de análisis/enviadas de **48h**.
- **Análisis por lotes** en el Sistema 2 (1 llamada LLM por cada ~5 noticias nuevas).
- **Reparto de carga LLM**: el reporte diario usa Cerebras/Gemini y reserva Groq para las alertas.
- **Anti-ruido** para ETFs de materias primas (USO, SLV, GLD, URA, SOXL, TNA): umbral `commodity_min_score` (70).
- **Health-check** de fuentes: avisa por Telegram si una fuente deja de traer noticias.

### 19.6 Dependencias nuevas
- `yfinance>=0.2.40` (precios, panorama, earnings) y `matplotlib>=3.8.0` (imagen de precios).

### 19.7 Config nuevo (`config.yaml`)
```yaml
filter:
  price_move_pct: 5         # alerta de precio si el ticker se mueve >= 5% en el día
  commodity_min_score: 70   # umbral estricto para ETFs de materias primas
watchlist:
  only: true                # Sistema 2 solo envía noticias de la lista
```

### 19.8 Pendiente
- Imagen de alertas de precio con **Gemini Nano Banana** (opción A híbrida o B tarjeta full-IA) — sin decidir.
