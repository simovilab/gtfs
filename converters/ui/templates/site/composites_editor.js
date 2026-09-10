/* The editing forms.
 *
 * Everything here works on one draft object — a deep copy of the entry being
 * edited — addressed by path strings like "props.0.sources.1". Scalar inputs
 * write straight into the draft as you type; only structural changes (adding,
 * removing or reordering a row) re-render the form. That is what keeps a
 * repeating list editable without losing the caret on every keystroke.
 *
 * The vocabulary — entities, cardinalities, modes, languages, patterns — comes
 * from FORM, which converters/ui/composites_form.py reads out of the JSON
 * schema. None of it is restated here, so adding an entity to the schema adds
 * it to this form.
 */

let editing = null;   // {section, name, draft, isNew} | null
let formNode = null;  // kept detached across re-renders

/* ------------------------------------------------------------- draft paths */

const getPath = (obj, path) =>
  path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj);

function setPath(obj, path, value){
  const keys = path.split('.'), last = keys.pop();
  const target = keys.reduce((o, k) => o[k], obj);
  if (value === '' || value === undefined) delete target[last];
  else target[last] = value;
}

/* -------------------------------------------------------------- templates */

function blankProp(){ return {name: '', sources: ['']}; }
function blankParam(){ return {name: '', source: '', required: true}; }

function blankEntry(section){
  const first = FORM.langsRequired[0];
  if (section === 'composites')
    return {entity: FORM.entities[0], cardinality: 'one',
            i18n: {[first]: {label: ''}}, props: [blankProp()]};
  if (section === 'views')
    return {path: '/', i18n: {[first]: {label: ''}}, blocks: []};
  return {from: [''], i18n: {[first]: {label: ''}}};
}

/* ---------------------------------------------------------------- widgets */

const opt = (value, current, text) =>
  `<option value="${esc(value)}"${value === current ? ' selected' : ''}>${esc(text ?? value)}</option>`;

function textRow(label, path, value, extra){
  return `<div class="row"><label>${esc(label)}</label>
    <input type="text" data-path="${esc(path)}" value="${esc(value || '')}"
      ${extra || ''}></div>`;
}

function selectRow(label, path, value, values, names){
  return `<div class="row"><label>${esc(label)}</label>
    <select data-path="${esc(path)}">
      ${values.map(v => opt(v, value, names ? names(v) : v)).join('')}
    </select></div>`;
}

/** A reference input: free text, but backed by the full catalog and checked
 *  as you type, because a mistyped path is the one error the schema cannot
 *  catch on its own. */
function refInput(path, value, derived){
  const state = value ? resolveRef(value, derived) : null;
  const mark = !value ? ''
    : state.exists
      ? `<span class="tag ${state.feed === 'realtime' ? 'rt' : state.feed === 'derived' ? 'der' : 'sched'}">${esc(state.feed)}</span>`
      : `<span class="tag bad">${esc(t().errUnknownRef)}</span>`;
  return `<input type="text" class="mono" list="refs" data-path="${esc(path)}"
    data-ref value="${esc(value || '')}" placeholder="schedule:routes.route_id">${mark}`;
}

const rowButtons = (kind, ...args) => `
  <button type="button" class="x" data-act="move-${kind}" data-args="${esc([...args, -1].join(':'))}" title="↑">↑</button>
  <button type="button" class="x" data-act="move-${kind}" data-args="${esc([...args, 1].join(':'))}" title="↓">↓</button>
  <button type="button" class="x" data-act="del-${kind}" data-args="${esc(args.join(':'))}" title="×">×</button>`;

/* ------------------------------------------------------------ composite form */

function i18nFieldset(draft, withHelp){
  const s = t();
  return `<fieldset><legend>${esc(s.labels)}</legend>
    ${FORM.langs.map(l => {
      const entry = (draft.i18n || {})[l] || {};
      const required = FORM.langsRequired.includes(l);
      return `<div class="row"><label class="${required ? 'req' : ''}">${esc(LANG_NAMES[l] || l)}</label>
        <input type="text" data-path="i18n.${l}.label" value="${esc(entry.label || '')}"
          placeholder="${esc(s.label)}">
        ${withHelp ? `<input type="text" data-path="i18n.${l}.help"
          value="${esc(entry.help || '')}" placeholder="${esc(s.help)}">` : ''}</div>`;
    }).join('')}</fieldset>`;
}

function propBlockForm(prop, index, derived, names){
  const s = t(), nested = prop.composite !== undefined;
  return `<div class="propedit">
    <div class="row">
      <input type="text" class="mono rname" data-path="props.${index}.name"
        value="${esc(prop.name || '')}" placeholder="${esc(s.propName)}">
      <label class="chk"><input type="checkbox" data-path="props.${index}.required"
        ${prop.required ? 'checked' : ''}> ${esc(s.required)}</label>
      <select data-path="props.${index}.mode" class="sev"
        ${nested ? 'disabled' : ''}>${FORM.modes.map(m => opt(m, prop.mode || 'fallback', s.modeNames[m])).join('')}</select>
      <button type="button" class="x" data-act="toggle-nested" data-args="${index}"
        title="${esc(s.nested)}">${nested ? '⤺' : '⤷'}</button>
      ${rowButtons('prop', index)}
    </div>

    ${nested
      ? `<div class="row"><label>${esc(s.nested)}</label>
          <select data-path="props.${index}.composite">
            ${['', ...names].map(n => opt(n, prop.composite, n || '—')).join('')}
          </select></div>`
      : `<p class="optcat">${esc((prop.mode === 'all') ? s.combined : s.sources)}</p>
         ${(prop.sources || []).map((ref, j) => `<div class="row">
            <span class="wfslot">${j + 1}</span>
            ${refInput(`props.${index}.sources.${j}`, ref, derived)}
            ${rowButtons('source', index, j)}</div>`).join('')}
         <button type="button" class="act tiny" data-act="add-source"
           data-args="${index}">${esc(s.addSource)}</button>`}

    ${textRow(s.freshness, `props.${index}.freshness`, prop.freshness,
              `placeholder="90s"`)}
    ${textRow(s.compute, `props.${index}.compute`, prop.compute)}
    ${textRow(s.note, `props.${index}.note`, prop.note)}
    <div class="row"><label>${esc(s.propLabel)}</label>
      ${FORM.langs.map(l => `<input type="text" data-path="props.${index}.i18n.${l}.label"
        value="${esc(((prop.i18n || {})[l] || {}).label || '')}"
        placeholder="${esc(l)}">`).join('')}</div>
  </div>`;
}

function compositeForm(draft, derived, names){
  const s = t();
  return `
    ${editing.isNew ? textRow(s.name, '@name', editing.name,
        `class="mono" placeholder="RouteHeader"`) : ''}
    <fieldset><legend>${esc(s.identity)}</legend>
      ${selectRow(s.entity, 'entity', draft.entity, FORM.entities, entityName)}
      ${selectRow(s.cardinality, 'cardinality', draft.cardinality, FORM.cardinalities,
                  v => v === 'many' ? s.many : s.one)}
      ${draft.cardinality === 'many'
        ? `<div class="row"><label class="req">${esc(s.key)}</label>
            ${refInput('key', draft.key, derived)}</div>` : ''}
    </fieldset>

    ${i18nFieldset(draft, true)}

    <fieldset><legend>${esc(s.params)}</legend>
      ${(draft.params || []).map((p, i) => `<div class="row">
        <input type="text" class="mono rname" data-path="params.${i}.name"
          value="${esc(p.name || '')}" placeholder="route_id">
        ${refInput(`params.${i}.source`, p.source, derived)}
        <label class="chk"><input type="checkbox" data-path="params.${i}.required"
          ${p.required !== false ? 'checked' : ''}> ${esc(s.required)}</label>
        ${rowButtons('param', i)}</div>`).join('')}
      <button type="button" class="act tiny" data-act="add-param">${esc(s.addParam)}</button>
    </fieldset>

    <fieldset><legend>${esc(s.props)}</legend>
      ${(draft.props || []).map((p, i) => propBlockForm(p, i, derived, names)).join('')}
      <button type="button" class="act tiny" data-act="add-prop">${esc(s.addProp)}</button>
    </fieldset>

    <fieldset><legend>${esc(s.notes)}</legend>
      ${(draft.notes || []).map((n, i) => `<div class="row">
        <input type="text" data-path="notes.${i}" value="${esc(n)}">
        ${rowButtons('note', i)}</div>`).join('')}
      <button type="button" class="act tiny" data-act="add-note">${esc(s.addNote)}</button>
    </fieldset>`;
}

function viewForm(draft, derived, names){
  const s = t();
  return `
    ${editing.isNew ? textRow(s.name, '@name', editing.name,
        `class="mono" placeholder="routes_detail"`) : ''}
    <fieldset><legend>${esc(s.identity)}</legend>
      ${textRow(s.path, 'path', draft.path, `class="mono" placeholder="/routes/:route_id"`)}
    </fieldset>
    ${i18nFieldset(draft, false)}
    <fieldset><legend>${esc(s.blocks)}</legend>
      ${(draft.blocks || []).map((b, i) => `<div class="row">
        <span class="wfslot">${i + 1}</span>
        <select data-path="blocks.${i}">${['', ...names].map(n => opt(n, b, n || '—')).join('')}</select>
        ${rowButtons('block', i)}</div>`).join('')}
      <button type="button" class="act tiny" data-act="add-block">${esc(s.addBlock)}</button>
    </fieldset>`;
}

function derivedForm(draft, derived){
  const s = t();
  return `
    ${editing.isNew ? textRow(s.name, '@name', editing.name,
        `class="mono" placeholder="shapes.geojson"`) : ''}
    ${i18nFieldset(draft, false)}
    <fieldset><legend>${esc(s.builtFrom)}</legend>
      ${(draft.from || []).map((ref, i) => `<div class="row">
        <span class="wfslot">${i + 1}</span>
        ${refInput(`from.${i}`, ref, derived)}
        ${rowButtons('from', i)}</div>`).join('')}
      <button type="button" class="act tiny" data-act="add-from">${esc(s.addSource)}</button>
    </fieldset>
    ${textRow(s.note, 'note', draft.note)}`;
}

/* --------------------------------------------------------------- rendering */

function renderForm(){
  const s = t(), {section, draft} = editing;
  const model = buildModel();
  const names = model.composites.map(c => c.name).sort();
  const derived = model.derived;

  const body = section === 'composites' ? compositeForm(draft, derived, names)
             : section === 'views' ? viewForm(draft, derived, names)
             : derivedForm(draft, derived);

  formNode.innerHTML = `<ul class="errs" hidden></ul>${body}
    <div class="acts">
      <button type="button" class="act primary" data-act="save">${esc(s.save)}</button>
      <button type="button" class="act" data-act="cancel">${esc(s.cancel)}</button>
    </div>`;
}

/* Structural edits rebuild the form; typing does not. */
function structural(fn){ fn(); renderForm(); }

function move(list, index, delta){
  const to = index + delta;
  if (to < 0 || to >= list.length) return;
  [list[index], list[to]] = [list[to], list[index]];
}

function onFormClick(event){
  const button = event.target.closest('[data-act]');
  if (!button || !editing) return;
  const draft = editing.draft;
  const args = (button.dataset.args || '').split(':').filter(x => x !== '');
  const n = args.map(Number);

  switch (button.dataset.act){
    case 'save':   return saveForm();
    case 'cancel': return closeForm();

    case 'add-param':  return structural(() => (draft.params ||= []).push(blankParam()));
    case 'del-param':  return structural(() => draft.params.splice(n[0], 1));
    case 'move-param': return structural(() => move(draft.params, n[0], n[1]));

    case 'add-prop':   return structural(() => (draft.props ||= []).push(blankProp()));
    case 'del-prop':   return structural(() => draft.props.splice(n[0], 1));
    case 'move-prop':  return structural(() => move(draft.props, n[0], n[1]));

    case 'add-source': return structural(() => (draft.props[n[0]].sources ||= []).push(''));
    case 'del-source': return structural(() => draft.props[n[0]].sources.splice(n[1], 1));
    case 'move-source':return structural(() => move(draft.props[n[0]].sources, n[1], n[2]));

    case 'toggle-nested': return structural(() => {
      const prop = draft.props[n[0]];
      // A prop is a fallback chain or a nested composite, never both, so the
      // toggle has to clear the other side rather than leave it hidden.
      if (prop.composite !== undefined){ delete prop.composite; prop.sources = ['']; }
      else { delete prop.sources; delete prop.mode; prop.composite = ''; }
    });

    case 'add-note':   return structural(() => (draft.notes ||= []).push(''));
    case 'del-note':   return structural(() => draft.notes.splice(n[0], 1));
    case 'move-note':  return structural(() => move(draft.notes, n[0], n[1]));

    case 'add-block':  return structural(() => (draft.blocks ||= []).push(''));
    case 'del-block':  return structural(() => draft.blocks.splice(n[0], 1));
    case 'move-block': return structural(() => move(draft.blocks, n[0], n[1]));

    case 'add-from':   return structural(() => (draft.from ||= []).push(''));
    case 'del-from':   return structural(() => draft.from.splice(n[0], 1));
    case 'move-from':  return structural(() => move(draft.from, n[0], n[1]));
  }
}

function onFormInput(event){
  const el = event.target;
  if (!editing || !el.dataset.path) return;
  const path = el.dataset.path;
  const value = el.type === 'checkbox' ? el.checked : el.value;

  if (path === '@name'){ editing.name = String(value).trim(); return; }
  setPath(editing.draft, path, value);

  // A changed reference redraws only its own badge; a changed cardinality or
  // mode changes which controls exist, so the form is rebuilt.
  if (el.dataset.ref !== undefined){
    const derived = buildModel().derived;
    const holder = document.createElement('span');
    holder.innerHTML = refInput(path, value, derived);
    const badge = holder.querySelector('.tag');
    el.parentElement.querySelectorAll(':scope > .tag').forEach(x => x.remove());
    if (badge) el.insertAdjacentElement('afterend', badge);
  } else if (path === 'cardinality' || path.endsWith('.mode')){
    renderForm();
  }
}

/* -------------------------------------------------------------- lifecycle */

function openEditor(section, name){
  const existing = entryOf(section, name);
  editing = {section, name, isNew: !existing, draft: clone(existing || blankEntry(section))};
  renderAll();
}

function openNew(section){
  editing = {section, name: '', isNew: true, draft: blankEntry(section)};
  renderAll();
}

function closeForm(){ editing = null; formNode = null; renderAll(); }

/* Validation here is for fast feedback only. The server revalidates the whole
 * merged document against the schema, and resolves every reference, before it
 * writes anything — that check is the authority. */
function validateDraft(){
  const s = t(), {section, name, draft, isNew} = editing;
  const model = buildModel(), errors = [];
  const pattern = {composites: FORM.compositeNamePattern, views: FORM.viewNamePattern,
                   derived_sources: FORM.derivedNamePattern}[section];

  if (!name) errors.push(s.errName);
  else if (!new RegExp(pattern).test(name)) errors.push(s.errNamePattern(pattern));
  else if (isNew && entryOf(section, name)) errors.push(s.errNameTaken(name));

  for (const l of FORM.langsRequired)
    if (!((draft.i18n || {})[l] || {}).label) errors.push(s.errLabel(l));

  const refs = [];
  const check = (ref, where) => {
    if (!ref) return errors.push(s.errRefEmpty(where));
    if (!resolveRef(ref, model.derived).exists) errors.push(s.errRefUnknown(ref));
    refs.push(ref);
  };

  if (section === 'composites'){
    if (draft.cardinality === 'many') check(draft.key, s.key);
    const seen = new Set();
    for (const [i, prop] of (draft.props || []).entries()){
      const where = prop.name || `#${i + 1}`;
      if (!prop.name) errors.push(s.errPropName(i + 1));
      else if (!new RegExp(FORM.namePattern).test(prop.name))
        errors.push(s.errPropPattern(prop.name));
      else if (seen.has(prop.name)) errors.push(s.errPropDup(prop.name));
      seen.add(prop.name);

      if (prop.composite !== undefined){
        if (!prop.composite) errors.push(s.errNestedEmpty(where));
        else if (prop.composite === name) errors.push(s.errNestedSelf(where));
      } else {
        if (!(prop.sources || []).length) errors.push(s.errNoSources(where));
        (prop.sources || []).forEach(r => check(r, where));
        if (prop.mode === 'all' && (prop.sources || []).length < 2)
          errors.push(s.errModeAll(where));
      }
      if (prop.freshness && !new RegExp(FORM.freshnessPattern).test(prop.freshness))
        errors.push(s.errFreshness(where));
    }
    for (const [i, param] of (draft.params || []).entries()){
      if (!param.name) errors.push(s.errParamName(i + 1));
      check(param.source, param.name || `#${i + 1}`);
    }
  } else if (section === 'views'){
    if (!draft.path || !new RegExp(FORM.pathPattern).test(draft.path))
      errors.push(s.errPath);
    if (!(draft.blocks || []).length) errors.push(s.errNoBlocks);
    (draft.blocks || []).forEach(b => {
      if (!b) errors.push(s.errBlockEmpty);
      else if (!model.composites.some(c => c.name === b)) errors.push(s.errBlockUnknown(b));
    });
  } else {
    if (!(draft.from || []).length) errors.push(s.errNoSources(name));
    (draft.from || []).forEach(r => check(r, name));
  }
  return errors;
}

/** Drop empty strings and empty containers, so an untouched optional field
 *  never lands in the file as `note: ''`. */
function prune(value){
  if (Array.isArray(value)){
    const out = value.map(prune).filter(v => v !== undefined);
    return out.length ? out : undefined;
  }
  if (value && typeof value === 'object'){
    const out = {};
    for (const [k, v] of Object.entries(value)){
      const cleaned = prune(v);
      if (cleaned !== undefined) out[k] = cleaned;
    }
    return Object.keys(out).length ? out : undefined;
  }
  if (value === '' || value === null || value === undefined) return undefined;
  return value;
}

/** Re-key an entry into the schema's own property order.
 *
 * Applied to the nested rows too, so a prop written by the form comes out in
 * the same order as the hand-written ones beside it in the file.
 */
function ordered(entry, keys){
  const out = {};
  for (const key of [...keys, ...Object.keys(entry)])
    if (key in entry && !(key in out)) out[key] = entry[key];
  if (Array.isArray(out.props)) out.props = out.props.map(p => ordered(p, FORM.propKeys));
  if (Array.isArray(out.params)) out.params = out.params.map(p => ordered(p, FORM.paramKeys));
  return out;
}

function saveForm(){
  const errors = validateDraft();
  const box = formNode.querySelector('.errs');
  box.hidden = !errors.length;
  box.innerHTML = errors.map(e => `<li>${esc(e)}</li>`).join('');
  if (errors.length){ box.scrollIntoView({block: 'nearest'}); return; }

  const {section, name, draft} = editing;
  const keys = {composites: FORM.compositeKeys, views: FORM.viewKeys,
                derived_sources: FORM.derivedKeys}[section];
  // `fallback` is the default; writing it out would put a key in the file that
  // the hand-written entries all omit.
  for (const prop of draft.props || []) if (prop.mode === 'fallback') delete prop.mode;
  const cleaned = prune(draft) || {};
  // `required: false` is meaningful on a param, where the default is true, so
  // pruning must not be allowed to eat it.
  for (const [i, param] of (draft.params || []).entries())
    if (param.required === false && cleaned.params?.[i]) cleaned.params[i].required = false;
  for (const [i, prop] of (draft.props || []).entries())
    if (prop.composite === '' && cleaned.props?.[i]) cleaned.props[i].composite = '';

  setEntry(section, name, ordered(cleaned, keys));
  closeForm();
}

function removeEntry(section, name){
  setEntry(section, name, null);
  renderAll();
}

function duplicateEntry(section, name){
  const copy = clone(entryOf(section, name));
  editing = {section, name: `${name}Copy`, isNew: true, draft: copy};
  renderAll();
}
