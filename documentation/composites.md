# Composites de visualización

Este documento describe `serializers/ui/composites.yaml`: el archivo que define
**qué campos de GTFS lee cada pantalla**, en qué orden y qué ocurre cuando
faltan.

El vocabulario está en inglés, igual que el resto del repositorio. La
documentación y las etiquetas de la interfaz están en español, portugués e
inglés.

> **Este archivo no es parte de GTFS.** La especificación no implica ninguna de
> estas pantallas. Son decisiones de producto de SIMOVI, y por eso viven en su
> propio directorio y no dentro de `serializers/schedule/`.

---

## 1. La transpuesta de `schedule.ui.yaml`

El repositorio ya tenía un archivo companion indexado por campo. Este es el
mismo patrón en la dirección contraria:

| Archivo | Pregunta que responde | Forma |
|---|---|---|
| `schedule.ui.yaml` | ¿Cómo se **edita** este campo? | una entrada por campo |
| `composites.yaml` | ¿Qué campos **muestra** esta pantalla? | una entrada, muchos campos |

Ambos indexan el mismo espacio de nombres de campos. De ahí salen tres cosas que
ninguno de los dos tendría por separado:

1. **Índice inverso.** Para cualquier campo, qué pantallas dependen de él. El
   explorador lo muestra como «Se muestra en: RouteBadge».
2. **Prioridad de anotación.** La cobertura de `schedule.ui.yaml` es sobre 218
   campos sin orden. Cruzada con este archivo, se convierte en «14 campos se
   muestran en pantalla y todavía no tienen anotación»: eso sí es una lista de
   trabajo.
3. **Verificación en CI.** Todo campo referenciado tiene que existir en
   `schedule.yaml` o `realtime.yaml`. Un nombre mal escrito, o un campo retirado
   en una revisión futura de la especificación, rompe la build en vez de dejar
   una pantalla en blanco.

## 2. De qué se compone un composite

Un composite se arma con las mismas piezas que un componente de interfaz:

- **`params`** — los identificadores que se le pasan para instanciarlo
  (`routes.route_id`). Son llaves de unión, no decoración. Cada uno está
  respaldado por un componente de edición en `schedule.ui.yaml`, casi siempre
  `id_input`.
- **`props`** — los atributos que dibuja (`route_desc`, un color, un ETA). Cada
  prop es una **cadena de respaldo ordenada**.

Un prop puede nombrar otro composite en lugar de `sources`. Así `RouteStops` se
reutiliza como contenido del globo del mapa dentro de `RouteMap`, en vez de
repetirse.

```yaml
RouteHeader:
  entity: route          # de qué habla una instancia
  cardinality: one       # una, o una lista
  params:
    - name: route_id
      source: schedule:routes.route_id
      required: true
  props:
    - name: title
      required: true
      sources:
        - schedule:routes.route_long_name
        - schedule:routes.route_short_name
```

Cuando `cardinality` es `many`, el esquema exige `key`: el identificador de cada
fila. Una lista sin identidad de fila no se puede actualizar ni diferenciar.

## 3. La cadena de respaldo

Esta es la parte que importa.

Un elemento en pantalla casi nunca viene de un solo campo. `sources` es una
lista **ordenada**: gana la primera fuente que no esté vacía.

```yaml
- name: eta
  required: true
  sources:
    - realtime:TripUpdate.stop_time_update.departure.time
    - realtime:TripUpdate.stop_time_update.arrival.time
    - schedule:stop_times.departure_time
    - schedule:stop_times.arrival_time
  freshness: 60s
  compute: 'Minutes remaining = source time minus FeedHeader.timestamp, not the device clock.'
```

Esa lista **es la política de degradación de tiempo real a horario programado**,
escrita una sola vez. Sin ella, cada pantalla vuelve a inventarla, y termina
inventándola distinto.

`freshness` dice cuánto puede envejecer un valor de tiempo real antes de tratarse
como ausente. `compute` documenta la transformación cuando lo que se dibuja no es
el valor crudo.

### La excepción: `mode: all`

A veces las fuentes de un prop no son alternativas sino **un solo valor**. Una
coordenada son dos campos; un monto son cifra y moneda; una alerta necesita causa
y efecto juntos. Para esos casos:

```yaml
- name: stop_pins
  mode: all
  sources:
    - schedule:stops.stop_lat
    - schedule:stops.stop_lon
```

`mode: all` es lo que impide leer esa lista como una prioridad que no existe. La
página tampoco las numera, justamente para no sugerir un orden. El valor por
defecto es `fallback`.

## 4. Referencias a campos

```
schedule:<archivo>.<campo>          plano, porque GTFS Schedule es plano
realtime:<Mensaje>.<campo>...       un camino recorrido por los mensajes protobuf
derived:<nombre>                    un artefacto que la aplicación construye
```

La referencia de tiempo real se **recorre**, no se busca por nombre plano. Es lo
que mantiene distinguibles `arrival.time` y `departure.time`: las dos terminan en
`StopTimeEvent.time`, y una llave plana no podría decir cuál de las dos quiso
decir la pantalla.

El verificador recorre el grafo de mensajes paso a paso. Si un tramo intermedio
resulta ser un escalar, la referencia no resuelve y falla.

### Fuentes derivadas

No todo lo que se dibuja es un campo del feed. El mapa consume **GeoJSON**, no
filas de `shapes.txt`. Eso se declara aparte, diciendo de qué campos se construye:

```yaml
derived_sources:
  shapes.geojson:
    from:
      - schedule:shapes.shape_id
      - schedule:shapes.shape_pt_lat
      - schedule:shapes.shape_pt_lon
      - schedule:shapes.shape_pt_sequence
```

Declararlo así mantiene la cadena completa: si `shapes.txt` pierde un campo, se
rompe la build igual que con cualquier otra referencia, y el índice inverso sigue
llegando hasta los campos de origen — `shape_pt_lat` aparece como «se muestra en
RouteMap», aunque el mapa nunca lo lea directamente.

## 5. Qué revisa CI y qué no

`uv run converters/ui/composites.py` termina con código distinto de cero cuando:

- una referencia no existe en la especificación
- un prop anida un composite que no existe
- una vista nombra un composite que no existe
- el anidamiento tiene un ciclo
- un composite repite el nombre de un prop
- el archivo no valida contra `composites.schema.json`

Advierte, sin fallar, cuando:

- un prop tiene `freshness` pero ninguna fuente de tiempo real, así que nunca
  puede expirar
- un prop obligatorio tiene **todas** sus fuentes en tiempo real, así que no
  puede dibujarse desde un feed estático
- un composite no lo usa ninguna vista ni lo anida nadie
- una fuente derivada que nadie muestra
- un prop con `mode: all` y una sola fuente, que no dice nada

La advertencia de «prop obligatorio con todas sus fuentes en tiempo real» no se
emite cuando el composite entero es de tiempo real. `RouteAlerts` sin feed de
tiempo real desaparece, y eso es correcto: no hay feed no significa que no haya
alertas.

Lo que **no** revisa: si la pantalla es buena. Eso no es trabajo de un
validador.

## 6. La página

`uv run converters/ui/composites2site.py` genera `web/dist/composites.html`,
hermana del explorador de campos. Tiene dos modos:

- **Esquema** — cajas grises apiladas, una por composite, con el nombre de cada
  prop y su etiqueta. Deliberadamente sin diseño: es un diagrama del contrato de
  datos, no una maqueta, así que no hay nada ahí que se pueda confundir con una
  decisión de diseño. Un composite de lista se dibuja dos veces, la segunda
  atenuada, porque «una fila por viaje» es un hecho de la pantalla que una sola
  fila escondería.
- **Detalle** — cada prop con su cadena de respaldo numerada, el feed de cada
  fuente, su tipo y presencia, y el componente de edición que ese campo tiene en
  `schedule.ui.yaml` (o «sin anotar», que es justamente la lista de trabajo).

- **Fuentes** — las fuentes derivadas declaradas en el archivo y el índice
  inverso completo: campo → pantallas.

## 6.1 Editar desde la página

No hace falta abrir el YAML. La página edita composites, vistas y fuentes
derivadas, con la misma arquitectura de dos capas que el explorador de campos:

| Capa | Qué es | Dónde vive |
|---|---|---|
| Base | `composites.yaml` tal como está en el repositorio | dentro de la página |
| Borrador | los cambios sin guardar | `localStorage` del navegador |

La diferencia entre las dos **es** el conjunto de cambios. De ahí salen gratis
las etiquetas «nuevo / modificado / eliminado», el descarte por entrada y el
parche de exportación.

Lo que hace editable una estructura anidada es que el formulario trabaja sobre
una copia del borrador direccionada por rutas (`props.0.sources.1`). Escribir
actualiza el borrador directamente; solo agregar, quitar o reordenar una fila
vuelve a dibujar el formulario. Por eso se puede editar una lista repetida sin
perder el cursor en cada tecla.

### Las referencias se resuelven mientras se escribe

La página lleva incrustadas las 869 referencias posibles — 218 campos de
Schedule y 650 rutas de Realtime — ya resueltas. Eso permite dos cosas:

1. Cada campo de referencia ofrece la lista completa, y marca al instante si lo
   escrito existe (`schedule`, `realtime`, `derivado`) o no (`no existe`).
2. La página entera se vuelve a calcular sobre el borrador sin guardar: el
   esquema, los contadores y el índice inverso reflejan el cambio antes de
   escribirlo al archivo.

### Cómo salen los cambios del navegador

- **En GitHub Pages** no hay servidor: la página emite un **parche** YAML con
  solo las entradas cambiadas, para copiar o descargar. Un parche y no el
  archivo completo a propósito: una exportación completa borraría los
  comentarios escritos a mano, incluidos los que dicen qué bloques siguen
  siendo provisionales.
- **Bajo `serve_site.py`** aparece el botón «Guardar en el archivo». Escribe
  `composites.yaml` a través del cargador round-trip de ruamel, así que los
  comentarios de las entradas que no se tocaron sobreviven. El endpoint acepta
  solo peticiones del mismo origen, valida el documento completo contra el
  esquema **y** resuelve todas las referencias antes de escribir nada.

Las revisiones del navegador son para retroalimentación rápida. El servidor
revalida todo antes de escribir, y CI decide.

### Una normalización de una sola vez

La primera vez que se edita una entrada, sus claves quedan en el orden del
esquema. Es ruido en el primer diff de cada entrada y nunca vuelve a pasar; a
cambio, todas las entradas terminan con la misma forma.

## 7. Alcance actual

Solo `/routes`, con los siete bloques de la propuesta del taller del 10 de
septiembre de 2026, en el orden en que están en la hoja:

| Composite | Notas de la propuesta |
|---|---|
| `RouteHeader` | **Provisional**: la foto corta la parte superior de la hoja |
| `RouteNextTrips` | Tiempo real con respaldo en horario programado |
| `RouteSchedule` | «Reemplazo de la tabla de horarios de uso común», marcado provisional |
| `RouteStops` | También escrito `RouteStopsSchedule` |
| `RouteMap` | Consume `shapes.geojson`; el globo reutiliza `RouteStops` |
| `RouteFares` | GTFS-Fares v2 explícitamente, no `fare_attributes.txt` |
| `RouteAlerts` | Tiempo real; sin feed, el bloque no se muestra |

Dos cosas de la propuesta quedaron **fuera** a propósito:

- **El calculador de tarifas.** Aparece en la hoja y es una funcionalidad, no un
  bloque de visualización. `RouteFares` solo muestra los productos aplicables.
- **El bloque superior.** `RouteHeader` está escrito por analogía, no
  transcrito. Hay que confirmarlo contra la hoja completa.
