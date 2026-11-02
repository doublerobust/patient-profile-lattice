/* Action history v1. Tool handlers provide data; this module owns transitions/UI.
 * Renderer commit must be atomic (or roll back itself on rejection). See docs.
 */
'use strict';
(function(root) {
  const core=typeof module==='object' && module.exports ? require('./state-core.js') : root.ViewStateCore;
  const fail=message=>{throw new TypeError(message);};
  function data(value, ancestors=new Set()) {
    if(value===null || typeof value==='string' || typeof value==='boolean' || (typeof value==='number' && Number.isFinite(value)))return value;
    if(!value || typeof value!=='object' || ancestors.has(value))fail('History accepts finite, acyclic JSON data only.');
    const array=Array.isArray(value),proto=Object.getPrototypeOf(value),keys=Reflect.ownKeys(value);
    if(!array && proto!==Object.prototype && proto!==null)fail('History needs plain records.');
    if(array && (keys.length!==value.length+1 || !Array.from({length:value.length},(_,i)=>Object.hasOwn(value,String(i))).every(Boolean)))fail('History needs dense arrays.');
    ancestors.add(value);const pairs=[];
    for(const key of keys) {
      if(array && key==='length')continue;
      if(typeof key!=='string' || ['__proto__','constructor','prototype'].includes(key))fail('Unsafe history key.');
      const d=Object.getOwnPropertyDescriptor(value,key);
      if(!Object.hasOwn(d,'value') || !d.enumerable)fail('History cannot contain accessors.');
      pairs.push([key,data(d.value,ancestors)]);
    }
    ancestors.delete(value);
    return Object.freeze(array ? pairs.map(p=>p[1]) : Object.fromEntries(pairs));
  }
  function fields(value, allowed, required=allowed) {
    if(!value || typeof value!=='object' || Array.isArray(value) || Object.keys(value).some(k=>!allowed.includes(k)) || required.some(k=>!Object.hasOwn(value,k)))fail('Missing or unsupported history fields: '+allowed.join(', '));
  }
  function ids(value) {
    if(!Array.isArray(value) || value.some(id=>typeof id!=='string' || !id.trim()) || new Set(value).size!==value.length)fail('Record IDs must be unique nonempty strings.');
  }
  function createHistory({initial,commit=async()=>{}}) {
    if(typeof commit!=='function')fail('commit must be a trusted function.');
    let baseline=core.createState(initial),current=baseline,entries=Object.freeze([]),busy=false,sequence=0;
    const listeners=new Set();
    const snapshot=()=>Object.freeze({state:current,entries,busy});
    // Observers are notifications, never part of a successful state transaction.
    const notify=()=>{const s=snapshot();for(const fn of listeners){try{fn(s);}catch{ /* observer isolation */ }}};
    const available=()=>{if(busy)fail('History is busy; await the current transition.');};
    async function transition(next, nextEntries, operation, result) {
      busy=true;notify();
      try {
        await commit(next,Object.freeze({operation,previous:current}));
        current=next;entries=Object.freeze(nextEntries);
        return result;
      } finally {busy=false;notify();}
    }
    return Object.freeze({
      snapshot,
      subscribe(fn) {
        if(typeof fn!=='function')fail('Subscriber must be a function.');
        listeners.add(fn);try{fn(snapshot());}catch{ /* observer isolation */ }
        return ()=>listeners.delete(fn);
      },
      async execute(input) {
        available();const p=data(input);
        fields(p,['action','diff','record_ids','linked_record_ids'],['action','diff']);
        fields(p.action,['tool','args']);
        if(typeof p.action.tool!=='string' || !p.action.tool.trim())fail('Executed action needs a tool name.');
        if(!p.action.args || typeof p.action.args!=='object' || Array.isArray(p.action.args))fail('Action args must be an object.');
        const record_ids=Object.hasOwn(p,'record_ids')?p.record_ids:[],linked_record_ids=Object.hasOwn(p,'linked_record_ids')?p.linked_record_ids:[];
        ids(record_ids);ids(linked_record_ids);
        const next=core.applyDiff(current,p.diff),id='action-'+(++sequence);
        const entry=data({schema_version:1,id,action:p.action,diff:p.diff,record_ids,linked_record_ids,controls:{undo:{entry_id:id},reset:{target:'initial'}}});
        return transition(next,[...entries,entry],'execute',entry);
      },
      async undo(entryId) {
        available();const entry=entries.at(-1);
        if(!entry)fail('No action to undo.');
        if(entryId!==undefined && entryId!==entry.id)fail('Undo is available only for the latest action.');
        return transition(core.revertDiff(current,entry.diff),entries.slice(0,-1),'undo',entry);
      },
      async reset() {
        available();return transition(core.resetState(current,baseline),[],'reset',undefined);
      },
      replaceSession(initialState) {
        available();const next=core.createState(initialState);
        // Caller already loaded this dataset. No old-dataset commit is performed.
        baseline=next;current=next;entries=Object.freeze([]);notify();
      }
    });
  }
  function mountHistory(container,history) {
    const doc=container.ownerDocument;
    const element=(tag,text)=>{const node=doc.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
    const panel=element('section');panel.className='action-history';panel.setAttribute('aria-label','Action history');
    const heading=element('h3','Action history'),controls=element('div'),undo=element('button','Undo'),reset=element('button','Reset');
    undo.type=reset.type='button';controls.append(undo,reset);
    const status=element('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const note=element('p','Undo restores the latest action’s state; Reset restores the session’s initial state. External side effects are not undone.');
    const list=element('ol');list.className='action-history-entries';
    panel.append(heading,controls,note,status,list);container.append(panel);
    let disposed=false;
    async function run(operation) {
      status.textContent='Applying…';
      try {await operation();if(!disposed)status.textContent='State restored.';}
      catch(error){if(!disposed)status.textContent='Not applied: '+error.message;}
    }
    undo.onclick=()=>run(()=>history.undo());reset.onclick=()=>run(()=>history.reset());
    const unsubscribe=history.subscribe(s=>{
      const focused=doc.activeElement,focusedControl=focused?.dataset.historyControl;
      const expanded=new Set(Array.from(list.querySelectorAll('details[open]'),n=>n.dataset.entryId));
      undo.disabled=s.busy || !s.entries.length;reset.disabled=s.busy;
      list.replaceChildren();
      if(!s.entries.length)list.append(element('li','No actions in this session.'));
      for(const entry of s.entries) {
        const item=element('li');item.dataset.entryId=entry.id;
        const details=element('details');details.dataset.entryId=entry.id;details.open=expanded.has(entry.id);
        const summary=element('summary',entry.id+' · '+entry.action.tool);
        const pre=element('pre',JSON.stringify(entry,null,2));details.append(summary,pre);
        const entryUndo=element('button','Undo this action'),entryReset=element('button','Reset to initial state');
        entryUndo.type=entryReset.type='button';
        entryUndo.dataset.historyControl=entry.id+'-undo';entryReset.dataset.historyControl=entry.id+'-reset';
        entryUndo.disabled=s.busy || entry.id!==s.entries.at(-1).id;entryReset.disabled=s.busy;
        entryUndo.onclick=()=>run(()=>history.undo(entry.id));entryReset.onclick=()=>run(()=>history.reset());
        item.append(details,entryUndo,entryReset);list.append(item);
      }
      if(focusedControl) {
        const replacement=Array.from(list.querySelectorAll('button')).find(n=>n.dataset.historyControl===focusedControl);
        if(replacement && !replacement.disabled)replacement.focus();
        else if(!s.busy)reset.focus();
      }
    });
    return ()=>{disposed=true;unsubscribe();panel.remove();};
  }
  const api=Object.freeze({createHistory,mountHistory});
  if(typeof module==='object' && module.exports)module.exports=api;
  else root.ViewActionHistory=api;
})(typeof globalThis!=='undefined'?globalThis:this);
