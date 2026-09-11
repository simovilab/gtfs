/* The edit form.
 *
 * Every control here is generated from FORM, which the builder derives from
 * the annotation schema governing this page — schedule.ui.schema.json or
 * realtime.ui.schema.json. Nothing about either vocabulary is written twice:
 * add a component to a schema's enum, or a rule to `validation`, and it shows
 * up in this form on the next build. That is also why one form serves two
 * feeds whose annotations do not have the same keys.
 *
 * The form does a fast subset of the schema's checks so mistakes surface while
 * typing; the authoritative check is still jsonschema, run by the coverage
 * scripts in CI.
 *
 * suggest(f) is the one piece each feed supplies for itself, since inferring a
 * starting annotation means reading that reference's own type vocabulary.
 */

const ruleSpec = name => FORM.rules.find(r => r.name === name);

/* ---------------------------------------------------------------- drawing */

function ruleRow(name, value){
  const s = t(), spec = ruleSpec(name);
  if (!spec) return '';
  let control, severity = 'error', notice = '';

  if (spec.kind === 'region'){
    const v = value || {};
    severity = v.severity || 'warning';
    control = `<select class="v">` + Object.keys(DATA.regions).map(r =>
      `<option value="${esc(r)}"${r === v.region ? ' selected' : ''}>${esc(r)}</option>`
    ).join('') + `</select>`;
  } else {
    // Unwrap the {value, severity, notice} long form if that is how it is written.
    let raw = value;
    if (raw && typeof raw === 'object' && !Array.isArray(raw) && 'value' in raw){
      severity = raw.severity || 'error';
      notice = raw.notice || '';
      raw = raw.value;
    }
    if (spec.kind === 'pair'){
      const pair = Array.isArray(raw) ? raw : ['', ''];
      control = `<input class="v0" type="number" step="any" placeholder="${esc(s.min)}" value="${esc(pair[0])}">
        <input class="v1" type="number" step="any" placeholder="${esc(s.max)}" value="${esc(pair[1])}">`;
    } else if (spec.kind === 'choice'){
      control = `<select class="v">` + spec.choices.map(c =>
        `<option value="${esc(c)}"${String(raw) === c ? ' selected' : ''}>${esc(c)}</option>`
      ).join('') + `</select>`;
    } else if (spec.kind === 'number' || spec.kind === 'integer'){
      control = `<input class="v" type="number" step="${spec.kind === 'integer' ? '1' : 'any'}" value="${esc(raw ?? '')}">`;
    } else {
      control = `<input class="v mono" type="text" value="${esc(raw ?? '')}">`;
    }
  }

  const sevControl = spec.severity
    ? `<select class="sev" title="${esc(s.severity)}">` + FORM.severities.map(v =>
        `<option value="${v}"${v === severity ? ' selected' : ''}>${v}</option>`).join('') + `</select>
       <input class="notice" type="text" placeholder="${esc(s.notice)}" value="${esc(notice)}">`
    : '';

  return `<div class="row" data-rule="${esc(name)}" title="${esc(spec.doc || '')}">
    <span class="rname">${esc(name)}</span>${control}${sevControl}
    <button type="button" class="x" data-drop="${esc(name)}">×</button></div>`;
}

function addRuleSelect(used){
  const s = t();
  const free = FORM.rules.filter(r => !used.includes(r.name));
  if (!free.length) return '';
  return `<div class="row"><select id="addrule"><option value="">${esc(s.addRule)}</option>` +
    free.map(r => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('') +
    `</select></div>`;
}

/* One control per scalar property in the annotation schema, drawn from its
 * declared kind. `component` is a select because the schema says enum;
 * `group` is a text box because the schema says string. */
function topFieldRow(spec, a){
  const s = t();
  const label = esc(s[spec.name] || spec.name);
  const value = a[spec.name] || '';
  const control = spec.kind === 'choice'
    ? `<select data-top="${esc(spec.name)}">` +
      (spec.required ? '' : `<option value=""></option>`) +
      spec.choices.map(c =>
        `<option value="${esc(c)}"${c === value ? ' selected' : ''}>${esc(c)}</option>`
      ).join('') + `</select>`
    : `<input data-top="${esc(spec.name)}" type="text" class="mono" value="${esc(value)}">`;
  return `<div class="row" title="${esc(spec.doc || '')}">
    <label${spec.required ? ' class="req"' : ''}>${label}</label>${control}</div>`;
}

function formHtml(key, a){
  const s = t();
  const rules = Object.keys(a.validation || {});

  const langBoxes = FORM.langs.map(l => {
    const entry = (a.i18n || {})[l] || {};
    const required = FORM.langsRequired.includes(l);
    return `<fieldset data-lang="${l}">
      <legend${required ? ' class="req"' : ''}>${esc(LANG_NAMES[l] || l)}</legend>
      ${FORM.i18nFields.map(fld => `<div class="row">
        <label${fld.required && required ? ' class="req"' : ''}>${esc(s[fld.name] || fld.name)}</label>
        <input type="text" data-i18n="${fld.name}" value="${esc(entry[fld.name] || '')}">
      </div>`).join('')}
    </fieldset>`;
  }).join('');

  return `<ul class="errs" id="formerrs" hidden></ul>
    <fieldset>
      <legend>${esc(s.definition)}</legend>
      ${FORM.topFields.map(spec => topFieldRow(spec, a)).join('')}
    </fieldset>
    <fieldset>
      <legend>${esc(s.validation)}</legend>
      <div id="rules">${rules.map(r => ruleRow(r, a.validation[r])).join('')}</div>
      ${addRuleSelect(rules)}
    </fieldset>
    ${langBoxes}
    <div class="acts">
      <button type="button" class="act primary" id="f-save">${esc(s.save)}</button>
      <button type="button" class="act" id="f-cancel">${esc(s.cancel)}</button>
    </div>`;
}

/* ---------------------------------------------------------------- reading */

function coerce(raw, spec){
  if (spec.kind === 'choice'){
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    return raw;
  }
  if (spec.kind === 'number' || spec.kind === 'integer') return raw === '' ? null : Number(raw);
  // `decimals` accepts an integer or the literal 'currency_precision'.
  if (/^-?\d+$/.test(raw) && spec.name === 'decimals') return Number(raw);
  return raw;
}

function readRule(row){
  const name = row.dataset.rule, spec = ruleSpec(name);
  const sevEl = row.querySelector('.sev');
  const severity = sevEl ? sevEl.value : null;

  if (spec.kind === 'region')
    return {region: row.querySelector('.v').value, severity: severity || 'warning'};

  let value;
  if (spec.kind === 'pair'){
    const a = row.querySelector('.v0').value, b = row.querySelector('.v1').value;
    value = (a === '' || b === '') ? null : [Number(a), Number(b)];
  } else {
    const raw = row.querySelector('.v').value;
    value = (raw === '') ? null : coerce(raw, spec);
  }
  if (value === null) return null;

  const notice = (row.querySelector('.notice') || {}).value?.trim() || '';
  // Short form is an error with no notice; anything else needs the long form.
  if (spec.severity && (severity !== 'error' || notice))
    return {value, severity, ...(notice ? {notice} : {})};
  return value;
}

function readForm(root){
  const validation = {}, i18n = {};

  for (const row of root.querySelectorAll('#rules .row')){
    const value = readRule(row);
    if (value !== null) validation[row.dataset.rule] = value;
  }

  for (const box of root.querySelectorAll('fieldset[data-lang]')){
    const entry = {};
    for (const input of box.querySelectorAll('[data-i18n]')){
      const v = input.value.trim();
      if (v) entry[input.dataset.i18n] = v;
    }
    if (Object.keys(entry).length) i18n[box.dataset.lang] = entry;
  }

  const top = {};
  for (const input of root.querySelectorAll('[data-top]')){
    const v = input.value.trim();
    if (v) top[input.dataset.top] = v;
  }

  return {...top, validation, i18n};
}

/** Fast subset of the JSON Schema. Returns human-readable problems. */
function validateAnnotation(a){
  const s = t(), errors = [];
  const key = new RegExp(FORM.refPattern);

  for (const name of FORM.annotationRequired)
    if (name !== 'i18n' && !a[name]) errors.push(s.errRequired(name));

  for (const lang of FORM.langsRequired)
    if (!(a.i18n[lang] || {}).label) errors.push(s.errLabel(LANG_NAMES[lang] || lang));

  // The schema's if/then clauses: "with origin = operator, component is required".
  for (const rule of FORM.conditionals)
    if (a[rule.field] === rule.value)
      for (const needed of rule.require)
        if (!a[needed]) errors.push(s.errWhen(rule.field, rule.value, needed));

  const refs = [...FORM.refFields.annotation.map(n => [n, a[n]]),
                ...FORM.refFields.validation.map(n => [n, a.validation[n]])];
  for (const [field, value] of refs){
    const raw = (value && typeof value === 'object' && 'value' in value) ? value.value : value;
    if (raw && !key.test(raw)) errors.push(s.errPattern(field));
  }

  for (const [rule, needs] of Object.entries(FORM.ruleDependencies))
    if (rule in a.validation)
      for (const other of needs)
        if (!(other in a.validation)) errors.push(s.errDep(rule, other));

  return errors;
}

/* ----------------------------------------------------------- form control */

function openForm(key){
  const a = annotationOf(key) || suggest(INDEX.get(key).field, INDEX.get(key).table);
  editing = key;

  formNode = document.createElement('form');
  formNode.className = 'edit';
  formNode.innerHTML = formHtml(key, a);
  formNode.onsubmit = e => e.preventDefault();
  wireForm(formNode, key);

  renderFields();
  // renderFields drops the form if the field is not in the current view.
  if (formNode) formNode.scrollIntoView({block: 'nearest'});
}

function wireForm(root, key){
  const add = root.querySelector('#addrule');
  if (add) add.onchange = () => {
    if (!add.value) return;
    const draft = readForm(root);
    draft.validation[add.value] = null;       // placeholder row, dropped if left empty
    reopenWith(key, draft, add.value);
  };

  root.querySelectorAll('[data-drop]').forEach(b => b.onclick = () => {
    const draft = readForm(root);
    delete draft.validation[b.dataset.drop];
    reopenWith(key, draft);
  });

  root.querySelector('#f-cancel').onclick = () => closeForm(true);
  root.querySelector('#f-save').onclick = () => {
    const draft = readForm(root);
    const errors = validateAnnotation(draft);
    const box = root.querySelector('#formerrs');
    if (errors.length){
      box.innerHTML = errors.map(e => `<li>${esc(e)}</li>`).join('');
      box.hidden = false;
      box.scrollIntoView({block: 'nearest'});
      return;
    }
    setAnnotation(key, draft);
    closeForm(true);
  };
}

/** Rebuild the form after a structural change (a rule added or dropped). */
function reopenWith(key, draft, added){
  const a = {...draft};
  if (added){
    // Give the new rule its schema default so the row draws with a value.
    const spec = ruleSpec(added);
    a.validation = {...draft.validation};
    a.validation[added] = spec.kind === 'region'
      ? {region: Object.keys(DATA.regions)[0], severity: 'warning'}
      : (spec.kind === 'choice' ? spec.choices[0] : (spec.kind === 'pair' ? ['', ''] : ''));
  }
  formNode.innerHTML = formHtml(key, a);
  wireForm(formNode, key);
}

function closeForm(rerender){
  editing = null;
  formNode = null;
  if (rerender) renderAll();
}
