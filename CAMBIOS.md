# 📝 Registro de cambios — AlphaBot

> Este archivo documenta las correcciones y mejoras aplicadas al proyecto.
> Complementa a `MANUAL.md` y `AGENTS.md`. Los sub-agentes deben leerlo.

---

## 14 de julio, 2026 (noche) — Sistema 1: panorama aparte, todos los eventos 2+★ y desplegables

Rediseño de la presentación del reporte diario (Sistema 1) según pedido del usuario:

### 1. Panorama y earnings como MENSAJES APARTE
- Antes `generate_daily_report` anteponía el panorama de mercado (`market_snapshot`) y los earnings DENTRO del mismo mensaje del reporte de eventos (variable `header`).
- Ahora `generate_daily_report` devuelve SOLO el texto de los eventos económicos. El panorama y los earnings se generan por separado con dos funciones nuevas en `src/report.py`: `build_market_snapshot_message()` y `build_earnings_message()`.
- `run_and_send` envía **tres mensajes independientes** en orden: (a) panorama, (b) earnings, (c) reporte de eventos. El guard anti-duplicado (`daily_report_sent_today` / `mark_daily_report_sent`) se mantiene; `force=True` lo salta (uso manual).
- El dry-run (`run_report.py --daily --no-send`) muestra los tres mensajes por separado.

### 2. Panorama simplificado (estilo limpio tipo Sistema 2)
- En `src/market_snapshot.py` se **eliminó el Bono del Tesoro 10 años (`^TNX`) y el índice del dólar DXY (`DX-Y.NYB`)** (el usuario no los quiere).
- Quedan solo: S&P 500, Nasdaq, Dow Jones, Russell 2000, VIX (miedo), Petróleo (WTI) y Oro.
- Nombres cortos + emojis (🟢/🔴/⚪ por dirección; 😨 VIX; 🛢️ Petróleo; 🥇 Oro). Encabezado "🌎 CÓMO ESTÁ EL MERCADO HOY". Sin `<blockquote>` (es corto y claro).

### 3. TODOS los eventos de 2+ estrellas
- En `generate_daily_report` se **quitó el límite `items = items[:10]`** que descartaba eventos válidos. Ahora salen TODOS los de 2+ estrellas (tope de seguridad alto en 40). El análisis por lotes (`analyze_batch`, chunk_size=4) los procesa todos.
- Se reemplazó `deduplicate()` (fusiona por similitud de tokens) por **`dedup_calendar()`**, específico del calendario: NO fusiona eventos macro con títulos distintos, solo quita duplicados exactos (mismo título + hora). Así "Fed Chair Warsh Testimony" y "Fed Barr Speech" ya no se fusionan.
- **Verificado hoy:** el scraper de Finviz trajo 19 eventos, **14 con 2+ estrellas** (5 de 3★ + 9 de 2★). El reporte incluyó los 14. Coinciden.

### 4. Flechita desplegable por evento
- `format_daily_report` ya envolvía cada evento en `<blockquote expandable>` (titular visible + detalle plegable). Se confirma el comportamiento y se mantiene el footer AlphaBot una sola vez al final.
- Se **quitó la truncación interna a 4000 chars** de `format_daily_report` (antes cortaba eventos con "... (truncado)"). Ahora el mensaje completo se parte en el notifier.
- `src/notifier.py`: nueva función `_balance_blockquotes()` en `_split_message()` que **equilibra las etiquetas `<blockquote>`** al partir mensajes largos, para que cada fragmento sea HTML válido (cierra el blockquote abierto y lo reabre en el siguiente). Verificado: reporte de 15k chars → 4 fragmentos, todos con opens==closes.

### 5. Nada de bonos del Tesoro en el análisis
- En `src/system_prompt.md` se añadió una sección de preferencias: NO centrar beneficiados/perjudicados en bonos del Tesoro / Treasuries salvo que sea imprescindible; priorizar acciones, sectores e índices bursátiles.

### 6. Envío real
- Se envió UNA vez el reporte con la nueva presentación (`run_and_send(reasoning=False, force=True)`): panorama simplificado (aparte), earnings (aparte) y reporte con los **14 eventos de 2+ estrellas**, cada uno con su desplegable. Reporte de 15.483 chars.

---

## 14 de julio, 2026 (tarde)

### Seguimiento de resultados (Sistema 1) — CONSOLIDADO en un solo mensaje

- **Antes:** `run_results_tracking()` en `src/results_tracker.py` enviaba **un mensaje por cada** evento con resultado listo (llamaba a `format_results_followup` + `send_to_telegram` dentro del bucle).
- **Ahora:** primero **recolecta TODOS** los seguimientos listos de la corrida (los que ya tienen valor `actual` y se re-analizaron) y luego decide cómo enviarlos:
  - **2 o más** eventos → **UN solo mensaje consolidado**: encabezado "📊 SEGUIMIENTO DE RESULTADOS" + día/fecha, cada evento en su propio `<blockquote expandable>` (deslizamiento) y el footer AlphaBot **una sola vez** al final.
  - **1** evento → mensaje individual (comportamiento previo con `format_results_followup`).
- **Nuevas funciones en `src/formatter.py`:**
  - `_result_event_block(entry, results)` → devuelve el `<blockquote expandable>` de UN evento (título, fuente, Forecast/Anterior/Actual, ✅ BEAT / ❌ MISS / ➡️ EN LÍNEA, análisis real, beneficiados/perjudicados, reacción, enlace), sin encabezado ni footer, para reutilizar.
  - `format_results_followup_group(items)` → arma el mensaje consolidado con N desplegables y un único footer.
- **Sin cambios en la detección de resultados:** solo cambió cómo se **agrupa el envío**. Se sigue marcando cada evento con `mark_event_followed` (no repetir) y se guarda `save_alert_backup` **por evento** (no se pierde ningún respaldo).
- **Envío HTML:** `send_to_telegram(..., parse_mode="HTML")`; el notifier parte a 4096 chars si hace falta.
- **Prueba (aislada, temporal):** 3 seguimientos de ejemplo → 1 solo texto con 3 `<blockquote expandable>`, 1 encabezado y 1 footer. ✅ Test borrado tras verificar.

### Ejecución real del Sistema 1 (reporte de hoy)

- Se ejecutó el envío REAL del reporte diario. El comando `run_report.py --daily` estaba fuera de la ventana horaria (7-8 AM NY), así que ese guard de ahorro de tokens lo omitía; se envió con `run_and_send(reasoning=False)`, que **respeta el guard anti-duplicado** `daily_report_sent_today` (estaba en False: aún no se había enviado hoy). Resultado: **reporte enviado a Telegram con 10 eventos macro** (4675 chars) y guard marcado.

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


---

## 14 de julio, 2026 — CLOUD-ONLY: la nube es el único emisor de alertas

Decisión del usuario: para eliminar de raíz las repeticiones (antes emitían PC +
nube sin memoria común), **solo la nube (GitHub Actions) emite alertas**. El bot
local pasa a ser un cliente de comandos/publicaciones.

### 1. Bot local ya no emite alertas automáticas

- `bot_local.py`: nuevo flag `_local_send_alerts()` que lee el env
  `LOCAL_SEND_ALERTS` (prioridad) o `coordination.local_send_alerts` en
  `config.yaml`. **Default `false`** (cloud-only).
- Con el default, el bucle NO ejecuta el Sistema 2 (`run_breaking_alerts`), el
  Sistema 1 (`run_and_send`) ni el seguimiento de resultados. Solo atiende
  **comandos/publicaciones** de Telegram cada 30s.
- **Excepción bajo demanda:** si el usuario manda `/report` o `/breaking` por
  Telegram, se ejecuta igual (acción explícita). `/report` usa `force=True` para
  saltarse el guard diario.
- Poniendo el flag en `true` se recupera el modo antiguo (PC emisora).

### 2. Memoria persistente + eliminación del heartbeat

- Se mantiene `data/state/sent_alerts.json` (rastreado por git, 48h). En la nube
  `pull()` es no-op y `record_and_sync()` hace commit/push tras enviar.
- Las noticias con firma ya presente se descartan **antes del análisis LLM**
  (ahorro de tokens) — confirmado en `run_breaking_alerts` (PASO 1).
- **Eliminada toda la lógica de heartbeat/coordinación** PC↔nube (ya no aplica
  con un solo emisor): se quitaron `write_heartbeat`, `_read_heartbeat`,
  `local_is_alive` y `HEARTBEAT_FILE` de `sent_state.py`, y el bloque de cesión
  en `report.run_breaking_alerts`.

### 3. Fix Sistema 1: cron fiable + guard de una-vez-al-día

- `.github/workflows/system1-daily.yml`: el cron pasó de `0 11`/`0 12` (que
  GitHub retrasa/salta) a **`15,35,55 11 * * *`** y **`15,35,55 12 * * *`**
  (3 intentos desfasados por hora, dentro de la ventana 7-8 AM NY).
- Nuevo **GUARD** en el estado compartido `data/state/daily_report.json`
  ({ "date": "YYYY-MM-DD" } hora NY). `run_and_send` consulta
  `daily_report_sent_today()` antes de generar y llama a
  `mark_daily_report_sent()` tras enviar. Aunque el cron dispare varias veces,
  el reporte sale **UNA sola vez al día**.
- Ambos workflows conservan `permissions: contents: write` y el checkout deja el
  token con push.

### 4. Agrupación de fuentes, Finviz fuera del S2, batch (ya vigentes)

- `NewsItem.sources: list[str]` + `deduplicate()` acumula todas las fuentes y
  conserva la de mayor prioridad; `format_breaking_alert` muestra
  "📰 N fuentes: A, B, C" si hay más de una. Verificado en pruebas aisladas.
- `config.yaml`: `sources.finviz.enabled: false` (Sistema 2). El Sistema 1 sigue
  con `finviz_calendar`. `coordination.local_send_alerts: false`.
- `analyze_batch` troceado (chunk_size=4, max_tokens 3500) + `_parse_json`
  recupera JSON truncado → el reporte diario sale completo (verificado en
  dry-run con Core Inflation, Inflation YoY, testimonio Fed, ADP).

### Pruebas (sin enviar a Telegram)

- `_verify_plan.py` (temporal, eliminado tras probar): dedup 3 fuentes → 1 item
  con `sources` de 3 y conserva Reuters; "3 fuentes" en el formato; 1 fuente sin
  línea extra; noticia repetida descartada antes del LLM; guard presente y
  heartbeat eliminado; flag `LOCAL_SEND_ALERTS` controla la emisión. **Todo OK.**
- `run_report.py --daily --no-send --no-reasoning`: reporte completo. ✅
- Imports OK: `src.report, src.sent_state, src.analyzer, src.formatter, bot_local`.

### Archivos tocados

- `bot_local.py` — flag cloud-only, bucle condicionado, `/report` force
- `src/report.py` — quitado heartbeat, guard diario en `run_and_send`
- `src/sent_state.py` — eliminado heartbeat, añadido guard `daily_report.json`
- `run_report.py` — `daily_forced` para `/report` manual
- `config.yaml` — `coordination.local_send_alerts: false`
- `.github/workflows/system1-daily.yml` — cron desfasado (15,35,55)
- `.kiro/specs/sistema2-cloud-only/` — requirements, design, tasks
