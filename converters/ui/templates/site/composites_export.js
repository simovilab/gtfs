/* Getting edits back out of the browser.
 *
 * Two routes, because the page has two homes:
 *
 *   GitHub Pages - no server. The page emits a YAML *patch* (only the entries
 *     that changed) to copy or download. A patch and not the whole file on
 *     purpose: a full-file export would drop every hand-written comment in
 *     composites.yaml, including the ones that say which blocks are still
 *     provisional.
 *
 *   serve_site.py - a companion endpoint on localhost writes the real file
 *     through ruamel's round-trip loader, comments and all. The page asks
 *     api/status at load time and only offers the button if someone answers.
 */

const YAML_BARE = /^[A-Za-z][A-Za-z0-9_.]*$/;
const YAML_REF = /^(schedule|realtime|derived):/;

function yamlScalar(v){
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return String(v);
  const s = String(v);
  return (YAML_REF.test(s) || YAML_BARE.test(s)) ? s : "'" + s.replace(/'/g, "''") + "'";
}

function yamlLines(value, depth){
  const pad = '  '.repeat(depth), out = [];
  if (Array.isArray(value)){
    for (const item of value){
      if (item && typeof item === 'object'){
        const lines = yamlLines(item, depth + 1);
        // First key sits on the dash line, the rest align under it.
        out.push(`${pad}- ${lines[0].trim()}`, ...lines.slice(1));
      } else out.push(`${pad}- ${yamlScalar(item)}`);
    }
    return out;
  }
  for (const [k, v] of Object.entries(value)){
    if (v && typeof v === 'object'){
      out.push(`${pad}${k}:`);
      out.push(...yamlLines(v, depth + 1));
    } else out.push(`${pad}${k}: ${yamlScalar(v)}`);
  }
  return out;
}

/** The changeset as a YAML fragment, grouped by section. */
function patchYaml(){
  const s = t();
  const lines = [
    '# Cambios exportados de la página de composites.',
    '# Fragmento, no el archivo completo: pegue las entradas en la sección que',
    '# corresponde de serializers/ui/composites.yaml y confirme en una rama.',
    ''
  ];
  const removed = [];

  for (const section of SECTIONS){
    const entries = changedKeys()
      .map(splitId).filter(([where]) => where === section);
    const live = entries.filter(([, name]) => OVERLAY[idOf(section, name)] !== null);
    entries.filter(([, name]) => OVERLAY[idOf(section, name)] === null)
      .forEach(([, name]) => removed.push(`${section}: ${name}`));
    if (!live.length) continue;

    lines.push(`${section}:`);
    for (const [, name] of live){
      lines.push(`  ${name}:`);
      lines.push(...yamlLines(OVERLAY[idOf(section, name)], 2));
      lines.push('');
    }
  }
  if (removed.length){
    lines.push('# Entradas por eliminar:');
    removed.forEach(r => lines.push(`#   ${r}`));
  }
  return lines.join('\n').replace(/\n{3,}/g, '\n\n') + '\n';
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
    if (await ask(s.discardAsk)){ discardDraft(); editing = null; renderAll(); }
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
  a.download = 'composites.patch.yaml';
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

/** The overlay regrouped the way the endpoint expects it. */
function changeset(){
  const out = {};
  for (const id of changedKeys()){
    const [section, name] = splitId(id);
    (out[section] ||= {})[name] = OVERLAY[id];
  }
  return out;
}

async function writeToFile(){
  const s = t(), button = document.getElementById('d-write');
  button.disabled = true;
  try {
    const res = await fetch('api/composites', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({changes: changeset()})
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
