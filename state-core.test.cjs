'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const core = require('./static/state-core.js');
const spec = require('./data/normalized_spec.json');
function fixture(renderer='timeline') {
  return {analysis:structuredClone(spec.analysis_state),display:{view:structuredClone(spec.view_state),sort:'duration',tier:'auto',renderer,camera:renderer==='timeline'?{start:0,end:100}:{x:0,y:0,z:0,yaw:0,pitch:0,distance:100,span:20},alignment:null,highlights:[]}};
}
test('stores analysis separately; display diff round trips exactly without mutating inputs',()=>{
  const before=fixture(), after=fixture();
  after.display.sort='desc';after.display.view.focus_patient_keys=[before.analysis.population[0]];
  after.display.view.hidden_lanes=['CM'];after.display.tier='2';after.display.camera={start:-10,end:30};after.display.highlights=['AE-001-2'];
  const original=structuredClone(before), diff=core.stateDiff(before,after);
  assert.deepEqual(Object.keys(diff),['display']);
  const applied=core.applyDiff(before,diff);
  assert.deepEqual(applied,after);assert.deepEqual(core.revertDiff(applied,diff),before);
  assert.deepEqual(before,original);assert.deepEqual(applied.analysis,before.analysis);
  assert.ok(Object.isFrozen(applied.analysis.population[0]));
});
test('analysis and combined diffs restore predicates, population, selection and camera exactly',()=>{
  for(const renderer of ['timeline','3d','lattice']) {
    const before=fixture(renderer), after=fixture(renderer);
    after.analysis.population=[];after.analysis.ae_predicate=null;
    after.display.view.selection=null;after.display.highlights=['AE-001-2'];
    const diff=core.stateDiff(before,after);
    assert.deepEqual(core.revertDiff(core.applyDiff(before,diff),diff),before);
    assert.deepEqual(core.resetState(after,before),before);
  }
});
test('display-only undo preserves later independent analysis changes',()=>{
  const before=fixture(), after=fixture();after.display.sort='asc';
  const diff=core.stateDiff(before,after), current=structuredClone(core.applyDiff(before,diff));
  current.analysis.population=[];
  const restored=core.revertDiff(current,diff);
  assert.deepEqual(restored.analysis,current.analysis);assert.deepEqual(restored.display,before.display);
});
test('stale apply/revert rejects atomically, including combined domain conflicts',()=>{
  const before=fixture(), after=fixture();after.display.sort='asc';after.analysis.population=[];
  const diff=core.stateDiff(before,after), stale=fixture();stale.analysis.ae_predicate=null;
  const original=structuredClone(stale);
  assert.throws(()=>core.applyDiff(stale,diff),/conflict/i);assert.deepEqual(stale,original);
  assert.throws(()=>core.revertDiff(before,diff),/conflict/i);
});
test('empty diff, serialized diff, and key-order-independent equality',()=>{
  const before=fixture(), reordered={display:before.display,analysis:{temporal_window:null,population:before.analysis.population,ae_predicate:{value:'SEVERE',operator:'eq',variable:'AESEV'}}};
  assert.deepEqual(core.stateDiff(before,reordered),{});
  assert.deepEqual(core.applyDiff(before,{}),before);
  const after=fixture();after.display.sort='asc';
  assert.deepEqual(core.applyDiff(before,JSON.parse(JSON.stringify(core.stateDiff(before,after)))),after);
});
test('snapshots and diff payloads are detached and deeply immutable',()=>{
  const before=fixture(), after=fixture();after.display.highlights=['AE-001-2'];
  const diff=core.stateDiff(before,after), saved=core.createState(before);
  after.display.highlights.push('later');before.analysis.population.length=0;
  assert.deepEqual(diff.display.after.highlights,['AE-001-2']);assert.notEqual(saved.analysis.population.length,0);
  assert.throws(()=>{diff.display.after.highlights.push('tamper');},TypeError);
});
test('unknown fields cannot smuggle analysis changes into display-only diff',()=>{
  const before=fixture();
  for(const diff of [{other:{}},{display:{before:before.display,after:{...before.display,analysis:before.analysis}}},{display:{before:before.display,after:before.display,code:'bad'}},JSON.parse('{"__proto__":{}}')])assert.throws(()=>core.applyDiff(before,diff));
  assert.throws(()=>core.createState({...before,code:'globalThis.executed=true'}));
  assert.equal(globalThis.executed,undefined);
});
test('malformed values, arrays, IDs, dates, cameras and unsupported analysis semantics fail closed',()=>{
  const edits=[s=>s.analysis.population.push(s.analysis.population[0]),s=>s.analysis.population=[['only-one']],s=>s.analysis.ae_predicate={variable:'CAUSE',operator:'eq',value:'drug'},s=>s.analysis.temporal_window={anchor:'randomization'},s=>s.display.sort='clinical benefit',s=>s.display.tier=2,s=>s.display.camera.end=NaN,s=>s.display.camera.end=-1,s=>s.display.highlights=['a','a'],s=>s.display.view.hidden_lanes=['FAKE'],s=>s.display.view.display_date_window={start:'2025-02-30',end:'2025-03-01'},s=>s.display.view.selection={mark_id:'m',source_record_ids:[]},s=>s.display.renderer='unknown'];
  for(const edit of edits){const s=fixture();edit(s);assert.throws(()=>core.createState(s));}
});
test('only finite JSON data accepted; accessors are rejected without execution',()=>{
  for(const value of [undefined,()=>1,Symbol('x'),1n,Infinity,new Date(),new Map()]){const s=fixture();s.display.camera=value;assert.throws(()=>core.createState(s));}
  const cyclic=fixture();cyclic.display.camera=cyclic;assert.throws(()=>core.createState(cyclic));
  let called=false;const s=fixture();Object.defineProperty(s.display,'camera',{enumerable:true,get(){called=true;return null;}});
  assert.throws(()=>core.createState(s));assert.equal(called,false);
  const sparse=fixture();sparse.display.highlights=new Array(2);assert.throws(()=>core.createState(sparse));
});
test('browser global loads without DOM/network and executes real diff round trip',()=>{
  const context=vm.createContext({});vm.runInContext(fs.readFileSync('./static/state-core.js','utf8'),context);
  context.input=JSON.stringify(fixture());
  const output=vm.runInContext('const a=JSON.parse(input),b=JSON.parse(input); b.display.sort="asc"; JSON.stringify(ViewStateCore.revertDiff(ViewStateCore.applyDiff(a,ViewStateCore.stateDiff(a,b)),ViewStateCore.stateDiff(a,b)))',context);
  assert.deepEqual(JSON.parse(output),fixture());
});
