# Sonda (solo lectura): rutas /admin declaradas en pages.py local (dev) y si existe la página work-persons.
$f = "D:\Proyectos\AI_OSAP\osap-storage\api\routes\pages.py"
Select-String -Path $f -Pattern '@router\.(get|post)\("/admin' | ForEach-Object { "{0}: {1}" -f $_.LineNumber, $_.Line.Trim() }
"--- referencias a work-persons en plantillas/rutas locales:"
Get-ChildItem D:\Proyectos\AI_OSAP\osap-storage -Recurse -Include *.py, *.html -File |
Where-Object { $_.FullName -notmatch '__pycache__' } |
Select-String -Pattern 'admin/work-persons' |
Select-Object -First 10 | ForEach-Object { "{0}:{1}: {2}" -f $_.Filename, $_.LineNumber, $_.Line.Trim() }
