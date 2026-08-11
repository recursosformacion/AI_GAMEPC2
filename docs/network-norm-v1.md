# OSAP — Norma de red entre aplicaciones (v1)

**Estado:** NORMA (aplicable a todas las aplicaciones OSAP). No es un contrato de endpoints,
sino la regla de **transporte** para todo diálogo entre aplicaciones.

---

# 1. Norma

> **Todo diálogo entre aplicaciones OSAP se realiza a través de Apache (proxy inverso).**
> Las aplicaciones pueden residir en equipos distintos; nunca se asume que otra aplicación
> esté en el mismo host ni que se pueda llamar directamente por origen.

## Consecuencias

- **Navegador → aplicación**: el Web solo habla con su propio origen (`osap-app`). Cualquier
  llamada a otra aplicación (osap-api, osap-auth, …) va por **Apache** de `osap-app`, que
  proxya la ruta al servicio destino. **Nunca** CORS directo a otro host/puerto.
- **Aplicación → aplicación** (p. ej. osap-api → osap-storage): la llamada sale del servicio a
  su **Apache local**, que proxya a la máquina destino. No se llaman hosts/puertos internos
  directamente desde el código de la aplicación.
- **Origen del Web**: los `fetch` del frontend usan rutas **relativas** (mismo origen) que
  Apache enruta. No se usan URLs absolutas a otros servicios.

## Por qué

- Los servicios pueden estar en **equipos distintos** → no hay garantía de `localhost` ni de
  puerto común.
- **Un solo punto de entrada** por aplicación (Apache) que centraliza proxy, TLS, cabeceras y
  aislamiento.
- Evita **CORS** y la exposición de puertos internos.

---

# 2. Aplicación (referencia)

## osap-app (Web)

Apache de `osap-app` proxya:
- `/api/*` → osap-api (8001);
- `/auth/*` → osap-auth (8200);
- (futuros) rutas a otros servicios.

El frontend llama **siempre** con rutas relativas (`/api/...`, `/auth/...`). Nunca a un
host/puerto absoluto.

## osap-api

- Expone su API en un puerto interno; **Apache** de su máquina proxya `/api/*` → el puerto.
- Para hablar con osap-storage, debe ir por el Apache de su máquina (o el de storage) a la URL
  pública/configurada, no por IP/puerto interno en el código.

## osap-auth

- Igual: solo se alcanza vía Apache (proxy `/auth`). No se expone el puerto interno al Web.

---

# 3. Estado actual y alineación pendiente

| Diálogo | Hoy | Conforme a la norma |
|---|---|---|
| Web → osap-api | `/api` vía Apache de osap-app | ✅ |
| Web → osap-auth | `/auth` vía Apache de osap-app | ✅ |
| osap-api → osap-storage | directo vía `osap.omr_base_url` | ⚠️ alinear: ir por Apache |
| Web → otros servicios | — | n/a |

> La llamada osap-api → osap-storage debe ajustarse para salir por Apache (proxy) cuando se
> desarrolle el diálogo, cumpliendo la norma.

---

# 4. Reglas operativas

- No commitear URLs absolutas a otros hosts en el frontend.
- No abrir puertos internos al navegador.
- Configurar los proxies en el Apache de cada aplicación.
- Documentar en cada app su mapa de rutas proxiedas.

---

*Norma de red OSAP v1 (2026-08) — aplicable a todas las aplicaciones.*
