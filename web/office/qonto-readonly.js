/* Selected Qonto changes are a read view, never a statement or a posting. */
const HASH=/^[a-f0-9]{64}$/,ID=/^[a-f0-9]{32}$/,UUID=/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
export const qontoStatusLabel=value=>({pending:'Vorgemerkt',completed:'Abgeschlossen',declined:'Abgelehnt',reversed:'Storniert'})[value];
const fail=()=>new Error('Der Qonto-Lesestand passt nicht eindeutig zum ausgewählten Konto und Zeitraum.');
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
export function qontoWindow(values){
 const first=new Date(values.from+'T00:00:00.000Z'),last=new Date(values.to+'T00:00:00.000Z');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(values.from)||!/^\d{4}-\d{2}-\d{2}$/.test(values.to)||!Number.isFinite(+first)||!Number.isFinite(+last)||first.toISOString().slice(0,10)!==values.from||last.toISOString().slice(0,10)!==values.to||!(last>first)||last-first>31*86400000)throw new Error('Einen UTC-Zeitraum von höchstens 31 Tagen wählen. Das Enddatum ist ausgeschlossen.');
 return {updated_from:first.toISOString(),updated_to:last.toISOString()};
}
export function qontoMoney(cents){if(!Number.isSafeInteger(cents)||Math.abs(cents)>999999999999999)throw fail();return (cents<0?'-':'')+Math.floor(Math.abs(cents)/100)+'.'+String(Math.abs(cents)%100).padStart(2,'0');}
export async function qontoReadView(value,{accountId,bindingHash,iban,body}){
 if(!value||value.schema_version!==1||value.provider!=='qonto'||value.read_only!==true||value.complete_statement!==false||value.atomic_snapshot!==false||value.financial_changes!==false||value.local_account_id!==accountId||!ID.test(accountId)||value.bank_binding_hash!==bindingHash||!HASH.test(bindingHash)||!HASH.test(value.content_hash)||!UUID.test(value.organization?.id)||!Array.isArray(value.items)||value.items.length>1000||!Array.isArray(value.source_pages)||value.source_pages.length>12||value.window?.updated_from!==body.updated_from||value.window.updated_to!==body.updated_to||value.window.upper_exclusive!==true||value.account_before?.iban!==value.account_after?.iban)throw fail();
 if(value.account_before?.iban!==iban||value.account_after?.iban!==iban)throw fail();
 const seen=new Set(),first=Date.parse(body.updated_from),last=Date.parse(body.updated_to);
 for(const row of value.items){const updated=Date.parse(row.updated_at);if(!UUID.test(row.id)||seen.has(row.id)||!UUID.test(row.bank_account_id)||!qontoStatusLabel(row.status)||!['credit','debit'].includes(row.side)||row.currency!=='EUR'||!Number.isSafeInteger(row.amount_cents)||row.amount_cents<0||row.amount_cents>999999999999999||row.signed_amount_cents!==(row.side==='debit'?-row.amount_cents:row.amount_cents)||!(updated>=first&&updated<last)||!['label','counterparty','reference'].every(k=>typeof row[k]==='string'||row[k]===null))throw fail();seen.add(row.id);}
 const payload=Object.fromEntries(Object.entries(value).filter(([key])=>!['content_hash','read_at','local_account_id','bank_binding_hash'].includes(key))),bytes=new TextEncoder().encode(JSON.stringify(ordered(payload))),hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
 if(hash!==value.content_hash)throw fail();return value;
}
export function qontoReadUi(h){
 const {api,el,button,field,form,notice,table,show,fresh}=h;
 async function open(){
  await fresh();const status=await api.get('/bank-feeds/qonto/status');await fresh();
  if(status?.schema_version!==1||status.provider!=='qonto'||status.read_only!==true||typeof status.configured!=='boolean')throw fail();
  if(!status.configured){show('Qonto lesen',notice('Qonto ist noch nicht verbunden. Ein Administrator muss den Lesezugang auf dem Server einrichten. Der CSV-Bankabgleich steht weiterhin zur Verfügung.'));return;}
  const binding=(await fresh({account:status.account_id})).page.items.find(v=>v.account_id===status.account_id);
  if(!binding?.payload.active)throw fail();
  show('Qonto lesen',form('',[
   field('from','Änderungen ab (UTC, einschließlich)','date','',{required:true}),
   field('to','Änderungen bis (UTC, ausschließlich)','date','',{required:true})
  ],async values=>{
   const body=qontoWindow(values);await fresh({account:status.account_id});
   const result=await api.post('/bank-feeds/qonto/read',body),current=await fresh({account:status.account_id}),bound=current.page.items.find(v=>v.account_id===status.account_id);
   const value=await qontoReadView(result,{accountId:status.account_id,bindingHash:bound?.content_hash,iban:bound?.payload.iban,body});
   await fresh({account:status.account_id});
   show('Qonto · gelesene Umsatzänderungen',el('div',{class:'stack'},
    notice('Dieser Abruf zeigt Umsatzänderungen. Er ist kein vollständiger Kontoauszug und erzeugt keine Zahlung oder Buchung.'),
    el('p',{},`${value.organization.name} · ${value.account_after.iban}`),
    el('p',{},`Aktuell gelesener Saldo: ${h.formatMoney(qontoMoney(value.account_after.balance_cents))}. Abruf ${h.formatDate(value.read_at,true)}.`),
    notice('Der Zeitraum bezieht sich auf Änderungen beim Anbieter. Bereits früher gebuchte Umsätze können darin enthalten sein. Vorgemerkte, abgelehnte und stornierte Umsätze sind gesondert gekennzeichnet.'),
    value.items.length?table(['Letzte Änderung','Status','Gegenpartei / Text','Betrag'],value.items.map(row=>[h.formatDate(row.updated_at,true),qontoStatusLabel(row.status),row.counterparty||row.label,h.formatMoney(qontoMoney(row.signed_amount_cents))])):notice('Für diesen Änderungszeitraum wurden keine Umsätze geliefert.'),
    button('Erneut lesen',()=>h.run(open))));return undefined;
  },{key:'qonto-read-window',submit:'Umsatzänderungen lesen',description:`${binding.payload.label} · ${binding.payload.iban}. Höchstens31 Tage und1000 Umsatzänderungen; keine Buchung.`}));
 }
 return {open};
}
