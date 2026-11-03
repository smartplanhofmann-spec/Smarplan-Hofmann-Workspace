/* Explicit typed additions; historical field meanings remain visible. */
const ID=/^[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/;
export const CUSTOM_TYPES={text:'Text',number:'Zahl',date:'Datum',choice:'Auswahl',boolean:'Ja / Nein'};
export const CUSTOM_ENTITIES={contact:'Kontakte',project:'Projekte',asset:'Geräte'};
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
export const customSame=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const copy=v=>JSON.parse(JSON.stringify(v));
function fail(){throw new Error('Zusatzfeld-Fassung oder Bestätigung stimmt nicht mit dem geprüften Vorgang überein.');}
export function customValue(definition,input,previous=null){
  let value=input===undefined||input===''?null:input;
  if(value===null){if(definition.required)throw new Error('Pflichtfeld „'+definition.label+'“ ausfüllen.');return null;}
  switch(definition.field_type){
    case 'text':if(typeof value!=='string'||value.length>4000||/[\x00-\x08\x0b-\x1f]/.test(value)||definition.required&&!value.trim())fail();break;
    case 'number':value=String(value).trim().replace(',','.');if(typeof input!=='string'||!/^-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?$/.test(value))throw new Error('Exakte Zahl mit höchstens zwölf Vor- und sechs Nachkommastellen eingeben.');break;
    case 'date':{const date=new Date(value+'T00:00:00Z');if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==value||value<'1900-01-01'||value>'2200-12-31')fail();break;}
    case 'boolean':if(value==='true')value=true;else if(value==='false')value=false;if(typeof value!=='boolean')fail();break;
    case 'choice':if(!definition.options.some(o=>o.id===value&&(o.active||value===previous)))throw new Error('Eine aktive Auswahl wählen; archivierte Auswahl darf unverändert bleiben.');break;
    default:fail();
  }return value;
}
export function customDisplay(item){if(!item||item.value===null)return 'Nicht erfasst';if(item.definition.field_type==='boolean')return item.value?'Ja':'Nein';if(item.definition.field_type==='choice')return item.definition.options.find(o=>o.id===item.value)?.label||'Unbekannte Auswahl';return String(item.value);}
export function customDefinition(raw){
  if(!raw||!ID.test(raw.id||'')||!Number.isSafeInteger(raw.revision)||raw.revision<1||!HASH.test(raw.content_hash||'')||!Object.hasOwn(CUSTOM_ENTITIES,raw.entity_type)||!Object.hasOwn(CUSTOM_TYPES,raw.field_type)||typeof raw.label!=='string'||!raw.label||typeof raw.help_text!=='string'||typeof raw.active!=='boolean'||typeof raw.required!=='boolean'||!Array.isArray(raw.options)||raw.options.some(o=>!ID.test(o.id||'')||typeof o.label!=='string'||typeof o.active!=='boolean'))fail();return raw;
}
export function customSnapshot(raw,type,id){
  if(raw?.entity?.entity_type!==type||raw.entity.id!==id||!Array.isArray(raw.definitions)||!HASH.test(raw.definitions_hash||'')||typeof raw.can_write!=='boolean'||!Array.isArray(raw.missing_required)||typeof raw.complete!=='boolean')fail();
  raw.definitions.forEach(d=>{customDefinition(d);if(d.entity_type!==type)fail();});
  const current=raw.current;if(!current||current.entity_type!==type||current.entity_id!==id||!Number.isSafeInteger(current.revision)||current.revision<0||!current.values||Array.isArray(current.values))fail();
  if(current.revision&&!HASH.test(current.content_hash||''))fail();
  for(const [key,item]of Object.entries(current.values)){customDefinition(item.definition);if(item.definition.id!==key||item.definition.entity_type!==type)fail();customValue(item.definition,item.value,item.value);}
  return raw;
}
export function customReceipt(body,previous=null,snapshot=null){const frozen=copy(body),prior=previous?copy(previous):null,view=snapshot?copy(snapshot):null;return raw=>{
  if(!raw||raw.revision!==frozen.revision+1||raw.previous_hash!==(prior?.content_hash||null)||!HASH.test(raw.content_hash||'')||!ID.test(raw.created_by||'')||typeof raw.created_at!=='string'||raw.reason!==frozen.reason)fail();
  if(frozen.definition){customDefinition(raw);if(frozen.id&&raw.id!==frozen.id)fail();for(const [key,value]of Object.entries(frozen.definition))if(!customSame(raw[key],value))fail();}
  else{if(!view||raw.entity_type!==view.entity.entity_type||raw.entity_id!==view.entity.id||raw.definitions_hash!==frozen.definitions_hash||!customSame(raw.definitions,view.definitions))fail();const expected=copy(prior?.values||{});for(const definition of view.definitions.filter(d=>d.active))expected[definition.id]={definition,value:frozen.values[definition.id]};if(!customSame(raw.values,expected))fail();}
};}
export async function customFieldsPendingAuthorize(api,{key,path}){
  const body=api.pendingCommandValues(key,path);if(!body)throw new Error('Unveränderter Zusatzfeld-Vorgang fehlt.');
  const caps=await api.get('/business/capabilities');
  if(caps.readonly!==false||!caps.features?.includes('custom_fields')||!caps.capabilities?.includes('business_custom_fields'))throw new Error('Die aktuelle Freigabe für Zusatzfelder fehlt.');
  if(path==='/business/custom-fields/definitions'){
    if(!caps.permissions?.includes('settings.manage'))throw new Error('Die aktuelle Einstellungsberechtigung fehlt.');
    const result=await api.get(path);if(!Array.isArray(result.items))fail();result.items.forEach(customDefinition);return;
  }
  const match=path.match(/^\/business\/custom-fields\/entities\/(contact|project|asset)\/([a-f0-9]{32})$/);
  if(!match)throw new Error('Unbekannter Zusatzfeld-Vorgang.');
  const view=customSnapshot(await api.get(path),match[1],match[2]);
  if(view.can_write!==true)throw new Error('Die aktuelle Schreibberechtigung für diesen Datensatz fehlt.');
}
export function customFieldsUi(h){
  const {api,biz,el,button,field,form,dialog,panel,rows,row,notice,table,mutation,action}=h;
  const enabled=()=>h.enabled();
  async function get(url){const stamp=h.stamp();const result=await api.get(url);if(stamp!==h.stamp())throw new Error('Sitzung oder Freigaben wurden geändert.');return result;}
  function check(admin=false){if(!enabled()||admin&&!h.admin())throw new Error('Die aktuelle Freigabe für Zusatzfelder fehlt.');}
  function show(title,content){check();content.setAttribute('data-custom-fields','true');return dialog(title,content,'Zusatzwerte ergänzen den Datensatz. Sie verändern keine Kernfelder, Rechte, Steuern oder Kennzahlen.');}
  const path=(type,id)=>`/custom-fields/entities/${type}/${id}`;
  function historyTable(events,definitions=false){return el('div',{class:'stack'},events.map(event=>panel(`Fassung ${event.revision} · ${event.created_at}`,el('p',{},event.reason||'Ersterfassung'),definitions?table(['Angabe','Stand'],[['Name',event.label],['Feldart',CUSTOM_TYPES[event.field_type]],['Status',event.active?'Aktiv':'Archiviert'],['Pflichtfeld',event.required?'Ja':'Nein'],['Ausfüllhilfe',event.help_text],...event.options.map(o=>['Auswahl',o.label+(o.active?'':' (archiviert)')])]):table(['Feld','Wert'],Object.values(event.values).map(item=>[item.definition.label,customDisplay(item)])))));}
  async function history(type,id,definition=false,before=null){check(definition);const result=await get(biz((definition?`/custom-fields/definitions/${id}`:path(type,id))+'/history')+(before?'?before_revision='+before:''));check(definition);show('Zusatzfelder · Historie',el('div',{class:'stack'},historyTable(result.items,definition),result.next_before_revision?button('Ältere Fassungen',()=>action(()=>history(type,id,definition,result.next_before_revision))):null));}
  async function open(type,id){check();const view=customSnapshot(await get(biz(path(type,id))),type,id);check();const body=el('div',{class:'stack'},notice(view.complete?'Alle aktuell definierten Pflichtfelder sind ausgefüllt.':'Pflichtangaben fehlen: '+view.definitions.filter(d=>view.missing_required.includes(d.id)).map(d=>d.label).join(', ')),table(['Feld','Wert'],view.definitions.map(d=>[d.label+(d.active?'':' (archiviert)'),customDisplay(view.current.values[d.id])])),button('Änderungshistorie',()=>action(()=>history(type,id))));
    if(view.can_write&&h.writable()){const fields=view.definitions.filter(d=>d.active).map(d=>{const old=view.current.values[d.id]?.value,base={required:d.required,help:d.help_text,keepEmpty:true};if(d.field_type==='boolean')return field(d.id,d.label,'select',old===undefined||old===null?'':String(old),{...base,options:[['','Nicht erfasst'],['true','Ja'],['false','Nein']]});if(d.field_type==='choice')return field(d.id,d.label,'select',old||'',{...base,options:[['','Nicht erfasst'],...d.options.filter(o=>o.active||o.id===old).map(o=>[o.id,o.label+(o.active?'':' (archiviert)')])]});return field(d.id,d.label,d.field_type==='date'?'date':d.field_type==='text'?'textarea':'text',old??'',{...base,maxLength:d.field_type==='text'?4000:30});});fields.push(field('reason','Änderungsgrund','text','',{required:view.current.revision>0,maxLength:1000}));const key=`custom-fields-${type}-${id}`;
      body.append(form('Zusatzwerte bearbeiten',fields,async values=>{check();const fresh=customSnapshot(await get(biz(path(type,id))),type,id);check();if(!fresh.can_write||!h.writable())throw new Error('Die aktuelle Schreibfreigabe fehlt.');const frozen=api.pendingCommandValues(key,biz(path(type,id)))||{revision:view.current.revision,definitions_hash:view.definitions_hash,values:Object.fromEntries(view.definitions.filter(d=>d.active).map(d=>[d.id,customValue(d,values[d.id],view.current.values[d.id]?.value)])),reason:String(values.reason||'').trim()};return mutation(key,path(type,id),frozen,{validate:customReceipt(frozen,view.current,view)});},{key,after:()=>open(type,id)}));}
    show('Zusatzfelder · '+view.entity.label,body);
  }
  async function definitions(){check(true);const result=await get(biz('/custom-fields/definitions'));check(true);show('Zusatzfelder verwalten',el('div',{class:'stack'},notice('Pflichtangaben gelten erst nach ausdrücklicher Aktivierung. Bestehende leere Werte bleiben sichtbar; gespeicherte Feldarten werden nicht umgedeutet.'),h.writable()?button('Feld anlegen',()=>edit(),'primary'):null,rows(result.items,d=>{customDefinition(d);return row(d.label,`${CUSTOM_ENTITIES[d.entity_type]} · ${CUSTOM_TYPES[d.field_type]} · ${d.active?'Aktiv':'Archiviert'}${d.required?' · Pflichtfeld':''}`,[h.writable()?button('Definition bearbeiten',()=>edit(d),'small'):null,button('Historie',()=>action(()=>history(null,d.id,true)),'small')]);})));}
  function edit(previous=null){check(true);const choices=previous?.options||[],fields=[field('entity_type','Zuordnung','select',previous?.entity_type||'contact',{required:true,options:Object.entries(CUSTOM_ENTITIES)}),field('label','Feldname','text',previous?.label||'',{required:true,maxLength:120}),field('help_text','Ausfüllhilfe','textarea',previous?.help_text||'',{maxLength:1000}),field('field_type','Feldart','select',previous?.field_type||'text',{required:true,options:Object.entries(CUSTOM_TYPES)}),field('required','Als Pflichtfeld aktivieren','checkbox',previous?.required||false),field('active','Feld aktiv','checkbox',previous?.active??true),...choices.flatMap(o=>[field('label_'+o.id,'Auswahlbezeichnung','text',o.label,{required:true,maxLength:120}),field('active_'+o.id,'Auswahl aktiv: '+o.label,'checkbox',o.active)]),field('new_options','Neue Auswahlmöglichkeiten · eine Bezeichnung je Zeile','textarea','',{help:'Nur für Auswahlfelder. Bestehende Auswahlen werden über ihre Aktivierung archiviert.'}),field('reason','Änderungsgrund','text','',{required:!!previous,maxLength:1000})],key='custom-fields-definition-'+(previous?.id||'new');
    show(previous?'Zusatzfeld bearbeiten':'Zusatzfeld anlegen',form('',fields,async values=>{check(true);if(!h.writable())throw new Error('Änderungen sind derzeit gesperrt.');const body=api.pendingCommandValues(key,biz('/custom-fields/definitions'))||{revision:previous?.revision||0,...previous?{id:previous.id}:{},definition:{entity_type:values.entity_type,label:values.label.trim(),help_text:values.help_text.trim(),field_type:values.field_type,required:values.required,active:values.active,options:values.field_type==='choice'?[...choices.map(o=>({id:o.id,label:values['label_'+o.id].trim(),active:values['active_'+o.id]})),...String(values.new_options||'').split('\n').map(s=>s.trim()).filter(Boolean).map(label=>({id:crypto.randomUUID().replaceAll('-',''),label,active:true}))]:[]},reason:values.reason.trim()};return mutation(key,'/custom-fields/definitions',body,{validate:customReceipt(body,previous)});},{key,after:definitions}));
  }
  return {open,definitions};
}
