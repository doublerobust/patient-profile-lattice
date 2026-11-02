'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {validateScopeProposal,selectsDisplay,validateCall}=require('./static/tool-registry.js');
const context={roster:[['S','SYN-001'],['S','SYN-002']],renderer:'timeline'};
const action={tool:'set_view',args:{subset:['SYN-001']}};
const propose=(evidence,a=action)=>({intent:a.tool==='set_view'?'display_patients':'highlight_records',evidence,action:a});

test('direct patient/focus/record selections all require scope, not ordinary display styling',()=>{
 for(const [tool,args] of [['set_view',{subset:['SYN-001']}],['set_view',{focus:null}],['set_view',{focus:'SYN-001'}],['highlight_events',{scope:'current_analysis',filters:{}}]])assert.equal(selectsDisplay(tool,args),true);
 assert.equal(selectsDisplay('set_view',{sort:'asc'}),false);
});
test('complete evidence and exact allowlisted scope are required, not merely valid IDs',()=>{
 const prompt='Show only patients SYN-001';
 assert.deepEqual(validateScopeProposal(prompt,propose(prompt),context),propose(prompt));
 for(const p of ['grade 3 AEs','Show the interesting patients','Show only patients SYN-002',prompt+' and the rest'])assert.throws(()=>validateScopeProposal(p,propose(p),context),/Clarification required/);
 for(const evidence of ['', 'SYN-001', 'Show only patients SYN-002'])assert.throws(()=>validateScopeProposal(prompt,propose(evidence),context),/Clarification required/);
 assert.throws(()=>validateScopeProposal(prompt,propose(prompt,{tool:'set_view',args:{subset:['SYN-001','SYN-002']}}),context),/Clarification required/);
});
test('clinical predicates cannot be laundered into explicit IDs or approveable proposals',()=>{
 for(const predicate of ['caused by treatment','related to treatment','due to treatment','with severe events','whose severity increased','whose nausea worsened','who improved','meeting the endpoint','responders','with progression','with treatment-emergent AEs']){
  const prompt='Show only patients '+predicate;
  assert.throws(()=>validateScopeProposal(prompt,propose(prompt),context),/Unsupported clinical predicate/);
 }
});
test('record scope and compound JSON retain exact filters and existing schemas',()=>{
 for(const [prompt,a] of [
  ['Highlight grade 3 AE records',{tool:'highlight_events',args:{scope:'current_analysis',filters:{grade:3}}}],
  ['Highlight source IDs AE-001-1, AE-002-1',{tool:'highlight_events',args:{scope:'current_analysis',filters:{record_ids:['AE-001-1','AE-002-1']}}}],
  ['Highlight exact term SYNTHETIC NAUSEA',{tool:'highlight_events',args:{scope:'current_analysis',filters:{term:'SYNTHETIC NAUSEA'}}}],
  ['Focus on SYN-001',{tool:'set_view',args:{focus:'SYN-001'}}],
  ['Show all patients',{tool:'set_view',args:{focus:null}}]
 ])assert.deepEqual(validateScopeProposal(prompt,propose(prompt,a),context).action,a);
 const a={tool:'highlight_events',args:{scope:'current_analysis',filters:{grade:3,patient:'SYN-001',date_window:{anchor:'AESTDTC',start:'2025-01-01',end:'2025-01-31'}}}};
 assert.deepEqual(validateScopeProposal(JSON.stringify(a),propose(JSON.stringify(a),a),context).action,a);
 for(const invalid of [
  {tool:'set_view',args:{subset:['SYN-001'],analysis_state:{}}},
  {tool:'set_view',args:{subset:['SYN-001'],focus:'SYN-001'}},
  {tool:'highlight_events',args:{scope:'current_analysis',filters:{caused_by:'drug'}}},
  {tool:'confirm_analysis_subset',args:{patients:['SYN-001']}}
 ])assert.throws(()=>validateScopeProposal(JSON.stringify(invalid),propose(JSON.stringify(invalid),invalid),context));
 // Original argument schema still rejects proposal/authorization fields on executable calls.
 assert.throws(()=>validateCall('set_view',{subset:['SYN-001'],approved:true},context));
 assert.throws(()=>validateScopeProposal('Show only patients SYN-001',{...propose('Show only patients SYN-001'),approved:true},context));
});
