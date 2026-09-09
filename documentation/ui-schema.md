# Esquema de anotaciones de edición y validación

Este documento describe `serializers/schedule/schedule.ui.yaml`: el archivo que
asocia, para cada campo de GTFS Schedule, **el componente visual con el que se
edita** y **las reglas de validación que se le aplican**.

El vocabulario está en inglés, igual que el resto del repositorio. La
documentación y las etiquetas de la interfaz están en español, portugués e
inglés.

---

## 1. Por qué un archivo aparte y no `schedule.yaml`

`serializers/schedule/schedule.yaml` es una transcripción fiel de la
especificación GTFS publicada por MobilityData. Se vuelve a generar cuando la
especificación cambia, y esa regeneración debe poder hacerse sin miedo.

Las decisiones de edición (qué componente usar, qué caja delimitadora aplicar)
**no vienen de GTFS**: son criterio propio del laboratorio. Si se escribieran
dentro de `schedule.yaml`, cada actualización de la especificación obligaría a
resolver conflictos entre texto ajeno y decisiones propias en el mismo archivo.

Por eso se separan en un archivo companion, indexado por `<archivo>.<campo>`:

| Archivo | Contenido | Quién lo cambia |
|---|---|---|
| `schedule.yaml` | Especificación GTFS | Se regenera desde la especificación |
| `schedule.ui.yaml` | Componentes y validación | El laboratorio |

Ambos archivos evolucionan y se revisan por separado. El script de cobertura
(sección 6) es el que detecta cuándo se desalinean.

## 2. Por qué la llave es `<archivo>.<campo>` y no solo `<campo>`

El nombre de un campo **no es único** en GTFS. Por ejemplo, `agency_id` aparece
en cuatro archivos distintos, y no significa lo mismo en todos: en `agency.txt`
es la llave primaria, mientras que en `routes.txt` y `fare_attributes.txt` es
una llave foránea que apunta a la primera.

Un editor tiene que tratarlos de forma distinta —`id_input` en un caso,
`foreign_key_select` en el otro—, así que la llave necesariamente incluye el
archivo.

Esta es también la razón por la que las etiquetas no se toman de la ontología:
ver sección 5.

## 3. Vocabulario de componentes

El vocabulario se mantiene deliberadamente pequeño. **Solo se agrega un
componente nuevo cuando un campo realmente no puede editarse con los
existentes**; la tentación de crear uno por cada campo hace que el editor no
tenga ninguna consistencia visual.

| Componente | Se usa para | Ejemplo |
|---|---|---|
| `text_input` | Texto libre visible para la persona usuaria | `stops.stop_name` |
| `id_input` | Identificadores internos (no visibles) | `stops.stop_id` |
| `number_input` | Valores numéricos | `fare_attributes.price` |
| `select` | Enumeraciones cerradas definidas en la especificación | `routes.route_type` |
| `color_picker` | Color hexadecimal de seis dígitos | `routes.route_color` |
| `map_point` | Coordenadas: mapa con marcador **más** dos campos decimales | `stops.stop_lat` |
| `foreign_key_select` | Referencias a filas de otra tabla | `routes.agency_id` |
| `currency_select` | Códigos ISO 4217 | `fare_attributes.currency_type` |

`id_input` se distingue de `text_input` a propósito: aunque ambos son cajas de
texto, un identificador exige unicidad dentro del archivo y se recomienda
restringirlo a ASCII imprimible, mientras que un texto visible para la persona
usuaria admite cualquier UTF-8 y no tiene por qué ser único.

### Campos que se editan juntos: `group`

`stop_lat` y `stop_lon` son dos campos en el archivo, pero **una sola decisión**
para quien edita: se pone un punto en un mapa. Ambos declaran
`component: map_point` y `group: stop_location`.

La regla para el editor es: los campos que comparten `group` se dibujan como un
único widget. En este caso, un mapa con marcador arrastrable acompañado de dos
campos decimales sincronizados, para que se pueda pegar una coordenada exacta
sin depender de la precisión del clic.

## 4. Vocabulario de validación

Toda regla tiene una **severidad**. La distinción no es cosmética: decide si el
editor bloquea el guardado o solo advierte.

- `error` — la especificación lo **exige** ("Required", "must"). Bloquea.
- `warning` — es una **recomendación** de Best Practices ("should", "recommend"),
  o una regla que agregó el laboratorio. Advierte y deja continuar.

Una regla escrita en forma corta (`min: 0`) es un `error`. Para declarar una
advertencia se usa la forma larga:

```yaml
pattern:
  value: '^[\x20-\x7E]+$'
  severity: warning
  notice: non_ascii_or_non_printable_char
```

El campo `notice` registra el aviso equivalente del validador canónico de GTFS,
para poder contrastar el editor contra esa herramienta.

**Codificar una recomendación como `error` es un defecto**, no una postura
estricta: rechazaría feeds perfectamente válidos. Por ejemplo, exigir ASCII
imprimible en los identificadores impediría guardar `parada_Ñ`, que la
especificación permite.

### 4.1 Reglas derivadas de la especificación

Son de cumplimiento obligatorio y por omisión tienen severidad `error`:

| Regla | Significado |
|---|---|
| `required` | `true`, `false` o `conditional` (ver abajo) |
| `unique_in_file` | El valor no puede repetirse dentro del archivo |
| `range: [min, max]` | Intervalo numérico cerrado |
| `min` / `max` | Cota inferior o superior |
| `max_length` | Longitud máxima en caracteres |
| `pattern` | Expresión regular |
| `decimals` | Cantidad de decimales, o `currency_precision` |
| `enum_from_spec` | Las opciones se leen de `schedule.yaml`; **nunca se copian aquí** |
| `empty_means` | Valor equivalente a la celda vacía |
| `code_list` | Lista externa de códigos (`iso_4217`, `iana_tz`, …) |

`required: conditional` corresponde a *Conditionally Required* de GTFS. No se
resuelve en este archivo: la condición ya está escrita en `schedule.yaml`, y el
editor la evalúa en tiempo de ejecución. Duplicarla aquí sería copiar la
especificación.

`enum_from_spec` merece énfasis: los valores de `route_type` no se repiten en
este archivo. Están en `schedule.yaml` y de ahí los toma el editor. Copiarlos
garantizaría que algún día queden desactualizados.

Tres precisiones que se verificaron contra el validador canónico y que
contradicen suposiciones habituales:

- La especificación **no impone longitud máxima** a los identificadores ni a
  `stop_name`. El único tope real es de 4096 caracteres, en la capa de lectura
  del CSV.
- El ASCII imprimible en identificadores es una **recomendación**, no un
  requisito: los IDs admiten cualquier UTF-8.
- Los 12 caracteres de `route_short_name` son una **recomendación**
  (`route_short_name_too_long` es un *warning*), no un límite de la
  especificación.

### 4.2 Reglas propias del laboratorio

`bounding_box` es distinta: **no viene de GTFS**. Una parada fuera de Costa Rica
no viola la especificación —es perfectamente válida— pero casi siempre es un
error de digitación (un signo cambiado, latitud y longitud invertidas).

Por eso lleva severidad explícita y su valor por omisión es `warning`, no
`error`:

```yaml
bounding_box:
  region: costa_rica
  severity: warning
```

Bloquear el guardado sería incorrecto: hay paradas transfronterizas legítimas
hacia Panamá y Nicaragua. El editor debe advertir y dejar continuar.

GTFS es un formato global y **no impone ninguna restricción geográfica** sobre
las coordenadas; el `countryCode` del validador canónico solo sirve para validar
teléfonos. La caja es enteramente criterio del laboratorio, y por eso nunca
puede ser `error`.

Vale la pena considerar además los avisos `point_near_origin` y
`point_near_pole` del validador canónico, que detectan coordenadas en (0,0) o
cerca de los polos. Son más universales que una caja por país y atrapan el error
de digitación más común. Todavía no están en el vocabulario.

Esta distinción —reglas de la especificación contra reglas del laboratorio— es
la que justifica que exista el campo `severity`.

### 4.3 Reglas que dependen de otro campo

Algunas validaciones no se pueden resolver campo por campo:

- **`fare_attributes.price`** declara `decimals: currency_precision` y
  `decimals_from: fare_attributes.currency_type`. La cantidad de decimales la
  fija ISO 4217 según la moneda: CRC y USD usan 2, JPY usa 0. El editor debe
  releer la precisión cuando cambia la moneda.
- **`routes.route_color`** declara `contrast_with: routes.route_text_color`. La
  especificación dice que el contraste *debería* ser suficiente, así que la
  regla es `warning` y solo puede evaluarse con los dos valores presentes.

Ni la especificación ni el validador definen una cantidad de decimales para
`stop_lat`/`stop_lon`, así que no se declara ninguna: la precisión del ingreso
es asunto del widget de mapa, no una regla de validación.

### 4.4 Llaves foráneas

Un campo con `component: foreign_key_select` **debe** declarar `references`
apuntando a `<archivo>.<campo>`. El esquema JSON lo exige.

Su validación es de naturaleza distinta a todas las demás: no es un patrón ni un
intervalo, sino **existencia de la fila referenciada**. No puede resolverse
mirando el valor en aislamiento; requiere consultar la otra tabla. Por eso se
marca con un campo propio y no con `pattern`.

## 5. Etiquetas: por qué no se reutiliza la ontología

`ontologies/schedule/i18n/{en,es,pt}.ttl` ya tiene etiquetas por campo en los
tres idiomas. Aun así, las etiquetas de la interfaz viven en este archivo, por
dos razones concretas:

**Primera: son de otro registro.** La ontología traduce el *nombre de máquina*
del campo, no la etiqueta que ve una persona:

| Campo | `rdfs:label` en la ontología | Etiqueta de interfaz |
|---|---|---|
| `stop_lat` | `latitud_parada` | Latitud |
| `route_color` | `color_ruta` | Color de la ruta |

`latitud_parada` es correcto como identificador traducido, pero nadie quiere
verlo encima de una caja de texto en un formulario.

**Segunda: la ontología no puede distinguir por tabla.** Su espacio de nombres
es plano: existe un único nodo `gtfs:agency_id`, aunque el campo aparezca en
cuatro archivos con significados distintos. No hay forma de darle una etiqueta
distinta en `agency.txt` y en `routes.txt`.

Las descripciones (`rdfs:comment`) sí sirvieron como punto de partida para el
texto de ayuda, adaptándolas al modo imperativo que corresponde a un formulario.

## 6. Cobertura

```bash
uv run converters/schedule/ui_coverage.py            # informe legible
uv run converters/schedule/ui_coverage.py --json     # informe en JSON
```

El script compara los campos declarados en `schedule.yaml` contra las llaves de
`schedule.ui.yaml`, y valida el archivo de anotaciones contra
`schedule.ui.schema.json`.

Distingue dos situaciones:

- **Campos sin anotar**: es lo esperado mientras el barrido está en curso. Se
  reportan y **no** hacen fallar la ejecución.
- **Anotaciones huérfanas o inválidas**: una llave que no corresponde a ningún
  campo real, o un archivo que viola su esquema. Siempre son errores y **sí**
  hacen fallar la ejecución (código de salida 1).

`--min-coverage N` permite exigir un piso de cobertura. Se deja en 0 mientras el
barrido avanza; conviene subirlo a medida que se completan tablas, para que la
cobertura no retroceda.

## 7. Cómo anotar un campo nuevo

1. Ubicar el campo en `schedule.yaml` y leer su `type`, `presence` y
   `description`.
2. Elegir un componente **del vocabulario existente**. Si ninguno sirve,
   agregarlo primero al `enum` de `schedule.ui.schema.json` y documentarlo en la
   sección 3 — no inventar valores sueltos.
3. Escribir solo las validaciones que la especificación exige, en forma corta.
   Todo lo que sea recomendación o criterio propio va en forma larga con
   `severity: warning`. Si el campo es una enumeración, usar
   `enum_from_spec: true` en lugar de copiar los valores.
   Ante la duda, revisar el aviso correspondiente del validador canónico: si
   ahí es *warning*, aquí también.
4. Agregar `label` y `help` al menos en español (el esquema lo exige); inglés y
   portugués son opcionales pero recomendados.
5. Correr el script de cobertura y confirmar que no aparecen errores.
