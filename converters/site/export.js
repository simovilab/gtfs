/* Getting edits back out of the browser.
 *
 * Two routes, because the page has two homes:
 *
 *   GitHub Pages - no server, nothing to write to. The page emits a YAML
 *     *patch* (only the entries that changed) to copy or download. A patch and
 *     not the whole file on purpose: a full-file export would silently drop
 *     every hand-written comment in the annotation file, and those comments
 *     are the record of why a rule is a warning rather than an error.
 *
 *   serve_site.py - a companion endpoint on localhost can write the real file,
 *     comments and all, through ruamel's round-trip loader. The page asks
 *     /api/status at load time and only offers the button if someone answers.
 */

const BARE = /^[a-z][a-z0-9_.]*$/;   // mirrors ui_yaml_io.BARE

function yamlScalar(v){
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return String(v);
  const s = String(v);
  return BARE.test(s) ? s : "'" + s.replace(/'/g, "''") + "'";
}

function yamlLines(value, depth){
  const pad = '  '.repeat(depth), out = [];
  for (const [k, v] of Object.entries(value)){
    if (Array.isArray(v)) out.push(`${pad}${k}: [${v.map(yamlScalar).join(', ')}]`);
    else if (v && typeof v === 'object'){
      out.push(`${pad}${k}:`);
      out.push(...yamlLines(v, depth + 1));
    } else out.push(`${pad}${k}: ${yamlScalar(v)}`);
  }
  return out;
}

/** The changeset as a YAML fragment, entries in spec order. */
function patchYaml(){
  const changed = changedKeys();
  const added = [], removed = [];
  for (const table of DATA.tables)
    for (const f of table.fields){
      if (!changed.includes(f.key)) continue;
      (OVERLAY[f.key] === null ? removed : added).push(f.key);
    }

  const lines = [
    `# Cambios exportados del explorador ${PAGE.feedLabel}.`,
    '# Fragmento, no el archivo completo: pegue las entradas bajo `fields:` en',
    `# ${PAGE.file} y confirme en una rama.`,
    ''
  ];
  if (added.length){
    lines.push('fields:');
    for (const key of added){
      lines.push(`  ${key}:`);
      lines.push(...yamlLines(OVERLAY[key], 2));
    }
  }
  if (removed.length){
    lines.push('', '# Entradas por eliminar de `fields:`:');
    removed.forEach(k => lines.push(`#   ${k}`));
  }
  return lines.join('\n') + '\n';
}

/* ------------------------------------------------------------- dialogues */

/* Native alert() and confirm() block the whole page while open, which stops
 * anything else on it from running. These do the same job out of a <dialog>. */
function ask(message){
  return new Promise(resolve => {
    const s = t(), dlg = document.getElementById('ask');
    dlg.querySelector('.msg').textContent = message;
    const yes = dlg.querySelector('#a-yes'), no = dlg.querySelector('#a-no');
    yes.textContent = s.yes; no.textContent = s.cancel;
    const done = answer => { dlg.close(); resolve(answer); };
    yes.onclick = () => done(true);
    no.onclick = () => done(false);
    dlg.showModal();
  });
}

function notify(message, bad){
  const line = document.getElementById('status');
  if (!line) return;
  line.textContent = message;
  line.className = bad ? 'hint bad' : 'hint';
}

/* -------------------------------------------------------------- draft bar */

function renderDraftBar(){
  const s = t(), bar = document.getElementById('draftbar');
  const n = changedKeys().length;
  bar.hidden = n === 0;
  if (!n) return;
  bar.innerHTML = `<p>${s.draft(n)}</p>
    <button class="act" id="d-view">${esc(s.review)}</button>
    <button class="act" id="d-download">${esc(s.download)}</button>
    ${canWrite ? `<button class="act primary" id="d-write">${esc(s.writeFile)}</button>` : ''}
    <button class="act danger" id="d-discard">${esc(s.discard)}</button>
    <span id="status" class="hint"></span>`;

  document.getElementById('d-view').onclick = showPatch;
  document.getElementById('d-download').onclick = downloadPatch;
  document.getElementById('d-discard').onclick = async () => {
    if (await ask(s.discardAsk)){ discardDraft(); renderAll(); }
  };
  const write = document.getElementById('d-write');
  if (write) write.onclick = writeToFile;
}

function showPatch(){
  const s = t(), dlg = document.getElementById('out');
  dlg.querySelector('h2').textContent = s.patchTitle;
  dlg.querySelector('.help').innerHTML = s.patchHelp;
  dlg.querySelector('textarea').value = patchYaml();
  const copy = dlg.querySelector('#p-copy');
  copy.textContent = s.copy;
  copy.onclick = async () => {
    try { await navigator.clipboard.writeText(patchYaml()); copy.textContent = s.copied; }
    catch (e) { dlg.querySelector('textarea').select(); }
  };
  dlg.querySelector('#p-close').textContent = s.close;
  dlg.querySelector('#p-close').onclick = () => dlg.close();
  dlg.showModal();
}

function downloadPatch(){
  const blob = new Blob([patchYaml()], {type: 'text/yaml;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = PAGE.patchName;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

/* ------------------------------------------------------- local write-back */

async function probeWriteAccess(){
  try {
    const res = await fetch('api/status', {headers: {'Accept': 'application/json'}});
    canWrite = res.ok && (await res.json()).writable === true;
  } catch (e) {
    canWrite = false;   // GitHub Pages: no endpoint, read-only page.
  }
  renderDraftBar();
}

async function writeToFile(){
  const s = t(), button = document.getElementById('d-write');
  button.disabled = true;
  try {
    const res = await fetch(PAGE.endpoint, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({changes: OVERLAY})
    });
    const body = await res.json();
    if (!res.ok) throw new Error((body.errors || [body.error]).join('\n'));
    discardDraft();
    const counts = Object.entries(body.counts).map(([k, v]) => `${k} ${v}`).join(', ');
    notify(s.saved(counts));
    // Reload so the page rebuilds from the file it just wrote: the draft
    // becomes the baseline, and nothing is left marked as pending.
    setTimeout(() => location.reload(), 400);
  } catch (e) {
    notify(s.saveFailed + ': ' + e.message, true);
    button.disabled = false;
  }
}
