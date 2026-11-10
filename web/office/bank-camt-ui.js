import {bankCamtInspection} from './bank-camt-contract.js';

/* Explicit XML selection, original-bound suggestions and human confirmation. */
export function bankCamtUi(h){
 const {api,biz,el,button,field,form,notice,table,show,fresh,run}=h;
 const requireFormat=state=>{if(!state.caps.features?.includes('bank_camt_v1'))throw new Error('Der aktuelle Server gibt den XML-Bankimport nicht frei.');};
 return {async open(binding){
  const initial=await fresh({write:true,account:binding.account_id});requireFormat(initial);
  const input=el('input',{type:'file',accept:'.xml,application/xml,text/xml','aria-label':'Originalen XML-Kontoauszug auswählen'});
  const key='bank-import-'+crypto.randomUUID().replaceAll('-','');
  const inspect=async()=>{
   const file=input.files?.[0],stamp=h.stamp();
   if(!file||!/\.xml$/i.test(file.name)||file.size<1||file.size>5*1024*1024)throw new Error('Eine originale XML-Datei mit1 Byte bis5 MiB auswählen.');
   const bytes=new Uint8Array(await file.arrayBuffer());
   const current=await fresh({write:true,account:binding.account_id});requireFormat(current);
   if(stamp!==h.stamp()||!input.isConnected||input.files?.[0]!==file||bytes.length!==file.size)throw new Error('Dateiauswahl, Ansicht oder Sitzung wurde geändert.');
   const account=current.page.available_accounts.find(a=>a.id===binding.account_id),bank=current.page.items.find(a=>a.account_id===binding.account_id);
   let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
   const sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
   const request={account_id:binding.account_id,account_revision:account.revision,bank_revision:bank.revision,filename:file.name,content_base64:btoa(binary)};
   const inspection=await bankCamtInspection(await api.post(biz('/bank/camt/inspect'),request),request,sha256);
   const after=await fresh({write:true,account:binding.account_id});requireFormat(after);
   if(stamp!==h.stamp()||!input.isConnected||input.files?.[0]!==file||after.page.available_accounts.find(a=>a.id===binding.account_id)?.revision!==request.account_revision||after.page.items.find(a=>a.account_id===binding.account_id)?.revision!==request.bank_revision)throw new Error('Konto, Ansicht, Sitzung oder Original wurde zwischenzeitlich geändert. Bitte erneut auswählen.');
   const values=inspection.suggested_body;
   show('XML-Kontoauszug prüfen',form('',[
    field('complete_statement_confirmed','Ich habe das XML-Original und seinen vollständigen Auszugszeitraum geprüft.','checkbox',false,{required:true}),
   ],async v=>{
    if(v.complete_statement_confirmed!==true)throw new Error('Vollständigen Originalauszug ausdrücklich bestätigen.');
    await h.importPreview({...values,content_base64:request.content_base64,complete_statement_confirmed:true},sha256,key);
    return undefined;
   },{key:key+'-xml-review',submit:'Auszug unverbindlich prüfen',extra:el('div',{class:'stack'},
    notice('Aus dem unveränderten XML gelesen. Ein Import erzeugt keine Zahlung und keine EÜR-Buchung.'),
    table(['Originalangabe','Gelesener Wert'],[['Datei',file.name],['Auszugsreferenz',values.statement_reference],['Auszugsbeginn',h.formatDate(values.period_from)],['Auszugsende',h.formatDate(values.period_to)],['Gebuchter Anfangssaldo',h.formatMoney(values.opening_balance)],['Gebuchter Endsaldo',h.formatMoney(values.closing_balance)],['Gebuchte Kontobewegungen',String(inspection.preview.metadata.rows.length)]]),
    notice('Nur camt.053.001.08 mit eindeutigem EUR-Konto, gebuchten Bewegungen und vollständigen Salden. Andere Versionen und unvollständige Auszüge werden zurückgewiesen.'),
   )}));
  };
  show('Originalen XML-Auszug auswählen',el('div',{class:'stack'},notice('Wählen Sie das unveränderte CAMT-XML Ihrer Bank. Es wird zuerst unverbindlich geprüft.'),input,button('XML-Auszug lesen',()=>run(inspect))));
 }};
}
