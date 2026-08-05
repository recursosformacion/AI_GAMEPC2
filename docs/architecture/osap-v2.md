Decisión 001 - Qué problema resuelve la fusión

Estado: Aprobada

Objetivo

OSAP no pretende catalogar la música.

OSAP necesita entregar al usuario una lista limpia de obras para que pueda trabajar sobre ellas.

La fusión existe únicamente para eliminar duplicados procedentes de distintos proveedores.

Consecuencia

La fusión no busca descubrir relaciones musicológicas complejas.

Solo necesita decidir cuándo dos representaciones corresponden, con suficiente confianza, a la misma obra.

Decisión 002 - Qué se fusiona

No se fusionan archivos.

No se fusionan títulos.

Se fusionan representaciones.

Representación
    proveedor
    título
    compositor
    catálogo
    descarga
    licencia
    ...

El resultado es

Work
    id
    representaciones[]
Decisión 003 - El matcher no interpreta texto

El matcher nunca ejecuta regex.

Nunca limpia títulos.

Nunca interpreta "KV".

Nunca interpreta "Köchel".

Nunca interpreta "No."

Todo eso pertenece al parser y al normalizador.

El matcher recibe únicamente campos normalizados.

Decisión 004 - Reglas antes que IA

Mientras podamos resolver un caso mediante reglas simples y explicables, no introduciremos IA.

La IA será una política adicional cuando las reglas no puedan decidir.

Eso ya sería un muy buen comienzo.

Y ahora te propongo una forma de trabajar que creo que nos hará avanzar mucho más deprisa.

No intentemos escribir la V2.

Intentemos escribir una decisión al día.

Porque ya hemos visto una cosa importante.

Hace tres días hablábamos de fingerprints, embeddings y grafos.

Hoy, después de mirar datos reales, hemos llegado a una conclusión mucho más sencilla:

OSAP solo necesita limpiar la lista de resultados para que el usuario pueda elegir una obra y trabajar con ella.

Eso cambia muchas cosas.

La siguiente decisión que me gustaría cerrar (y que considero la más importante de todas) sería:

¿Qué es una "obra" dentro de OSAP?

No desde el punto de vista musicológico.

Sino desde el punto de vista del programa.

Porque, por ejemplo:

¿El Requiem es una obra?
¿El Lacrymosa es una obra?
¿"Symphony No.40 - IV. Allegro Assai" es una obra?
¿"Ave Verum Corpus SATB" es la misma obra que "Ave Verum Corpus"?

Cuando esa decisión esté clara, la fusión dejará de ser un problema de programación y pasará a ser un problema de aplicar reglas sobre una definición que todos compartimos. Ahí es donde creo que debemos concentrar el siguiente esfuerzo.