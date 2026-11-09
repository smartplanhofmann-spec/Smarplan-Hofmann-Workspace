/* Project material returns reuse an immutable issue and its historical cost. */
import {inventoryQuantity} from './inventory-counts.js';
const ID=/^[a-f0-9]{32}$/;
const path='/business/inventory/movements';
const fail=(message,status=0)=>Object.assign(new Error(message),{status});
const copy=value=>structuredClone(value);
const units=value=>BigInt(inventoryQuantity(value).replace('.',''));
const quantity=value=>{const raw=value.toString().padStart(5,'0');return raw.slice(0,-4)+'.'+raw.slice(-4);};
export const stockReturnKey=projectId=>'stock-return-'+projectId;
export const isStockReturn=(key,resource,body)=>resource===path&&key===stockReturnKey(body?.project_id)&&body?.kind==='return'&&ID.test(body?.reversal_of||'');
export function stockReturnOriginal(value,projectId,actorId){
 const exact=(v,keys)=>v&&Object.getPrototypeOf(v)===Object.prototype&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
 const id=v=>typeof v==='string'&&v.length===32&&ID.test(v);
 const body=value?.body;
 if(!exact(value,['schema_version','path','key','actor_id','body'])||value.schema_version!==1||value.path!==path||value.key!==stockReturnKey(projectId)||value.actor_id!==actorId||
   !id(actorId)||!exact(body,['kind','article_id','project_id','reversal_of','to_location_id','quantity','note','request_id'])||body.kind!=='return'||body.project_id!==projectId||
   ![body.article_id,body.project_id,body.reversal_of,body.to_location_id,body.request_id].every(id)||
   typeof body.note!=='string'||[...body.note].length>2000||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(body.note)||
   inventoryQuantity(body.quantity)!==body.quantity)throw fail('Der gespeicherte Rückgabeauftrag gehört nicht zur ursprünglichen Anmeldung und Projektentnahme.');
 return copy(value);
}
export function stockReturnRights(caps){const rights=new Set(caps?.permissions||[]),read=caps?.capabilities?.includes('business_inventory')===true&&rights.has('inventory.read');return {read,write:read&&caps.readonly===false&&caps.organization?.modules?.material?.enabled!==false&&rights.has('inventory.write'),financial:rights.has('finance.read')};}
export function stockReturnMovement(value,kind=null){
 if(!value||!ID.test(value.id||'')||!ID.test(value.article_id||'')||!['receive','issue','return','transfer'].includes(value.kind)||kind&&value.kind!==kind||!Number.isSafeInteger(value.sequence_number)||value.sequence_number<1||typeof value.quantity!=='string'||!/^\d{1,12}\.\d{4}$/.test(value.quantity)||units(value.quantity)<=0n||value.article_snapshot?.id!==value.article_id)throw fail('Der unveränderte Lagerbeleg ist nicht eindeutig.');
 if(['issue','return'].includes(value.kind)&&!ID.test(value.project_id||''))throw fail('Der ursprüngliche Projektbezug fehlt.');
 if(value.kind==='issue'&&(!ID.test(value.from_location_id||'')||value.to_location_id!==null||value.reversal_of!==null)||value.kind==='return'&&(!ID.test(value.to_location_id||'')||value.from_location_id!==null||!ID.test(value.reversal_of||'')))throw fail('Die Originalentnahme oder Rückgabe besitzt keinen gültigen Lagerbezug.');
 return value;
}
export function stockReturnRemaining(issue,items){
 stockReturnMovement(issue,'issue');if(!Array.isArray(items))throw fail('Das vollständige Rückgabejournal fehlt.');let returned=0n;const seen=new Set();
 for(const item of items){stockReturnMovement(item);if(seen.has(item.id)||item.project_id!==issue.project_id)throw fail('Das Journal gehört nicht eindeutig zum ursprünglichen Projekt.');seen.add(item.id);if(item.kind==='return'&&item.reversal_of===issue.id){if(item.article_id!==issue.article_id||item.sequence_number<=issue.sequence_number)throw fail('Eine Rückgabe widerspricht ihrer ursprünglichen Entnahme.');returned+=units(item.quantity);}}
 const available=units(issue.quantity)-returned;if(available<0n)throw fail('Das Rückgabejournal überschreitet seine ursprüngliche Entnahme.');return quantity(available);
}
export function stockReturnData(issue,items,values){
 const amount=inventoryQuantity(values.quantity),remaining=stockReturnRemaining(issue,items);if(units(amount)<=0n||units(amount)>units(remaining))throw fail('Die Rückgabemenge muss positiv sein und darf die offene Entnahmemenge nicht überschreiten.',400);
 if(!ID.test(values.to_location_id||'')||values.confirmed!==true)throw fail('Ziellager und die tatsächliche Materialrückgabe ausdrücklich bestätigen.',400);
 const note=String(values.note??'').trim();if([...note].length>2000||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(note)||[...note].some(ch=>{const n=ch.codePointAt(0);return n>=0xd800&&n<=0xdfff;}))throw fail('Eine gültige Buchungsnotiz mit höchstens 2000 Zeichen angeben.',400);
 return {kind:'return',article_id:issue.article_id,project_id:issue.project_id,reversal_of:issue.id,to_location_id:values.to_location_id,quantity:amount,note};
}
export async function stockReturnAuthorize(api,body,{replay=false}={}){
 if(!ID.test(body?.project_id||'')||!ID.test(body?.reversal_of||'')||body.kind!=='return')throw fail('Die Rückgabe benötigt ihre ursprüngliche Projektentnahme.',409);
 const [caps,issue,actor]=await Promise.all([api.get('/business/capabilities?project_id='+body.project_id),api.get(path+'/'+body.reversal_of),api.get('/me')]);const rights=stockReturnRights(caps);stockReturnMovement(issue,'issue');
 if(!rights.write||!ID.test(actor?.id||''))throw fail('Aktuelle Lager-Schreibrechte für dieses Projekt fehlen.',403);
 if(issue.project_id!==body.project_id||issue.article_id!==body.article_id)throw fail('Der Rückgabeauftrag gehört nicht zur ursprünglichen Entnahme.',409);
 let items=null;if(!replay){const page=await api.get(path+'?project_id='+body.project_id);items=page.items;if(units(body.quantity)>units(stockReturnRemaining(issue,items)))throw fail('Die offene Entnahmemenge wurde inzwischen geändert.',409);}
 if(!replay){const location=await api.get('/business/inventory/locations/'+body.to_location_id);if(location?.id!==body.to_location_id||![true,1].includes(location.active))throw fail('Das ausgewählte Ziellager ist nicht mehr aktiv.',409);}
 return {caps,rights,issue,actor,items};
}
export async function stockReturnPendingAuthorize(api,operation){const body=api.pendingCommandValues(operation.key,operation.path);if(!isStockReturn(operation.key,operation.path,body))throw fail('Der ursprüngliche Rückgabeauftrag fehlt.',409);return stockReturnAuthorize(api,body,{replay:true});}
export function stockReturnReceipt(body,actorId){const original=copy(body);return async(raw,api)=>{
 const result=stockReturnMovement(raw,'return');
 if(result.project_id!==original.project_id||result.article_id!==original.article_id||result.reversal_of!==original.reversal_of||result.to_location_id!==original.to_location_id||inventoryQuantity(result.quantity)!==inventoryQuantity(original.quantity)||result.note!==(original.note??'')||result.created_by!==actorId)throw fail('Die Rückgabebestätigung passt nicht zum unveränderten Auftrag.');
 const read=stockReturnMovement(await api.get(path+'/'+result.id),'return');for(const key of ['id','kind','article_id','project_id','reversal_of','from_location_id','to_location_id','quantity','note','created_by','created_at','sequence_number'])if(read[key]!==result[key])throw fail('Der zurückgelesene Lagerbeleg passt nicht zur Rückgabebestätigung.');for(const key of ['unit_cost_net','cost_net'])if(read[key]!==undefined&&result[key]!==undefined&&read[key]!==result[key])throw fail('Die bestätigte historische Bewertung passt nicht zum Lagerjournal.');return result;
};}
export function stockReturnsUi(h){
 const {api,el,button,field,form,panel,table,notice,dialog,action}=h;let active=null;
 const token=()=>({stamp:h.stamp(),body:active}),current=t=>t.stamp===h.stamp()&&t.body===active&&t.body?.isConnected&&document.visibilityState!=='hidden';
 function show(title,body){active=body;body.setAttribute('data-stock-return','true');dialog(title,body);}
 async function open(projectId=''){
  const stamp=h.stamp();
  if(!ID.test(projectId)){const page=await api.get('/projects');if(stamp!==h.stamp())return;show('Projekt der Materialrückgabe',form('',[field('project_id','Projekt der ursprünglichen Entnahme','select','',{required:true,options:[['','Projekt ausdrücklich wählen'],...(page.items||page).map(value=>[value.id,value.name]) ]})],values=>open(values.project_id),{key:'stock-return-project',submit:'Originalentnahmen öffnen'}));return;}
  const [caps,page,locations]=await Promise.all([api.get('/business/capabilities?project_id='+projectId),api.get(path+'?project_id='+projectId),api.get('/business/inventory/locations')]);if(stamp!==h.stamp())return;
  const rights=stockReturnRights(caps);if(!rights.read)throw fail('Die aktuelle Lesefreigabe für diese Projektentnahmen fehlt.',403);if(!Array.isArray(page.items)||!Array.isArray(locations.items))throw fail('Die Lagerquellen sind unvollständig.');
  if(typeof api.restoreStockReturn==='function')await api.restoreStockReturn(projectId,caps);
  else if(caps.features?.includes('client_original_key'))throw fail('Der geschützte Browserauftrag ist in diesem Client noch nicht verfügbar.');
  if(stamp!==h.stamp())return;
  const body=el('div',{class:'stack'}),pending=api.pendingCommandValues(stockReturnKey(projectId),path);show('Material zurückgeben',body);
  if(pending){body.append(notice('Die ursprüngliche Rückgabe kann bereits gebucht sein. Zuerst genau diesen Auftrag erneut prüfen.'));if(rights.write)body.append(button('Ursprüngliche Rückgabe erneut prüfen',()=>action(async()=>{const origin=token();await api.retry(stockReturnKey(projectId),{stillCurrent:()=>current(origin)});if(current(origin)){h.closeModal();await h.refresh();}}),'primary'));return;}
  const issues=page.items.filter(v=>v.kind==='issue'&&v.project_id===projectId&&units(stockReturnRemaining(v,page.items))>0n);
  if(!issues.length){body.append(notice('Für dieses Projekt besteht keine offene Materialentnahme.'));return;}
  body.append(notice('Die Rückgabe bleibt an die tatsächliche Originalentnahme und deren historischen Einstand gebunden.'));
  body.append(form('',[field('issue_id','Ursprüngliche Materialentnahme','select','',{required:true,options:[['','Entnahme ausdrücklich wählen'],...issues.map(v=>[v.id,(v.article_snapshot.name||v.article_id)+' · '+stockReturnRemaining(v,page.items)+' '+(v.article_snapshot.unit||'')+' offen · '+h.formatDate(v.created_at,true)])]})],values=>edit(issues.find(v=>v.id===values.issue_id),page.items,locations.items,rights),{key:'stock-return-issue-'+projectId,submit:'Rückgabe zur Originalentnahme erfassen'}));
 }
 function edit(issue,items,locations,rights){
  stockReturnMovement(issue,'issue');const details=el('div',{class:'stack'},table(['Originalentnahme','Belegter Stand'],[['Artikel',issue.article_snapshot.name||issue.article_id],['Entnommen',issue.quantity+' '+(issue.article_snapshot.unit||'')],['Noch rückgebbar',stockReturnRemaining(issue,items)],...(rights.financial&&issue.unit_cost_net!==undefined?[['Historischer Einstand netto je Einheit',h.formatMoney(issue.unit_cost_net)]]:[])]));
  details.append(form('',[field('to_location_id','Ziellager für die Rückgabe','select','',{required:true,options:[['','Ziellager ausdrücklich wählen'],...locations.filter(v=>v.active===true||v.active===1).map(v=>[v.id,v.name])]}),field('quantity','Tatsächlich zurückgegebene Menge','decimal','',{required:true,help:'Höchstens '+stockReturnRemaining(issue,items)+' '+(issue.article_snapshot.unit||'')}),field('note','Buchungsnotiz zur Rückgabe','textarea','',{maxLength:2000}),field('confirmed','Ich bestätige die tatsächliche Rückgabe zu dieser Originalentnahme.','checkbox',false,{required:true})],async values=>{
   const origin=token(),key=stockReturnKey(issue.project_id);if(api.pendingCommandValues(key,path))throw fail('Die ursprüngliche Rückgabe ist noch unbestätigt. Über „Antwort offen“ genau diesen Auftrag erneut prüfen.',409);
   const data=stockReturnData(issue,items,values),access=await stockReturnAuthorize(api,data);if(!current(origin))return;const verify=stockReturnReceipt(data,access.actor.id);await h.mutation(key,'/inventory/movements',data,{validate:value=>verify(value,api),stillCurrent:()=>current(origin)});if(current(origin)){h.closeModal();await h.refresh();}
  },{key:stockReturnKey(issue.project_id),submit:'Materialrückgabe verbindlich buchen'}));show('Rückgabe zur Originalentnahme',details);
 }
 return {open};
}
