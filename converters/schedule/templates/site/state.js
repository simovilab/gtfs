/* Application state.
 *
 * Two layers, deliberately never merged in storage:
 *
 *   DATA    - built into the page from schedule.yaml + schedule.ui.yaml. Read
 *             only. This is what the repository currently says.
 *   OVERLAY - the reader's unsaved edits, kept in localStorage, keyed the same
 *             way. `null` marks an annotation the reader deleted.
 *
 * Keeping them apart is what makes "modified", "new", per-field revert and the
 * export patch fall out for free: the difference between the two layers *is*
 * the changeset. Merging happens once, at render time.
 */
const DATA = JSON.parse(document.getElementById('data').textContent);
const FORM = JSON.parse(document.getElementById('form-model').textContent);

const DRAFT_KEY = 'gtfs.schedule.ui.draft.v1';

let OVERLAY = loadDraft();
let lang = 'es';
let editing = null;   // field key currently open in the form
let canWrite = false; // set once /api/status answers (local server only)

/** key -> {field, table} for every field in the spec. */
const INDEX = new Map();
for (const table of DATA.tables)
  for (const field of table.fields) INDEX.set(field.key, {field, table});

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

const baselineOf = key => (INDEX.get(key) || {}).field?.annotation || null;

/** The annotation as it should be shown: overlay wins where it has an entry. */
function annotationOf(key){
  return Object.prototype.hasOwnProperty.call(OVERLAY, key)
    ? OVERLAY[key] : baselineOf(key);
}

/** null | 'new' | 'modified' | 'removed' */
function statusOf(key){
  if (!Object.prototype.hasOwnProperty.call(OVERLAY, key)) return null;
  const base = baselineOf(key), draft = OVERLAY[key];
  if (draft === null) return base ? 'removed' : null;
  return base ? 'modified' : 'new';
}

/* Writes replace OVERLAY rather than mutating it, so any render reading the
 * old object still sees a consistent snapshot. */
function setAnnotation(key, annotation){
  const next = {...OVERLAY};
  // An edit that lands back on the committed value is not a change.
  if (canon(annotation) === canon(baselineOf(key))) delete next[key];
  else next[key] = annotation;
  OVERLAY = next;
  saveDraft();
}

function revert(key){
  const next = {...OVERLAY};
  delete next[key];
  OVERLAY = next;
  saveDraft();
}

function discardDraft(){
  OVERLAY = {};
  saveDraft();
}

const changedKeys = () => Object.keys(OVERLAY).filter(k => statusOf(k) !== null);

/** Coverage recomputed over the merged view, so the meter tracks edits live. */
function coverage(){
  let annotated = 0;
  for (const key of INDEX.keys()) if (annotationOf(key)) annotated++;
  const total = INDEX.size;
  return {total, annotated, percent: total ? Math.round(1000 * annotated / total) / 10 : 0};
}

function tableCounts(table){
  let annotated = 0;
  for (const f of table.fields) if (annotationOf(f.key)) annotated++;
  return annotated;
}
