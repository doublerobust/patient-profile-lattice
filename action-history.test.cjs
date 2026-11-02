'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const core=require('./static/state-core.js');
const {createHistory}=require('./static/action-history.js');
const spec=require('./data/normalized_spec.json');
const fixture=()=>({analysis:structuredClone(spec.analysis_state),display:{view:structuredClone(spec.view_state),sort:'duration',tier:'auto',renderer:'timeline',camera:{start:0,end:100},alignment:null,highlights:[]}});
const payload=(before,after,tool='set_view')=>({action:{tool,args:{synthetic:true}},diff:core.stateDiff(before,after),record_ids:['AE-001-1'],linked_record_ids:['CM-001-1']});
test('records immutable schema, source IDs, no-op queries, and exact combined undo/reset',async()=>{
  const initial=fixture();let rendered=initial;
  const h=createHistory({initial,commit:async next=>{rendered=next;}});
  const next=fixture();next.analysis.population=[];next.display.sort='asc';next.display.camera={start:-10,end:20};
  const input=payload(initial,next), entry=await h.execute(input);
  input.action.args.synthetic=false;input.record_ids.push('tamper');
  assert.deepEqual(rendered,next);assert.deepEqual(entry.action,{tool:'set_view',args:{synthetic:true}});
  assert.deepEqual(entry.record_ids,['AE-001-1']);assert.deepEqual(entry.linked_record_ids,['CM-001-1']);
  assert.deepEqual(entry.controls,{undo:{entry_id:entry.id},reset:{target:'initial'}});
  assert.ok(Object.isFrozen(entry.diff.analysis.before.population));
  await h.execute(payload(next,next,'query_data'));assert.equal(h.snapshot().entries.length,2);
  await h.undo();assert.deepEqual(rendered,next);
  await h.undo();assert.deepEqual(rendered,initial);assert.deepEqual(h.snapshot().state,initial);
  await h.execute(payload(initial,next));await h.reset();
  assert.deepEqual(rendered,initial);assert.deepEqual(h.snapshot().entries,[]);
  await assert.rejects(h.undo(),/No action/);
});
test('invalid/stale actions and failed commits never append or change authoritative state',async()=>{
  const initial=fixture(), next=fixture();next.display.sort='desc';let fail=true;
  const h=createHistory({initial,commit:async()=>{if(fail)throw Error('render failed');}});
  await assert.rejects(h.execute(payload(initial,next)),/render failed/);
  assert.deepEqual(h.snapshot().state,initial);assert.equal(h.snapshot().entries.length,0);
  fail=false;await h.execute(payload(initial,next));
  await assert.rejects(h.execute(payload(initial,next)),/conflict/i);
  fail=true;await assert.rejects(h.undo(),/render failed/);await assert.rejects(h.reset(),/render failed/);
  assert.deepEqual(h.snapshot().state,next);assert.equal(h.snapshot().entries.length,1);
  assert.equal(h.snapshot().busy,false);
});
test('serializes commits by rejecting overlap and prevents stale per-entry undo',async()=>{
  let release;const initial=fixture(),next=fixture();next.display.sort='asc';
  const h=createHistory({initial,commit:()=>new Promise(resolve=>{release=resolve;})});
  const pending=h.execute(payload(initial,next));assert.equal(h.snapshot().busy,true);
  await assert.rejects(h.reset(),/busy/);await assert.rejects(h.undo(),/busy/);
  await assert.rejects(h.execute(payload(initial,next)),/busy/);
  assert.throws(()=>h.replaceSession(initial),/busy/);
  release();const first=await pending;
  const pending2=h.execute(payload(next,next,'query_data'));release();await pending2;
  await assert.rejects(h.undo(first.id),/latest/);assert.equal(h.snapshot().entries.length,2);
});
test('session replacement drops old baseline and entries; returned snapshots cannot be tampered',async()=>{
  const initial=fixture(),next=fixture();next.analysis.population=[];
  const h=createHistory({initial});const e=await h.execute(payload(initial,next));
  h.replaceSession(next);assert.deepEqual(h.snapshot().entries,[]);
  const changed=structuredClone(next);changed.display.sort='desc';
  const e2=await h.execute(payload(next,changed));assert.notEqual(e.id,e2.id);
  assert.throws(()=>h.snapshot().entries.push({}),TypeError);
  await h.reset();assert.deepEqual(h.snapshot().state,next);
});
test('rejects executable/non-JSON metadata without invoking getters; subscribers cannot break commit',async()=>{
  const initial=fixture(),h=createHistory({initial});let invoked=false;
  const bad=payload(initial,initial);Object.defineProperty(bad.action.args,'evil',{enumerable:true,get(){invoked=true;return 1;}});
  await assert.rejects(h.execute(bad));assert.equal(invoked,false);
  for(const edit of [p=>p.record_ids=null,p=>p.linked_record_ids=false,p=>p.record_ids=['x','x'],p=>p.record_ids=[3],p=>p.action.tool='',p=>p.action.args={code:()=>1},p=>p.extra=true]) {
    const p=payload(initial,initial);edit(p);await assert.rejects(h.execute(p));
  }
  const unsubscribe=h.subscribe(()=>{throw Error('observer');});
  await h.execute(payload(initial,initial));assert.equal(h.snapshot().entries.length,1);unsubscribe();
});
