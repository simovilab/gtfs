/* Seeding a first annotation from what realtime.yaml already says.
 *
 * The feed-specific half of the editor. The Schedule page reads GTFS type
 * names ('Enum', 'Latitude', 'Currency code'); here the vocabulary is protobuf
 * scalars plus the message graph, so the inference is a different one.
 *
 * The guess that matters most is `origin`. It is inferred from which message
 * the field lives in rather than from the field: everything under Alert is
 * written by a person, and almost nothing else is. That is a statement about
 * how this lab produces its feed, not about GTFS Realtime, which is exactly
 * why it is a suggestion the human then confirms.
 */

// Messages whose fields a person fills in, because they describe a service
// alert rather than report a vehicle.
const AUTHORED = ['Alert', 'TimeRange', 'EntitySelector', 'Translation',
                  'TranslatedString', 'TranslatedImage', 'LocalizedImage'];

/** A starting annotation inferred from what the spec already says.
 *
 * Most of the 100+ unannotated fields are mechanical: an enum is a select
 * reading the spec's own options, a message-typed field is a sub-form, an
 * *_id is a join into the static feed. Seeding those turns annotation into
 * review rather than typing. The human still has to write the label. */
function suggest(f, table){
  const name = f.name || '', type = (f.type || '').toLowerCase();
  const validation = {};

  const presence = (f.presence || '').toLowerCase();
  if (presence.startsWith('required')) validation.required = true;
  else if (presence.startsWith('conditionally')) validation.required = 'conditional';
  else if (presence) validation.required = false;

  const origin = AUTHORED.includes(table.name) ? 'operator' : 'system';
  let component, references;

  if (f.opens){
    // A nested message is edited as a block, not as one control.
    component = 'subform';
  } else if (f.options && f.options.length){
    component = 'select';
    validation.enum_from_spec = true;
  } else if (/^(timestamp|time|start|end|last_modified_time)$/.test(name)
             && /int/.test(type)){
    // POSIX seconds. Worth asserting: milliseconds are syntactically fine and
    // put every prediction about fifty thousand years into the future.
    component = 'datetime_input';
    validation.posix_time = true;
  } else if (name === 'latitude' || name === 'longitude'){
    component = 'map_point';
    validation.range = name === 'latitude' ? [-90, 90] : [-180, 180];
    validation.bounding_box = {region: Object.keys(DATA.regions)[0], severity: 'warning'};
  } else if (STATIC_JOINS[name]){
    component = 'foreign_key_select';
    references = STATIC_JOINS[name];
  } else if (/_id$/.test(name)){
    component = 'id_input';
  } else if (type === 'bool'){
    component = 'toggle';
  } else if (/int|float|double/.test(type)){
    component = 'number_input';
    if (type.startsWith('uint')) validation.min = 0;
  } else {
    component = 'text_input';
  }

  const i18n = {};
  i18n[FORM.langsRequired[0] || 'es'] = {label: ''};
  return {origin, component, ...(references ? {references} : {}), validation, i18n};
}

/* Realtime identifiers are resolved against the static feed, so a field named
 * route_id is a join into routes.txt and not free text. These are the joins the
 * spec defines; anything else named *_id is local to the feed. */
const STATIC_JOINS = {
  agency_id: 'agency.agency_id',
  route_id: 'routes.route_id',
  trip_id: 'trips.trip_id',
  stop_id: 'stops.stop_id',
  shape_id: 'shapes.shape_id',
  zone_id: 'stops.zone_id',
  level_id: 'levels.level_id',
  parent_station: 'stops.stop_id',
  assigned_stop_id: 'stops.stop_id',
  affected_trip_id: 'trips.trip_id'
};
