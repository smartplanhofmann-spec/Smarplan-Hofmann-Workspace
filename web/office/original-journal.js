/* Ciphertext-only local originals. Keys require fresh online resource access. */
const ID=/^[a-f0-9]{32}$/;
const id=value=>typeof value==='string'&&value.length===32&&ID.test(value);
const fail=(message,status=0)=>Object.assign(new Error(message),{status});
const copy=value=>structuredClone(value);
const exact=(value,keys)=>value&&Object.getPrototypeOf(value)===Object.prototype&&
  Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
const text=new TextEncoder();
export function originalCanonical(value){
  if(value===null||typeof value==='boolean')return JSON.stringify(value);
  if(typeof value==='string'){
    if([...value].some(c=>{const n=c.codePointAt(0);return n>=0xd800&&n<=0xdfff;}))throw fail('Der Originalauftrag enthält ungültigen Text.');
    return JSON.stringify(value);
  }
  if(Number.isSafeInteger(value))return String(value);
  if(Array.isArray(value))return '['+value.map(originalCanonical).join(',')+']';
  if(value&&Object.getPrototypeOf(value)===Object.prototype)return '{'+Object.keys(value).sort().map(k=>originalCanonical(k)+':'+originalCanonical(value[k])).join(',')+'}';
  throw fail('Der Originalauftrag enthält keinen unveränderten JSON-Wert.');
}
function encode(bytes){let value='';for(let n=0;n<bytes.length;n+=32768)value+=String.fromCharCode(...bytes.subarray(n,n+32768));return btoa(value);}
function decode(value,limit){
  if(typeof value!=='string'||value.length>limit||!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value))throw fail('Der geschützte Originalauftrag ist beschädigt.');
  const bytes=Uint8Array.from(atob(value),c=>c.charCodeAt(0));if(encode(bytes)!==value)throw fail('Der geschützte Originalauftrag ist beschädigt.');return bytes;
}
function command(value){
  if(!value||Object.getPrototypeOf(value)!==Object.prototype)throw fail('Der vollständige Originalauftrag fehlt.');
  if(text.encode(originalCanonical(value)).length>1048576)throw fail('Der Originalauftrag ist für den geschützten Speicher zu groß.');
  return copy(value);
}
function binding(value){
  if(!exact(value,['schema_version','instance_id','account_id','host','api_version','kind','subject_id'])||value.schema_version!==1||
    ![value.instance_id,value.account_id,value.subject_id].every(id)||value.api_version!=='v1'||
    typeof value.host!=='string'||value.host.length>253||value.host.trim()!==value.host||!/^[a-z0-9]+(?:[.-][a-z0-9]+)+$/.test(value.host)||
    !['material_return','private_car_mileage'].includes(value.kind))throw fail('Die Firmenbindung des Browserauftrags fehlt.');
  return value;
}
export class OriginalIndexedStore{
  constructor(indexedDB=globalThis.indexedDB){this.indexedDB=indexedDB;}
  async open(){
    if(!this.indexedDB)throw fail('Der geschützte Browserspeicher ist nicht verfügbar. Es wurde nichts gesendet.');
    return new Promise((resolve,reject)=>{
      const request=this.indexedDB.open('smartplan-originals-v1',1);let blocked=false;
      request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('originals'))request.result.createObjectStore('originals',{keyPath:'locator'});};
      request.onsuccess=()=>{if(blocked)request.result.close();else resolve(request.result);};
      request.onerror=()=>reject(fail('Der geschützte Browserspeicher konnte nicht geöffnet werden.'));
      request.onblocked=()=>{blocked=true;reject(fail('Der Browserspeicher ist in einem anderen Fenster belegt. Bitte erneut öffnen.'));};
    });
  }
  async get(locator){
    const db=await this.open();
    try{return await new Promise((resolve,reject)=>{
      const tx=db.transaction('originals','readonly'),request=tx.objectStore('originals').get(locator);
      tx.oncomplete=()=>resolve(request.result??null);tx.onabort=()=>reject(fail('Der ursprüngliche Browserspeicher konnte nicht gelesen werden.'));
      tx.onerror=()=>{};
    });}finally{db.close();}
  }
  async compareAndSwap(locator,expected,next){
    const db=await this.open();
    try{return await new Promise((resolve,reject)=>{
      const tx=db.transaction('originals','readwrite'),store=tx.objectStore('originals'),request=store.get(locator);let changed=false;
      request.onsuccess=()=>{
        const previous=request.result;
        if(expected===null?previous!==undefined:previous?.revision!==expected){tx.abort();return;}
        if(next===null)store.delete(locator);else store.put(next);changed=true;
      };
      tx.oncomplete=()=>resolve(changed);tx.onabort=()=>reject(fail('Der Originalauftrag wurde in einem anderen Fenster geändert oder konnte nicht gespeichert werden. Es wurde nichts gesendet.'));
      tx.onerror=()=>{};
    });}finally{db.close();}
  }
}

export class BrowserOriginalJournal{
  constructor({locator,scope,kind,subjectId,access,guard=()=>{},store=new OriginalIndexedStore()}){
    if(typeof locator!=='string'||!scope||scope.schema_version!==1||![scope.instance_id,scope.account_id,subjectId].every(id)||
      !['material_return','private_car_mileage'].includes(kind)||typeof access!=='function')throw fail('Der ursprüngliche Browserkontext fehlt.');
    this.locator=locator;this.scope=copy(scope);this.kind=kind;this.subjectId=subjectId;this.access=access;this.guard=guard;this.store=store;
  }
  checkBinding(value){
    binding(value);
    if(value.instance_id!==this.scope.instance_id||value.account_id!==this.scope.account_id||value.kind!==this.kind||value.subject_id!==this.subjectId)
      throw fail('Ein früherer Auftrag benötigt die ursprüngliche Firmenanmeldung. Es wurde nichts erneut gesendet.');
  }
  async key(){
    this.guard();const reply=await this.access();this.guard();
    if(!exact(reply,['schema_version','binding','wrapping_key'])||reply.schema_version!==1)throw fail('Die geschützte Schlüsselantwort ist unvollständig.');
    this.checkBinding(reply.binding);
    const raw=decode(reply.wrapping_key,44);if(raw.length!==32)throw fail('Die geschützte Schlüsselantwort ist ungültig.');
    const key=await crypto.subtle.importKey('raw',raw,'AES-GCM',false,['encrypt','decrypt']);raw.fill(0);reply.wrapping_key='';this.guard();
    return {key,binding:copy(reply.binding)};
  }
  aad(envelope){return text.encode(originalCanonical({schema_version:1,locator:this.locator,binding:envelope.binding,revision:envelope.revision}));}
  async read(){
    this.guard();const envelope=await this.store.get(this.locator);this.guard();if(envelope===null)return null;
    if(!exact(envelope,['schema_version','locator','revision','binding','nonce','ciphertext'])||envelope.schema_version!==1||
      envelope.locator!==this.locator||!id(envelope.revision))throw fail('Der geschützte Originalauftrag ist nicht lesbar. Den Browserspeicher erhalten.');
    this.checkBinding(envelope.binding);
    const {key,binding:current}=await this.key();
    if(originalCanonical(current)!==originalCanonical(envelope.binding))throw fail('Der ursprüngliche Server-/Firmenbezug wurde geändert.');
    const iv=decode(envelope.nonce,16),bytes=decode(envelope.ciphertext,1400000);
    if(iv.length!==12||bytes.length<17)throw fail('Der geschützte Originalauftrag ist beschädigt.');
    let value;
    try{
      const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv,additionalData:this.aad(envelope),tagLength:128},key,bytes);this.guard();
      value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(plain));
    }catch(error){this.guard();throw fail('Der ursprüngliche Auftrag konnte nicht entschlüsselt werden. Es wurde nichts gesendet. Den Browserspeicher erhalten.');}
    this.guard();return {command:command(value),revision:envelope.revision};
  }
  async pending(){return (await this.read())?.command??null;}
  async prepare(value){
    const original=command(value),old=await this.read();
    if(old){if(originalCanonical(old.command)!==originalCanonical(original))throw fail('Zuerst den ursprünglichen Browserauftrag klären.',409);return;}
    const {key,binding:current}=await this.key(),iv=crypto.getRandomValues(new Uint8Array(12));
    const envelope={schema_version:1,locator:this.locator,revision:crypto.randomUUID().replaceAll('-',''),binding:current,nonce:encode(iv),ciphertext:''};
    const encrypted=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:this.aad(envelope),tagLength:128},key,text.encode(JSON.stringify(original)));
    this.guard();envelope.ciphertext=encode(new Uint8Array(encrypted));
    await this.store.compareAndSwap(this.locator,null,envelope);this.guard();
  }
  async requireOriginal(value){
    const original=command(value),old=await this.read();
    if(!old||originalCanonical(old.command)!==originalCanonical(original))throw fail('Der gespeicherte Originalauftrag wurde geändert. Bitte erneut öffnen.');
  }
  async clear(value){
    const original=command(value),old=await this.read();if(old===null)return;
    if(originalCanonical(old.command)!==originalCanonical(original))throw fail('Die Bestätigung gehört nicht zum gespeicherten Originalauftrag.');
    this.guard();await this.store.compareAndSwap(this.locator,old.revision,null);this.guard();
  }
}

export async function browserOriginalJournal(api,{caps,actorId,kind,subjectId,guard=()=>{},origin=globalThis.location?.origin??'',store=new OriginalIndexedStore()}={}){
  guard();
  const scope=caps.project_creation_scope;
  actorId??=scope?.account_id;
  if(!id(actorId)||!id(subjectId)||!['material_return','private_car_mileage'].includes(kind)||!origin)throw fail('Die ursprüngliche Browseranmeldung fehlt.');
  const locator=JSON.stringify([origin,'/api/v1',actorId,kind,subjectId]);
  if(!caps?.features?.includes('client_original_key')){
    const previous=await store.get(locator);guard();
    if(previous!==null)throw fail('Ein ursprünglicher Browserauftrag ist noch geschützt gespeichert. Diese Serverfreigabe erlaubt seine Klärung nicht. Es wurde nichts gesendet.');
    return null;
  }
  if(!exact(scope,['schema_version','instance_id','account_id'])||scope.schema_version!==1||
    ![scope.instance_id,scope.account_id,subjectId].every(id)||scope.account_id!==actorId)throw fail('Die bestätigte Firmenanmeldung für den Browserauftrag fehlt.');
  return new BrowserOriginalJournal({locator,scope,kind,subjectId,store,guard,
    access:()=>api.get('/business/client-original-key?kind='+kind+'&subject_id='+subjectId)});
}
