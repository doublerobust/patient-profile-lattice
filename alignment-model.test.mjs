import test from 'node:test';
import assert from 'node:assert/strict';
import {DAY, alignedTime, alignmentRoster, summaries} from './lattice-model.mjs';
const patients=[['s','a'],['s','b'],['s','c']];
const alignment={anchor:'first_PR',patients:[
  {patient_key:patients[0],status:'resolved',date:'2025-01-10'},
  {patient_key:patients[1],status:'no_qualifying_event',date:null},
  {patient_key:patients[2],status:'event_date_unresolved',date:null}]};
const marks=patients.map((patient_key,i)=>({patient_key,record_id:String(i),lane:'AE',date:'2025-01-08',end_date:'2025-01-12',end_state:'recorded'}));
test('elapsed coordinate preserves source dates, unresolved never imputed',()=>{
  const before=structuredClone(marks);
  assert.equal(alignedTime(marks[0].date,patients[0],alignment),-2*DAY);
  assert.equal(alignedTime(marks[0].end_date,patients[0],alignment),2*DAY);
  assert.equal(alignedTime(marks[1].date,patients[1],alignment),null);
  assert.equal(alignedTime(marks[2].date,patients[2],alignment),null);
  assert.deepEqual(marks,before);
});
test('visible roster denominators and missing groups are explicit',()=>{
  assert.deepEqual(alignmentRoster(alignment,patients).counts,{resolved:1,no_qualifying_event:1,event_date_unresolved:1});
  const cells=summaries(marks,patients,-30*DAY,'layer-time',marks,alignment);
  assert.equal(cells.length,3);
  const dated=cells.find(c=>c.bin!==null);
  assert.equal(dated.bin,-1);assert.equal(dated.denominator,1);assert.equal(dated.start,'day -30');assert.equal(dated.end,'day -1');
  assert.equal(cells.find(c=>c.bucket==='no_qualifying_event').denominator,1);
  assert.equal(cells.find(c=>c.bucket==='event_date_unresolved').denominator,1);
  assert.deepEqual(cells.flatMap(c=>c.recordIds).sort(),['0','1','2']);
  const subset=alignmentRoster(alignment,[patients[1]]);
  assert.equal(subset.counts.resolved,0);assert.equal(subset.counts.no_qualifying_event,1);
});
