/* Explicit physical origin, with existing authenticated commands and dialogs. */
export function assetOriginValues(source, values, asset=null) {
  if (!source || !/^[a-f0-9]{32}$/.test(source.receipt_id) || !Number.isSafeInteger(source.line_index) || source.line_index<0)
    throw new Error('Eine gültige Lieferposition auswählen.');
  if (!source.document_accessible || !source.document)
    throw new Error('Zuerst das zugängliche Original des Lieferscheins zuordnen.');
  const issue=source.issues?.find(item=>item.id===values.issue_movement_id);
  if (!issue) throw new Error('Eine passende Entnahme aus dem Empfangslager auswählen.');
  const amount=String(values.quantity??'').trim().replace(',','.');
  if (!/^\d{1,12}(?:\.\d{1,4})?$/.test(amount)||/^0*(?:\.0*)?$/.test(amount))
    throw new Error('Eine positive Menge mit höchstens vier Nachkommastellen eingeben.');
  if (values.confirmed!==true) throw new Error('Die tatsächliche Geräteherkunft ausdrücklich bestätigen.');
  const result={receipt_id:source.receipt_id,line_index:source.line_index,issue_movement_id:issue.id,quantity:amount,confirmed:true};
  if (asset) return {...result,asset_revision:asset.revision};
  const name=String(values.name??'').trim(),serial=String(values.serial_number??'').trim();
  if (!name||!serial) throw new Error('Gerätename und Seriennummer eingeben.');
  return {...result,asset:{name,serial_number:serial,asset_type:String(values.asset_type??'').trim(),location:String(values.location??'').trim(),notes:String(values.notes??'').trim()}};
}

export function assetProvenanceUi(h) {
  const {el,button,field,form,dialog,panel,rows,row,notice,table,api,biz,query,mutation,action,download,refresh,formatDate,formatQuantity}=h;
  function allowed(project) { return h.allowed(project); }
  function check(project,write=false) {
    if (!allowed(project)||(write&&!h.writable(project))) throw new Error('Die aktuelle Freigabe für diese Geräteherkunft fehlt.');
  }
  function show(project,title,body,description='') {
    check(project);body.setAttribute('data-asset-origin-detail',project);return dialog(title,body,description);
  }
  async function document(project,receiptId) {
    check(project);let result;
    try { result=await api.get(biz(`/purchasing/receipts/${receiptId}/document`)); }
    catch(error) {
      check(project);if(error.status!==404)throw error;
      show(project,'Original-Lieferschein fehlt',el('div',{class:'stack'},notice('Für diesen Wareneingang ist noch kein Original zugeordnet.'),
        h.writable(project)?button('Original auswählen',()=>action(()=>attach(project,receiptId)),'primary'):null));return;
    }
    check(project);
    show(project,'Original-Lieferschein',el('div',{class:'stack'},
      el('p',{},`Lieferung ${result.receipt_reference} · Bestellung ${result.order_reference}`),
      el('p',{},result.original.filename),el('p',{class:'caption'},`Original SHA-256: ${result.original.sha256}`),
      button('Original herunterladen',()=>action(async()=>{check(project);await download(biz(result.download_path),result.original.filename);}),'primary')));
  }
  async function attach(project,receiptId) {
    check(project,true);
    const result=await api.get(query(biz('/media'),{project_id:project}));check(project,true);
    const media=(Array.isArray(result)?result:result.items||[]).filter(item=>item.status==='ready'&&['document','site_photo'].includes(item.purpose));
    if(!media.length) { show(project,'Original-Lieferschein fehlt',notice('Das Original zuerst im selben Projekt unter Fotos & Doku hochladen. Danach hier auswählen.','warn'));return; }
    const editor=form('',[
      field('media_id','Original des Lieferscheins','select','',{required:true,options:media.map(item=>[item.id,item.filename])}),
      field('confirmed','Ich habe Original und Wareneingang geprüft und ordne diesen Lieferschein dauerhaft zu.','checkbox',false,{required:true}),
    ],(data,key)=>{check(project,true);return mutation(key,`/purchasing/receipts/${receiptId}/document`,{media_id:data.media_id,confirmed:data.confirmed});},
    {key:'delivery-document-'+receiptId,submit:'Original verbindlich zuordnen',after:async()=>{await refresh();await document(project,receiptId);}});
    show(project,'Lieferschein zuordnen',editor,'Die Originaldatei und ihre Prüfsumme bleiben mit diesem Wareneingang verbunden.');
  }
  function create(project,source,asset=null) {
    check(project,true);
    const fields=asset?[]:[field('name','Gerät','text',source.article.name,{required:true}),
      field('serial_number','Seriennummer','text','',{required:true}),field('asset_type','Anlagentyp','text',''),
      field('location','Standort / Raum','text',''),field('notes','Hinweise','textarea','')];
    fields.push(field('issue_movement_id','Tatsächliche Materialentnahme','select','',{required:true,
      options:source.issues.map(item=>[item.id,`Entnahme ${item.sequence_number} · noch ${formatQuantity(item.available_quantity,source.article.unit)}`])}),
      field('quantity','Zugeordnete Menge','text','1',{required:true,inputMode:'decimal'}),
      field('confirmed','Ich bestätige, dass dieses Gerät tatsächlich aus der genannten Lieferung und Entnahme stammt.','checkbox',false,{required:true}));
    const key=`asset-origin-${asset?.id||project}-${source.receipt_id}-${source.line_index}`;
    const editor=form('',fields,async(data,requestKey)=>{
      check(project,true);const values=assetOriginValues(source,data,asset);
      return mutation(requestKey,asset?`/assets/${asset.id}/origin`:'/assets/from-delivery',asset?values:{...values,project_id:project});
    },{key,submit:asset?'Herkunft verbindlich zuordnen':'Gerät und Herkunft anlegen',after:async()=>{await refresh();await sources(project);}});
    show(project,asset?'Geräteherkunft zuordnen':'Gerät aus Lieferung anlegen',editor,
      `Bestellung ${source.order_reference} · Lieferschein ${source.receipt_reference} · Position ${source.line_index+1}. Die gewichtete Lagerbewertung wird nicht erneut gebucht.`);
  }
  async function sources(project,asset=null,offset=0) {
    check(project);const result=await api.get(query(biz('/assets/origin-sources'),{project_id:project,limit:25,offset}));check(project);
    const body=el('div',{class:'stack'},notice('Die Herkunft wird ausdrücklich bestätigt. Lieferungen und Entnahmen werden nicht automatisch nach FIFO zugeordnet. Direkte Entnahmen aus dem Empfangslager sind auswählbar.'),
      rows(result.items||[],source=>row(`${source.article.name} · ${source.receipt_reference}`,
        `${source.order_reference} · Position ${source.line_index+1} · verfügbar ${formatQuantity(source.available_quantity,source.article.unit)}`,[
        source.document_accessible?button('Original-Lieferschein',()=>action(()=>document(project,source.receipt_id)),'small'):
          h.writable(project)?button('Lieferschein zuordnen',()=>action(()=>attach(project,source.receipt_id)),'small'):null,
        source.document_accessible&&Number(source.available_quantity)>0&&source.issues.length&&h.writable(project)?button(asset?'Diesem Gerät zuordnen':'Gerät aus Lieferung',()=>create(project,source,asset),'primary'):null,
      ]),'Noch keine projektgebundenen Lieferpositionen vorhanden.'),
      el('div',{class:'actions'},offset>0?button('Vorherige Lieferpositionen',()=>action(()=>sources(project,asset,Math.max(0,offset-25)))):null,
        result.next_offset!==null&&result.next_offset!==undefined?button('Weitere Lieferpositionen',()=>action(()=>sources(project,asset,result.next_offset))):null));
    show(project,asset?'Lieferherkunft für '+asset.name:'Lieferungen und Geräte',body);
  }
  async function origin(project,asset) {
    check(project);let result;
    try { result=await api.get(biz(`/assets/${asset.id}/origin`)); }
    catch(error) {
      check(project);if(error.status!==404)throw error;
      show(project,'Geräteherkunft · '+asset.name,el('div',{class:'stack'},notice('Für dieses bestehende Gerät ist noch keine Lieferherkunft bestätigt.'),
        h.writable(project)?button('Lieferherkunft auswählen',()=>action(()=>sources(project,asset)),'primary'):null));return;
    }
    check(project);
    const history=await api.get(query(biz('/maintenance/history'),{project_id:project,asset_id:asset.id}));check(project);
    const body=el('div',{class:'stack'},
      table(['Quelle','Bestätigter Stand'],[['Gerät / Seriennummer',`${asset.name} · ${result.serial_number}`],
        ['Bestellung',result.order_reference],['Lieferschein',`${result.receipt_reference} · ${formatDate(result.received_on)}`],
        ['Lieferposition',`${result.line_index+1} · ${result.article.name}`],['Materialentnahme',String(result.issue_sequence_number)],
        ['Zugeordnete Menge',formatQuantity(result.quantity,result.article.unit)]]),
      el('div',{class:'actions'},button('Original-Lieferschein',()=>action(()=>document(project,result.receipt_id)),'primary'),
        button('Bestellung öffnen',()=>action(()=>h.openOrder(result.order_id)),'small'),
        button('Materialentnahme öffnen',()=>action(async()=>{const movement=await api.get(biz('/inventory/movements/'+result.issue_movement_id));check(project);
          show(project,'Materialentnahme',el('div',{class:'stack'},table(['Angabe','Wert'],[['Artikel',movement.article_snapshot?.name||result.article.name],['Menge',formatQuantity(movement.quantity,result.article.unit)],['Erfasst',formatDate(movement.created_at,true)],['Entnahme',String(movement.sequence_number)]])));}),'small')),
      panel('Wartung für dieses Gerät',rows(Array.isArray(history)?history:history.items||[],visit=>row(visit.contract_snapshot?.title||'Wartung',`${formatDate(visit.due_date)} · ${{completed:'Abgeschlossen',planned:'Geplant'}[visit.status]||visit.status}`,[
        visit.status==='completed'?button('Service-PDF',()=>action(()=>download(biz(`/service-reports/${visit.report_id}/pdf`),'Servicebericht.pdf')),'small'):null
      ]),'Noch keine Wartung für dieses Gerät geplant.')));
    show(project,'Geräteherkunft · '+asset.name,body,'Die Zuordnung erzeugt keine zusätzliche Lagerbewegung und keine zusätzlichen Kosten.');
  }
  return {sources,origin,attach,document,allowed};
}
