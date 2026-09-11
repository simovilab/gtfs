/* Rendering. Reads through annotationOf(), so the spec column always shows the
 * repository and the editor column always shows the merged (spec + draft) view.
 *
 * Nothing here knows which feed it is drawing. A "table" is a GTFS file on the
 * Schedule side and a protobuf message on the Realtime side; the per-field
 * facts the spec column lists arrive as data, built by whichever builder made
 * the page. */

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// Show annotated tables first so the demo scope is what you land on.
const tablesSorted = () => DATA.tables.slice().sort((a,b) =>
  (tableCounts(b) > 0) - (tableCounts(a) > 0) || a.name.localeCompare(b.name));

// Land on the first annotated table, not the first table in spec order.
let current = (tablesSorted()[0] || {}).name || null;

// The live edit form, kept as a detached node across re-renders so typing is
// not lost when the list around it is rebuilt.
let formNode = null;

function renderLangs(){
  document.getElementById('langs').innerHTML = DATA.langs.map(l =>
    `<button data-l="${l}" aria-pressed="${l===lang}">${LANG_NAMES[l]||l}</button>`).join('');
  document.querySelectorAll('#langs button').forEach(b =>
    b.onclick = () => { lang = b.dataset.l; document.documentElement.lang = lang; renderAll(); });
}

function renderChrome(){
  const s = t(), c = coverage();
  document.getElementById('subtitle').textContent = s.subtitle;
  document.getElementById('covtext').textContent = s.coverage(c.annotated, c.total, c.percent);
  document.getElementById('covbar').style.width = Math.max(c.percent, 1.5) + '%';
  document.getElementById('search').placeholder = s.search;
  document.getElementById('footer').innerHTML =
    s.footer(PAGE) + ' ' + esc(DATA.metadata.revision_date || '');
  document.getElementById('table').innerHTML = tablesSorted().map(tb =>
    `<option value="${tb.name}"${tb.name===current?' selected':''}>${esc(tb.title)} — ${tableCounts(tb)}/${tb.total} ${esc(s.annotated)}</option>`
  ).join('');
}

function validationRows(v){
  return Object.entries(v).map(([k, val]) => {
    let out, sev = '';
    // Long form: {value, severity, notice}. Scalars are spec-required errors.
    if (val && typeof val === 'object' && !Array.isArray(val) && 'value' in val){
      const inner = val.value;
      out = esc(Array.isArray(inner) ? '[' + inner.join(', ') + ']' : String(inner));
      if (val.severity && val.severity !== 'error')
        sev = `<span class="sev">${esc(val.severity)}</span>`;
      if (val.notice) sev += `<span class="notice">${esc(val.notice)}</span>`;
    } else if (k === 'bounding_box' && val && typeof val === 'object'){
      const r = DATA.regions[val.region] || {};
      const label = (r.label && (r.label[lang] || r.label.es)) || val.region;
      const box = (r.min_lat != null)
        ? ` — lat [${r.min_lat}, ${r.max_lat}], lon [${r.min_lon}, ${r.max_lon}]` : '';
      out = esc(label) + esc(box);
      sev = `<span class="sev">${esc(val.severity || 'warning')}</span>`;
    } else if (Array.isArray(val)) {
      out = esc('[' + val.join(', ') + ']');
    } else {
      out = esc(String(val));
    }
    return `<div><dt>${esc(k)}</dt><dd>${out}${sev}</dd></div>`;
  }).join('');
}

function optionsHtml(groups){
  return groups.map(g =>
    (g.category ? `<p class="optcat">${esc(g.category)}</p>` : '') +
    `<table class="opts">` + g.values.map(v =>
      `<tr><td>${esc(v.value)}</td><td>${esc(v.description)}</td></tr>`).join('') + `</table>`
  ).join('');
}

/* The one-word summary of an annotation. A Schedule annotation always names a
 * component; a Realtime field the operator never types has an origin instead,
 * and that is the more useful thing to show. */
const badgeOf = a => a.component || a.origin || '';

function stateTag(key){
  const s = t(), st = statusOf(key);
  if (!st) return '';
  const cls = {new:'', modified:'mod', removed:'del'}[st];
  const text = {new:s.stNew, modified:s.stMod, removed:s.stDel}[st];
  return `<span class="tag state ${cls}">${esc(text)}</span>`;
}

/* Which screens display this field. The link opens the composites page with
 * that composite expanded, so the two files stay one click apart. */
function usesHtml(f){
  const s = t();
  if (!f.usage || !f.usage.length) return '';
  const seen = [...new Set(f.usage.map(u => u.composite))];
  return `<p class="uses">${esc(s.shownIn)}: ` + seen.map(c =>
    `<a href="composites.html#${encodeURIComponent(c)}">${esc(c)}</a>`).join(', ') + `</p>`;
}

/* The spec column's rows. Each builder decides which facts its reference
 * actually has — Schedule has type and presence, Realtime adds cardinality —
 * and names them by string key so they stay translatable. */
function factRows(f){
  const s = t();
  return (f.facts || []).filter(x => x.v).map(x =>
    `<div><dt>${esc(s[x.k] || x.k)}</dt><dd>${esc(x.v)}</dd></div>`).join('');
}

/* A field whose type is another group — a protobuf message — is a doorway to
 * it. The link retargets the group selector rather than navigating, so the
 * draft and any open form survive the jump. */
function opensHtml(f){
  if (!f.opens || !DATA.tables.some(tb => tb.name === f.opens)) return '';
  return `<p class="uses">${esc(t().opens)}: ` +
    `<a href="#" data-open="${esc(f.opens)}">${esc(f.opens)}</a></p>`;
}

function specColumn(f){
  const s = t();
  return `<div class="col"><h3>${esc(s.spec)}</h3>
    <p class="desc">${esc(f.description)}</p>
    <dl>${factRows(f)}</dl>
    ${opensHtml(f)}
    ${f.conditions.length ? `<p class="optcat">${esc(s.conditions)}</p>
      <ul class="notes">${f.conditions.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>` : ''}
    ${f.notes.length ? `<p class="optcat">${esc(s.notes)}</p>
      <ul class="notes">${f.notes.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>` : ''}
    ${f.options.length ? `<p class="optcat">${esc(s.options)}</p>${optionsHtml(f.options)}` : ''}
    ${usesHtml(f)}
  </div>`;
}

function editorColumn(f){
  const s = t(), a = annotationOf(f.key);
  const i18n = a && (a.i18n[lang] || a.i18n.es || {});
  const dirty = statusOf(f.key) !== null;

  const buttons = `<div class="acts">
    <button class="act primary" data-edit="${esc(f.key)}">${esc(a ? s.edit : s.annotate)}</button>
    ${a ? `<button class="act danger" data-remove="${esc(f.key)}">${esc(s.remove)}</button>` : ''}
    ${dirty ? `<button class="act" data-revert="${esc(f.key)}">${esc(s.revert)}</button>` : ''}
  </div>`;

  // One row per scalar property the annotation schema declares, in its order,
  // so a vocabulary that gains a key gains a row.
  const rows = !a ? '' : FORM.topFields.filter(x => a[x.name]).map(x =>
    `<div><dt>${esc(s[x.name] || x.name)}</dt><dd>${esc(a[x.name])}</dd></div>`).join('');

  const body = a ? `
    ${i18n.help ? `<p class="desc">${esc(i18n.help)}</p>` : ''}
    <dl>
      <div><dt>${esc(s.label)}</dt><dd>${esc(i18n.label || '')}</dd></div>
      ${rows}
    </dl>
    ${Object.keys(a.validation || {}).length
      ? `<p class="optcat">${esc(s.validation)}</p><dl>${validationRows(a.validation)}</dl>` : ''}`
    : `<p class="nomap"><b>${esc(s.nomap)}.</b> ${esc(s.nomapLong)}</p>`;

  return `<div class="col" data-editor="${esc(f.key)}"><h3>${esc(s.editor)}</h3>${body}${buttons}</div>`;
}

function fieldHtml(f){
  const s = t(), a = annotationOf(f.key);
  const open = f.key === editing ? ' open' : '';
  const head = `<summary>
    <span class="fname">${esc(f.name)}</span>
    <span class="tag type">${esc(f.type)}</span>
    ${f.presence ? `<span class="tag req">${esc(f.presence)}</span>` : ''}
    ${a ? `<span class="tag comp">${esc(badgeOf(a))}</span>`
        : `<span class="tag gap">${esc(s.nomap)}</span>`}
    ${f.usage && f.usage.length ? `<span class="tag use">${esc(s.displayed)}</span>` : ''}
    ${stateTag(f.key)}
  </summary>`;

  return `<details class="field" data-key="${esc(f.key)}"${open}>${head}
    <div class="body"><div class="cols">${specColumn(f)}${editorColumn(f)}</div></div></details>`;
}

function renderFields(){
  const s = t();
  const tb = DATA.tables.find(x => x.name === current);
  const q = document.getElementById('search').value.trim().toLowerCase();
  const info = document.getElementById('tinfo');
  const host = document.getElementById('fields');
  if (!tb){ host.innerHTML = ''; info.textContent = ''; return; }

  info.textContent = `${tb.title} · ${tb.total} ${s.fields} · ${tableCounts(tb)} ${s.annotated}`
    + (tb.presence ? ` · ${tb.presence}` : '');

  const shown = tb.fields.filter(f => !q
    || f.name.toLowerCase().includes(q)
    || (f.description || '').toLowerCase().includes(q));

  host.innerHTML = shown.length
    ? shown.map(fieldHtml).join('')
    : `<div class="empty">${esc(s.noresults)}</div>`;

  // Put the live form back where it belongs, without rebuilding it.
  if (editing && formNode){
    const slot = host.querySelector(`[data-editor="${CSS.escape(editing)}"]`);
    if (slot){ slot.innerHTML = `<h3>${esc(s.editor)}</h3>`; slot.appendChild(formNode); }
    else closeForm(false);
  }
  wireFieldButtons(host);
}

function wireFieldButtons(host){
  host.querySelectorAll('[data-edit]').forEach(b =>
    b.onclick = () => openForm(b.dataset.edit));
  host.querySelectorAll('[data-remove]').forEach(b =>
    b.onclick = async () => {
      if (await ask(t().removeAsk)){ setAnnotation(b.dataset.remove, null); renderAll(); }
    });
  host.querySelectorAll('[data-revert]').forEach(b =>
    b.onclick = () => { revert(b.dataset.revert); renderAll(); });
  host.querySelectorAll('[data-open]').forEach(a =>
    a.onclick = e => {
      e.preventDefault();
      if (editing) closeForm(false);
      current = a.dataset.open;
      document.getElementById('search').value = '';
      renderChrome();
      renderFields();
      window.scrollTo({top: 0});
    });
}

function renderAll(){ renderLangs(); renderChrome(); renderFields(); renderDraftBar(); }

/* Deep links. The composites page links a displayed field straight to the
 * field that backs it, so `#stops.stop_lat` has to select the right group and
 * open the right entry — the page is one long list per group, and landing on
 * the top of the wrong group would be no answer at all. */
function openFromHash(){
  const key = decodeURIComponent((location.hash || '').slice(1));
  const entry = INDEX.get(key);
  if (!entry) return false;
  if (editing) closeForm(false);
  current = entry.table.name;
  document.getElementById('search').value = '';
  renderChrome();
  renderFields();
  const node = document.querySelector(`.field[data-key="${CSS.escape(key)}"]`);
  if (node){
    node.open = true;
    node.scrollIntoView({block: 'center'});
  }
  return true;
}
