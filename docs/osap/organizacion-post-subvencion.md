# Organización e ingeniería — backlog post-subvención

**Estado:** PENDIENTE DE FINANCIACIÓN. No ejecutar ahora. El tiempo disponible se dedica a
mantener y mejorar servicios.

**Origen:** incidente del 2026-10-24 en la ficha pública de obra: un id de storage
(`121355`) se trató como id de índice (`456780`), el SSR seguía sirviendo un bundle antiguo
y las acciones de representación (Ver/Descargar/OMR) estaban duplicadas en tres vistas.
El arreglo fue pequeño; el diagnóstico y la verificación costaron más de 45 minutos.

**Objetivo:** reducir el tiempo de corrección y la tasa de regresiones, y que “desplegado”
signifique lo mismo en desarrollo y en producción.

## Cuándo se activa

- Cuando se conceda la subvención o exista financiación equivalente para dedicar una o dos
  semanas de ingeniería.
- Antes de empezar: crear las tareas, asignar responsable y fijar fecha de revisión.
- No mezclar esta acción con una entrega funcional grande.

## Orden de ejecución

### F1. Un único camino de build, arranque y verificación

- Un comando de desarrollo que haga, en orden: parar servicios, compilar SSR, compilar SPA,
  arrancar, esperar healthchecks y ejecutar el smoke test.
- `script/restart-dev.ps1` debe usar ese camino por defecto; `-Build` no puede dejar el SSR
  con un bundle anterior.
- El deploy debe usar el mismo build que se verifica; nada de compilar a mano en el servidor.

**Estado parcial:** ya existen `script/build-web.ps1` y `script/smoke-web.ps1`, y
`restart-dev.ps1 -Build` compila SSR + SPA. Falta integrarlo en el flujo habitual y en el
deploy.

**Criterio de aceptación:** después de un cambio de frontend, un único comando deja el
entorno coherente y el smoke pasa sin pasos manuales.

### F2. Definición de hecho para cambios de UI

Un cambio de ficha, compositor o representación no se cierra hasta comprobar:

- La API pública devuelve el registro esperado.
- El SSR renderiza el contenido (no solo la SPA).
- El bundle servido es el nuevo.
- Las acciones Visor/Descargar/Abrir funcionan según el proveedor.
- El smoke test de regresión pasa.

**Estado parcial:** `smoke-web.ps1` cubre `/obras/121355` y una representación OMR.

**Criterio de aceptación:** checklist obligatoria en la descripción de la tarea o del PR.

### F3. Contrato compartido de obras y representaciones

- Un único módulo para ids canónicos (`index-*`, numéricos, storage) y para las reglas de
  representación (visor, descarga, enlace externo, excepción OMR).
- Las vistas de obra, el desplegable del compositor y la página de representación consumen
  ese contrato; no pueden reimplementar las reglas.
- El backend mantiene la resolución de ids legados y devuelve siempre el id canónico.

**Estado parcial:** `web/src/lib/representations.ts`, `RepresentationActions.tsx` y la
resolución de ids en `IndexCatalogProvider` ya existen.

**Criterio de aceptación:** no queda lógica duplicada de acciones; un test unitario cubre las
reglas y un smoke cubre las rutas reales.

### F4. CI mínima y obligatoria

- Backend: `ruff`, `mypy`, `pytest` (con base de datos de test aislada y reproducible).
- Frontend: `tsc --noEmit`, `vitest run`, build SSR + SPA.
- Smoke contra un entorno levantado, no solo tests unitarios.
- Un fallo de cualquiera de estos pasos bloquea la entrega.

**Criterio de aceptación:** pipeline verde obligatorio antes de desplegar; los fallos de
entorno de test dejan de confundirse con regresiones.

### F5. Trazabilidad de versión y despliegue

- Health y HTML exponen el hash/commit del build y la versión desplegada.
- El deploy es atómico y tiene rollback documentado.
- Un healthcheck distingue API, SSR y frontend; una página con bundle viejo se detecta sin
  abrir el navegador.

**Criterio de aceptación:** “¿qué está sirviendo producción?” se responde con una petición.

### F6. Disciplina de trabajo y aprendizaje de incidentes

- Límite de una iniciativa activa; las mejoras nuevas esperan.
- Postmortem breve por incidente: síntoma, impacto, causa, detección, prevención y tiempo.
- Revisión periódica de regresiones y tiempo medio de corrección.
- Versionado A.B.C. y commits coherentes; no acumular cambios sin cerrar.

**Criterio de aceptación:** cada incidente repetido tiene una prueba o automatización que lo
habría detectado.

## Esfuerzo orientativo

| Bloque | Esfuerzo |
|---|---|
| F1. Build/arranque único | 1–2 días |
| F2. Definición de hecho y smoke | 1 día |
| F3. Contrato compartido | 2–3 días |
| F4. CI mínima | 2 días |
| F5. Trazabilidad y rollback | 1 día |
| F6. Disciplina y postmortems | Continuo |

Total orientativo: **7–10 días de ingeniería**, más revisión y pruebas en un entorno real.

## Métricas de éxito

- Tiempo de corrección de un fallo de ficha: **menos de 15 minutos** desde la reproducción.
- Cero despliegues con SSR y SPA de builds distintos.
- Cero regresiones del mismo tipo sin un test que las cubra.
- CI verde como condición de entrega, no como recomendación.

## Fuera de alcance

- Nuevas funcionalidades de producto.
- Reescrituras grandes de arquitectura.
- La app de vídeos y el pipeline de IA, salvo que compartan el mismo build/CI.
