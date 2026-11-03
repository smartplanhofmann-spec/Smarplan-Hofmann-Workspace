import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi} from '../office.js';

for (const path of ['/business/assistant/plans', '/business/payroll/runs', '/business/customer-workspace/publications', '/business/personnel/expenses', '/business/accounting/euer/confirm']) {
  test(`uncertain workflow command retains its exact nonce: ${path}`, async () => {
    let status=0, resolution=null; const sent=[];
    const api=new OfficeApi({fetcher:async (url, options)=>{
      if(options.method==='GET')return new Response(JSON.stringify(url.includes('/capabilities')?{readonly:false,features:['assistant_workflow','german_payroll_2026'],capabilities:['business_assistant','business_payroll'],permissions:['assistant.use','personnel.read','personnel.approve']}:url.includes('/contexts/')?{project_id:'a'.repeat(32)}:{employee_id:'c'.repeat(32),items:[]}));
      sent.push(JSON.parse(options.body));
      if(!status)throw new Error('Lost acknowledgement');
      return new Response(JSON.stringify({error:'Synthetic conflict',request_resolution:resolution}),{status});
    }});
    api.setToken('synthetic-workflow-owner-token');
    await assert.rejects(api.mutate('workflow',path,{reason:'Reviewed original',...(path.includes('/assistant/')?{context_id:'b'.repeat(32)}:{}),...(path.includes('/payroll/')?{employee_id:'c'.repeat(32)}:{})}));
    for(status of [403,404,409,423,429,500]) {
      await assert.rejects(api.retry('workflow'));
      assert.equal(api.pendingCount,1);
    }
    status=409; resolution='not_accepted';
    await assert.rejects(api.retry('workflow'));
    assert.equal(api.pendingCount,0);
    for(const body of sent)assert.deepEqual(body,sent[0]);
  });
}
