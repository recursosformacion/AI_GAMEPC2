# Mantenimiento y token de revisión

## Activar

```powershell
pwsh web/scripts/maintenance.ps1 -RemoteOnly -On
```

El script imprime una línea como:

```
PROD: MANTENIMIENTO ACTIVO -> https://app.openmusicrepository.com/?preview=<TOKEN>
```

Guarda ese enlace: **es el token de revisión**. Abrirlo en el navegador fija la cookie
`osap_preview=1` durante 1 día, por lo que el equipo puede navegar aunque el público vea el
503. El token también queda en `web/dist/maintenance.token` (local; no se despliega) y
`deploy_with_maintenance.ps1` lo imprime al final.

## Desactivar

```powershell
pwsh web/scripts/maintenance.ps1 -RemoteOnly -Off
```

## Si se pierde el token

```powershell
Get-Content web\dist\maintenance.token
```

No hay que volver a activar el mantenimiento para consultarlo. La cookie de preview caduca
sola en un día; el enlace con `?preview=` se puede volver a abrir mientras el mantenimiento
esté activo.
