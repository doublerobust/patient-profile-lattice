/* Structured-data boundary only: no DOM, code evaluation, or model confirmation tool. */
'use strict';
(function(root){
  const core=typeof module!=='undefined'&&module.exports?require('./state-core.js'):root.ViewStateCore;
  const historyAPI=typeof module!=='undefined'&&module.exports?require('./action-history.js'):root.ViewActionHistory;
  const copy=x=>structuredClone(x), equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const names=Object.freeze(['get_capabilities','get_view_state','set_view','set_alignment','highlight_events','query_data','propose_analysis_subset','propose_development_task','clarify_request']);
  const fail=m=>{throw new TypeError(m);};
  // Inspect descriptors before values: getters, prototypes, cycles and sparse arrays are not JSON.
  function json(v,seen=new Set()){
    if(v===null||['string','boolean'].includes(typeof v)||typeof v==='number'&&Number.isFinite(v))return;
    if(!v||typeof v!=='object'||seen.has(v))fail('Only finite, acyclic JSON data is allowed.');
    const array=Array.isArray(v);
    if(!array&&![Object.prototype,null].includes(Object.getPrototypeOf(v)))fail('Use plain JSON objects.');
    if(array&&(Reflect.ownKeys(v).length!==v.length+1||!Array.from({length:v.length},(_,i)=>Object.hasOwn(v,String(i))).every(Boolean)))fail('Use dense JSON arrays.');
    seen.add(v);
    for(const k of Reflect.ownKeys(v)){
      if(array&&k==='length')continue;
      if(typeof k!=='string'||['__proto__','prototype','constructor'].includes(k))fail('Unsafe argument field.');
      const d=Object.getOwnPropertyDescriptor(v,k);
      if(!Object.hasOwn(d,'value')||!d.enumerable)fail('Executable/accessor arguments are forbidden.');
      json(d.value,seen);
    }
    seen.delete(v);
  }
  function keys(v,allowed,required=[]){if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!allowed.includes(k))||required.some(k=>!Object.hasOwn(v,k)))fail('Unsupported fields or ambiguous arguments; specify the documented fields.');}
  const text=s=>typeof s==='string'&&s.trim().length>0;
  const unique=(a,check)=>Array.isArray(a)&&new Set(a).size===a.length&&a.every(check);
  const date=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(d).toISOString().slice(0,10)===d;
  function filters(f){
    keys(f,['term','grade','patient','linked_cm','date_window','record_ids']);
    for(const k of ['term','patient','linked_cm'])if(k in f&&!text(f[k]))fail('Choose an exact nonempty source value.');
    if('grade' in f&&(!Number.isInteger(f.grade)||f.grade<1||f.grade>5))fail('Grade must be integer 1–5, not inferred severity.');
    if('record_ids' in f&&!unique(f.record_ids,text))fail('Choose unique source record IDs.');
    if('date_window' in f){const w=f.date_window;keys(w,['anchor','start','end'],['anchor','start','end']);if(w.anchor!=='AESTDTC'||!date(w.start)||!date(w.end)||w.end<w.start)fail('Use explicit inclusive AESTDTC calendar dates; relative analytical windows require development.');}
  }
  function validateCall(name,args,{roster=[],renderer='timeline'}={}){
    if(!names.includes(name))fail('Unsupported tool; development task required. No model code is executed.');
    json(args);
    if(['get_capabilities','get_view_state'].includes(name))keys(args,[]);
    if(name==='set_view'){
      keys(args,['sort','focus','subset','layers','tier','camera']);
      if(!Object.keys(args).length)fail('Which view property should change?');
      if('sort' in args&&!['duration','asc','desc','response','pd','reason'].includes(args.sort))fail('Unsupported sort order.');
      if('tier' in args&&!['auto','0','1','2'].includes(args.tier))fail('Choose tier auto, 0, 1 or 2.');
      const patient=id=>typeof id==='string'&&roster.filter(p=>p[1]===id).length===1;
      if('focus' in args&&args.focus!==null&&!patient(args.focus))fail('Choose one unambiguous roster patient ID, or null for all.');
      if('subset' in args&&('focus' in args||!unique(args.subset,patient)||!args.subset.length))fail('Choose explicit unique display subset IDs without focus; focus:null restores all.');
      if('layers' in args&&!unique(args.layers,l=>['AE','CM','EX','RS'].includes(l)))fail('Choose unique visible layers AE/CM/EX/RS.');
      if('camera' in args){const c=args.camera;
        if(renderer==='timeline'){keys(c,['start','end'],['start','end']);if(![c.start,c.end].every(n=>typeof n==='number'&&Math.abs(n)<=8e15)||c.end<=c.start)fail('Timeline camera needs finite ordered UTC epoch start/end.');}
        else {keys(c,['position','target','span'],['position','target','span']);if(![c.position,c.target].every(v=>Array.isArray(v)&&v.length===3&&v.every(n=>typeof n==='number'&&Math.abs(n)<1e6))||typeof c.span!=='number'||c.span<8||c.span>100000)fail('Supply position, target and span (8–100000).');
          const d=c.position.map((v,i)=>v-c.target[i]),distance=Math.hypot(...d);if(distance<1||distance>10000||Math.hypot(d[0],d[2])<.001)fail('Camera direction must be nonvertical, distance 1–10000.');}
      }
    }
    if(name==='set_alignment'){keys(args,['anchor'],['anchor']);if(!text(args.anchor))fail('Name an explicit alignment anchor.');}
    if(['query_data','highlight_events'].includes(name)){
      keys(args,name==='query_data'?['scope','unit','filters','include_records']:['scope','filters'],name==='query_data'?['scope','unit','filters']:['scope','filters']);
      if(args.scope!=='current_analysis'||name==='query_data'&&!['patients','AE records'].includes(args.unit))fail('Specify current_analysis and an explicit counting unit: patients or AE records.');
      if('include_records' in args&&typeof args.include_records!=='boolean')fail('include_records must be boolean.');filters(args.filters);
    }
    if(name==='propose_analysis_subset'){keys(args,['patients'],['patients']);if(!unique(args.patients,text)||!args.patients.length||args.patients.some(id=>roster.filter(p=>p[1]===id).length!==1))fail('Choose explicit unique unambiguous patient IDs.');}
    for(const [tool,key] of [['propose_development_task','description'],['clarify_request','question']])if(name===tool){keys(args,[key],[key]);if(!text(args[key])||args[key].length>1000)fail('Provide nonempty text of at most 1000 characters.');}
  }
  function planView(display,args,roster){
    validateCall('set_view',args,{roster,renderer:display.renderer});const next=copy(display);
    for(const k of ['sort','tier'])if(k in args)next[k]=args[k];
    if('focus' in args)next.view.focus_patient_keys=args.focus===null?[]:copy(roster.filter(p=>p[1]===args.focus));
    if('subset' in args)next.view.focus_patient_keys=copy(roster.filter(p=>args.subset.includes(p[1])));
    if('layers' in args)next.view.hidden_lanes=['AE','CM','EX','RS'].filter(l=>!args.layers.includes(l));
    if(args.camera){const c=args.camera;if(display.renderer==='timeline')next.camera=copy(c);else {const d=c.position.map((v,i)=>v-c.target[i]),distance=Math.hypot(...d);next.camera={...next.camera,x:c.target[0],y:c.target[1],z:c.target[2],yaw:Math.atan2(d[0],d[2]),pitch:Math.asin(d[1]/distance),distance,span:c.span};}}
    return next;
  }
  class ToolSession {
    constructor(bridge){this.bridge=bridge;this.tasks=[];this.serial=0;this.busy=false;this.pending=null;this.dataset=bridge.dataset?.();this.history=historyAPI.createHistory({initial:bridge.snapshot(),commit:async(next,{previous})=>{this.assertCurrent(previous);if(!equal(previous,next))await bridge.apply(copy(next));}});}
    get audit(){return this.history.snapshot().entries;}
    get stack(){return this.audit;}
    get initial(){return this.history.snapshot().state;}
    snapshot(){return core.createState(this.bridge.snapshot());}
    assertCurrent(before){if(this.dataset!==this.bridge.dataset?.()||!equal(before,this.snapshot()))fail('State or dataset changed; proposal/request expired.');}
    clear(){if(this.busy)fail('Request in flight.');this.history.replaceSession(this.bridge.snapshot());this.dataset=this.bridge.dataset?.();this.pending=null;}
    async exclusive(work){if(this.busy)fail('Request in flight; wait before another action.');this.busy=true;try{return await work();}finally{this.busy=false;}}
    async dispatch(tool,args,{recordEgress=false}={}){return this.exclusive(async()=>{
      const before=this.snapshot();this.assertCurrent(this.history.snapshot().state);
      validateCall(tool,args,{roster:this.bridge.roster(),renderer:before.display.renderer});args=copy(args);
      if(this.pending)fail('Confirm or cancel the pending analysis proposal first.');
      let next=copy(before),result,task;
      if(tool==='set_view'){next.display=planView(before.display,args,this.bridge.roster());result={status:'executed',note:'View changed; analysis unchanged.',record_ids:this.bridge.records()};}
      else if(tool==='get_view_state')result={status:'read_only',view:copy(before.display),analysis:copy(before.analysis),record_ids:this.bridge.records()};
      else if(tool==='clarify_request')return {status:'clarification_required',note:args.question,record_ids:[]};
      else if(tool==='propose_development_task'){
        task={id:'development-'+(++this.serial),description:args.description,status:'proposed',result_created:false,scope:'local session task; not an external ticket; retained across Undo/Reset'};
        result={status:'development_proposal',result_created:false,task,record_ids:[],note:'Development task created in the local session ledger. No clinical result, implementation or external ticket created.'};
      }else result=await this.bridge.resolve(tool,args,recordEgress);
      json(result);this.assertCurrent(before);
      if(['unsupported','refused','clarification_required'].includes(result.status))return copy(result);
      if(tool==='set_alignment'){
        if(result.status!=='resolved')fail('Alignment did not resolve; nothing changed.');
        if(before.display.renderer!=='lattice')return {...result,status:'unsupported',note:'Display alignment '+args.anchor+' is supported on /lattice only. No transform applied; no dates imputed. Development required for this renderer.'};
        next.display.alignment=result.anchor==='calendar'?null:copy(result);
      }
      if(['query_data','highlight_events'].includes(tool)){
        if(!Number.isInteger(result.count)||result.count<0||result.unit!==(tool==='query_data'?args.unit:'AE records')||!unique(result.record_ids,text)||!unique(result.linked_record_ids||[],text))fail('Invalid source query result.');
        if(result.unit==='AE records'&&result.count!==result.record_ids.length)fail('Query count disagrees with source IDs.');
        if(tool==='highlight_events')next.display.highlights=copy(result.record_ids);
      }
      if(tool==='propose_analysis_subset'){
        const population=before.analysis.population.filter(p=>args.patients.includes(p[1]));
        if(result.status!=='confirmation_required'||population.length!==args.patients.length||!equal(population,result.population)||!result.before||!result.after)fail('Analysis tool must return the exact subset and proposed count consequences.');
        next.analysis.population=copy(population);
        next.display.highlights=next.display.highlights.filter(id=>result.record_ids.includes(id));
        if(result.view_state)next.display.view=copy(result.view_state);
        core.validateState(next);
        result={...result,proposal_id:'proposal-'+(++this.serial)};
        this.pending={id:result.proposal_id,before:copy(before),next:copy(next),args,result:copy(result)};
        return copy(result);
      }
      const diff=core.stateDiff(before,next);if(diff.analysis)fail('Analysis changes require explicit user confirmation.');
      await this.history.execute({action:{tool,args:task?{...args,task}:args},diff,record_ids:result.record_ids||[],linked_record_ids:result.linked_record_ids||[]});
      if(task)this.tasks.push(copy(task));return copy(result);
    });}
    async confirm(id){return this.exclusive(async()=>{
      const p=this.pending;if(!p||p.id!==id)fail('Explicit matching user confirmation required.');this.assertCurrent(p.before);
      await this.history.execute({action:{tool:'confirm_analysis_subset',args:{proposal_id:id,patients:p.args.patients}},diff:core.stateDiff(p.before,p.next),record_ids:p.result.record_ids||[]});
      this.pending=null;return {status:'executed_after_user_confirmation',record_ids:copy(p.result.record_ids||[])};
    });}
    cancel(){if(this.busy)fail('Request in flight.');this.pending=null;}
    async undo(){return this.exclusive(async()=>{this.assertCurrent(this.history.snapshot().state);await this.history.undo();this.pending=null;return {record_ids:copy(this.snapshot().display.highlights)};});}
    async reset(){return this.exclusive(async()=>{this.assertCurrent(this.history.snapshot().state);await this.history.reset();this.pending=null;return {record_ids:copy(this.snapshot().display.highlights)};});}
  }
  const api=Object.freeze({ToolSession,validateCall,planView,stateDiff:core.stateDiff,names});
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ViewTools=api;
})(globalThis);
