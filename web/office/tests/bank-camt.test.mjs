import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {webcrypto} from 'node:crypto';
import {bankCamtInspection,bankCamtMetadata,bankCamtPreviewHash,bankCamtCanonical} from '../bank-camt-contract.js';
globalThis.crypto??=webcrypto;
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/bank_camt.json',import.meta.url)));
const copy=v=>JSON.parse(JSON.stringify(v));

test('canonical key order matches Unicode scalar ordering including negative integers',()=>{
 assert.equal(bankCamtCanonical({'😀':1,'\uE000':-2}),'{"\uE000":-2,"😀":1}');
});

test('actual accepted XML bank fixture passes independent metadata and preview hashes',async()=>{
 const original=copy(f);
 assert.deepEqual(bankCamtMetadata(f.receipt.statement.payload),f.preview.metadata);
 assert.deepEqual(await bankCamtPreviewHash(f.preview),f.preview);
 assert.deepEqual(await bankCamtInspection(f.inspection,f.request,f.inspection.original_sha256),f.inspection);
 assert.deepEqual(f,original);
});

test('changed schema, namespace, version or format cannot select a new rule',()=>{
 for(const [where,key,value]of [['meta','contract','unknown'],['meta','delimiter',';'],['proof','schema_sha256','0'.repeat(64)],['proof','namespace','urn:unknown']]){
  const meta=copy(f.preview.metadata);(where==='meta'?meta:meta.camt)[key]=value;
  assert.throws(()=>bankCamtMetadata(meta));
 }
});

test('changed rows and balances still fail the actual server preview hash',async()=>{
 const p=copy(f.preview);p.metadata.rows[0].amount='125.01';p.metadata.closing_balance='200.01';p.total='100.01';
 bankCamtMetadata(p.metadata);
 await assert.rejects(()=>bankCamtPreviewHash(p));
});

test('wrong account, original or automatic confirmation claim is rejected',async()=>{
 for(const [key,value]of [['original_sha256','0'.repeat(64)],['financial_changes',true],['confirmation_required',false],['schema_version',2]]){
  const v=copy(f.inspection);v[key]=value;
  await assert.rejects(()=>bankCamtInspection(v,f.request,f.inspection.original_sha256));
 }
 await assert.rejects(()=>bankCamtInspection(f.inspection,{...f.request,account_id:'b'.repeat(32)},f.inspection.original_sha256));
});

test('unknown fields in original proof or entry projection fail closed',()=>{
 const mutations=[m=>{m.extra=true;},m=>{m.camt.extra=true;},m=>{m.camt.entry_sources[0].ignore_reference=true;},m=>{m.rows[0].tax_guess='19';}];
 for(const mutate of mutations){const meta=copy(f.preview.metadata);mutate(meta);assert.throws(()=>bankCamtMetadata(meta));}
});

test('duplicate entry identity, wrong direction and fractional cents cannot pass',()=>{
 for(const mutate of [m=>{m.rows[1].transaction_id=m.rows[0].transaction_id;},m=>{m.rows[0].amount='125.001';},m=>{m.rows[1].amount='25.00';},m=>{m.rows[0].currency='USD';}]){
  const meta=copy(f.preview.metadata);mutate(meta);assert.throws(()=>bankCamtMetadata(meta));
 }
});

test('entry sources bind every ordinal and bank identity to the selected original',()=>{
 for(const mutate of [m=>{m.camt.entry_sources.pop();},m=>{m.camt.entry_sources[0].line_number=2;},m=>{m.camt.entry_sources[0].bank_reference='other';},m=>{m.camt.file_sha256='0'.repeat(64);}]){
  const meta=copy(f.preview.metadata);mutate(meta);assert.throws(()=>bankCamtMetadata(meta));
 }
});

test('key order is immaterial but altered period and value date are rejected',async()=>{
 const p=Object.fromEntries(Object.entries(f.preview).reverse());
 assert.deepEqual(await bankCamtPreviewHash(p),f.preview);
 for(const mutate of [m=>{m.period_to='2026-10-30';},m=>{m.rows[0].booking_date='2026-11-01';},m=>{m.rows[0].value_date='2026-02-30';}]){
  const meta=copy(f.preview.metadata);mutate(meta);assert.throws(()=>bankCamtMetadata(meta));
 }
});
