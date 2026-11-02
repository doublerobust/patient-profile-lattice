'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {ToolSession,names}=require('./static/tool-registry.js');
const core=require('./static/state-core.js');
const spec=require('./data/normalized_spec.json');
const copy=x=>structuredClone(x);

// Deliberately synthetic bridge responses: these test dispatch, not cohort facts.
function fixture(renderer='timeline',selection=null) {
  let state={analysis:copy(spec.analysis_state),display:{view:copy(spec.view_state),sort:'duration',tier:'auto',renderer,camera:renderer==='timeline'?{start:0,end:100}:{x:0,y:0,z:0,yaw:0,pitch:0,distance:50,span:25},alignment:null,highlights:[]}};
  state.display.view.selection=copy(selection);
  const roster=copy(state.analysis.population), calls=[], commits=[];
  let dataset='synthetic', override, commitError=false;
  const bridge={snapshot:()=>copy(state),roster:()=>copy(roster),dataset:()=>dataset,records:()=>['AE-test-1'],
    apply:async next=>{if(commitError)throw new Error('synthetic commit failure');commits.push(copy(next));state=copy(next);},
    resolve:async(tool,args)=>{
      calls.push({tool,args:copy(args)});
      if(override)return copy(override);
      if(tool==='get_capabilities')return {status:'read_only',tools:[...names],record_ids:[]};
      if(tool==='set_alignment') {
        if(args.anchor!=='first_PR')return {status:'unsupported',anchor:args.anchor,denominator:roster.length,denominator_unit:'synthetic roster patients',missing_anchor_handling:'No transform, exclusions or imputation.',record_ids:[]};
        return {status:'resolved',anchor:'first_PR',axis_label:'Days since recorded PR',definition:'Synthetic recorded PR at RSDTC',convention:'Elapsed days',denominator:roster.length,denominator_unit:'synthetic roster patients',counts:{resolved:1,no_qualifying_event:roster.length-1,event_date_unresolved:0},patients:roster.map((p,i)=>({patient_key:p,status:i?'no_qualifying_event':'resolved',date:i?null:'2025-01-10',record_ids:i?[]:['RS-test-1']})),record_ids:['RS-test-1'],missing_anchor_handling:'Keep unresolved patients unaligned; never impute.',note:'Synthetic display-only resolution'};
      }
      if(tool==='propose_analysis_subset') {
        const population=state.analysis.population.filter(p=>args.patients.includes(p[1]));
        const view=copy(state.display.view);view.selection=null;
        return {status:'confirmation_required',population,view_state:view,before:{patients:state.analysis.population.length,'AE records':2},after:{patients:population.length,'AE records':1},record_ids:['AE-test-1']};
      }
      return {count:1,unit:args.unit||'AE records',record_ids:['AE-test-1'],linked_record_ids:['CM-test-1']};
    }};
  return {session:new ToolSession(bridge),roster,calls,commits,snapshot:()=>copy(state),override:r=>{override=r;},changeDataset:()=>{dataset='other';},failCommit:()=>{commitError=true;}};
}

const invalidCalls=[
  ['eval',{code:'globalThis.modelRan=true'}],['constructor',{}],['confirm_analysis_subset',{}],
  ['set_view',{}],['set_view',{sort:'best prognosis'}],['set_view',{tier:2}],
  ['set_view',{layers:['AE','AE']}],['set_view',{subset:[]}],['set_view',{focus:'not-in-roster'}],
  ['set_view',{camera:{start:NaN,end:10}}],['set_view',{camera:{start:5,end:5}}],
  ['query_data',{scope:'current_analysis',filters:{}}],
  ['query_data',{scope:'visible',unit:'patients',filters:{}}],
  ['query_data',{scope:'current_analysis',unit:'patients',filters:{caused_by:'drug'}}],
  ['highlight_events',{scope:'current_analysis',filters:{grade:true}}],
  ['highlight_events',{scope:'current_analysis',filters:{record_ids:['AE-test-1','AE-test-1']}}],
  ['highlight_events',{scope:'current_analysis',filters:{date_window:{anchor:'AESTDTC',start:'2025-02-30',end:'2025-03-01'}}}],
  ['propose_analysis_subset',{patients:[]}],['propose_development_task',{description:''}],
  ['clarify_request',{question:'Which anchor?',execute:true}],['get_view_state',{code:'alert(1)'}]
];
test('AC1/4: invalid, ambiguous and inferential calls fail closed before resolver or commit',async t=>{
  for(const [tool,args] of invalidCalls)await t.test(tool+' '+JSON.stringify(args),async()=>{
    const f=fixture(),before=f.snapshot();
    await assert.rejects(f.session.dispatch(tool,args),TypeError);
    assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.calls,[]);assert.deepEqual(f.commits,[]);assert.deepEqual(f.session.audit,[]);
  });
});

test('AC1/5: functions, getters, cycles, sparse arrays and prototype keys are never executed',async()=>{
  let invoked=0;const getter={};Object.defineProperty(getter,'sort',{enumerable:true,get(){invoked++;return 'asc';}});
  const cyclic={};cyclic.sort=cyclic;
  const bad=[getter,cyclic,{sort:()=>invoked++},{layers:new Array(1)},JSON.parse('{"__proto__":{"sort":"asc"}}'),{camera:{start:0,end:Infinity}}];
  for(const args of bad){const f=fixture();await assert.rejects(f.session.dispatch('set_view',args),TypeError);assert.deepEqual(f.calls,[]);assert.deepEqual(f.session.audit,[]);}
  assert.equal(invoked,0);
});

test('AC2/9: proposal discloses consequences; only matching out-of-band confirmation applies combined diff',async()=>{
  const f=fixture('timeline',{mark_id:'excluded-test-mark',source_record_ids:['AE-test-excluded']});
  await f.session.dispatch('highlight_events',{scope:'current_analysis',filters:{}});
  const before=f.snapshot(),historyBefore=f.session.audit;
  const p=await f.session.dispatch('propose_analysis_subset',{patients:[f.roster[0][1]]});
  assert.equal(p.status,'confirmation_required');assert.deepEqual(p.before,{patients:before.analysis.population.length,'AE records':2});assert.deepEqual(p.after,{patients:1,'AE records':1});
  assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.session.audit,historyBefore);
  await assert.rejects(f.session.confirm(),/confirmation/);await assert.rejects(f.session.confirm('wrong'),/confirmation/);
  await assert.rejects(f.session.dispatch('confirm_analysis_subset',{proposal_id:p.proposal_id}),/Unsupported tool/);
  await assert.rejects(f.session.dispatch('set_view',{sort:'asc'}),/pending/);
  assert.deepEqual(f.snapshot(),before);
  assert.equal((await f.session.confirm(p.proposal_id)).status,'executed_after_user_confirmation');
  assert.deepEqual(f.snapshot().analysis.population,[f.roster[0]]);
  const entry=f.session.audit.at(-1);assert.deepEqual(entry.record_ids,['AE-test-1']);assert.deepEqual(entry.diff.analysis.before,before.analysis);
  assert.deepEqual(Object.keys(entry.diff).sort(),['analysis','display']);assert.equal(f.snapshot().display.view.selection,null);
  await f.session.undo();assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.session.audit,historyBefore);
});

test('AC2: cancelled and dataset-stale proposals cannot commit',async()=>{
  for(const stale of [false,true]){
    const f=fixture(),before=f.snapshot(),p=await f.session.dispatch('propose_analysis_subset',{patients:[f.roster[0][1]]});
    if(stale)f.changeDataset();else f.session.cancel();
    await assert.rejects(f.session.confirm(p.proposal_id),/confirmation|expired|changed/);
    assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.commits,[]);assert.deepEqual(f.session.audit,[]);
  }
});

test('AC3/4: unsupported anchors, resolver refusals and clarification return unchanged state and history',async()=>{
  const f=fixture('lattice'),before=f.snapshot();
  const r=await f.session.dispatch('set_alignment',{anchor:'randomization'});
  assert.equal(r.status,'unsupported');assert.equal(r.anchor,'randomization');assert.equal(r.denominator,f.roster.length);assert.match(r.missing_anchor_handling,/No transform.*imputation/);
  for(const status of ['refused','clarification_required']){
    f.override({status,note:'No causal inference; specify a source filter.',record_ids:[]});
    assert.equal((await f.session.dispatch('query_data',{scope:'current_analysis',unit:'patients',filters:{}})).status,status);
  }
  assert.equal((await f.session.dispatch('clarify_request',{question:'Which unit and anchor?'})).status,'clarification_required');
  assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.session.audit,[]);assert.deepEqual(f.commits,[]);
});

test('AC6: both counting units retain contributing and linked IDs; invalid resolver counts cannot enter history',async()=>{
  for(const unit of ['patients','AE records']){
    const f=fixture(),before=f.snapshot(),r=await f.session.dispatch('query_data',{scope:'current_analysis',unit,filters:{record_ids:['AE-test-1']}});
    assert.equal(r.unit,unit);assert.equal(r.count,1);assert.deepEqual(r.record_ids,['AE-test-1']);assert.deepEqual(f.snapshot(),before);
    assert.deepEqual(f.session.audit[0].record_ids,r.record_ids);assert.deepEqual(f.session.audit[0].linked_record_ids,['CM-test-1']);assert.deepEqual(f.session.audit[0].diff,{});
  }
  for(const result of [{count:2,unit:'AE records',record_ids:['AE-test-1']},{count:1,unit:'patients',record_ids:['AE-test-1']},{count:1,unit:'AE records',record_ids:['AE-test-1','AE-test-1']}]){
    const f=fixture(),before=f.snapshot();f.override(result);
    await assert.rejects(f.session.dispatch('query_data',{scope:'current_analysis',unit:'AE records',filters:{}}),/source|count/);
    assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.session.audit,[]);
  }
});

test('AC7: development requests create real local ledger entries, not results; Undo/Reset do not erase tasks',async()=>{
  const f=fixture(),before=f.snapshot(),description='globalThis.modelRan = true; <script>throw Error()</script>';
  const a=await f.session.dispatch('propose_development_task',{description});
  const b=await f.session.dispatch('propose_development_task',{description:'Implement unsupported randomization alignment'});
  assert.notEqual(a.task.id,b.task.id);assert.deepEqual(f.session.tasks,[a.task,b.task]);
  for(const result of [a,b]){assert.equal(result.result_created,false);assert.equal(result.task.result_created,false);assert.equal(result.task.status,'proposed');assert.match(result.task.scope,/local session.*not an external ticket/);assert.match(result.note,/No clinical result/);}
  assert.equal(a.task.description,description);assert.deepEqual(f.calls,[]);assert.deepEqual(f.snapshot(),before);
  await f.session.undo();await f.session.reset();assert.deepEqual(f.session.tasks,[a.task,b.task]);assert.deepEqual(f.snapshot(),before);assert.equal(globalThis.modelRan,undefined);
});

test('AC8/9: every executed registered tool has replayable diff, IDs and Undo/Reset; reverse restores each exact state',async()=>{
  const f=fixture('lattice'),states=[];
  const calls=[['get_capabilities',{}],['get_view_state',{}],['set_view',{sort:'asc',subset:[f.roster[0][1]],layers:['AE'],tier:'2',camera:{position:[20,30,40],target:[1,2,3],span:40}}],['set_alignment',{anchor:'first_PR'}],['highlight_events',{scope:'current_analysis',filters:{record_ids:['AE-test-1']}}],['query_data',{scope:'current_analysis',unit:'AE records',filters:{}}],['propose_development_task',{description:'Add audited anchor'}],['propose_analysis_subset',{patients:[f.roster[0][1]]}]];
  assert.deepEqual(new Set(calls.map(c=>c[0]).concat('clarify_request')),new Set(names));
  for(const [tool,args] of calls){
    const before=f.snapshot();states.push(before);const result=await f.session.dispatch(tool,args);
    if(tool==='propose_analysis_subset')await f.session.confirm(result.proposal_id);
    const entry=f.session.audit.at(-1);
    assert.equal(f.session.audit.length,states.length);assert.equal(entry.action.tool,tool==='propose_analysis_subset'?'confirm_analysis_subset':tool);
    assert.deepEqual(entry.record_ids,result.record_ids);assert.deepEqual(core.applyDiff(before,entry.diff),f.snapshot());assert.deepEqual(core.revertDiff(f.snapshot(),entry.diff),before);
    assert.equal(entry.controls.undo.entry_id,entry.id);assert.equal(entry.controls.reset.target,'initial');
  }
  while(states.length){await f.session.undo();assert.deepEqual(f.snapshot(),states.pop());}
  assert.deepEqual(f.session.audit,[]);
});

test('AC8: failed bridge commit adds neither state nor history and releases dispatch lock',async()=>{
  const f=fixture(),before=f.snapshot();f.failCommit();
  await assert.rejects(f.session.dispatch('set_view',{sort:'asc'}),/synthetic commit failure/);
  assert.deepEqual(f.snapshot(),before);assert.deepEqual(f.session.audit,[]);assert.equal(f.session.busy,false);
  await f.session.dispatch('get_view_state',{});assert.equal(f.session.audit.length,1);
});

test('AC5: all registered paths run with DOM access trapped and string code generation disabled',async()=>{
  const context=vm.createContext({nativeClone:structuredClone,specText:JSON.stringify(spec)},{codeGeneration:{strings:false,wasm:false}});
  // Only trusted checked-in module/test source is compiled here; model text is data.
  // Re-home native cloned JSON into the VM realm (host prototypes are rightly rejected).
  vm.runInContext(`globalThis.structuredClone=x=>JSON.parse(JSON.stringify(nativeClone(x)));
    globalThis.domTouches=0; globalThis.codeTouches=0;
    for(const key of ['document','window','HTMLElement','Element']) Object.defineProperty(globalThis,key,{get(){domTouches++;throw Error('DOM access');}});
    for(const key of ['eval','Function','setTimeout','setInterval']) globalThis[key]=()=>{codeTouches++;throw Error('Code execution');};`,context);
  for(const file of ['state-core','action-history','tool-registry'])vm.runInContext(fs.readFileSync(require.resolve('./static/'+file+'.js'),'utf8'),context,{filename:file+'.js'});
  await vm.runInContext(`(async()=>{
    const copy=x=>JSON.parse(JSON.stringify(x)), spec=JSON.parse(specText), ToolSession=ViewTools.ToolSession, names=ViewTools.names;
    const fixture=${fixture.toString()};
    const f=fixture('lattice');
    const payload='globalThis.modelRan=true; document.body.innerHTML="unsafe"';
    const calls=[['get_capabilities',{}],['get_view_state',{}],['set_view',{sort:'asc'}],['set_alignment',{anchor:'first_PR'}],['set_alignment',{anchor:'randomization'}],['highlight_events',{scope:'current_analysis',filters:{}}],['query_data',{scope:'current_analysis',unit:'patients',filters:{}}],['propose_development_task',{description:payload}],['clarify_request',{question:payload}]];
    for(const [tool,args] of calls)await f.session.dispatch(tool,args);
    const p=await f.session.dispatch('propose_analysis_subset',{patients:[f.roster[0][1]]});await f.session.confirm(p.proposal_id);
    await f.session.undo();await f.session.reset();
  })()`,context);
  assert.equal(context.domTouches,0);assert.equal(context.codeTouches,0);assert.equal(context.modelRan,undefined);
});
