/* Seeding a first annotation from what schedule.yaml already says.
 *
 * The feed-specific half of the editor: inferring a component means reading
 * the GTFS Schedule type vocabulary ('Enum', 'Latitude', 'Currency code'),
 * which is nothing like the protobuf one the Realtime page reads.
 */

/** A starting annotation inferred from what the spec already says.
 *
 * Most of the 200+ unannotated fields are mechanical: a foreign key is a
 * foreign_key_select pointing where the spec says it points, an Enum is a
 * select reading the spec's own options. Seeding those turns annotation into
 * review rather than typing. The human still has to write the label. */
function suggest(f, table){
  const type = (f.type || '').toLowerCase();
  const validation = {};

  const presence = (f.presence || '').toLowerCase();
  if (presence.startsWith('required')) validation.required = true;
  else if (presence.startsWith('conditionally required')) validation.required = 'conditional';
  else if (presence) validation.required = false;

  let component = 'text_input', references;

  if (f.foreign_key){
    component = 'foreign_key_select';
    references = [].concat(f.foreign_key)[0].replace('.txt', '');
  } else if (type.includes('enum')){
    component = 'select';
    validation.enum_from_spec = true;
  } else if (type.includes('color')){
    component = 'color_picker';
    validation.pattern = '^[0-9A-Fa-f]{6}$';
  } else if (type.includes('latitude')){
    component = 'map_point';
    validation.range = [-90, 90];
  } else if (type.includes('longitude')){
    component = 'map_point';
    validation.range = [-180, 180];
  } else if (type.includes('currency code')){
    component = 'currency_select';
    validation.code_list = 'iso_4217';
  } else if (type.includes('id')){
    component = 'id_input';
  } else if (/integer|float|currency amount/.test(type)){
    component = 'number_input';
    if (type.includes('non-negative')) validation.min = 0;
    else if (type.includes('positive')) validation.min = 1;
  }

  const i18n = {};
  i18n[FORM.langsRequired[0] || 'es'] = {label: ''};
  return {component, ...(references ? {references} : {}), validation, i18n};
}

