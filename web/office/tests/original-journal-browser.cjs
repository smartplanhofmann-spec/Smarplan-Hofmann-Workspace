/* Exercise real IndexedDB transactions and encrypted failure retention. */
async function originalJournalBrowser({page,projectId,token}){
 const result=await page.evaluate(async({projectId,token})=>{
  const {BrowserOriginalJournal,OriginalIndexedStore,browserOriginalJournal}=await import('/office/original-journal.js');
  const get=async path=>{
   const response=await fetch('/api/v1'+path,{headers:{Authorization:token},cache:'no-store'});
   if(!response.ok)throw new Error('Synthetic original access '+response.status);
   return response.json();
  };
  const actor=await get('/me'),caps=await get('/business/capabilities?project_id='+projectId);
  const options={caps,actorId:actor.id,kind:'material_return',subjectId:projectId};
  const first=await browserOriginalJournal({get},options),second=await browserOriginalJournal({get},options);
  if(await first.pending()!==null)throw new Error('A real synthetic return must be resolved before storage acceptance');
  const a={request_id:'1'.repeat(32),note:'Synthetic private original A'},b={request_id:'2'.repeat(32),note:'Synthetic private original B'};
  const races=await Promise.allSettled([first.prepare(a),second.prepare(b)]);
  if(races.filter(r=>r.status==='fulfilled').length!==1)throw new Error('Real IndexedDB must commit exactly one competing original');
  const winner=await first.pending();
  if(![a.request_id,b.request_id].includes(winner.request_id))throw new Error('Competing original was replaced');
  const store=new OriginalIndexedStore(),saved=await store.get(first.locator);
  if(JSON.stringify(saved).includes(winner.note)||Object.keys(saved).length!==6)throw new Error('Only the ciphertext envelope may persist');
  async function denied(action){try{await action();}catch{return;}throw new Error('Retained original must fail closed');}
  await denied(()=>browserOriginalJournal({get},{...options,caps:{...caps,features:caps.features.filter(f=>f!=='client_original_key')}}));
  const replacement=new BrowserOriginalJournal({locator:first.locator,scope:{...caps.project_creation_scope,instance_id:'f'.repeat(32)},kind:'material_return',subjectId:projectId,access:()=>{throw new Error('Wrong instance must be rejected before key access');}});
  await denied(()=>replacement.pending());
  const damaged={...saved,ciphertext:(saved.ciphertext[0]==='A'?'B':'A')+saved.ciphertext.slice(1)};
  await store.compareAndSwap(first.locator,saved.revision,damaged);
  await denied(()=>second.pending());
  if(JSON.stringify(await store.get(first.locator))!==JSON.stringify(damaged))throw new Error('Corrupt ciphertext was overwritten');
  await store.compareAndSwap(first.locator,damaged.revision,saved);
  if(JSON.stringify(await second.pending())!==JSON.stringify(winner))throw new Error('Original recovery changed confirmed values');
  await second.clear(winner);
  if(await first.pending()!==null)throw new Error('Verified clear must remove the exact resolved local original');
  return {competing_originals:2,committed:1,ciphertext_only:true,downgrade_blocked:true,replacement_blocked:true,corruption_preserved:true};
 },{projectId,token});
 console.log('actual IndexedDB original acceptance: '+JSON.stringify(result));
 return result;
}
module.exports={originalJournalBrowser};
