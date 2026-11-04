/* Local supplier catalog files. No provider contacts or inferred price validity. */
const ID=/^[a-f0-9]{32}$/, HASH=/^[a-f0-9]{64}$/;
export const catalogProfiles={catalog_csv_v1:'Smartplan Artikel-CSV v1',datanorm_a14_cp850_v1:'DATANORM A/N, 14 Felder, CP850'};
const MONEY=['cost_price_net','unit_price_net','tax_rate'];
const FIELDS=['code','name','unit',...MONEY,'kind','currency','active','cost_known','tax_category','tax_exemption_reason','pricing_calculation'];
const LABELS={code:'Artikelnummer',name:'Bezeichnung',unit:'Einheit',cost_price_net:'Einkauf netto',unit_price_net:'Verkauf netto',tax_rate:'USt. %',kind:'Artikelart',currency:'Währung',active:'Aktiv',cost_known:'Einstand bekannt',tax_category:'Steuerkategorie',tax_exemption_reason:'Steuerbefreiungsgrund',pricing_calculation:'Gespeicherte Preiskalkulation'};
const display=value=>typeof value==='boolean'?(value?'Ja':'Nein'):value===undefined||value===''?'—':({material:'Material',service:'Leistung',labor:'Arbeit',machine:'Maschine'}[value]||value);
export function catalogStatusAccess(caps){return (caps?.permissions||[]).includes('settings.manage')&&(caps?.capabilities||[]).includes('business_adapters');}
export function catalogAccess(caps){
 const permissions=new Set(caps?.permissions||[]),capabilities=new Set(caps?.capabilities||[]);
 const read=permissions.has('settings.manage')&&permissions.has('finance.read')&&capabilities.has('business_adapters')&&capabilities.has('business_catalog_imports');
 const modules=caps?.organization?.modules,configured=(caps?.features||[]).includes('organization_modules');
 return {read,write:read&&permissions.has('finance.write')&&caps.readonly===false&&(!configured||modules?.documents?.enabled===true)};
}
export function catalogDecimal(raw){const value=String(raw??'').trim().replace(',','.');if(!/^(0|[1-9][0-9]{0,12})(\.[0-9]{1,4})?$/.test(value))throw new Error('Nicht negative Dezimalzahl mit höchstens vier Nachkommastellen erforderlich.');return value;}
const scaled=value=>{const [whole,fraction='']=catalogDecimal(value).split('.');return BigInt(whole)*10000n+BigInt(fraction.padEnd(4,'0'));};
export function catalogDatanormPrice(item,scale){
 if(!/^\d{1,14}$/.test(item?.source_price_integer||'')||!['1','10','100','1000'].includes(item.price_basis)||scaled(scale)<=0n)throw new Error('Rohpreis, Preiseinheit und positive Skalierung ausdrücklich prüfen.');
 const numerator=BigInt(item.source_price_integer)*scaled(scale),basis=BigInt(item.price_basis),result=(numerator+basis/2n)/basis;
 return `${result/10000n}.${String(result%10000n).padStart(4,'0')}`;
}
export function catalogRun(value,{adapterId,sourceHash,runId}={}){
 if(!ID.test(value?.id||'')||!ID.test(value.adapter_id||'')||!catalogProfiles[value.profile]||!['staged','applied'].includes(value.status)||!HASH.test(value.source_sha256||'')||!Array.isArray(value.rows)||!value.rows.length||value.rows.length>2000||typeof value.result!=='object'||!value.result)throw new Error('Importantwort ist unvollständig. Den ursprünglichen Auftrag erneut prüfen.');
 if(adapterId&&value.adapter_id!==adapterId||sourceHash&&value.source_sha256!==sourceHash||runId&&value.id!==runId)throw new Error('Die Importantwort gehört nicht zur gewählten Originaldatei.');
 const codes=new Set();for(const row of value.rows){if(typeof row.code!=='string'||!row.code||codes.has(row.code)||typeof row.name!=='string'||typeof row.unit!=='string')throw new Error('Importpositionen sind unvollständig oder doppelt.');codes.add(row.code);if(value.profile==='catalog_csv_v1')for(const key of MONEY)catalogDecimal(row[key]);}
 return value;
}
const stable=value=>JSON.stringify(value,(_,item)=>item&&typeof item==='object'&&!Array.isArray(item)?Object.fromEntries(Object.keys(item).sort().map(key=>[key,item[key]])):item);
export function catalogChanges(run,mapping,preview){
 catalogRun(run);if(preview?.run_id!==run.id||preview.source_sha256!==run.source_sha256||preview.profile!==run.profile||!HASH.test(preview.preview_sha256||'')||stable(preview.price_mapping)!==stable(mapping)||!Array.isArray(preview.rows)||preview.rows.length!==run.rows.length)throw new Error('Die Übernahmevorschau ist nicht vollständig an Original und Preiszuordnung gebunden.');
 return preview.rows.map((item,index)=>{
  const source=run.rows[index],expected=run.result.target_revisions?.[source.code];
  if(item.code!==source.code||!['create','update','noop'].includes(item.action)||!!expected!==(item.action!=='create')||expected&&(item.article_id!==expected.article_id||item.revision!==expected.revision)||!expected&&(item.article_id!==null||item.revision!==null)||!item.after||expected&&!item.before||!expected&&item.before!==null)throw new Error('Artikelzuordnung oder Revision der Vorschau stimmt nicht mit dem Import überein.');
  if(item.action==='noop'&&stable(item.before)!==stable(item.after))throw new Error('Eine unveränderte Übernahme darf keine Artikelwerte ändern.');
  const next={...item.after,pricing_calculation:!!item.after.pricing_snapshot},old=item.before?{...item.before,pricing_calculation:!!item.before.pricing_snapshot,revision:item.revision}:null;
  for(const key of MONEY){catalogDecimal(next[key]);if(old)catalogDecimal(old[key]);}
  {
   if(['code','name','unit'].some(key=>next[key]!==source[key])||next.kind!=='material'||next.currency!=='EUR'||next.active!==true)throw new Error('Die Vorschau verändert die gewählten Originalpositionen.');
   if(run.profile==='catalog_csv_v1'&&MONEY.some(key=>scaled(next[key])!==scaled(source[key])))throw new Error('Die Vorschau verändert die Originalpreise.');
   if(run.profile==='datanorm_a14_cp850_v1'){
    const key=mapping.target_price==='purchase_net'?'cost_price_net':'unit_price_net',other=key==='cost_price_net'?'unit_price_net':'cost_price_net';
    if(!['purchase_net','sales_net'].includes(mapping.target_price)||source.discount_group||source.long_text_key||scaled(next[key])!==scaled(catalogDatanormPrice(source,mapping.price_scale))||scaled(next[other])!==scaled(old?.[other]||'0')||scaled(next.tax_rate)!==scaled(mapping.tax_rate))throw new Error('Die Vorschau entspricht nicht der bestätigten DATANORM-Zuordnung.');
   }
  }
  const differences=FIELDS.filter(key=>old&&(MONEY.includes(key)?scaled(old[key])!==scaled(next[key]):old[key]!==next[key])).map(key=>({field:key,before:old[key],after:next[key]}));
  return {code:item.code,old,next,differences,kind:item.action==='create'?'new':differences.length?'changed':'same',action:item.action};
 });
}
export async function catalogFile(file){
 if(!file||!Number.isSafeInteger(file.size)||file.size<1||file.size>2097152)throw new Error('Eine Originaldatei zwischen 1 Byte und 2 MiB auswählen.');
 const bytes=new Uint8Array(await file.arrayBuffer());if(bytes.length!==file.size)throw new Error('Dateigröße hat sich beim Lesen geändert.');
 const sha256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');
 let binary='';for(let index=0;index<bytes.length;index+=8192)binary+=String.fromCharCode(...bytes.subarray(index,index+8192));
 return {body:{filename:file.name,content_base64:btoa(binary)},sha256,size:bytes.length};
}
export async function catalogPendingAuthorize(api,operation){
 const generation=api.generation,values=api.pendingCommandValues(operation?.key,operation?.path);
 if(!values||!/^\/business\/adapters(?:\/[a-f0-9]{32}\/import|\/imports\/[a-f0-9]{32}\/apply)?$/.test(operation.path))throw new Error('Ursprünglicher Katalogauftrag fehlt.');
 const caps=await api.get('/business/capabilities');if(generation!==api.generation)throw new Error('Sitzung gewechselt.');
 if(!catalogAccess(caps).write)throw new Error('Aktuelle Katalog- und Finanzfreigabe fehlt; der ursprüngliche Auftrag bleibt offen.');
}
export class CatalogContext {
 constructor(stamp){this.stamp=stamp;this.epoch=0;}
 begin(){return {epoch:++this.epoch,stamp:this.stamp()};}
 invalidate(){this.epoch++;}
 current(token){return token?.epoch===this.epoch&&token.stamp===this.stamp();}
}
export function catalogImportsUi(h){
 const {api,el,button,notice,panel,table}=h,biz=path=>'/business'+path,context=new CatalogContext(h.stamp);let active=null,observer=null,editing=false,latestCaps=null;
 const pending=key=>api.pendingOperations().find(item=>item.key===key);
 function clear(){context.invalidate();editing=false;latestCaps=null;observer?.disconnect();observer=null;const own=active;active=null;if(own?.isConnected)h.closeModal();own?.replaceChildren();}
 if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')clear();});
 function valid(token){return context.current(token)&&active?.isConnected&&h.available()&&document.visibilityState!=='hidden';}
 function screen(title,children,requiresWrite=false){observer?.disconnect();editing=requiresWrite;const token=context.begin(),body=el('div',{class:'stack','data-catalog-import':'true'},children);active=body;h.dialog(title,body);observer=new MutationObserver(()=>{if(active===body&&!body.isConnected)clear();});observer.observe(document.body,{childList:true,subtree:true});return token;}
 function error(token,value){if(valid(token)&&[401,403].includes(value.status)){clear();return;}if(valid(token)){active.querySelector('[data-catalog-error]')?.remove();active.prepend(el('div',{'data-catalog-error':'true'},notice(value.message||'Vorgang fehlgeschlagen.','error')));}}
 function perform(token,work){return async()=>{if(!valid(token))return;try{await work();}catch(value){error(token,value);}};}
 async function fresh(token,write=false){
  if(!valid(token))throw new Error('Ansicht gewechselt.');const caps=await api.get(biz('/capabilities'));
  if(!valid(token))throw new Error('Ansicht gewechselt.');latestCaps=caps;if((editing&&!catalogAccess(caps).write)||!(write==='status'?catalogStatusAccess(caps):catalogAccess(caps)[write?'write':'read'])){clear();throw new Error('Aktuelle Katalogfreigabe fehlt.');}return caps;
 }
 function label(text,input){return el('label',{class:'field'},el('span',{},text),input);}
 function input(text,attributes={}){return el('input',{'aria-label':text,...attributes});}
 function select(text,options){return el('select',{'aria-label':text},options.map(([value,name])=>el('option',{value},name)));}
 function pages(headers,values,caption='Positionen'){let page=0;const box=el('div',{class:'stack'});const draw=()=>{box.replaceChildren(table(headers,values.slice(page*50,page*50+50)),notice(`${caption} ${page*50+1}–${Math.min((page+1)*50,values.length)} von ${values.length}`),page>0?button('Vorige '+caption,()=>{page--;draw();}):null,(page+1)*50<values.length?button('Weitere '+caption,()=>{page++;draw();}):null);};draw();return box;}
 function submit(token,caption,work){const control=button(caption,perform(token,async()=>{control.disabled=true;try{await work();}finally{if(valid(token))control.disabled=false;}}),'primary');return control;}
 function pendingButton(token,operation,after){return submit(token,'Ursprüngliche Antwort erneut prüfen',async()=>{await fresh(token,true);const result=await api.retry(operation.key);if(!valid(token))return;await fresh(token,true);await after(result);});}
 async function open(){
  const token=screen('Lieferantenkataloge und Adapter',notice('Lokale Dateien prüfen und ausdrücklich übernehmen. Es wird keine Verbindung zu Lieferanten aufgebaut.'));
  await perform(token,async()=>{const caps=await fresh(token,'status');const response=await api.get(biz('/adapters'));if(!valid(token))return;
   const list=el('div',{class:'stack'});for(const source of response.items||[])list.append(panel(source.name,el('p',{},catalogProfiles[source.profile]||source.profile),el('p',{},source.enabled?'Aktiviert':'Deaktiviert'),catalogProfiles[source.profile]&&catalogAccess(caps).read?button('Katalog öffnen',perform(token,()=>openSource(source))):notice(catalogProfiles[source.profile]?'Kataloghistorie benötigt das installierte Originalmodul und aktuelle Finanzleserechte.':'Für dieses Profil ist hier keine Katalogübernahme vorgesehen.')));
   if(!list.children.length)list.append(notice('Noch keine lokale Katalogquelle angelegt.'));active.append(list);
   if(catalogAccess(caps).write){const operation=pending('catalog-create');active.append(operation?pendingButton(token,operation,()=>open()):button('Lokale Katalogquelle anlegen',perform(token,()=>create())));}
  })();
 }
 function create(){
  const name=input('Name der Katalogquelle',{maxLength:200,required:true}),profile=select('Dateiformat',Object.entries(catalogProfiles));
  const token=screen('Lokale Katalogquelle anlegen',[label('Name der Katalogquelle',name),label('Dateiformat',profile),notice('Format ist nach dem Anlegen fest. Diese Quelle hat keine Lieferantenverbindung.')],true);
  active.append(submit(token,'Katalogquelle speichern',async()=>{if(!name.value.trim())throw new Error('Einen Namen eingeben.');await fresh(token,true);const result=await api.mutate('catalog-create',biz('/adapters'),{name:name.value.trim(),profile:profile.value,enabled:true},{validate:value=>{if(!ID.test(value?.id||''))throw new Error('Quellenantwort unvollständig.');}});if(valid(token)){await fresh(token,true);await openSource(result);}}));
 }
 async function openSource(source,offset=0){
  const token=screen('Katalog · '+source.name,[notice(catalogProfiles[source.profile]),notice('Importierte Preise haben keine automatisch angenommene zeitliche Gültigkeit. Bestehende Artikelnummern anderer Quellen werden nicht automatisch zugeordnet.')]);
  await perform(token,async()=>{await fresh(token);const history=await api.get(biz(`/adapters/${source.id}/imports?offset=${offset}&limit=20`));if(!valid(token))return;
   if(source.enabled&&catalogAccess(latestCaps||h.caps()).write){const operation=pending('catalog-import-'+source.id);active.append(operation?pendingButton(token,operation,result=>preview(source,result)):button('Katalogdatei auswählen',perform(token,()=>upload(source))));}
   active.append(panel('Importhistorie',...(history.items||[]).map(run=>panel(`${h.formatDate(run.created_at,true)} · ${run.status==='applied'?'Übernommen':'Zur Prüfung'}`,el('p',{},`${run.row_count} Artikel · ${run.original?.filename||'Früherer Import ohne gespeichertes Original'}`),button('Import ansehen',perform(token,async()=>{await fresh(token);const detail=await api.get(biz('/adapters/imports/'+run.id));if(valid(token))await preview(source,detail);})))),!(history.items||[]).length?notice('Noch keine Importe vorhanden.'):null));
   if(offset>0)active.append(button('Neuere Importe',perform(token,()=>openSource(source,Math.max(0,offset-20)))));if(offset+20<history.total)active.append(button('Ältere Importe',perform(token,()=>openSource(source,offset+20))));active.append(button('Alle Katalogquellen',perform(token,open)));
  })();
 }
 function upload(source){
  const picker=input('Katalogdatei',{type:'file',accept:source.profile==='catalog_csv_v1'?'.csv':'.dat,.001,.txt'}),info=el('div');let file=null,selection=0;
  const token=screen('Katalogdatei prüfen',[notice(source.profile==='catalog_csv_v1'?'UTF-8, Semikolon, exakte Kopfzeile: code;name;unit;cost_price_net;unit_price_net;tax_rate. Dezimalpunkt, höchstens vier Nachkommastellen.':'Begrenztes DATANORM-Profil: CP850, ausschließlich A/N-Neuanlage mit genau 14 Feldern. Keine vollständige DATANORM-Zertifizierung.'),notice('Maximal 2 MiB und 2.000 Artikel. Die Prüfung speichert das Original, verändert jedoch noch keine Artikel.'),label('Katalogdatei',picker),info],true);
  picker.addEventListener('change',async()=>{const selected=++selection;file=null;info.replaceChildren();try{const result=await catalogFile(picker.files?.[0]);if(!valid(token)||selected!==selection)return;file=result;info.append(notice(`${result.body.filename} · ${result.size} Bytes`));}catch(value){if(selected===selection)error(token,value);}});
  const key='catalog-import-'+source.id;active.append(submit(token,'Datei prüfen und Vorschau laden',async()=>{await fresh(token,true);let result;
   try{if(pending(key))result=await api.retry(key);else{if(!file)throw new Error('Zuerst die vollständige Originaldatei auswählen.');const expected=file.sha256;result=await api.mutate(key,biz(`/adapters/${source.id}/import`),file.body,{validate:value=>catalogRun(value,{adapterId:source.id,sourceHash:expected})});}}
   finally{if(valid(token)&&pending(key)){picker.disabled=true;file=null;active.querySelectorAll('button.primary').forEach(node=>node.textContent='Ursprüngliche Antwort erneut prüfen');}}
   if(valid(token)){await fresh(token,true);await preview(source,result);}
  }));
 }
 async function preview(source,raw){
  const run=catalogRun(raw,{adapterId:source.id}),token=screen('Import prüfen · '+source.name,[notice(`${run.rows.length} Artikel · ${run.status==='applied'?'Bereits übernommen':'Noch nicht übernommen'}`),notice('SHA-256: '+run.source_sha256)],run.status==='staged'&&catalogAccess(latestCaps||h.caps()).write);
  await perform(token,async()=>{await fresh(token);if(run.original?.available)active.append(button('Original herunterladen',perform(token,()=>download(token,run))));else active.append(notice('Für diesen früheren Import wurde kein Original gespeichert.'));
   if(run.status==='applied'){const operation=pending('catalog-apply-'+run.id);if(operation)active.append(pendingButton(token,operation,result=>preview(source,result)));active.append(notice('Die Übernahme ist gespeichert. Die Originalpositionen bleiben unverändert; aktuelle Artikel können inzwischen weiter bearbeitet worden sein.'),pages(run.profile==='catalog_csv_v1'?['Artikelnummer','Bezeichnung','Einheit','Einkauf netto','Verkauf netto','USt. %']:['Artikelnummer','Bezeichnung','Einheit','Rohpreis','Preisbasis'],run.rows.map(item=>run.profile==='catalog_csv_v1'?[item.code,item.name,item.unit,item.cost_price_net,item.unit_price_net,item.tax_rate]:[item.code,item.name,item.unit,item.source_price_integer,item.price_basis]),'Originalartikel'),run.acceptance?notice('Annahme am '+h.formatDate(run.acceptance.created_at,true)+' · '+run.acceptance.articles.length+' gebundene Artikelrevisionen'+(run.profile==='datanorm_a14_cp850_v1'?' · '+(run.acceptance.price_mapping.target_price==='purchase_net'?'Einkauf netto':'Verkauf netto')+' · Skalierung '+run.acceptance.price_mapping.price_scale+' · USt. '+run.acceptance.price_mapping.tax_rate+' %':'')):notice('Für diese frühere Übernahme liegt kein zusätzlicher Annahmebeleg vor.'),button('Zur Importhistorie',perform(token,()=>openSource(source))));return;}
   const mapping={},changes=el('div',{class:'stack'}),confirmation=input('Ich bestätige diese Artikel und alle angezeigten Änderungen.',{type:'checkbox'}),key='catalog-apply-'+run.id;let checked=null,previewVersion=0;
   const render=async()=>{const version=++previewVersion;confirmation.checked=false;checked=null;changes.replaceChildren(notice('Übernahmeentscheidung wird geprüft …'));try{if(run.profile==='datanorm_a14_cp850_v1'&&(!['purchase_net','sales_net'].includes(mapping.target_price)||scaled(mapping.price_scale)<=0n||scaled(mapping.tax_rate)>1000000n))throw new Error('Nettopreisziel, positive Rohpreisskalierung und Steuersatz bis 100 ausdrücklich festlegen.');await fresh(token);const boundMapping=structuredClone(mapping),boundPreview=await api.post(biz(`/adapters/imports/${run.id}/catalog-preview`),boundMapping);if(!valid(token)||version!==previewVersion)return;await fresh(token);if(!valid(token)||version!==previewVersion)return;checked=catalogChanges(run,boundMapping,boundPreview);changes.replaceChildren();const counts={new:0,changed:0,same:0};checked.forEach(item=>counts[item.kind]++);changes.append(notice(`${counts.new} neu · ${counts.changed} geändert · ${counts.same} unverändert`));let page=0;const result=el('div');const draw=()=>{result.replaceChildren(table(['Artikel','Bisher','Vorschau'],checked.slice(page*50,page*50+50).flatMap(item=>[
     [item.code+' · '+item.next.name,item.old?'Revision '+item.old.revision:'Neu',item.action==='noop'?'Ohne erneute Artikeländerung':item.action==='create'?'Neuer Artikel':'Artikel wird aktualisiert'],
     ...FIELDS.map(field=>[LABELS[field],display(field==='pricing_calculation'?(item.old?!!item.old.pricing_snapshot:undefined):item.old?.[field]),display(item.next[field])]),
    ])),notice(`Artikel ${page*50+1}–${Math.min((page+1)*50,checked.length)} von ${checked.length}`),page>0?button('Vorige Artikel',()=>{page--;draw();}):null,(page+1)*50<checked.length?button('Weitere Artikel',()=>{page++;draw();}):null);};draw();changes.append(result);}catch(value){if(!valid(token)||version!==previewVersion)return;checked=null;changes.replaceChildren();if([401,403].includes(value.status)){clear();return;}changes.append(notice(value.message,'error'));}};
   if(run.profile==='datanorm_a14_cp850_v1'){
    active.append(notice('Rohpreis, Preisbasis und Kennzeichen aus der Datei prüfen. Preisziel, Skalierung und Steuersatz müssen ausdrücklich festgelegt werden; Rabatte/Langtextverweise werden nicht aufgelöst.'),pages(['Artikel','Rohpreis','Preisbasis','Kennzeichen'],run.rows.map(item=>[item.code,item.source_price_integer,item.price_basis,item.price_flag]),'Rohpreise'));
    for(const [key,text,control]of [['target_price','Nettopreisziel',select('Nettopreisziel',[['','Bitte auswählen'],['purchase_net','Einkauf netto'],['sales_net','Verkauf netto']])],['price_scale','Rohpreisskalierung',input('Rohpreisskalierung',{inputMode:'decimal',placeholder:'z. B. 0,01 laut Dateivertrag'})],['tax_rate','Umsatzsteuersatz',input('Umsatzsteuersatz',{inputMode:'decimal'})]]){control.addEventListener('change',()=>{mapping[key]=control.value.trim().replace(',','.');render();});active.append(label(text,control));}
   }
   active.append(changes);render();
   if(source.enabled&&catalogAccess(latestCaps||h.caps()).write){active.append(label('Ich bestätige diese Artikel und alle angezeigten Änderungen.',confirmation),submit(token,pending(key)?'Ursprüngliche Antwort erneut prüfen':'Artikel ausdrücklich übernehmen',async()=>{await fresh(token,true);try{let result;if(pending(key))result=await api.retry(key);else{if(!checked||!confirmation.checked)throw new Error('Vollständige Vorschau prüfen und Übernahme ausdrücklich bestätigen.');result=await api.mutate(key,biz(`/adapters/imports/${run.id}/apply`),{confirmed:true,...mapping},{validate:value=>{catalogRun(value,{adapterId:source.id,runId:run.id,sourceHash:run.source_sha256});if(value.status!=='applied'||value.result.article_ids?.length!==run.rows.length)throw new Error('Die Artikelübernahme wurde nicht vollständig bestätigt.');}});}if(valid(token)){await fresh(token,true);await preview(source,result);}}finally{if(valid(token)&&pending(key)){active.querySelectorAll('input,select').forEach(node=>node.disabled=true);active.querySelectorAll('button.primary').forEach(node=>node.textContent='Ursprüngliche Antwort erneut prüfen');}}}));}
   active.append(button('Zur Importhistorie',perform(token,()=>openSource(source))));
  })();
 }
 async function download(token,run){await fresh(token);const original=run.original,blob=await api.request(biz(`/adapters/imports/${run.id}/original`),{binary:true,maxBytes:2097152}),bytes=await blob.arrayBuffer(),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');await fresh(token);if(hash!==run.source_sha256||hash!==original.sha256||bytes.byteLength!==original.size)throw new Error('Originaldatei stimmt nicht mit dem gespeicherten Import überein.');if(valid(token))h.saveBlob(blob,original.filename);}
 return {open,clear};
}
