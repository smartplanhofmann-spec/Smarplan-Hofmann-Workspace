import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {overviewModel,renderCompanyOverview} from '../company-overview.js';

const fixture=()=>JSON.parse(readFileSync(new URL('../../../app/test/fixtures/company_overview.json',import.meta.url),'utf8'));
test('separate net revenue, cash and incomplete tax result retain server values',()=>{
  const value=overviewModel(fixture());
  assert.equal(value.finance.revenue_net,'1000.00');assert.equal(value.finance.receipts_gross,'119.00');
  assert.equal(value.finance.contribution_net,'600.00');assert.equal(value.accounting.totals.euer_surplus,null);
});
test('unproven financial totals and global accounting within selected project are refused',()=>{
  for(const edit of [v=>v.finance.complete_for_recorded_sources=false,v=>v.accounting.balance='100.00',v=>v.scope='selected_project',v=>v.finance.revenue_net=1000]){
    const value=fixture();edit(value);assert.throws(()=>overviewModel(value));
  }
});
test('cards link to their actual project and EÜR; arbitrary source URLs are never navigated',()=>{
  const value=fixture();value.tasks[0].source_path='https://untrusted.example.invalid';
  const buttons=[];const selected=[];let accounting=0;
  const node=(...children)=>({children,append(...items){this.children.push(...items);}});
  const result=renderCompanyOverview(value,{el:node,panel:node,row:node,rows:(items,fn)=>node(...items.map(fn)),
    notice:node,button:(label,fn)=>{buttons.push({label,fn});return node(label);},formatMoney:v=>v??'UNKNOWN',formatDate:v=>v??'UNKNOWN',
    onProject:(id,tab)=>selected.push([id,tab]),onAccounting:()=>accounting++});
  buttons.filter(v=>v.label==='Vorgang öffnen').forEach(v=>v.fn());
  assert.deepEqual(selected,[['c'.repeat(32),'tasks'],['c'.repeat(32),'costs']]);
  buttons.find(v=>v.label==='EÜR und Belege öffnen').fn();assert.equal(accounting,1);
  assert.match(JSON.stringify(result),/Klärung erforderlich/);assert.match(JSON.stringify(result),/Anfangsbestände/);
});
