/* Application state for the composites page.
 *
 * Two layers, deliberately never merged in storage:
 *
 *   DOC     - the authored composites.yaml, built into the page. Read only.
 *             This is what the repository currently says.
 *   OVERLAY - the reader's unsaved edits, in localStorage, keyed
 *             "<section>/<name>". `null` marks an entry the reader deleted.
 *
 * The difference between the two layers *is* the changeset, which is what
 * makes "new/modified/removed", per-entry revert and the export fall out for
 * free. Merging happens once, at render time.
 *
 * CATALOG carries every reference that could be typed, already resolved at
 * build time. That is what lets an edited document be re-resolved here rather
 * than on the server: the page can redraw a draft without saving it first.
 */
const DOC = JSON.parse(document.getElementById('doc').textContent);
const CATALOG = JSON.parse(document.getElementById('catalog').textContent);
const FORM = JSON.parse(document.getElementById('form-model').textContent);

const DRAFT_KEY = 'gtfs.composites.draft.v1';
const SECTIONS = ['derived_sources', 'composites', 'views'];

let OVERLAY = loadDraft();
let lang = 'es';
let canWrite = false;   // set once api/status answers (local server only)

function loadDraft(){
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    console.warn('draft unreadable, starting empty', e);
    return {};
  }
}

function saveDraft(){
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(OVERLAY)); }
  catch (e) { console.warn('draft could not be stored', e); }
}

/** Stable stringify, so key order never counts as a difference. */
function canon(value){
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return '[' + value.map(canon).join(',') + ']';
  return '{' + Object.keys(value).sort()
    .filter(k => value[k] !== undefined)
    .map(k => JSON.stringify(k) + ':' + canon(value[k])).join(',') + '}';
}

const clone = v => JSON.parse(JSON.stringify(v));
const idOf = (section, name) => `${section}/${name}`;
const baselineOf = (section, name) => (DOC[section] || {})[name] || null;

function entryOf(section, name){
  const id = idOf(section, name);
  return Object.prototype.hasOwnProperty.call(OVERLAY, id)
    ? OVERLAY[id] : baselineOf(section, name);
}

/** null | 'new' | 'modified' | 'removed' */
function statusOf(section, name){
  const id = idOf(section, name);
  if (!Object.prototype.hasOwnProperty.call(OVERLAY, id)) return null;
  const base = baselineOf(section, name), draft = OVERLAY[id];
  if (draft === null) return base ? 'removed' : null;
  return base ? 'modified' : 'new';
}

/* Writes replace OVERLAY rather than mutating it, so any render reading the
 * old object still sees a consistent snapshot. */
function setEntry(section, name, entry){
  const next = {...OVERLAY}, id = idOf(section, name);
  // An edit that lands back on the committed value is not a change.
  if (canon(entry) === canon(baselineOf(section, name))) delete next[id];
  else next[id] = entry;
  OVERLAY = next;
  saveDraft();
}

function revert(section, name){
  const next = {...OVERLAY};
  delete next[idOf(section, name)];
  OVERLAY = next;
  saveDraft();
}

function discardDraft(){ OVERLAY = {}; saveDraft(); }

const changedKeys = () => Object.keys(OVERLAY)
  .filter(id => statusOf(...splitId(id)) !== null);

function splitId(id){
  const cut = id.indexOf('/');
  return [id.slice(0, cut), id.slice(cut + 1)];
}

/** DOC with the overlay applied: what the page draws and what gets written. */
function merged(){
  const out = {};
  for (const section of SECTIONS){
    const entries = {...(DOC[section] || {})};
    for (const id of Object.keys(OVERLAY)){
      const [where, name] = splitId(id);
      if (where !== section) continue;
      if (OVERLAY[id] === null) delete entries[name];
      else entries[name] = OVERLAY[id];
    }
    out[section] = entries;
  }
  return out;
}

/* ------------------------------------------------------------- resolving */

const labelsOf = i18n => Object.fromEntries(
  FORM.langs.map(l => [l, ((i18n || {})[l] || {}).label || '']));

/** One reference, resolved the way converters/ui/composites.py resolves it.
 *
 * Derived sources are looked up in the *merged* document rather than the
 * catalog, so an artifact the reader just declared resolves immediately.
 */
function resolveRef(ref, derived){
  const cut = String(ref).indexOf(':');
  const feed = cut < 0 ? '' : ref.slice(0, cut), path = cut < 0 ? ref : ref.slice(cut + 1);

  if (feed === 'derived'){
    const artifact = (derived || {})[path];
    if (!artifact) return {ref, feed, path, exists: false, label: {}};
    return {ref, feed, path, exists: true, type: 'derived',
            label: labelsOf(artifact.i18n), description: artifact.note || '',
            sources: (artifact.from || []).map(r => resolveRef(r, derived))};
  }
  const hit = CATALOG[ref];
  if (!hit) return {ref, feed, path, exists: false, label: {}};
  return {...hit, ref, exists: true, label: hit.label || {}};
}

/** The resolved model the page renders, rebuilt on every change. */
function buildModel(){
  const doc = merged();
  const derived = doc.derived_sources || {};
  const composites = [], reverse = {};

  for (const [name, spec] of Object.entries(doc.composites || {})){
    const params = (spec.params || []).map(p => ({
      ...p, required: p.required !== false, resolved: resolveRef(p.source, derived)}));

    const props = (spec.props || []).map(prop => {
      const sources = (prop.sources || []).map(r => resolveRef(r, derived));
      for (const source of sources){
        (reverse[source.ref] ||= []).push({composite: name, prop: prop.name});
        // A field used only to build shapes.geojson is still displayed by
        // whatever draws that geojson.
        for (const under of source.sources || [])
          (reverse[under.ref] ||= []).push(
            {composite: name, prop: prop.name, via: source.path});
      }
      return {...prop, required: !!prop.required,
              mode: prop.mode || 'fallback', sources};
    });

    for (const param of params)
      (reverse[param.resolved.ref] ||= []).push(
        {composite: name, prop: param.name, param: true});

    composites.push({
      name,
      entity: spec.entity,
      cardinality: spec.cardinality,
      key: spec.key ? resolveRef(spec.key, derived) : null,
      i18n: spec.i18n || {},
      params, props,
      notes: spec.notes || [],
      usedBy: Object.entries(doc.views || {})
        .filter(([, v]) => (v.blocks || []).includes(name)).map(([n]) => n),
      nestedIn: [...new Set(Object.entries(doc.composites || {})
        .filter(([, s]) => (s.props || []).some(p => p.composite === name))
        .map(([n]) => n))].sort(),
    });
  }

  const views = Object.entries(doc.views || {}).map(([name, view]) => ({name, ...view}));
  const refs = Object.keys(reverse);
  const scheduleRefs = refs.filter(r => r.startsWith('schedule:'));
  const annotated = scheduleRefs.filter(r => (CATALOG[r] || {}).annotated).length;

  return {
    composites, views, derived, reverse, langs: FORM.langs,
    stats: {
      composites: composites.length, views: views.length, refs: refs.length,
      schedule: scheduleRefs.length,
      realtime: refs.filter(r => r.startsWith('realtime:')).length,
      derived: refs.filter(r => r.startsWith('derived:')).length,
      annotated,
      percent: scheduleRefs.length
        ? Math.round(1000 * annotated / scheduleRefs.length) / 10 : 0,
    },
  };
}
