import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {customerWorkspaceAcceptance,customerWorkspaceRights,customerWorkspaceStaffView,customerWorkspaceIssuedLink,customerWorkspacePublicationData,customerWorkspaceOriginal} from '../customer-workspace-staff.js';
import {workspaceSHA256} from '../customer-workspace.js';

const id=c=>c.repeat(32),project=id('a'),customer=id('b'),entry=id('c'),source=id('d'),grant=id('e'),stamp='2026-11-03T12:00:00+00:00';
const bytes=new TextEncoder().encode('%PDF-1.7\nSynthetic archive\n%%EOF'),hash=await workspaceSHA256(bytes);
const metadata=()=>({filename:'Original.pdf',media_type:'application/pdf',size:bytes.length,sha256:hash});
const grantDTO=()=>({id:grant,recipient_name:'Synthetic recipient',recipient_email:'customer@example.test',allow_upload:true,status:'active',created_at:stamp,expires_at:'2026-11-10T12:00:00+00:00'});
const capabilities=()=>({features:['customer_workspace_portal'],capabilities:['business_customer_workspace'],active_capabilities:['business_customer_workspace'],readonly:false,permissions:['portal.manage','documents.read','documents.write','documents.classify']});
const view=()=>({project:{id:project,customer_id:customer,name:'Synthetic project',customer:'Synthetic customer'},publication:null,grants:[grantDTO()],files:[{...metadata(),id:entry,project_id:project,source_kind:'media',source_id:source,title:'Published original',status:'published',created_at:stamp}],uploads:[{...metadata(),id:id('f'),project_id:project,customer_id:customer,grant_id:grant,note:'Customer file',status:'received',created_at:stamp,acceptance:null}],source_files:[{...metadata(),source_kind:'media',source_id:source,title:'Original source'}],writes_allowed:true,can_accept:true});

test('workspace rights require specific portal and document access with current feature, write mode and module',()=>{
  const value=customerWorkspaceRights(capabilities());assert.deepEqual(value,{available:true,read:true,writes:true,classifications:['restricted','operational']});
  for(const change of [{permissions:['finance.read','finance.write']},{features:[]},{capabilities:[]}])assert.equal(customerWorkspaceRights({...capabilities(),...change}).read,false);
  assert.equal(customerWorkspaceRights({...capabilities(),readonly:true}).writes,false);
  assert.equal(customerWorkspaceRights({...capabilities(),active_capabilities:[]}).writes,false);
  assert.equal(customerWorkspaceRights(capabilities(),{modules:{documents:{enabled:false}}}).writes,false);
  const elevated={...capabilities(),permissions:[...capabilities().permissions,'finance.read','finance.write','personnel.read','personnel.manage']};assert.deepEqual(customerWorkspaceRights(elevated).classifications,['restricted','operational','financial','personnel']);
});

test('staff projection validates project bindings and excludes unneeded private data',()=>{
  const input=view();input.password='secret';input.project.secret='secret';input.grants[0].secret_hash='secret';input.source_files[0].private_notes='secret';
  const actual=customerWorkspaceStaffView(input,project);assert.equal(JSON.stringify(actual).includes('secret'),false);assert.equal(actual.source_files[0].source_id,source);
  for(const changes of [{project:{...input.project,id:id('f')}},{files:[{...input.files[0],project_id:id('f')}]},{uploads:[{...input.uploads[0],status:'accepted'}]},{can_accept:'true'},{source_files:[{...input.source_files[0],source_kind:'personnel'}]}])assert.throws(()=>customerWorkspaceStaffView({...view(),...changes},project));
});

test('only a same-host project invitation for the acknowledged grant is exposed once',()=>{
  const base={grant:grantDTO(),link_available:true,portal_url:'https://office.example.test/office/customer-workspace.html#grant='+grant+'&key=SPCI_'+'x'.repeat(43)};
  assert.equal(customerWorkspaceIssuedLink(base,'office.example.test'),base.portal_url);assert.equal(customerWorkspaceIssuedLink({grant:grantDTO(),link_available:false},'office.example.test'),null);
  for(const portal_url of [base.portal_url.replace('office.example.test','foreign.example.test'),base.portal_url.replace('customer-workspace.html','portal.html'),base.portal_url.replace('SPCI_','SPPI_'),base.portal_url.replace('#','?trace=1#'),base.portal_url.replace('grant='+grant,'grant='+id('f')),base.portal_url+'&key=SPCI_'+'y'.repeat(43)])assert.throws(()=>customerWorkspaceIssuedLink({...base,portal_url},'office.example.test'));
  assert.throws(()=>customerWorkspaceIssuedLink({...base,link_available:'true'},'office.example.test'));
});

test('publication approval carries only the explicitly reviewed text, customer and previous revision',()=>{
  const p=view().project,values={title:'  Visible title ',description:'Visible content',status_label:'Ready',start_date:'2026-11-04',end_date:'2026-11-05',confirmation:true,private_margin:'never copied'};
  const payload=customerWorkspacePublicationData(p,{revision:4},values);
  assert.deepEqual(payload,{project_id:project,customer_id:customer,expected_revision:4,title:'Visible title',description:'Visible content',status_label:'Ready',start_date:'2026-11-04',end_date:'2026-11-05',confirmation:true});
  for(const confirmation of [false,'true',1,undefined])assert.throws(()=>customerWorkspacePublicationData(p,null,{...values,confirmation}));
  assert.throws(()=>customerWorkspacePublicationData(p,null,{...values,end_date:'2026-11-01'}));
  assert.throws(()=>customerWorkspacePublicationData(p,null,{...values,start_date:'not-a-date'}));
});

test('upload acceptance cannot acknowledge another upload, archive or chosen access classification',()=>{
  const result={upload_id:entry,media_id:source,classification:'restricted',accepted_at:stamp};assert.deepEqual(customerWorkspaceAcceptance(result,entry,'restricted'),result);
  assert.throws(()=>customerWorkspaceAcceptance({...result,upload_id:id('f')},entry,'restricted'));assert.throws(()=>customerWorkspaceAcceptance({...result,media_id:'wrong'},entry,'restricted'));assert.throws(()=>customerWorkspaceAcceptance({...result,classification:'operational'},entry,'restricted'));assert.throws(()=>customerWorkspaceAcceptance({...result,classification:'unknown'},entry));
});

test('staff original preview verifies exact bytes, media type and size before download',async()=>{
  const api={binary:async()=>new Blob([bytes],{type:'application/pdf'})};assert.deepEqual(Buffer.from(await (await customerWorkspaceOriginal(api,'/business/customer-workspace/uploads/'+entry+'/content',metadata())).arrayBuffer()),Buffer.from(bytes));
  await assert.rejects(customerWorkspaceOriginal({binary:async()=>new Blob([bytes],{type:'image/png'})},'/original',metadata()));
  await assert.rejects(customerWorkspaceOriginal(api,'/original',{...metadata(),sha256:'f'.repeat(64)}));
  await assert.rejects(customerWorkspaceOriginal(api,'/original',{...metadata(),size:bytes.length+1}));
});

test('staff view uses existing API request receipts and never persists invitation links',async()=>{
  const sourceText=await readFile(new URL('../customer-workspace-staff.js',import.meta.url),'utf8');assert.ok(!/localStorage|sessionStorage|indexedDB|innerHTML|insertAdjacentHTML|document\.cookie/.test(sourceText));
  assert.match(sourceText,/api\.mutate\(/);assert.match(sourceText,/\{validate\}/);assert.match(sourceText,/isCurrent\(\)/);assert.match(sourceText,/api\.generation===generation/);assert.match(sourceText,/classification:choice/);assert.match(sourceText,/restricted/);
});
