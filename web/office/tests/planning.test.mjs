import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {planningRange,shiftPlanningAnchor,timelinePlacement,planningTicks} from '../office.js';

test('calendar selection covers December, the following January, leap February and whole years',()=>{
  assert.deepEqual(planningRange('month','2030-12-15'),{from:'2030-12-01',to:'2030-12-31',days:31});
  assert.equal(shiftPlanningAnchor('month','2030-12-31',1),'2031-01-01');
  assert.deepEqual(planningRange('month','2031-01-01'),{from:'2031-01-01',to:'2031-01-31',days:31});
  assert.deepEqual(planningRange('month','2028-02-29'),{from:'2028-02-01',to:'2028-02-29',days:29});
  assert.deepEqual(planningRange('year','2028-08-12'),{from:'2028-01-01',to:'2028-12-31',days:366});
});

test('weeks and navigation remain calendar days across year and daylight-saving boundaries',()=>{
  assert.deepEqual(planningRange('week','2027-01-01'),{from:'2026-12-28',to:'2027-01-03',days:7});
  assert.equal(shiftPlanningAnchor('week','2026-03-23',1),'2026-03-30');
  assert.equal(shiftPlanningAnchor('week','2026-10-19',1),'2026-10-26');
  assert.equal(shiftPlanningAnchor('month','2028-01-31',1),'2028-02-01');
});

test('multiple years stay within the server calendar limit and reject impossible dates',()=>{
  assert.deepEqual(planningRange('multi','2027-11-01',3),{from:'2027-01-01',to:'2029-12-31',days:1096});
  assert.equal(planningRange('multi','2029-11-01',3).days,1095);
  assert.equal(shiftPlanningAnchor('multi','2027-01-01',1,3),'2030-01-01');
  for(const value of ['2027-02-29','2030-13-01','2030-01-32','','2030-01-01T00:00:00Z'])assert.throws(()=>planningRange('year',value));
  for(const years of [1,4,5,'3'])assert.throws(()=>planningRange('multi','2030-01-01',years));
  assert.equal(planningRange('year','2200-01-01').to,'2200-12-31');
  assert.throws(()=>planningRange('multi','2199-01-01',3));
  assert.throws(()=>shiftPlanningAnchor('year','2200-01-01',1));
});

test('project bars include both bounds, retain one-day projects, and clip only the visible part',()=>{
  const range={from:'2030-12-29',to:'2031-01-04',days:7};
  assert.deepEqual(timelinePlacement({start_date:range.from,end_date:range.to},range),{left:0,width:100,clippedStart:false,clippedEnd:false});
  const oneDay=timelinePlacement({start_date:'2031-01-01',end_date:'2031-01-01'},range);
  assert.equal(oneDay.left,3/7*100);assert.equal(oneDay.width,1/7*100);
  assert.deepEqual(timelinePlacement({start_date:'2030-01-01',end_date:'2032-01-01'},range),{left:0,width:100,clippedStart:true,clippedEnd:true});
  const clipped=timelinePlacement({start_date:'2030-12-30',end_date:'2031-02-01'},range);
  assert.equal(clipped.left,1/7*100);assert.equal(clipped.width,6/7*100);assert.equal(clipped.clippedEnd,true);
});

test('missing or invalid project bounds and projects outside the window never produce bars',()=>{
  const range=planningRange('year','2030-01-01');
  for(const item of [{},{start_date:'2030-01-01',end_date:null},{start_date:null,end_date:'2030-01-01'},
    {start_date:'2031-01-01',end_date:'2031-02-01'},{start_date:'2029-01-01',end_date:'2029-12-31'},
    {start_date:'2030-02-01',end_date:'2030-01-01'},{start_date:'2030-02-30',end_date:'2030-03-01'}]){
    assert.equal(timelinePlacement(item,range),null);
  }
});

test('timeline headers expose actual days and all months across the year boundary',()=>{
  const month=planningTicks('month',planningRange('month','2028-02-01'));
  assert.equal(month.length,29);assert.equal(month.at(-1).date,'2028-02-29');
  const years=planningTicks('multi',planningRange('multi','2030-01-01',2));
  assert.equal(years.length,24);assert.equal(years[12].date,'2031-01-01');
  assert.match(years[12].label,/2031/);
  assert.ok(Math.abs(years.reduce((sum,tick)=>sum+tick.width,0)-100)<1e-10);
});

test('calendar math and project clipping are identical in Berlin, Los Angeles and Auckland',()=>{
  const moduleUrl=new URL('../office.js',import.meta.url).href;
  const source=`import {planningRange,timelinePlacement,planningTicks} from ${JSON.stringify(moduleUrl)};const range=planningRange('multi','2027-12-31',3);console.log(JSON.stringify({range,bar:timelinePlacement({start_date:'2027-12-31',end_date:'2028-01-01'},range),ticks:planningTicks('multi',range)}));`;
  const results=['Europe/Berlin','America/Los_Angeles','Pacific/Auckland'].map(TZ=>execFileSync(process.execPath,['--input-type=module','-e',source],{env:{...process.env,TZ},encoding:'utf8'}));
  assert.equal(results[0],results[1]);assert.equal(results[1],results[2]);
});
