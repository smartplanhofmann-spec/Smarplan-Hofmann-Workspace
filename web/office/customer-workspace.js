/* Project-scoped customer client. Credentials and uncertain uploads stay in RAM. */
export class WorkspaceError extends Error {
  constructor(message,status=0){super(message);this.name='WorkspaceError';this.status=status;}
}
const ID=/^[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/;
export const WORKSPACE_UPLOAD_LIMIT=4*1024*1024;
const DOWNLOAD_LIMIT=21*1024*1024;
const TYPES=new Set(['application/pdf','image/png','image/jpeg','image/webp']);
const token=(value,prefix)=>typeof value==='string'&&new RegExp('^'+prefix+'[A-Za-z0-9_-]{43}$').test(value);
function invalid(message='Der freigegebene Projektstand konnte nicht sicher gelesen werden.'){return new WorkspaceError(message,502);}
function object(value){if(!value||typeof value!=='object'||Array.isArray(value))throw invalid();return value;}
function text(value,maximum=10000,required=false){if(typeof value!=='string'||value.length>maximum||(required&&!value.trim()))throw invalid();return value;}
function id(value){if(typeof value!=='string'||!ID.test(value))throw invalid();return value;}
function instant(value){text(value,100,true);if(!Number.isFinite(Date.parse(value)))throw invalid();return value;}
function date(value){if(value===null)return null;text(value,10,true);if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value)))throw invalid();return value;}
function fields(value,names){object(value);return Object.fromEntries(names.map(name=>[name,text(value[name])]));}
function fileMetadata(value,projectId,maximum=DOWNLOAD_LIMIT){
  object(value);id(value.id);if(id(value.project_id)!==projectId||!TYPES.has(value.media_type)||!Number.isSafeInteger(value.size)||value.size<1||value.size>maximum||!HASH.test(value.sha256||''))throw invalid();
  return {id:value.id,project_id:projectId,filename:text(value.filename,240,true),media_type:value.media_type,size:value.size,sha256:value.sha256,created_at:instant(value.created_at)};
}
export function workspaceUpload(value,projectId,grantId){
  const result=fileMetadata(value,projectId,WORKSPACE_UPLOAD_LIMIT);
  if(id(value.grant_id)!==grantId||!['received','accepted'].includes(value.status))throw invalid();
  return {...result,grant_id:grantId,note:text(value.note,5000),status:value.status,...(value.status==='accepted'?{accepted_at:instant(value.accepted_at)}:{})};
}
export function workspaceView(value,grantId,projectId=null){
  object(value);if(id(value.grant_id)!==grantId)throw invalid();
  object(value.project);const current=id(value.project.id);
  if(projectId!==null&&current!==projectId)throw invalid();
  const project={id:current,name:text(value.project.name,500,true),customer:text(value.project.customer,500,true)};
  let publication=null;
  if(value.publication!==null){const v=object(value.publication);if(!Number.isSafeInteger(v.revision)||v.revision<1)throw invalid();
    publication={id:id(v.id),revision:v.revision,...fields(v,['title','description','status_label']),start_date:date(v.start_date),end_date:date(v.end_date),published_at:instant(v.published_at)};
  }
  if(!Array.isArray(value.files)||value.files.length>500||!Array.isArray(value.uploads)||value.uploads.length>500||typeof value.uploads_allowed!=='boolean')throw invalid();
  const files=value.files.map(v=>({...fileMetadata(v,current),title:text(v.title,300,true)}));
  const uploads=value.uploads.map(v=>workspaceUpload(v,current,grantId));
  for(const rows of [files,uploads])if(new Set(rows.map(v=>v.id)).size!==rows.length)throw invalid();
  return {grant_id:grantId,project,publication,files,uploads,expires_at:instant(value.expires_at),uploads_allowed:value.uploads_allowed};
}
export function consumeWorkspaceInvitation(location,history){
  const fragment=location.hash;history.replaceState(null,'',location.pathname);
  if(location.search)throw new WorkspaceError('Bitte den vollständigen Projektlink ohne zusätzliche URL-Parameter öffnen.',400);
  if(!fragment)return null;
  const parts=new URLSearchParams(fragment.slice(1));
  if(parts.size!==2||parts.getAll('grant').length!==1||parts.getAll('key').length!==1||!ID.test(parts.get('grant')||'')||!token(parts.get('key'),'SPCI_'))
    throw new WorkspaceError('Dieser Projektlink ist unvollständig. Bitte den vollständigen Kundenlink erneut öffnen.',400);
  return {grant_id:parts.get('grant'),key:parts.get('key')};
}
export async function workspaceSHA256(bytes){return [...new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');}
function base64(bytes){let raw='';for(let offset=0;offset<bytes.length;offset+=32768)raw+=String.fromCharCode(...bytes.subarray(offset,offset+32768));return btoa(raw);}
export async function workspaceUploadPayload(file,note,request_id){
  if(!ID.test(request_id||'')||!file||!Number.isSafeInteger(file.size)||file.size<1||file.size>WORKSPACE_UPLOAD_LIMIT||typeof file.arrayBuffer!=='function')throw new WorkspaceError('Bitte eine Datei mit höchstens 4 MiB auswählen.',400);
  const filename=typeof file.name==='string'?file.name:'',media_type=file.type||({pdf:'application/pdf',png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp'}[filename.split('.').at(-1)?.toLowerCase()]);
  if(!filename.trim()||filename.length>240||/[\x00-\x1f\x7f/\\]/.test(filename)||!TYPES.has(media_type))throw new WorkspaceError('Unterstützt werden PDF, PNG, JPEG und WebP mit einem gültigen Dateinamen.',400);
  if(typeof note!=='string'||note.length>5000||/[\x00-\x08\x0b-\x1f\x7f]/.test(note))throw new WorkspaceError('Bitte einen Hinweis mit höchstens 5.000 Zeichen eingeben.',400);
  const bytes=new Uint8Array(await file.arrayBuffer());
  if(bytes.byteLength!==file.size)throw new WorkspaceError('Die Datei wurde beim Lesen verändert. Bitte erneut auswählen.',400);
  return {request_id,filename,media_type,size:bytes.byteLength,sha256:await workspaceSHA256(bytes),content_base64:base64(bytes),note:note.trim()};
}
function errorMessage(status){
  if([401,403,404,410].includes(status))return 'Dieser Projektzugang ist nicht mehr verfügbar. Bitte einen gültigen Kundenlink erneut öffnen.';
  if(status===423)return 'Dateien können derzeit nicht gespeichert werden. Die unveränderte Übertragung kann später erneut versucht werden.';
  if(status===429)return 'Zu viele Versuche. Bitte später unverändert erneut versuchen.';
  if([400,413,415,422].includes(status))return 'Die Datei oder ihre Angaben wurden nicht angenommen. Bitte Format, Größe und Hinweis prüfen.';
  if(status===409)return 'Die Übertragung konnte nicht eindeutig zugeordnet werden. Bitte die Ansicht prüfen und die ursprüngliche Übertragung unverändert wiederholen.';
  return 'Keine sichere Antwort erhalten. Bitte die ursprüngliche Übertragung unverändert erneut versuchen.';
}
export class CustomerWorkspaceClient {
  #token='';#expires='';#grant='';#project=null;#generation=0;#pending=null;#controllers=new Set();
  constructor(fetcher=globalThis.fetch){this.fetcher=fetcher.bind(globalThis);}
  get authenticated(){return !!this.#token;}
  get expiresAt(){return this.#expires;}
  get pending(){return this.#pending!==null;}
  clear(){this.#generation++;for(const controller of this.#controllers)controller.abort();this.#controllers.clear();this.#token='';this.#expires='';this.#grant='';this.#project=null;this.#pending=null;}
  async request(path,{method='GET',body,publicRequest=false,binary=false,maxBytes=2*1024*1024}={}){
    const contentPath=/^\/(files|uploads)\/[a-f0-9]{32}\/content$/.test(path);
    const allowed=method==='POST'&&['/sessions','/logout','/uploads'].includes(path)||method==='GET'&&(path==='/workspace'||contentPath);
    if(!allowed||publicRequest!==(path==='/sessions')||binary!==contentPath||!Number.isSafeInteger(maxBytes)||maxBytes<1||maxBytes>DOWNLOAD_LIMIT)throw new WorkspaceError('Ungültiger Projektportal-Aufruf.',400);
    if(!publicRequest&&(!this.#token||Date.parse(this.#expires)<=Date.now())){this.clear();throw new WorkspaceError(errorMessage(401),401);}
    const generation=this.#generation,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);this.#controllers.add(controller);
    try{
      const response=await this.fetcher('/api/v1/customer-workspace'+path,{method,headers:{Accept:binary?'application/octet-stream':'application/json',...(body===undefined?{}:{'Content-Type':'application/json'}),...(publicRequest?{}:{Authorization:'Bearer '+this.#token})},...(body===undefined?{}:{body:JSON.stringify(body)}),credentials:'omit',redirect:'error',cache:'no-store',referrerPolicy:'no-referrer',signal:controller.signal});
      if(generation!==this.#generation)throw new WorkspaceError('Die Portalsitzung wurde beendet.',401);
      if(!response.ok){if([401,403,404,410].includes(response.status))this.clear();throw new WorkspaceError(errorMessage(response.status),response.status);}
      if(response.status!==(method==='POST'&&['/sessions','/uploads'].includes(path)?201:200))throw invalid();
      const advertised=response.headers.get('Content-Length');if(advertised!==null&&(!/^\d+$/.test(advertised)||Number(advertised)>maxBytes))throw invalid('Die Antwort ist zu groß.');
      const chunks=[];let size=0;const reader=response.body?.getReader();
      if(reader){try{for(;;){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;if(size>maxBytes){await reader.cancel();throw invalid('Die Antwort ist zu groß.');}chunks.push(next.value);}}finally{reader.releaseLock();}}
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
      if(generation!==this.#generation)throw new WorkspaceError('Die Portalsitzung wurde beendet.',401);
      const contentType=(response.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase();
      if(binary)return {bytes,media_type:contentType};
      if(contentType!=='application/json')throw invalid();
      try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{throw invalid();}
    }catch(error){if(error instanceof WorkspaceError)throw error;throw new WorkspaceError(errorMessage(0),0);}
    finally{clearTimeout(timer);this.#controllers.delete(controller);}
  }
  async open(invitation){
    if(!invitation||!ID.test(invitation.grant_id||'')||!token(invitation.key,'SPCI_'))throw new WorkspaceError('Gültiger Projektlink erwartet.',400);
    this.clear();const generation=this.#generation;
    const result=await this.request('/sessions',{method:'POST',body:{grant_id:invitation.grant_id,key:invitation.key},publicRequest:true});
    if(generation!==this.#generation||!token(result?.token,'SPCT_')||!Number.isFinite(Date.parse(result.expires_at))||Date.parse(result.expires_at)<=Date.now())throw invalid();
    this.#token=result.token;this.#expires=result.expires_at;this.#grant=invitation.grant_id;return {expires_at:this.#expires};
  }
  async view(){const generation=this.#generation,result=workspaceView(await this.request('/workspace'),this.#grant,this.#project);if(generation!==this.#generation)throw new WorkspaceError('Die Portalsitzung wurde beendet.',401);if(Date.parse(result.expires_at)!==Date.parse(this.#expires))throw invalid();this.#project=result.project.id;return result;}
  async upload(file,note){
    if(!this.#project)throw new WorkspaceError('Bitte zuerst die Projektansicht laden.',400);
    const generation=this.#generation,request_id=this.#pending?.request_id||globalThis.crypto.randomUUID().replaceAll('-','');
    const body=await workspaceUploadPayload(file,note,request_id);
    if(generation!==this.#generation)throw new WorkspaceError('Die Portalsitzung wurde beendet.',401);
    if(this.#pending&&JSON.stringify(body)!==JSON.stringify(this.#pending))throw new WorkspaceError('Zuerst die ursprüngliche Übertragung unverändert erneut versuchen.',409);
    this.#pending=JSON.parse(JSON.stringify(body));return this.retryUpload();
  }
  async retryUpload(){
    if(!this.#pending)throw new WorkspaceError('Keine ausstehende Übertragung vorhanden.',400);
    const body=this.#pending,generation=this.#generation;
    try{
      const result=workspaceUpload(await this.request('/uploads',{method:'POST',body}),this.#project,this.#grant);
      if(generation!==this.#generation)throw new WorkspaceError('Die Portalsitzung wurde beendet.',401);
      if(['filename','media_type','size','sha256','note'].some(name=>result[name]!==body[name]))throw invalid('Die Empfangsbestätigung passt nicht zur übertragenen Datei. Bitte unverändert erneut versuchen.');
      this.#pending=null;return result;
    }catch(error){if([400,413,415,422].includes(error.status))this.#pending=null;throw error;}
  }
  async download(file,{upload=false}={}){
    const record=fileMetadata(file,this.#project),generation=this.#generation;
    if(upload&&file.grant_id!==this.#grant)throw invalid();
    const result=await this.request('/'+(upload?'uploads':'files')+'/'+record.id+'/content',{binary:true,maxBytes:record.size});
    if(result.bytes.length!==record.size||result.media_type!==record.media_type||await workspaceSHA256(result.bytes)!==record.sha256)throw invalid('Die Datei stimmt nicht mit dem freigegebenen Original überein.');
    if(generation!==this.#generation)throw new WorkspaceError('Die Portalsitzung wurde beendet.',401);
    return new Blob([result.bytes],{type:record.media_type});
  }
  async logout(){try{return await this.request('/logout',{method:'POST',body:{}});}finally{this.clear();}}
}
function node(tag,attributes={},...children){const result=document.createElement(tag);for(const [name,value]of Object.entries(attributes)){if(value===undefined||value===null)continue;if(name.startsWith('on'))result.addEventListener(name.slice(2).toLowerCase(),value);else if(name==='class')result.className=value;else if(name in result)result[name]=value;else result.setAttribute(name,value);}for(const child of children.flat(Infinity))if(child!==null&&child!==undefined)result.append(child instanceof Node?child:document.createTextNode(String(child)));return result;}
const button=(label,run,primary=false)=>node('button',{type:'button',class:primary?'primary':'',onClick:run},label);
const notice=(value,error=false)=>node('p',{class:error?'notice error':'notice',role:error?'alert':'status'},value);
const humanDate=value=>new Date(value).toLocaleString('de-DE');
function saveBlob(blob,filename){const url=URL.createObjectURL(blob),a=node('a',{href:url,download:filename});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}

if(typeof document!=='undefined'&&document.getElementById('customer-workspace-main')){
  let invitation=null,invitationError=null;
  try{invitation=consumeWorkspaceInvitation(globalThis.location,globalThis.history);}catch(error){invitationError=error;}
  const root=document.getElementById('customer-workspace-main'),client=new CustomerWorkspaceClient();let version=0,expiryTimer=null,lastView=null,busy=false;
  function clear(){version++;clearTimeout(expiryTimer);client.clear();lastView=null;busy=false;}
  function unavailable(error){root.replaceChildren(node('section',{class:'card'},node('h1',{},'Ihr Kundenprojekt'),notice(error?.message||'Bitte den vollständigen Projektlink erneut öffnen.',!!error)));}
  async function act(action){if(busy)return;busy=true;try{await action();}catch(error){if(!client.authenticated){lastView=null;unavailable(error);}else{const holder=root.querySelector('[data-status]');holder?.replaceChildren(notice(error.message,true));}}finally{busy=false;root.querySelectorAll('[data-busy]').forEach(control=>{control.disabled=false;});}}
  async function load(){const attempt=++version;const view=await client.view();if(attempt!==version)return;lastView=view;render(view);}
  function render(view){
    const status=node('div',{'data-status':''});
    const header=node('header',{},node('div',{},node('p',{class:'eyebrow'},'KUNDENPROJEKT'),node('h1',{class:'preserve'},view.project.name),node('p',{class:'muted'},view.project.customer)),node('div',{class:'actions'},button('Ansicht aktualisieren',()=>act(load)),button('Zugang beenden',()=>act(async()=>{try{await client.logout();}finally{clear();unavailable();}}))));
    const published=view.publication?node('section',{class:'card'},node('h2',{class:'preserve'},view.publication.title),node('p',{class:'muted'},view.publication.status_label+' · Freigegeben '+humanDate(view.publication.published_at)),node('p',{class:'preserve'},view.publication.description),...(view.publication.start_date||view.publication.end_date?[node('p',{},'Zeitraum: '+(view.publication.start_date||'Offen')+' bis '+(view.publication.end_date||'Offen'))]:[])):node('section',{class:'card'},node('h2',{},'Projektinformationen'),notice('Noch keine Projektinformationen freigegeben.'));
    const downloads=node('section',{class:'card'},node('h2',{},'Freigegebene Dateien'),view.files.length?view.files.map(file=>node('article',{},node('h3',{class:'preserve'},file.title),node('p',{class:'muted preserve'},file.filename+' · '+Math.ceil(file.size/1024)+' KiB'),button('Original herunterladen',()=>act(async()=>saveBlob(await client.download(file),file.filename))))):notice('Noch keine Dateien freigegeben.'));
    const history=node('section',{class:'card'},node('h2',{},'Ihre übermittelten Dateien'),view.uploads.length?view.uploads.map(file=>node('article',{},node('h3',{class:'preserve'},file.filename),node('p',{},file.status==='accepted'?'Ins Projekt übernommen':'Eingegangen · interne Übernahme ausstehend'),node('p',{class:'muted'},humanDate(file.created_at)),node('p',{class:'preserve'},file.note),button('Übermitteltes Original herunterladen',()=>act(async()=>saveBlob(await client.download(file,{upload:true}),file.filename))))):notice('Noch keine Dateien übermittelt.'));
    const uploads=node('section',{class:'card'},node('h2',{},'Datei zum Projekt senden'));
    if(client.pending){uploads.append(notice('Eine Empfangsbestätigung ist noch offen. Bitte diesen Tab geöffnet lassen und dieselbe Übertragung wiederholen.'),button('Ursprüngliche Übertragung erneut versuchen',()=>act(async()=>{await client.retryUpload();await load();}),true));}
    else if(view.uploads_allowed){const file=node('input',{type:'file',accept:'.pdf,.png,.jpg,.jpeg,.webp',required:true,id:'workspace-upload-file'}),note=node('textarea',{id:'workspace-upload-note',rows:4,maxLength:5000}),submit=node('button',{type:'submit',class:'primary','data-busy':''},'Datei übermitteln'),form=node('form',{},node('label',{htmlFor:file.id},'Datei auswählen · höchstens 4 MiB',file),node('label',{htmlFor:note.id},'Hinweis zur Datei',note),node('p',{class:'muted'},'PDF, PNG, JPEG oder WebP. Die Datei geht zunächst zur internen Prüfung ein.'),submit);form.addEventListener('submit',event=>{event.preventDefault();act(async()=>{submit.disabled=true;try{await client.upload(file.files?.[0],note.value);await load();}catch(error){if(client.pending)render(lastView);throw error;}});});uploads.append(form);}
    else uploads.append(notice('Dateiübertragungen sind für diesen Zugang derzeit nicht freigegeben.'));
    root.replaceChildren(header,status,published,downloads,uploads,history,node('p',{class:'muted'},'Zugang gültig bis '+humanDate(view.expires_at)+'. Nicht freigegebene Projektdaten sind hier nicht sichtbar.'));
    clearTimeout(expiryTimer);expiryTimer=setTimeout(()=>{clear();unavailable(new WorkspaceError(errorMessage(401),401));},Math.max(0,Date.parse(client.expiresAt)-Date.now()));
  }
  async function open(){const attempt=++version;root.replaceChildren(notice('Projektzugang wird geprüft …'));try{await client.open(invitation);if(attempt!==version)return;invitation=null;await load();}catch(error){if(attempt!==version)return;unavailable(error);if(invitation&&![400,401,403,404,410].includes(error.status))root.append(button('Zugang erneut öffnen',open));else invitation=null;}}
  if(root){if(invitationError)unavailable(invitationError);else if(invitation)open();else unavailable();}
  addEventListener('beforeunload',event=>{if(client.pending){event.preventDefault();event.returnValue='';}});addEventListener('pagehide',clear);addEventListener('pageshow',event=>{if(event.persisted)unavailable();});
}
