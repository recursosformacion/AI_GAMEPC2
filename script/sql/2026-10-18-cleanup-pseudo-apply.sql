-- 2026-10-18 · Limpieza de personas placeholder (con backup).
-- Ejecutar como root: sudo mysql osap_storage < 2026-10-18-cleanup-pseudo-apply.sql
-- Reglas:
--   * ANONIMA: anónimo/anonymous/anon, rangos de fechas y resto de pseudo.
--   * TRADICIONAL: tradicional/traditional/traditionell/popular/folk/volkslied.
--   * DESCONOCIDO: desconocido/unknown/unattributed.
--   * VARIOS: various.
--   * Las personas se BORRAN (no se desactivan); los vínculos caen en cascada.
--   * Solo se marca `works_attr_type` cuando está NULL (no se pisa lo ya definido).

START TRANSACTION;

CREATE TABLE IF NOT EXISTS cleanup_20261018_persons LIKE persons;
INSERT INTO cleanup_20261018_persons
SELECT p.* FROM persons p
WHERE p.persons_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|volkslied|[[:space:]]*[(])'
   OR p.persons_id IN (SELECT persons_id FROM pseudo_persons_backup);

CREATE TABLE IF NOT EXISTS cleanup_20261018_wpr LIKE works_person_roles;
INSERT INTO cleanup_20261018_wpr
SELECT w.* FROM works_person_roles w
JOIN cleanup_20261018_persons p ON p.persons_id = w.works_person_roles_person_id;

CREATE TABLE IF NOT EXISTS cleanup_20261018_works LIKE works;
INSERT INTO cleanup_20261018_works
SELECT DISTINCT w.* FROM works w
JOIN works_person_roles r ON r.works_person_roles_work_id = w.id
JOIN cleanup_20261018_persons p ON p.persons_id = r.works_person_roles_person_id
JOIN roles ro ON ro.id = r.works_person_roles_role_id
WHERE ro.role_name = 'Compositor/a';

-- Marca de atribución (solo donde está vacía)
UPDATE works w
JOIN works_person_roles r ON r.works_person_roles_work_id = w.id
JOIN cleanup_20261018_persons p ON p.persons_id = r.works_person_roles_person_id
JOIN roles ro ON ro.id = r.works_person_roles_role_id
SET w.works_attr_type = CASE
      WHEN p.persons_name REGEXP '^(tradicional|traditional|traditionell|popular|folk|volkslied)' THEN 'TRADICIONAL'
      WHEN p.persons_name REGEXP '^(desconocido|unknown|unattributed)' THEN 'DESCONOCIDO'
      WHEN p.persons_name REGEXP '^various' THEN 'VARIOS'
      ELSE 'ANONIMA' END
WHERE ro.role_name = 'Compositor/a'
  AND w.works_attr_type IS NULL;

-- Regla: sin compositor y rango > 100 años -> ANONIMA (hoy no-op: aún no hay rangos).
UPDATE works w
SET w.works_attr_type = 'ANONIMA'
WHERE w.works_attr_type IS NULL
  AND w.works_year_from IS NOT NULL
  AND w.works_year_to IS NOT NULL
  AND (w.works_year_to - w.works_year_from) > 100
  AND NOT EXISTS (
        SELECT 1 FROM works_person_roles r
        JOIN roles ro ON ro.id = r.works_person_roles_role_id AND ro.role_name = 'Compositor/a'
        WHERE r.works_person_roles_work_id = w.id
      );

-- Época por año inicial del rango (o año puntual), solo si el puntero está vacío.
UPDATE works w
JOIN epochs e
  ON (e.year_start IS NULL OR COALESCE(w.works_year_from, w.works_year) >= e.year_start)
 AND (e.year_end   IS NULL OR COALESCE(w.works_year_from, w.works_year) <  e.year_end)
SET w.works_epoch_id = e.id
WHERE w.works_epoch_id IS NULL
  AND COALESCE(w.works_year_from, w.works_year) IS NOT NULL;

-- Borrado (cascada sobre vínculos/evidencias; SET NULL en el resto)
DELETE p FROM persons p
JOIN cleanup_20261018_persons c ON c.persons_id = p.persons_id;

COMMIT;

SELECT 'personas en backup' AS k, COUNT(*) AS v FROM cleanup_20261018_persons;
SELECT 'vinculos en backup' AS k, COUNT(*) AS v FROM cleanup_20261018_wpr;
SELECT 'obras en backup' AS k, COUNT(*) AS v FROM cleanup_20261018_works;
SELECT 'personas restantes' AS k, COUNT(*) AS v FROM persons;
