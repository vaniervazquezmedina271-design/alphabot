# 📝 Registro de cambios — AlphaBot

> Este archivo documenta las correcciones y mejoras aplicadas al proyecto.
> Complementa a `MANUAL.md` y `AGENTS.md`. Los sub-agentes deben leerlo.

---

## 13 de julio, 2026

### 1. Sistema 1 (Reporte diario) — SOLO Finviz + arreglo del filtro que lo rompía

- **Fuentes:** en `config.yaml`, `forex_factory` y `yahoo_calendar` quedaron en `enabled: false`. El Sistema 1 usa **únicamente `finviz_calendar`**.
- **Bug corregido (causa de que el Sistema 1 no enviara nada):** en `src/report.py`, `generate_daily_report()` aplicaba el filtro `_is_us_relevant()`, que exige `currency == "USD"`. Finviz NO rellena la moneda en eventos como discursos de la Fed, así que el filtro **borraba TODOS los eventos** y el reporte salía vacío. Se **eliminó ese filtro del Sistema 1**. Ahora solo filtra por estrellas (`min_stars`, 2+).
- **Aclaración de diseño:** la relevancia-USA es peculiaridad del **Sistema 2** (llegan noticias de cualquier tema), NO del Sistema 1 (el calendario de Finviz ya es de EE.UU.).
- **Zona horaria:** `src/sources/finviz_calendar.py` ahora filtra "hoy" con `_ny_today()` (hora de Nueva York), no con la hora del servidor. Evita perder eventos en la nube (UTC). Si no detecta el país, asume USD/🇺🇸.
- **Prueba (13 jul):** `run_report.py --daily --no-send` generó el reporte con Fed Bowman Speech, Fed Waller Speech y Monthly Budget Statement. ✅

### 2. Sistema 2 (Alertas) — solo watchlist + deduplicación entre fuentes

- **Modo solo-watchlist:** nuevo flag `watchlist.only: true` en `config.yaml`. Con él, el Sistema 2 envía **solo** noticias que mencionan empresas de la watchlist; descarta el resto. Con `only: false` vuelve al modo prioridad (watchlist primero + resto con umbral 70%).
- **Deduplicación (variante 2 + prioridad de fuente):** en `src/report.py`, `deduplicate()` ya no compara títulos exactos. Agrupa la misma noticia de fuentes distintas por **similitud de tokens** (Jaccard ≥ 0.6 o contención ≥ 0.8) y conserva la fuente de mayor prioridad: **Bloomberg > Investing/CNBC > Yahoo > Finviz**. Funciones nuevas: `_title_tokens()`, `_titles_similar()`, `news_signature()`, `_source_rank()`.
- **No repetir entre ejecuciones:** `get_sent_hash()` ahora devuelve la firma de tokens (no el título exacto). `run_breaking_alerts()` mantiene `sent_token_sets` y compara por similitud contra lo ya enviado, así la misma noticia desde otra web no se reenvía.
- **Tickers ambiguos:** en `src/watchlist.py`, el set `COMMON_WORD_TICKERS` (now, low, c, v, ma, dia, spy, coin, meta, uso, hd, mu…) hace que esos tickers se detecten por **nombre/alias** de la empresa, NO por el ticker suelto (evita falsos positivos como "now", "low", "spy").

### 3. Mensajes viejos — el bot ya no republica lo antiguo

En `src/telegram_bot.py`, `fetch_updates()`:
- **Filtro de antigüedad:** ignora mensajes más viejos que `TELEGRAM_MAX_MSG_AGE_SEC` (default 600s = 10 min). Solo procesa "lo que le mandas en el momento".
- **Confirmación server-side:** tras procesar, llama a getUpdates con `offset = max+1` para que Telegram descarte esos updates. Clave en la nube, donde el offset no persiste entre runs de GitHub Actions (antes, cada run recibía y republicaba los mismos mensajes).

### 4. Watchlist reemplazada (40 tickers del usuario)

En `config.yaml`, se borraron las 11 empresas anteriores y se cargaron:
- **Acciones (29):** AMZN, AAPL, GOOG, META, MSFT, NFLX, TSLA, PLTR, IBM, ORCL, NOW, AMD, MU, NVDA, QCOM, AVGO, INTC, DASH, LYFT, UBER, HD, LOW, WMT, AXP, COIN, PYPL, MA, C, V
- **ETFs/índices (11):** SOXL, DIA, QQQ, SPY, SPX, IWM, TNA, URA, USO, SLV, GLD

Cada una con `name` y `aliases` para el matching por nombre.

### 5. Ejecución local de ambos sistemas

`bot_local.py` reescrito. Además de revisar Telegram cada 30s, ahora:
- Corre el **Sistema 2** cada 5 min (`BOT_LOCAL_BREAKING_SEC`).
- Corre el **Sistema 1** una vez entre 7-8 AM NY (marcador `data/cache/last_daily_local.txt` para no repetir).
- Variables de entorno: `BOT_LOCAL_COMMANDS_SEC` (30), `BOT_LOCAL_BREAKING_SEC` (300).

### 6. Nube — Sistema 2 más frecuente

`.github/workflows/system2-breaking.yml`: cron pasó de `0 * * * *` (cada hora) a `*/5 * * * *` (cada 5 min, repo público con minutos ilimitados).

| Cron | Frecuencia | Min/mes aprox. | ¿Cabe en gratis privado (2.000)? |
|------|-----------|----------------|----------------------------------|
| `*/5 * * * *` | 5 min | ~8.600 | No (sí público, ilimitado) |
| `*/10 * * * *` | 10 min | ~4.300 | No (sí público) |
| `*/15 * * * *` | 15 min | ~2.880 | Casi (mejor público) ← actual |
| `*/30 * * * *` | 30 min | ~1.440 | Sí |
| `0 * * * *` | 1 h | ~720 | Sí |

Para tiempo real de verdad, usar el bot local; la nube como respaldo.

### 7. Robustez en Windows

- `run_report.py` y `bot_local.py` reconfiguran stdout/stderr a **UTF-8** (evita `UnicodeEncodeError` con emojis en cp1252 al redirigir salida).
- **Terminal:** se creó `.vscode/settings.json` con **PowerShell 7** como perfil predeterminado (Windows PowerShell 5.1 no soporta `&&`). PowerShell 7 ya estaba instalado en el equipo.
- `config.yaml`: `telegram.parse_mode` pasó a `HTML` (consistente con el notifier, que ya usa HTML).

---

## Archivos tocados

- `config.yaml` — fuentes Sistema 1, watchlist (40), `watchlist.only`, parse_mode
- `src/report.py` — dedup variante 2, sin filtro país en Sistema 1, watchlist-only, sent_token_sets
- `src/watchlist.py` — `COMMON_WORD_TICKERS`, matching por nombre/alias
- `src/telegram_bot.py` — filtro de antigüedad + confirmación de updates
- `src/sources/finviz_calendar.py` — fecha en hora NY, país default USD
- `bot_local.py` — corre ambos sistemas en local
- `run_report.py` — salida UTF-8
- `.github/workflows/system2-breaking.yml` — cron cada 15 min
- `.vscode/settings.json` — PowerShell 7 por defecto


---

## 13 de julio, 2026 — Mejoras de eficiencia

### 8. Cache de análisis de 48h (antes se borraba a medianoche)

`load_analyzed_cache()` y `load_sent_alerts()` en `report.py` ahora leen **hoy + ayer** (hora NY) y los fusionan. Muchas noticias siguen "vivas" al día siguiente; con 48h no se re-analizan (ahorro de tokens) ni se reenvían al cambiar el día. Helper nuevo: `_ny_date_offset()`.

### 9. Análisis por lotes en el Sistema 2 (antes: 1 llamada por noticia)

- Nueva función `analyze_batch_breaking()` en `analyzer.py`: analiza varias noticias en **una sola llamada** al LLM (trocea en lotes de 5 para que el JSON no se corte).
- `run_breaking_alerts()` reescrito en 3 pasos: (1) filtrar candidatos y separar cacheadas de nuevas, (2) analizar las nuevas EN LOTE, (3) decidir y enviar. Antes eran N llamadas; ahora ~1 por cada 5 noticias.
- Probado: 2 noticias analizadas en 1 llamada, devolviendo `puede_mover_mercado`, `confianza`, `stars`, `sentimiento`.

### 10. Reparto de carga entre proveedores LLM

- `get_failover_chain(prefer=...)` y `chat(prefer=...)` en `llm.py`: permiten poner un proveedor al frente de la cadena.
- El **reporte diario** (1 vez/día) usa `prefer=["Cerebras", "Google Gemini"]`, reservando la cuota de **Groq** para las alertas frecuentes del Sistema 2. Reduce los choques con el rate limit de Groq (se veía el 429).

### 11. Anti-ruido para ETFs de materias primas

- `NOISY_ETF_TICKERS` + `is_noisy_etf()` en `watchlist.py`: USO, SLV, GLD, URA, SOXL, TNA (tienen alias genéricos como "oil", "gold", "silver" que generan ruido).
- En `run_breaking_alerts()`, a las noticias que matchean uno de esos ETFs se les exige el umbral estricto `filter.commodity_min_score` (default 70) en vez del 55 de watchlist.

### 12. Health-check de fuentes

- `report.py`: `_record_source_health()` cuenta ejecuciones seguidas con 0 ítems por fuente (estado en `data/cache/source_health.json`). `notify_unhealthy_sources()` avisa por Telegram (una sola vez) si una fuente lleva 3+ ejecuciones sin traer nada. Se llama desde `run_breaking_alerts()` y `run_and_send()`. Evita "silencios" sin darte cuenta.

### Nota sobre repo público (minutos ilimitados)

No es un cambio de código: si quieres frecuencia alta en la nube sin gastar la cuota gratis (2.000 min/mes en repos privados), pon el repositorio de GitHub en **público** → minutos de Actions ilimitados. Alternativa: mantener la nube en 30 min y usar el bot local para el tiempo real.

### Archivos tocados (eficiencia)

- `src/report.py` — cache 48h, batch en Sistema 2, umbral ETFs, health-check
- `src/analyzer.py` — `analyze_batch_breaking()`, reporte diario con `prefer`
- `src/llm.py` — `prefer` en `get_failover_chain()`/`chat()`
- `src/watchlist.py` — `NOISY_ETF_TICKERS`, `is_noisy_etf()`
- `config.yaml` — `filter.commodity_min_score: 70`


---

## 13 de julio, 2026 — Fix de precisión del watchlist (falsos positivos)

**Problema:** el Sistema 2 enviaba noticias que NO eran de la lista (ej. SpaceX, Paramount, macro de empleo/Fed). Causa: `match_company` buscaba en el **resumen** además del título y por **subcadena**, así que menciones de pasada colaban la noticia:
- SpaceX entró por su resumen ("Elon Musk's... Nasdaq-100") → matcheaba TSLA (alias "Elon Musk") y QQQ.
- Macro de empleo entró por "Dow Jones consensus" en el resumen → matcheaba DIA.

**Arreglo (`src/watchlist.py` → `match_company`):**
- Ahora busca **solo en el TÍTULO** (el sujeto real de la noticia), no en el resumen.
- Coincidencia por **palabra completa** (`_word_match`), no por subcadena, también para nombres y alias.

**Config:** se quitó el alias **"Elon Musk"** de TSLA (Musk dirige SpaceX/xAI/X, no solo Tesla).

**Verificado:** SpaceX, World Cup jobs, Fed rate hike, Middle East, Paramount → descartadas. Netflix→NFLX, Micron→MU, NVIDIA→NVDA, oil prices→USO, Amazon→AMZN → siguen matcheando.

### Sobre el seguimiento del Sistema 1 (results_tracker)
Funciona: envía la actualización cuando el evento tiene **valor numérico real** (ej. Monthly Budget Statement con déficit real -120.0B, beat). Los **discursos de la Fed no tienen dato numérico**, por eso no generan actualización (no hay resultado que comparar). Es el comportamiento correcto por diseño.


---

## 13 de julio, 2026 — Máximo 1 alerta por ticker por ejecución

**Problema:** llegaban 2 alertas del mismo activo (ej. USO) porque eran titulares distintos de webs distintas sobre el mismo tema (petróleo), redactados diferente, y el dedup por similitud no los juntaba.

**Arreglo (`src/report.py` → `run_breaking_alerts`, PASO 3):** ahora, entre las noticias que pasan el umbral, se envía como **máximo 1 alerta por ticker** en cada ejecución, quedándose con la de **mayor confianza**. Las demás del mismo ticker se omiten (no se marcan como enviadas, así que si en la siguiente ejecución siguen siendo relevantes, pueden salir). Elimina los duplicados de tema aunque los titulares sean distintos.


---

## 13 de julio, 2026 — Fuente Reuters + AP (agencias de cable)

Se añadió `src/sources/reuters.py` (`ReutersSource`, nombre `reuters`), que trae titulares de **Reuters** y **Associated Press** vía **Google News RSS** filtrado por dominio (`site:reuters.com` / `site:apnews.com`) y últimas 24h (`when:1d`). Se hace así porque los RSS oficiales de Reuters/AP ya no están disponibles.

- Registrada en `report.py` (`NEWS_SOURCES`, primera de la lista) y en `config.yaml` (`sources.reuters.enabled: true`).
- Prioridad de dedup **máxima**: `reuters`=5, `associated press`=5 (por encima de Bloomberg=4). Si la misma noticia sale en Reuters/AP y en otra web, se conserva la de la agencia.
- Los títulos de Google News (" - Reuters") se limpian automáticamente.
- Probado: 30 titulares frescos (Fed Waller, Wall Street, chips, petróleo, TSMC earnings).

**Fuentes actuales del Sistema 2:** Reuters/AP, CNBC/MarketWatch (investing), Yahoo Finance, Finviz, Bloomberg.


---

## 13 de julio, 2026 — Alertas de PRECIO (yfinance) — Sistema 2b

Nueva función: avisa cuando un ticker de la watchlist se mueve fuerte en el día (% vs cierre anterior), aunque no haya salido una noticia. Complementa las alertas de noticias.

- Nuevo módulo `src/price_alerts.py` (`run_price_alerts`), usa **yfinance** (gratis, sin API key).
- Umbral configurable: `filter.price_move_pct` (default **5%**).
- Envía **un solo mensaje consolidado** con todos los que superan el umbral (no spam), ordenados por magnitud.
- **Dedup por día y dirección**: no repite el mismo ticker+dirección el mismo día (`data/cache/sent_price_DATE.json`).
- Solo alerta con **datos frescos de hoy** (evita movimientos viejos de fin de semana/feriado).
- Símbolos de índice mapeados a Yahoo (`SPX` → `^GSPC`).
- Se ejecuta dentro de `run_breaking_alerts` (local cada 5 min y en la nube), en try/except para no afectar las alertas de noticias.
- `yfinance>=0.2.40` añadido a `requirements.txt`.
- **Probado:** los 40 tickers con datos frescos; detectó SOXL -14%, USO +8.4%, ORCL -6.5%, INTC -6.1%, URA -5.2%.

Nota: yfinance también habilita a futuro el snapshot de mercado en el reporte diario y la "reacción de precio" para eventos sin dato numérico (discursos Fed).


---

## 13 de julio, 2026 — Panorama de mercado en el reporte diario (yfinance)

Nuevo módulo `src/market_snapshot.py` (`format_market_snapshot`): antepone al reporte diario del Sistema 1 un bloque con el estado del mercado (cambio % del día vs cierre anterior), dentro de un `<blockquote expandable>`:
- Índices: S&P 500, Nasdaq 100, Dow Jones, Russell 2000
- Volatilidad: VIX (nivel + %)
- Materias primas: WTI (petróleo), Oro
- Bono 10Y (rendimiento) y Dólar (DXY)
- **Sin cripto** (solo bolsa/mercado, por preferencia del usuario)

Detalles:
- Semáforo 🟢/🔴/⚪ por dirección (en VIX se invierte: subida del VIX = 🔴).
- Ventana de 5 días en yfinance para que futuros/índices tengan ≥2 cierres válidos (evita "+0.0%" falsos).
- Integrado en `generate_daily_report` (se antepone a `format_daily_report`), en try/except para no romper el reporte.
- **Probado:** S&P -0.8%, Nasdaq -1.9%, VIX 17.2 (+14.2%), WTI +11.2%, Oro -2.5%, 10Y 4.61%, DXY +0.3%.


---

## 13 de julio, 2026 — Calendario de earnings + etiquetas más claras del snapshot

**Earnings próximos:** nuevo módulo `src/earnings_calendar.py` (`format_earnings_calendar`). Añade al reporte diario un bloque con las empresas de la watchlist que reportan resultados en los próximos 7 días (vía yfinance `Ticker.calendar`). Marca 🔔 HOY si reportan ese día. Los ETFs/índices se omiten (no tienen earnings). Integrado en `generate_daily_report` junto al snapshot (variable `header`). Probado: detectó C (Citigroup) 14/07 y NFLX 16/07 en 7 días; lista completa de 29 empresas en 30 días.

**Snapshot más claro:** las etiquetas ahora explican qué es cada cosa:
- S&P 500 (índice 500 grandes empresas EE.UU.), Nasdaq 100 (índice tecnológicas), Dow Jones (índice 30 industriales), Russell 2000 (índice small caps), VIX (índice del miedo / volatilidad), Petróleo WTI (crudo), Oro (onza), Bono del Tesoro EE.UU. 10 años (rendimiento), Índice del dólar (DXY).

**Resumen mejoras estilo market-intel-bot:** (1) alertas de precio ✅, (2) panorama de mercado en reporte diario ✅, (3) calendario de earnings ✅.


---

## 13 de julio, 2026 — Alertas de precio como IMAGEN profesional (matplotlib)

Las alertas de precio (Sistema 2b) ahora se envían como una **imagen** en vez de solo texto:
- Nuevo módulo `src/price_chart.py` (`render_price_movers_image`): gráfico de barras horizontal, tema oscuro tipo terminal financiera, verde/rojo, con %, precio y marca AlphaBot. Ordenado por mayor movimiento arriba. Etiquetas limpias sin solapamiento.
- Nueva función `notifier.send_photo_to_telegram()` (usa `sendPhoto` de Telegram, caption con nombres).
- `run_price_alerts` genera la imagen y la envía como foto con caption; si la imagen falla, cae a texto (robusto).
- `matplotlib>=3.8.0` añadido a `requirements.txt`.
- **Probado en vivo:** imagen generada e inspeccionada (SOXL -14%, USO +8.4%, ORCL, INTC, URA), enviada a Telegram (SENT_MOVERS=5).

Nota sobre imágenes/animaciones: se descartó Midjourney/IA generativa porque inventa/deforma los números (no sirve para datos exactos) y no tiene API práctica. matplotlib da una imagen profesional, fiable y ligera que funciona igual en local y en la nube. Opción futura de mayor "diseño": tarjeta HTML/CSS renderizada con navegador headless (más pesada).


---

## 13 de julio, 2026 — FIX DEFINITIVO de repeticiones (Sistema 2): estado compartido

**Causa raíz encontrada:** el bot enviaba desde DOS lugares (bot local + nube GitHub
Actions, repo público con cron activo) y **la nube olvidaba su memoria en cada
ejecución** porque `data/cache/` está en `.gitignore` (no se sube). Cada corrida de la
nube arrancaba sin saber qué se había enviado → repetía. Además local y nube no
compartían estado.

**Solución (Opción 2 — una sola fuente de verdad):**
- Nuevo módulo `src/sent_state.py`: guarda las firmas de lo enviado en
  `data/state/sent_alerts.json` (**rastreado por git**, ventana 48h, formato
  {firma: timestamp}).
- `report.py`: `load_sent_alerts()` lee ese estado; `run_breaking_alerts` hace
  `pull()` al inicio (git pull en local; en la nube el checkout ya trae lo último) y
  `record_and_sync(nuevas)` al final (git commit + push con reintentos, unión sin
  conflictos de merge). Local y nube comparten el mismo estado → **ninguno repite**.
- Migradas las 28 firmas del cache del día al nuevo estado (no reenvía lo de hoy).
- Los workflows ya tienen `permissions: contents: write` para poder pushear.

Con esto, corran juntos o por separado (PC encendida o apagada), no se repiten noticias.
