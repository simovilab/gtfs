/* Composites page.
 *
 * Read-only for now: composites.yaml is edited by hand and checked by
 * converters/ui/composites.py. The page's job is to make the file legible in
 * the two directions it is useful in —
 *
 *   the wireframe   what a screen is made of, in the order it stacks
 *   the detail      each prop's fallback chain, with the editor component
 *                   each source carries in schedule.ui.yaml
 *
 * plus the reverse index at the bottom: which screens depend on a given field.
 */

const CDATA = JSON.parse(document.getElementById('data').textContent);

const CSTRINGS = {
  es: {
    subtitle: 'Composites de visualización: qué campos GTFS lee cada pantalla',
    stats: s => `${s.composites} composites en ${s.views} vistas · ${s.refs} referencias a campos (${s.schedule} schedule, ${s.realtime} realtime)`,
    coverage: s => `${s.annotated} de ${s.schedule} campos de schedule que se muestran tienen anotación de edición (${s.percent}%). El resto marca la prioridad para anotar.`,
    wire: 'Esquema', detail: 'Detalle', view: 'Vista',
    entity: 'Entidad', cardinality: 'Cardinalidad', one: 'uno', many: 'lista',
    params: 'Parámetros', props: 'Props', key: 'Identidad de fila',
    sources: 'Cadena de respaldo', nested: 'Composite anidado',
    combined: 'Se usan todas juntas', derivedFrom: 'Derivado de', derived: 'derivado',
    required: 'obligatorio', optional: 'opcional',
    freshness: 'Vigencia', compute: 'Cálculo', note: 'Nota',
    usedBy: 'Usado en', nestedIn: 'Anidado en', unused: 'sin usar',
    noAnnotation: 'sin anotar', missing: 'no existe en la referencia',
    reverse: 'Índice inverso: campo → pantallas',
    field: 'Campo', usedIn: 'Aparece en',
    empty: 'Vacío', andMore: e => `… una fila por cada ${e}`,
    entities: {route:'ruta', trip:'viaje', stop:'parada', agency:'agencia',
               vehicle:'vehículo', alert:'alerta', fare:'tarifa'},
    footer: 'Generado desde <code>serializers/ui/composites.yaml</code>, resuelto contra <code>schedule.yaml</code>, <code>realtime.yaml</code> y <code>schedule.ui.yaml</code>. Este archivo no forma parte de la especificación GTFS.',
    notSpec: 'Los composites son decisiones de producto de SIMOVI, no parte de GTFS. La especificación no implica ninguna de estas pantallas.'
  },
  en: {
    subtitle: 'Display composites: which GTFS fields each screen reads',
    stats: s => `${s.composites} composites across ${s.views} views · ${s.refs} field references (${s.schedule} schedule, ${s.realtime} realtime)`,
    coverage: s => `${s.annotated} of ${s.schedule} displayed schedule fields have an editor annotation (${s.percent}%). The rest is the annotation priority list.`,
    wire: 'Wireframe', detail: 'Detail', view: 'View',
    entity: 'Entity', cardinality: 'Cardinality', one: 'one', many: 'list',
    params: 'Params', props: 'Props', key: 'Row identity',
    sources: 'Fallback chain', nested: 'Nested composite',
    combined: 'All used together', derivedFrom: 'Built from', derived: 'derived',
    required: 'required', optional: 'optional',
    freshness: 'Freshness', compute: 'Computed', note: 'Note',
    usedBy: 'Used by', nestedIn: 'Nested in', unused: 'unused',
    noAnnotation: 'not annotated', missing: 'not a field in the reference',
    reverse: 'Reverse index: field → screens',
    field: 'Field', usedIn: 'Appears in',
    empty: 'Empty', andMore: e => `… one row per ${e}`,
    entities: {route:'route', trip:'trip', stop:'stop', agency:'agency',
               vehicle:'vehicle', alert:'alert', fare:'fare'},
    footer: 'Generated from <code>serializers/ui/composites.yaml</code>, resolved against <code>schedule.yaml</code>, <code>realtime.yaml</code> and <code>schedule.ui.yaml</code>. This file is not part of the GTFS specification.',
    notSpec: 'Composites are SIMOVI product decisions, not part of GTFS. The specification implies none of these screens.'
  },
  pt: {
    subtitle: 'Composites de exibição: quais campos GTFS cada tela lê',
    stats: s => `${s.composites} composites em ${s.views} telas · ${s.refs} referências a campos (${s.schedule} schedule, ${s.realtime} realtime)`,
    coverage: s => `${s.annotated} de ${s.schedule} campos de schedule exibidos têm anotação de edição (${s.percent}%). O restante é a lista de prioridade.`,
    wire: 'Esquema', detail: 'Detalhe', view: 'Tela',
    entity: 'Entidade', cardinality: 'Cardinalidade', one: 'um', many: 'lista',
    params: 'Parâmetros', props: 'Props', key: 'Identidade da linha',
    sources: 'Cadeia de fallback', nested: 'Composite aninhado',
    combined: 'Usadas em conjunto', derivedFrom: 'Derivado de', derived: 'derivado',
    required: 'obrigatório', optional: 'opcional',
    freshness: 'Validade', compute: 'Cálculo', note: 'Nota',
    usedBy: 'Usado em', nestedIn: 'Aninhado em', unused: 'sem uso',
    noAnnotation: 'sem anotação', missing: 'não existe na referência',
    reverse: 'Índice inverso: campo → telas',
    field: 'Campo', usedIn: 'Aparece em',
    empty: 'Vazio', andMore: e => `… uma linha por ${e}`,
    entities: {route:'rota', trip:'viagem', stop:'parada', agency:'agência',
               vehicle:'veículo', alert:'alerta', fare:'tarifa'},
    footer: 'Gerado a partir de <code>serializers/ui/composites.yaml</code>, resolvido contra <code>schedule.yaml</code>, <code>realtime.yaml</code> e <code>schedule.ui.yaml</code>. Este arquivo não faz parte da especificação GTFS.',
    notSpec: 'Composites são decisões de produto da SIMOVI, não parte do GTFS. A especificação não implica nenhuma destas telas.'
  }
};

const CLANG_NAMES = {es:'Español', en:'English', pt:'Português'};

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

let lang = 'es';
let currentView = (CDATA.views[0] || {}).name || null;
let mode = 'wire';

const ct = () => CSTRINGS[lang];
const byName = name => CDATA.composites.find(c => c.name === name);

/** The entity name in the reading language; the machine name if unlisted. */
const entityName = entity => (ct().entities || {})[entity] || entity;

/** Rider-facing label, falling back to Spanish and then to the machine name. */
function labelOf(i18n, fallback){
  const entry = (i18n || {})[lang] || (i18n || {}).es;
  return (entry && entry.label) || fallback || '';
}

/* ----------------------------------------------------------- wireframe */

/** The placeholder a box shows: the annotated label if the field has one,
 *  otherwise the prop's own label, otherwise its machine name. */
function placeholder(prop){
  const own = labelOf(prop.i18n, '');
  if (own) return {text: own, ph: false};
  const named = (prop.sources || []).map(s => (s.label || {})[lang] || (s.label || {}).es)
    .find(Boolean);
  return named ? {text: named, ph: false} : {text: prop.name, ph: true};
}

function wireProp(prop){
  if (prop.composite){
    const nested = byName(prop.composite);
    return `<div class="wfprop"><span class="wfslot">${esc(prop.name)}</span></div>`
      + (nested ? wireBlock(nested, true) : '');
  }
  const {text, ph} = placeholder(prop);
  return `<div class="wfprop">
    <span class="wfslot">${esc(prop.name)}</span>
    <span class="wfbox${ph ? ' ph' : ''}">${esc(text)}</span>
  </div>`;
}

function wireBlock(composite, nested){
  const s = ct();
  const body = composite.props.map(wireProp).join('');
  // A list composite is drawn twice, the second faded, because "one row per
  // trip" is a fact about the screen that a single row would hide.
  const repeat = composite.cardinality === 'many'
    ? `<div class="wfrep">${body}</div>
       <p class="wfmore">${esc(s.andMore(entityName(composite.entity)))}</p>` : '';
  return `<div class="wf${nested ? ' nest' : ''}">
    <div class="wfhead">
      <span class="wfname">${esc(composite.name)}</span>
      <span class="wfsub">${esc(labelOf(composite.i18n, composite.name))}</span>
      <span class="tag ent">${esc(entityName(composite.entity))}</span>
      <span class="tag card">${esc(composite.cardinality === 'many' ? s.many : s.one)}</span>
    </div>${body}${repeat}
  </div>`;
}

/* -------------------------------------------------------------- detail */

/** The inner cells of one resolved reference. Callers wrap it, because a
 *  reference appears both as a chain step and inside a param row. */
function sourceCells(source){
  const s = ct();
  if (!source.exists)
    return `<span class="cref missing">${esc(source.ref)}</span>
      <span class="cmeta">${esc(s.missing)}</span>`;
  if (source.feed === 'derived')
    return `<span class="tag der">${esc(s.derived)}</span>
      <span class="cref">${esc(source.path)}</span>
      <span class="cmeta">${esc(labelOf({[lang]: {label: (source.label||{})[lang]}}, '')
        || (source.label || {}).es || '')}</span>`;
  const badge = source.feed === 'realtime'
    ? `<span class="tag rt">realtime</span>` : `<span class="tag sched">schedule</span>`;
  const component = source.feed === 'schedule'
    ? (source.component ? `<span class="tag comp">${esc(source.component)}</span>`
                        : `<span class="tag gap">${esc(s.noAnnotation)}</span>`)
    : '';
  return `${badge}<span class="cref">${esc(source.path)}</span>
    <span class="cmeta">${esc(source.type)}${source.presence ? ' · ' + esc(source.presence) : ''}</span>
    ${component}`;
}

const sourceRow = source => `<li>${sourceCells(source)}</li>`;

function propBlock(prop){
  const s = ct();
  const lines = [
    prop.freshness && `<b>${esc(s.freshness)}:</b> ${esc(prop.freshness)}`,
    prop.compute && `<b>${esc(s.compute)}:</b> ${esc(prop.compute)}`,
    prop.note && `<b>${esc(s.note)}:</b> ${esc(prop.note)}`,
  ].filter(Boolean);

  // `mode: all` is not an ordering, so it must not be drawn as a numbered
  // chain — the numbers would read as a priority that does not exist.
  const combined = prop.mode === 'all';
  const body = prop.composite
    ? `<p class="pnote"><b>${esc(s.nested)}:</b> <code>${esc(prop.composite)}</code></p>`
    : `<p class="optcat">${esc(combined ? s.combined : s.sources)}</p>
       <ol class="chain${combined || prop.sources.length === 1 ? ' single' : ''}">
         ${prop.sources.map(sourceRow).join('')}</ol>`
      + prop.sources.filter(x => (x.sources || []).length).map(x =>
          `<p class="optcat">${esc(s.derivedFrom)} <code>${esc(x.path)}</code></p>
           <ol class="chain single">${x.sources.map(sourceRow).join('')}</ol>`).join('');

  return `<div class="prop">
    <div class="prophead">
      <span class="propname">${esc(prop.name)}</span>
      <span class="proplabel">${esc(labelOf(prop.i18n, ''))}</span>
      <span class="tag ${prop.required ? 'req' : 'used'}">${esc(prop.required ? s.required : s.optional)}</span>
    </div>${body}
    ${lines.map(l => `<p class="pnote">${l}</p>`).join('')}
  </div>`;
}

function compositeDetail(composite){
  const s = ct();
  const help = ((composite.i18n || {})[lang] || (composite.i18n || {}).es || {}).help;

  const params = composite.params.length ? `<p class="optcat">${esc(s.params)}</p>
    <ol class="chain single">${composite.params.map(p =>
      `<li><span class="cref">${esc(p.name)}</span>${sourceCells(p.resolved)}
       <span class="tag ${p.required ? 'req' : 'used'}">${esc(p.required ? s.required : s.optional)}</span></li>`
    ).join('')}</ol>` : '';

  const key = composite.key
    ? `<p class="optcat">${esc(s.key)}</p><ol class="chain single">${sourceRow(composite.key)}</ol>`
    : '';

  const where = [
    ...composite.usedBy.map(v => `${esc(s.usedBy)}: ${esc(v)}`),
    ...composite.nestedIn.map(c => `${esc(s.nestedIn)}: ${esc(c)}`),
  ];

  return `<details class="comp"${composite.name === highlightName ? ' open' : ''}>
    <summary>
      <span class="cname">${esc(composite.name)}</span>
      <span class="tag ent">${esc(entityName(composite.entity))}</span>
      <span class="tag card">${esc(composite.cardinality === 'many' ? s.many : s.one)}</span>
      ${where.length ? where.map(w => `<span class="tag used">${w}</span>`).join('')
                     : `<span class="tag gap">${esc(s.unused)}</span>`}
    </summary>
    <div class="body">
      ${help ? `<p class="desc">${esc(help)}</p>` : ''}
      ${params}${key}
      <p class="optcat">${esc(s.props)}</p>
      ${composite.props.map(propBlock).join('')}
    </div>
  </details>`;
}

/* ------------------------------------------------------------ rendering */

let highlightName = null;

function renderReverse(){
  const s = ct();
  const rows = Object.keys(CDATA.reverse).sort().map(ref => {
    const uses = CDATA.reverse[ref]
      .map(u => `${u.composite}.${u.prop}`).join(', ');
    return `<tr><td>${esc(ref)}</td><td class="usein">${esc(uses)}</td></tr>`;
  }).join('');
  // The refs are monospace and must not wrap mid-path, so the table scrolls
  // inside its own box rather than widening the page on a phone.
  return `<h2 class="viewhead">${esc(s.reverse)}</h2>
    <div class="scrollx"><table class="rev">
      <thead><tr><th>${esc(s.field)}</th><th>${esc(s.usedIn)}</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
}

/** A view's blocks, followed by every composite they nest.
 *
 * The wireframe draws a nested composite inside its parent, but the detail
 * list would otherwise never show one — a composite that is only ever nested,
 * like RouteBadge inside RouteHeader, would have no page of its own.
 */
function blocksOf(view){
  const out = [], seen = new Set();
  const walk = name => {
    const composite = byName(name);
    if (!composite || seen.has(name)) return;
    seen.add(name);
    out.push(composite);
    composite.props.forEach(p => p.composite && walk(p.composite));
  };
  view.blocks.forEach(walk);
  return out;
}

function renderBody(){
  const s = ct();
  const view = CDATA.views.find(v => v.name === currentView);
  const host = document.getElementById('body');
  if (!view){ host.innerHTML = ''; return; }

  const blocks = blocksOf(view);
  const head = `<div class="viewhead">
    <h2>${esc(labelOf(view.i18n, view.name))}</h2>
    <span class="vpath">${esc(view.path)}</span>
  </div>`;

  host.innerHTML = head + (mode === 'wire'
    // The wireframe stacks only the view's own blocks; nested composites are
    // drawn inside their parent, not again at the top level.
    ? `<div class="wire">${view.blocks.map(byName).filter(Boolean)
        .map(b => wireBlock(b, false)).join('')}</div>`
    : blocks.map(compositeDetail).join(''))
    + `<div style="margin-top:22px">${renderReverse()}</div>`;
}

function renderChrome(){
  const s = ct(), stats = CDATA.stats;
  document.getElementById('subtitle').textContent = s.subtitle;
  document.getElementById('stats').textContent = s.stats(stats);
  document.getElementById('covtext').textContent = s.coverage(stats);
  document.getElementById('covbar').style.width = Math.max(stats.percent, 1.5) + '%';
  document.getElementById('notspec').textContent = s.notSpec;
  document.getElementById('footer').innerHTML = s.footer;

  document.getElementById('langs').innerHTML = CDATA.langs.map(l =>
    `<button data-l="${l}" aria-pressed="${l===lang}">${CLANG_NAMES[l]||l}</button>`).join('');
  document.querySelectorAll('#langs button').forEach(b =>
    b.onclick = () => { lang = b.dataset.l; document.documentElement.lang = lang; renderAll(); });

  document.getElementById('view').innerHTML = CDATA.views.map(v =>
    `<option value="${esc(v.name)}"${v.name===currentView?' selected':''}>${esc(labelOf(v.i18n, v.name))} — ${esc(v.path)}</option>`
  ).join('');

  document.querySelectorAll('#modes button').forEach(b => {
    b.textContent = s[b.dataset.m];
    b.setAttribute('aria-pressed', String(b.dataset.m === mode));
  });
}

function renderAll(){ renderChrome(); renderBody(); }

document.getElementById('view').onchange = e => { currentView = e.target.value; renderBody(); };
document.querySelectorAll('#modes button').forEach(b =>
  b.onclick = () => { mode = b.dataset.m; renderAll(); });

// Deep link from the field explorer: composites.html#RouteHeader opens it.
if (location.hash){
  const wanted = decodeURIComponent(location.hash.slice(1));
  const owner = CDATA.composites.find(c => c.name === wanted);
  if (owner){
    highlightName = owner.name;
    mode = 'detail';
    const host = CDATA.views.find(v => blocksOf(v).some(c => c.name === owner.name));
    if (host) currentView = host.name;
  }
}

renderAll();
