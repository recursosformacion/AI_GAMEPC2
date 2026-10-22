# Subida 5.5.0 — checklist con mantenimiento

Clasificación: **B (mejora compatible)**. Alcance: `osap-api` + `osap-auth` (+ versión del
conjunto). Fecha de ventana: **2026-10-22, 12:00–13:00 (Europe/Madrid)**.

**Esta subida NO despliega el SSR de React.** Producción sigue sirviendo `/composers`,
`/composers/{id}` y `/obras/{id}` con osap-api (Jinja). El servidor Node y el proxy 3000 se
reservan para `docs/osap/prod-ssr-plan.md`.

## Antes

```powershell
pwsh script/check-versions.ps1 -Expected 5.5.0
pwsh script/predeploy_backup.ps1        # BBDD + programas en ~/backups/<fecha>
```

Comprobaciones ya ejecutadas:

- `pytest tests/osap` → **913** OK.
- `ruff` + `mypy src/osap` → OK (347 ficheros).
- SPA: `tsc --noEmit` + **148** tests OK.
- Web de auth: `tsc --noEmit` + build OK (sus tests están bloqueados por una instalación
  rota de `@testing-library/jest-dom` en `node_modules`; no afecta al build).
- `check-versions` → 5.5.0 en los 5 destinos.

## Subida con mantenimiento

Opción recomendada (activa mantenimiento, despliega y lo deja activo):

```powershell
pwsh script/deploy_with_maintenance.ps1
```

Equivale a:

```powershell
pwsh web/scripts/maintenance.ps1 -RemoteOnly -On   # imprime ?preview=<TOKEN>
pwsh script/deploy_all.ps1                          # SPA + 4 backends, sin BBDD
```

No usar `script/deploy.ps1` en esta ventana: ese sube también el vhost nginx y no es
necesario para 5.5.0. No usar `-WithConfig` (no se toca `osap.toml`).

## Verificar con el enlace de preview

Abrir el `https://app.openmusicrepository.com/?preview=<TOKEN>` que imprime el paso de
mantenimiento (deja `osap_preview=1` durante 1 día) y comprobar:

- [ ] Portada, login OIDC y `/explore`.
- [ ] `/composers` (Jinja) y una ficha `/composers/<id>/<slug>`: fieldset Identidad/Biografía,
      Visible en identidad, fechas/nacionalidad en Biografía, botón «Ver»/«Descargar».
- [ ] Ficha de obra `/obras/index-...`: Resumen con todos los datos, Páginas, Evidencia,
      Proveedores.
- [ ] Listado de compositores: iniciales correctas (`AB`, `AD`, `AK`, no «ANUNCIO»).
- [ ] Admin → Usuarios: email verificado junto al correo, columna «Público», nombres largos
      truncados.
- [ ] `/corrections` pide sesión para correcciones; el contacto general sigue abierto.
- [ ] Alta: el onboarding propone el nickname derivado del nombre (`ana_maria`).
- [ ] `/api/v1/system/health` y `verify-auth-m2m.ps1` al final de `deploy_all`.

## Publicar

```powershell
pwsh web/scripts/maintenance.ps1 -RemoteOnly -Off
```

## Rollback

Con el mantenimiento **activo**:

1. Restaurar de `~/backups/<fecha>/` el `dist` de la SPA y los programas afectados
   (`app.tar.gz`, `osap-api.tar.gz`, `osap-auth.tar.gz`).
2. `sudo systemctl restart osap-api osap-auth`.
3. Verificar con preview y desactivar mantenimiento.

No hay migraciones ni cambios de esquema en 5.5.0.
