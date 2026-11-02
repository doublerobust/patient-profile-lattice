'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {ToolSession,validateCall}=require('./static/tool-registry.js');
const spec=require('./data/normalized_spec.json');
const copy=x=>structuredClone(x);
function fixture(){
 let state={analysis:copy(spec.analysis_state),display:{view:copy(spec.view_state),sort:'duration',tier:'auto',renderer:'timeline',camera:{start:0,end:100},alignment:null,highlights:[]}};
 const roster=copy(state.analysis.population); let resolveCalls=0;
 const session=new ToolSession({snapshot:()=>copy(state),roster:()=>roster,dataset:()=> 'fixture',records:()=>['AE-1'],
  apply:async next=>{state=copy(next);},resolve:async(tool,args)=>{
   resolveCalls++;
   if(tool==='propose_analysis_subset')return {status:'confirmation_required',population:roster.filter(p=>args.patients.includes(p[1])),view_state:copy(state.display.view),before:{patients:3,'AE records':4},after:{patients:1,'AE records':1},population_before:roster.length,population_after:1,record_ids:['AE-1']};
   if(tool==='set_alignment')return {status:'unsupported',anchor:args.anchor,denominator:roster.length,denominator_unit:'loaded roster patients',missing_anchor_handling:'No imputation; unchanged.',note:'Unsupported randomization; development task required.',record_ids:[]};
   return {count:1,unit:args.unit||'AE records',record_ids:['AE-1'],linked_record_ids:[]};
  }});
 return {session,roster,snapshot:()=>copy(state),external:s=>{state=copy(s);},resolveCalls:()=>resolveCalls};
}
test('rejects unknown, ambiguous, executable and clinically inferential calls atomically',async()=>{
 const f=fixture(), before=f.snapshot();
 for(const [name,args] of [['eval',{code:'globalThis.bad=true'}],['set_view',{}],['set_view',{focus:f.roster[0][1],subset:[f.roster[0][1]]}],['query_data',{scope:'current_analysis',filters:{}}],['highlight_events',{scope:'current_analysis',filters:{caused_by:'drug'}}],['set_view',{camera:{start:NaN,end:5}}],['confirm_analysis_subset',{}]])await assert.rejects(f.session.dispatch(name,args));
 let accessed=false;const args={};Object.defineProperty(args,'sort',{enumerable:true,get(){accessed=true;return 'asc';}});
 assert.throws(()=>validateCall('set_view',args));assert.equal(accessed,false);
 assert.equal(globalThis.bad,undefined);assert.deepEqual(f.snapshot(),before);assert.equal(f.resolveCalls(),0);assert.equal(f.session.audit.length,0);
});
test('core-backed history records reads, validated display diff and exact Undo/Reset',async()=>{
 const f=fixture(),before=f.snapshot();
 await f.session.dispatch('set_view',{subset:[f.roster[0][1]],sort:'asc',layers:['AE'],tier:'2'});
 assert.deepEqual(f.snapshot().analysis,before.analysis);
 const entry=f.session.audit[0];assert.deepEqual(Object.keys(entry.diff),['display']);assert.ok(entry.controls.undo);assert.deepEqual(entry.record_ids,['AE-1']);
 const changed=f.snapshot();const q=await f.session.dispatch('query_data',{scope:'current_analysis',unit:'patients',filters:{grade:3}});
 assert.equal(q.count,1);assert.equal(q.unit,'patients');assert.deepEqual(q.record_ids,['AE-1']);assert.deepEqual(f.session.audit[1].diff,{});
 await f.session.undo();assert.deepEqual(f.snapshot(),changed);await f.session.undo();assert.deepEqual(f.snapshot(),before);
 await f.session.dispatch('highlight_events',{scope:'current_analysis',filters:{record_ids:['AE-1']}});await f.session.reset();assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.session.audit,[]);
});
test('analysis population cannot change before separate explicit confirmation; undo exact',async()=>{
 const f=fixture(),before=f.snapshot(),p=await f.session.dispatch('propose_analysis_subset',{patients:[f.roster[0][1]]});
 assert.equal(p.status,'confirmation_required');assert.ok(p.after);assert.deepEqual(f.snapshot(),before);assert.equal(f.session.audit.length,0);
 await assert.rejects(f.session.dispatch('set_view',{sort:'asc'}));await assert.rejects(f.session.confirm('wrong'));
 await f.session.confirm(p.proposal_id);assert.equal(f.snapshot().analysis.population.length,1);assert.ok(f.session.audit[0].diff.analysis);
 await f.session.undo();assert.deepEqual(f.snapshot(),before);
});
test('stale proposal and concurrent dispatch fail closed',async()=>{
 const f=fixture(),p=await f.session.dispatch('propose_analysis_subset',{patients:[f.roster[0][1]]});const changed=f.snapshot();changed.display.sort='desc';f.external(changed);
 await assert.rejects(f.session.confirm(p.proposal_id),/expired|changed/);assert.deepEqual(f.snapshot(),changed);
 const g=fixture();const a=g.session.dispatch('query_data',{scope:'current_analysis',unit:'patients',filters:{}});
 await assert.rejects(g.session.dispatch('set_view',{sort:'asc'}),/flight|busy/);await a;
});
test('unsupported alignments and clarification leave state unchanged; local task exists after reset',async()=>{
 const f=fixture(),before=f.snapshot();const r=await f.session.dispatch('set_alignment',{anchor:'randomization'});
 assert.equal(r.anchor,'randomization');assert.ok(r.missing_anchor_handling);assert.equal(r.status,'unsupported');
 await f.session.dispatch('clarify_request',{question:'Which unit and anchor?'});assert.deepEqual(f.snapshot(),before);assert.equal(f.session.audit.length,0);
 const task=await f.session.dispatch('propose_development_task',{description:'Add audited randomization support'});
 assert.equal(task.result_created,false);assert.equal(task.task.status,'proposed');assert.equal(f.session.tasks[0].id,task.task.id);assert.equal(f.session.audit[0].action.args.task.id,task.task.id);
 await f.session.reset();assert.equal(f.session.tasks[0].id,task.task.id);assert.deepEqual(f.snapshot(),before);
});
