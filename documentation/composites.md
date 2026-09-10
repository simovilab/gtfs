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

Un prop puede nombrar otro composite en lugar de `sources`. Así `RouteBadge` se
reutiliza dentro de `RouteHeader` en vez de repetirse.

```yaml
RouteHeader:
  entity: route          # de qué habla una instancia
  cardinality: one       # una, o una lista
  params:
    - name: route_id
      source: schedule:routes.route_id
      required: true
  props:
    - name: badge
      required: true
      composite: RouteBadge
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

## 4. Referencias a campos

```
schedule:<archivo>.<campo>          plano, porque GTFS Schedule es plano
realtime:<Mensaje>.<campo>...       un camino recorrido por los mensajes protobuf
```

La referencia de tiempo real se **recorre**, no se busca por nombre plano. Es lo
que mantiene distinguibles `arrival.time` y `departure.time`: las dos terminan en
`StopTimeEvent.time`, y una llave plana no podría decir cuál de las dos quiso
decir la pantalla.

El verificador recorre el grafo de mensajes paso a paso. Si un tramo intermedio
resulta ser un escalar, la referencia no resuelve y falla.

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

Abajo va el índice inverso completo: campo → pantallas.

La página es de solo lectura. `composites.yaml` se edita a mano; el editor del
explorador todavía no sabe editar listas repetidas, que es lo que hacen falta
para `props` y `sources`.

## 7. Alcance actual

Solo `/routes`. Cuatro composites — `RouteBadge`, `RouteHeader`, `RouteMap`,
`RouteNextTrips` — en dos vistas. Es una rebanada vertical a propósito: sirve
para saber si el modelo de cadenas de respaldo aguanta el contacto con una
pantalla real antes de escribir las demás.
