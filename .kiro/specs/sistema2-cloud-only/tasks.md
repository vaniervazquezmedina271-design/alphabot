# Plan de implementación — Sistema 2 Cloud-Only

- [x] 1. Bot local deja de emitir alertas automáticas (cloud-only)
  - Añadir `_local_send_alerts()` + flag `LOCAL_SEND_ALERTS` / `coordination.local_send_alerts` (default false)
  - Ejecutar Sistema 2 / Sistema 1 / seguimiento solo si el flag es true
  - Mantener comandos y triggers manuales `/report` (force=True) y `/breaking`
  - _Requisitos: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Memoria persistente en la nube + eliminar heartbeat
  - Mantener `data/state/sent_alerts.json` (rastreado, 48h)
  - Confirmar descarte de firmas ya enviadas antes del LLM
  - Eliminar `write_heartbeat`, `_read_heartbeat`, `local_is_alive`, `HEARTBEAT_FILE`
  - Quitar el bloque de coordinación heartbeat de `run_breaking_alerts`
  - _Requisitos: 2.1, 2.2, 2.3, 2.4_

- [x] 3. Permisos de escritura en los workflows
  - Verificar `permissions: contents: write` en ambos workflows
  - Verificar que el checkout permite `git push`
  - _Requisitos: 3.1, 3.2_

- [x] 4. Agrupación de fuentes ("N fuentes")
  - `NewsItem.sources: list[str]` (default [])
  - `deduplicate()` conserva mayor prioridad y acumula fuentes
  - `format_breaking_alert` muestra "📰 N fuentes: ..." si >1
  - _Requisitos: 4.1, 4.2, 4.3_

- [x] 5. Quitar Finviz del Sistema 2
  - `config.yaml`: `sources.finviz.enabled: false`
  - Verificar que el Sistema 1 sigue con `finviz_calendar`
  - _Requisitos: 5.1, 5.2_

- [x] 6. Fix del Sistema 1 (reporte vacío + cron)
  - `analyze_batch` troceado (chunk_size=4, max_tokens ~3500), lista alineada
  - `_parse_json` recupera JSON truncado
  - Cron desfasado (minutos 15,35,55 de 11 y 12 UTC)
  - Guard "reporte diario ya enviado hoy" en `data/state/daily_report.json`
  - Verificar dry-run genera reporte completo
  - _Requisitos: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 7. Pruebas y verificación (sin Telegram real)
  - Dedup 3 fuentes, formato N fuentes, descarte pre-LLM, guard, flag
  - Dry-run Sistema 1 completo
  - Compilación/import de módulos clave
  - _Requisitos: todos_
