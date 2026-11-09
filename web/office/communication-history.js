/* Read-only, source-bound customer/project communication. No provider actions. */
export const historyKinds={inquiry:'Anfragen',sales:'Vertrieb und Aktivitäten',service:'Kundenservice',document:'Belegstände',delivery:'Belegversand',project_note:'Projektnotizen'};
const ID=/^[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/;
const fail=message=>Object.assign(new Error(message),{status:502});
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const keys=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&equal(Object.keys(v).sort(),[...k].sort());
const nullableId=v=>v===null||typeof v==='string'&&ID.test(v);
const provenance={inquiry:['received_inquiry','recorded_inquiry'],sales:['canonical_record','manual_activity'],service:['canonical_record','manual_activity'],document:['current_document_revision'],delivery:['mail_outbox','mail_receipt'],project_note:['internal_project_note']};
export function historyStatus(item){const common={recorded_activity:'Protokollierte Aktivität',recorded_note:'Interne Notiz',draft:'Entwurf',final:'Abgeschlossen',new:'Neu',qualified:'Qualifiziert',proposal:'Angebotsphase',negotiation:'Verhandlung',won:'Gewonnen',lost:'Verloren',open:'Offen',triaged:'Geprüft',planned:'Geplant',in_progress:'In Bearbeitung',waiting_customer:'Rückmeldung des Kunden offen',waiting_supplier:'Rückmeldung des Lieferanten offen',resolved:'Gelöst',closed:'Abgeschlossen',cancelled:'Abgebrochen',callback:'Rückruf',review:'In Prüfung',offer:'Angebot',awaiting_acceptance:'Zusage offen',accepted:'Zusage vermerkt',declined:'Abgelehnt',converted:'In Projekt übernommen'};const delivery={pending:'Vorbereitet',sending:'Versand läuft',accepted:'Vom Versandserver angenommen',failed:'Versand fehlgeschlagen',unknown:'Versand ungeklärt',not_sent:'Nicht versendet bestätigt'};return (item.kind==='delivery'?delivery:common)[item.status]||item.status;}
const order=i=>[i.precision==='day'?i.occurred_at+'T00:00:00+00:00':i.occurred_at,i.key].join('|');
function day(v){return typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;}
function stamp(v){return typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,19)===v.slice(0,19);}

export function communicationHistoryPage(value,scope,previous=null){
  if(!keys(value,['schema_version','scope','snapshot_sha256','customer','project','items','next_cursor','has_more','page_size','limitations'])||value.schema_version!==1||!HASH.test(value.snapshot_sha256||''))throw fail('Der Kommunikationsverlauf besitzt keinen eindeutigen Quellstand.');
  const s=value.scope;
  if(!keys(s,['customer_id','project_id','kind','q','from','to'])||!nullableId(s.customer_id)||!nullableId(s.project_id)||!s.customer_id&&!s.project_id||s.project_id!==(scope.project_id||null)||scope.customer_id&&s.customer_id!==scope.customer_id||s.kind!==(scope.kind||null)||s.q!==String(scope.q||'').trim()||s.from!==(scope.from||null)||s.to!==(scope.to||null))throw fail('Der Verlauf gehört nicht zu diesem Kunden, Projekt oder Filter.');
  for(const [name,id]of [['customer',s.customer_id],['project',s.project_id]])if(id===null?value[name]!==null:!keys(value[name],['id','name'])||value[name].id!==id||typeof value[name].name!=='string'||!value[name].name)throw fail('Der kanonische Kunden-/Projektbezug fehlt.');
  if(!Array.isArray(value.items)||!Number.isSafeInteger(value.page_size)||value.page_size!==Number(scope.limit||50)||value.page_size<1||value.page_size>100||value.items.length>value.page_size||typeof value.has_more!=='boolean'||value.has_more!==Boolean(value.next_cursor)||value.next_cursor!==null&&(typeof value.next_cursor!=='string'||!/^[A-Za-z0-9_-]{1,1400}$/.test(value.next_cursor))||!Array.isArray(value.limitations)||value.limitations.some(v=>typeof v!=='string'))throw fail('Die Verlaufsseite ist unvollständig.');
  const all=[...(previous?.items||[])],seen=new Set(all.map(i=>i.key));
  if(previous&&(['customer_id','project_id','kind','q','from','to'].some(key=>previous.scope[key]!==s[key])||previous.snapshot_sha256!==value.snapshot_sha256||!previous.has_more))throw fail('Der Verlauf wurde zwischen den Seiten verändert. Bitte neu laden.');
  for(const item of value.items){
    if(!keys(item,['key','kind','source_id','source_revision','source_sha256','project_ids','title','text','occurred_at','precision','recorded_at','status','provenance','supersedes_key','superseded','accepted_by_server','recipient_delivery_confirmed'])||!Object.hasOwn(historyKinds,item.kind)||!provenance[item.kind].includes(item.provenance)||!ID.test(item.source_id||'')||!Number.isSafeInteger(item.source_revision)||item.source_revision<0||item.source_revision===0&&item.provenance!=='mail_outbox'||item.key!==`${item.kind}:${item.provenance}:${item.source_id}:${item.source_revision}`||seen.has(item.key)||!HASH.test(item.source_sha256||'')||!Array.isArray(item.project_ids)||new Set(item.project_ids).size!==item.project_ids.length||item.project_ids.some(v=>!ID.test(v))||s.project_id&&!item.project_ids.includes(s.project_id)||typeof item.title!=='string'||Array.from(item.title).length>500||typeof item.text!=='string'||Array.from(item.text).length>40000||typeof item.status!=='string'||!['day','second'].includes(item.precision)||!(item.precision==='day'?day(item.occurred_at):stamp(item.occurred_at))||!stamp(item.recorded_at)||typeof item.superseded!=='boolean'||item.supersedes_key!==null&&(typeof item.supersedes_key!=='string'||!item.supersedes_key.startsWith(item.kind+':manual_activity:'))||typeof item.accepted_by_server!=='boolean'||item.accepted_by_server!==(item.kind==='delivery'&&item.status==='accepted')||item.recipient_delivery_confirmed!==false)throw fail('Ein Verlaufseintrag widerspricht seinem Ursprung oder Nachweis.');
    if(all.length&&order(all.at(-1))<=order(item))throw fail('Die Reihenfolge des Verlaufs ist nicht eindeutig.');
    seen.add(item.key);all.push(item);
  }
  if(value.has_more&&!value.items.length)throw fail('Eine leere Seite darf keine weitere Seite behaupten.');
  return {...value,items:all};
}

export function createCommunicationHistory(h){
  const {api,biz,el,button,notice,formatDate,action}=h,instances=new Set();
  let opening=0;
  const active=()=>{if(!h.allowed()||globalThis.document?.hidden)throw Object.assign(new Error('Der aktuelle Zugang zum Kommunikationsverlauf fehlt.'),{status:403});};
  async function fresh(scope){
    active();const caps=await api.get(biz('/capabilities')+(scope.project_id?'?project_id='+encodeURIComponent(scope.project_id):''));active();
    if(!caps.permissions?.includes('contacts.read')||!caps.features?.includes('communication_history')||!caps.capabilities?.includes('business_sales'))throw Object.assign(new Error('Die aktuelle Lesefreigabe für den Kommunikationsverlauf fehlt.'),{status:403});
    return JSON.stringify({generation:caps.generation,permissions:[...caps.permissions].sort(),features:[...caps.features].sort(),capabilities:[...caps.capabilities].sort()});
  }
  function clear(root=null){if(!root)opening++;for(const state of instances)if(!root||root.contains(state.node)){state.clear();if(!state.node.isConnected)instances.delete(state);}}
  globalThis.document?.addEventListener('visibilitychange',()=>{if(document.hidden)clear();});
  globalThis.window?.addEventListener('pagehide',()=>clear());
  async function view(scope,heading=true){
    active();for(const state of instances)if(state.loaded&&!state.node.isConnected){state.clear();instances.delete(state);}
    const stamp=h.stamp(),node=el('section',{class:'communication-history stack','aria-label':'Kommunikationsverlauf'}),results=el('div',{'aria-live':'polite',class:'stack'});
    let page=null,sequence=0,filters={},loading=false;
    const q=el('input',{type:'search','aria-label':'Kommunikationsverlauf durchsuchen',maxLength:200}),kind=el('select',{'aria-label':'Verlaufsquelle'},el('option',{value:''},'Alle Quellen'),...Object.entries(historyKinds).map(([key,name])=>el('option',{value:key},name))),from=el('input',{type:'date','aria-label':'Verlauf ab'}),to=el('input',{type:'date','aria-label':'Verlauf bis'});
    const form=el('form',{class:'form-grid'},el('label',{class:'field'},'Suche',q),el('label',{class:'field'},'Quelle',kind),el('label',{class:'field'},'Ab',from),el('label',{class:'field'},'Bis',to),el('button',{type:'submit',class:'button primary'},'Verlauf filtern'));
    form.addEventListener('submit',event=>{event.preventDefault();filters={...(q.value?{q:q.value}:{}),...(kind.value?{kind:kind.value}:{}),...(from.value?{from:from.value}:{}),...(to.value?{to:to.value}:{})};action(()=>load());});
    const state={node,loaded:false,clear(){sequence++;page=null;loading=false;q.value=kind.value=from.value=to.value='';filters={};results.replaceChildren(notice('Der private Verlauf wurde ausgeblendet. Zum Fortsetzen neu laden.'));}};
    instances.add(state);
    function render(){
      results.replaceChildren(el('p',{class:'muted'},page.project?'Projekt: '+page.project.name:'Kunde: '+page.customer.name),
        el('details',{},el('summary',{},'Hinweise zu Quellen und Nachweisen'),...page.limitations.map(v=>el('p',{class:'caption'},v))),
        ...(page.items.length?page.items.map(item=>el('article',{class:'panel stack','data-history-key':item.key},
          el('h3',{},item.title),el('p',{class:'muted'},historyKinds[item.kind]+' · '+formatDate(item.occurred_at,item.precision==='second')+(item.precision==='day'?' · ohne belegte Uhrzeit':'')),
          el('p',{},historyStatus(item)),item.provenance==='manual_activity'?el('p',{class:'caption'},'Manuell protokolliert; kein Versandnachweis.'):null,
          item.superseded?notice('Dieser Originaleintrag wurde korrigiert. Die spätere Korrektur bleibt ein eigener Nachweis.'):null,
          item.text?el('p',{class:'history-text'},item.text):null,
          item.kind==='delivery'?el('p',{class:'caption'},'Zustellung und Lesen sind nicht bestätigt.'):null,
          item.project_ids.length&&!scope.project_id?el('div',{class:'actions'},...item.project_ids.map(id=>button('Projekt öffnen',()=>h.openProject(id),'small'))):null,
          el('small',{},'Erfasst: '+formatDate(item.recorded_at,true)))):[notice('Keine freigegebenen Einträge für diese Auswahl vorhanden.')]),
        page.has_more?button('Weitere Einträge laden',()=>action(()=>load(true))):null);
    }
    async function load(next=false){
      if(loading&&next)return;loading=true;const connected=node.isConnected,ticket=++sequence,previous=next?page:null,params=Object.fromEntries(Object.entries({...scope,...filters,limit:'50',...(previous?{cursor:previous.next_cursor}:{})}).filter(([,v])=>v!==null&&v!==undefined));
      results.replaceChildren(notice('Kommunikationsverlauf wird geladen.'));
      try{
        const before=await fresh(scope),value=await api.get(biz('/sales/communication-history')+'?'+new URLSearchParams(params));
        const after=await fresh(scope);
        if(ticket!==sequence||stamp!==h.stamp())return;
        if(connected&&!node.isConnected){state.clear();return;}
        if(before!==after)throw new Error('Die Leserechte wurden während des Abrufs geändert. Bitte neu laden.');
        page=communicationHistoryPage(value,params,previous);state.loaded=true;render();
      }catch(error){if(ticket===sequence&&stamp===h.stamp()){page=null;results.replaceChildren(notice(error.message||String(error),'warn'));}}
      finally{if(ticket===sequence)loading=false;}
    }
    node.append(...(heading?[el('h2',{},'Kommunikationsverlauf')]:[]),form,button('Verlauf neu laden',()=>action(()=>load())),results);
    await load();return node;
  }
  async function open(customerId){const stamp=h.stamp(),ticket=++opening,content=await view({customer_id:customerId},false);active();if(stamp===h.stamp()&&ticket===opening)h.dialog('Kommunikationsverlauf',content);}
  return {view,open,clear};
}
