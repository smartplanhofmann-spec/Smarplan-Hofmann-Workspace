import assert from 'node:assert/strict';
import test from 'node:test';
import {employeeAccountSelection} from '../office.js';

const value=()=>({schema_version:1,items:[{id:'a'.repeat(32),email:'synthetic@example.test'}]});
test('HR account selection contains only bounded current identity fields',()=>{
 const v=value();assert.deepEqual(employeeAccountSelection(v),v.items);
 assert.notEqual(employeeAccountSelection(v)[0],v.items[0]);
 assert.deepEqual(employeeAccountSelection({schema_version:1,items:[]}),[]);
});
test('unknown schema extra fields duplicated identities and partial lists are rejected',()=>{
 for(const v of [{...value(),schema_version:2},{...value(),has_more:true},{...value(),items:[{...value().items[0],role:'owner'}]},{...value(),items:[value().items[0],value().items[0]]},{...value(),items:Array.from({length:501},(_,n)=>({id:n.toString(16).padStart(32,'0'),email:'synthetic@example.test'}))}])assert.throws(()=>employeeAccountSelection(v));
});
test('invalid identity and email shape cannot populate a personnel form',()=>{
 for(const row of [{id:'../user',email:'synthetic@example.test'},{id:'a'.repeat(32),email:'invalid'},{id:'a'.repeat(32),email:'x'.repeat(250)+'@example.test'},null])assert.throws(()=>employeeAccountSelection({schema_version:1,items:[row]}));
});
