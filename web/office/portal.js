/* Isolated customer offer client. Tokens and uncertain decisions live in RAM. */
export class PortalError extends Error {
  constructor(message,status=0){super(message);this.name='PortalError';this.status=status;}
}
const ID=/^[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/;
const tokenValue=(value,prefix)=>typeof value==='string'&&new RegExp('^'+prefix+'[A-Za-z0-9_-]{43,195}$').test(value);
export function consumeInvitation(location,history){
  const fragment=location.hash;
  history.replaceState(null,'',location.pathname+location.search);
  if(!fragment)return null;
  const parts=new URLSearchParams(fragment.slice(1));
  if(parts.size!==2||parts.getAll('grant').length!==1||parts.getAll('key').length!==1||!ID.test(parts.get('grant')||'')||!tokenValue(parts.get('key'),'SPPI_'))
    throw new PortalError('Dieser Zugangslink ist unvollständig. Bitte den vollständigen Kundenlink erneut öffnen.',400);
  return {grant_id:parts.get('grant'),key:parts.get('key')};
}
let invitation=null,invitationError=null;
if(typeof document!=='undefined'){
  try{invitation=consumeInvitation(globalThis.location,globalThis.history);}catch(error){invitationError=error;}
}
function text(value,maximum=10000,required=false){
  if(typeof value!=='string'||value.length>maximum||(required&&!value.trim()))throw new PortalError('Die freigegebene Fassung konnte nicht vollständig gelesen werden.',502);
  return value;
}
function fields(source,names){
  if(!source||typeof source!=='object'||Array.isArray(source))throw new PortalError('Die freigegebene Fassung konnte nicht vollständig gelesen werden.',502);
  return Object.fromEntries(names.filter(name=>source[name]!==undefined).map(name=>[name,text(source[name])]));
}
const BUYER=['name','contact_name','address_line','postal_code','city','country','email','vat_id'];
const ISSUER=['company_name','address_line','postal_code','city','country','email','phone','website','vat_id','tax_number','iban','bic','payment_terms','footer'];
const POSITION=['description','quantity','unit','unit_price_net','price_base_quantity','discount_percent','tax_rate','tax_category','tax_exemption_reason','net'];
const TOTALS=['net','tax','gross','payable','labor_net','labor_tax','labor_gross','material_net','material_tax','material_gross'];
export function portalDecisionReceipt(value){
  if(!value||!ID.test(value.id||'')||!ID.test(value.offer_id||'')||!['accepted','declined'].includes(value.decision)||!HASH.test(value.content_hash||'')||!HASH.test(value.pdf_hash||''))
    throw new PortalError('Die gespeicherte Erklärung konnte nicht sicher bestätigt werden. Bitte unverändert erneut versuchen.',502);
  return fields(value,['id','offer_id','grant_id','principal_id','decision','declared_name','statement_version','statement_text','content_hash','pdf_hash','created_at']);
}
export function portalView(value){
  const offer=value?.offer;
  if(!offer||!ID.test(offer.id||'')||!Number.isSafeInteger(offer.revision)||offer.revision<1||!HASH.test(offer.content_hash||'')||!HASH.test(offer.pdf_hash||'')||offer.currency!=='EUR'||!Array.isArray(offer.positions)||offer.positions.length>200||typeof value.actions_allowed!=='boolean')
    throw new PortalError('Die freigegebene Fassung konnte nicht vollständig gelesen werden.',502);
  const projected={...fields(offer,['id','number','content_hash','pdf_hash','title','issue_date','due_date','currency','intro','notes']),revision:offer.revision,
    buyer:fields(offer.buyer,BUYER),issuer:fields(offer.issuer,ISSUER),positions:offer.positions.map((line,index)=>{
      if(!Number.isSafeInteger(line.index)||line.index<0)throw new PortalError('Die Angebotspositionen konnten nicht gelesen werden.',502);
      return {...fields(line,POSITION),index:line.index};}),totals:fields(offer.totals,TOTALS)};
  for(const name of ['net','tax','gross'])text(projected.totals[name],100,true);
  if(!Array.isArray(offer.totals.tax_breakdown))throw new PortalError('Die Steuerübersicht konnte nicht gelesen werden.',502);
  projected.totals.tax_breakdown=offer.totals.tax_breakdown.map(line=>fields(line,['rate','category','reason','net','tax']));
  const statements=fields(value.statements,['version','accepted','declined']);for(const name of ['version','accepted','declined'])text(statements[name],10000,true);
  return {offer:projected,expires_at:text(value.expires_at,100,true),actions_allowed:value.actions_allowed,statements,
    decision:value.decision===null?null:portalDecisionReceipt(value.decision)};
}
export function portalDecisionPayload(view,values,request_id){
  if(!ID.test(request_id)||!['accepted','declined'].includes(values.decision)||values.confirmation!==true)
    throw new PortalError('Bitte die ausgewählte Erklärung ausdrücklich bestätigen.',400);
  if(typeof values.declared_name!=='string'||!values.declared_name.trim()||values.declared_name.length>200||/[\x00-\x1f]/.test(values.declared_name))
    throw new PortalError('Bitte Ihren vollständigen Namen eingeben.',400);
  const declared_name=values.declared_name.trim();
  return {request_id,content_hash:view.offer.content_hash,pdf_hash:view.offer.pdf_hash,decision:values.decision,
    declared_name,statement_version:view.statements.version,confirmation:true};
}
function message(status){return [401,403,404,410].includes(status)?'Dieser Zugang ist nicht mehr verfügbar. Bitte einen gültigen Kundenlink erneut öffnen.':
  status===409?'Zu diesem Angebot liegt inzwischen eine andere Fassung oder Entscheidung vor. Die aktuelle Ansicht wird neu geladen.':
  status===423?'Erklärungen können derzeit nicht gespeichert werden. Bitte später unverändert erneut versuchen.':
  status===429?'Zu viele Versuche. Bitte später unverändert erneut versuchen.':
  status===400||status===422?'Bitte Ihre Eingaben prüfen. Diese Erklärung wurde nicht übernommen.':'Keine sichere Antwort erhalten. Bitte unverändert erneut versuchen.';}
export class PortalClient {
  #token='';#generation=0;#pending=null;#controllers=new Set();#expires='';
  constructor(fetcher=globalThis.fetch){this.fetcher=fetcher.bind(globalThis);}
  get pending(){return this.#pending!==null;}
  get expiresAt(){return this.#expires;}
  get authenticated(){return !!this.#token;}
  clear(){this.#generation++;for(const controller of this.#controllers)controller.abort();this.#controllers.clear();this.#token='';this.#expires='';this.#pending=null;}
  async request(path,{method='GET',body,publicRequest=false,binary=false}={}){
    const allowed={'POST /sessions':true,'POST /logout':true,'GET /offer':true,'GET /offer/pdf':true,'POST /offer/decision':true};
    if(!allowed[method+' '+path]||publicRequest!==(path==='/sessions'))throw new PortalError('Ungültiger Portalaufruf.',400);
    if(!publicRequest&&(!this.#token||Date.parse(this.#expires)<=Date.now())){this.clear();throw new PortalError(message(401),401);}
    const generation=this.#generation,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000),maximum=binary?21*1024*1024:1024*1024;
    this.#controllers.add(controller);
    try{
      const response=await this.fetcher('/api/v1/portal'+path,{method,headers:{Accept:binary?'application/pdf':'application/json',...(body===undefined?{}:{'Content-Type':'application/json'}),...(publicRequest?{}:{Authorization:'Bearer '+this.#token})},
        ...(body===undefined?{}:{body:JSON.stringify(body)}),credentials:'omit',redirect:'error',cache:'no-store',referrerPolicy:'no-referrer',signal:controller.signal});
      if(generation!==this.#generation)throw new PortalError('Die Portalsitzung wurde beendet.',401);
      if(Number(response.headers.get('Content-Length'))>maximum)throw new PortalError('Die Serverantwort ist zu groß.',502);
      const reader=response.body?.getReader(),chunks=[];let size=0;
      if(reader){for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>maximum){await reader.cancel();throw new PortalError('Die Serverantwort ist zu groß.',502);}chunks.push(value);}}
      else{const value=new Uint8Array(await response.arrayBuffer());size=value.length;chunks.push(value);}
      if(size>maximum)throw new PortalError('Die Serverantwort ist zu groß.',502);
      if(generation!==this.#generation)throw new PortalError('Die Portalsitzung wurde beendet.',401);
      if(!response.ok){if([401,403,404,410].includes(response.status)&&!publicRequest)this.clear();throw new PortalError(message(response.status),response.status);}
      if(response.status!==(method==='POST'&&path!=='/logout'?201:200))throw new PortalError('Keine abschließende Serverbestätigung erhalten. Bitte unverändert erneut versuchen.',502);
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
      if(binary){if(new TextDecoder().decode(bytes.subarray(0,5))!=='%PDF-')throw new PortalError('Das Original-PDF konnte nicht geprüft werden.',502);return new Blob([bytes],{type:'application/pdf'});}
      try{return JSON.parse(new TextDecoder().decode(bytes));}catch{throw new PortalError('Keine lesbare Bestätigung erhalten. Bitte unverändert erneut versuchen.',502);}
    }catch(error){if(error instanceof PortalError)throw error;throw new PortalError(message(0));}
    finally{clearTimeout(timer);this.#controllers.delete(controller);}
  }
  async open(invite){
    this.clear();if(!invite||!ID.test(invite.grant_id||'')||!tokenValue(invite.key,'SPPI_'))throw new PortalError('Bitte den vollständigen Kundenlink öffnen.',400);
    const generation=this.#generation,result=await this.request('/sessions',{method:'POST',publicRequest:true,body:{grant_id:invite.grant_id,key:invite.key}});
    if(generation!==this.#generation)throw new PortalError('Die Portalsitzung wurde beendet.',401);
    if(!tokenValue(result.token,'SPPT_')||!Number.isFinite(Date.parse(result.expires_at))||Date.parse(result.expires_at)<=Date.now())throw new PortalError('Der Zugang wurde nicht sicher bestätigt. Bitte den Kundenlink erneut öffnen.',502);
    this.#token=result.token;this.#expires=result.expires_at;return {expires_at:this.#expires};
  }
  async view(){const generation=this.#generation,result=portalView(await this.request('/offer'));if(generation!==this.#generation)throw new PortalError('Die Portalsitzung wurde beendet.',401);if(result.decision)this.#pending=null;return result;}
  pdf(){return this.request('/offer/pdf',{binary:true});}
  async logout(){const generation=this.#generation;try{if(this.#token)await this.request('/logout',{method:'POST',body:{}});}finally{if(generation===this.#generation)this.clear();}}
  async decide(view,values){
    if(view.decision)throw new PortalError(message(409),409);
    if(!view.actions_allowed)throw new PortalError(message(423),423);
    const payload=portalDecisionPayload(view,values,this.#pending?.payload.request_id||crypto.randomUUID().replaceAll('-','')),fingerprint=JSON.stringify(payload);
    if(this.#pending&&this.#pending.fingerprint!==fingerprint)throw new PortalError('Die vorige Antwort ist unklar. Bitte zuerst die unveränderte Erklärung erneut senden.');
    const generation=this.#generation;this.#pending={payload,fingerprint};
    try{
      const receipt=portalDecisionReceipt(await this.request('/offer/decision',{method:'POST',body:payload}));
      if(generation!==this.#generation)throw new PortalError('Die Portalsitzung wurde beendet.',401);
      if(receipt.offer_id!==view.offer.id||receipt.decision!==payload.decision||receipt.declared_name!==payload.declared_name||receipt.content_hash!==payload.content_hash||receipt.pdf_hash!==payload.pdf_hash||receipt.statement_version!==payload.statement_version||receipt.statement_text!==view.statements[payload.decision])
        throw new PortalError('Die Erklärung wurde noch nicht sicher bestätigt. Bitte unverändert erneut versuchen.',502);
      this.#pending=null;return receipt;
    }catch(error){if(generation===this.#generation&&error.status>=400&&error.status<500&&![423,429].includes(error.status))this.#pending=null;throw error;}
  }
}

const money=value=>typeof value==='string'&&/^-?\d+(\.\d+)?$/.test(value)?value.replace('.',',')+' €':'—';
const quantity=value=>typeof value==='string'?value.replace('.',','):'—';
const date=value=>Number.isFinite(Date.parse(value))?new Intl.DateTimeFormat('de-DE',{dateStyle:'medium',...(value?.includes('T')?{timeStyle:'short'}:{})}).format(new Date(value)):'—';
function node(tag,attributes={},...children){
  const result=document.createElement(tag);
  for(const [key,value]of Object.entries(attributes)){
    if(key.startsWith('on'))result.addEventListener(key.slice(2).toLowerCase(),value);
    else if(key==='class')result.className=value;
    else if(value!==undefined&&value!==false){if(key in result)result[key]=value;else result.setAttribute(key,value===true?'':value);}
  }
  for(const child of children.flat()){if(child!==null&&child!==undefined)result.append(child instanceof Node?child:document.createTextNode(String(child)));}
  return result;
}
const actionButton=(label,run,primary=false)=>node('button',{type:'button',class:primary?'primary':'',onClick:run},label);
const notice=(value,error=false)=>node('p',{class:error?'notice error':'notice',role:error?'alert':'status'},value);
function party(title,value,issuer=false){
  return node('section',{class:'card party'},node('h2',{},title),node('strong',{},issuer?value.company_name:value.name),
    !issuer&&value.contact_name?node('p',{},value.contact_name):null,
    node('p',{class:'preserve'},[value.address_line,[value.postal_code,value.city].filter(Boolean).join(' '),value.country].filter(Boolean).join('\n')),
    ['email','phone','website','vat_id','tax_number'].filter(key=>value[key]).map(key=>node('p',{},({vat_id:'USt-IdNr.: ',tax_number:'Steuernummer: '}[key]||'')+value[key])));
}
if(typeof document!=='undefined'){
  const root=document.getElementById('portal-main'),client=new PortalClient(),urls=new Set();let version=0,expiryTimer,draft=null,currentView=null;
  function clear(){version++;clearTimeout(expiryTimer);for(const url of urls)URL.revokeObjectURL(url);urls.clear();client.clear();draft=null;currentView=null;invitation=null;}
  function unavailable(error){root.replaceChildren(node('section',{class:'card'},node('h1',{},'Kundenzugang'),notice(error?.message||'Bitte den vollständigen Kundenlink erneut öffnen.',!!error),
    node('p',{},'Der Link öffnet ausschließlich das freigegebene Angebot. Zugangsdaten werden in diesem Browserfenster nicht dauerhaft gespeichert.')));}
  async function load(){const attempt=++version;try{const view=await client.view();if(attempt!==version)return;currentView=view;render(view);}catch(error){if(attempt!==version)return;if(!client.authenticated)unavailable(error);else root.prepend(notice(error.message,true));}}
  async function downloadPdf(view,button){button.disabled=true;try{const blob=await client.pdf(),url=URL.createObjectURL(blob);urls.add(url);
    const link=node('a',{href:url,download:(view.offer.number||'Angebot').replace(/[^a-z0-9._-]/gi,'_')+'.pdf'});document.body.append(link);link.click();link.remove();
    setTimeout(()=>{URL.revokeObjectURL(url);urls.delete(url);},30000);
  }catch(error){if(!client.authenticated)unavailable(error);else root.prepend(notice(error.message,true));}finally{button.disabled=false;}}
  function receipt(value){return node('section',{class:'card'},node('h2',{},value.decision==='accepted'?'Annahme dokumentiert':'Ablehnung dokumentiert'),
    notice('Ihre Erklärung wurde gespeichert.'),node('p',{},value.declared_name+' · '+date(value.created_at)),node('p',{class:'preserve'},value.statement_text));}
  function decisionForm(view,choice){
    draft=draft?.decision===choice?draft:{decision:choice,declared_name:'',confirmation:false};
    const name=node('input',{type:'text',id:'declared-name',name:'declared_name',maxLength:200,required:true,autoComplete:'name',value:draft.declared_name}),
      confirm=node('input',{type:'checkbox',id:'decision-confirmation',required:true,checked:draft.confirmation}),
      submit=node('button',{type:'submit',class:choice==='accepted'?'primary':'',},choice==='accepted'?'Annahme verbindlich erklären':'Ablehnung verbindlich erklären'),errors=node('div',{}),
      form=node('form',{},node('h2',{},choice==='accepted'?'Angebot annehmen':'Angebot ablehnen'),
        node('p',{},view.offer.number+' · Fassung '+view.offer.revision+' · Gesamtbetrag '+money(view.offer.totals.gross)),
        node('p',{class:'statement preserve'},view.statements[choice]),node('label',{htmlFor:'declared-name'},'Ihr vollständiger Name',name),
        node('label',{class:'check',htmlFor:'decision-confirmation'},confirm,'Ich bestätige diese Erklärung zum angezeigten Angebot.'),
        node('p',{class:'muted'},'Ihr eingegebener Name wird zusammen mit dieser Erklärung und der Angebotsfassung gespeichert.'),
        node('div',{class:'actions'},submit,actionButton('Zur Angebotsansicht',()=>{if(!client.pending){draft=null;render(view);}})),errors);
    function pending(){name.disabled=client.pending;confirm.disabled=client.pending;if(client.pending)submit.textContent='Unverändert erneut senden';}
    pending();form.addEventListener('submit',async event=>{
      event.preventDefault();if(submit.disabled)return;errors.replaceChildren();submit.disabled=true;
      const attempt=version;draft={decision:choice,declared_name:name.value,confirmation:confirm.checked};
      try{const result=await client.decide(view,draft);if(attempt!==version||!form.isConnected)return;draft=null;currentView={...view,decision:result,actions_allowed:false};render(currentView);}
      catch(error){if(attempt!==version||!form.isConnected)return;if(!client.authenticated){unavailable(error);return;}if(error.status===409){draft=null;await load();return;}errors.replaceChildren(notice(error.message,true));pending();}
      finally{submit.disabled=false;}
    });return node('section',{class:'card decision'},form);
  }
  function render(view){
    const offer=view.offer,pdf=actionButton('Original-PDF herunterladen',()=>downloadPdf(view,pdf)),
      top=node('header',{},node('div',{},node('p',{class:'eyebrow'},'KUNDENANGEBOT'),node('h1',{},offer.title),node('p',{class:'muted'},offer.number+' · Fassung '+offer.revision)),
        node('div',{class:'actions'},actionButton('Ansicht aktualisieren',()=>load()),actionButton('Zugang beenden',async()=>{const attempt=++version;root.replaceChildren(notice('Zugang wird beendet …'));try{await client.logout();}catch{}finally{if(attempt===version){clear();unavailable();}}}))),
      positions=node('div',{class:'table-scroll',role:'region',tabIndex:0,'aria-label':'Angebotspositionen'},node('table',{},
        node('thead',{},node('tr',{},['Position','Menge','Netto je Preiseinheit','Rabatt','MwSt.','Netto'].map(title=>node('th',{scope:'col'},title)))),
        node('tbody',{},offer.positions.map(line=>node('tr',{},node('td',{class:'preserve'},line.description),node('td',{},quantity(line.quantity)+' '+line.unit),
          node('td',{},money(line.unit_price_net)+' / '+quantity(line.price_base_quantity)+' '+line.unit),node('td',{},quantity(line.discount_percent)+' %'),
          node('td',{},quantity(line.tax_rate)+' %',line.tax_exemption_reason?node('p',{},line.tax_exemption_reason):null),node('td',{},money(line.net))))))),
      totals=node('section',{class:'card totals'},node('h2',{},'Angebotssumme'),node('p',{},'Netto: '+money(offer.totals.net)),node('p',{},'Steuer: '+money(offer.totals.tax)),
        node('strong',{},'Gesamtbetrag: '+money(offer.totals.gross)),offer.totals.payable&&offer.totals.payable!==offer.totals.gross?node('p',{},'Zahlbetrag laut Angebot: '+money(offer.totals.payable)):null,
        offer.totals.tax_breakdown.map(line=>node('p',{class:'muted'},quantity(line.rate)+' % · Basis '+money(line.net)+' · Steuer '+money(line.tax)+(line.reason?' · '+line.reason:''))));
    root.replaceChildren(top,notice('Zugang verfügbar bis '+date(view.expires_at)+'. Bitte vor einer Erklärung das Angebot einschließlich Original-PDF prüfen.'),
      node('div',{class:'parties'},party('Ausgestellt von',offer.issuer,true),party('Angebot für',offer.buyer)),
      node('section',{class:'card'},node('div',{class:'actions'},pdf),node('p',{},'Belegdatum: '+date(offer.issue_date)+' · Datum laut Angebot: '+date(offer.due_date)),node('p',{class:'preserve'},offer.intro),positions),totals,
      node('section',{class:'card'},node('h2',{},'Hinweise und Bedingungen'),node('p',{class:'preserve'},offer.notes),node('p',{class:'preserve'},offer.issuer.payment_terms||''),
        offer.issuer.iban?node('p',{},'IBAN: '+offer.issuer.iban+(offer.issuer.bic?' · BIC: '+offer.issuer.bic:'')):null,node('p',{class:'preserve'},offer.issuer.footer||'')),
      view.decision?receipt(view.decision):draft?decisionForm(view,draft.decision):view.actions_allowed?
        node('section',{class:'card'},node('h2',{},'Ihre Entscheidung'),node('p',{},'Wählen Sie eine Erklärung. Gespeichert wird sie erst nach Ihrer ausdrücklichen Bestätigung.'),
          node('div',{class:'actions'},actionButton('Angebot annehmen',()=>{draft={decision:'accepted',declared_name:'',confirmation:false};render(view);root.querySelector('#declared-name').focus();},true),
            actionButton('Angebot ablehnen',()=>{draft={decision:'declined',declared_name:'',confirmation:false};render(view);root.querySelector('#declared-name').focus();}))):notice('Neue Erklärungen sind derzeit nicht freigegeben. Das Angebot bleibt hier lesbar.'));
    clearTimeout(expiryTimer);expiryTimer=setTimeout(()=>{clear();unavailable(new PortalError(message(401),401));},Math.max(0,Date.parse(client.expiresAt)-Date.now()));
  }
  async function open(){const attempt=++version;root.replaceChildren(notice('Kundenzugang wird geprüft …'));
    try{await client.open(invitation);if(attempt!==version)return;invitation=null;await load();}
    catch(error){if(attempt!==version)return;unavailable(error);if(invitation&&![400,401,403,404,410].includes(error.status))root.append(actionButton('Zugang erneut öffnen',()=>open()));else invitation=null;}
  }
  if(invitationError)unavailable(invitationError);else if(invitation)open();else unavailable();
  addEventListener('beforeunload',event=>{if(client.pending){event.preventDefault();event.returnValue='';}});
  addEventListener('pagehide',()=>clear());addEventListener('pageshow',event=>{if(event.persisted)unavailable();});
}
