/* Physical inventory: a count is not a delivery or project consumption. */
const ID=/^[a-f0-9]{32}$/;
export const inventoryCountStatus={open:'Zählung offen',counted:'Gezählt, Freigabe offen',approved:'Bestandsdifferenz freigegeben',cancelled:'Abgebrochen'};
const fail=(message,status=0)=>Object.assign(new Error(message),{status});
export function inventoryQuantity(value){
  const amount=String(value??'').trim().replace(',','.');
  if(!/^\d{1,12}(?:\.\d{1,4})?$/.test(amount))throw fail('Eine nichtnegative Menge mit höchstens vier Nachkommastellen angeben.');
  const [whole,fraction='']=amount.split('.');return BigInt(whole).toString()+'.'+fraction.padEnd(4,'0');
}
export function inventoryCountValues(record,values){
  if(!ID.test(record?.id||'')||!Number.isSafeInteger(record.revision)||!Array.isArray(record.items)||!record.items.length)throw fail('Eine gültige Inventurfassung auswählen.');
  return {revision:record.revision,lines:record.items.map(item=>{
    const id=item.article.id,quantity=inventoryQuantity(values['quantity_'+id]),reason=String(values['reason_'+id]??'').trim();
    if(quantity!==inventoryQuantity(item.on_hand)&&!reason)throw fail('Jede Bestandsdifferenz begründen.');
    return {article_id:id,quantity,reason};
  })};
}
export function inventoryCountRights(caps){
  const p=new Set(caps?.permissions||[]),module=caps?.organization?.modules?.material;
  const read=(caps?.features||[]).includes('inventory_counts')&&(caps?.capabilities||[]).includes('business_inventory_counts')&&p.has('inventory.read');
  const write=read&&caps.readonly===false&&module?.enabled!==false&&p.has('inventory.write');
  return {read,write,approve:write&&['finance.read','finance.write','finance.approve'].every(value=>p.has(value))};
}
export function inventoryCountRecord(value,{id=null,revision=null,status=null}={}){
  if(!ID.test(value?.id||'')||!Object.hasOwn(inventoryCountStatus,value.status)||!Number.isSafeInteger(value.revision)||value.revision<1||!Array.isArray(value.items)||id&&value.id!==id||revision!==null&&value.revision!==revision||status&&value.status!==status||!/^[a-f0-9]{64}$/.test(value.history_sha256||''))throw fail('Die Inventurbestätigung stimmt nicht mit dem Auftrag überein. Der Auftrag bleibt erhalten.');
  return value;
}
export async function inventoryCountPendingAuthorize(api,operation){
  const body=api.pendingCommandValues(operation?.key,operation?.path),match=/^\/business\/inventory\/counts(?:\/([a-f0-9]{32})\/(count|approve|cancel))?$/.exec(operation?.path||'');
  if(!body||!match)throw fail('Der ursprüngliche Inventurauftrag fehlt.',409);
  const rights=inventoryCountRights(await api.get('/business/capabilities'));
  if(!rights.write||match[2]==='approve'&&!rights.approve)throw fail('Die aktuelle Inventur- oder Finanzfreigabe fehlt.',403);
  if(match[1])inventoryCountRecord(await api.get('/business/inventory/counts/'+match[1]),{id:match[1]});
  else {if(!ID.test(body.location_id||''))throw fail('Ursprünglicher Lagerort fehlt.',409);const source=await api.get('/business/inventory/count-sources?location_id='+body.location_id);if(source.location?.id!==body.location_id)throw fail('Der Lagerort stimmt nicht mit dem Auftrag überein.');}
}
export function inventoryCountsUi(h){
  const {el,button,field,form,dialog,panel,rows,row,notice,table,api,biz,query,mutation,action,refresh,formatDate,formatMoney}=h;
  const stateOf=()=>inventoryCountRights(h.caps());
  function check(write=false,approve=false){const rights=stateOf();if(!rights.read||write&&!rights.write||approve&&!rights.approve)throw fail('Die aktuelle Inventurberechtigung fehlt.',403);}
  function show(title,body,description=''){check();body.setAttribute('data-inventory-count','true');dialog(title,body,description);}
  async function fresh(){const result=await api.get(biz('/capabilities'));check();if(!inventoryCountRights(result).read)throw fail('Inventur nicht mehr freigegeben.',403);return result;}
  async function commit(key,path,body,expected){
    check(true,path.endsWith('/approve'));
    const stamp=h.stamp(),rights=inventoryCountRights(await fresh());
    if(!rights.write||path.endsWith('/approve')&&!rights.approve)throw fail('Die aktuelle Freigabe fehlt.',403);
    if(stamp!==h.stamp())return undefined;
    const original=api.pendingCommandValues(key,biz(path));
    return mutation(key,path,original||body,{validate:value=>inventoryCountRecord(value,expected)});
  }
  async function list(){check();const stamp=h.stamp(),result=await api.get(biz('/inventory/counts'));check();if(stamp!==h.stamp())return;
    show('Inventur',el('div',{class:'stack'},notice('Physisch gezählte Mengen werden zuerst dokumentiert. Erst eine ausdrückliche Finanzfreigabe bucht Differenzen; Projektkosten bleiben unverändert.'),stateOf().write?button('Neue Inventur',()=>action(()=>chooseLocation()),'primary'):null,
      rows(result.items||[],item=>row(item.title,`${item.location_name} · ${inventoryCountStatus[item.status]} · ${formatDate(item.counted_on)}`,[button('Inventur öffnen',()=>action(()=>detail(item.id)),'small')]),'Noch keine Inventur erfasst.')));
  }
  async function chooseLocation(){check(true);const stamp=h.stamp(),locations=await api.get(biz('/inventory/locations'));check(true);if(stamp!==h.stamp())return;
    show('Lagerort auswählen',form('',[field('location_id','Lagerort','select','',{options:[['','Bitte wählen'],...(locations.items||locations).filter(item=>item.active).map(item=>[item.id,item.name])],required:true})],async values=>{await openForm(values.location_id);return undefined;},{submit:'Artikel auswählen',key:'inventory-count-location'}));
  }
  async function openForm(locationId,correction=null){check(true);const stamp=h.stamp(),source=await api.get(query(biz('/inventory/count-sources'),{location_id:locationId}));check(true);if(stamp!==h.stamp())return;
    const choices=(source.items||[]).map(item=>[item.article.id,`${item.article.code} · ${item.article.name} (${item.article.unit})`]);
    if(!choices.length){show('Keine physischen Artikel',notice('Zuerst Material- oder Geräteartikel anlegen.'));return;}
    const fields=[field('title','Inventurtitel','text',correction?'Nachzählung · '+correction.title:'',{required:true}),field('counted_on','Tatsächlicher Zähltag','date','',{required:true}),field('reason','Anlass / Korrekturgrund','textarea','',{required:true})];
    if(!correction)fields.push(field('article_ids','Zu zählende Artikel','multi',[],{options:choices,required:true,help:'Der Auftrag umfasst genau diese Auswahl, höchstens 200 Artikel.'}));
    show(correction?'Korrektur neu zählen':'Inventur beginnen',form('',fields,(values,key)=>commit(key,'/inventory/counts',{...values,location_id:locationId,article_ids:correction?correction.items.map(i=>i.article.id):values.article_ids,correction_of:correction?.id||null},{revision:1,status:'open'}),
      {key:'inventory-count-open-'+locationId+(correction?'-'+correction.id:''),submit:'Zählumfang festhalten',after:async value=>{await refresh();await detail(value.id);}}),'Der aktuelle Bestand wird festgehalten. Spätere Bewegungen, Reservierungen oder Artikeländerungen erfordern einen neuen Zählauftrag.');
  }
  async function detail(id,revision=null){check();const stamp=h.stamp(),record=inventoryCountRecord(await api.get(query(biz('/inventory/counts/'+id),{revision})),{id});check();if(stamp!==h.stamp())return;
    const writable=stateOf().write&&revision===null&&['open','counted'].includes(record.status),controls=[];
    if(writable&&record.basis_current)controls.push(button(record.status==='counted'?'Zählung korrigieren':'Mengen zählen',()=>countForm(record),'primary'));
    if(writable&&record.status==='counted'&&record.basis_current&&stateOf().approve)controls.push(button('Differenzen prüfen und freigeben',()=>approveForm(record),'primary'));
    if(writable)controls.push(button('Zählauftrag abbrechen',()=>cancelForm(record),'small'));
    if(record.status==='approved'&&stateOf().write&&revision===null)controls.push(button('Neue Korrektur zählen',()=>action(()=>openForm(record.location_id,record)),'small'));
    controls.push(button('Fassungen anzeigen',()=>action(()=>history(id)),'small'));
    show(record.title,el('div',{class:'stack'},el('p',{},`${record.location_name} · ${inventoryCountStatus[record.status]} · Fassung ${record.revision} · ${formatDate(record.counted_on)}`),el('p',{},record.reason),record.basis_current===false?notice('Der Lagerstand wurde seit Zählbeginn geändert. Diesen Auftrag abbrechen und neu zählen.','warn'):null,
      table(['Artikel','Sollbestand','Reserviert','Gezählt','Differenz',...(record.financial_values_visible?['Wertdifferenz netto']:[])],record.items.map(item=>[`${item.article.name} · ${item.article.unit}`,item.on_hand,item.reserved,item.counted_quantity??'Noch nicht gezählt',item.difference??'—',...(record.financial_values_visible?[item.adjustment_value_net===undefined?'Nach Freigabe':formatMoney(item.adjustment_value_net)]:[])])),el('div',{class:'actions'},...controls)),revision===null?'Inventurdifferenzen verändern Lagerbestand und Lagerwert. Sie werden keinem Projekt als Verbrauch zugeordnet.':'Historische Fassung. Spätere Zählungen bleiben eigenständig erhalten.');
  }
  function countForm(record){check(true);const fields=record.items.flatMap(item=>[field('quantity_'+item.article.id,'Gezählte Menge · '+item.article.name,'text',item.counted_quantity??'',{required:true,help:'Einheit: '+item.article.unit+' · ausdrücklich 0 bei keinem Bestand'}),field('reason_'+item.article.id,'Differenzgrund · '+item.article.name,'text',item.reason||'')]);
    show('Mengen zählen',form('',fields,(values,key)=>commit(key,`/inventory/counts/${record.id}/count`,inventoryCountValues(record,values),{id:record.id,revision:record.revision+1,status:'counted'}),{key:'inventory-count-count-'+record.id,submit:'Zählung dokumentieren',after:()=>detail(record.id)}));
  }
  function cancelForm(record){check(true);show('Zählauftrag abbrechen',form('',[field('reason','Abbruchgrund','textarea','',{required:true})],(values,key)=>commit(key,`/inventory/counts/${record.id}/cancel`,{revision:record.revision,...values},{id:record.id,revision:record.revision+1,status:'cancelled'}),{key:'inventory-count-cancel-'+record.id,submit:'Abbruch dokumentieren',after:()=>detail(record.id)}));}
  function approveForm(record){check(true,true);const needed=record.items.filter(item=>inventoryQuantity(item.on_hand)==='0.0000'&&inventoryQuantity(item.counted_quantity)!=='0.0000');
    const fields=needed.map(item=>field(item.article.id,'Einstandspreis netto · '+item.article.name,'text','',{required:true,help:'Kein bisheriger Bestand; auch einen tatsächlichen Nullpreis ausdrücklich eintragen.'}));
    show('Inventurdifferenzen prüfen',form('',fields,async values=>{check(true,true);const stamp=h.stamp(),prices=Object.fromEntries(needed.map(item=>[item.article.id,inventoryQuantity(values[item.article.id])])),preview=await api.post(biz(`/inventory/counts/${record.id}/preview`),{revision:record.revision,zero_stock_unit_costs:prices});check(true,true);if(stamp!==h.stamp())return undefined;
      if(preview.id!==record.id||preview.revision!==record.revision||preview.project_cost_effect!=='none')throw fail('Die Vorschau gehört nicht zu dieser Inventurfassung.');
      show('Bestandsdifferenzen freigeben',form('',[field('confirmed','Ich bestätige die gezählten Mengen, Differenzgründe und Lagerbewertung.','checkbox',false,{required:true})],(input,key)=>commit(key,`/inventory/counts/${record.id}/approve`,{revision:record.revision,confirmed:input.confirmed,zero_stock_unit_costs:prices},{id:record.id,revision:record.revision+1,status:'approved'}),
        {key:'inventory-count-approve-'+record.id,submit:'Differenzen verbindlich buchen',extra:table(['Artikel','Mengenänderung','Wertänderung netto'],preview.items.map(item=>[record.items.find(i=>i.article.id===item.article_id)?.article.name||'Artikel',item.quantity_delta,formatMoney(item.value_delta_net)])),after:async()=>{await refresh();await detail(record.id);}}),'Die Buchung ist unveränderlich. Eine spätere Berichtigung erfolgt durch einen neuen Zählauftrag.');return undefined;
    },{key:'inventory-count-preview-'+record.id,submit:'Bewertung berechnen'}));
  }
  async function history(id){check();const stamp=h.stamp(),result=await api.get(biz('/inventory/counts/'+id+'/history'));check();if(stamp!==h.stamp())return;show('Inventurhistorie',rows(result.items||[],record=>row(`Fassung ${record.revision} · ${inventoryCountStatus[record.status]}`,formatDate(record.updated_at,true),[button('Fassung öffnen',()=>action(()=>detail(id,record.revision)),'small')])));}
  return {list,detail};
}
