// Página "Cómo funciona OSAP" — guía sencilla para usuarios.
// (Contenido en español; traducción i18n pendiente.)

export function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Cómo funciona OSAP</h1>
      <p className="text-sm text-osap-muted">
        Bienvenido a OSAP, el catálogo musical abierto que reúne obras, compositores y
        partituras procedentes de varias fuentes (por ejemplo IMSLP, MuseScore, MusicBrainz,
        Mutopia u OpenScore) en una sola página.
      </p>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">1. Qué es OSAP y cómo funciona</h2>
        <p className="text-sm">
          OSAP funciona como un <strong>buscador e índice unificado de música</strong>. En lugar
          de ser un almacén cerrado, OSAP conecta e indexa los fondos de varias plataformas en
          una única interfaz.
        </p>
        <h3 className="mb-1 mt-3 text-sm font-semibold">Qué hace OSAP por ti</h3>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            <strong>Indexa y agrupa:</strong> encuentra obras equivalentes entre distintas
            fuentes para que las veas en un solo lugar.
          </li>
          <li>
            <strong>Organiza el catálogo:</strong> relaciona obras con compositores, añade
            valoraciones de la comunidad y clasifica los formatos disponibles.
          </li>
          <li>
            <strong>Te conecta con el origen:</strong> te da accesos directos a los sitios donde
            vive cada partitura.
          </li>
        </ul>
        <h3 className="mb-1 mt-3 text-sm font-semibold">Qué hace cada proveedor externo</h3>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            <strong>Aloja los archivos originales:</strong> cada fuente (IMSLP, MuseScore, etc.)
            guarda los archivos (PDF, MusicXML, MIDI…).
          </li>
          <li>
            <strong>Gestiona las descargas y licencias:</strong> la descarga final y las
            condiciones legales se deciden en la web del proveedor.
          </li>
        </ul>
        <p className="mt-3 text-sm">OSAP no reemplaza a los proveedores: te lleva hasta ellos.</p>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">2. Primeros pasos</h2>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>Busca una obra o compositor.</li>
          <li>Ábrela para ver el detalle.</li>
          <li>Consulta las representaciones (versiones y formatos).</li>
          <li>Vota (regístrate y verifica tu email).</li>
        </ol>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">3. Glosario de conceptos clave</h2>
        <ul className="space-y-2 text-sm">
          <li>
            <strong>Obra:</strong> la composición musical (por ejemplo, el Ave Verum Corpus de
            Mozart). OSAP le da una identidad única y la vincula con su autor.
          </li>
          <li>
            <strong>Compositor:</strong> el autor o autora de las obras. Su perfil muestra sus
            obras y una valoración media.
          </li>
          <li>
            <strong>Fuente / proveedor:</strong> el repositorio externo de donde procede la obra
            o el archivo.
          </li>
          <li>
            <strong>Representación:</strong> cada versión o formato de una misma obra (una
            partitura en PDF, un archivo MusicXML, un archivo MIDI…).
          </li>
          <li>
            <strong>Voto:</strong> la puntuación individual (de 1 a 5) que da un usuario
            registrado a una obra.
          </li>
          <li>
            <strong>Valoración:</strong> la nota media que calcula OSAP con todos los votos de la
            comunidad.
          </li>
          <li>
            <strong>Obra privada de usuario (más adelante):</strong> obras que guarda el usuario
            y que no son visibles públicamente hasta que decida.
          </li>
        </ul>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">4. Guía de uso: Descubrir, Entender y Actuar</h2>
        <p className="text-sm">Cada pantalla de OSAP se organiza en tres ideas:</p>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>
            <strong>Descubrir</strong> — identificar qué estás viendo.
          </li>
          <li>
            <strong>Entender</strong> — comprender los datos.
          </li>
          <li>
            <strong>Actuar</strong> — explorar, valorar y acceder.
          </li>
        </ol>
        <h3 className="mb-1 mt-3 text-sm font-semibold">Ejemplo en una obra</h3>
        <ul className="space-y-2 text-sm">
          <li>
            <strong>Descubrir (¿qué estás viendo?):</strong> la ficha unificada de una
            composición, asociada a su compositor y con sus ediciones agrupadas.
          </li>
          <li>
            <strong>Entender (¿qué significa cada dato?):</strong> ★ 4,32 (37 votos) es la
            valoración media de la comunidad. Si una obra no tiene valoración, se muestra
            "Sin valorar" (no aparece un 0). Varias fuentes: la misma obra está en varios
            repositorios y formatos.
          </li>
          <li>
            <strong>Actuar (¿qué puedes hacer?):</strong> consultar representaciones, ir a la
            fuente para descargar la partitura, y valorar (requiere iniciar sesión con un email
            verificado).
          </li>
        </ul>
      </section>

      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-lg font-semibold">5. Preguntas frecuentes</h2>
        <div className="space-y-3 text-sm">
          <div>
            <p className="font-semibold">¿Por qué OSAP no me descarga directamente la partitura?</p>
            <p>OSAP es un agregador que respeta las fuentes. Te lleva al sitio del proveedor para
            que obtengas la versión más actualizada y respetes las condiciones de distribución.</p>
          </div>
          <div>
            <p className="font-semibold">
              He votado una obra, pero la nota media no ha cambiado de inmediato. ¿Es un error?
            </p>
            <p>No. Las valoraciones se recalculan periódicamente en segundo plano, no al instante
            con cada voto. Tu voto quedó registrado correctamente.</p>
          </div>
          <div>
            <p className="font-semibold">¿Puedo guardar mis propias obras o borradores?</p>
            <p>Próximamente podrás gestionar obras privadas en tu perfil y decidir cuándo hacerlas
            públicas.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
