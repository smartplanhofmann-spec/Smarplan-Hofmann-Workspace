/* Versioned projection of an unchanged XML bank original; no payment execution. */
export const CAMT_CONTRACT='smartplan_bank_camt053_08_v1';
export const CAMT_FORMAT='camt.053.001.08';
export const CAMT_SCHEMA='c3cfac080dc31476bde7444b05d00e1b23558d5e44529e58d0ad562e6013873d';
const NS='urn:iso:std:iso:20022:tech:xsd:camt.053.001.08',HASH=/^[a-f0-9]{64}$/;
const fail=()=>{throw new Error('Der XML-Banknachweis gehört nicht zum unveränderten geprüften Original.');};
function shape(v,keys){if(!v||Array.isArray(v)||typeof v!=='object'||Object.keys(v).sort().join(' ')!==keys.split(' ').sort().join(' '))fail();}
function integer(v,min=0,max=Number.MAX_SAFE_INTEGER){if(!Number.isSafeInteger(v)||v<min||v>max)fail();return v;}
function day(v){if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(v)||+v.slice(0,4)<1900||+v.slice(0,4)>2200||new Date(v+'T00:00:00Z').toISOString().slice(0,10)!==v)fail();return v;}
function money(v){if(typeof v!=='string'||! /^-?(?:0|[1-9]\d{0,10})\.\d{2}$/.test(v)||v==='-0.00')fail();return BigInt(v.replace('.',''));}
function text(v,max,nullable=false){if(nullable&&v===null)return;if(typeof v!=='string'||[...v].length<1||[...v].length>max)fail();}
function keyOrder(a,b){const x=[...a].map(c=>c.codePointAt(0)),y=[...b].map(c=>c.codePointAt(0));for(let i=0;i<Math.min(x.length,y.length);i++)if(x[i]!==y[i])return x[i]-y[i];return x.length-y.length;}
function ordered(v){if(Array.isArray(v))return v.map(ordered);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort(keyOrder).map(k=>[k,ordered(v[k])]));if(typeof v==='number')integer(v,-Number.MAX_SAFE_INTEGER);return v;}
export const bankCamtCanonical=value=>JSON.stringify(ordered(value));
export const camtSame=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
export function bankCamtMetadata(meta){
 shape(meta,'contract account bank statement_reference period_from period_to opening_balance closing_balance filename delimiter file_sha256 rows complete_statement_confirmed distinct_transaction_confirmations camt');
 if(meta.contract!==CAMT_CONTRACT||meta.delimiter!==CAMT_FORMAT||!HASH.test(meta.file_sha256)||meta.complete_statement_confirmed!==true||!Array.isArray(meta.rows)||meta.rows.length>10000)fail();
 const proof=meta.camt;shape(proof,'schema_sha256 namespace file_sha256 message_id original_period_from original_period_to entry_sources');
 if(proof.schema_sha256!==CAMT_SCHEMA||proof.namespace!==NS||proof.file_sha256!==meta.file_sha256||!Array.isArray(proof.entry_sources)||proof.entry_sources.length!==meta.rows.length)fail();
 text(proof.message_id,35);text(meta.statement_reference,35);
 const stamp=/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$/;
 if(!stamp.test(proof.original_period_from)||!stamp.test(proof.original_period_to)||!/^\d{4}-\d{2}-\d{2}T00:00:00(?:\.0+)?(?:Z|[+-]\d{2}:\d{2})?$/.test(proof.original_period_from))fail();
 let end=day(proof.original_period_to.slice(0,10));
 if(proof.original_period_to.slice(11,19)==='00:00:00')end=new Date(Date.parse(end+'T00:00:00Z')-86400000).toISOString().slice(0,10);
 else if(proof.original_period_to.slice(11,19)!=='23:59:59')fail();
 if(day(meta.period_from)!==day(proof.original_period_from.slice(0,10))||day(meta.period_to)!==end||meta.period_from>meta.period_to)fail();
 const ids=new Set();let movement=0n;
 meta.rows.forEach((row,i)=>{
  shape(row,'line_number transaction_id booking_date value_date amount currency counterparty reference');
  const source=proof.entry_sources[i];shape(source,'line_number xml_line bank_reference entry_reference transaction_details reversal');
  if(row.line_number!==i+1||source.line_number!==i+1||typeof source.reversal!=='boolean'||row.currency!=='EUR')fail();
  integer(source.xml_line,1,5*1024*1024);integer(source.transaction_details,0,100000);text(source.bank_reference,35);text(source.entry_reference,35,true);
  if(row.transaction_id!=='camt08:'+source.bank_reference.trim()||ids.has(row.transaction_id))fail();ids.add(row.transaction_id);
  if(day(row.booking_date)<meta.period_from||row.booking_date>meta.period_to)fail();day(row.value_date);
  if(typeof row.counterparty!=='string'||[...row.counterparty].length>500||typeof row.reference!=='string'||[...row.reference].length>2000)fail();
  const amount=money(row.amount);if(amount===0n)fail();movement+=amount;
 });
 if(money(meta.opening_balance)+movement!==money(meta.closing_balance))fail();
 if(!meta.distinct_transaction_confirmations||Array.isArray(meta.distinct_transaction_confirmations)||typeof meta.distinct_transaction_confirmations!=='object')fail();
 for(const [id,reason]of Object.entries(meta.distinct_transaction_confirmations)){if(!ids.has(id)||typeof reason!=='string'||!reason.trim()||[...reason].length>1000||/[\u0000-\u001f\u007f]/.test(reason))fail();}
 return meta;
}
export async function bankCamtPreviewHash(preview){
 bankCamtMetadata(preview.metadata);
 const value={...preview};delete value.preview_hash;
 const bytes=new TextEncoder().encode(bankCamtCanonical(value));
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
 if(hash!==preview.preview_hash)fail();return preview;
}
export async function bankCamtInspection(value,expected,sha256){
 shape(value,'schema_version contract original_sha256 suggested_body camt preview confirmation_required financial_changes');
 if(value.schema_version!==1||value.contract!==CAMT_CONTRACT||value.original_sha256!==sha256||value.confirmation_required!==true||value.financial_changes!==false)fail();
 const body=value.suggested_body;shape(body,'account_id account_revision bank_revision filename delimiter statement_reference period_from period_to opening_balance closing_balance');
 if(['account_id','account_revision','bank_revision','filename'].some(k=>body[k]!==expected[k])||body.delimiter!==CAMT_FORMAT)fail();
 const meta=bankCamtMetadata(value.preview?.metadata);
 if(meta.file_sha256!==sha256||!camtSame(meta.camt,value.camt)||meta.account?.id!==expected.account_id||meta.account?.revision!==expected.account_revision||meta.bank?.revision!==expected.bank_revision||Object.keys(body).filter(k=>!['account_id','account_revision','bank_revision'].includes(k)).some(k=>meta[k]!==body[k]))fail();
 await bankCamtPreviewHash(value.preview);return value;
}
