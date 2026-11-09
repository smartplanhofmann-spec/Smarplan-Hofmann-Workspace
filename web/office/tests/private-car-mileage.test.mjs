import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {TravelCommand,travelHash} from '../travel-allowances.js';
import {MILEAGE_ROOT,MILEAGE_FEATURE,MILEAGE_READ_FEATURE,MILEAGE_RULE,MILEAGE_CONFIRMATIONS,mileageCatalog,mileageTripDetails,mileageTripInput,mileageTripRecord,mileageTripValidator,mileageRecord,mileageCalculation,mileagePreview,mileageResult,mileageActionValidator} from '../private-car-mileage.js';
const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/private_car_mileage.json',import.meta.url),'utf8')),copy=structuredClone,id=f.employee.id;
const clean=v=>{v=copy(v);delete v.request_id;return v;};
function values(branch){const x=f[branch],d=x.trip_command.details,m=d.mileage;return{id:x.trip_command.id,purpose:d.purpose,project_id:d.project_id,home_site_id:d.home_site_ref.id,first_workplace_id:d.first_workplace_ref?.id||'',source_file_ids:copy(d.source_file_ids),vehicle_registration:m.vehicle_registration,vehicle_file_id:m.vehicle_file_id,declaration_file_id:m.declaration_file_id,...Object.fromEntries(Object.keys(MILEAGE_CONFIRMATIONS).map(k=>[k,m[k]])),review_note:m.review_note,correction_reason:x.trip_command.correction_reason,legs:m.legs.map(v=>({id:v.id,departed_at:v.departed_at,arrived_at:v.arrived_at,from_site_id:v.from_site_ref.id,to_site_id:v.to_site_ref.id,distance_m:v.distance_m,evidence_file_id:v.evidence_file_id}))};}
for(const branch of ['initial','correction'])test('actual '+branch+' private car originals, exact requests and independently frozen cash proofs validate',async()=>{
 const x=f[branch],previous=branch==='correction'?x.rejected:null;const body=mileageTripInput(id,f.sources,values(branch),previous),expected=clean(x.trip_command);expected.details.source_file_ids.sort();assert.deepEqual(body,expected);
 mileageCatalog(f.catalog);mileageTripRecord(x.draft,id);mileageTripRecord(x.trip,id);mileageTripValidator(clean(x.trip_command),previous)(x.draft);mileagePreview(x.preview,id,x.preview_command,x.trip);mileageRecord(x.settlement,'settlements',id);mileageRecord(x.payment,'payments',id);
 for(const [command,receipt]of [[x.trip_command,x.draft_receipt],[x.submit_command,x.submit_receipt],[x.settlement_command,x.settlement_receipt],[x.payment_command,x.payment_receipt],...(branch==='correction'?[[x.reject_command,x.reject_receipt]]:[])]){mileageResult(receipt.result,clean(command),receipt);assert.equal(await travelHash(receipt.result),receipt.result_hash);assert.equal(await travelHash([receipt.operation,receipt.target_kind,receipt.target_id,command]),receipt.request_hash);}
});

test('a corrected 50km trip preserves the original 100km/30EUR payment and evidences 15EUR repayment separately',()=>{
 const first=copy(f.initial),second=f.correction;mileageCalculation(first.settlement.calculation,first.settlement.details.trip_refs,first.trip);mileageCalculation(second.preview,second.preview_command.trip_refs,second.trip);
 assert.equal(first.settlement.calculation.totals.mileage_distance_m,100000);assert.equal(first.settlement.calculation.totals.tax_free_minor,3000);assert.equal(second.preview.totals.mileage_distance_m,50000);assert.equal(second.preview.totals.already_paid_minor,3000);assert.equal(second.preview.totals.overpaid_minor,1500);assert.equal(second.payment.details.kind,'repayment');assert.equal(second.payment.details.amount_minor,1500);assert.equal(first.payment.details.amount_minor,3000);assert.equal(f.trip_history.items[0].id,first.draft.id);assert.equal(f.settlement_history.items.length,2);
});

test('integer meters, private original ownership, contiguous domestic route and no commuting are required',()=>{
 for(const change of [v=>v.legs[0].distance_m=0.5,v=>v.legs[0].distance_m=0,v=>v.legs[0].distance_m=2000001,v=>v.legs[0].from_site_id=v.legs[0].to_site_id,v=>v.legs[0].departed_at='2026-10-26T08:00:00+02:00',v=>v.legs[1].departed_at='2026-10-27T12:00:00+01:00',v=>v.vehicle_file_id='e'.repeat(32),v=>v.source_file_ids=[],v=>v.review_note='\ud800']){const value=values('initial');change(value);assert.throws(()=>mileageTripInput(id,f.sources,value));}
 const ordinary=copy(f.sources);ordinary.files.push({...copy(ordinary.files[0]),id:'c'.repeat(32),purpose:'expense_receipt'});mileageTripInput(id,ordinary,values('initial'));
 const s=copy(f.sources);s.files.find(v=>v.id===f.initial.trip_command.details.mileage.vehicle_file_id).employee_id='e'.repeat(32);assert.throws(()=>mileageTripInput(id,s,values('initial')));
 const foreign=copy(f.initial.trip);foreign.sources.files[0].employee_id='e'.repeat(32);assert.throws(()=>mileageTripRecord(foreign,id));
 const d=copy(f.initial.trip.details);delete d.mileage.no_other_reimbursement;assert.throws(()=>mileageTripDetails(d,id,f.initial.trip.sources));
});

test('all six declarations are explicit booleans and draft false flags never become an automatic approval',()=>{
 for(const key of Object.keys(MILEAGE_CONFIRMATIONS)){const value=values('initial');value[key]=false;const body=mileageTripInput(id,f.sources,value);assert.equal(body.details.mileage[key],false);delete value[key];assert.throws(()=>mileageTripInput(id,f.sources,value));}
});

test('correlated but inconsistent distance, private proof, net or first approval metadata is rejected',()=>{
 for(const change of [v=>v.totals.mileage_allowance_minor++,v=>v.totals.tax_free_minor+=3000,v=>v.totals.remaining_minor++,v=>v.totals.flat_taxable_minor=1,v=>v.mileage_items[0].distance_m++,v=>v.mileage_items[0].evidence_sha256='e'.repeat(64),v=>v.days[0].letter_m=true,v=>v.can_approve=false,v=>v.site_refs=[],v=>v.expense_refs=[{}],v=>v.payroll_month='2026-10']){const value=copy(f.initial.preview);change(value);assert.throws(()=>mileagePreview(value,id,f.initial.preview_command,f.initial.trip,f.catalog));}
 const receipt=copy(f.initial.payment_receipt);receipt.result.details.amount_minor++;assert.throws(()=>mileageResult(receipt.result,clean(f.initial.payment_command),receipt));
});

test('legacy and new private write roots cannot cross; invalid configuration is rejected',async()=>{
 const api={get:async()=>{throw new Error('unexpected read');},post:async()=>{throw new Error('unexpected write');}};const old=new TravelCommand(api,{employeeId:id}),modern=new TravelCommand(api,{employeeId:id,root:MILEAGE_ROOT,writeFeature:MILEAGE_FEATURE});
 await assert.rejects(old.submit(MILEAGE_ROOT+'/trips',clean(f.initial.trip_command),{operation:'trip.save',targetKind:'trip',targetId:f.initial.trip.id}));await assert.rejects(modern.submit('/business/personnel/travel/trips',clean(f.initial.trip_command),{operation:'trip.save',targetKind:'trip',targetId:f.initial.trip.id}));assert.throws(()=>new TravelCommand(api,{employeeId:id,root:MILEAGE_ROOT}));
});

for(const kind of ['draft','settlement','payment'])test('accepted '+kind+' lost reply is resolved by original private status, even after write feature withdrawal',async()=>{
 const names={draft:'trip',settlement:'settlement',payment:'payment'},x=f.initial,body=clean(x[kind==='draft'?'trip_command':kind+'_command']),receipt=x[kind+'_receipt'],posts=[],reads=[];let feature=true;
 const source=copy(f.sources);source.rights={...source.rights,read:true,write:true,approve:true,payments:true};const api={get:async path=>{reads.push(path);if(path==='/me')return{id:receipt.actor_id};if(path==='/business/capabilities')return{readonly:false,features:['travel_allowances',MILEAGE_READ_FEATURE,...feature?[MILEAGE_FEATURE]:[]],capabilities:['business_travel_allowances']};if(path.endsWith('/sources?employee_id='+id))return source;if(path.endsWith('/requests/'+receipt.request_id))return receipt;throw new Error('Unexpected private read '+path);},post:async(path,command)=>{posts.push({path,body:copy(command)});throw new Error('Synthetic accepted response lost');}};
 const old=crypto.randomUUID;Object.defineProperty(crypto,'randomUUID',{configurable:true,value:()=>receipt.request_id});try{
  const command=new TravelCommand(api,{employeeId:id,root:MILEAGE_ROOT,writeFeature:MILEAGE_FEATURE,validateResult:mileageResult});await assert.rejects(command.submit(MILEAGE_ROOT+'/'+(kind==='draft'?'trips':kind==='settlement'?'settlements':'payments'),body,{operation:receipt.operation,targetKind:names[kind],targetId:receipt.target_id,right:kind==='settlement'?'approve':kind==='payment'?'payments':'write'}));assert.ok(command.pending);feature=false;const accepted=await command.retry();assert.equal(accepted.result.id,receipt.target_id);assert.equal(command.pending,null);assert.equal(posts.length,1);assert.deepEqual(posts[0].body,kind==='draft'?x.trip_command:x[kind+'_command']);assert.ok(reads.every(path=>!path.includes('/travel/sources')&&!path.includes('/travel/requests')));
 }finally{Object.defineProperty(crypto,'randomUUID',{configurable:true,value:old});}
});

test('submitted and rejected actions retain the exact previous route and private source snapshot',()=>{
 mileageActionValidator(f.initial.draft,'submit')(f.initial.trip);mileageActionValidator(f.initial.trip,'reject')(f.correction.rejected);const wrong=copy(f.initial.trip);wrong.details.mileage.legs[0].distance_m--;assert.throws(()=>mileageActionValidator(f.initial.draft,'submit')(wrong));
});

test('missing historical read marker denies the new root even when write metadata is present',async()=>{
 let posts=0;const api={get:async path=>path==='/me'?{id:f.owner.id}:path==='/business/capabilities'?{readonly:false,features:['travel_allowances',MILEAGE_FEATURE],capabilities:['business_travel_allowances']}:f.sources,post:async()=>{posts++;}};const command=new TravelCommand(api,{employeeId:id,root:MILEAGE_ROOT,writeFeature:MILEAGE_FEATURE});await assert.rejects(command.fresh());assert.equal(posts,0);
});
