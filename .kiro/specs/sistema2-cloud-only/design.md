# Diseño — Sistema 2 Cloud-Only

## Visión general

La nube (GitHub Actions) pasa a ser el ÚNICO emisor de alertas. El bot local se
degrada a un cliente de comandos/publicaciones de Telegram. La memoria compartida
(`data/state/`) rastreada por git elimina las repeticiones. Se elimina la
coordinación por heartbeat porque con un solo emisor ya no hace falta.

## Componentes y cambios

### 1. `bot_local.py` — emisor local opt-in
- Nuevo `_local_send_alerts()`: lee `LOCAL_SEND_ALERTS` (env, prioridad) o
  `coordination.local_send_alerts` (config); default `False`.
- Constante `SEND_ALERTS` calculada al inicio.
- En el bucle `main()`: los flujos automáticos (Sistema 2, Sistema 1, seguimiento)
  solo se ejecutan si `SEND_ALERTS` es `True`. Los comandos y los triggers
  manuales `/report` y `/breaking` siempre se atienden.
- El trigger manual `/report` llama a `run_and_send(..., force=True)` para saltarse
  el guard diario (es acción explícita del usuario).

### 2. `src/report.py`
- `run_breaking_alerts`: se elimina el bloque de coordinación por heartbeat
  (pull + `local_is_alive` + cesión). Comentario que explica el modo cloud-only.
- `run_and_send(reasoning, force=False)`: guard anti-duplicado del reporte diario.
  Si `force` es `False`, hace `pull()` + `daily_report_sent_today()`; si ya salió
  hoy (hora NY) se omite. Tras enviar con éxito llama a `mark_daily_report_sent()`.
- `deduplicate()` (ya existente): agrupa por similitud de tokens, conserva la
  fuente de mayor prioridad y acumula `item.sources`.

### 3. `src/sent_state.py`
- Se eliminan `write_heartbeat`, `_read_heartbeat`, `local_is_alive` y
  `HEARTBEAT_FILE`.
- Nuevo guard del reporte diario:
  - `DAILY_FILE = data/state/daily_report.json` ({ "date": "YYYY-MM-DD" } hora NY).
  - `daily_report_sent_today()`: True si `date` == hoy NY.
  - `mark_daily_report_sent()`: escribe + git add/commit/push con reintentos.

### 4. `src/analyzer.py` (ya aplicado, se deja robusto)
- `analyze_batch(chunk_size=4, max_tokens=3500)`: trocea, una llamada por lote,
  lista alineada por `idx` dentro del lote.
- `_parse_json`: recuperación de arrays truncados hasta el último `}`.

### 5. `src/formatter.py` (ya aplicado)
- `format_breaking_alert`: línea "📰 N fuentes: ..." solo si hay >1 fuente.

### 6. Config y workflows
- `config.yaml`: `coordination.local_send_alerts: false` (sustituye a
  `heartbeat_max_min`). `sources.finviz.enabled: false`.
- `.github/workflows/system1-daily.yml`: cron `15,35,55 11 * * *` y
  `15,35,55 12 * * *`; `permissions: contents: write`.
- `.github/workflows/system2-breaking.yml`: `permissions: contents: write`.

## Manejo de errores
- Todas las operaciones de git en `sent_state` van en try/except y reintentos; si
  fallan, el estado local igual queda escrito y se reintenta en la próxima
  ejecución. No son fatales.
- El guard diario en `run_and_send` va en try/except: si falla la lectura del
  estado, no bloquea el envío.

## Estrategia de pruebas
- Aisladas (sin Telegram): dedup de 3 fuentes, formato "N fuentes", descarte
  pre-LLM de repetidas, existencia del guard y eliminación del heartbeat, flag
  cloud-only.
- Integración dry-run: `run_report.py --daily --no-send --no-reasoning` genera un
  reporte completo.
