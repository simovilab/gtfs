/* Composites page: wording and rendering.
 *
 * Everything is drawn from buildModel(), which merges the authored document
 * with the reader's unsaved draft and re-resolves every reference. So an edit
 * shows up everywhere at once — the wireframe, the counters, the reverse
 * index — without saving first.
 *
 * Three views onto the same file:
 *   Esquema  what a screen is made of, in the order it stacks
 *   Detalle  each prop's fallback chain, with the editor component every
 *            source carries in schedule.ui.yaml
 *   Fuentes  the derived artifacts and the reverse index
 */

const CSTRINGS = {
  es: {
    subtitle: 'Composites de visualización: qué campos GTFS lee cada pantalla',
    stats: s => `${s.composites} composites en ${s.views} vistas · ${s.refs} referencias a campos (${s.schedule} schedule, ${s.realtime} realtime, ${s.derived} derivadas)`,
    coverage: s => `${s.annotated} de ${s.schedule} campos de schedule que se muestran tienen anotación de edición (${s.percent}%). El resto marca la prioridad para anotar.`,
    wire: 'Esquema', detail: 'Detalle', sources: 'Fuentes',
    entity: 'Entidad', cardinality: 'Cardinalidad', one: 'uno', many: 'lista',
    params: 'Parámetros', props: 'Props', key: 'Identidad de fila',
    fallback: 'Cadena de respaldo', nested: 'Composite anidado',
    combined: 'Se usan todas juntas', derivedFrom: 'Derivado de', derived: 'derivado',
    required: 'obligatorio', optional: 'opcional',
    freshness: 'Vigencia', compute: 'Cálculo', note: 'Nota', notes: 'Notas',
    usedBy: 'Usado en', nestedIn: 'Anidado en', unused: 'sin usar',
    noAnnotation: 'sin anotar', missing: 'no existe en la referencia',
    reverse: 'Índice inverso: campo → pantallas', derivedTitle: 'Fuentes derivadas',
    field: 'Campo', usedIn: 'Aparece en',
    andMore: e => `… una fila por cada ${e}`,
    entities: {route:'ruta', trip:'viaje', stop:'parada', agency:'agencia',
               vehicle:'vehículo', alert:'alerta', fare:'tarifa'},
    modeNames: {fallback:'respaldo', all:'todas juntas'},
    footer: 'Generado desde <code>serializers/ui/composites.yaml</code>, resuelto contra <code>schedule.yaml</code>, <code>realtime.yaml</code> y <code>schedule.ui.yaml</code>. Este archivo no forma parte de la especificación GTFS.',
    notSpec: 'Los composites son decisiones de producto de SIMOVI, no parte de GTFS. La especificación no implica ninguna de estas pantallas.',

    edit: 'Editar', duplicate: 'Duplicar', remove: 'Eliminar',
    revert: 'Descartar cambios', save: 'Guardar', cancel: 'Cancelar',
    newComposite: '+ Composite', newView: '+ Vista', newDerived: '+ Fuente derivada',
    identity: 'Identidad', labels: 'Etiquetas', name: 'Nombre interno',
    label: 'Etiqueta', help: 'Ayuda', path: 'Ruta', blocks: 'Bloques',
    builtFrom: 'Construido a partir de', propName: 'nombre', propLabel: 'Etiqueta',
    addParam: '+ Parámetro', addProp: '+ Prop', addSource: '+ Fuente',
    addNote: '+ Nota', addBlock: '+ Bloque',
    stNew: 'nuevo', stMod: 'modificado', stDel: 'eliminado',
    draft: n => `<b>${n}</b> ${n === 1 ? 'entrada modificada' : 'entradas modificadas'} sin guardar, solo en este navegador.`,
    review: 'Ver YAML', download: 'Descargar parche', writeFile: 'Guardar en el archivo',
    discard: 'Descartar todo', discardAsk: '¿Descartar todos los cambios sin guardar?',
    removeAsk: n => `¿Eliminar «${n}»?`, yes: 'Sí, continuar',
    patchTitle: 'Parche para composites.yaml',
    patchHelp: 'Pegue estas entradas en la sección correspondiente de <code>serializers/ui/composites.yaml</code>. Es un fragmento, no el archivo completo, para que no borre los comentarios ya escritos.',
    copy: 'Copiar', copied: 'Copiado', close: 'Cerrar',
    saved: n => `Guardado en composites.yaml (${n}).`,
    saveFailed: 'No se pudo guardar',
    errUnknownRef: 'no existe',
    errName: 'Falta el nombre.',
    errNamePattern: p => `El nombre no cumple el patrón ${p}.`,
    errNameTaken: n => `Ya existe una entrada llamada «${n}».`,
    errLabel: l => `Falta la etiqueta en «${l}», que es obligatoria.`,
    errRefEmpty: w => `«${w}» tiene una fuente vacía.`,
    errRefUnknown: r => `«${r}» no existe en la referencia GTFS.`,
    errPropName: i => `El prop #${i} no tiene nombre.`,
    errPropPattern: n => `«${n}» debe ir en minúsculas con guion bajo.`,
    errPropDup: n => `El prop «${n}» está repetido.`,
    errNestedEmpty: w => `«${w}» no indica qué composite anida.`,
    errNestedSelf: w => `«${w}» se anida a sí mismo.`,
    errNoSources: w => `«${w}» no tiene ninguna fuente.`,
    errModeAll: w => `«${w}» usa «todas juntas» con una sola fuente.`,
    errFreshness: w => `La vigencia de «${w}» debe ser como «90s» o «5m».`,
    errParamName: i => `El parámetro #${i} no tiene nombre.`,
    errPath: 'La ruta debe empezar con «/».',
    errNoBlocks: 'La vista no tiene bloques.',
    errBlockEmpty: 'Hay un bloque sin elegir.',
    errBlockUnknown: b => `El bloque «${b}» no existe.`,
  },
  en: {
    subtitle: 'Display composites: which GTFS fields each screen reads',
    stats: s => `${s.composites} composites across ${s.views} views · ${s.refs} field references (${s.schedule} schedule, ${s.realtime} realtime, ${s.derived} derived)`,
    coverage: s => `${s.annotated} of ${s.schedule} displayed schedule fields have an editor annotation (${s.percent}%). The rest is the annotation priority list.`,
    wire: 'Wireframe', detail: 'Detail', sources: 'Sources',
    entity: 'Entity', cardinality: 'Cardinality', one: 'one', many: 'list',
    params: 'Params', props: 'Props', key: 'Row identity',
    fallback: 'Fallback chain', nested: 'Nested composite',
    combined: 'All used together', derivedFrom: 'Built from', derived: 'derived',
    required: 'required', optional: 'optional',
    freshness: 'Freshness', compute: 'Computed', note: 'Note', notes: 'Notes',
    usedBy: 'Used by', nestedIn: 'Nested in', unused: 'unused',
    noAnnotation: 'not annotated', missing: 'not a field in the reference',
    reverse: 'Reverse index: field → screens', derivedTitle: 'Derived sources',
    field: 'Field', usedIn: 'Appears in',
    andMore: e => `… one row per ${e}`,
    entities: {route:'route', trip:'trip', stop:'stop', agency:'agency',
               vehicle:'vehicle', alert:'alert', fare:'fare'},
    modeNames: {fallback:'fallback', all:'all together'},
    footer: 'Generated from <code>serializers/ui/composites.yaml</code>, resolved against <code>schedule.yaml</code>, <code>realtime.yaml</code> and <code>schedule.ui.yaml</code>. This file is not part of the GTFS specification.',
    notSpec: 'Composites are SIMOVI product decisions, not part of GTFS. The specification implies none of these screens.',

    edit: 'Edit', duplicate: 'Duplicate', remove: 'Delete',
    revert: 'Discard changes', save: 'Save', cancel: 'Cancel',
    newComposite: '+ Composite', newView: '+ View', newDerived: '+ Derived source',
    identity: 'Identity', labels: 'Labels', name: 'Internal name',
    label: 'Label', help: 'Help', path: 'Path', blocks: 'Blocks',
    builtFrom: 'Built from', propName: 'name', propLabel: 'Label',
    addParam: '+ Param', addProp: '+ Prop', addSource: '+ Source',
    addNote: '+ Note', addBlock: '+ Block',
    stNew: 'new', stMod: 'modified', stDel: 'removed',
    draft: n => `<b>${n}</b> unsaved ${n === 1 ? 'entry' : 'entries'}, in this browser only.`,
    review: 'View YAML', download: 'Download patch', writeFile: 'Write to file',
    discard: 'Discard all', discardAsk: 'Discard all unsaved changes?',
    removeAsk: n => `Delete “${n}”?`, yes: 'Yes, continue',
    patchTitle: 'Patch for composites.yaml',
    patchHelp: 'Paste these entries into the matching section of <code>serializers/ui/composites.yaml</code>. It is a fragment, not the whole file, so it cannot wipe the comments already there.',
    copy: 'Copy', copied: 'Copied', close: 'Close',
    saved: n => `Written to composites.yaml (${n}).`,
    saveFailed: 'Could not save',
    errUnknownRef: 'unknown',
    errName: 'The name is missing.',
    errNamePattern: p => `The name does not match ${p}.`,
    errNameTaken: n => `An entry called “${n}” already exists.`,
    errLabel: l => `Missing the label for “${l}”, which is required.`,
    errRefEmpty: w => `“${w}” has an empty source.`,
    errRefUnknown: r => `“${r}” is not a field in the GTFS reference.`,
    errPropName: i => `Prop #${i} has no name.`,
    errPropPattern: n => `“${n}” must be lower case with underscores.`,
    errPropDup: n => `Prop “${n}” appears twice.`,
    errNestedEmpty: w => `“${w}” does not say which composite it nests.`,
    errNestedSelf: w => `“${w}” nests itself.`,
    errNoSources: w => `“${w}” has no sources.`,
    errModeAll: w => `“${w}” uses “all together” with a single source.`,
    errFreshness: w => `Freshness on “${w}” must look like “90s” or “5m”.`,
    errParamName: i => `Param #${i} has no name.`,
    errPath: 'The path must start with “/”.',
    errNoBlocks: 'The view has no blocks.',
    errBlockEmpty: 'A block is left unchosen.',
    errBlockUnknown: b => `Block “${b}” does not exist.`,
  },
  pt: {
    subtitle: 'Composites de exibição: quais campos GTFS cada tela lê',
    stats: s => `${s.composites} composites em ${s.views} telas · ${s.refs} referências a campos (${s.schedule} schedule, ${s.realtime} realtime, ${s.derived} derivadas)`,
    coverage: s => `${s.annotated} de ${s.schedule} campos de schedule exibidos têm anotação de edição (${s.percent}%). O restante é a lista de prioridade.`,
    wire: 'Esquema', detail: 'Detalhe', sources: 'Fontes',
    entity: 'Entidade', cardinality: 'Cardinalidade', one: 'um', many: 'lista',
    params: 'Parâmetros', props: 'Props', key: 'Identidade da linha',
    fallback: 'Cadeia de fallback', nested: 'Composite aninhado',
    combined: 'Usadas em conjunto', derivedFrom: 'Derivado de', derived: 'derivado',
    required: 'obrigatório', optional: 'opcional',
    freshness: 'Validade', compute: 'Cálculo', note: 'Nota', notes: 'Notas',
    usedBy: 'Usado em', nestedIn: 'Aninhado em', unused: 'sem uso',
    noAnnotation: 'sem anotação', missing: 'não existe na referência',
    reverse: 'Índice inverso: campo → telas', derivedTitle: 'Fontes derivadas',
    field: 'Campo', usedIn: 'Aparece em',
    andMore: e => `… uma linha por ${e}`,
    entities: {route:'rota', trip:'viagem', stop:'parada', agency:'agência',
               vehicle:'veículo', alert:'alerta', fare:'tarifa'},
    modeNames: {fallback:'fallback', all:'em conjunto'},
    footer: 'Gerado a partir de <code>serializers/ui/composites.yaml</code>, resolvido contra <code>schedule.yaml</code>, <code>realtime.yaml</code> e <code>schedule.ui.yaml</code>. Este arquivo não faz parte da especificação GTFS.',
    notSpec: 'Composites são decisões de produto da SIMOVI, não parte do GTFS. A especificação não implica nenhuma destas telas.',

    edit: 'Editar', duplicate: 'Duplicar', remove: 'Excluir',
    revert: 'Descartar alterações', save: 'Salvar', cancel: 'Cancelar',
    newComposite: '+ Composite', newView: '+ Tela', newDerived: '+ Fonte derivada',
    identity: 'Identidade', labels: 'Rótulos', name: 'Nome interno',
    label: 'Rótulo', help: 'Ajuda', path: 'Caminho', blocks: 'Blocos',
    builtFrom: 'Construído a partir de', propName: 'nome', propLabel: 'Rótulo',
    addParam: '+ Parâmetro', addProp: '+ Prop', addSource: '+ Fonte',
    addNote: '+ Nota', addBlock: '+ Bloco',
    stNew: 'novo', stMod: 'modificado', stDel: 'removido',
    draft: n => `<b>${n}</b> ${n === 1 ? 'entrada alterada' : 'entradas alteradas'} sem salvar, apenas neste navegador.`,
    review: 'Ver YAML', download: 'Baixar patch', writeFile: 'Gravar no arquivo',
    discard: 'Descartar tudo', discardAsk: 'Descartar todas as alterações não salvas?',
    removeAsk: n => `Excluir “${n}”?`, yes: 'Sim, continuar',
    patchTitle: 'Patch para composites.yaml',
    patchHelp: 'Cole estas entradas na seção correspondente de <code>serializers/ui/composites.yaml</code>. É um fragmento, não o arquivo inteiro, para não apagar os comentários já escritos.',
    copy: 'Copiar', copied: 'Copiado', close: 'Fechar',
    saved: n => `Gravado em composites.yaml (${n}).`,
    saveFailed: 'Não foi possível salvar',
    errUnknownRef: 'não existe',
    errName: 'Falta o nome.',
    errNamePattern: p => `O nome não corresponde a ${p}.`,
    errNameTaken: n => `Já existe uma entrada chamada “${n}”.`,
    errLabel: l => `Falta o rótulo em “${l}”, que é obrigatório.`,
    errRefEmpty: w => `“${w}” tem uma fonte vazia.`,
    errRefUnknown: r => `“${r}” não existe na referência GTFS.`,
    errPropName: i => `O prop #${i} não tem nome.`,
    errPropPattern: n => `“${n}” deve ser minúsculo com sublinhado.`,
    errPropDup: n => `O prop “${n}” está repetido.`,
    errNestedEmpty: w => `“${w}” não indica qual composite aninha.`,
    errNestedSelf: w => `“${w}” aninha a si mesmo.`,
    errNoSources: w => `“${w}” não tem nenhuma fonte.`,
    errModeAll: w => `“${w}” usa “em conjunto” com uma única fonte.`,
    errFreshness: w => `A validade de “${w}” deve ser como “90s” ou “5m”.`,
    errParamName: i => `O parâmetro #${i} não tem nome.`,
    errPath: 'O caminho deve começar com “/”.',
    errNoBlocks: 'A tela não tem blocos.',
    errBlockEmpty: 'Há um bloco não escolhido.',
    errBlockUnknown: b => `O bloco “${b}” não existe.`,
  }
};

const LANG_NAMES = {es:'Español', en:'English', pt:'Português'};

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const t = () => CSTRINGS[lang];
const entityName = entity => (t().entities || {})[entity] || entity;

let MODEL = buildModel();
let currentView = (MODEL.views[0] || {}).name || null;
let mode = 'wire';

const byName = name => MODEL.composites.find(c => c.name === name);

/** Rider-facing label, falling back to Spanish and then to the machine name. */
function labelOf(i18n, fallback){
  const entry = (i18n || {})[lang] || (i18n || {}).es;
  return (entry && entry.label) || fallback || '';
}

function stateTag(section, name){
  const s = t(), st = statusOf(section, name);
  if (!st) return '';
  const cls = {new:'', modified:'mod', removed:'del'}[st];
  return `<span class="tag state ${cls}">${esc({new:s.stNew, modified:s.stMod, removed:s.stDel}[st])}</span>`;
}

function entryActions(section, name){
  const s = t(), dirty = statusOf(section, name) !== null;
  return `<div class="acts">
    <button class="act primary" data-open="${esc(section)}|${esc(name)}">${esc(s.edit)}</button>
    <button class="act" data-dup="${esc(section)}|${esc(name)}">${esc(s.duplicate)}</button>
    <button class="act danger" data-del="${esc(section)}|${esc(name)}">${esc(s.remove)}</button>
    ${dirty ? `<button class="act" data-revert="${esc(section)}|${esc(name)}">${esc(s.revert)}</button>` : ''}
  </div>`;
}

/* ----------------------------------------------------------- wireframe */

/** The placeholder a box shows: the annotated label if the field has one,
 *  otherwise the prop's own label, otherwise its machine name. */
function placeholder(prop){
  const own = labelOf(prop.i18n, '');
  if (own) return {text: own, ph: false};
  const named = (prop.sources || [])
    .map(s => (s.label || {})[lang] || (s.label || {}).es).find(Boolean);
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
  const s = t();
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
      ${stateTag('composites', composite.name)}
    </div>${body}${repeat}
  </div>`;
}

/* -------------------------------------------------------------- detail */

/** The inner cells of one resolved reference. Callers wrap it, because a
 *  reference appears both as a chain step and inside a param row. */
function sourceCells(source){
  const s = t();
  if (!source.exists)
    return `<span class="cref missing">${esc(source.ref)}</span>
      <span class="cmeta">${esc(s.missing)}</span>`;
  if (source.feed === 'derived')
    return `<span class="tag der">${esc(s.derived)}</span>
      <span class="cref">${esc(source.path)}</span>
      <span class="cmeta">${esc((source.label || {})[lang] || (source.label || {}).es || '')}</span>`;
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
  const s = t();
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
    : `<p class="optcat">${esc(combined ? s.combined : s.fallback)}</p>
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
  const s = t();
  const open = editing && editing.section === 'composites' && editing.name === composite.name;
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

  return `<details class="comp"${open ? ' open' : ''} data-name="${esc(composite.name)}">
    <summary>
      <span class="cname">${esc(composite.name)}</span>
      <span class="tag ent">${esc(entityName(composite.entity))}</span>
      <span class="tag card">${esc(composite.cardinality === 'many' ? s.many : s.one)}</span>
      ${where.length ? where.map(w => `<span class="tag used">${w}</span>`).join('')
                     : `<span class="tag gap">${esc(s.unused)}</span>`}
      ${stateTag('composites', composite.name)}
    </summary>
    <div class="body" data-slot="composites|${esc(composite.name)}">
      ${help ? `<p class="desc">${esc(help)}</p>` : ''}
      ${params}${key}
      <p class="optcat">${esc(s.props)}</p>
      ${composite.props.map(propBlock).join('')}
      ${composite.notes.length ? `<p class="optcat">${esc(s.notes)}</p>
        <ul class="notes">${composite.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
      ${entryActions('composites', composite.name)}
    </div>
  </details>`;
}

/* ------------------------------------------------------------- sources */

function derivedDetail(name, artifact){
  const s = t();
  const open = editing && editing.section === 'derived_sources' && editing.name === name;
  const resolved = resolveRef(`derived:${name}`, MODEL.derived);
  return `<details class="comp"${open ? ' open' : ''}>
    <summary>
      <span class="cname">${esc(name)}</span>
      <span class="tag der">${esc(s.derived)}</span>
      <span class="tag used">${esc(labelOf(artifact.i18n, ''))}</span>
      ${stateTag('derived_sources', name)}
    </summary>
    <div class="body" data-slot="derived_sources|${esc(name)}">
      ${artifact.note ? `<p class="desc">${esc(artifact.note)}</p>` : ''}
      <p class="optcat">${esc(s.builtFrom)}</p>
      <ol class="chain single">${(resolved.sources || []).map(sourceRow).join('')}</ol>
      ${entryActions('derived_sources', name)}
    </div>
  </details>`;
}

function reverseTable(){
  const s = t();
  const rows = Object.keys(MODEL.reverse).sort().map(ref => {
    const uses = MODEL.reverse[ref].map(u => `${u.composite}.${u.prop}`).join(', ');
    return `<tr><td>${esc(ref)}</td><td class="usein">${esc(uses)}</td></tr>`;
  }).join('');
  // The refs are monospace and must not wrap mid-path, so the table scrolls
  // inside its own box rather than widening the page on a phone.
  return `<h2 class="viewhead">${esc(s.reverse)}</h2>
    <div class="scrollx"><table class="rev">
      <thead><tr><th>${esc(s.field)}</th><th>${esc(s.usedIn)}</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
}

/* ----------------------------------------------------------- rendering */

/** A view's blocks, followed by every composite they nest.
 *
 * The wireframe draws a nested composite inside its parent, but the detail
 * list would otherwise never show one — a composite only ever nested would
 * have no page of its own.
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
  (view.blocks || []).forEach(walk);
  return out;
}

function renderBody(){
  const s = t();
  const host = document.getElementById('body');
  const view = MODEL.views.find(v => v.name === currentView);

  if (mode === 'sources'){
    host.innerHTML = `<div class="viewhead"><h2>${esc(s.derivedTitle)}</h2>
        <button class="act" data-new="derived_sources">${esc(s.newDerived)}</button></div>
      ${Object.entries(MODEL.derived).map(([n, a]) => derivedDetail(n, a)).join('')
        || `<div class="empty">—</div>`}
      <div style="margin-top:22px">${reverseTable()}</div>`;
    return placeForm(host);
  }

  if (!view){ host.innerHTML = `<div class="empty">—</div>`; return placeForm(host); }

  const head = `<div class="viewhead">
    <h2>${esc(labelOf(view.i18n, view.name))}</h2>
    <span class="vpath">${esc(view.path)}</span>
    ${stateTag('views', view.name)}
    <button class="act" data-open="views|${esc(view.name)}">${esc(s.edit)}</button>
    <button class="act danger" data-del="views|${esc(view.name)}">${esc(s.remove)}</button>
    ${statusOf('views', view.name) ? `<button class="act" data-revert="views|${esc(view.name)}">${esc(s.revert)}</button>` : ''}
  </div>`;

  host.innerHTML = head + (mode === 'wire'
    // The wireframe stacks only the view's own blocks; nested composites are
    // drawn inside their parent, not again at the top level.
    ? `<div class="wire">${(view.blocks || []).map(byName).filter(Boolean)
        .map(b => wireBlock(b, false)).join('')}</div>`
    : blocksOf(view).map(compositeDetail).join(''))
    + `<div style="margin-top:22px">${reverseTable()}</div>`;

  placeForm(host);
}

/** Put the live form where it belongs, without rebuilding it. */
function placeForm(host){
  if (!editing) return;
  if (!formNode){
    formNode = document.createElement('form');
    formNode.className = 'edit';
    formNode.addEventListener('click', onFormClick);
    formNode.addEventListener('input', onFormInput);
    formNode.addEventListener('change', onFormInput);
    renderForm();
  }
  const slot = host.querySelector(`[data-slot="${CSS.escape(editing.section)}|${CSS.escape(editing.name)}"]`);
  if (slot){ slot.innerHTML = ''; slot.appendChild(formNode); }
  else {
    // A new entry, or one whose card is not in the current view: give the form
    // its own panel at the top rather than dropping it.
    const panel = document.createElement('div');
    panel.className = 'formpanel';
    panel.appendChild(formNode);
    host.prepend(panel);
  }
  formNode.scrollIntoView({block: 'nearest', behavior: 'smooth'});
}

function renderChrome(){
  const s = t(), stats = MODEL.stats;
  document.getElementById('subtitle').textContent = s.subtitle;
  document.getElementById('stats').textContent = s.stats(stats);
  document.getElementById('covtext').textContent = s.coverage(stats);
  document.getElementById('covbar').style.width = Math.max(stats.percent, 1.5) + '%';
  document.getElementById('notspec').textContent = s.notSpec;
  document.getElementById('footer').innerHTML = s.footer;

  document.getElementById('langs').innerHTML = MODEL.langs.map(l =>
    `<button data-l="${l}" aria-pressed="${l===lang}">${LANG_NAMES[l]||l}</button>`).join('');
  document.querySelectorAll('#langs button').forEach(b =>
    b.onclick = () => { lang = b.dataset.l; document.documentElement.lang = lang; renderAll(); });

  document.getElementById('view').innerHTML = MODEL.views.map(v =>
    `<option value="${esc(v.name)}"${v.name===currentView?' selected':''}>${esc(labelOf(v.i18n, v.name))} — ${esc(v.path)}</option>`
  ).join('');

  document.querySelectorAll('#modes button').forEach(b => {
    b.textContent = s[b.dataset.m];
    b.setAttribute('aria-pressed', String(b.dataset.m === mode));
  });

  document.getElementById('newbar').innerHTML = `
    <button class="act" data-new="composites">${esc(s.newComposite)}</button>
    <button class="act" data-new="views">${esc(s.newView)}</button>`;
}

function renderAll(){
  MODEL = buildModel();
  if (!MODEL.views.some(v => v.name === currentView))
    currentView = (MODEL.views[0] || {}).name || null;
  renderChrome();
  renderBody();
  renderDraftBar();
}

/* Delegated so the buttons survive every re-render. */
document.addEventListener('click', async event => {
  const el = event.target.closest('[data-open],[data-del],[data-dup],[data-revert],[data-new]');
  if (!el || el.closest('form.edit')) return;
  const split = value => value.split('|');

  if (el.dataset.new) return openNew(el.dataset.new);
  if (el.dataset.open) return openEditor(...split(el.dataset.open));
  if (el.dataset.dup) return duplicateEntry(...split(el.dataset.dup));
  if (el.dataset.revert){
    const [section, name] = split(el.dataset.revert);
    revert(section, name); return renderAll();
  }
  const [section, name] = split(el.dataset.del);
  if (await ask(t().removeAsk(name))) removeEntry(section, name);
});
