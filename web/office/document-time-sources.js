/* Existing approved-time import contract. Selecting time only prepares a draft. */
import {ApiError,StaleSession,decimalText} from './office.js';

const id=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const fail=message=>{throw new ApiError(message,502);};
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const changedReceipts=new WeakSet();
export const documentTimesChanged=value=>changedReceipts.has(value);
function decimal(value){const match=/^(-?)(\d+)(?:\.(\d{1,4}))?$/.exec(String(value));if(!match)fail('Der bestätigte Abrechnungssatz ist ungültig.');return (match[1]? -1n:1n)*(BigInt(match[2])*10000n+BigInt((match[3]||'').padEnd(4,'0')));}
function day(value){return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value+'T12:00:00Z'))&&new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value;}
export function documentTimeSources(value){
  if(!Array.isArray(value?.items))fail('Die freigegebenen Zeiten konnten nicht vollständig gelesen werden.');
  const seen=new Set();
  for(const item of value.items){
    if(!id(item?.entry_id)||seen.has(item.entry_id)||!Number.isSafeInteger(item.revision)||item.revision<1||!hash(item.source_hash)||!Number.isSafeInteger(item.net_seconds)||item.net_seconds<0||!day(item.date)||typeof item.label!=='string'||!Array.isArray(item.segments)||!item.segments.length)fail('Eine Zeitquelle enthält keinen gültigen Originalnachweis.');
    let total=0;const dates=new Set();for(const segment of item.segments){if(!day(segment?.work_date)||dates.has(segment.work_date)||!Number.isSafeInteger(segment.net_seconds)||segment.net_seconds<0)fail('Die freigegebenen Tagesanteile sind unvollständig.');dates.add(segment.work_date);total+=segment.net_seconds;}
    if(!Number.isSafeInteger(total)||total!==item.net_seconds||item.date!==item.segments[0].work_date)fail('Die Zeitquelle stimmt nicht mit ihren Tagesanteilen überein.');
    seen.add(item.entry_id);
  }
  return structuredClone(value.items);
}
export function documentTimeRights(caps,project){
  const available=caps?.project_id===project&&caps.capabilities?.includes('business_documents')&&caps.capabilities?.includes('business_time');
  const read=!!available&&['finance.read','documents.read'].every(permission=>caps.permissions?.includes(permission));
  return {read,write:read&&caps.permissions.includes('finance.write')&&caps.readonly===false&&(!(caps.features||[]).includes('organization_modules')||caps.organization?.modules?.documents?.enabled===true)};
}
export async function documentTimeContext(api,project){
  if(!id(project))throw new ApiError('Bitte zuerst das Projekt auswählen.',400);
  const generation=api.generation,caps=await api.get('/business/capabilities?project_id='+project);
  if(generation!==api.generation)throw new StaleSession();
  if(!documentTimeRights(caps,project).write)throw new ApiError('Für diese Zeitübernahme fehlen aktuell Projekt-, Beleg- oder Finanzrechte.',403);
  const projects=await api.get('/projects');if(generation!==api.generation)throw new StaleSession();
  if(!(Array.isArray(projects)?projects:projects?.items||[]).some(item=>item.id===project))throw new ApiError('Das Projekt ist nicht mehr freigegeben.',403);
  return caps;
}
export function documentTimeCommand(key,path,body){return /^document-(?:new|[a-f0-9]{32})$/.test(key)&&/^\/business\/documents(?:\/[a-f0-9]{32})?$/.test(path)&&(Array.isArray(body?.time_entry_ids)&&body.time_entry_ids.length>0||Array.isArray(body?.positions)&&body.positions.some(item=>item?.source_type==='time'));}
export async function documentTimePendingAuthorize(api,operation){
  const body=api.pendingCommandValues(operation.key,operation.path);
  if(!documentTimeCommand(operation.key,operation.path,body))fail('Der ursprüngliche Zeitabrechnungsauftrag fehlt.');
  await documentTimeContext(api,body.project_id);
  // Availability is deliberately not checked here: an accepted original can
  // already have been invoiced. Fresh rights still apply to its exact replay.
}
export function documentTimeUnchanged(selected,current){
  const byId=new Map(current.map(item=>[item.entry_id,item]));
  if(selected.some(item=>!byId.has(item.entry_id)||!same(item,byId.get(item.entry_id))))throw new ApiError('Ausgewählte Arbeitszeiten wurden geändert oder bereits abgerechnet. Bitte die Zeiten neu laden und erneut auswählen.',409);
}
export function documentTimeReceipt(value,{project,identifier,revision,selected,existing,rate,tax}){
  if(!id(value?.id)||identifier&&value.id!==identifier||value.project_id!==project||value.status!=='draft'||value.revision!==(revision||0)+1||!Array.isArray(value.positions))fail('Die Belegantwort gehört nicht zum gespeicherten Entwurf.');
  const positions=value.positions.filter(item=>item.source_type==='time');
  const expected=[...existing.map(item=>item.source_id),...selected.map(item=>item.entry_id)];
  if(new Set(expected).size!==expected.length||positions.length!==expected.length||new Set(positions.map(item=>item.source_id)).size!==expected.length||positions.some(item=>!expected.includes(item.source_id)))fail('Der gespeicherte Entwurf enthält andere Zeitquellen als der Auftrag.');
  const changed=[];
  for(const source of selected){const position=positions.find(item=>item.source_id===source.entry_id);
    if(!hash(position.source_hash)||!Number.isSafeInteger(position.source_revision)||position.source_revision<1||!Number.isSafeInteger(position.source_seconds)||position.source_seconds<0||String(position.quantity)!==String(position.source_seconds)||position.unit!=='SEC'||Number(position.price_base_quantity)!==3600||position.kind!=='labor')fail('Die angenommene Zeitposition ist unvollständig.');
    if(decimal(position.unit_price_net)!==decimal(rate)||decimal(position.tax_rate)!==decimal(tax))fail('Die angenommene Zeitposition verwendet einen anderen Stundensatz oder Steuersatz.');
    // The existing endpoint imports its current original at acceptance. A
    // change between preflight and POST is a visible draft for review, not an
    // unresolvable pending response and never an automatic final invoice.
    if(position.source_hash!==source.source_hash||position.source_revision!==source.revision||position.source_seconds!==source.net_seconds)changed.push(source.entry_id);
  }
  for(const source of existing){const position=positions.find(item=>item.source_id===source.source_id);for(const key of ['source_hash','source_revision','source_seconds','quantity','unit','unit_price_net','price_base_quantity','tax_rate','kind','description'])if(position[key]!==source[key])fail('Eine vorhandene Zeitposition wurde beim Speichern verändert.');}
  if(changed.length)changedReceipts.add(value);
  return changed;
}

export function documentTimePicker({api,el,button,notice,formatDate,stamp,project,positions,onSelect}){
  const root=el('section',{class:'panel stack','data-document-times':''}),body=el('div',{class:'stack'}),selected=new Set();
  const rate=el('input',{type:'text',inputMode:'decimal','aria-label':'Abrechnungssatz netto je Stunde (€)',value:''}),tax=el('input',{type:'text',inputMode:'decimal','aria-label':'Umsatzsteuer für Arbeitszeiten (%)',value:'19'});
  const rates=el('div',{class:'form-grid'},el('label',{class:'field'},'Abrechnungssatz netto je Stunde (€)',rate),el('label',{class:'field'},'Umsatzsteuer für Arbeitszeiten (%)',tax));
  const reload=button('Freigegebene Zeiten neu laden',()=>{void load();},'small');
  root.append(el('h3',{},'Freigegebene Arbeitszeiten übernehmen'),notice('Nur vollständig freigegebene, noch nicht abgerechnete Zeiten dieses Projekts. Die Auswahl erstellt einen Entwurf; die Festschreibung erfolgt gesondert.'),body,rates,reload);
  let epoch=0,owner,sources=[],loadedProject=null,locked=false;
  const alive=(token,p)=>root.isConnected&&stamp()===owner&&epoch===token&&project()===p&&document.visibilityState!=='hidden';
  function render(){
    const bound=new Set(positions().filter(item=>item.source_type==='time').map(item=>item.source_id));
    const available=sources.filter(item=>item.net_seconds>0&&!bound.has(item.entry_id));
    body.replaceChildren(...available.map(item=>el('label',{class:'check'},el('input',{type:'checkbox','data-time-entry':item.entry_id,checked:selected.has(item.entry_id),disabled:locked,onChange:event=>{if(event.target.checked){if(selected.size>=100){event.target.checked=false;return;}selected.add(item.entry_id);onSelect();}else selected.delete(item.entry_id);}}),`${formatDate(item.date)} · ${item.net_seconds} Sekunden · ${item.label}`)),notice(`${available.length} verfügbare Zeitquelle(n)${bound.size?' · '+bound.size+' bereits im Entwurf gebunden':''}.`));
    rate.disabled=tax.disabled=reload.disabled=locked;
  }
  async function load(){
    const token=++epoch,p=project();sources=[];selected.clear();loadedProject=null;rate.disabled=tax.disabled=true;
    if(!p){body.replaceChildren(notice('Zuerst ein Projekt auswählen.'));return;}
    body.replaceChildren(notice('Freigegebene Arbeitszeiten werden geladen …'));
    try{await documentTimeContext(api,p);if(!alive(token,p))return;const result=documentTimeSources(await api.get('/business/documents/time-sources?project_id='+p));if(!alive(token,p))return;await documentTimeContext(api,p);if(!alive(token,p))return;sources=result;loadedProject=p;render();}
    catch(error){if(alive(token,p))body.replaceChildren(notice(error.message,'error'));}
  }
  function busy(value){locked=value;root.querySelectorAll('input,button').forEach(input=>input.disabled=locked);if(!loadedProject)rate.disabled=tax.disabled=true;}
  return {element:root,start(){owner=stamp();void load();},load,busy,freeze(){busy(true);},
    async prepare(){
      const token=epoch,p=project(),chosen=sources.filter(item=>selected.has(item.entry_id));
      if(!alive(token,p))throw new StaleSession();
      if(!chosen.length)return {data:{},selected:[]};
      if(loadedProject!==p)throw new ApiError('Bitte die freigegebenen Zeiten neu laden.',409);
      const hourly=decimalText(rate.value),vat=decimalText(tax.value);
      await documentTimeContext(api,p);if(!alive(token,p))throw new StaleSession();
      const current=documentTimeSources(await api.get('/business/documents/time-sources?project_id='+p));if(!alive(token,p))throw new StaleSession();
      documentTimeUnchanged(chosen,current);await documentTimeContext(api,p);if(!alive(token,p))throw new StaleSession();
      return {data:{time_entry_ids:chosen.map(item=>item.entry_id),hourly_rate_net:hourly,time_tax_rate:vat},selected:structuredClone(chosen)};
    }};
}
