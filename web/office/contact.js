/* Public contact intake only: no Office bearer, cookies, provider key or browser storage. */
export const PRIVACY_NOTICE_VERSION='2026-10-25-v1';
export class ContactError extends Error {
  constructor(message,status=0){super(message);this.name='ContactError';this.status=status;}
}
function bounded(value,name,maximum,required=false,multiline=false){
  if(typeof value!=='string'||value.length>maximum||[...value].some(character=>character.charCodeAt(0)<32&&(!multiline||!['\n','\r','\t'].includes(character))))throw new ContactError('Bitte '+name+' prüfen.',400);
  const result=value.trim();if(required&&!result)throw new ContactError('Bitte '+name+' ausfüllen.',400);return result;
}
export function contactPayload(values,request_id){
  if(!/^[a-f0-9]{32}$/.test(request_id))throw new ContactError('Anfrage konnte nicht vorbereitet werden.');
  if(values.privacy!==true)throw new ContactError('Bitte den Hinweis zur Verarbeitung Ihrer Anfrage bestätigen.',400);
  const email=bounded(values.sender_email,'Ihre E-Mail',254,true);
  if(!/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(email))throw new ContactError('Bitte eine gültige E-Mail-Adresse eingeben.',400);
  const website=values.website??'';bounded(website,'das Formular',200);
  const payload={request_id,subject:bounded(values.subject,'den Betreff',300,true),message:bounded(values.message,'Ihre Nachricht',6000,true,true),
    sender_name:bounded(values.sender_name,'Ihren Namen',200,true),sender_email:email,sender_phone:bounded(values.sender_phone??'','Ihre Telefonnummer',100),
    website,privacy_notice_version:PRIVACY_NOTICE_VERSION};
  if(new TextEncoder().encode(JSON.stringify(payload)).byteLength>32000)throw new ContactError('Bitte die Anfrage kürzen.',400);
  return payload;
}
export function receiptMessage(receipt){
  if(!receipt||receipt.status!=='received'||typeof receipt.id!=='string'||!/^[a-f0-9]{32}$/.test(receipt.id))throw new ContactError('Der Eingang wurde noch nicht sicher bestätigt. Bitte dieselbe Anfrage erneut senden.');
  return 'Vielen Dank. Ihre Anfrage ist eingegangen. Die Bearbeitung steht noch aus. '+(receipt.reply_status==='pending'
    ?'Eine automatische Eingangsantwort ist vorbereitet; ihr Versand ist noch nicht bestätigt.'
    :'Damit ist kein Versand und keine Zustellung einer E-Mail bestätigt.');
}
export class ContactClient {
  #pending=null;
  constructor(fetcher=globalThis.fetch){this.fetcher=fetcher.bind(globalThis);}
  get pending(){return this.#pending!==null;}
  async submit(values){
    const id=this.#pending?.payload.request_id||crypto.randomUUID().replaceAll('-',''),payload=contactPayload(values,id),fingerprint=JSON.stringify(payload);
    if(this.#pending&&this.#pending.fingerprint!==fingerprint)throw new ContactError('Die vorige Antwort ist unklar. Bitte zuerst die unveränderte Anfrage erneut senden.');
    this.#pending={payload,fingerprint};
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),20000);
    try{
      const response=await this.fetcher('/api/v1/intake/contact',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(payload),credentials:'omit',redirect:'error',cache:'no-store',referrerPolicy:'no-referrer',signal:controller.signal});
      const reader=response.body?.getReader();let encoded;
      if(reader){let size=0;const chunks=[];for(;;){const{done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>65536){await reader.cancel();throw new ContactError('Serverantwort nicht lesbar. Bitte dieselbe Anfrage erneut senden.');}chunks.push(value);}encoded=new Uint8Array(size);let offset=0;for(const chunk of chunks){encoded.set(chunk,offset);offset+=chunk.byteLength;}}
      else{encoded=new Uint8Array(await response.arrayBuffer());if(encoded.byteLength>65536)throw new ContactError('Serverantwort nicht lesbar. Bitte dieselbe Anfrage erneut senden.');}
      let receipt;try{receipt=JSON.parse(new TextDecoder().decode(encoded));}catch{throw new ContactError('Der Eingang ist noch nicht bestätigt. Bitte dieselbe Anfrage erneut senden.');}
      if(response.status!==201){
        if(response.status>=400&&response.status<500&&response.status!==429)this.#pending=null;
        const message=response.status===429?'Bitte verwenden Sie das Kontaktformular später erneut.':response.status===403||response.status===409?'Das Kontaktformular ist derzeit nicht zur Annahme freigegeben. Bitte später erneut versuchen.':response.status===400?'Bitte Ihre Eingaben prüfen. Die Anfrage wurde nicht übernommen.':'Der Eingang ist noch nicht sicher bestätigt. Bitte dieselbe Anfrage erneut senden.';
        throw new ContactError(message,response.status);
      }
      const message=receiptMessage(receipt);this.#pending=null;return{receipt,message};
    }catch(error){if(error instanceof ContactError)throw error;throw new ContactError('Keine sichere Antwort erhalten. Bitte Verbindung prüfen und dieselbe Anfrage erneut senden.');}
    finally{clearTimeout(timeout);}
  }
}
if(typeof document!=='undefined'){
  const form=document.getElementById('contact-form'),result=document.getElementById('contact-result'),submit=document.getElementById('contact-submit'),client=new ContactClient();
  if(form&&submit)submit.disabled=false;
  if(form)form.addEventListener('submit',async event=>{
    event.preventDefault();if(submit.disabled)return;result.replaceChildren();submit.disabled=true;
    const values=Object.fromEntries(new FormData(form));values.privacy=document.getElementById('privacy').checked;
    try{
      const response=await client.submit(values),message=document.createElement('div');message.className='notice success';message.setAttribute('role','status');message.textContent=response.message;
      form.reset();form.hidden=true;result.replaceChildren(message);message.tabIndex=-1;message.focus();
      const again=document.createElement('button');again.type='button';again.className='button';again.textContent='Weitere Anfrage';again.addEventListener('click',()=>{form.hidden=false;result.replaceChildren();form.querySelector('input').focus();});result.append(again);
    }catch(error){const message=document.createElement('div');message.className='notice error';message.setAttribute('role','alert');message.textContent=error.message;result.replaceChildren(message);submit.textContent=client.pending?'Unverändert erneut übermitteln':'Anfrage übermitteln';}
    finally{submit.disabled=false;}
  });
  addEventListener('beforeunload',event=>{if(client.pending){event.preventDefault();event.returnValue='';}});
}
