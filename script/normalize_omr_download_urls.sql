-- Normaliza las URLs de OMR del índice a rutas relativas.
--
-- Los hosts dependen del entorno (storage local, dominio público, CDN). La API resuelve
-- `/api/download/<file_id>` con `[osap] storage_web_base`. CPDL/IMSLP/Mutopia conservan
-- sus URLs absolutas.
--
-- Aplicar en mantenimiento, con copia previa. Es idempotente.

UPDATE index_representations
SET download_url = SUBSTRING(download_url, LOCATE('/api/download/', download_url))
WHERE provider = 'omr'
  AND download_url LIKE '%/api/download/%'
  AND download_url NOT LIKE '/api/download/%';
