-- 2026-10-18 · obras: rango de fechas por obra (migración aditiva).
-- Ejecutar como root: sudo mysql osap_storage < 2026-10-18-works-year-range.sql
-- El usuario de la app no tiene ALTER; es idempotente.

SET @sql = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE works ADD COLUMN works_year_from SMALLINT NULL AFTER works_year',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'osap_storage' AND TABLE_NAME = 'works'
    AND COLUMN_NAME = 'works_year_from'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE works ADD COLUMN works_year_to SMALLINT NULL AFTER works_year_from',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'osap_storage' AND TABLE_NAME = 'works'
    AND COLUMN_NAME = 'works_year_to'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- La FK `fk_works_epoch` (works_epoch_id -> epochs.id, ON DELETE SET NULL) ya existe.
