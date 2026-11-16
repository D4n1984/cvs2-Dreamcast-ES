# CvS2 Dreamcast ES v0.1.0-alpha.1

Primera versión preliminar de la traducción parcial al español, basada en el parche inglés v1.2 de Derek Pascarella y su equipo.

Se incluyen los diálogos de victoria, finales y narración, descripciones de modos y opciones, entrevistas y descripciones de Bonus Mode. Se conservan en inglés los movimientos, comandos, títulos, nombres propios y créditos originales.

## Instalación

1. Usa la imagen japonesa original sin modificar. MD5 de la pista 3: `FF8E199324FC11D4F638E5C99315CDBB`.
2. Abre el GDI o CUE con Universal Dreamcast Patcher 1.3 o posterior: https://github.com/DerekPascarella/UniversalDreamcastPatcher
3. Selecciona el archivo DCP español y aplica el parche.

El DCP ya incorpora los cambios de la traducción inglesa. No apliques primero el parche inglés ni uses su imagen como origen. Este paquete no contiene el juego ni imágenes de disco.

## Comprobaciones realizadas

- Catálogos completos: 8.496 entradas de victoria, 498 de finales, 26 líneas de descripciones y 456 segmentos de Bonus Mode.
- Reconstrucción sin cambios de los tres archivos de mensajes, idéntica byte a byte, antes de insertar el español.
- Punteros reconstruidos, referencias compartidas y límites de buffers comprobados.
- Lista de comandos inglesa activa preservada.
- Arranque y representación de todos los glifos españoles probados en Flycast.
- Imagen local con lectura de los recursos insertados y paridad EDC/ECC comprobadas.
- Deltas nuevos decodificados y comparados con los recursos españoles; integridad ZIP del DCP comprobada.

## Límites de esta alpha

El borrador y la revisión dirigida cuentan con asistencia de IA. Falta una revisión lingüística y visual extensa de los combates, finales y Bonus Mode, y no se ha probado en Dreamcast real. Las líneas se han ajustado inicialmente a un máximo de 50 caracteres visibles, pero el centrado y las distintas rutas de texto necesitan revisión en pantalla.

Los subtítulos del anuncio de Bonus Mode siguen en inglés. Los avisos de sistema, controles, títulos y gráficos con texto quedan fuera de esta primera versión. No incluye mejoras de texturas ni personajes nuevos.

Para comunicar un error, indica el ID del catálogo cuando lo conozcas, personaje, rival y dónde aparece. Las siguientes versiones actualizarán esta traducción antes de comenzar las mejoras gráficas.

## Créditos y fuentes

Parche inglés: Derek Pascarella (ateam), Duralumin, Jesuszilla, Tortita, Justin Gibbins, rob2d, Silentscope y hasnopants. Entrevistas inglesas: Benjamin Roodberg. Se conservan sus créditos dentro del juego.

Original: https://github.com/DerekPascarella/Capcomvs.SNK2-EnglishPatchDreamcast

Proyecto español e incidencias: https://github.com/D4n1984/cvs2-Dreamcast-ES
