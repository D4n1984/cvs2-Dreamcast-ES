# Construcción local

Requisitos: Python 3.13, Pillow (`python -m pip install -r requirements.txt`), xdelta3 y las tres pistas de la imagen japonesa original. No se distribuyen archivos del juego.

Descarga los dos parches oficiales v1.2 del proyecto inglés (`.dcp` y `.GDI.xdelta`) en `parches/`. Los scripts comprueban el MD5 de la pista original y los SHA-256 de los parches publicados.

## Preparar los recursos

Para el BIN/CUE Redump usado en este proyecto:

```powershell
python herramientas/preparar_base.py --xdelta C:/ruta/xdelta3.exe
python herramientas/integrar_traducciones.py
python herramientas/construir_recursos.py
```

`preparar_base.py` reconstruye una base inglesa separada en `build/ingles`, extrae los archivos necesarios y valida los parches. El original permanece intacto. Se puede indicar otra pista de datos mediante `--original-track3`.

Los TSV se validan antes de crear los CSV. Los archivos de mensajes superan una prueba de reconstrucción sin cambios, idéntica byte a byte, antes de insertar el español. Se conservan las referencias compartidas y los símbolos, se recalculan los punteros y se comprueban los límites de los buffers.

La fuente española reutiliza dieciséis glifos estrechos de `S20RM04.BIN`. La codificación del juego difiere del UTF-8 de los catálogos; no copies directamente los bytes de los TSV a los BIN.

Las descripciones se alojan en el antiguo bloque japonés de Command List, abandonado por el parche inglés. El constructor comprueba que no queden punteros a ese bloque y que la lista inglesa activa no cambie. No se modifica código de instrucciones para añadir los caracteres.

Bonus Mode conserva sus etiquetas y enlaces HTML. Los caracteres españoles se escriben como entidades numéricas y utilizan la fuente europea ya incluida en el parche inglés.

## Imagen local y parche distribuible

```powershell
python herramientas/montar_imagen.py
python herramientas/empaquetar_dcp.py --xdelta C:/ruta/xdelta3.exe --version v0.1.0-alpha.1
```

La imagen de prueba se crea en `build/es-disc/`. Los sectores modificados regeneran EDC/ECC; se releen los archivos insertados y se comprueba la paridad. Las imágenes locales no se publican.

El DCP se construye sobre el original japonés, conservando las modificaciones del DCP inglés. Los deltas nuevos se decodifican de nuevo y se comparan con los recursos españoles antes de empaquetar. El resultado se guarda en `dist/`.

`montar_imagen.py --proof` crea una imagen de diagnóstico distinta que muestra todos los caracteres españoles en el aviso inicial. No se distribuye esa imagen ni ese mensaje.

## Verificación pendiente

La primera alpha necesita revisión visual y lingüística extensa, pruebas de cuadros con dos hablantes, finales de todos los personajes, Bonus Mode y hardware real. La prueba de glifos confirma el renderer directo; otras rutas de normalización de texto requieren comprobarse en pantalla.

El vídeo del anuncio contiene subtítulos ingleses incrustados y se abordará por separado. Las mejoras de texturas y las apariencias extra no forman parte de esta versión.
