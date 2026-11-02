'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const core=require('./static/state-core.js');
const spec=require('./data/normalized_spec.json');
function state(){return {analysis:structuredClone(spec.analysis_state),display:{view:structuredClone(spec.view_state),sort:'duration',tier:'auto',renderer:'3d',camera:{x:880,y:-680,z:0,span:1520,yaw:0,pitch:0,peel:0,distance:5000},alignment:null,highlights:[]}};}
test('legacy 3d chatSnapshot includes peel, preserved exactly on apply/revert',()=>{
  const before=state(),after=state();after.display.camera.peel=1;
  const diff=core.stateDiff(before,after);
  assert.deepEqual(core.revertDiff(core.applyDiff(before,diff),diff),before);
});
test('documented temporal contract survives exact restoration without inferred semantics',()=>{
  const before=state();before.analysis.temporal_window={anchor_domain:'EX',anchor_variable:'EXSTDTC',anchor_occurrence:'first',event_variable:'AESTDTC',direction:'after',lower_days:0,upper_days:30,lower_inclusive:true,upper_inclusive:true,date_policy:'exclude_incomplete_with_diagnostic',missing_anchor_policy:'exclude_patient_with_diagnostic'};
  const after=structuredClone(before);after.analysis.temporal_window=null;
  const diff=core.stateDiff(before,after);assert.deepEqual(core.revertDiff(after,diff),before);
});
test('alignment resolver result shape preserves dates and null missing anchors; invalid forms rejected',()=>{
  const before=state();before.display.renderer='lattice';delete before.display.camera.peel;
  const after=structuredClone(before);
  // Synthetic shape test, NOT evidence of fixture anchor counts or source resolution.
  after.display.alignment={status:'resolved',anchor:'first_PR',axis_label:'days since first recorded PR',definition:'RSORRES=PR at RSDTC',convention:'Elapsed days; no imputation',denominator:2,denominator_unit:'loaded roster patients',counts:{resolved:1,no_qualifying_event:1,event_date_unresolved:0},patients:[{patient_key:['S','P1'],status:'resolved',date:'2025-01-01',record_ids:['RS1']},{patient_key:['S','P2'],status:'no_qualifying_event',date:null,record_ids:[]}],record_ids:['RS1'],missing_anchor_handling:'Missing anchors remain unaligned.',note:'Display only.'};
  const diff=core.stateDiff(before,after);assert.deepEqual(core.applyDiff(before,diff),after);assert.deepEqual(core.revertDiff(after,diff),before);
  for(const change of [a=>a.anchor='randomization',a=>a.denominator=3,a=>a.counts.resolved=2,a=>a.patients[1].date='2025-01-01',a=>a.record_ids=[],a=>a.patients[0].date='2025-02-30']) {
    const invalid=structuredClone(after);change(invalid.display.alignment);assert.throws(()=>core.createState(invalid));
  }
});
