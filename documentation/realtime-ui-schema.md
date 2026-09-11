# Anotaciones de edición y validación para GTFS Realtime

Este documento describe `serializers/realtime/realtime.ui.yaml`: el archivo que
registra, para cada campo de GTFS Realtime, **de dónde sale el valor** y —
cuando lo escribe una persona — **con qué componente se edita y qué reglas de
validación se le aplican**.

Es el gemelo de `schedule.ui.yaml`. Todo lo que ya explica
[`ui-schema.md`](./ui-schema.md) sigue valiendo aquí: por qué las anotaciones
viven en un archivo aparte de la especificación, por qué las etiquetas no se
reutilizan de la ontología, cómo se editan desde el navegador y dónde se valida
qué. **Este documento solo cubre lo que es distinto**, que son tres cosas.

---

## 1. Un feed de Realtime se produce, no se escribe

La diferencia de fondo. Un feed de GTFS Schedule lo teclea alguien: cada campo
de `stops.txt` tiene, tarde o temprano, un formulario detrás. Un feed de GTFS
Realtime lo produce una máquina — el AVL, el motor de predicciones, el
constructor del feed — y casi ningún campo tiene formulario ni debería tenerlo.

La excepción son las **alertas de servicio**. Ésas sí las redacta una persona,
y son la única parte del feed que de verdad necesita una pantalla de edición.

Si las anotaciones no distinguieran los dos casos, el archivo se leería para
siempre como incompleto: `VehiclePosition.odometer` nunca va a tener componente
de edición, y eso no es una tarea pendiente sino una respuesta. Por eso la
llave obligatoria de cada anotación es `origin`:

| `origin` | Significado | Ejemplo |
|---|---|---|
| `operator` | Lo escribe una persona en un editor | `Alert.header_text` |
| `system` | Lo produce una máquina | `VehiclePosition.position` |
| `derived` | Se calcula del feed estático más observación | un tiempo de viaje medido |
| `constant` | Fijo para todo el feed, se configura una vez | `FeedHeader.gtfs_realtime_version` |

`component` es obligatorio **solo** cuando `origin` es `operator`. El esquema lo
expresa con un `if`/`then`, y el formulario del navegador lo aplica mientras se
escribe porque lo lee del esquema, no porque esté programado aparte.

El reporte de cobertura imprime las dos cifras: cuántos campos están anotados y
cómo se reparten por origen. La segunda es la que dice si falta trabajo de
diseño de pantallas o solo de inventario.

## 2. La llave es la definición del campo, no el camino hasta él

GTFS Realtime no es un conjunto de tablas: es un grafo de mensajes protobuf. Un
mismo campo se alcanza por varios caminos.

`TripUpdate.stop_time_update.departure.time` y
`TripUpdate.stop_time_update.arrival.time` terminan los dos en el campo `time`
del mensaje `StopTimeEvent`. Son **el mismo campo** visto desde dos lugares.

Las dos preguntas son distintas y por eso las llaves también:

| Archivo | Llave | Pregunta que responde |
|---|---|---|
| `realtime.ui.yaml` | `StopTimeEvent.time` | ¿Qué significa este campo y cómo se valida? |
| `composites.yaml` | `TripUpdate.stop_time_update.departure.time` | ¿Cuál de los dos muestra esta pantalla? |

Una pantalla necesita saber si enseña la llegada o la salida; el campo en sí no
cambia de significado según quién lo lea. Así que `StopTimeEvent.time` se anota
una vez y los dos caminos heredan esa anotación. El módulo
`converters/realtime/rt_spec.py` es el que traduce entre ambas formas.

**Los enums no se anotan.** No tienen campos propios, y sus valores se muestran
sobre el campo que los selecciona. Hay una trampa ahí: existen **dos** enums
llamados `ScheduleRelationship`, uno para paradas y otro para viajes, con
valores distintos. Buscarlos por nombre devuelve en silencio el que el parser
haya visto de último. `rt_spec` los resuelve por posición — la especificación
documenta cada tipo anidado justo después del mensaje que lo usa — y muestra en
pantalla el nombre y la descripción del enum para que se vea cuál es cuál.

## 3. Dos comprobaciones que cruzan archivos

### `references`: la junta con el feed estático

Los identificadores de Realtime se resuelven contra el GTFS estático. Un
`route_id` en un `EntitySelector` no es texto libre: tiene que existir en
`routes.txt`, o la alerta no aparece en ninguna pantalla.

```yaml
  EntitySelector.route_id:
    origin: operator
    component: foreign_key_select
    references: routes.route_id
```

`converters/realtime/ui_coverage.py` resuelve cada `references` contra
`schedule.yaml` y falla si apunta a un campo que no existe. Es la única
comprobación que detecta ese error antes de que alguien vea una pantalla vacía.

### `bounding_box`: las regiones no se redeclaran

`realtime.ui.yaml` **no** tiene bloque `regions`. La caja de Costa Rica es una
propiedad del territorio, no del feed, así que se lee de `schedule.ui.yaml` y el
script de cobertura comprueba que el nombre de región exista allí. Tenerla dos
veces sería tenerla mal una de las dos.

## 4. Reglas de validación propias de Realtime

Además de las reglas compartidas (`required`, `range`, `pattern`,
`enum_from_spec`, `max_length`, `bounding_box`…), hay cuatro que solo existen
aquí:

| Regla | Para qué |
|---|---|
| `posix_time` | El valor está en segundos POSIX, no en milisegundos |
| `not_stale` | Segundos de antigüedad máxima antes de dejar de confiar en el valor |
| `unique_in_feed` | No se repite dentro de un mensaje (el lado estático dice `unique_in_file`) |
| `after` | El extremo de un rango temporal no precede al otro |

`posix_time` merece su propio renglón: un timestamp en milisegundos es
sintácticamente válido, pasa cualquier validador de tipos, y coloca todas las
predicciones unos cincuenta mil años en el futuro. Es el error más común de un
productor de Realtime.

`not_stale` es sobre la **frescura del feed**, no sobre cómo degrada una
pantalla. La política de degradación de una pantalla —qué mostrar cuando el
dato en vivo falta— vive en `composites.yaml`, en la cadena `sources`. Son dos
decisiones distintas y están en dos archivos distintos a propósito.

## 5. El explorador

```bash
# Cobertura y comprobaciones; falla con referencias colgantes
uv run converters/realtime/ui_coverage.py
uv run converters/realtime/ui_coverage.py --json

# Construir la página en web/dist/realtime.html
uv run converters/realtime/realtime2site.py

# Construir las tres páginas, servirlas y editarlas desde el navegador
uv run converters/schedule/serve_site.py
```

Es **la misma página** que el explorador de Schedule. Comparten plantilla,
estilos, modelo de borrador en dos capas, formulario generado desde el esquema
y escritura de vuelta al archivo; están en `converters/site/`. Lo único propio
de cada feed es cómo se convierte su especificación en la lista de campos, y la
función `suggest()` que propone una primera anotación — porque adivinar un
componente significa leer un vocabulario de tipos, y el de protobuf no se
parece en nada al de GTFS Schedule.

Un grupo es un archivo `.txt` en un lado y un mensaje protobuf en el otro. Un
campo de tipo mensaje enlaza al mensaje que abre, igual que una llave foránea
enlaza al archivo al que apunta.

La escritura va a `PUT /api/realtime-annotations`. Es el mismo código que
escribe `schedule.ui.yaml`: **la ruta decide qué archivo se escribe y contra qué
esquema se valida, nunca el contenido de la petición**.

## 6. Alcance actual

El barrido va por la parte que se edita a mano y por los campos que alguna
pantalla ya muestra:

| Mensaje | Estado |
|---|---|
| `Alert`, `TimeRange`, `EntitySelector`, `Translation` | La superficie de redacción de alertas, anotada |
| `TripUpdate`, `StopTimeEvent`, `StopTimeUpdate`, `TripDescriptor`, `TripProperties` | Solo los campos que `composites.yaml` muestra |
| `VehiclePosition`, `Position`, `FeedHeader`, `FeedEntity` | Solo los campos que `composites.yaml` muestra |
| `Shape`, `Stop`, `TripModifications` y sus mensajes | Sin anotar todavía |

Los 21 campos de Realtime que alguna pantalla muestra están anotados; el resto
del barrido es inventario, y la página lo marca como «aún no mapeado».
