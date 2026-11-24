# Checklist de verificación funcional de OSAP

**Estado:** preparado; ejecución con cuenta de prueba pendiente.  
**Entorno:** producción, https://app.openmusicrepository.com/.  
**Regla:** distinguir pruebas de lectura de operaciones que crean o modifican datos.

## 1. Web pública — solo lectura

- [ ] Inicio y navegación principal.
- [ ] Listado de compositores y paginación.
- [ ] Búsqueda por título, compositor y catálogo.
- [ ] Filtros y ordenación; conservar estado al navegar y volver.
- [ ] Ficha de compositor y enlaces a sus obras.
- [ ] Ficha de obra: título, autoría, catálogo, fuentes y representaciones.
- [ ] Ficha de representación: formato, proveedor, disponibilidad, abrir y descargar.
- [ ] Clasificaciones: épocas, géneros, instrumentos, ensembles y catálogos.
- [ ] Fuentes externas: IMSLP y CPDL; repositorio propio OMR y Mutopia.
- [ ] Sitemaps, canonical, hreflang, redirecciones y enlaces antiguos.
- [ ] Idiomas: comprobar que el idioma de la interfaz coincide con el contenido traducido.

## 2. Cuenta — lectura primero

- [ ] Registro y respuesta del formulario.
- [ ] Verificación de correo y estado de cuenta.
- [ ] Login OIDC y flujo alternativo si se ofrece.
- [ ] Logout y caducidad de sesión.
- [ ] Nombre visible y edición de perfil, si está habilitada.
- [ ] Preferencias de idioma y temas de noticias.
- [ ] Acceso a Mi Actividad.
- [ ] Datos de descargas, cuotas, aportaciones y biblioteca personal.
- [ ] Confirmar que el usuario solo ve sus propios datos y que el backend deriva su identidad del token.

## 3. Operaciones personales — requieren autorización de escritura

No ejecutar estos pasos en producción hasta que el usuario autorice expresamente la creación de datos de prueba y se acuerde cómo retirarlos:

- [ ] Añadir un elemento a la biblioteca y retirarlo.
- [ ] Crear una aportación de prueba, adjuntar un archivo no protegido y enviarla.
- [ ] Comprobar estados, devolución y retirada de la aportación.
- [ ] Probar una corrección de metadatos solo si existe flujo de propuesta/revisión.
- [ ] Probar límites de descarga con un fichero pequeño y permitido.
- [ ] Verificar que los eventos aparecen en Mi Actividad y no se duplican.

No realizar pagos, compras, envíos de correo ni operaciones irreversibles.

## 4. Los Amigos — permisos separados

- [ ] Páginas públicas de grupos, artículos y actuaciones.
- [ ] Miembros y datos públicos; no exponer correo ni datos privados.
- [ ] Mi Actividad de Los Amigos y permisos efectivos.
- [ ] Solicitud de incorporación a un grupo.
- [ ] Autorizaciones de escritura para blog y eventos.
- [ ] Borradores, revisión, publicación directa autorizada y retirada.
- [ ] Confirmar que un cargo organizativo no concede permisos globales por sí solo.

Las operaciones administrativas requieren un usuario con autorización adecuada; no elevar una cuenta de prueba a administrador global para facilitar la auditoría.

## 5. Integraciones y degradación

- [ ] API health y tiempos de respuesta.
- [ ] Auth: tokens de usuario y scopes.
- [ ] Storage: disponibilidad, permisos y descarga.
- [ ] Support: rutas administrativas M2M y 401/403/503.
- [ ] Noticias: feed disponible, filtros por idioma/temas y degradación si el servicio no responde.
- [ ] Publicidad: composición, fallback SponsorSlot, impresión y click-through.
- [ ] Confirmar que ningún token de servicio aparece en HTML, JavaScript o respuestas públicas.

## 6. Registro de evidencia

Para cada caso registrar:

- fecha/hora local;
- URL y usuario de prueba (sin correo ni datos personales en el informe);
- pasos ejecutados;
- resultado esperado y resultado real;
- código HTTP y mensaje visible cuando corresponda;
- captura sin datos sensibles;
- si hubo escritura, ID del dato de prueba y método de retirada.

No marcar como verificada una función solo porque la página cargue; hay que ejecutar la acción y comprobar el resultado del backend.
