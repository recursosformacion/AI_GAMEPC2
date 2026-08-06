# Cliente Web — Diseño (V3.3)

> **Status: draft** (iteración 2 — se congelará antes de la implementación de V3.3).
>
> Parte de V3 (Plataforma). Define la arquitectura del **cliente web** de OSAP. No se
> escribe HTML/React hasta congelar este diseño (V3.3.a).

## Principio rector

> **La web es un adaptador del sistema, igual que la CLI o la API REST. Nunca habla con
> el dominio.**

```
Browser
      │
Frontend
      │
REST API
      │
Application
      │
Domain
```

**Nunca**:

```
Browser
      │
Domain
```

## 1. La web como tercer adaptador

```
                 ┌────────────────────┐
                 │      Dominio       │
                 └─────────┬──────────┘
                           │
                  Application Services
                           │
          ┌────────────────┼────────────────┐
          │                │                │
      CLI / Tests      REST API         Cliente Web
```

La web consume **solo la API REST** (`/api/v1/`). No conoce el dominio ni los
Application Services: toda la lógica la expone la API.

## 2. Objetivo

Diseñar la arquitectura del cliente web **antes** de escribir pantallas. Igual que en el
dominio y en la API, primero se congela la arquitectura; después se implementa.

## 3. ¿Qué se define en V3.3?

No pantallas todavía. Se define:

- **arquitectura SPA**;
- **routing** y **navegación** (consecuencia del routing);
- **layout** y **componentes reutilizables**;
- **cliente REST** (`ApiClient`);
- **gestión de estado** y **estados de interfaz**;
- **tratamiento de errores**;
- **organización de páginas**;
- **design system**;
- **invariantes**.

## 4. Arquitectura SPA

Aplicación de una sola página (`Single Page Application`):

- **Frontend** en el navegador, servido como artefacto estático.
- Consume la **REST API** (`/api/v1/`) como única fuente.
- **Sin renderizado en servidor**: el estado y el routing viven en el cliente.

```
SPA
├── routing
├── layouts
├── pages
├── components
├── api
│   └── ApiClient
├── state
└── design-system
```

## 5. Recursos principales — simetría con REST

La web tendrá **cinco áreas**, que corresponden **exactamente** a los recursos REST:

| Web | REST |
|-----|------|
| Dashboard | `/api/v1/system` |
| Searches | `/api/v1/searches` |
| Jobs | `/api/v1/jobs` |
| Knowledge | `/api/v1/knowledge` |
| Administration | `/api/v1/providers` (y admin) |

Eso mantiene una **simetría enorme** entre REST y Web: cada página es un cliente de un
recurso REST.

## 6. Routing

El **routing** define las rutas de la aplicación:

```
/          → Dashboard
/searches  → Searches
/jobs      → Jobs
/knowledge → Knowledge
/providers → Administration
/system    → System / Dashboard
```

La **navegación es consecuencia del routing**: no hay navegación sin ruta.

## 7. Estructura de navegación

```
Dashboard
├── Searches
├── Jobs
├── Knowledge
│   ├── Observaciones
│   ├── Facts
│   └── Sugerencias
└── Administration
    ├── Providers
    └── (jobs, conocimiento, estadísticas)
```

Navegación por las cinco áreas, anidando los subrecursos donde existan.

## 8. Layout

El **Layout no es un componente cualquiera**: define el armazón de la aplicación y envuelve
el contenido.

```
Layout
├── Header
├── Navigation
├── Breadcrumb
├── Content
└── Footer
```

Los componentes reutilizables viven **dentro del Content**.

## 9. Cliente REST — `ApiClient`

La Web **nunca realiza llamadas HTTP directamente desde las páginas**. Toda comunicación
con la API se realiza **exclusivamente mediante `ApiClient`**, responsable de:

- **serializar DTO**;
- **interpretar el envelope uniforme** (`success`, `request_id`, `data`/`error`);
- **transformar errores HTTP**;
- **encapsular la infraestructura REST**.

Las páginas **nunca conocen** `fetch`, `axios` ni detalles HTTP.

## 10. Componentes reutilizables

Se define un conjunto de componentes base reutilizables:

- `Envelope` — envoltorio de respuesta uniforme (éxito/error).
- `ResultList` — listado de resultados (obras, jobs, proveedores).
- `EvidenceView` — visualización de evidence.
- `EnvelopeError` — error uniforme (código + mensaje + detalles).
- componentes de identidad visual (botones, tarjetas, cabecera).

## 11. Estados de interfaz

Toda SPA acaba teniendo exactamente estos estados, que se fijan como **invariantes**:

- **Loading**
- **Ready**
- **Empty**
- **Error**

Cada listado y cada página implementa estos cuatro estados.

## 12. Gestión de estado

- Estado mínimo y **centralizado** (librería de estado de la SPA).
- Cada área de navegación maneja su propia sección de estado, alineada con su recurso
  REST.
- El estado **no duplica** el dominio: es el reflejo de lo que devuelve la API.

## 13. Tratamiento de errores

- Se respeta el **envelope de error** (`code`, `message`, `details`).
- Errores uniformes por componente reutilizable (`EnvelopeError`).
- Estados de carga / vacío / error en cada listado (ver §11).

## 14. Organización de páginas

Cada página corresponde a un recurso REST y se compone de componentes reutilizables. No
hay lógica de dominio en la página: solo petición → estado → render.

## 15. Design System

No hablamos de "estilos" sueltos: hablamos de un **Design System único y centralizado**.

```
Design System
├── Design Tokens
├── Typography
├── Spacing
├── Colors
├── Icons
└── Components
```

> **El framework CSS utilizado durante la implementación constituye un detalle de
> infraestructura y no forma parte del contrato arquitectónico.**

Eso mantiene la misma filosofía que el resto de OSAP: el contrato es estable; el framework
es sustituible.

## 16. Qué NO hace el cliente web

- No habla con el dominio.
- No contiene lógica de negocio (no canoniza, no matchea, no rankea, no fusiona).
- No duplica reglas de la API.
- Solo **consume** la API y **presenta** el resultado.

## 17. Invariantes

- La Web **nunca accede al dominio**.
- **Toda comunicación pasa por la API REST.**
- **Ninguna regla de negocio se implementa en el cliente.**
- El estado del cliente representa **exclusivamente** información recibida desde la API.
- **Toda página corresponde a un recurso REST público.**
- **Todo acceso HTTP pasa por `ApiClient`.**
- El **Design System es único** para toda la aplicación.
- Toda interfaz implementa los cuatro estados: **Loading, Ready, Empty, Error**.

## 18. ADR

Se congelará un ADR (V3.3) con un principio más fuerte:

> **El cliente web constituye un adaptador de presentación. Toda lógica funcional reside
> en el dominio y se expone exclusivamente mediante la API REST. El cliente web
> únicamente gestiona navegación, estado de interfaz y representación visual.**

Ese principio probablemente siga siendo válido en V4 y V5.

## Stack tecnológico (V3.3, congelado)

La arquitectura definida en este documento (ApiClient, Routing, Layout, Components,
State y Design System) es **independiente del framework**. Se congela el stack oficial
para evitar decisiones dispersas durante el desarrollo:

- **React 19**
- **TypeScript 5.x**
- **Vite**
- **React Router**
- **Zustand** (estado global ligero)
- **Tailwind CSS** (framework CSS; detalle de infraestructura)

> **Nota (decisión)**: se **descarta TanStack Query** para la obtención de datos, porque
> movería el HTTP fuera de `ApiClient`. Para mantener el invariante **"toda comunicación
> pasa por `ApiClient`"**, la obtención de datos se realiza en los **stores de estado**
> (Zustand) llamando a `ApiClient`. TanStack Query podría incorporarse en el futuro solo
> si respeta ese invariante.

Si en una futura versión React fuese sustituido por otra tecnología, la organización
arquitectónica (ApiClient, Routing, Layout, Components, State, Design System) deberá
mantenerse.

---

## Criterios de aceptación (V3.3)

- **contratos congelados** antes de implementar;
- arquitectura **SPA** definida (routing, layouts, pages, components, `api`, state,
  design-system);
- **cinco áreas** de navegación simétricas con REST;
- **todo acceso HTTP pasa por `ApiClient`** (las páginas no conocen `fetch`/`axios`);
- gestión de estado centralizada y mínima;
- los **cuatro estados** de interfaz (Loading/Ready/Empty/Error) fijados;
- **Design System único** y framework CSS como detalle de infraestructura;
- la web **no habla con el dominio**;
- **sin modificar** la API V3.1 ni el dominio V2.

---

## Plan de entrega

1. **V3.3.a — Diseño del cliente web** (este documento): arquitectura SPA, routing,
   navegación, layout, ApiClient, componentes, estados, estado, errores, páginas,
   design system e invariantes.
2. **ADR** (V3.3).
3. **Implementación** de la web como tercer adaptador.
4. **Tests** de la comunicación con la API (a través de `ApiClient`).
