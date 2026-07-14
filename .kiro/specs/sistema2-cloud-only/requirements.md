# Requisitos — Sistema 2 Cloud-Only + agrupación de fuentes + fix Sistema 1

## Introducción

El bot AlphaBot emitía alertas desde DOS lugares a la vez (el bot local en la PC
y la nube en GitHub Actions) sin una memoria común fiable, lo que provocaba
alertas repetidas. Se decide que **la NUBE sea el único emisor de alertas** para
eliminar de raíz las repeticiones. Además se agrupan las fuentes de una misma
noticia ("N fuentes"), se quita Finviz del Sistema 2 y se corrige el Sistema 1
(reporte diario que salía vacío y cron poco fiable).

## Requisitos

### Requisito 1 — La nube es el único emisor de alertas

**Historia:** Como usuario, quiero que solo la nube emita alertas, para no
recibir noticias duplicadas desde la PC y la nube a la vez.

#### Criterios de aceptación
1. CUANDO el bot local corre en su modo por defecto ENTONCES NO debe ejecutar
   automáticamente el Sistema 2 (`run_breaking_alerts`), el Sistema 1
   (`run_and_send`) ni el seguimiento de resultados en su bucle.
2. CUANDO el bot local corre ENTONCES SÍ debe seguir atendiendo comandos y
   publicaciones de Telegram (`process_commands`, `pop_trigger`, `/list`,
   add/remove, audios).
3. CUANDO existe el flag `LOCAL_SEND_ALERTS` (env) o `coordination.local_send_alerts`
   (config) ENTONCES su valor por defecto debe ser `false` (cloud-only) y debe
   poder ponerse en `true` para reactivar la emisión local.
4. CUANDO el usuario manda `/report` o `/breaking` manualmente por Telegram
   ENTONCES esa acción SÍ se ejecuta bajo demanda, respetando el estado
   compartido para no duplicar.

### Requisito 2 — Memoria persistente anti-repetición en la nube

**Historia:** Como usuario, quiero que la nube recuerde lo ya enviado, para que
no repita noticias entre ejecuciones.

#### Criterios de aceptación
1. CUANDO se envía una alerta ENTONCES su firma se guarda en
   `data/state/sent_alerts.json` (rastreado por git, ventana 48h).
2. CUANDO corre en la nube (`GITHUB_ACTIONS`) ENTONCES `pull()` es no-op y
   `record_and_sync()` hace git add/commit/push del estado tras enviar.
3. CUANDO una noticia tiene una firma ya presente en el estado ENTONCES se
   descarta ANTES del análisis LLM (ahorro de tokens).
4. CUANDO existía lógica de "heartbeat"/coordinación entre emisores ENTONCES se
   elimina (no se usa en cloud-only).

### Requisito 3 — Permisos de escritura en la nube

**Historia:** Como operador, quiero que los workflows puedan escribir el estado,
para que la memoria persista y no se repita.

#### Criterios de aceptación
1. CUANDO se define `system2-breaking.yml` o `system1-daily.yml` ENTONCES deben
   incluir `permissions: contents: write`.
2. CUANDO el checkout se ejecuta ENTONCES deja el token con permiso de `git push`
   al mismo repositorio.

### Requisito 4 — Agrupación de fuentes ("N fuentes")

**Historia:** Como usuario, quiero ver todas las fuentes que publicaron una misma
noticia, para conocer su cobertura.

#### Criterios de aceptación
1. CUANDO se define `NewsItem` ENTONCES tiene un campo opcional `sources: list[str]`
   (default `[]`).
2. CUANDO `deduplicate()` agrupa la misma noticia de varias fuentes ENTONCES
   conserva la de MAYOR prioridad (`_SOURCE_PRIORITY`) y acumula en `item.sources`
   los nombres de TODAS las fuentes (incluida la propia, sin duplicar).
3. CUANDO `format_breaking_alert` recibe >1 fuente ENTONCES añade la línea
   "📰 N fuentes: A, B, C"; SI es 1, no añade línea extra.

### Requisito 5 — Quitar Finviz del Sistema 2

**Historia:** Como usuario, quiero quitar Finviz noticias del Sistema 2, para
reducir ruido/duplicados, sin afectar al Sistema 1.

#### Criterios de aceptación
1. CUANDO se lee `config.yaml` ENTONCES `sources.finviz.enabled` es `false`.
2. CUANDO corre el Sistema 1 ENTONCES sigue usando `finviz_calendar` (distinto) y
   funciona.

### Requisito 6 — Fix del Sistema 1 (reporte vacío + cron)

**Historia:** Como usuario, quiero que el reporte diario salga completo y una sola
vez al día, aunque el cron dispare varias veces.

#### Criterios de aceptación
1. CUANDO `analyze_batch` analiza ~10 eventos ENTONCES trocea en lotes
   (chunk_size=4), una llamada LLM por lote, y devuelve una lista ALINEADA con
   los items (None si falla), con `max_tokens` por lote ~3500.
2. CUANDO `_parse_json` recibe un JSON truncado ENTONCES recupera los objetos
   completos hasta el último `}` y cierra el array.
3. CUANDO se ejecuta `run_report.py --daily --no-send --no-reasoning` ENTONCES
   genera un reporte COMPLETO con eventos analizados (no "No se pudo analizar").
4. CUANDO GitHub retrasa/salta el cron a la hora en punto ENTONCES se usan
   minutos desfasados y varios intentos en la ventana 7-8 AM NY (minutos 15,35,55
   de las horas 11 y 12 UTC).
5. CUANDO el cron dispara varias veces el mismo día ENTONCES un GUARD en el estado
   compartido (`data/state/daily_report.json`) hace que el reporte salga UNA sola
   vez al día.
