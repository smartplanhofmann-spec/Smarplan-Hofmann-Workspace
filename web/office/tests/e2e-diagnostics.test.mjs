import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';

// Importing diagnostics neither launches a browser nor requires Playwright.
const {compactFailure}=createRequire(import.meta.url)('./e2e.cjs');

test('browser crash diagnostics retain the initial error and final stack, with a bounded middle',()=>{
  const lines=['browserType.launch: browser closed','FATAL: No usable sandbox!'];
  for(let index=0;index<500;index++)lines.push('Chromium switch dump '+index);
  lines.push('at main (e2e.cjs:99)');
  const result=compactFailure({stack:lines.join('\n')});
  assert.deepEqual(result.split('\n').slice(0,35),lines.slice(0,35));
  assert.deepEqual(result.split('\n').slice(-15),lines.slice(-15));
  assert.equal(result.split('\n').length,51);
  assert.match(result,/453 middle diagnostic lines omitted/);
});

test('one enormous Chromium command cannot hide the following fatal message',()=>{
  const result=compactFailure({stack:'browserType.launch failed\n'+('--synthetic-switch '.repeat(500))+'\nFATAL: user namespace denied'});
  assert.ok(result.length<550);
  assert.match(result,/\[line truncated\]/);
  assert.match(result,/FATAL: user namespace denied/);
});

test('short ordinary browser errors remain complete',()=>{
  assert.equal(compactFailure({stack:'Synthetic assertion\r\nat main'}),'Synthetic assertion\nat main');
});
