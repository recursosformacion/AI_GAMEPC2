"""Capa de adquisición de ResolutionSession (FASE 2).

Provee la máquina de adquisición idempotente y reanudable: un provider se pagina por
`(session_id, provider, cursor_value)`, cada página se persiste en `provider_results` y el
progreso/estado de la sesión se mantiene en `resolution_sessions`. Aún no hay matching.
"""
