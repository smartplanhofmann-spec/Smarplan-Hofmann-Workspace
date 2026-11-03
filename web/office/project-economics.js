/* Project economics uses document amounts and existing originals, never tax estimates. */
export const ECONOMICS_CATEGORIES = Object.freeze({
  external_service: 'Fremdleistungen', machine: 'Maschinenkosten', other: 'Sonstige Kosten',
  stock_material: 'Lagerbezug · Kosten aus Materialentnahme', excluded: 'Nicht als Projektkosten berücksichtigen',
});
const ID=/^[a-f0-9]{32}$/, HASH=/^[a-f0-9]{64}$/;
function invalid(message='Die Projektwirtschaftlichkeit konnte nicht sicher gelesen werden.') {
  const error=new Error(message);error.status=502;return error;
}
function id(value) { if(typeof value!=='string'||!ID.test(value))throw invalid();return value; }
function revision(value,zero=false) { if(!Number.isSafeInteger(value)||value<(zero?0:1))throw invalid();return value; }
export function economicsCents(value) {
  if(typeof value!=='string'||! /^-?\d{1,15}\.\d{2}$/.test(value))throw invalid('Genaue EUR-Beträge mit zwei Nachkommastellen erwartet.');
  return BigInt(value.replace('.',''));
}
export function economicsAmount(value) {
  const text=String(value).trim().replace(',','.');
  if(!/^\d{1,9}(?:\.\d{1,2})?$/.test(text))throw new Error('Bitte einen positiven Betrag mit höchstens zwei Nachkommastellen eingeben.');
  const [whole,fraction='']=text.split('.'),result=BigInt(whole).toString()+'.'+fraction.padEnd(2,'0');
  if(economicsCents(result)<=0n)throw new Error('Eine Kostenposition benötigt einen positiven Betrag. Leere Kategorien bleiben unberücksichtigt.');
  return result;
}
function text(value,label,limit=2000) { if(typeof value!=='string'||!value.trim()||value.length>limit)throw new Error(label+' vollständig eingeben.');return value.trim(); }
export function economicsRights(capabilities,organization=null) {
  const permissions=new Set(capabilities?.permissions||[]),modules=new Set(capabilities?.capabilities||[]);
  const available=capabilities?.features?.includes('project_economics')===true&&modules.has('business_project_economics');
  const read=available&&permissions.has('finance.read'),enabled=organization?.modules?.finance?.enabled!==false&&capabilities?.organization?.modules?.finance?.enabled!==false;
  const active=!Array.isArray(capabilities?.active_capabilities)||capabilities.active_capabilities.includes('business_project_economics');
  const writable=read&&enabled&&active&&capabilities.readonly===false;
  return {available,read,capture:writable&&permissions.has('finance.write'),review:writable&&permissions.has('finance.approve'),classify:writable&&permissions.has('finance.write')&&permissions.has('finance.approve')};
}
export function economicsEntry(value,projectId,receiptId=null) {
  if(!value||typeof value!=='object')throw invalid();
  id(value.id);id(value.project_id);id(value.receipt_id);revision(value.revision);revision(value.source_revision);
  if(value.project_id!==projectId||(receiptId!==null&&value.receipt_id!==receiptId)||typeof value.reason!=='string'||!Array.isArray(value.allocations)||!HASH.test(value.entry_hash||''))throw invalid();
  const source=value.source;
  if(!source||source.receipt_id!==value.receipt_id||!HASH.test(source.original_sha256||'')||!HASH.test(source.review_sha256||'')||!HASH.test(source.source_hash||''))throw invalid();
  for(const field of ['net','tax','gross'])economicsCents(source[field]);
  if(economicsCents(source.net)+economicsCents(source.tax)!==economicsCents(source.gross))throw invalid();
  validateAllocations(value.allocations,source.net);
  return value;
}
function sameAllocations(a,b){return Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((line,index)=>line&&Object.keys(line).length===2&&line.category===b[index].category&&line.amount_net===b[index].amount_net);}
function validateAllocations(allocations,net) {
  if(!Array.isArray(allocations)||allocations.length>5)throw invalid();
  const categories=new Set();let total=0n;
  for(const line of allocations){if(!line||!Object.hasOwn(ECONOMICS_CATEGORIES,line.category)||categories.has(line.category)||economicsCents(line.amount_net)<=0n)throw invalid();categories.add(line.category);total+=economicsCents(line.amount_net);}
  if(total!==economicsCents(net))throw invalid('Die Einordnung muss den vollständigen geprüften Nettobetrag abbilden.');
}
export function economicsSources(value,projectId) {
  if(!value||!Array.isArray(value.items))throw invalid();
  const seen=new Set();for(const source of value.items){
    id(source.id);if(source.project_id!==projectId||seen.has(source.id)||typeof source.filename!=='string'||!HASH.test(source.sha256||'')||!['unreviewed','unclassified','current','source_changed'].includes(source.classification_status))throw invalid();
    seen.add(source.id);revision(source.revision,true);revision(source.classification_revision,true);
    if(source.latest_entry!==null&&source.latest_entry!==undefined)economicsEntry(source.latest_entry,projectId,source.id);
    if(['reviewed','rejected'].includes(source.status)){for(const field of ['net','tax','gross'])economicsCents(source[field]);if(economicsCents(source.net)+economicsCents(source.tax)!==economicsCents(source.gross))throw invalid();}
  }return value.items;
}
export function economicsSummary(value,projectId) {
  if(!value||value.project_id!==projectId||value.currency!=='EUR'||value.valuation_basis!=='document_net'||value.tax_result_available!==false||value.result?.scope!=='recorded_sources_only'||typeof value.result.complete_for_recorded_sources!=='boolean'||!Array.isArray(value.issues))throw invalid();
  for(const [object,fields]of [[value.budget,['base_net','approved_changes_net','total_net']],[value.costs,['material_net','labor_net','external_service_net','machine_net','other_net','total_net']],[value.revenue,['invoiced_net','credited_net','revenue_net','invoiced_gross','credited_gross']],[value.payments,['receipts_gross','refunds_gross','net_inflow_gross','open_gross']]])for(const field of fields)economicsCents(object?.[field]);
  revision(value.budget.revision,true);
  const sum=fields=>fields.reduce((total,field)=>total+economicsCents(value.costs[field]),0n);
  if(sum(['material_net','labor_net','external_service_net','machine_net','other_net'])!==economicsCents(value.costs.total_net)||economicsCents(value.budget.base_net)+economicsCents(value.budget.approved_changes_net)!==economicsCents(value.budget.total_net)||economicsCents(value.revenue.invoiced_net)-economicsCents(value.revenue.credited_net)!==economicsCents(value.revenue.revenue_net)||economicsCents(value.payments.receipts_gross)-economicsCents(value.payments.refunds_gross)!==economicsCents(value.payments.net_inflow_gross))throw invalid();
  for(const [amount,expected]of [[value.budget.remaining_net,economicsCents(value.budget.total_net)-economicsCents(value.costs.total_net)],[value.result.document_net_contribution,economicsCents(value.revenue.revenue_net)-economicsCents(value.costs.total_net)]])if(amount!==null&&(!value.result.complete_for_recorded_sources||economicsCents(amount)!==expected))throw invalid('Ungeklärte Kosten dürfen kein vollständiges Ergebnis erzeugen.');
  for(const field of ['material_movements','approved_times','receipt_allocations','documents','payment_allocations'])if(!Array.isArray(value.sources?.[field]))throw invalid();
  if(typeof value.payments.complete!=='boolean')throw invalid();
  for(const key of ['supplier_outflows_gross','cash_balance_gross'])if(value.payments[key]!==null)economicsCents(value.payments[key]);
  if(!value.payments.complete&&(value.payments.supplier_outflows_gross!==null||value.payments.cash_balance_gross!==null))throw invalid('Nicht freigegebene Auszahlungen dürfen nicht als Nullsaldo erscheinen.');
  if(value.payments.complete&&economicsCents(value.payments.net_inflow_gross)-economicsCents(value.payments.supplier_outflows_gross)!==economicsCents(value.payments.cash_balance_gross))throw invalid();
  if(!Array.isArray(value.sources.supplier_payments))throw invalid();
  return value;
}
export function economicsPreviewInput(source,projectId,values,reason) {
  if(source.project_id!==projectId||!['reviewed','rejected'].includes(source.status))throw new Error('Zuerst das Original und seine Belegdaten prüfen.');
  const allocations=[];
  for(const category of Object.keys(ECONOMICS_CATEGORIES)){const raw=values[category];if(raw!==undefined&&String(raw).trim()!=='')allocations.push({category,amount_net:economicsAmount(raw)});}
  validateAllocations(allocations,source.net);
  if(source.status==='rejected'&&allocations.some(line=>line.category!=='excluded'))throw new Error('Ein zurückgewiesener Beleg kann nur ausdrücklich aus den Projektkosten ausgeschlossen werden.');
  allocations.sort((a,b)=>a.category.localeCompare(b.category));
  return {project_id:projectId,receipt_id:id(source.id),source_revision:revision(source.revision),expected_revision:revision(source.classification_revision,true),allocations,reason:text(reason,'Begründung',4000)};
}
export function economicsPreview(value,input) {
  if(!value||!HASH.test(value.preview_hash||''))throw invalid();
  for(const field of ['project_id','receipt_id','source_revision','expected_revision','reason'])if(value[field]!==input[field])throw invalid('Die Vorschau gehört nicht zur eingegebenen Einordnung.');
  if(!sameAllocations(value.allocations,input.allocations)||value.source?.receipt_id!==input.receipt_id)throw invalid();
  validateAllocations(value.allocations,value.source.net);return value;
}
export function economicsConfirmation(value,input,preview,actorId=null) {
  economicsEntry(value,input.project_id,input.receipt_id);
  if(value.revision!==input.expected_revision+1||value.source_revision!==input.source_revision||value.preview_hash!==preview.preview_hash||value.reason!==input.reason||!sameAllocations(value.allocations,input.allocations)||(actorId!==null&&value.created_by!==actorId)||value.source.source_hash!==preview.source.source_hash)throw invalid('Die Empfangsbestätigung stimmt nicht mit der geprüften Einordnung überein. Die ursprüngliche Anfrage bleibt offen.');
  return value;
}
export function economicsReviewInput(source,values) {
  const amount=raw=>{const text=String(raw).trim().replace(',','.');if(!/^\d{1,12}(?:\.\d{1,2})?$/.test(text))throw new Error('Belegbeträge mit höchstens zwei Nachkommastellen eingeben.');const [whole,fraction='']=text.split('.');return whole+'.'+fraction.padEnd(2,'0');};
  const result={revision:revision(source.revision,true),vendor:text(values.vendor,'Lieferant'),invoice_number:text(values.invoice_number,'Belegnummer'),issue_date:values.issue_date,net:amount(values.net),tax:amount(values.tax),gross:amount(values.gross),currency:'EUR',status:values.status,note:String(values.note||'').trim()};
  if(!['reviewed','rejected'].includes(result.status)||!/^\d{4}-\d{2}-\d{2}$/.test(result.issue_date)||result.note.length>2000)throw new Error('Belegdatum, Prüfentscheidung und Notiz prüfen.');
  if(economicsCents(result.net)+economicsCents(result.tax)!==economicsCents(result.gross))throw new Error('Netto und ausgewiesene Steuer müssen den Bruttobetrag ergeben.');
  return result;
}
const STATUS={unreviewed:'Belegdaten prüfen',unclassified:'Noch nicht eingeordnet',current:'Aktuell eingeordnet',source_changed:'Belegprüfung geändert · Einordnung klären'};

export function createProjectEconomics(ui) {
  const {api,biz,query,el,button,panel,row,rows,notice,empty,form:baseForm,field,dialog,closeModal,table,formatMoney,formatDate,mutation:baseMutation,action:baseAction,refresh,download,dateInput}=ui;
  const drafts=new Map(),uploads=new Map(),confirmations=new Map();let generation=api.generation;
  function deny(error){if([401,403,404].includes(error?.status))ui.onDenied?.();}
  async function secure(callback){try{return await callback();}catch(error){deny(error);throw error;}}
  const form=(title,fields,save,options)=>baseForm(title,fields,(values,key)=>secure(()=>save(values,key)),options);
  const action=(callback,target)=>baseAction(()=>secure(callback),target);
  const mutation=(...args)=>secure(()=>baseMutation(...args));
  function clear(){drafts.clear();uploads.clear();confirmations.clear();generation=api.generation;}
  function current(projectId,initialGeneration=generation){return api.generation===initialGeneration&&ui.projectId()===projectId;}
  function guard(projectId,initialGeneration=generation){if(!current(projectId,initialGeneration)){const error=new Error('Sitzung oder Projekt gewechselt.');error.name='StaleSession';throw error;}}
  function reset(){if(generation!==api.generation)clear();}
  async function authorize(projectId,kind='read'){
    reset();const before=api.generation,caps=await secure(()=>api.get(query(biz('/capabilities'),{project_id:projectId})));guard(projectId,before);
    const rights=economicsRights(caps,ui.organization());if(!rights[kind]){const error=new Error('Keine aktuelle Freigabe für diesen Schritt der Projektwirtschaftlichkeit.');error.status=403;deny(error);throw error;}return rights;
  }
  function remember(editor,key){const saved=drafts.get(key)||{};for(const [name,{input,spec}]of editor.controls){if(Object.hasOwn(saved,name)){if(spec.type==='checkbox')input.checked=!!saved[name];else input.value=saved[name];}input.addEventListener('input',()=>{drafts.set(key,Object.fromEntries([...editor.controls].map(([name,{input,spec}])=>[name,spec.type==='checkbox'?input.checked:input.value])));});}return editor;}
  function sourceOriginal(source){return button('Original ansehen',()=>action(()=>download(biz('/finance/receipts/'+source.id+'/original'),source.filename)),'small');}
  async function sourceDetail(projectId,source){await authorize(projectId);guard(projectId);dialog('Kostenquelle',panel(source.vendor||source.filename,el('p',{},source.invoice_number||'Noch nicht geprüft'),el('p',{},'Original SHA-256: '+source.sha256),sourceOriginal(source),el('p',{},'Netto: '+formatMoney(source.net)+' · Steuer laut Beleg: '+formatMoney(source.tax)+' · Brutto: '+formatMoney(source.gross))));}
  async function history(projectId,source){const before=api.generation;await authorize(projectId);const value=await api.get(query(biz('/project-economics/receipts/'+source.id),{project_id:projectId}));guard(projectId,before);if(!Array.isArray(value?.items))throw invalid();const items=value.items.map(item=>economicsEntry(item,projectId,source.id));dialog('Einordnungshistorie',el('div',{class:'stack'},sourceOriginal(source),rows(items.slice().reverse(),item=>panel('Fassung '+item.revision,el('p',{},formatDate(item.created_at,true)+' · '+item.reason),el('p',{},'Belegprüfung '+item.source_revision+' · '+item.source.invoice_number+' · '+formatMoney(item.source.net)),table(['Kategorie','Belegnetto'],item.allocations.map(line=>[ECONOMICS_CATEGORIES[line.category],formatMoney(line.amount_net)])),el('p',{class:'caption'},'Nachweis: '+item.entry_hash)),'Noch keine Einordnung bestätigt.')));}
  async function review(projectId,source){const before=api.generation;await authorize(projectId,'review');const fresh=await api.get(biz('/finance/receipts/'+source.id));guard(projectId,before);if(fresh.project_id!==projectId)throw invalid();const key='economics-review-'+source.id;
    const editor=form('',[field('vendor','Lieferant','text',fresh.vendor||fresh.suggestion?.vendor||'',{required:true}),field('invoice_number','Belegnummer','text',fresh.invoice_number||fresh.suggestion?.invoice_number||'',{required:true}),field('issue_date','Belegdatum','date',fresh.issue_date||fresh.suggestion?.issue_date||dateInput(),{required:true}),field('net','Netto laut Beleg EUR','decimal',fresh.net||'',{required:true}),field('tax','Ausgewiesene Steuer EUR','decimal',fresh.tax||'',{required:true}),field('gross','Brutto laut Beleg EUR','decimal',fresh.gross||'',{required:true}),field('status','Prüfentscheidung','select','reviewed',{options:[['reviewed','Original und Belegdaten geprüft'],['rejected','Beleg zurückweisen']],required:true}),field('note','Prüfnotiz','textarea',fresh.note||'',{maxLength:2000}),field('checked','Ich habe das Original geöffnet und die Angaben damit abgeglichen.','checkbox',false,{required:true})],async values=>{if(!values.checked)throw new Error('Das Original zuerst prüfen.');const body=economicsReviewInput(fresh,values);await authorize(projectId,'review');guard(projectId,before);const result=await mutation(key,'/finance/receipts/'+source.id,body,{validate:value=>{if(value.id!==source.id||value.project_id!==projectId||value.revision!==body.revision+1||Object.entries(body).some(([key,v])=>key!=='revision'&&value[key]!==v))throw invalid('Die Belegprüfung wurde nicht mit denselben Angaben bestätigt.');}});guard(projectId,before);drafts.delete(key);return result;},{key,submit:'Belegprüfung speichern',extra:el('div',{},sourceOriginal(fresh)),description:'Die Prüfung bestätigt Belegdaten, keine Zahlung und keine steuerliche Behandlung.'});remember(editor,key);dialog('Eingangsbeleg prüfen',editor);
  }
  async function classify(projectId,source){const before=api.generation;await authorize(projectId,'classify');const values=economicsSources(await api.get(query(biz('/project-economics/sources'),{project_id:projectId})),projectId);guard(projectId,before);source=values.find(value=>value.id===source.id);if(!source||!['reviewed','rejected'].includes(source.status))throw new Error('Der Eingangsbeleg muss zunächst geprüft werden.');
    const key='economics-classify-'+source.id,pendingKey='economics-confirm-'+source.id;
    if(api.pendingOperations().some(op=>op.key===pendingKey)){return pending(projectId,source,pendingKey);}
    const amounts=Object.fromEntries((source.latest_entry?.allocations||[]).map(line=>[line.category,line.amount_net]));
    const editor=form('',[...Object.entries(ECONOMICS_CATEGORIES).filter(([category])=>source.status!=='rejected'||category==='excluded').map(([category,label])=>field(category,label+' netto EUR','decimal',amounts[category]||'',{help:category==='stock_material'?'Diese Belegposition wird nicht erneut als Kosten gezählt; Kosten entstehen über die Materialentnahme.':category==='excluded'?'Begründet außerhalb der Projektkosten. Die Einordnung bleibt in der Historie.':'Nicht verwendete Kategorien leer lassen.'})),field('reason','Begründung der Einordnung','textarea','',{required:true,maxLength:4000})],async values=>{await authorize(projectId,'classify');guard(projectId,before);const input=economicsPreviewInput(source,projectId,values,values.reason);const preview=economicsPreview(await api.post(biz('/project-economics/preview'),input),input);guard(projectId,before);confirm(projectId,source,input,preview);return undefined;},{key,submit:'Einordnung prüfen',description:(source.status==='rejected'?'Dieser Beleg wurde zurückgewiesen. Nur ein begründeter Ausschluss ist zulässig. ':'')+'Den vollständigen geprüften Nettobetrag von '+formatMoney(source.net)+' einordnen. Die Vorschau speichert keine Projektkosten.',extra:el('div',{},sourceOriginal(source))});remember(editor,key);dialog(source.latest_entry?'Einordnung korrigieren':'Belegkosten einordnen',editor);
  }
  function confirm(projectId,source,input,preview){const before=api.generation,key='economics-confirm-'+source.id,body={...input,preview_hash:preview.preview_hash};confirmations.set(key,{projectId,source,input,preview,generation:before});
    const editor=form('',[field('confirmed','Ich bestätige diese vollständige Belegeinordnung für das Projekt.','checkbox',false,{required:true})],async values=>{if(!values.confirmed)throw new Error('Einordnung ausdrücklich bestätigen.');await authorize(projectId,'classify');guard(projectId,before);const result=await mutation(key,'/project-economics/confirm',body,{validate:value=>economicsConfirmation(value,input,preview,ui.actorId())});guard(projectId,before);confirmations.delete(key);drafts.delete('economics-classify-'+source.id);return result;},{key,submit:'Einordnung verbindlich festhalten',extra:el('div',{class:'stack'},panel(source.vendor+' · '+source.invoice_number,el('p',{},'Geprüfter Nettobetrag: '+formatMoney(preview.source.net)),table(['Kategorie','Belegnetto'],preview.allocations.map(line=>[ECONOMICS_CATEGORIES[line.category],formatMoney(line.amount_net)])),el('p',{},preview.reason),sourceOriginal(source))),description:'Eine neue Fassung ersetzt die vorherige Einordnung für die Auswertung. Beide Fassungen bleiben nachvollziehbar. Keine Zahlung und keine Steuerbuchung.'});dialog('Einordnung bestätigen',editor);
  }
  function pending(projectId,source,key){dialog('Antwort der Einordnung noch offen',el('div',{class:'stack'},notice('Der Server kann diese Fassung bereits gespeichert haben. Nur die ursprüngliche Anfrage unverändert wiederholen.','warn'),button('Ursprüngliche Anfrage erneut senden',()=>action(async()=>{const before=api.generation;await authorize(projectId,'classify');const result=economicsEntry(await api.retry(key),projectId,source.id);guard(projectId,before);confirmations.delete(key);drafts.delete('economics-classify-'+source.id);closeModal();await refresh();return result;}),'primary')));}
  async function upload(projectId){const before=api.generation;await authorize(projectId,'capture');guard(projectId,before);const record=uploads.get(projectId)||{};uploads.set(projectId,record);
    const file=el('input',{type:'file',accept:'application/pdf,image/jpeg,image/png','aria-label':'Belegoriginal auswählen'}),selected=el('p',{},record.file?.name||'Noch kein Original ausgewählt.'),progress=el('progress',{max:1,value:0,'aria-label':'Belegübertragung'});
    file.addEventListener('change',()=>{if(record.locked){file.value='';selected.textContent=record.file.name+' · begonnene Übertragung zuerst abschließen';return;}record.file=file.files?.[0];selected.textContent=record.file?.name||'Noch kein Original ausgewählt.';});
    const key='economics-upload-'+projectId,editor=form('',[field('note','Notiz zum Beleg','textarea',record.note||'',{maxLength:2000})],async values=>{await authorize(projectId,'capture');guard(projectId,before);if(!record.file)throw new Error('Bitte ein Belegoriginal auswählen.');if(record.locked&&record.note!==values.note)throw new Error('Die begonnene Übertragung mit unveränderter Notiz abschließen.');const original=record.file;if(original.size<1||original.size>20*1024*1024||!['application/pdf','image/jpeg','image/png'].includes(original.type))throw new Error('PDF, JPEG oder PNG mit höchstens 20 MiB auswählen.');record.note=values.note;record.locked=true;file.disabled=true;
      const bytes=new Uint8Array(await original.arrayBuffer());if(original.type==='application/pdf'){if(new TextDecoder().decode(bytes.subarray(0,5))!=='%PDF-'){record.locked=false;file.disabled=false;throw new Error('Das Original ist keine gültige PDF-Datei.');}}else{let bitmap;try{bitmap=await createImageBitmap(original);if(bitmap.width*bitmap.height>40000000||Math.max(bitmap.width,bitmap.height)>15000)throw new Error('Das Belegfoto überschreitet die zulässige Bildgröße.');}catch(error){record.locked=false;file.disabled=false;throw error;}finally{bitmap?.close();}}const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),value=>value.toString(16).padStart(2,'0')).join('');guard(projectId,before);const uploadKey=projectId+':'+sha+':'+original.name;
      if(!record.media)record.media=await mutation('economics-media-'+uploadKey,'/receipt-media',{project_id:projectId,filename:original.name,media_type:original.type,size:bytes.length,sha256:sha,purpose:'receipt',classification:'financial',caption:values.note},{validate:value=>{id(value.id);if(value.project_id!==projectId||value.sha256!==sha||value.size!==bytes.length||value.filename!==original.name||value.purpose!=='receipt'||value.classification!=='financial')throw invalid('Das Belegoriginal wurde nicht für dieses Projekt vorgemerkt.');}});guard(projectId,before);
      const metadata=await api.get(biz('/receipt-media/'+record.media.id));guard(projectId,before);if(metadata.project_id!==projectId||metadata.sha256!==sha||metadata.size!==bytes.length)throw invalid('Die Uploadbestätigung gehört nicht zu diesem Belegoriginal.');const chunks=new Set(metadata.uploaded_chunks||[]);if(!Number.isSafeInteger(metadata.chunk_size)||metadata.chunk_size<1||metadata.chunk_size>262144)throw invalid();progress.max=bytes.length;
      for(let index=0,offset=0;offset<bytes.length;index++,offset+=metadata.chunk_size){await authorize(projectId,'capture');guard(projectId,before);const part=bytes.subarray(offset,Math.min(offset+metadata.chunk_size,bytes.length));if(!chunks.has(index))await api.post(biz('/receipt-media/'+record.media.id+'/chunks/'+index),{content_base64:ui.bytesBase64(part)});guard(projectId,before);progress.value=offset+part.length;}
      await mutation('economics-complete-'+record.media.id,'/receipt-media/'+record.media.id+'/complete',{}, {validate:value=>{if(value.id!==record.media.id||value.project_id!==projectId||value.sha256!==sha||value.status!=='ready')throw invalid('Die Belegübertragung wurde nicht vollständig bestätigt.');}});guard(projectId,before);const captured=await mutation('economics-receipt-'+record.media.id,'/finance/receipts',{project_id:projectId,media_id:record.media.id,note:values.note},{validate:value=>{id(value.id);if(value.project_id!==projectId||value.sha256!==sha||value.filename!==original.name||value.media_type!==original.type||value.status!=='needs_review')throw invalid('Das Belegoriginal wurde nicht eindeutig bestätigt.');}});guard(projectId,before);if(captured.project_id!==projectId||captured.sha256!==sha)throw invalid('Der gespeicherte Beleg bestätigt nicht das hochgeladene Original.');uploads.delete(projectId);return captured;
    },{key,submit:'Original speichern und prüfen',description:'Das Original wird unverändert in die geschützte Belegablage übertragen. Es entstehen noch keine Projektkosten und keine Zahlung.',extra:el('div',{class:'stack'},file,selected,progress),after:async captured=>{await refresh();if(current(projectId,before)){const freshRights=await authorize(projectId);if(freshRights.review)await review(projectId,captured);else dialog('Belegoriginal gespeichert',notice('Das Original ist gespeichert. Für die Belegprüfung ist eine Freigabe zur Finanzprüfung erforderlich.'));}}});dialog('Projektbeleg erfassen',editor);
  }
  function identity(item){return [item.id||'',item.entry_id||'',item.receipt_id||'',item.category||'',item.payment_id||'',item.document_id||'',item.event_id||'',item.work_date||''].join('|');}
  function evidenceFields(kind,item){
    const fields=[];
    if(item.number)fields.push(['Belegnummer',item.number]);
    if(item.invoice_number)fields.push(['Eingangsbeleg',item.invoice_number]);
    if(item.vendor)fields.push(['Lieferant',item.vendor]);
    if(item.category)fields.push(['Einordnung',ECONOMICS_CATEGORIES[item.category]||item.category]);
    if(item.article_name||item.article_snapshot?.name)fields.push(['Artikel',item.article_name||item.article_snapshot.name]);
    if(item.quantity)fields.push(['Menge',String(item.quantity)+' '+(item.unit||item.article_snapshot?.unit||'')]);
    if(item.kind)fields.push(['Art',({issue:'Materialentnahme',return:'Materialrückgabe',receipt:'Kundenzahlung',refund:'Erstattung',invoice:'Rechnung',credit_note:'Gutschrift',supplier_payout:'Lieferantenauszahlung'})[item.kind]||item.kind]);
    if(item.work_date)fields.push(['Arbeitstag',formatDate(item.work_date)]);
    if(item.net_seconds!==undefined)fields.push(['Genehmigte Zeit',ui.duration(item.net_seconds)]);
    if(Number.isSafeInteger(item.hourly_cost_minor))fields.push(['Historischer Stundensatz',formatMoney((item.hourly_cost_minor/100).toFixed(2))]);
    if(item.supplement_percent!==undefined)fields.push(['Historischer Zuschlag',String(item.supplement_percent)+' %']);
    if(item.cost_state==='missing_rate')fields.push(['Kostenstatus','Kostensatz fehlt; keine vollständige Kostenaussage.']);
    for(const [key,label]of [['cost_net','Kosten netto'],['amount_net','Eingeordneter Nettobetrag'],['net','Netto'],['gross','Brutto'],['amount_gross','Zugeordneter Bruttobetrag'],['amount','Geldfluss']])if(item[key]!==undefined)fields.push([label,formatMoney(item[key])]);
    if(Number.isSafeInteger(item.cost_minor))fields.push(['Zeitkosten netto',item.cost_state==='missing_rate'?'Nicht vollständig ermittelt':formatMoney((item.cost_minor/100).toFixed(2))]);
    for(const [key,label]of [['booking_date','Buchungstag'],['cash_date','Geldflusstag'],['issue_date','Belegdatum'],['created_at','Erfasst']])if(item[key])fields.push([label,formatDate(item[key],key==='created_at')]);
    if(item.note)fields.push(['Notiz',item.note]);
    if(item.classification_status)fields.push(['Einordnungsstand',STATUS[item.classification_status]||item.classification_status]);
    if(item.revision)fields.push(['Fassung',String(item.revision)]);
    if(item.source_revision)fields.push(['Zugrunde liegende Belegprüfung',String(item.source_revision)]);
    return fields;
  }
  function sourceLink(projectId,item,label='Quelle öffnen',kind=null){
    const path=item.source_path||item.source?.source_path;
    if(!kind&&(typeof path!=='string'||!/^\/(?:finance\/receipts|documents)\/[a-f0-9]{32}$/.test(path)))return null;
    return button(label,()=>action(async()=>{
      const before=api.generation;await authorize(projectId);guard(projectId,before);
      if(!kind&&path.startsWith('/finance/receipts/')){const value=await api.get(biz(path));guard(projectId,before);await sourceDetail(projectId,value);return;}
      if(!kind&&path.startsWith('/documents/')){await ui.documentDetail(path.split('/')[2]);return;}
      const fresh=economicsSummary(await api.get(query(biz('/project-economics'),{project_id:projectId})),projectId);guard(projectId,before);
      const source=fresh.sources[kind].find(value=>identity(value)===identity(item));if(!source)throw new Error('Die Quelle wurde inzwischen geändert. Die Übersicht neu laden.');
      const controls=[];if(source.source_path?.startsWith('/documents/'))controls.push(button('Rechnungsbeleg öffnen',()=>action(()=>ui.documentDetail(source.source_path.split('/')[2])),'small'));
      if(source.source_path?.startsWith('/finance/receipts/'))controls.push(button('Belegoriginal ansehen',()=>action(()=>download(biz(source.source_path+'/original'),source.filename||'Belegoriginal')),'small'));
      dialog('Quellnachweis',panel('Gespeicherte Projektquelle',table(['Angabe','Nachweis'],evidenceFields(kind,source)),el('div',{class:'actions'},controls),el('p',{class:'caption'},'Quelle: '+(source.id||source.entry_id||source.payment_id||source.event_id||source.receipt_id||'Projektzuordnung'))));
    }),'small');
  }
  async function budgetPanel(projectId,summary){
    const before=api.generation,[rawBudgets,rawChanges]=await Promise.all([api.get(query(biz('/budgets'),{project_id:projectId})),api.get(biz('/projects/'+projectId+'/changes'))]);guard(projectId,before);
    if(!Array.isArray(rawBudgets?.items)||!Array.isArray(rawChanges?.items))throw invalid();
    const budget=rawBudgets.items[0]||{},changes=rawChanges.items;
    return el('div',{class:'stack'},panel('Nachträge',rows(changes,item=>row(item.title,formatMoney(item.amount_net),[el('span',{class:'badge'},item.approved?'Freigegeben':'Vorschlag'),!item.approved&&ui.canWrite('finance.approve','material')?button('Nachtrag freigeben',()=>ui.confirmDialog('Nachtrag freigeben','Das Projektbudget wird um '+formatMoney(item.amount_net)+' erhöht. Die ursprüngliche Fassung bleibt erhalten.',async()=>{await mutation('approve-change-'+item.id,'/projects/'+projectId+'/changes/'+item.id+'/approve',{revision:item.revision});await refresh();}),'small'):null]))),
      ui.canWrite('finance.write','material')?form('Budget festlegen',[...['material_net','labor_net','machine_net','other_net'].map((key,index)=>field(key,['Material netto EUR','Lohn netto EUR','Maschinen netto EUR','Sonstige Kosten netto EUR'][index],'decimal',budget[key]||'0.00',{required:true}))],(values,key)=>mutation(key,'/budgets',{...values,project_id:projectId,...(summary.budget.revision?{revision:summary.budget.revision}:{})}),{key:'budget-'+projectId,submit:'Neue Budgetfassung speichern'}):null,
      ui.canWrite('finance.write','material')?form('Nachtrag erfassen',[field('title','Nachtrag','text','',{required:true}),field('amount_net','Zusätzlicher Budgetbetrag netto EUR','decimal','',{required:true}),...(ui.canWrite('finance.approve','material')?[field('approved','Nachtrag ausdrücklich freigeben','checkbox',false)]:[])],(values,key)=>mutation(key,'/projects/'+projectId+'/changes',values),{key:'change-'+projectId}):null);
  }
  async function render(projectId){reset();const before=api.generation,rights=await authorize(projectId),[raw,sourcePage]=await Promise.all([api.get(query(biz('/project-economics'),{project_id:projectId})),api.get(query(biz('/project-economics/sources'),{project_id:projectId}))]);guard(projectId,before);const summary=economicsSummary(raw,projectId),sources=economicsSources(sourcePage,projectId),metric=(title,value,description)=>panel(title,el('div',{class:'metric'},formatMoney(value)),el('p',{class:'metric-sub'},description));
    const result=el('div',{class:'stack project-economics'},notice('Belegnetto-Vergleich für erfasste Quellen. Kein steuerlicher Gewinn; noch nicht erfasste Kosten sind nicht enthalten.'),summary.issues.length?panel('Offene Klärungen',rows(summary.issues,item=>row(item.message,item.code,[sourceLink(projectId,item)]))):null,
      el('div',{class:'grid'},metric('Erfasste Projektkosten netto',summary.costs.total_net,'Material, genehmigte Zeiten und eingeordnete Belege'),metric('Rechnungsumsatz netto',summary.revenue.revenue_net,'Festgeschriebene Rechnungen abzüglich Gutschriften'),metric('Belegter Beitrag netto',summary.result.document_net_contribution,summary.result.complete_for_recorded_sources?'Nur der Vergleich erfasster Quellen; kein vollständiger Unternehmensgewinn.':'Wegen offener Klärungen nicht berechnet.')),
      panel('Kostenquellen',table(['Kostenart','Netto'],[['Materialentnahmen',summary.costs.material_net],['Genehmigte Zeiten',summary.costs.labor_net],['Fremdleistungen',summary.costs.external_service_net],['Maschinenkosten',summary.costs.machine_net],['Sonstige Kosten',summary.costs.other_net]].map(([label,amount])=>[label,formatMoney(amount)]))),
      el('div',{class:'grid'},metric('Budget einschließlich Nachträge',summary.budget.total_net,'Basis '+formatMoney(summary.budget.base_net)+' · Freigegebene Nachträge '+formatMoney(summary.budget.approved_changes_net)),metric('Rest zum Budget',summary.budget.remaining_net,'Budget abzüglich erfasster Kosten; bei offenen Kosten nicht berechnet.'),metric('Zahlungszufluss nach Erstattungen',summary.payments.net_inflow_gross,'Tatsächliche zugeordnete Bruttozahlungen; getrennt vom Nettoumsatz.')),
      panel('Zahlungen und offene Posten',el('p',{},'Zahlungseingänge brutto: '+formatMoney(summary.payments.receipts_gross)),el('p',{},'Erstattungen brutto: '+formatMoney(summary.payments.refunds_gross)),el('p',{},'Offene Forderungen brutto: '+formatMoney(summary.payments.open_gross)),el('p',{},'Bestätigte Lieferantenauszahlungen brutto: '+formatMoney(summary.payments.supplier_outflows_gross)),el('p',{},'Saldo zugeordneter Geldflüsse: '+formatMoney(summary.payments.cash_balance_gross)),!summary.payments.complete?notice('Lieferantenauszahlungen sind in dieser Freigabe nicht vollständig sichtbar. Ein Zahlungssaldo wird deshalb nicht berechnet.','warn'):null),
      panel('Eingangsbelege und Kosten',rights.capture?button('Projektbeleg erfassen',()=>action(()=>upload(projectId)),'primary'):null,rows(sources,source=>row(source.vendor?source.vendor+' · '+source.invoice_number:source.filename,(source.status==='rejected'?'Zurückgewiesen · ':'')+STATUS[source.classification_status]+' · '+formatMoney(source.net),[sourceOriginal(source),rights.review?button('Belegdaten prüfen',()=>action(()=>review(projectId,source)),'small'):null,rights.classify&&['reviewed','rejected'].includes(source.status)?button(source.latest_entry?'Einordnung korrigieren':'Kosten einordnen',()=>action(()=>classify(projectId,source)),'small'):null,source.classification_revision?button('Historie',()=>action(()=>history(projectId,source)),'small'):null]))));
    for(const [key,title]of [['material_movements','Materialnachweise'],['approved_times','Zeitnachweise'],['receipt_allocations','Belegeinordnungen mit Herkunft'],['documents','Rechnungen und Gutschriften'],['payment_allocations','Zahlungszuordnungen'],['supplier_payments','Bestätigte Lieferantenauszahlungen']])result.append(panel(title,rows(summary.sources[key],item=>row(item.title||item.number||item.invoice_number||item.article_name||item.receipt_id||item.entry_id||item.id||'Nachweis',item.amount_net!==undefined?(ECONOMICS_CATEGORIES[item.category]?ECONOMICS_CATEGORIES[item.category]+' · ':'')+formatMoney(item.amount_net):item.cost_net!==undefined?formatMoney(item.cost_net):item.net!==undefined?formatMoney(item.net):item.amount_gross!==undefined?formatMoney(item.amount_gross):item.amount!==undefined?formatMoney(item.amount):Number.isSafeInteger(item.cost_minor)?formatMoney((item.cost_minor/100).toFixed(2)):item.work_date?formatDate(item.work_date):'', [sourceLink(projectId,item,'Quelle öffnen',key)]))));
    result.append(await budgetPanel(projectId,summary));guard(projectId,before);return result;
  }
  return {render,clear};
}
