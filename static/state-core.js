/* Pure, synchronous state boundary. No DOM, I/O, callbacks or code evaluation.
 * Model intents belong in tool handlers; this module accepts validated data only.
 * Runtime contract and integration notes: docs/state-core.md.
 */
'use strict';
(function(root) {
  const fail = message => { throw new TypeError(message); };
  const domains = ['analysis', 'display'];
  const lanes = ['AE','CM','EX','RS','RELREC','SUPPAE'];
  const sorts = ['duration','asc','desc','response','pd','reason'];
  const temporal = {anchor_domain:'EX',anchor_variable:'EXSTDTC',anchor_occurrence:'first',event_variable:'AESTDTC',direction:'after',lower_days:0,upper_days:30,lower_inclusive:true,upper_inclusive:true,date_policy:'exclude_incomplete_with_diagnostic',missing_anchor_policy:'exclude_patient_with_diagnostic'};

  // Inspect descriptors before reading values: even a getter is not state data.
  function json(value, ancestors=new Set()) {
    if(value===null || typeof value==='string' || typeof value==='boolean')return;
    if(typeof value==='number' && Number.isFinite(value))return;
    if(!value || typeof value!=='object')fail('State must contain finite JSON data only.');
    if(ancestors.has(value))fail('Cyclic state is not JSON.');
    const array=Array.isArray(value), proto=Object.getPrototypeOf(value);
    if(!array && proto!==Object.prototype && proto!==null)fail('State objects must be plain records.');
    const keys=Reflect.ownKeys(value);
    if(array && (keys.length!==value.length+1 || !Array.from({length:value.length},(_,i)=>Object.hasOwn(value,String(i))).every(Boolean)))fail('Arrays must be dense with no extra fields.');
    ancestors.add(value);
    for(const key of keys) {
      if(array && key==='length')continue;
      if(typeof key!=='string' || ['__proto__','constructor','prototype'].includes(key))fail('Unsafe state field.');
      const d=Object.getOwnPropertyDescriptor(value,key);
      if(!Object.hasOwn(d,'value') || !d.enumerable)fail('Only enumerable data fields are accepted.');
      json(d.value,ancestors);
    }
    ancestors.delete(value);
  }
  function fields(value,allowed,required=allowed) {
    if(!value || typeof value!=='object' || Array.isArray(value) || Object.keys(value).some(k=>!allowed.includes(k)) || required.some(k=>!Object.hasOwn(value,k)))fail('Missing or unsupported state fields: '+allowed.join(', '));
  }
  function equal(a,b) {
    if(Object.is(a,b))return true;
    if(!a || !b || typeof a!=='object' || typeof b!=='object' || Array.isArray(a)!==Array.isArray(b))return false;
    const keys=Object.keys(a);
    return keys.length===Object.keys(b).length && keys.every(k=>Object.hasOwn(b,k)&&equal(a[k],b[k]));
  }
  function copy(value) {
    if(Array.isArray(value))return value.map(copy);
    if(value && typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,copy(v)]));
    return value;
  }
  function freeze(value) {
    if(value && typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}
    return value;
  }
  const snapshot = value => freeze(copy(value));
  const text = s => typeof s==='string' && s.trim().length>0;
  function list(value,check) {
    if(!Array.isArray(value) || !value.every(check) || new Set(value.map(v=>JSON.stringify(v))).size!==value.length)fail('Expected unique valid state values.');
  }
  function patient(p){return Array.isArray(p)&&p.length===2&&p.every(text);}
  function date(d) {
    return typeof d==='string' && /^\d{4}-\d{2}-\d{2}$/.test(d) && Number.isFinite(Date.parse(d)) && new Date(d).toISOString().slice(0,10)===d;
  }
  function analysis(a) {
    fields(a,['population','ae_predicate','temporal_window']);
    list(a.population,patient);
    if(a.ae_predicate!==null) {
      fields(a.ae_predicate,['variable','operator','value']);
      if(a.ae_predicate.variable!=='AESEV' || a.ae_predicate.operator!=='eq' || !['MILD','MODERATE','SEVERE'].includes(a.ae_predicate.value))fail('Unsupported analysis predicate.');
    }
    if(a.temporal_window!==null && !equal(a.temporal_window,temporal))fail('Unsupported temporal analysis; no anchor inference or imputation.');
  }
  function view(v) {
    fields(v,['patient_sort','hidden_lanes','focus_patient_keys','display_date_window','selection']);
    if(!Array.isArray(v.patient_sort)||v.patient_sort.length!==1)fail('One patient sort is required.');
    fields(v.patient_sort[0],['field','direction']);
    if(v.patient_sort[0].field!=='USUBJID'||!['asc','desc'].includes(v.patient_sort[0].direction))fail('Unsupported patient sort.');
    list(v.hidden_lanes,l=>lanes.includes(l));list(v.focus_patient_keys,patient);
    if(v.display_date_window!==null) {
      fields(v.display_date_window,['start','end']);
      const {start,end}=v.display_date_window;
      if(!date(start)||!date(end)||end<start)fail('Invalid display date window.');
    }
    if(v.selection!==null) {
      fields(v.selection,['mark_id','source_record_ids']);
      if(!text(v.selection.mark_id))fail('Selection needs a mark ID.');
      list(v.selection.source_record_ids,text);
      if(!v.selection.source_record_ids.length)fail('Selection needs source record IDs.');
    }
  }
  function alignment(a) {
    if(a===null)return;
    fields(a,['status','anchor','axis_label','definition','convention','denominator','denominator_unit','counts','patients','record_ids','missing_anchor_handling','note']);
    if(!['resolved','executed'].includes(a.status) || !['first_treatment','first_PR','first_PD','death'].includes(a.anchor))fail('Unsupported resolved display alignment.');
    for(const key of ['axis_label','definition','convention','denominator_unit','missing_anchor_handling','note'])if(!text(a[key]))fail('Alignment disclosure is required.');
    if(!Number.isInteger(a.denominator)||a.denominator<0||!Array.isArray(a.patients)||a.patients.length!==a.denominator)fail('Invalid alignment denominator.');
    const statuses=['resolved','no_qualifying_event','event_date_unresolved'];
    fields(a.counts,statuses);const counts=Object.fromEntries(statuses.map(k=>[k,0]));
    const keys=[], records=new Set();
    for(const p of a.patients) {
      fields(p,['patient_key','status','date','record_ids']);
      if(!patient(p.patient_key)||!statuses.includes(p.status))fail('Invalid aligned patient.');
      if(p.status==='resolved'?!date(p.date):p.date!==null)fail('Unresolved anchors must retain null dates.');
      list(p.record_ids,text);
      if(p.status==='resolved'&&!p.record_ids.length)fail('Resolved anchor requires source records.');
      keys.push(p.patient_key);p.record_ids.forEach(id=>records.add(id));counts[p.status]++;
    }
    list(keys,patient);list(a.record_ids,text);
    if(!equal(counts,a.counts)||a.record_ids.length!==records.size||!a.record_ids.every(id=>records.has(id)))fail('Alignment counts/record IDs disagree.');
  }
  function display(d) {
    fields(d,['view','sort','tier','renderer','camera','alignment','highlights']);
    view(d.view);list(d.highlights,text);
    if(!sorts.includes(d.sort)||!['auto','0','1','2'].includes(d.tier)||!['timeline','3d','lattice'].includes(d.renderer))fail('Unsupported display mode.');
    // null is the pre-initialization camera, not an invented default viewport.
    if(d.camera!==null) {
      if(d.renderer==='timeline') {
        fields(d.camera,['start','end']);
        if(![d.camera.start,d.camera.end].every(n=>typeof n==='number'&&Math.abs(n)<=8e15)||d.camera.end<=d.camera.start)fail('Invalid timeline camera.');
      } else {
        const required=['x','y','z','yaw','pitch','distance','span'];
        fields(d.camera,d.renderer==='3d'?[...required,'peel']:required,required);
        if(!Object.values(d.camera).every(n=>typeof n==='number')||d.camera.distance<=0||d.camera.span<=0)fail('Invalid spatial camera.');
      }
    }
    if(d.alignment!==null && d.renderer!=='lattice')fail('Alignment is supported only by the lattice renderer.');
    alignment(d.alignment);
  }
  function validateState(state) {
    json(state);fields(state,domains);analysis(state.analysis);display(state.display);
    return state;
  }
  function createState(state){validateState(state);return snapshot(state);}
  function validateDiff(diff) {
    json(diff);fields(diff,domains,[]);
    for(const domain of Object.keys(diff)) {
      fields(diff[domain],['before','after']);
      const validate=domain==='analysis'?analysis:display;
      validate(diff[domain].before);validate(diff[domain].after);
    }
    return diff;
  }
  function stateDiff(before,after) {
    validateState(before);validateState(after);const diff={};
    for(const domain of domains)if(!equal(before[domain],after[domain]))diff[domain]={before:before[domain],after:after[domain]};
    return snapshot(diff);
  }
  function transition(state,diff,from,to) {
    validateState(state);validateDiff(diff);
    // Check every touched domain BEFORE constructing any result: atomic on conflict.
    for(const domain of Object.keys(diff))if(!equal(state[domain],diff[domain][from]))fail('State conflict in '+domain+'; refresh or undo in order.');
    const next={...state};
    for(const domain of Object.keys(diff))next[domain]=diff[domain][to];
    return createState(next);
  }
  const applyDiff=(state,diff)=>transition(state,diff,'before','after');
  const revertDiff=(state,diff)=>transition(state,diff,'after','before');
  const resetState=(state,initial)=>applyDiff(state,stateDiff(state,initial));
  const api=Object.freeze({createState,validateState,validateDiff,stateDiff,applyDiff,revertDiff,resetState});
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.ViewStateCore=api;
})(globalThis);
