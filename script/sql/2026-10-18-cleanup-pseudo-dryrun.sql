-- Dry-run (solo lectura) de la limpieza de personas placeholder.
SELECT 'personas candidatas' AS k, COUNT(*) AS v
FROM persons
WHERE persons_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|volkslied|[[:space:]]*[(])'
   OR persons_id IN (SELECT persons_id FROM pseudo_persons_backup);

SELECT CASE
         WHEN persons_name REGEXP '^(tradicional|traditional|traditionell|popular|folk|volkslied)' THEN 'TRADICIONAL'
         WHEN persons_name REGEXP '^(desconocido|unknown|unattributed)' THEN 'DESCONOCIDO'
         WHEN persons_name REGEXP '^various' THEN 'VARIOS'
         ELSE 'ANONIMA' END AS attr,
       COUNT(*) AS personas
FROM persons
WHERE persons_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|volkslied|[[:space:]]*[(])'
   OR persons_id IN (SELECT persons_id FROM pseudo_persons_backup)
GROUP BY attr ORDER BY personas DESC;

SELECT 'vinculos compositor afectados' AS k, COUNT(*) AS v
FROM works_person_roles r
JOIN persons p ON p.persons_id = r.works_person_roles_person_id
JOIN roles ro ON ro.id = r.works_person_roles_role_id
WHERE ro.role_name = 'Compositor/a'
  AND (p.persons_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|volkslied|[[:space:]]*[(])'
       OR p.persons_id IN (SELECT persons_id FROM pseudo_persons_backup));

SELECT 'obras afectadas' AS k, COUNT(DISTINCT r.works_person_roles_work_id) AS v
FROM works_person_roles r
JOIN persons p ON p.persons_id = r.works_person_roles_person_id
JOIN roles ro ON ro.id = r.works_person_roles_role_id
WHERE ro.role_name = 'Compositor/a'
  AND (p.persons_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|volkslied|[[:space:]]*[(])'
       OR p.persons_id IN (SELECT persons_id FROM pseudo_persons_backup));

SELECT 'obras afectadas con attr NULL' AS k, COUNT(DISTINCT w.id) AS v
FROM works w
JOIN works_person_roles r ON r.works_person_roles_work_id = w.id
JOIN persons p ON p.persons_id = r.works_person_roles_person_id
JOIN roles ro ON ro.id = r.works_person_roles_role_id
WHERE ro.role_name = 'Compositor/a' AND w.works_attr_type IS NULL
  AND (p.persons_name REGEXP '^(an[oó]nimo|anonymous|anon|desconocido|unknown|unattributed|tradicional|traditional|traditionell|popular|various|folk|volkslied|[[:space:]]*[(])'
       OR p.persons_id IN (SELECT persons_id FROM pseudo_persons_backup));

-- Muestra de rangos detectados en el nombre
SELECT persons_name, REGEXP_SUBSTR(persons_name, '[0-9]{3,4}', 1, 1) AS y1,
       REGEXP_SUBSTR(persons_name, '[0-9]{3,4}', 1, 2) AS y2
FROM persons
WHERE persons_name REGEXP '[(][^)]*[0-9]{3,4}'
LIMIT 10;
