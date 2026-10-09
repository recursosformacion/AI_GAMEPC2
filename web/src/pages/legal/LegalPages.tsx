// Documentos legales de OSAP (Aviso legal, Política de privacidad, Política de cookies).
// Los datos no verificados se marcan como [PENDIENTE DE CONFIRMAR] y NO se inventan.

import type { ReactNode } from "react";

export const LEGAL_UPDATED = "2026-10-09";

function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl space-y-4 text-sm leading-relaxed">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-xs text-osap-muted">Última actualización: {LEGAL_UPDATED}</p>
      <div className="space-y-4">{children}</div>
    </article>
  );
}

function Pending({ children }: { children: ReactNode }) {
  return (
    <mark className="rounded bg-amber-100 px-1 text-amber-900 [PENDIENTE DE CONFIRMAR]">
      [PENDIENTE DE CONFIRMAR] {children}
    </mark>
  );
}

export function LegalNoticePage() {
  return (
    <LegalPage title="Aviso legal">
      <section>
        <h2 className="font-semibold">1. Identificación del titular</h2>
        <p>
          Titular: <strong>Miguel Garcia Garcia</strong>. Domicilio: C/ Nou, 35, 08458 Sant Pere de
          Vilamajor, Barcelona, España. Correo de contacto:{" "}
          <a className="text-osap-accent hover:underline" href="mailto:admin@openmusicrepository.com">
            admin@openmusicrepository.com
          </a>
          . NIF: <Pending>(dato fiscal del titular)</Pending>. Actividad: gestión y explotación del
          sitio <strong>OpenMusicRepository (OSAP)</strong>, catálogo musical en línea.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">2. Objeto y finalidad</h2>
        <p>
          OSAP es una plataforma de catalogación y consulta de música y partituras, con búsqueda por
          obra, compositor y catálogo, aportaciones de la comunidad y estadísticas de uso. El acceso
          al sitio atribuye la condición de usuario e implica la aceptación de este aviso legal.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">3. Condiciones de acceso y uso</h2>
        <p>
          El usuario se compromete a un uso lícito, a no dañar el servicio y a no realizar
          extracciones masivas no autorizadas. El titular puede suspender o limitar el acceso por
          motivos técnicos, de seguridad o de mantenimiento.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">4. Propiedad intelectual e industrial</h2>
        <p>
          El código, el diseño, la base de datos y los contenidos propios de OSAP están protegidos
          por la normativa de propiedad intelectual e industrial. Las marcas y signos distintivos
          pertenecen a sus titulares.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">5. Licencias de obras, partituras, grabaciones y metadatos</h2>
        <p>
          <strong>
            No todos los materiales del catálogo son de dominio público ni están bajo una licencia
            universal.
          </strong>{" "}
          Cada obra, edición, grabación, archivo y metadato puede tener su propia situación y
          licencia. La información de origen y licencia se muestra cuando está disponible; su uso
          por el usuario se realiza bajo su responsabilidad y conforme a la licencia aplicable.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">6. Responsabilidad de quienes aportan</h2>
        <p>
          Quien aporta contenido declara que dispone de los derechos o de la base legítima para
          hacerlo y responde de la veracidad de la información. Una aportación catalográfica
          <strong> no equivale a la autoría de la obra ni a la titularidad de sus derechos</strong>.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">7. Cuentas y reconocimientos de colaboradores</h2>
        <p>
          La cuenta es personal y su titular es responsable de su uso. Los reconocimientos
          (colaborador, voz, fundador, etc.) se otorgan por el equipo y no implican cesión de
          derechos ni autorización para publicar datos del usuario.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">8. Enlaces y servicios externos</h2>
        <p>
          El sitio puede enlazar a servicios de terceros (alojamiento, correo, DNS/seguridad y
          analítica). El titular no es responsable del contenido ni de las condiciones de dichos
          servicios externos.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">9. Disponibilidad y limitaciones</h2>
        <p>
          El servicio se presta «tal cual», sin garantía de disponibilidad continua ni de ausencia
          de errores. El titular no será responsable de daños derivados de interrupciones, fallos o
          del uso indebido del sitio, salvo en los supuestos legalmente exigibles.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">10. Comunicaciones, reclamaciones y legislación aplicable</h2>
        <p>
          Para comunicaciones y reclamaciones: admin@openmusicrepository.com. Esta relación se rige
          por la legislación española; serán competentes los juzgados y tribunales que correspondan
          conforme a la normativa aplicable.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">11. Notificación de contenidos que infrinjan derechos</h2>
        <p>
          Si consideras que un contenido infringe derechos, escribe a
          admin@openmusicrepository.com indicando: identificación del contenido, tu identidad y
          legitimación, el derecho supuestamente infringido y la documentación que lo acredite. Se
          atenderá y, en su caso, se retirará el contenido conforme a la normativa aplicable
          (incluido el mecanismo de la LSSI-CE).
        </p>
      </section>
    </LegalPage>
  );
}

export function PrivacyPolicyPage() {
  return (
    <LegalPage title="Política de privacidad">
      <section>
        <h2 className="font-semibold">1. Responsable del tratamiento</h2>
        <p>
          Miguel Garcia Garcia, C/ Nou, 35, 08458 Sant Pere de Vilamajor, Barcelona, España. NIF:{" "}
          <Pending>(dato fiscal del titular)</Pending>. Contacto para privacidad:
          admin@openmusicrepository.com.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">2. Datos del catálogo y datos de cuenta</h2>
        <p>
          Los <strong>datos del catálogo</strong> (obras, compositores, metadatos, fuentes) son
          información pública del repositorio. Los <strong>datos de cuenta</strong> (correo,
          identificadores, nickname, preferencias y registros de aceptación) son datos personales
          tratados como se describe a continuación.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">3. Tratamientos, finalidades y bases jurídicas</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Registro y gestión de la cuenta</strong> (correo, identificador, credenciales):
            gestión del acceso. Base: ejecución de contrato.
          </li>
          <li>
            <strong>Nickname y perfil</strong>: identidad en la plataforma. Base: ejecución de
            contrato; la <strong>publicación del nickname</strong> requiere consentimiento específico
            (ver punto 4).
          </li>
          <li>
            <strong>Aceptación de condiciones y privacidad</strong>: registro versionado de la
            aceptación. Base: cumplimiento legal / interés legítimo en la trazabilidad.
          </li>
          <li>
            <strong>Contribuciones y operaciones catalográficas</strong>: trazabilidad de aportaciones
            y correcciones. Base: ejecución de contrato / interés legítimo.
          </li>
          <li>
            <strong>Búsquedas, descargas y estadísticas de uso</strong>: mejora del servicio. Base:
            consentimiento (analítica) o interés legítimo (métricas agregadas internas).
          </li>
          <li>
            <strong>Seguridad y prevención de abusos</strong> y <strong>comunicaciones de servicio</strong>
            (p. ej. verificación de correo): base: interés legítimo y ejecución de contrato.
          </li>
        </ul>
      </section>
      <section>
        <h2 className="font-semibold">4. Regla del nickname: consentimiento específico</h2>
        <p>
          Aceptar las condiciones de uso o la política de privacidad{" "}
          <strong>no autoriza por sí solo a publicar tu nickname</strong>. La autorización para
          mostrarlo públicamente es <strong>específica, independiente y revocable</strong> (casilla
          propia en el perfil). La concesión de un reconocimiento{" "}
          <strong>tampoco equivale</strong> a ese consentimiento.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">5. Destinatarios y proveedores</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li><strong>OVH</strong> — alojamiento.</li>
          <li><strong>Raiola Networks</strong> — servicio de correo electrónico.</li>
          <li><strong>Cloudflare</strong> — DNS y seguridad.</li>
          <li><strong>Google Analytics</strong> (Google) — estadísticas web, únicamente con consentimiento de analítica.</li>
        </ul>
      </section>
      <section>
        <h2 className="font-semibold">6. Transferencias internacionales</h2>
        <p>
          Algunos proveedores pueden tratar datos fuera del EEE (p. ej. Google).
          <Pending>garantías aplicables (SCC/DPF) y proveedores concretos con transferencia</Pending>.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">7. Conservación</h2>
        <p>
          Los datos de cuenta se conservan mientras la cuenta esté activa y, tras la baja, durante
          los plazos legalmente exigibles.{" "}
          <Pending>plazos concretos de conservación por tratamiento</Pending>.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">8. Derechos</h2>
        <p>
          Puedes ejercer acceso, rectificación, supresión, oposición, limitación y portabilidad
          escribiendo a admin@openmusicrepository.com. Puedes reclamar ante la Agencia Española de
          Protección de Datos (www.aepd.es).
        </p>
      </section>
      <section>
        <h2 className="font-semibold">9. Seguridad y modificaciones</h2>
        <p>
          Se aplican medidas técnicas y organizativas razonables. Esta política puede actualizarse;
          la fecha de última actualización figura al inicio.
        </p>
      </section>
    </LegalPage>
  );
}

export function CookiePolicyPage() {
  return (
    <LegalPage title="Política de cookies">
      <section>
        <h2 className="font-semibold">1. Qué son y cómo las usamos</h2>
        <p>
          Las cookies y tecnologías similares (incluido el almacenamiento local del navegador)
          permiten el funcionamiento del sitio y, con tu consentimiento, la medición de uso. La SPA
          de OSAP usa <strong>almacenamiento local</strong> para el token de sesión, el idioma y tus
          preferencias; el consentimiento de cookies se guarda también localmente.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">2. Cookies necesarias</h2>
        <p>
          Imprescindibles para el funcionamiento y la seguridad. No se usan con fines de analítica.
          <Pending>cookies estrictamente necesarias concretas y su proveedor (p. ej. seguridad de Cloudflare)</Pending>.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">3. Preferencias (almacenamiento local)</h2>
        <p>
          Guardamos en el navegador tus preferencias (idioma, filtros y tu decisión de cookies) para
          no volver a preguntar en cada visita.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">4. Analítica (solo con consentimiento)</h2>
        <p>
          Google Analytics 4 (Google). Cookies: <code>_ga</code> y <code>_ga_8QXVPF8VP0</code>,
          finalidad de medición de uso, solo tras aceptar la categoría «analítica». Duración por
          defecto de GA4: <Pending>duraciones configuradas</Pending>.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">5. Terceros</h2>
        <p>
          Los proveedores de seguridad (Cloudflare) o analítica (Google) pueden establecer cookies
          según su configuración.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">6. Consentimiento y retirada</h2>
        <p>
          En la primera visita puedes <strong>Aceptar todas</strong>, <strong>Rechazar las no
          necesarias</strong> o <strong>Configurar preferencias</strong>. Puedes cambiar o retirar tu
          elección en cualquier momento desde el enlace <strong>«Configurar cookies»</strong> del pie
          de página. Si rechazas la analítica, no se carga Google Analytics.
        </p>
      </section>
      <section>
        <h2 className="font-semibold">7. Cambios</h2>
        <p>
          Si cambian las categorías o finalidades, se solicitará de nuevo el consentimiento.
        </p>
      </section>
    </LegalPage>
  );
}
