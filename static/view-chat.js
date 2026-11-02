/* Local deterministic command UI. No model, eval, or browser automation. */
'use strict';
window.mountViewChat = bridge => {
  const el = id => document.getElementById(id);
  const copy = x => structuredClone(x);
  const root = document.createElement('aside');
  root.id='view-chat'; root.setAttribute('aria-label','Ask about this view');
  root.innerHTML=`<button id="chat-toggle" aria-expanded="false" aria-controls="chat-body">Ask about this view</button>
  <section id="chat-body" hidden aria-label="Local view commands">
    <p>Local rule/parser demo — not an AI agent.</p>
    <p>Model connection: not connected. No outbound model calls.</p>
    <p id="chat-tool-status" role="status">Tool execution: ready (local validated tools only).</p>
    <p>Counts use the current qualifying analysis, never the visible subset. Omitted date filter means all dates. Highlights are outlines, not analysis filters; hidden or off-screen matches stay listed below.</p>
    <details><summary>Command syntax and examples</summary>
      <p>Use one exact JSON command below. Also accepted: “count grade 3 AE records in current analysis” or “count patients with a grade 3 AE in current analysis”. No other natural language is inferred.</p>
      <pre id="chat-examples"></pre>
      <p>Filters: term (exact AETERM), grade (integer 1–5, AETOXGR only), patient (USUBJID), linked_cm (exact CMTRT via source relationships), date_window: {"anchor":"AESTDTC","start":"2025-01-01","end":"2025-01-31"}. Dates are inclusive onset dates. No relative windows or inferred treatment anchor. Unknown grade and incomplete dates are excluded with diagnostics.</p>
      <p>set_view: sort duration/asc/desc/response/pd/reason; focus patient ID or null; layers array of AE/CM/EX/RS (DS context stays on); tier auto/0/1/2. Camera: timeline {start,end} as UTC epoch milliseconds, or 3D {position:[x,y,z],target:[x,y,z],span:number} in scene units. Undo restores the pre-command settled camera, not an animation in flight. Reset restores the view before this command session. Analysis changes invalidate history.</p>
    </details>
    <form id="chat-form"><label for="chat-request">View request</label><textarea id="chat-request" rows="4" required spellcheck="false"></textarea><button type="submit">Run local command</button></form>
    <div><button id="chat-undo" disabled>Undo</button> <button id="chat-reset" disabled>Reset</button></div>
    <p id="chat-result" role="status" aria-live="polite"></p>
    <details open><summary>Matched source record IDs</summary><pre id="chat-records">None</pre></details>
  </section>`;
  document.body.append(root);
  el('chat-examples').textContent=[
    {tool:'set_view',args:{sort:'asc',tier:'2'}},
    {tool:'highlight_events',args:{scope:'current_analysis',filters:{grade:3}}},
    {tool:'query_data',args:{scope:'current_analysis',unit:'patients',filters:{grade:3}}}
  ].map(x=>JSON.stringify(x)).join('\n');
  let history=[], initial=null, signature=null;
  const object = x => x && typeof x==='object' && !Array.isArray(x);
  const keys = (x,allowed) => {if(!object(x)||Object.keys(x).some(k=>!allowed.includes(k)))throw Error('Unsupported fields. Use only the documented tool arguments.');};
  function parse(text) {
    const a=text.trim().match(/^count grade ([1-5]) AE records in current analysis$/i);
    const b=text.trim().match(/^count patients with a grade ([1-5]) AE in current analysis$/i);
    if(a||b)return {tool:'query_data',args:{scope:'current_analysis',unit:a?'AE records':'patients',filters:{grade:+(a||b)[1]}}};
    try{return JSON.parse(text);}catch{throw Error('Unsupported or ambiguous request. Which counting unit (patients or AE records), date window and anchor? Use an explicit documented command; nothing changed.');}
  }
  function validateView(args) {
    keys(args,['sort','focus','layers','tier','camera']);
    if(!Object.keys(args).length)throw Error('Which view property should change?');
    if('sort' in args&&!['duration','asc','desc','response','pd','reason'].includes(args.sort))throw Error('Unsupported sort order.');
    if('tier' in args&&!['auto','0','1','2'].includes(args.tier))throw Error('Choose tier auto, 0, 1 or 2 as a string.');
    if('focus' in args && args.focus!==null && bridge.roster().filter(p=>p[1]===args.focus).length!==1)throw Error('Choose one unambiguous roster patient ID, or null for all.');
    if('layers' in args && (!Array.isArray(args.layers)||args.layers.some(l=>!['AE','CM','EX','RS'].includes(l))||new Set(args.layers).size!==args.layers.length))throw Error('Choose unique visible layers AE/CM/EX/RS.');
    if('camera' in args) {
      const c=args.camera;
      if(bridge.is3d()) {
        keys(c,['position','target','span']);
        if(Object.keys(c).length!==3||![c.position,c.target].every(v=>Array.isArray(v)&&v.length===3&&v.every(n=>Number.isFinite(n)&&Math.abs(n)<1e6))||!Number.isFinite(c.span)||c.span<8||c.span>100000)throw Error('Supply finite camera position, target and span (8–100000).');
        const d=c.position.map((v,i)=>v-c.target[i]), distance=Math.hypot(...d);
        if(distance<1||distance>10000||Math.hypot(d[0],d[2])<.001)throw Error('Camera direction must be nonvertical, with distance 1–10000.');
      } else {
        keys(c,['start','end']);
        if(!Number.isFinite(c.start)||!Number.isFinite(c.end)||c.end<=c.start||Math.abs(c.start)>8e15||Math.abs(c.end)>8e15)throw Error('Timeline camera needs finite ordered UTC epoch start/end.');
      }
    }
  }
  function report(text,ids=[]) {el('chat-result').textContent=text;el('chat-records').textContent=ids.length?ids.join('\n'):'None';}
  function buttons(){el('chat-undo').disabled=!history.length;el('chat-reset').disabled=!initial;}
  async function run(work) {
    if(bridge.busy())return;
    el('chat-tool-status').textContent='Tool execution: validating locally…';
    try {await bridge.lock(async()=>{
      if(signature!==bridge.signature()){history=[];initial=null;signature=bridge.signature();}
      await work();
    });el('chat-tool-status').textContent='Tool execution: completed locally. Analysis unchanged.';}
    catch(e){el('chat-tool-status').textContent='Tool execution: refused; nothing changed.';report(e.message);}
    buttons();
  }
  el('chat-toggle').onclick=()=>{const open=el('chat-body').hidden;el('chat-body').hidden=!open;el('chat-toggle').setAttribute('aria-expanded',String(open));if(open)el('chat-request').focus();};
  root.addEventListener('keydown',e=>{if(e.key==='Escape'){el('chat-body').hidden=true;el('chat-toggle').setAttribute('aria-expanded','false');el('chat-toggle').focus();}});
  el('chat-form').onsubmit=e=>{e.preventDefault();run(async()=>{
    const cmd=parse(el('chat-request').value);keys(cmd,['tool','args']);
    if(!['set_view','highlight_events','query_data'].includes(cmd.tool))throw Error('Unsupported tool. Choose set_view, highlight_events or query_data.');
    let result;
    if(cmd.tool==='set_view')validateView(cmd.args);
    else {
      keys(cmd.args,cmd.tool==='query_data'?['scope','unit','filters']:['scope','filters']);
      result=await bridge.query({...cmd.args,...(cmd.tool==='highlight_events'?{unit:'AE records'}:{})});
    }
    const before=bridge.snapshot();
    if(cmd.tool==='set_view') {
      await bridge.setView(cmd.args);
      result={record_ids:bridge.records()};
    } else if(cmd.tool==='highlight_events') bridge.highlight(result.record_ids);
    history.push(before);if(!initial)initial=copy(before);
    const detail=cmd.tool==='query_data'?`${result.count} ${result.unit}; read-only, view unchanged`:
      cmd.tool==='highlight_events'?`Highlight overlay replaced: ${result.record_ids.length} AE records`:`View changed: ${JSON.stringify(cmd.args)}`;
    report(`${detail}. Analysis unchanged.${result.note?' '+result.note+' Missing grade excluded: '+result.excluded_missing_grade+'; incomplete onset excluded: '+result.excluded_incomplete_onset+'.':''}`,
      [...result.record_ids,...(result.linked_record_ids||[]).map(id=>id+' (linked CM evidence)')]);
  });};
  el('chat-undo').onclick=()=>run(async()=>{if(!history.length)throw Error('No history for this analysis.');const previous=history.at(-1);await bridge.restore(previous);history.pop();report('Undo: previous view restored exactly. Analysis unchanged.',previous.highlights);});
  el('chat-reset').onclick=()=>run(async()=>{if(!initial)throw Error('No session baseline for this analysis.');await bridge.restore(initial);report('Reset: pre-session view restored exactly. Analysis unchanged.',initial.highlights);history=[];initial=null;});
};
