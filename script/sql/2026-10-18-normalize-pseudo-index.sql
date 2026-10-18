-- 2026-10-18 · Normaliza pseudo-compositores en storage e índice SIN vaciar el índice.
-- Ejecutar como root: sudo mysql < 2026-10-18-normalize-pseudo-index.sql
--
-- 1) Marca `works_attr_type` en las obras de storage mapeadas por representaciones
--    (el índice y `works.id` NO comparten id; el puente es
--     index_representations.resource_id -> works_resources.id -> works_resources_work_id).
-- 2) Sustituye en el índice el nombre del pseudo-compositor por su etiqueta genérica y
--    deja `person_id` a NULL (la persona ya no existe).

-- 1) Storage: marca de atribución (solo donde está NULL)
UPDATE osap_storage.works w
JOIN (
  SELECT DISTINCT wr.works_resources_work_id AS wid,
         CASE
           WHEN i.composer_name = 'Various' THEN 'VARIOS'
           WHEN i.composer_name REGEXP '^(tradicional|traditional|traditionell|popular|folk)' THEN 'TRADICIONAL'
           WHEN i.composer_name REGEXP '^(desconocido|unknown|unattributed)' THEN 'DESCONOCIDO'
           ELSE 'ANONIMA' END AS attr
  FROM osap_api.index_works i
  JOIN osap_api.index_representations ir ON ir.work_id = i.id
  JOIN osap_storage.works_resources wr ON wr.id = ir.resource_id
  WHERE i.composer_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|[[:space:]]*[(])'
) m ON m.wid = w.id
SET w.works_attr_type = m.attr
WHERE w.works_attr_type IS NULL;

-- 2) Índice: etiqueta genérica + person_id NULL
UPDATE osap_api.index_works
SET composer_name = CASE
      WHEN composer_name = 'Various' THEN 'Varios'
      WHEN composer_name REGEXP '^(tradicional|traditional|traditionell|popular|folk)' THEN 'Tradicional'
      WHEN composer_name REGEXP '^(desconocido|unknown|unattributed)' THEN 'Desconocido'
      WHEN composer_name REGEXP '^[(].*[0-9]{3,4}' THEN 'Anónimo'
      WHEN composer_name REGEXP '^[(]' THEN NULL
      ELSE 'Anónimo' END,
    person_id = NULL
WHERE composer_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|[[:space:]]*[(])';

SELECT 'obras marcadas ANONIMA' AS k, COUNT(*) AS v FROM osap_storage.works WHERE works_attr_type='ANONIMA';
SELECT 'obras marcadas TRADICIONAL' AS k, COUNT(*) AS v FROM osap_storage.works WHERE works_attr_type='TRADICIONAL';
SELECT 'obras marcadas DESCONOCIDO' AS k, COUNT(*) AS v FROM osap_storage.works WHERE works_attr_type='DESCONOCIDO';
SELECT 'obras marcadas VARIOS' AS k, COUNT(*) AS v FROM osap_storage.works WHERE works_attr_type='VARIOS';
SELECT 'indice: person_id pseudo restantes' AS k, COUNT(*) AS v FROM osap_api.index_works WHERE person_id IS NOT NULL AND composer_name IS NULL;
