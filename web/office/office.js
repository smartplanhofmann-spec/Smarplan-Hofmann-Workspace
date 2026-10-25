/* Smartplan Office online browser client. No providers, persistent credentials or service worker. */
export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = 'ApiError'; this.status = status; }
}
export class StaleSession extends Error { constructor() { super('Sitzung gewechselt'); this.name = 'StaleSession'; } }
export function requestId() { return crypto.randomUUID().replaceAll('-', ''); }
export function formatMoney(value) {
  if (typeof value !== 'string' || !/^-?\d+(\.\d+)?$/.test(value)) return '—';
  const [whole, fraction = ''] = value.split('.');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${fraction.padEnd(2, '0')} €`;
}
export function formatDate(value, time = false) {
  if (!value) return '—';
  const date = new Date(value.length === 10 ? value + 'T12:00:00' : value);
  if (!Number.isFinite(date.getTime())) return '—';
  return new Intl.DateTimeFormat('de-DE', {dateStyle: 'medium', ...(time ? {timeStyle: 'short'} : {})}).format(date);
}
export function duration(seconds) { return Number.isInteger(seconds) ? `${Math.floor(seconds / 3600)}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')} Std.` : '—'; }
export function formatQuantity(value,unit='') {
  if(typeof value!=='string'||! /^-?\d+(\.\d+)?$/.test(value))return '—';
  const [whole,fraction]=value.split('.'),display=whole.replace(/\B(?=(\d{3})+(?!\d))/g,'.')+(fraction!==undefined?','+fraction:'');
  return display+(unit?' '+({m2:'m²',m3:'m³',piece:'Stk.',h:'Std.'}[unit]||unit):'');
}
export function decimalText(value) {
  const result = String(value).trim().replace(',', '.');
  if (!/^-?\d+(\.\d{1,4})?$/.test(result)) throw new Error('Bitte eine Dezimalzahl mit höchstens vier Nachkommastellen eingeben.');
  return result;
}
export function dateInput(date = new Date()) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`; }
export function localDateTime(value) {
  const d = value ? new Date(value) : new Date();
  return `${dateInput(d)}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}
export function collection(value) { return Array.isArray(value) ? value : value?.items || []; }
const DAY_MS=86400000;
function calendarDay(value) {
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))throw new Error('Gültiges Kalenderdatum erwartet.');
  const [year,month,day]=value.split('-').map(Number),date=new Date(Date.UTC(year,month-1,day));
  if(year<1900||year>2200||date.toISOString().slice(0,10)!==value)throw new Error('Gültiges Kalenderdatum zwischen 1900 und 2200 erwartet.');
  return date;
}
const utcDate=date=>date.toISOString().slice(0,10);
export function planningRange(mode,anchor,years=3) {
  const day=calendarDay(anchor),year=day.getUTCFullYear(),month=day.getUTCMonth();let from,to;
  if(mode==='week'){from=new Date(day.getTime()-((day.getUTCDay()+6)%7)*DAY_MS);to=new Date(from.getTime()+6*DAY_MS);}
  else if(mode==='month'){from=new Date(Date.UTC(year,month,1));to=new Date(Date.UTC(year,month+1,0));}
  else if(mode==='year'){from=new Date(Date.UTC(year,0,1));to=new Date(Date.UTC(year,11,31));}
  else if(mode==='multi'&&[2,3].includes(years)&&year+years-1<=2200){from=new Date(Date.UTC(year,0,1));to=new Date(Date.UTC(year+years-1,11,31));}
  else throw new Error('Woche, Monat, Jahr oder zwei bis drei Jahre auswählen.');
  if(from.getUTCFullYear()<1900||to.getUTCFullYear()>2200)throw new Error('Dieser Zeitraum liegt außerhalb der Datumsauswahl 1900 bis 2200.');
  return {from:utcDate(from),to:utcDate(to),days:Math.round((to-from)/DAY_MS)+1};
}
export function shiftPlanningAnchor(mode,anchor,direction,years=3) {
  if(![-1,1].includes(direction))throw new Error('Ungültige Zeitraumnavigation.');
  const day=calendarDay(anchor),year=day.getUTCFullYear(),month=day.getUTCMonth();
  const moved=mode==='week'?new Date(day.getTime()+direction*7*DAY_MS):mode==='month'?new Date(Date.UTC(year,month+direction,1)):
    ['year','multi'].includes(mode)?new Date(Date.UTC(year+direction*(mode==='multi'?years:1),0,1)):null;
  if(!moved)throw new Error('Ungültige Planungsansicht.');
  const value=utcDate(moved);planningRange(mode,value,years);return value;
}
export function timelinePlacement(item,range) {
  try {
    const start=calendarDay(item.start_date),end=calendarDay(item.end_date),first=calendarDay(range.from),last=calendarDay(range.to);
    if(end<start||last<first||end<first||start>last)return null;
    const visibleStart=Math.max(start,first),visibleEnd=Math.min(end,last),days=Math.round((last-first)/DAY_MS)+1;
    return {left:(visibleStart-first)/DAY_MS/days*100,width:((visibleEnd-visibleStart)/DAY_MS+1)/days*100,
      clippedStart:start<first,clippedEnd:end>last};
  } catch{return null;}
}
export function planningTicks(mode,range) {
  const first=calendarDay(range.from),last=calendarDay(range.to),daily=['week','month'].includes(mode),ticks=[];
  for(let day=new Date(first);day<=last;day=daily?new Date(day.getTime()+DAY_MS):new Date(Date.UTC(day.getUTCFullYear(),day.getUTCMonth()+1,1))) {
    const end=daily?new Date(day.getTime()+DAY_MS):new Date(Date.UTC(day.getUTCFullYear(),day.getUTCMonth()+1,1));
    ticks.push({date:utcDate(day),left:(day-first)/DAY_MS/range.days*100,width:Math.min((end-day)/DAY_MS,range.days-(day-first)/DAY_MS)/range.days*100,
      label:new Intl.DateTimeFormat('de-DE',{timeZone:'UTC',...(mode==='week'?{weekday:'short',day:'2-digit'}:mode==='month'?{day:'2-digit'}:{month:'short',year:'numeric'})}).format(day)});
  }
  return ticks;
}

export class OfficeApi {
  #token = ''; #generation = 0; #controllers = new Set(); #pending = new Map();
  constructor({fetcher = globalThis.fetch, base = '/api/v1'} = {}) {
    if (base !== '/api/v1') throw new Error('Nur die eigene Office-API ist erlaubt.');
    this.fetcher = fetcher.bind(globalThis); this.base = base;
  }
  get generation() { return this.#generation; }
  get pendingCount() { return this.#pending.size; }
  pendingOperations() { return [...this.#pending.entries()].map(([key,operation])=>({key,path:operation.path})); }
  retry(key) {
    const operation=this.#pending.get(key);
    if(!operation)throw new ApiError('Vorgang ist nicht mehr offen.');
    return this.mutate(key,operation.path,JSON.parse(operation.fingerprint));
  }
  setToken(token) {
    if (typeof token !== 'string' || token.length < 20 || token.length > 200) throw new Error('Ungültige Sitzung.');
    this.clear(); this.#token = token;
  }
  clear() {
    this.#generation++;
    this.#controllers.forEach(controller => controller.abort());
    this.#controllers.clear(); this.#pending.clear(); this.#token = '';
  }
  async request(path, {method = 'GET', body, publicRequest = false, binary = false, maxBytes = binary ? 21 * 1024 * 1024 : 4 * 1024 * 1024} = {}) {
    if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//') || path.includes('#') || /[\r\n]/.test(path)) throw new Error('Ungültiger API-Pfad.');
    if (!publicRequest && !this.#token) throw new ApiError('Bitte anmelden.', 401);
    const generation = this.#generation, controller = new AbortController();
    this.#controllers.add(controller);
    const headers = {'Accept': binary ? '*/*' : 'application/json'};
    if (!publicRequest) headers.Authorization = 'Bearer ' + this.#token;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    try {
      const response = await this.fetcher(this.base + path, {method, headers, ...(body !== undefined ? {body: JSON.stringify(body)} : {}),
        signal: controller.signal, credentials: 'omit', redirect: 'error', cache: 'no-store', referrerPolicy: 'no-referrer'});
      if (generation !== this.#generation) throw new StaleSession();
      const advertised = Number(response.headers.get('Content-Length'));
      if (Number.isFinite(advertised) && advertised > maxBytes) throw new ApiError('Antwort ist zu groß.', 413);
      const reader = response.body?.getReader();
      let data;
      if (reader) {
        let size = 0; const parts = [];
        for (;;) {
          const {done, value} = await reader.read(); if (done) break;
          if (generation !== this.#generation) { await reader.cancel(); throw new StaleSession(); }
          size += value.byteLength;
          if (size > maxBytes) { await reader.cancel(); throw new ApiError('Antwort ist zu groß.', 413); }
          parts.push(value);
        }
        data = new Uint8Array(size); let offset = 0;
        parts.forEach(part => { data.set(part, offset); offset += part.byteLength; });
      } else {
        data = new Uint8Array(await response.arrayBuffer());
        if (data.byteLength > maxBytes) throw new ApiError('Antwort ist zu groß.', 413);
      }
      if (generation !== this.#generation) throw new StaleSession();
      if (!response.ok) {
        let message = 'Anfrage fehlgeschlagen.';
        try { message = JSON.parse(new TextDecoder().decode(data)).error || message; } catch { /* Do not expose HTML/proxy bodies. */ }
        throw new ApiError(message, response.status);
      }
      if (binary) return new Blob([data], {type: response.headers.get('Content-Type') || 'application/octet-stream'});
      try { return JSON.parse(new TextDecoder().decode(data)); } catch { throw new ApiError('Serverantwort ist nicht lesbar.', 502); }
    } catch (error) {
      if (generation !== this.#generation || error.name === 'AbortError') throw new StaleSession();
      if (error instanceof ApiError || error instanceof StaleSession) throw error;
      throw new ApiError('Keine sichere Antwort erhalten. Verbindung prüfen und dieselbe Eingabe erneut senden.');
    } finally { this.#controllers.delete(controller); }
  }
  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, {method: 'POST', body}); }
  binary(path) { return this.request(path, {binary: true}); }
  async mutate(key, path, data) {
    const fingerprint = JSON.stringify(data), old = this.#pending.get(key);
    if (old && (old.path !== path || old.fingerprint !== fingerprint)) throw new ApiError('Die vorige Antwort ist noch unklar. Bitte zuerst die unveränderte Eingabe erneut senden.');
    const operation = old || {path, fingerprint, body: {...data, request_id: requestId()}};
    this.#pending.set(key, operation);
    try {
      const result = await this.post(path, operation.body);
      this.#pending.delete(key); return result;
    } catch (error) {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) this.#pending.delete(key);
      throw error;
    }
  }
}

const NAV = [
  ['overview','Übersicht','◈'], ['inquiries','Anfragen','↗'], ['projects','Projekte','▦'], ['contacts','Kontakte','◎'],
  ['planning','Einsatzplanung','▤'], ['documents','Dokumente','▧'], ['finance','Finanzen','€'],
  ['material','Material','▣'], ['personnel','Personal','◷'], ['settings','Einstellungen','⚙']
];
const LABELS = {draft:'Entwurf',final:'Festgeschrieben',signed:'Unterzeichnet',new:'Neu',in_progress:'In Arbeit',open:'Offen',
  resolved:'Behoben',accepted:'Abgenommen',needs_review:'Prüfen',queued:'In Warteschlange',running:'Wird verarbeitet',failed:'Fehlgeschlagen',
  ready:'Bereit',uploading:'Upload läuft',planned:'Geplant',completed:'Abgeschlossen',paused:'Pausiert',working:'Läuft',stopped:'Beendet',
  reserved:'Reserviert',partial:'Teilweise entnommen',picked:'Entnommen',pending:'Ausstehend',not_sent:'Nicht versendet',unknown:'Unklar',
  offer:'Angebot',estimate:'Kostenvoranschlag',order_confirmation:'Auftragsbestätigung',invoice:'Rechnung',advance_invoice:'Abschlagsrechnung',
  cumulative_invoice:'Kumulierte Rechnung',final_invoice:'Schlussrechnung',delivery_note:'Lieferschein',credit_note:'Gutschrift',
  receipt:'Zahlungseingang',refund:'Erstattung',material:'Material',labor:'Lohn',service:'Leistung',machine:'Maschine',
  operational:'Operativ',financial:'Finanziell',personnel:'Personal',restricted:'Geschützt'};
const api = new OfficeApi();
const state = {section:'overview', projectId:'', tab:'overview', user:null, projects:[], permissions:new Set(), globalPermissions:new Set(), capabilities:new Set(), features:new Set(), readonly:true, planning:{mode:'week',anchor:dateInput(),years:3}, render:0, urls:new Set(), deviceId:'browser-'+requestId()};
let root, main, shell, banner, modal;
const has = permission => state.permissions.has(permission);
const biz = path => '/business' + path;
const query = (path, values = {}) => path + '?' + new URLSearchParams(Object.entries(values).filter(([,v]) => v !== undefined && v !== null && v !== '')).toString();

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(attributes).forEach(([key,value]) => {
    if (value === undefined || value === null) return;
    if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'class') node.className = value;
    else if (key.startsWith('aria-') || key.startsWith('data-')) node.setAttribute(key, String(value));
    else if (key in node) node[key] = value;
    else node.setAttribute(key, String(value));
  });
  children.flat(Infinity).forEach(child => { if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child))); });
  return node;
}
function button(label, action, kind = '') { return el('button',{type:'button',class:'button '+kind,onClick:action},label); }
function badge(value) { return el('span',{class:'badge '+(['signed','ready','completed','final','accepted'].includes(value)?'success':value==='failed'?'warn':'')},LABELS[value]||value||'—'); }
function notice(message, kind = '') { return el('div',{class:'notice '+kind,role:kind==='error'?'alert':'status'},message); }
function empty(message) { return el('div',{class:'empty'},message); }
function panel(title, ...children) { return el('section',{class:'panel'},title?el('div',{class:'panel-title'},el('h2',{},title)):null,...children); }
function row(title, subtitle, actions = [], detail = null) { return el('div',{class:'list-row'},el('div',{class:'body'},el('h3',{},title),subtitle?el('p',{},subtitle):null,detail?el('p',{class:'detail'},detail):null),el('div',{class:'actions'},actions)); }
function rows(values, render, message = 'Noch keine Einträge vorhanden.') { return values.length ? el('div',{class:'list'},values.map(render)) : empty(message); }
function options(values, label = item => item.name || item.title || item.id) { return values.map(item => [item.id,label(item)]); }
function select(label, values, value, onChange) { return el('label',{class:'field'},label,el('select',{'aria-label':label,value,onChange:event=>onChange(event.target.value)},values.map(([id,name])=>el('option',{value:id,selected:id===value},name)))); }
function revokeUrls() { state.urls.forEach(url=>URL.revokeObjectURL(url)); state.urls.clear(); }
function objectUrl(blob) { const url=URL.createObjectURL(blob); state.urls.add(url); return url; }
function showError(error, target = main) {
  if (error instanceof StaleSession) return;
  if (error.status===401 && state.user) { endSession(); return; }
  target.prepend(notice(error.message||'Vorgang fehlgeschlagen.','error'));updatePending();
}
async function action(function_, target = main) { try { return await function_(); } catch(error) { showError(error,target); } }
function heading(title, description, actions = []) { return el('header',{class:'page-header'},el('div',{},el('p',{class:'eyebrow'},'Smartplan Office'),el('h1',{},title),el('p',{class:'muted'},description)),el('div',{class:'actions'},actions)); }
function field(name,label,type='text',value='',extra={}) { return {name,label,type,value,...extra}; }
function projectField(value=state.projectId) { return field('project_id','Projekt','select',value,{options:[['','Bitte auswählen'],...options(state.projects)],required:true}); }

function form(title, fields, save, {description, submit='Speichern', after=()=>refresh(), key=title, extra, initial={}} = {}) {
  const controls = new Map(), form = el('form',{'data-form':key});
  const error = el('div',{class:'form-error'}), submitButton=el('button',{type:'submit',class:'button primary'},submit);
  const grid=el('div',{class:'form-grid'});
  fields.forEach(spec=> {
    const id='field-'+requestId(); const value=initial[spec.name] ?? spec.value;
    let input;
    if(spec.type==='select'||spec.type==='multi') input=el('select',{id,name:spec.name,multiple:spec.type==='multi',required:!!spec.required},(spec.options||[]).map(([id_,name])=>el('option',{value:id_,selected:Array.isArray(value)?value.includes(id_):id_===value},name)));
    else if(spec.type==='textarea') input=el('textarea',{id,name:spec.name,value:value??'',required:!!spec.required,maxLength:spec.maxLength||10000,rows:spec.rows||3});
    else input=el('input',{id,name:spec.name,type:spec.type==='decimal'?'text':spec.type==='integer'?'number':spec.type,inputMode:spec.type==='decimal'?'decimal':undefined,value:spec.type==='checkbox'?undefined:value??'',checked:spec.type==='checkbox'?!!value:undefined,required:!!spec.required,maxLength:spec.maxLength||2000,step:spec.type==='integer'?1:undefined,min:spec.min,max:spec.max,autoComplete:spec.autoComplete||'off'});
    input.setAttribute('aria-label',spec.label);
    if(spec.help)input.setAttribute('aria-describedby',id+'-help');
    const label=el('label',{class:'field '+(spec.wide||spec.type==='textarea'?'wide ':'')+(spec.type==='checkbox'?'check':''),htmlFor:id},spec.label,input,spec.help?el('small',{id:id+'-help'},spec.help):null);
    grid.append(label); controls.set(spec.name,{input,spec});
  });
  form.append(grid); if(extra) form.append(extra);
  form.append(el('div',{class:'form-actions'},submitButton),error);
  form.addEventListener('submit',async event=> {
    event.preventDefault(); if(submitButton.disabled) return;
    error.replaceChildren(); submitButton.disabled=true;
    try {
      const data={};
      controls.forEach(({input,spec},name)=> {
        let value=spec.type==='checkbox'?input.checked:spec.type==='multi'?Array.from(input.selectedOptions).map(option=>option.value):input.value;
        if(!spec.required&&value===''&&!spec.keepEmpty&&!['text','textarea','email','tel','date'].includes(spec.type)) return;
        if(spec.type==='decimal') value=decimalText(value);
        if(spec.type==='integer') { value=Number(value); if(!Number.isSafeInteger(value)) throw new Error('Ganze Zahl erwartet.'); }
        if(spec.type==='datetime-local') { const date=new Date(value); if(!Number.isFinite(date.getTime())) throw new Error('Gültige Uhrzeit eingeben.'); value=date.toISOString(); }
        data[name]=value;
      });
      const result=await save(data,key);
      if(result!==undefined) { closeModal(); await after(result); }
    } catch(error_) { showError(error_,error); }
    finally { submitButton.disabled=false; }
  });
  const section=panel(title,description?el('p',{class:'muted'},description):null,form);
  section.controls=controls; return section;
}
function dialog(title, content, description = '') {
  closeModal(); const previous=document.activeElement;
  const close=button('×',()=>closeModal(),'icon'); close.className='modal-close'; close.setAttribute('aria-label','Dialog schließen');
  const box=el('section',{class:'modal',role:'dialog','aria-modal':'true','aria-label':title,tabIndex:-1},el('div',{class:'modal-head'},el('div',{},el('h2',{},title),description?el('p',{class:'muted'},description):null),close),content);
  modal=el('div',{class:'modal-backdrop'},box); modal.previous=previous;
  modal.addEventListener('keydown',event=> {
    if(event.key==='Escape') closeModal();
    if(event.key==='Tab') {
      const targets=Array.from(box.querySelectorAll('button,input,select,textarea,a[href]')).filter(node=>!node.disabled);
      if(!targets.length) { event.preventDefault(); box.focus(); return; }
      if(event.shiftKey&&document.activeElement===targets[0]) { event.preventDefault(); targets.at(-1).focus(); }
      else if(!event.shiftKey&&document.activeElement===targets.at(-1)) { event.preventDefault(); targets[0].focus(); }
    }
  });
  document.body.append(modal); box.focus(); return box;
}
function closeModal() { if(modal) { const previous=modal.previous;modal.querySelectorAll('canvas').forEach(canvas=>canvas.disconnect?.());modal.remove();modal=null;previous?.focus(); } }
async function download(path,filename) { const blob=await api.binary(path),url=objectUrl(blob),link=el('a',{href:url,download:filename,rel:'noopener'}); document.body.append(link); link.click(); link.remove(); }
function jsonDownload(value,filename) { const link=el('a',{href:objectUrl(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),download:filename}); document.body.append(link); link.click(); link.remove(); }
function mutation(key,path,data) { return api.mutate(key,biz(path),data); }
function sectionAllowed(section) {
  return ({contacts:has('contacts.read'),planning:has('planning.read'),finance:has('finance.read'),material:has('inventory.read')||has('finance.read'),
    personnel:has('time.own')||has('personnel.read'),settings:has('settings.manage'),inquiries:state.metadata?.can_read_inquiries===true,documents:has('documents.read')||has('finance.read')})[section]??true;
}

function loginScreen(challenge = null, enrollment = null) {
  closeModal(); revokeUrls(); state.user=null; root.replaceChildren();
  const card=el('section',{class:'login-card'},el('div',{class:'brand'},el('span',{class:'brand-mark'},'S'),el('div',{},el('strong',{},'smartplan'),el('small',{},'OFFICE'))),el('h1',{},challenge?'Anmeldung bestätigen':'Willkommen im Büro.'),el('p',{class:'muted'},challenge?'Authentifizierungscode oder Wiederherstellungscode eingeben.':'Projekte, Team und Unterlagen an einem Ort.'));
  if(enrollment) card.append(notice('Diesen Schlüssel einmalig in der eigenen Authenticator-App einrichten. Keine Drittanbieter-QR-Webseite verwenden.'),el('p',{class:'secret'},enrollment.secret));
  const fields=challenge?[field('code','Authentifizierungscode','text','',{required:true,maxLength:100,autoComplete:'one-time-code'})]:[
    field('email','E-Mail','email','',{required:true,autoComplete:'username'}),field('password','Passwort','password','',{required:true,autoComplete:'current-password',maxLength:512})];
  const login=form('',fields,async data=> {
    if(!challenge) {
      const result=await api.request('/login',{method:'POST',body:data,publicRequest:true});
      card.querySelector('input[type=password]').value='';
      if(!result.mfa_required||typeof result.challenge!=='string') throw new ApiError('Der Server hat keine sichere MFA-Anmeldung bestätigt.',502);
      loginScreen(result.challenge,result.enrollment); return undefined;
    }
    const result=await api.request('/login/verify',{method:'POST',body:{challenge,code:data.code},publicRequest:true});
    api.setToken(result.token);
    if(result.recovery_codes?.length) {
      card.replaceChildren(el('h1',{},'Wiederherstellungscodes sichern'),notice('Diese Codes werden nur jetzt angezeigt. Geschützt aufbewahren; jeder Code kann nur einmal verwendet werden.','warn'),
        el('div',{class:'recovery-list'},result.recovery_codes.map(code=>el('span',{},code))),button('Ich habe die Codes gesichert',()=>action(startSession,card),'primary'));
    } else await startSession();
    return undefined;
  },{submit:challenge?'Bestätigen':'Weiter',key:'login',after:()=>{}});
  login.className=''; card.append(login);
  if(challenge) card.append(button('Andere Anmeldung',()=>{api.clear();loginScreen();},'link'));
  card.append(el('p',{class:'login-foot'},'Diese Browseransicht arbeitet online. Zugangsdaten werden nicht im Browserspeicher abgelegt. Für dauerhaft gespeicherte Offlinearbeit die native Smartplan-App verwenden.'));
  root.append(el('main',{id:'main-content',class:'login-shell'},card));
}
async function startSession() {
  const generation=api.generation;
  const [user,caps,projects,metadata]=await Promise.all([api.get('/me'),api.get(biz('/capabilities')),api.get('/projects'),api.get(biz('/overview'))]);
  if(generation!==api.generation) throw new StaleSession();
  state.user=user;state.metadata=metadata;state.permissions=new Set(caps.permissions||[]);state.globalPermissions=new Set(caps.permissions||[]);state.capabilities=new Set(caps.capabilities||[]);state.features=new Set(caps.features||[]);state.readonly=caps.readonly!==false;state.projects=collection(projects);
  if(!state.projects.some(project=>project.id===state.projectId))state.projectId='';
  state.section='overview'; buildShell(); await refresh();
}
function endSession() { api.clear();photoUploads.clear();state.render++;state.projects=[];state.projectId='';state.metadata=null;state.employeeId=null;state.newTimeEntryId=null;state.permissions.clear();state.globalPermissions.clear();state.capabilities.clear();state.features.clear();state.readonly=true;state.planning={mode:'week',anchor:dateInput(),years:3};loginScreen(); }
function buildShell() {
  root.replaceChildren(); shell=el('div',{class:'shell'});
  const nav=el('nav',{class:'navigation','aria-label':'Hauptnavigation'},NAV.filter(([id])=>sectionAllowed(id)).map(([id,label,glyph])=>el('button',{type:'button',class:'nav-button','data-section':id,'aria-current':id===state.section?'page':undefined,onClick:()=>navigate(id)},el('span',{class:'nav-glyph','aria-hidden':'true'},glyph),label)));
  const sidebar=el('aside',{class:'sidebar'},el('div',{class:'brand'},el('span',{class:'brand-mark'},'S'),el('div',{},el('strong',{},'smartplan'),el('small',{},'OFFICE'))),nav,el('div',{class:'sidebar-foot'},'Ihr Betrieb. Ein gemeinsamer Stand.',el('p',{class:'caption'},'Online · Daten vom eigenen Office-Server')));
  const projectSelect=el('select',{class:'project-select','aria-label':'Aktuelles Projekt',onChange:event=>{state.projectId=event.target.value;state.tab='overview';refresh();}},el('option',{value:''},'Alle Projekte'),state.projects.map(project=>el('option',{value:project.id,selected:project.id===state.projectId},project.name)));
  const menu=button('☰',()=>{shell.classList.toggle('menu-open');updateDrawer();},'icon mobile-menu');menu.setAttribute('aria-label','Navigation öffnen');menu.setAttribute('aria-expanded','false');
  const header=el('header',{class:'topbar'},menu,projectSelect,el('div',{class:'identity'},el('span',{},state.user.email||'Angemeldet'),button('Abmelden',()=>action(async()=>{try{await api.post('/logout',{});}finally{endSession();}}),'small')));
  const pending=button('Antworten offen',()=>pendingDialog(),'small');pending.dataset.pendingIndicator='true';pending.hidden=api.pendingCount===0;header.insertBefore(pending,header.lastChild);
  banner=el('div',{});main=el('main',{id:'main-content',class:'content',tabIndex:-1});
  shell.append(sidebar,el('div',{class:'workspace'},header,banner,main));root.append(shell);networkState();updateDrawer();
}
function updateDrawer() {
  if(!shell)return;const sidebar=shell.querySelector('.sidebar'),mobile=matchMedia('(max-width:760px)').matches,open=shell.classList.contains('menu-open');
  if(sidebar){sidebar.inert=mobile&&!open;sidebar.setAttribute('aria-hidden',String(mobile&&!open));}
  shell.querySelector('.mobile-menu')?.setAttribute('aria-expanded',String(mobile&&open));
}
function networkState() { if(!banner)return;banner.replaceChildren(...(navigator.onLine?[]:[notice('Keine Internetverbindung. Browseränderungen werden erst nach bestätigter Serverantwort gespeichert. Dieses Fenster geöffnet lassen.','warn')])); }
function updatePending() { const button_=root?.querySelector('[data-pending-indicator]');if(button_){button_.hidden=api.pendingCount===0;button_.textContent=api.pendingCount+' Antwort'+(api.pendingCount===1?'':'en')+' offen';} }
function operationLabel(path) {
  if(path.endsWith('/finalize'))return 'Beleg festschreiben';
  if(path.endsWith('/sign'))return 'Fassung unterzeichnen';
  if(path.includes('/media'))return 'Foto / Unterlage speichern';
  if(path.includes('/inquiries'))return 'Anfrage bearbeiten';
  if(path.includes('/contacts'))return 'Kontakt speichern';
  if(path.includes('/inventory'))return 'Lagerbuchung bestätigen';
  if(path.includes('/time'))return 'Zeitnachweis speichern';
  return 'Begonnenen Vorgang bestätigen';
}
function pendingDialog() {
  dialog('Unbestätigte Antworten',el('div',{class:'stack'},notice('Der Server kann die Eingabe bereits gespeichert haben. Eine Wiederholung verwendet exakt dieselbe Vorgangskennung und denselben Inhalt. Dieses Fenster bis zur Klärung geöffnet lassen.','warn'),
    rows(api.pendingOperations(),item=>row(operationLabel(item.path),'Unveränderte Eingabe im Arbeitsspeicher',[button('Unverändert erneut senden',()=>action(async()=>{await api.retry(item.key);updatePending();closeModal();await refresh();}),'primary')]))));
}
function navigate(section) { closeModal();state.section=section;shell?.classList.remove('menu-open');updateDrawer();root.querySelectorAll('[data-section]').forEach(node=>{if(node.dataset.section===section)node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');});refresh(); }
async function refresh() {
  if(!state.user)return;
  const version=++state.render,generation=api.generation;revokeUrls();main.replaceChildren(el('div',{class:'loading',role:'status'},'Daten werden geladen …'));
  try {
    const [caps,projects,metadata]=await Promise.all([api.get(biz('/capabilities')),api.get('/projects'),api.get(biz('/overview'))]);
    if(version!==state.render||generation!==api.generation)return;
    const navigationChanged=state.metadata?.can_read_inquiries!==metadata.can_read_inquiries||JSON.stringify(state.projects)!==JSON.stringify(collection(projects));
    state.globalPermissions=new Set(caps.permissions||[]);state.capabilities=new Set(caps.capabilities||[]);state.features=new Set(caps.features||[]);state.readonly=caps.readonly!==false;state.projects=collection(projects);state.metadata=metadata;
    if(state.projectId&&!state.projects.some(project=>project.id===state.projectId)){state.projectId='';state.tab='overview';closeModal();}
    let effective=state.globalPermissions;
    if(state.projectId) {
      const profile=await api.get(biz(`/projects/${state.projectId}/profile`));
      if(version!==state.render||generation!==api.generation)return;
      effective=new Set(profile.permissions||state.globalPermissions);
    }
    if(navigationChanged||[...effective].sort().join('|')!==[...state.permissions].sort().join('|')) {
      state.permissions=new Set(effective);
      if(!sectionAllowed(state.section))state.section='overview';
      buildShell();
    }
    const view=await ({overview:overviewView,inquiries:inquiriesView,projects:projectsView,contacts:contactsView,planning:planningView,documents:documentsView,finance:financeView,material:materialView,personnel:personnelView,settings:settingsView}[state.section]||overviewView)();
    if(version!==state.render||generation!==api.generation)return;
    main.replaceChildren(view);updatePending();main.focus({preventScroll:true});
  } catch(error) { if(version===state.render&&generation===api.generation) {main.replaceChildren();showError(error);main.append(button('Erneut laden',()=>refresh()));} }
}

async function overviewView() {
  const data=await api.get(biz('/overview'));
  const feed=collection(await api.get(query(biz('/feed'),{project_id:state.projectId})));
  const projects=data.projects||[];
  const content=el('div',{class:'stack'},heading('Guten Tag.','Was heute zählt – aus Ihrem gemeinsamen Projektbestand.',[button('Aktualisieren',()=>refresh())]),
    el('div',{class:'grid'},panel('Projekte',el('div',{class:'metric'},data.counters?.projects??projects.length),el('p',{class:'metric-sub'},'Für Ihren Zugang freigegeben')),panel('Arbeitsbereich',el('h2',{},state.projectId?state.projects.find(p=>p.id===state.projectId)?.name:'Alle Projekte'),el('p',{class:'muted'},'Wählen Sie oben ein Projekt für die gemeinsame Projektmappe.'),button('Projekte öffnen',()=>navigate('projects'),'primary'))),
    panel('Zuletzt im Betrieb',rows(feed.slice(0,10),item=>row(item.summary||item.message||item.event_type,formatDate(item.created_at,true),[badge(item.visibility||'operational')]),'Noch keine Projektereignisse vorhanden.')),
    panel('Ihre Projekte',rows(projects.slice(0,8),project=>row(project.name,project.customer,[project.status?badge(project.status.name):null,button('Projekt öffnen',()=>openProject(project.id),'small')]))));
  return content;
}
function openProject(id,tab='overview') { state.projectId=id;state.tab=tab;const projectSelect=root.querySelector('.project-select');if(projectSelect)projectSelect.value=id;navigate('projects'); }
async function projectsView() {
  if(state.projectId)return projectView();
  const data=await api.get(biz('/overview')),projects=data.projects||[],statuses=data.statuses||[];
  const group=[{id:'',name:'Noch ohne Status'},...statuses];
  const headerActions=data.can_create_project&&has('projects.manage')?[button('Neues Projekt',()=>newProjectDialog(),'primary')]:[];
  const board=el('div',{class:'pipeline'},group.filter(status=>!status.id||status.active).map(status=>el('section',{class:'pipeline-column'},el('h3',{},status.name),
    ...projects.filter(project=>(project.status_id||'')===status.id).map(project=>el('button',{type:'button',class:'pipeline-card',onClick:()=>openProject(project.id)},el('strong',{},project.name),el('small',{},project.customer),el('p',{class:'caption'},project.site_address||'Objektadresse noch offen'))))));
  return el('div',{class:'stack'},heading('Projekte','Eine gemeinsame Projektmappe. Frei planbar, ohne starre Reihenfolge.',headerActions),
    projects.length?board:empty('Noch keine freigegebenen Projekte. Ein Projekt kann aus einer geprüften Anfrage oder direkt angelegt werden.'));
}
function newProjectDialog() {
  const content=form('',[field('name','Projektname','text','',{required:true}),field('customer','Kunde / Auftraggeber','text','',{required:true})],data=>api.mutate('new-project','/projects',data),
    {submit:'Projekt anlegen',after:async result=>{state.projects=collection(await api.get('/projects'));buildShell();openProject(result.id||result);}});
  dialog('Neues Projekt',content,'Eine Projektanlage ist noch keine Auftragszusage.');
}
async function projectView() {
  const id=state.projectId,profile=await api.get(biz(`/projects/${id}/profile`));
  const tabs=[['overview','Übersicht'],['tasks','Aufgaben'],['appointments','Termine'],['documents','Dokumente'],['documentation','Fotos & Doku'],['materials','Material'],...(has('finance.read')?[['costs','Kalkulation']]:[]),['maintenance','Wartung'],['logbook','Logbuch']];
  if(!tabs.some(([tab])=>tab===state.tab))state.tab='overview';
  const head=heading(profile.name,`${profile.customer||''}${profile.site_address?' · '+profile.site_address:''}`,[button('Alle Projekte',()=>{state.projectId='';root.querySelector('.project-select').value='';refresh();})]);
  const navigation=el('div',{class:'tabs',role:'tablist','aria-label':'Projektmappe'},tabs.map(([tab,label])=>el('button',{type:'button',class:'tab',role:'tab','aria-selected':tab===state.tab,onClick:()=>{state.tab=tab;refresh();}},label)));
  let body;
  if(state.tab==='overview') {
    const dashboard=await api.get(`/projects/${id}/workspace`);
    body=el('div',{class:'grid two'},panel('Projektstand',el('div',{class:'actions'},profile.status?badge(profile.status.name):badge('Ohne Pipeline-Status')),
      el('p',{class:'muted'},profile.description||'Projektbeschreibung noch offen.'),el('p',{},`Projektnummer: ${profile.project_number||'noch nicht vergeben'}`),has('projects.manage')?button('Projektprofil bearbeiten',()=>projectProfileDialog(profile),'small'):null),
      panel('Nächste Aufgaben',rows(dashboard.open_tasks||[],item=>row(item.title,item.details,[badge(item.status)]),'Keine offenen Aufgaben.')),
      panel('Nächste Termine',rows(dashboard.upcoming_appointments||[],item=>row(item.title,`${formatDate(item.start_at,true)} – ${formatDate(item.end_at,true)}`),'Noch keine Termine geplant.')),
      panel('Projektteam',rows(dashboard.team||[],member=>row(member.email||member.name,member.role),'Noch keine Teammitglieder zugewiesen.')));
  } else if(state.tab==='tasks') body=await tasksPanel(id);
  else if(state.tab==='appointments') body=await planningContent(id);
  else if(state.tab==='documents') body=await documentsContent(id);
  else if(state.tab==='documentation') body=await documentationPanel(id);
  else if(state.tab==='materials') body=await materialContent(id);
  else if(state.tab==='costs') body=await costsPanel(id);
  else if(state.tab==='maintenance') body=await maintenancePanel(id);
  else body=await logbookPanel(id);
  return el('div',{class:'stack'},head,navigation,body);
}
async function projectProfileDialog(profile) {
  const statuses=collection(await api.get(biz('/project-statuses')));
  dialog('Projektprofil',form('',[field('project_number','Projektnummer','text',profile.project_number),field('status_id','Projektstatus','select',profile.status_id||'',{options:[['','Ohne Status'],...options(statuses)],keepEmpty:true}),field('site_address','Objektadresse','textarea',profile.site_address),field('description','Beschreibung','textarea',profile.description)],
    (data,key)=>mutation(key,`/projects/${profile.id}/profile`,{...data,status_id:data.status_id||null,revision:profile.revision,workspace_revision:profile.workspace_revision}),{key:'profile-'+profile.id}));
}
async function tasksPanel(id) {
  const tasks=collection(await api.get(`/projects/${id}/tasks`));
  return panel('Aufgaben',has('documents.write')?button('Aufgabe hinzufügen',()=>dialog('Neue Aufgabe',form('',[
    field('title','Aufgabe','text','',{required:true}),field('due_date','Fällig am','date'),field('priority','Priorität','select','normal',{options:[['normal','Normal'],['high','Hoch'],['low','Niedrig']]}),field('details','Beschreibung','textarea')],
    (data,key)=>api.mutate(key,`/projects/${id}/tasks`,data),{key:'task-'+id})), 'primary'):null,
    rows(tasks,item=>row(item.title,[item.due_date?`Fällig ${formatDate(item.due_date)}`:'',item.details].filter(Boolean).join(' · '),[badge(item.status),has('documents.write')&&item.status!=='done'?button('Erledigt',()=>action(async()=>{await api.mutate('task-done-'+item.id,`/projects/${id}/tasks/${item.id}`,{revision:item.revision,status:'done'});refresh();}),'small'):null])));
}
async function logbookPanel(id) {
  const feed=collection(await api.get(query(biz('/feed'),{project_id:id})));
  return el('div',{class:'stack'},has('documents.write')?form('Notiz im Projekt',[field('text','Nachricht / Notiz','textarea','',{required:true,maxLength:5000})],(data,key)=>mutation(key,'/feed',{...data,project_id:id}),{key:'message-'+id,submit:'Notiz hinzufügen'}):null,
    panel('Projektlogbuch',rows(feed,item=>row(item.summary,formatDate(item.created_at,true),[badge(item.event_type)]),'Noch keine Logbucheinträge.')));
}
async function inquiriesView() {
  const inquiries=collection(await api.get('/inquiries'));
  return el('div',{class:'stack'},heading('Anfragen','Erst prüfen, dann gezielt in Kunde und Projekt übernehmen.',[button('Anfrage erfassen',()=>inquiryDialog(),'primary')]),
    panel('Posteingang',rows(inquiries,item=>row(item.subject,`${item.sender_name||item.sender_email||'Absender offen'} · ${formatDate(item.received_at,true)}`,[badge(item.status),button('Öffnen',()=>action(()=>inquiryDetail(item.id)),'small')],item.message?.slice(0,180)),'Noch keine Anfragen eingegangen.')));
}
function inquiryDialog() {
  dialog('Neue Anfrage',form('',[field('subject','Betreff','text','',{required:true,maxLength:300}),field('source','Kanal','select','manual',{options:[['manual','Telefon / manuell'],['whatsapp','WhatsApp – manuell übernommen']]}),field('sender_name','Name'),field('sender_email','E-Mail','email'),field('sender_phone','Telefon','tel'),field('message','Anfrage','textarea','',{required:true,maxLength:40000})],
    (data,key)=>api.mutate(key,'/inquiries',{...data,source_account:'office-browser'}),{key:'inquiry-create',submit:'Anfrage speichern'}),'WhatsApp-Nachrichten hier manuell erfassen. Es wird kein Messenger abgerufen oder versendet.');
}
async function inquiryDetail(id) {
  const item=await api.get('/inquiries/'+id),files=await api.get('/inquiries/'+id+'/attachments');
  const content=el('div',{class:'stack'},panel('Anfrage',row(item.subject,item.sender_name||item.sender_email,[badge(item.status)]),el('p',{class:'break-word'},item.message)),
    panel('Originalunterlagen',rows(collection(files.files||files),file=>row(file.filename,`${file.media_type} · ${Math.ceil(file.size/1024)} KB`,[file.status==='ready'?button('Original laden',()=>action(()=>download(`/inquiries/${id}/attachments/${file.id}/content`,file.filename)),'small'):badge(file.status)]),'Keine Originalunterlagen vorhanden.')));
  if(item.project_id)content.append(button('Verknüpftes Projekt öffnen',()=>{closeModal();openProject(item.project_id);},'primary'));
  else content.append(button('Geprüft in Projekt übernehmen',()=>action(()=>convertInquiryDialog(item)),'primary'));
  dialog(item.subject,content,'Eine Anfrage bestätigt weder Auftrag noch Termin oder Zahlung.');
}
async function convertInquiryDialog(item) {
  const contacts=collection(await api.get(biz('/contacts')));
  dialog('Anfrage übernehmen',form('',[field('project_name','Projektname','text',item.subject,{required:true}),field('customer_id','Bestehender Kontakt','select','',{options:[['','Neuen Kunden anlegen'],...options(contacts)],keepEmpty:true}),field('customer_name','Name des neuen Kunden','text',item.sender_name||''),field('customer_email','E-Mail des neuen Kunden','email',item.sender_email||'')],
    (data,key)=>api.mutate(key,`/inquiries/${item.id}/convert`,{request_id:undefined,revision:item.revision,project_name:data.project_name,...(data.customer_id?{customer_id:data.customer_id}:{customer:{name:data.customer_name,email:data.customer_email||''}})}),
    {key:'convert-'+item.id,submit:'Kunde & Projekt verknüpfen',after:async result=>{state.projects=collection(await api.get('/projects'));buildShell();openProject(result.project.id);}}),'Die Quelle und Originalunterlagen bleiben mit dem neuen Projekt verknüpft.');
}
async function contactsView() {
  const response=await api.get(biz('/contacts')),contacts=collection(response);
  return el('div',{class:'stack'},heading('Kontakte','Kunden, Lieferanten und Partner mit nachvollziehbaren Projektbezügen.',response.can_create&&has('contacts.write')?[button('Kontakt anlegen',()=>contactDialog(),'primary')]:[]),
    panel('Kontaktkartei',rows(contacts,item=>row(item.name,[item.email,item.phone,item.address].filter(Boolean).join(' · '),[...(item.kinds||[]).map(kind=>badge(({customer:'Kunde',supplier:'Lieferant',partner:'Partner'})[kind])),has('contacts.write')?button('Bearbeiten',()=>action(async()=>contactDialog(await api.get(biz('/contacts/'+item.id)))),'small'):null]))));
}
function contactDialog(contact=null) {
  const fields=[field('name','Name / Firma','text',contact?.name||'',{required:true}),field('entity_type','Kontakttyp','select',contact?.entity_type||'company',{options:[['company','Unternehmen'],['person','Person']]}),field('kinds','Beziehungen','multi',contact?.kinds||['customer'],{options:[['customer','Kunde'],['supplier','Lieferant'],['partner','Partner']],required:true}),field('contact','Ansprechpartner','text',contact?.contact||''),field('email','E-Mail','email',contact?.email||''),field('phone','Telefon','tel',contact?.phone||''),field('address','Adresse','textarea',contact?.address||''),field('notes','Interne Notizen','textarea',contact?.notes||'')];
  dialog(contact?'Kontakt bearbeiten':'Neuer Kontakt',form('',fields,(data,key)=>mutation(key,'/contacts'+(contact?'/'+contact.id:''),{...data,...(contact?{revision:contact.revision}:{})}),{key:'contact-'+(contact?.id||'new')}));
}

async function planningView() { return el('div',{class:'stack'},heading('Einsatzplanung','Ein gemeinsamer Kalender für Projekte, Team und Ressourcen.'),await planningContent(state.projectId)); }
function planningControls(range) {
  const update=async values=>{
    const proposed={...state.planning,...values};
    try{planningRange(proposed.mode,proposed.anchor,proposed.years);}catch(error){await refresh();showError(error);return;}
    state.planning=proposed;await refresh();
  };
  const {mode,anchor,years}=state.planning;
  const picker=mode==='week'?el('label',{class:'field'},'Woche auswählen',el('input',{type:'date',value:anchor,min:'1900-01-01',max:'2200-12-31',onChange:event=>{try{planningRange(mode,event.target.value,years);update({anchor:event.target.value});}catch(error){showError(error);}}})):
    mode==='month'?el('label',{class:'field'},'Monat auswählen',el('input',{type:'month',value:anchor.slice(0,7),min:'1900-01',max:'2200-12',onChange:event=>{try{const value=event.target.value+'-01';planningRange(mode,value,years);update({anchor:value});}catch(error){showError(error);}}})):
      el('label',{class:'field'},mode==='multi'?'Startjahr':'Planungsjahr',el('input',{type:'number',value:Number(anchor.slice(0,4)),min:1900,max:mode==='multi'?2201-years:2200,step:1,onChange:event=>{
        try{if(!/^\d{4}$/.test(event.target.value))throw new Error('Ein gültiges vierstelliges Jahr eingeben.');const value=event.target.value+'-01-01';planningRange(mode,value,years);update({anchor:value});}catch(error){showError(error);}
      }}));
  return el('div',{class:'planning-toolbar'},select('Planungsansicht',[['week','Woche'],['month','Monat'],['year','Jahr'],['multi','Mehrere Jahre']],mode,value=>update({mode:value})),picker,
    mode==='multi'?select('Zeitraum',[['2','2 Jahre'],['3','3 Jahre']],String(years),value=>update({years:Number(value)})):null,
    el('div',{class:'actions period-navigation'},button('Zurück',()=>action(async()=>update({anchor:shiftPlanningAnchor(mode,anchor,-1,years)})),'small'),button('Heute',()=>update({anchor:dateInput()}),'small'),button('Weiter',()=>action(async()=>update({anchor:shiftPlanningAnchor(mode,anchor,1,years)})),'small')),
    el('p',{class:'planning-range',role:'status'},formatDate(range.from)+' – '+formatDate(range.to)));
}
function projectDatesDialog(item) {
  if(item.can_edit!==true||state.readonly)return;
  dialog('Projektzeitraum: '+item.name,form('',[
    field('start_date','Projektbeginn','date',item.start_date||'',{min:'1900-01-01',max:'2200-12-31',help:'Leer lassen, solange der Beginn nicht feststeht.'}),
    field('end_date','Projektende','date',item.end_date||'',{min:'1900-01-01',max:'2200-12-31',help:'Leer lassen, solange das Ende nicht feststeht.'})],(data,key)=>{
      if(data.start_date&&data.end_date&&data.end_date<data.start_date)throw new Error('Das Projektende muss am oder nach dem Beginn liegen.');
      return mutation(key,`/planning/projects/${item.id}/dates`,{revision:item.revision,start_date:data.start_date||null,end_date:data.end_date||null});
    },{key:'project-dates-'+item.id,submit:'Zeitraum speichern'}),'Es werden nur diese Projekttermine geändert. Einzelne Kalendereinsätze behalten ihre eigenen Zeiten.');
}
function projectTimeline(data,range,mode) {
  const items=[...(data.items||[]),...(data.unplanned||[])],ticks=planningTicks(mode,range);
  if(!items.length)return panel('Projektzeiträume',empty('In diesem Zeitraum sind keine freigegebenen Projekte geplant oder ungeplant.'));
  const sheet=el('div',{class:'timeline-sheet'}),grid=el('div',{class:'timeline-gridlines','aria-hidden':'true'});
  sheet.style.minWidth=(220+Math.max(650,ticks.length*(mode==='month'?27:mode==='week'?90:85)))+'px';
  const axis=el('div',{class:'timeline-axis-track'});
  for(const tick of ticks){
    const label=el('span',{class:'timeline-tick'},tick.label);label.style.left=tick.left+'%';label.style.width=tick.width+'%';axis.append(label);
    const line=el('span',{});line.style.left=tick.left+'%';grid.append(line);
  }
  sheet.append(grid,el('div',{class:'timeline-axis'},el('div',{class:'timeline-project-label'},'Projekt'),axis));
  for(const item of items){
    const position=timelinePlacement(item,range),dates=item.start_date&&item.end_date?formatDate(item.start_date)+' – '+formatDate(item.end_date):
      item.start_date?'Beginn '+formatDate(item.start_date)+' · Ende offen':item.end_date?'Beginn offen · Ende '+formatDate(item.end_date):'Beginn und Ende offen';
    const label=el('div',{class:'timeline-project-label'},el('strong',{},item.name),el('small',{},dates),item.status?el('small',{class:'timeline-status'},item.status.name):null,
      item.can_edit===true&&!state.readonly?el('button',{type:'button',class:'button small timeline-edit','aria-label':'Projektzeitraum ändern: '+item.name,onClick:()=>projectDatesDialog(item)},'Zeitraum ändern'):null);
    const track=el('div',{class:'timeline-track'});
    if(position){
      const bar=el('span',{class:'timeline-project-bar'+(position.clippedStart?' clipped-start':'')+(position.clippedEnd?' clipped-end':''),role:'img',
        'aria-label':item.name+': '+dates,'data-start':item.start_date,'data-end':item.end_date,title:item.name+' · '+dates},el('span',{},dates));
      bar.style.left=position.left+'%';bar.style.width=position.width+'%';track.append(bar);
    }else track.append(el('span',{class:'timeline-unplanned'},item.planning_state==='partial'?'Teilweise geplant · '+dates:'Ungeplant · '+dates));
    sheet.append(el('div',{class:'timeline-row','data-project-id':item.id},label,track));
  }
  return panel('Projektzeiträume',el('p',{class:'caption'},'Balken zeigen gespeicherten Projektbeginn und Projektende einschließlich beider Tage. Offene Zeiträume bleiben ungeplant. Die Ansicht lässt sich seitlich scrollen.'),
    el('div',{class:'timeline-scroll',role:'region','aria-label':'Projektzeitleiste '+formatDate(range.from)+' bis '+formatDate(range.to),tabIndex:0},sheet));
}
async function planningContent(projectId='') {
  const enhanced=state.features.has('project_timeline'),mode=enhanced?state.planning.mode:'week',range=planningRange(mode,enhanced?state.planning.anchor:dateInput(),state.planning.years);
  const timeline=enhanced?await api.get(query(biz('/planning/timeline'),{from:range.from,to:range.to,project_id:projectId})):null;
  const controls=enhanced?planningControls(range):null;
  if(!['week','month'].includes(mode))return el('div',{class:'stack'},controls,projectTimeline(timeline,range,mode));
  const [calendar,employees,resources]=await Promise.all([api.get(query(biz('/planning/calendar'),{from:range.from,to:range.to,project_id:projectId})),api.get(query(biz('/employees'),{project_id:projectId})),api.get(biz('/resources'))]);
  const appointments=calendar.appointments||[],days=[];
  for(let index=0;index<range.days;index++) {
    const dayId=utcDate(new Date(calendarDay(range.from).getTime()+index*DAY_MS)),day=new Date(dayId+'T12:00:00');
    const column=el('section',{class:'day','aria-label':formatDate(dayId)},el('h3',{},new Intl.DateTimeFormat('de-DE',{weekday:'short',day:'2-digit',month:'2-digit'}).format(day)));
    appointments.filter(item=>dateInput(new Date(item.start_at))===dayId).forEach(item=> {
      const node=el('button',{type:'button',class:'appointment',draggable:has('planning.write'),onClick:()=>appointmentDialog(item,collection(employees),collection(resources))},
        new Intl.DateTimeFormat('de-DE',{hour:'2-digit',minute:'2-digit'}).format(new Date(item.start_at)),el('strong',{},item.title),el('small',{},item.project_name||state.projects.find(p=>p.id===item.project_id)?.name||'Interner Einsatz'));
      node.addEventListener('dragstart',event=>event.dataTransfer.setData('text/plain',item.id));column.append(node);
    });
    if(has('planning.write')) {
      column.addEventListener('dragover',event=>{event.preventDefault();column.classList.add('drag-over');});column.addEventListener('dragleave',()=>column.classList.remove('drag-over'));
      column.addEventListener('drop',event=> {event.preventDefault();column.classList.remove('drag-over');const item=appointments.find(a=>a.id===event.dataTransfer.getData('text/plain'));if(!item)return;
        action(async()=> {const oldStart=new Date(item.start_at),oldEnd=new Date(item.end_at),moved=new Date(day);moved.setHours(oldStart.getHours(),oldStart.getMinutes(),0,0);
          await mutation('move-'+item.id,`/appointments/${item.id}`,{revision:item.revision,project_id:item.project_id,start_at:moved.toISOString(),end_at:new Date(moved.getTime()+oldEnd.getTime()-oldStart.getTime()).toISOString()});await refresh();});});
    }
    days.push(column);
  }
  const calendarGrid=el('div',{class:'calendar'+(mode==='month'?' calendar-month':'')},days);
  if(mode==='month')days[0].style.gridColumnStart=String((calendarDay(range.from).getUTCDay()+6)%7+1);
  const board=panel(mode==='month'?'Monatskalender':'Wochenkalender',el('div',{class:'actions'},has('planning.write')?button('Termin planen',()=>appointmentDialog(null,collection(employees),collection(resources)),'primary'):null),
    el('p',{class:'caption'},'Kalenderzeiten werden in Ihrer Gerätezeitzone angezeigt. Termine lassen sich auch ohne Ziehen per Formular ändern.'),el('div',{class:'table-scroll'},calendarGrid));
  return el('div',{class:'stack'},controls,board,enhanced?projectTimeline(timeline,range,mode):null,panel('Abwesenheiten & Belegungen',rows(calendar.absences||[],item=>row(item.employee_name||'Abwesenheit',`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`,[badge(item.status||'Geplant')]),'Keine Abwesenheiten für diesen Zeitraum gemeldet.')));
}
function appointmentDialog(item,employees,resources) {
  const begin=new Date();begin.setMinutes(0,0,0);const end=new Date(begin);end.setHours(end.getHours()+1);
  const fields=[projectField(item?.project_id||state.projectId),field('title','Termin','text',item?.title||'',{required:true}),field('start_at','Beginn (Gerätezeit)','datetime-local',localDateTime(item?.start_at||begin),{required:true}),field('end_at','Ende (Gerätezeit)','datetime-local',localDateTime(item?.end_at||end),{required:true}),field('employee_ids','Mitarbeitende','multi',item?.employee_ids||[],{options:options(employees)}),field('resource_ids','Fahrzeuge / Werkzeuge','multi',item?.resource_ids||[],{options:options(resources)}),field('details','Details','textarea',item?.details||'')];
  if(!item)fields.push(field('frequency','Wiederholung','select','',{options:[['','Einmalig'],['daily','Täglich'],['weekly','Wöchentlich'],['monthly','Monatlich']]}),field('count','Anzahl Termine','integer',4,{min:1,max:104}));
  dialog(item?'Termin ändern':'Termin planen',form('',fields,(data,key)=> {const {frequency,count,...values}=data;return mutation(key,'/appointments'+(item?'/'+item.id:''),{...values,timezone:'Europe/Berlin',...(item?{revision:item.revision}:frequency?{recurrence:{frequency,interval:1,count}}:{})});},{key:'appointment-'+(item?.id||'new')}),'Ressourcenüberschneidungen werden serverseitig geprüft. Eine Konfliktmeldung wird nicht automatisch übergangen.');
}

async function documentsView() { return el('div',{class:'stack'},heading('Dokumente','Belege und Berichte bleiben mit ihrem Projekt verknüpft.'),await documentsContent(state.projectId)); }
async function documentsContent(projectId='') {
  const commercial=has('finance.read')?collection(await api.get(query(biz('/documents'),{project_id:projectId}))):[];
  const signed=projectId?collection(await api.get(query(biz('/service-reports'),{project_id:projectId}))):[];
  return el('div',{class:'stack'},has('finance.read')?panel('Angebote & Belege',has('finance.write')?button('Belegentwurf erstellen',()=>documentDialog(null,projectId),'primary'):null,
    rows(commercial,item=>row(item.title||LABELS[item.kind],`${item.number||'Noch ohne Nummer'} · ${formatDate(item.issue_date)} · ${formatMoney(item.totals?.gross)}`,[badge(item.status),button('Öffnen',()=>action(()=>documentDetail(item.id)),'small')]),'Noch keine eigenen kaufmännischen Belege vorhanden.')):notice('Kaufmännische Belege benötigen eine gesonderte Freigabe. Operative Berichte finden Sie im Projekt.'),
    projectId?panel('Serviceberichte',rows(signed,item=>row(item.title,formatDate(item.created_at,true),[badge(item.status),item.status==='signed'?button('PDF',()=>action(()=>download(biz('/service-reports/'+item.id+'/pdf'),'Servicebericht.pdf')),'small'):has('documents.write')?button('Unterzeichnen',()=>signatureDialog(item,'service-reports'),'small'):null]))):empty('Ein Projekt auswählen, um operative Serviceberichte anzuzeigen.'));
}
function positionEditor(initial=[]) {
  const container=el('div',{class:'table-scroll'}),list=el('div',{}),records=[];
  function add(value={}) {
    const controls={};const node=el('div',{class:'row-fields'});
    for(const [name,label,defaultValue]of [['description','Beschreibung',''],['quantity','Menge','1'],['unit','Einheit','Stk.'],['unit_price_net','Netto / Einheit','0.00'],['tax_rate','MwSt. %','19']]) {
      const input=el('input',{value:value[name]??defaultValue,required:true,'aria-label':label,inputMode:['quantity','unit_price_net','tax_rate'].includes(name)?'decimal':undefined,maxLength:name==='description'?10000:100});controls[name]=input;node.append(el('label',{},label,input));
    }
    const kind=el('select',{'aria-label':'Positionsart'},['material','labor','service','machine'].map(type=>el('option',{value:type,selected:type===(value.kind||'service')},LABELS[type])));controls.kind=kind;node.append(el('label',{},'Art',kind));
    const remove=button('×',()=>{node.remove();records.splice(records.indexOf(controls),1);},'small');remove.setAttribute('aria-label','Position entfernen');node.append(remove);records.push(controls);list.append(node);
  }
  initial.forEach(add);if(!initial.length)add();container.append(list,button('Position hinzufügen',()=>add(),'small'));
  container.values=()=>records.map(controls=>({description:controls.description.value,quantity:decimalText(controls.quantity.value),unit:controls.unit.value,unit_price_net:decimalText(controls.unit_price_net.value),tax_rate:decimalText(controls.tax_rate.value),kind:controls.kind.value}));return container;
}
function documentDialog(item=null,projectId='') {
  const editor=positionEditor(item?.positions||[]);
  const fields=[projectField(item?.project_id||projectId||state.projectId),field('kind','Belegart','select',item?.kind||'offer',{options:['estimate','offer','order_confirmation','delivery_note','invoice','advance_invoice','final_invoice'].map(kind=>[kind,LABELS[kind]]),required:true}),field('title','Titel','text',item?.title||'Angebot',{required:true}),field('issue_date','Belegdatum','date',item?.issue_date||dateInput(),{required:true}),field('due_date','Fällig am','date',item?.due_date||dateInput(),{required:true}),field('intro','Einleitung','textarea',item?.intro||''),field('notes','Hinweise','textarea',item?.notes||'')];
  dialog(item?'Belegentwurf bearbeiten':'Neuer Belegentwurf',form('',fields,(data,key)=>mutation(key,'/documents'+(item?'/'+item.id:''),{...data,positions:editor.values(),...(item?{revision:item.revision}:{})}),{key:'document-'+(item?.id||'new'),extra:el('div',{},el('h3',{},'Positionen'),editor),submit:'Entwurf speichern'}),'Preise werden als Dezimalwerte an den Server gesendet. Summen und Steuer berechnet und prüft der Server.');
}
async function documentDetail(id) {
  const item=await api.get(biz('/documents/'+id));
  const controls=[button(item.status==='final'?'Original-PDF':'PDF-Vorschau',()=>action(()=>download(biz(`/documents/${id}/${item.status==='final'?'pdf':'preview'}`),(item.number||item.title)+'.pdf')),'small')];
  if(item.status==='draft'&&has('finance.write'))controls.push(button('Bearbeiten',()=>documentDialog(item),'small'));
  if(item.status==='draft'&&has('finance.issue'))controls.push(button('Festschreiben',()=>confirmDialog('Beleg festschreiben','Die geprüfte Fassung wird unveränderlich archiviert und erhält eine Nummer. Es erfolgt kein automatischer Versand.',async()=>{await mutation('finalize-'+id,`/documents/${id}/finalize`,{revision:item.revision});refresh();}),'primary'));
  const targets=({estimate:['offer','order_confirmation'],offer:['order_confirmation','invoice','advance_invoice','delivery_note'],order_confirmation:['delivery_note','invoice','advance_invoice','final_invoice'],delivery_note:['invoice'],advance_invoice:['final_invoice']})[item.kind]||[];
  if(has('finance.write'))targets.forEach(kind=>controls.push(button('→ '+LABELS[kind],()=>action(async()=>{const result=await mutation('convert-'+id+'-'+kind,`/documents/${id}/convert`,{revision:item.revision,target_kind:kind});closeModal();await documentDetail(result.id);}), 'small')));
  dialog(item.number||item.title,el('div',{class:'stack'},el('div',{class:'actions'},badge(item.status),...controls),panel('Empfänger',el('h3',{},item.buyer?.name),el('p',{class:'muted'},item.buyer?.address_line||'')),
    panel('Positionen',table(['Beschreibung','Menge','Einheit','Netto'],(item.positions||[]).map(line=>[line.description,formatQuantity(line.quantity),line.unit,formatMoney(line.net)]))),panel('Belegsumme',el('p',{},'Netto: '+formatMoney(item.totals?.net)),el('p',{},'Steuer: '+formatMoney(item.totals?.tax)),el('h2',{},'Brutto: '+formatMoney(item.totals?.gross)))));
}
function confirmDialog(title,message,confirm) {
  const error=el('div',{}),submit=button('Verbindlich bestätigen',()=>action(async()=>{submit.disabled=true;try{await confirm();closeModal();}finally{submit.disabled=false;}},error),'primary');
  dialog(title,el('div',{},el('p',{},message),el('div',{class:'actions'},button('Abbrechen',()=>closeModal()),submit),error));
}
function table(headers,body) { return el('div',{class:'table-scroll'},el('table',{},el('thead',{},el('tr',{},headers.map(header=>el('th',{},header)))),el('tbody',{},body.map(values=>el('tr',{},values.map(value=>el('td',{},value))))))); }
async function financeView() {
  const [open,payments,outbox]=await Promise.all([api.get(query(biz('/finance/open-items'),{project_id:state.projectId})),api.get(biz('/finance/payments')),api.get(biz('/finance/outbox'))]);
  const invoices=collection(open);
  return el('div',{class:'stack'},heading('Finanzen','Bestätigte Zahlungen und offene Posten. Ein Freigabeschritt ersetzt keinen Versandnachweis.',has('finance.write')?[button('Zahlung erfassen',()=>paymentDialog(invoices),'primary')]:[]),
    panel('Offene Posten',rows(invoices,item=>row(`${item.number||item.id} · ${item.buyer?.name||''}`,`Fällig ${formatDate(item.due_date)} · Offen ${formatMoney(item.open)} · Bezahlt ${formatMoney(item.paid)}`,[badge(item.dunning_status||item.status||'open')]),'Keine offenen Posten vorhanden.')),
    panel('Zahlungseingänge',rows(collection(payments),item=>row(formatMoney(item.amount),`${formatDate(item.booking_date)} · ${item.reference||item.source_id}`,[badge(item.kind)]))),
    panel('Versandaufträge',rows(collection(outbox),item=>row(item.recipient||'Empfänger offen',`Mahnlevel ${item.level} · ${formatDate(item.created_at,true)}`,[badge(item.status)]),'Keine freigegebenen Versandaufträge vorhanden.')),
    has('finance.approve')?form('Mahnlauf prüfen',[],async(data,key)=>{const result=await mutation(key,'/finance/dunning/preview',{...data,...(state.projectId?{project_id:state.projectId}:{})});dunningDialog(collection(result));return undefined;},{key:'dunning-preview',submit:'Vorschläge für heute berechnen',description:'Der heutige Serverstichtag gilt. Der Vorschlag löst keine Nachricht und keine Mahnstufenfortschreibung aus.'}):null);
}
function paymentDialog(invoices) {
  dialog('Zahlungseingang erfassen',form('',[field('document_id','Rechnung','select','',{options:[['','Noch nicht zuordnen'],...invoices.map(item=>[item.id,`${item.number||item.id} · ${formatMoney(item.open)}`])]}),field('amount','Betrag EUR','decimal','',{required:true}),field('source_id','Eindeutige Buchungsreferenz','text','',{required:true,help:'Zum Beispiel die unveränderte Referenz des Kontoauszugs.'}),field('booking_date','Buchungsdatum','date',dateInput(),{required:true}),field('reference','Verwendungszweck','text')],(data,key)=>{const {document_id,...values}=data;const amount=decimalText(values.amount);const cents=amount.includes('.')?amount.padEnd(amount.indexOf('.')+3,'0'):amount+'.00';return mutation(key,'/finance/payments',{...values,amount:cents,kind:'receipt',currency:'EUR',allocations:document_id?[{document_id,amount:cents}]:[]});},{key:'payment-new'}),'Nur einen tatsächlich bestätigten Zahlungseingang buchen.');
}
function dunningDialog(items) {
  dialog('Mahnvorschläge',rows(items,item=>row(item.number||item.document_id,`${item.buyer?.name||''} · Offen ${formatMoney(item.open)} · Stufe ${item.level}`,[button('Freigeben',()=>confirmDialog('Mahnung freigeben','Empfänger, Betrag und Text prüfen. Ein Auftrag wird zur Zustellung vorbereitet; diese Ansicht behauptet keine versendete Nachricht.',async()=>{await mutation('dunning-approve-'+item.id,`/finance/dunning/proposals/${item.id}/approve`,{confirmation:true});refresh();}),'small')]),'Aktuell gibt es keine geeigneten Mahnvorschläge.'));
}

async function materialView() { return el('div',{class:'stack'},heading('Material','Artikel, Bestände und nachvollziehbare Entnahmen.'),await materialContent(state.projectId)); }
async function materialContent(projectId='') {
  const [locations,stock]=await Promise.all([api.get(biz('/inventory/locations')),api.get(biz('/inventory/stock'))]);
  const articles=has('finance.read')?collection(await api.get(biz('/articles'))):[];
  const reserved=projectId?collection(await api.get(query(biz('/inventory/reservations'),{project_id:projectId}))):[];
  const controls=[];
  if(has('inventory.write'))controls.push(button('Lagerort anlegen',()=>dialog('Lagerort',form('',[field('name','Name','text','',{required:true})],(data,key)=>mutation(key,'/inventory/locations',data),{key:'location-new'})),'small'),
    button('Bewegung buchen',()=>stockMovementDialog(collection(locations),articles,projectId),'primary'));
  if(has('finance.write'))controls.push(button('Artikel / Leistung anlegen',()=>articleDialog(),'small'));
  const content=el('div',{class:'stack'},panel('Lagerbestand',el('div',{class:'actions'},controls),table(['Lagerort','Artikel','Bestand','Reserviert','Verfügbar',...(has('finance.read')?['Wert netto']:[])],collection(stock).map(item=>[
    collection(locations).find(location=>location.id===item.location_id)?.name||'Lagerort',item.article_name||articles.find(article=>article.id===item.article_id)?.name||item.article_code||'Artikel',formatQuantity(item.on_hand,item.unit),formatQuantity(item.reserved),formatQuantity(item.available),...(has('finance.read')?[formatMoney(item.stock_value_net)]:[])]))),
    form('Artikel per Code finden',[field('code','Artikelnummer / Barcode','text','',{required:true})],async data=>{const found=await api.get(query(biz('/inventory/scan'),{code:data.code}));dialog('Artikel gefunden',panel(found.name,el('p',{},`${found.code} · ${found.unit}`),found.cost_price_net?el('p',{},'EK netto: '+formatMoney(found.cost_price_net)):null));return undefined;},{submit:'Suchen',key:'scan',description:'Die Suche liest nur Stammdaten. Sie löst keine Entnahme aus.'}));
  if(projectId)content.append(panel('Kommissionierung',has('inventory.write')?button('Material reservieren',()=>reservationDialog(projectId,collection(locations),articles),'small'):null,
    rows(reserved,item=>row(item.article_snapshot?.name||item.article_id,`Reserviert ${formatQuantity(item.quantity)} · Entnommen ${formatQuantity(item.picked_quantity)} · Rest ${formatQuantity(item.remaining_quantity)}`,[badge(item.status),has('inventory.write')&&['reserved','partial'].includes(item.status)?button('Entnehmen',()=>dialog('Material entnehmen',form('',[field('quantity','Entnahmemenge','decimal',item.remaining_quantity,{required:true})],(data,key)=>mutation(key,'/inventory/pick',{project_id:projectId,items:[{reservation_id:item.id,quantity:data.quantity}]}),{key:'pick-'+item.id,submit:'Entnahme verbindlich buchen'})),'small'):null]))));
  if(has('finance.read'))content.append(panel('Artikel & Leistungen',rows(articles,item=>row(item.name,`${item.code||'Ohne Artikelnummer'} · ${item.unit} · VK ${formatMoney(item.unit_price_net)} · EK ${formatMoney(item.cost_price_net)}`,[badge(item.kind),has('finance.write')?button('Bearbeiten',()=>articleDialog(item),'small'):null]))));
  return content;
}
function articleDialog(item=null) {
  dialog(item?'Artikel bearbeiten':'Artikel / Leistung',form('',[field('code','Artikelnummer','text',item?.code||''),field('name','Bezeichnung','text',item?.name||'',{required:true}),field('kind','Art','select',item?.kind||'material',{options:['material','labor','service','machine'].map(kind=>[kind,LABELS[kind]])}),field('unit','Einheit','text',item?.unit||'Stk.',{required:true}),field('unit_price_net','Verkauf netto EUR','decimal',item?.unit_price_net||'0.00',{required:true}),field('cost_price_net','Einstand netto EUR','decimal',item?.cost_price_net||'0.00',{required:true}),field('tax_rate','MwSt. %','select',item?.tax_rate||'19',{options:[['19','19 %'],['7','7 %'],['0','0 %']]}),field('active','Aktiv','checkbox',item?.active??true)],
    (data,key)=>mutation(key,'/articles'+(item?'/'+item.id:''),{...data,currency:'EUR',tax_category:data.tax_rate==='0'?'Z':'S',...(item?{revision:item.revision}:{})}),{key:'article-'+(item?.id||'new')}));
}
function stockMovementDialog(locations,articles,projectId) {
  const fields=[field('kind','Bewegung','select','receive',{options:[['receive','Zugang'],['issue','Entnahme'],['transfer','Umbuchung']]}),field('article_id','Artikel','select','',{options:options(articles),required:true}),field('quantity','Menge','decimal','1',{required:true}),...(has('finance.write')?[field('unit_cost_net','Bestätigter Einstand netto EUR / Einheit','decimal','',{help:'Optional für Zugang. Ein tatsächlicher Nullpreis muss ausdrücklich als 0 eingegeben werden.'})]:[]),field('from_location_id','Quelllager','select','',{options:[['','Kein Quelllager'],...options(locations)]}),field('to_location_id','Ziellager','select','',{options:[['','Kein Ziellager'],...options(locations)]}),field('project_id','Projekt für Entnahme','select',projectId,{options:[['','Kein Projekt'],...options(state.projects)]}),field('note','Buchungsnotiz','textarea')];
  dialog('Lagerbewegung',form('',fields,(data,key)=>{if(data.kind!=='receive')delete data.unit_cost_net;return mutation(key,'/inventory/movements',data);},{key:'stock-move',submit:'Bewegung buchen'}),'Zugang: nur Ziellager. Entnahme: nur Quelllager und Projekt. Umbuchung: Quell- und Ziellager. Historische Einstandskosten entstehen aus dem Journal.');
}
function reservationDialog(projectId,locations,articles) {
  dialog('Material reservieren',form('',[field('article_id','Artikel','select','',{options:options(articles),required:true}),field('location_id','Lagerort','select','',{options:options(locations),required:true}),field('quantity','Menge','decimal','1',{required:true})],
    (data,key)=>mutation(key,'/inventory/reservations',{...data,project_id:projectId}),{key:'reserve-'+projectId}),'Reservierungen werden gegen den freien Bestand geprüft.');
}
async function costsPanel(projectId) {
  const [costs,changes]=await Promise.all([api.get(biz(`/projects/${projectId}/costs`)),api.get(biz(`/projects/${projectId}/changes`))]);
  return el('div',{class:'stack'},costs.costs_complete===false?notice(`Die Istkosten sind unvollständig: ${costs.missing_rates_count} genehmigte Zeitnachweise haben keinen bestätigten Kostensatz. Die bekannte Teilsumme ist kein vollständiger Gewinn- oder Budgetnachweis.`,'warn'):null,
    el('div',{class:'grid'},panel('Gespeichertes Budget',el('div',{class:'metric'},formatMoney(costs.budget_net)),el('p',{class:'metric-sub'},'Baseline · Revision '+costs.budget_revision)),
    panel(costs.costs_complete===false?'Bekannte Istkosten':'Gebuchte Istkosten',el('div',{class:'metric'},formatMoney(costs.actual_net)),el('p',{class:'metric-sub'},'Materialbewegungen + genehmigte Zeiten')),panel('Verfügbares Budget',el('div',{class:'metric'},formatMoney(costs.remaining_net)),el('p',{class:'metric-sub'},'Inklusive freigegebener Nachträge'))),
    panel('Nachweis',el('p',{},'Material netto: '+formatMoney(costs.material_actual_net)),el('p',{},'Genehmigte Zeitkosten: '+formatMoney(costs.labor_actual_net)),el('p',{class:'caption'},'Zeitkosten verwenden den historischen Satz des Zeiteintrags. Unbestätigte Zeiten und manuelle Terminlängen zählen nicht als Istkosten.'),
      table(['Arbeitstag','Genehmigte Dauer','Kosten netto'],costs.approved_times.map(item=>[formatDate(item.work_date),duration(item.net_seconds),formatMoney((item.cost_minor/100).toFixed(2))]))),
    panel('Nachträge',rows(collection(changes),item=>row(item.title,formatMoney(item.amount_net),[badge(item.approved?'Freigegeben':'Vorschlag'),!item.approved&&has('finance.approve')?button('Nachtrag freigeben',()=>confirmDialog('Nachtrag freigeben','Dieser Vorschlag erhöht das Projektbudget um '+formatMoney(item.amount_net)+'. Die ursprüngliche Fassung bleibt nachvollziehbar. Es wird keine Nachricht versendet.',async()=>{await mutation('approve-change-'+item.id,`/projects/${projectId}/changes/${item.id}/approve`,{revision:item.revision});refresh();}),'small'):null]))),
    has('finance.write')?form('Budget festlegen',[field('material_net','Material netto EUR','decimal','0.00',{required:true}),field('labor_net','Lohn netto EUR','decimal','0.00',{required:true}),field('machine_net','Maschinen netto EUR','decimal','0.00',{required:true}),field('other_net','Sonstige Kosten netto EUR','decimal','0.00',{required:true})],(data,key)=>mutation(key,'/budgets',{...data,project_id:projectId,...(costs.budget_revision?{revision:costs.budget_revision}:{})}),{key:'budget-'+projectId,submit:'Neue Budgetfassung speichern'}):null,
    has('finance.write')?form('Nachtrag erfassen',[field('title','Nachtrag','text','',{required:true}),field('amount_net','Zusätzlicher Budgetbetrag netto EUR','decimal','',{required:true}),...(has('finance.approve')?[field('approved','Nachtrag ausdrücklich freigeben','checkbox',false)]:[])],(data,key)=>mutation(key,`/projects/${projectId}/changes`,data),{key:'change-'+projectId}):null);
}

async function documentationPanel(projectId) {
  const [media,diary,defects,measurements,checklists,runs]=await Promise.all(['media','diary','defects','measurements','checklists','checklist-runs'].map(resource=>api.get(query(biz('/'+resource),{project_id:projectId}))));
  const allMedia=collection(media).slice().reverse(),page=Math.min(state.galleryPage||0,Math.max(0,Math.ceil(allMedia.length/12)-1));
  state.galleryPage=page;
  const shownMedia=allMedia.slice(page*12,page*12+12);
  const gallery=el('div',{class:'gallery'});
  for(const item of shownMedia) {
    const card=el('article',{class:'photo-card'});
    if(item.status==='ready'&&item.media_type.startsWith('image/')) {
      try {
        const blob=await api.binary(biz(`/media/${item.id}/content`));const thumbnail=await photoThumbnail(blob);
        card.append(el('img',{src:objectUrl(thumbnail),alt:item.caption||item.filename,loading:'lazy'}));
      }catch(error){
        if(error instanceof StaleSession||[401,403,404].includes(error.status))throw error;
        card.append(notice('Galerievorschau nicht verfügbar. Das Original separat prüfen.','warn'));
      }
    }
    card.append(el('div',{class:'photo-info'},el('h3',{},item.caption||item.filename),el('p',{},formatDate(item.captured_at||item.created_at,true)),el('div',{class:'actions'},badge(item.status),
      item.status==='ready'?button('Original',()=>action(()=>download(biz(`/media/${item.id}/content`),item.filename)),'small'):null,
      item.status==='ready'&&item.media_type.startsWith('image/')&&has('documents.write')?button('Markieren',()=>action(()=>annotateDialog(item)),'small'):null)));gallery.append(card);
  }
  const previous=button('Vorherige Fotos',()=>{state.galleryPage=page-1;refresh();},'small');previous.disabled=page===0;
  const next=button('Weitere Fotos',()=>{state.galleryPage=page+1;refresh();},'small');next.disabled=(page+1)*12>=allMedia.length;
  const content=el('div',{class:'stack'},panel('Fotos & Originalunterlagen',has('documents.write')?button('Foto aufnehmen / hochladen',()=>photoDialog(projectId),'primary'):null,
    el('p',{class:'caption'},'Verkleinerte Galerievorschauen · Die unveränderten Originale bleiben separat abrufbar.'),allMedia.length?gallery:empty('Noch keine Baustellenfotos vorhanden.'),
    allMedia.length>12?el('div',{class:'actions'},previous,el('span',{class:'caption'},`Seite ${page+1} von ${Math.ceil(allMedia.length/12)}`),next):null),
    panel('Bautagebuch',has('documents.write')?button('Tagesbericht hinzufügen',()=>diaryDialog(projectId),'small'):null,rows(collection(diary),item=>row(item.title,`${formatDate(item.entry_date)} · ${item.crew_count} Personen · ${item.imported_net_seconds?duration(item.imported_net_seconds):'Keine übernommenen Zeiten'}`,[badge(item.status)],item.work))),
    panel('Mängel',has('documents.write')?button('Mangel aufnehmen',()=>defectDialog(projectId),'small'):null,rows(collection(defects),item=>row(item.title,`${item.location||''}${item.due_date?' · Frist '+formatDate(item.due_date):''}`,[badge(item.status),has('documents.write')?button('Bearbeiten',()=>defectDialog(projectId,item),'small'):null],item.details))),
    panel('Aufmaß',has('documents.write')?button('Aufmaß erfassen',()=>measurementDialog(projectId),'small'):null,rows(collection(measurements),item=>row(item.title,(item.lines||[]).map(line=>line.description+': '+formatQuantity(line.quantity,line.unit)).join(' · '),[badge(item.status),item.status==='signed'?button('PDF',()=>action(()=>download(biz(`/measurements/${item.id}/pdf`),'Aufmass.pdf')),'small'):has('documents.write')?button('Prüfen & unterzeichnen',()=>signatureDialog(item,'measurements'),'small'):null]))),
    panel('Checklisten',has('documents.write')?button('Prüfliste anlegen',()=>checklistDialog(projectId),'small'):null,rows(collection(checklists),item=>row(item.title,`${item.items.length} Prüfpunkte · Vorlage ${item.revision}`,[has('documents.write')?button('Prüfung starten',()=>action(async()=>{const run=await mutation('run-'+item.id,'/checklists/'+item.id+'/start',{project_id:projectId});checklistRunDialog(run);}), 'small'):null])),
      rows(collection(runs),item=>row(item.title,formatDate(item.created_at,true),[badge(item.status),button('Prüfung öffnen',()=>checklistRunDialog(item),'small')]))),
    button('Dokumentation exportieren',()=>action(async()=>jsonDownload(await api.get(query(biz('/documentation/export'),{project_id:projectId})),'Projektdokumentation.json')),'small'));
  return content;
}
const photoUploads=new Map();
async function photoThumbnail(original) {
  const bitmap=await createImageBitmap(original);
  try {
    const ratio=Math.min(1,600/Math.max(bitmap.width,bitmap.height)),canvas=el('canvas',{width:Math.max(1,Math.round(bitmap.width*ratio)),height:Math.max(1,Math.round(bitmap.height*ratio))});
    const context=canvas.getContext('2d',{alpha:false});context.fillStyle='#ffffff';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(bitmap,0,0,canvas.width,canvas.height);
    return await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Galerievorschau konnte nicht erzeugt werden.')),'image/jpeg',0.8));
  } finally { bitmap.close(); }
}
function bytesBase64(bytes) { let value='';for(let offset=0;offset<bytes.length;offset+=16384)value+=String.fromCharCode(...bytes.subarray(offset,offset+16384));return btoa(value); }
function photoDialog(projectId) {
  const file=el('input',{type:'file',accept:'image/jpeg,image/png,image/webp',capture:'environment','aria-label':'Baustellenfoto auswählen',required:true});
  const progress=el('progress',{max:1,value:0,'aria-label':'Uploadfortschritt'});
  const editor=form('',[field('caption','Bildnotiz','textarea','',{maxLength:2000})],async(data)=> {
    const original=file.files?.[0];if(!original)throw new Error('Bitte ein Foto auswählen.');
    if(original.size<1||original.size>20*1024*1024)throw new Error('Fotos dürfen höchstens 20 MiB groß sein.');
    if(!['image/jpeg','image/png','image/webp'].includes(original.type))throw new Error('JPEG, PNG oder WebP auswählen. Das Original wird unverändert gespeichert.');
    const bytes=new Uint8Array(await original.arrayBuffer()),digest=await crypto.subtle.digest('SHA-256',bytes),sha=Array.from(new Uint8Array(digest),value=>value.toString(16).padStart(2,'0')).join('');
    const key=projectId+':'+sha+':'+original.name;
    let record=photoUploads.get(key);
    if(record&&record.caption!==(data.caption||''))throw new Error('Den begonnenen Upload zuerst mit unveränderter Bildnotiz abschließen. Danach lässt sich die Notiz bearbeiten.');
    if(!record) {record=await mutation('photo-'+key,'/media',{project_id:projectId,filename:original.name,media_type:original.type,size:bytes.length,sha256:sha,caption:data.caption||'',purpose:'site_photo',classification:'operational'});photoUploads.set(key,record);}
    record=await api.get(biz('/media/'+record.id));const chunks=new Set(record.uploaded_chunks);progress.max=bytes.length;
    for(let index=0,offset=0;offset<bytes.length;index++,offset+=record.chunk_size) {
      const part=bytes.subarray(offset,Math.min(offset+record.chunk_size,bytes.length));
      if(!chunks.has(index))await api.post(biz(`/media/${record.id}/chunks/${index}`),{content_base64:bytesBase64(part)});
      progress.value=offset+part.length;
    }
    const completed=await mutation('complete-photo-'+record.id,`/media/${record.id}/complete`,{});photoUploads.delete(key);return completed;
  },{key:'photo-upload-'+projectId,submit:'Original sicher hochladen',after:()=>{state.galleryPage=0;return refresh();},extra:el('div',{class:'stack'},file,progress),description:'Original, Bildnotiz und Markierungen bleiben getrennt. Der Browser benötigt eine aktive Verbindung; unklare Antworten mit unverändertem Foto erneut versuchen.'});
  dialog('Baustellenfoto',editor);
}
function diaryDialog(projectId) {
  dialog('Bautagesbericht',form('',[field('title','Titel','text','Tagesbericht',{required:true}),field('entry_date','Arbeitstag','date',dateInput(),{required:true}),field('weather','Wetter'),field('crew_count','Personenzahl','integer',1,{min:0,max:1000}),field('work','Ausgeführte Arbeiten','textarea','',{required:true}),field('issues','Probleme / Hinweise','textarea')],(data,key)=>mutation(key,'/diary',{...data,project_id:projectId}),{key:'diary-'+projectId}));
}
function defectDialog(projectId,item=null) {
  dialog(item?'Mangel bearbeiten':'Mangel erfassen',form('',[field('title','Mangel','text',item?.title||'',{required:true}),field('location','Ort / Bauteil','text',item?.location||''),field('due_date','Frist','date',item?.due_date||''),field('details','Beschreibung','textarea',item?.details||''),field('status','Status','select',item?.status||'open',{options:[['open','Offen'],['in_progress','In Bearbeitung'],['resolved','Behoben'],['accepted','Abgenommen']]}),field('resolution','Abschlussnachweis','textarea',item?.resolution||'')],
    (data,key)=>mutation(key,'/defects'+(item?'/'+item.id:''),{...data,project_id:projectId,...(item?{revision:item.revision}:{})}),{key:'defect-'+(item?.id||'new')}));
}
function measurementDialog(projectId) {
  dialog('Metrisches Aufmaß',form('',[field('title','Aufmaßbezeichnung','text','',{required:true}),field('description','Position / Bauteil','text','',{required:true}),field('shape','Berechnung','select','area',{options:[['length','Länge'],['area','Rechteckfläche'],['volume','Quader-Volumen']]}),field('length','Länge in Metern','decimal','',{required:true}),field('width','Breite in Metern','decimal'),field('height','Höhe in Metern','decimal')],
    (data,key)=>{const variables={length:{value:data.length,unit:'m'}};if(data.shape!=='length'){if(!data.width)throw new Error('Breite eingeben.');variables.width={value:data.width,unit:'m'};}if(data.shape==='volume'){if(!data.height)throw new Error('Höhe eingeben.');variables.height={value:data.height,unit:'m'};}
      return mutation(key,'/measurements',{project_id:projectId,title:data.title,lines:[{description:data.description,unit:({length:'m',area:'m2',volume:'m3'})[data.shape],formula:({length:'length',area:'length * width',volume:'length * width * height'})[data.shape],variables}]});},
    {key:'measurement-'+projectId,description:'Bestätigte metrische Werte manuell erfassen. Aus einem Foto oder maßstabslosen Plan werden keine Maße abgeleitet.'}));
}
function drawingCanvas({height=180,background=null,annotations=[]}={}) {
  const canvas=el('canvas',{class:background?'':'signature',tabIndex:0,'aria-label':background?'Bildmarkierungen':'Unterschriftsfläche'}),strokes=[],marks=annotations.map(item=>structuredClone(item));let current=null,mode='signature',textValue='';
  const context=canvas.getContext('2d');
  function redraw() {
    const rect=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1;canvas.width=Math.max(1,Math.round(rect.width*ratio));canvas.height=Math.max(1,Math.round((background?rect.height:height)*ratio));context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,rect.width,rect.height);context.lineWidth=2;context.lineCap='round';context.strokeStyle='#245ec8';
    const line=points=>{context.beginPath();points.forEach((point,index)=>context[index?'lineTo':'moveTo'](point[0]*rect.width,point[1]*rect.height));context.stroke();};
    strokes.forEach(line);if(current&&mode==='signature')line(current);
    [...marks,...(current&&mode!=='signature'?[{kind:mode,points:[current[0],current.at(-1)]}]:[])].forEach(mark=>{context.strokeStyle=mark.color||'#ff3333';context.fillStyle=mark.color||'#ff3333';if(mark.kind==='text'){context.font='16px system-ui';context.fillText(mark.text,mark.point[0]*rect.width,mark.point[1]*rect.height);}else if(mark.kind==='rectangle'){const[a,b]=mark.points;context.strokeRect(a[0]*rect.width,a[1]*rect.height,(b[0]-a[0])*rect.width,(b[1]-a[1])*rect.height);}else line(mark.points);});
  }
  const point=event=>{const bounds=canvas.getBoundingClientRect();return[Math.min(1,Math.max(0,(event.clientX-bounds.left)/bounds.width)),Math.min(1,Math.max(0,(event.clientY-bounds.top)/bounds.height))];};
  canvas.addEventListener('pointerdown',event=>{event.preventDefault();canvas.setPointerCapture(event.pointerId);const p=point(event);if(mode==='text'){if(textValue.trim())marks.push({kind:'text',point:p,text:textValue.trim(),color:'#ff3333'});redraw();return;}current=[p,p];redraw();});
  canvas.addEventListener('pointermove',event=>{if(!current)return;event.preventDefault();const p=point(event);if(mode==='signature'){if(current.length<2000)current.push(p);}else current=[current[0],p];redraw();});
  canvas.addEventListener('pointerup',()=>{if(!current)return;if(mode==='signature')strokes.push(current);else marks.push({kind:mode,points:[current[0],current.at(-1)],color:'#ff3333'});current=null;redraw();});
  canvas.addEventListener('pointercancel',()=>{current=null;redraw();});
  const observer=new ResizeObserver(()=>redraw());observer.observe(canvas);canvas.disconnect=()=>observer.disconnect();canvas.strokes=strokes;canvas.marks=marks;canvas.clear=()=>{strokes.splice(0);marks.splice(0);redraw();};canvas.mode=(value,text='')=>{mode=value;textValue=text;};return canvas;
}
function signatureDialog(item,resource) {
  const canvas=drawingCanvas(),snapshot=resource==='measurements'?table(['Position','Formel','Ergebnis'],item.lines.map(line=>[line.description,line.formula,formatQuantity(line.quantity,line.unit)])):panel('Prüfliste',rows(item.checklist?.items||[],line=>row(line.label,item.checklist.answers[line.key]===true?'Ja':item.checklist.answers[line.key]===false?'Nein':String(item.checklist.answers[line.key]))));
  const editor=form('',[field('signer','Name der unterzeichnenden Person','text','',{required:true,maxLength:200}),field('confirmed','Ich bestätige die dargestellte Fassung','checkbox',false,{required:true})],(data,key)=>{if(!data.confirmed||!canvas.strokes.length)throw new Error('Fassung bestätigen und auf der Zeichenfläche unterzeichnen.');return mutation(key,`/${resource}/${item.id}/sign`,{revision:item.revision,expected_hash:item.content_hash,signer:data.signer,strokes:canvas.strokes});},
    {key:'sign-'+item.id,submit:'Fassung unterzeichnen',extra:el('div',{class:'stack'},snapshot,el('p',{class:'caption'},'Inhalt SHA-256: '+item.content_hash),canvas,button('Unterschrift löschen',()=>canvas.clear(),'small'))});
  dialog('Fassung prüfen & unterzeichnen',editor,'Name, Zeichnung und UTC-Zeit werden mit dieser Fassung als unveränderliches PDF gespeichert. Dies ist keine qualifizierte elektronische Signatur.');
}
async function annotateDialog(item) {
  const blob=await api.binary(biz(`/media/${item.id}/content`)),image=el('img',{src:objectUrl(blob),alt:item.caption||item.filename}),canvas=drawingCanvas({background:true,annotations:item.annotations||[]});
  canvas.mode('line');const stage=el('div',{class:'annotation-stage'},image,canvas),label=el('input',{type:'text',placeholder:'Text für die Markierung','aria-label':'Markierungstext',maxLength:500});
  const tool=select('Werkzeug',[['line','Linie'],['rectangle','Rechteck'],['text','Text']],'line',value=>canvas.mode(value,label.value));label.addEventListener('input',()=>canvas.mode(tool.querySelector('select').value,label.value));
  dialog('Bild separat markieren',form('',[field('caption','Bildnotiz','textarea',item.caption||'',{maxLength:2000})],(data,key)=>mutation(key,`/media/${item.id}`,{...data,revision:item.revision,annotations:canvas.marks}),{key:'annotate-'+item.id,extra:el('div',{class:'stack'},tool,label,stage,button('Markierungen löschen',()=>canvas.clear(),'small'))}),'Das Original bleibt unverändert. Die Markierungsebene wird getrennt versioniert.');
}
function checklistDialog(projectId) {
  dialog('Prüflistenvorlage',form('',[field('title','Checkliste','text','',{required:true}),field('items','Prüfpunkte – ein Punkt pro Zeile','textarea','',{required:true,maxLength:10000,help:'In dieser einfachen Vorlage sind alle Punkte verpflichtende Ja/Nein-Prüfungen.'})],
    (data,key)=>mutation(key,'/checklists',{project_id:projectId,title:data.title,items:data.items.split('\n').map(line=>line.trim()).filter(Boolean).map((label,index)=>({key:'check_'+index,label,required:true,type:'boolean'}))}),{key:'checklist-'+projectId}));
}
function checklistRunDialog(run) {
  if(run.status==='completed') {action(async()=>{const report=await api.get(biz('/service-reports/'+run.report_id));if(report.status==='signed')await download(biz('/service-reports/'+report.id+'/pdf'),'Servicebericht.pdf');else signatureDialog(report,'service-reports');});return;}
  let savedAnswers=null;
  const fields=run.items.map(item=>field(item.key,item.label,item.type==='boolean'?'select':item.type==='number'?'decimal':'text',run.answers[item.key]===undefined?'':String(run.answers[item.key]),{required:item.required,...(item.type==='boolean'?{options:[['','Bitte prüfen'],['true','Ja'],['false','Nein']]}:{})}));
  dialog(run.title,form('',fields,async(data,key)=>{const answers={};run.items.forEach(item=>{if(data[item.key]!==undefined)answers[item.key]=item.type==='boolean'?data[item.key]==='true':data[item.key];});
    const fingerprint=JSON.stringify(answers);
    if(savedAnswers&&savedAnswers!==fingerprint)throw new Error('Zuerst den begonnenen Berichtsabschluss mit unveränderten Antworten wiederholen.');
    if(!savedAnswers){await mutation(key,'/checklists/'+run.id+'/answers',{revision:run.revision,answers});savedAnswers=fingerprint;}
    const report=await mutation('check-report-'+run.id,'/checklists/'+run.id+'/report',{});signatureDialog(report,'service-reports');return undefined;},
    {key:'answers-'+run.id,submit:'Prüfergebnis in Servicebericht übernehmen'}),'Diese Prüfung verwendet die eingefrorene Vorlagenfassung '+run.template_revision+'.');
}

async function personnelView() {
  const employees=collection(await api.get(biz('/employees'))),own=employees.find(employee=>employee.user_id===state.user.id);
  const selected=employees.find(employee=>employee.id===state.employeeId)||own||(has('personnel.read')?employees[0]:null);
  const from=new Date();from.setDate(1);const to=new Date();
  let entries=[],summary=null;
  if(selected) {
    const filters={employee_id:selected.id,from:dateInput(from),to:dateInput(to)};
    [entries,summary]=await Promise.all([api.get(query(biz('/time/entries'),filters)).then(collection),api.get(query(biz('/time/summary'),filters))]);
  }
  const current=entries.find(item=>['working','paused'].includes(item.status)&&item.employee_id===own?.id);
  const buttons=[];if(own&&has('time.own'))buttons.push(button(current?'Laufende Zeit öffnen':'Zeit starten',()=>timeDialog(current),'primary'));
  if(has('personnel.manage'))buttons.push(button('Mitarbeiterprofil anlegen',()=>action(()=>employeeDialog()),'small'));
  const content=el('div',{class:'stack'},heading('Personal & Zeiten','Eigene Zeiten und bestätigte Tagesnachweise. Keine Hintergrundortung.',buttons),
    selected?select('Mitarbeiter',options(has('personnel.read')?employees:employees.filter(employee=>employee.user_id===state.user.id)),selected.id,value=>{state.employeeId=value;refresh();}):notice('Für diesen Zugang ist noch kein Mitarbeiterprofil eingerichtet. Die Geschäftsführung kann es mit dem vorhandenen Benutzer verknüpfen.','warn'));
  if(summary)content.append(el('div',{class:'grid'},panel('Arbeitszeit im Monat',el('div',{class:'metric'},duration(summary.worked_seconds)),el('p',{class:'metric-sub'},formatDate(dateInput(from))+' bis '+formatDate(dateInput(to))))),
    panel('Arbeitszeiteinträge',rows(entries,item=>row(state.projects.find(project=>project.id===item.project_id)?.name||'Projekt',`${formatDate(item.started_at,true)}${item.ended_at?' – '+formatDate(item.ended_at,true):''}`,[badge(item.status),el('span',{class:'caption'},duration(item.worked_seconds)),item.employee_id===own?.id&&['working','paused'].includes(item.status)?button('Fortsetzen / beenden',()=>timeDialog(item),'small'):null]))),
    panel('Tagesfreigaben',rows(summary.days||[],day=>row(formatDate(day.date),`Netto ${duration(day.net_seconds)} · Pause ${duration(day.break_seconds||0)}`,[badge(day.status),has('time.approve')&&day.status!=='approved'?button('Tag freigeben',()=>confirmDialog('Arbeitstag freigeben','Die geprüfte Zeit wird eingefroren. Optionale Ortsdaten werden aus den aktiven Daten und Wiederholungsquittungen entfernt.',async()=>{await mutation('approve-day-'+selected.id+'-'+day.date,`/time/days/${day.date}/approve`,{employee_id:selected.id,revision:day.revision});refresh();}),'small'):null]))));
  if(has('personnel.read'))content.append(panel('Mitarbeiterprofile',rows(employees,employee=>row(employee.name,`${employee.weekly_minutes??'—'} Sollminuten / Woche`,[badge(employee.active?'Aktiv':'Inaktiv'),has('personnel.manage')?button('Bearbeiten',()=>action(()=>employeeDialog(employee)),'small'):null]))));
  return content;
}
function timeDialog(entry=null) {
  const actions=entry?entry.status==='paused'?[['resume','Arbeit fortsetzen'],['stop','Zeit beenden']]:[['pause','Pause beginnen'],['stop','Zeit beenden']]:[['start','Arbeit beginnen']];
  dialog('Zeiterfassung',form('',[...(!entry?[projectField()]:[]),field('action','Aktion','select',actions[0][0],{options:actions,required:true}),field('occurred_at','Zeitpunkt (Gerätezeit)','datetime-local',localDateTime(),{required:true})],
    (data,key)=>mutation(key,'/time/events',{...data,project_id:entry?.project_id||data.project_id,entry_id:entry?.id||state.newTimeEntryId||(state.newTimeEntryId=requestId()),device_id:entry?.events?.at(-1)?.device_id||state.deviceId,sequence:(entry?.last_sequence||0)+1,revision:entry?.revision||0}),
    {key:'time-event-'+(entry?.id||'start')+'-'+(entry?.revision||0),submit:'Zeitereignis speichern',after:()=>{state.newTimeEntryId=null;refresh();}}),'Der Browser speichert keine dauerhafte Offlinewarteschlange. Bei unklarer Antwort dieselbe Eingabe in diesem Fenster erneut senden.');
}
async function employeeDialog(employee=null) {
  const users=collection(await api.get('/users'));
  dialog(employee?'Mitarbeiterprofil ändern':'Mitarbeiterprofil anlegen',form('',[field('user_id','Benutzerkonto','select',employee?.user_id||'',{options:options(users,item=>item.email),required:true}),field('name','Anzeigename','text',employee?.name||'',{required:true}),field('weekly_minutes','Wöchentliche Sollminuten','integer',employee?.weekly_minutes??2400,{required:true,min:0,max:10080}),field('hourly_cost_minor','Historischer Kostensatz in Cent / Stunde','integer',employee?.hourly_cost_minor??0,{required:true,min:0,help:'3500 entspricht 35,00 EUR. Bestehende Zeiteinträge behalten ihren ursprünglichen Satz.'}),field('active','Aktiv','checkbox',employee?.active??true)],
    (data,key)=>mutation(key,'/employees'+(employee?'/'+employee.id:''),{...data,...(employee?{revision:employee.revision}:{})}),{key:'employee-'+(employee?.id||'new')}));
}

async function maintenancePanel(projectId) {
  const [assets,contracts,visits,reports]=await Promise.all(['assets','maintenance/contracts','maintenance/history','service-reports'].map(path=>api.get(query(biz('/'+path),{project_id:projectId})).then(collection)));
  return el('div',{class:'stack'},panel('Anlagen',has('documents.write')?button('Anlage erfassen',()=>assetDialog(projectId),'primary'):null,rows(assets,item=>row(item.name,`${item.serial_number||'Seriennummer offen'} · ${item.location||'Standort offen'}`,[has('documents.write')?button('Bearbeiten',()=>assetDialog(projectId,item),'small'):null]))),
    panel('Wartungsverträge',has('projects.manage')?button('Wartungsvertrag anlegen',()=>maintenanceContractDialog(projectId,assets),'small'):null,rows(contracts,item=>row(item.title,`${assets.find(asset=>asset.id===item.asset_id)?.name||'Anlage'} · Nächste Fälligkeit ${formatDate(item.next_due_date)}`,[badge(item.active?'Aktiv':'Pausiert')])),
      has('projects.manage')?button('Fällige Einsätze planen',()=>action(async()=>{const result=await mutation('maintenance-schedule-'+projectId+'-'+dateInput(),'/maintenance/schedule',{project_id:projectId,as_of:dateInput()});if(result.more_due)main.prepend(notice('Weitere Fälligkeiten vorhanden. Planung erneut ausführen.','warn'));await refresh();}),'small'):null),
    panel('Wartungshistorie',rows(visits,visit=>row(visit.asset_snapshot?.name||'Anlage',`${formatDate(visit.due_date)} · ${visit.contract_snapshot?.title||''}`,[badge(visit.status),visit.status==='completed'?button('Service-PDF',()=>action(()=>download(biz(`/service-reports/${visit.report_id}/pdf`),'Servicebericht.pdf')),'small'):has('documents.write')?button('Mit Servicebericht abschließen',()=>completeVisitDialog(projectId,visit,reports),'small'):null]))));
}
function assetDialog(projectId,item=null) {
  dialog(item?'Anlage bearbeiten':'Anlage erfassen',form('',[field('name','Anlage','text',item?.name||'',{required:true}),field('serial_number','Seriennummer','text',item?.serial_number||''),field('asset_type','Anlagentyp','text',item?.asset_type||''),field('location','Standort / Raum','text',item?.location||''),field('notes','Anlagenhinweise','textarea',item?.notes||'')],
    (data,key)=>mutation(key,'/assets'+(item?'/'+item.id:''),{...data,project_id:projectId,...(item?{revision:item.revision}:{})}),{key:'asset-'+(item?.id||'new')}));
}
function maintenanceContractDialog(projectId,assets) {
  dialog('Wartungsvertrag',form('',[field('asset_id','Anlage','select','',{options:options(assets),required:true}),field('title','Vertragsbezeichnung','text','',{required:true}),field('anchor_date','Erste Fälligkeit','date',dateInput(),{required:true}),field('interval_unit','Intervalltyp','select','months',{options:[['months','Kalendermonate'],['days','Tage']]}),field('interval_count','Intervall','integer',12,{required:true,min:1,max:120}),field('notes','Vertragshinweise','textarea')],
    (data,key)=>mutation(key,'/maintenance/contracts',{...data,project_id:projectId}),{key:'maintenance-contract-'+projectId}),'Monatsintervalle bleiben am ursprünglichen Kalendertag verankert. Monatsende und Schaltjahre werden serverseitig berücksichtigt.');
}
function completeVisitDialog(projectId,visit,reports) {
  const signed=reports.filter(report=>report.status==='signed');
  if(!signed.length){dialog('Servicebericht fehlt',notice('Zuerst unter Fotos & Doku eine Checkliste durchführen und den zugehörigen Servicebericht unterzeichnen. Danach lässt sich die Wartung damit abschließen.','warn'));return;}
  dialog('Wartung abschließen',form('',[field('report_id','Unterzeichneter Servicebericht','select','',{options:options(signed),required:true})],(data,key)=>mutation(key,`/maintenance/visits/${visit.id}/complete`,{...data,project_id:projectId,revision:visit.revision}),{key:'complete-visit-'+visit.id,submit:'Abschluss verbindlich speichern'}),'Der PDF-Hash des gewählten Berichts wird dauerhaft mit diesem Wartungsbesuch verknüpft.');
}

async function settingsView() {
  const [branding,statuses]=await Promise.all([api.get(biz('/settings/branding')),api.get(biz('/project-statuses'))]);
  const content=el('div',{class:'stack'},heading('Einstellungen','Betriebsdaten und Freigaben. Externe Integrationen bleiben ausdrücklich getrennt.'),
    form('Aussteller & Briefpapier',[field('company_name','Firmenname','text',branding.company_name||'',{required:true}),field('address_line','Straße / Hausnummer','text',branding.address_line||''),field('postal_code','Postleitzahl','text',branding.postal_code||''),field('city','Ort','text',branding.city||''),field('vat_id','USt-IdNr.','text',branding.vat_id||''),field('tax_number','Steuernummer','text',branding.tax_number||''),field('email','Betriebliche E-Mail','email',branding.email||''),field('phone','Telefon','tel',branding.phone||''),field('iban','IBAN','text',branding.iban||''),field('bic','BIC','text',branding.bic||''),field('footer','Fußzeile','textarea',branding.footer||'')],
      (data,key)=>mutation(key,'/settings/branding',{...data,revision:branding.revision}),{key:'branding',description:'Die vorhandene Ausstellerfreigabe wird hier nicht still aktiviert. Historisch finale Dokumente behalten ihre eigene Fassung.'}),
    panel('Projektstatus',button('Status hinzufügen',()=>dialog('Projektstatus',form('',[field('name','Bezeichnung','text','',{required:true}),field('color','Farbe','color','#2864da'),field('position','Reihenfolge','integer',collection(statuses).length,{min:0}),field('terminal','Abschlussstatus','checkbox',false)],(data,key)=>mutation(key,'/project-statuses',{...data,active:true}),{key:'status-new'})),'small'),rows(collection(statuses),status=>row(status.name,`Position ${status.position}`,[badge(status.terminal?'Abschluss':'Laufend')]))),
    panel('Benutzerrechte',button('Freigaben ansehen / ändern',()=>action(()=>permissionsDialog()),'small'),el('p',{class:'caption'},'Berechtigungen werden bei jeder Serveroperation erneut geprüft. Projektzuweisung und Fachrecht sind getrennt.')),
    panel('Externe Verbindungen',el('p',{class:'muted'},'Diese Oberfläche erzeugt keine externen Sendungen, Bestellungen oder Appregistrierungen.'),button('Vorbereitete Adapter prüfen',()=>action(()=>adapterDialog()),'small')));
  return content;
}
async function permissionsDialog() {
  const [grants,users]=await Promise.all([api.get(biz('/settings/permissions')),api.get('/users')]);
  const permissions=['contacts.read','contacts.write','projects.manage','documents.read','documents.write','documents.classify','finance.read','finance.write','finance.issue','finance.approve','personnel.read','personnel.manage','time.own','time.approve','inventory.read','inventory.write','settings.manage','privacy.manage'];
  dialog('Fachrechte',el('div',{class:'stack'},form('Freigabe / Sperre',[field('user_id','Benutzer','select','',{options:options(collection(users),user=>user.email),required:true}),field('permission','Fachrecht','select','documents.read',{options:permissions.map(name=>[name,name])}),field('scope','Geltungsbereich','select','*',{options:[['*','Alle freigegebenen Projekte'],...options(state.projects)]}),field('effect','Entscheidung','select','allow',{options:[['allow','Erlauben'],['deny','Sperren']]})],
    (data,key)=>mutation(key,'/settings/permissions',{...data,revision:collection(grants).find(grant=>grant.user_id===data.user_id&&grant.permission===data.permission&&grant.scope===data.scope)?.revision||0}),{key:'grant-new',description:'Eine Projektfreigabe wird dadurch nicht ersetzt. Sperren gelten serverseitig auch bei wiederholten Anfragen.'}),
    panel('Vorhandene Entscheidungen',rows(collection(grants),grant=>row(collection(users).find(user=>user.id===grant.user_id)?.email||grant.user_id,`${grant.permission} · ${grant.scope==='*'?'Global':state.projects.find(project=>project.id===grant.scope)?.name||grant.scope}`,[badge(grant.effect==='allow'?'Freigegeben':'Gesperrt')])))));
}
async function adapterDialog() {
  const response=await api.get(biz('/adapters'));
  dialog('Adapterstatus',rows(collection(response),adapter=>row(adapter.name||adapter.id,adapter.description||adapter.profile||'', [badge(adapter.enabled?'Freigeschaltet':'Deaktiviert')] ),'Kein freigegebener Adapter vorhanden.'));
}

if(typeof document!=='undefined') {
  root=document.getElementById('office-app');
  if(root) {
    loginScreen();
    addEventListener('online',networkState);addEventListener('offline',networkState);
    matchMedia('(max-width:760px)').addEventListener('change',updateDrawer);
    addEventListener('beforeunload',event=>{if(api.pendingCount){event.preventDefault();event.returnValue='';}});
    addEventListener('pagehide',()=>endSession());
  }
}
