/* Optional model tool-calling UI plus explicit local commands. No eval or model DOM access. */
'use strict';
window.mountViewChat = bridge => {
  const el = id => document.getElementById(id);
  const copy = x => structuredClone(x);
  const root = document.createElement('aside');
  root.id='view-chat'; root.setAttribute('aria-label','Ask about this view');
  root.innerHTML=`<button id="chat-toggle" aria-expanded="false" aria-controls="chat-body">Ask about this view</button>
  <section id="chat-body" hidden aria-label="Model connection and local view commands">
    <p id="agent-status" role="status">No model is connected. Local rule/parser commands remain available; not an AI agent.</p>
    <details id="agent-config"><summary>Configure model (session only)</summary>
      <p>Synthetic demo, not real trial data. Calls go through this machine's loopback adapter. Public HTTPS only; loopback development URLs require a startup allowlist.</p>
      <label>Full chat/completions endpoint <input id="agent-endpoint" type="url" autocomplete="off" placeholder="https://provider.example/v1/chat/completions"></label>
      <label>Model ID <input id="agent-model" autocomplete="off"></label>
      <label>Session credential <input id="agent-key" type="password" autocomplete="off" spellcheck="false"></label>
      <p>Credential is held only in session memory, not persisted in saved views, exports, history or browser storage. The password field is cleared when you test; Disconnect forgets the credential. Reloading requires configuration again.</p>
      <p id="agent-destination"></p>
      <button id="agent-test" type="button">Test and connect model</button>
      <button id="agent-disconnect" type="button">Disconnect and forget credential</button>
    </details>
    <label><input id="agent-record-consent" type="checkbox"> Request record-level content for the next request only (separate confirmation required). Leave unchecked for aggregate-only model context.</label>
    <p id="chat-tool-status" role="status">Tool execution: ready (local validated tools only).</p>
    <p>Counts use the current qualifying analysis, never the visible subset. Omitted date filter means all dates. Highlights are outlines, not analysis filters; hidden or off-screen matches stay listed below.</p>
    <details><summary>Command syntax and examples</summary>
      <p>Use one exact JSON command below. Also accepted: “count grade 3 AE records in current analysis” or “count patients with a grade 3 AE in current analysis”. No other natural language is inferred.</p>
      <pre id="chat-examples"></pre>
      <p>Filters: term (exact AETERM), grade (integer 1–5, AETOXGR only), patient (USUBJID), linked_cm (exact CMTRT via source relationships), date_window: {"anchor":"AESTDTC","start":"2025-01-01","end":"2025-01-31"}. Dates are inclusive onset dates. No relative windows or inferred treatment anchor. Unknown grade and incomplete dates are excluded with diagnostics.</p>
      <p>set_view: sort duration/asc/desc/response/pd/reason; focus patient ID or null; layers array of AE/CM/EX/RS (DS context stays on); tier auto/0/1/2. Camera: timeline {start,end} as UTC epoch milliseconds, or 3D {position:[x,y,z],target:[x,y,z],span:number} in scene units. Undo restores the pre-command settled camera, not an animation in flight. Reset restores the view before this command session. Analysis changes invalidate history.</p>
      <p>Model display alignment on /lattice: calendar, first_treatment (first_dose), first_PR, first_PD, death. Elapsed calendar days, not SDTM study days. Missing anchors remain in labeled unaligned groups. Alignment is session-only, like camera/sort, not part of saved analysis/replay packages. Randomization and anchor-relative analytical windows require a development task; display alignment never changes analysis counts.</p>
    </details>
    <form id="chat-form"><label for="chat-request">View request</label><textarea id="chat-request" rows="4" required spellcheck="false"></textarea><button type="submit">Run local command</button><button type="button" id="agent-send" disabled>Ask configured model</button></form>
    <section id="agent-proposal" hidden aria-label="Confirm analysis change"><p id="agent-consequence"></p><button id="agent-confirm" type="button">Confirm analysis subset</button><button id="agent-cancel" type="button">Cancel proposal</button></section>
    <div><button id="chat-undo" disabled>Undo</button> <button id="chat-reset" disabled>Reset</button></div>
    <p id="chat-result" role="status" aria-live="polite"></p>
    <details open><summary>Matched source record IDs</summary><pre id="chat-records">None</pre></details>
    <details><summary>In-page action history (session only)</summary><pre id="chat-history">[]</pre></details>
  </section>
  <dialog id="agent-egress-dialog" aria-labelledby="agent-egress-title" aria-describedby="agent-egress-details">
    <h2 id="agent-egress-title">Confirm model data egress</h2>
    <p id="agent-egress-details"></p>
    <pre id="agent-egress-destination"></pre>
    <pre id="agent-egress-request"></pre>
    <p>This loaded demo dataset is synthetic, not real trial data. The credential is session-only and not persisted. Your own prompt may contain identifiers.</p>
    <label><input id="agent-consent" type="checkbox"> I acknowledge that my prompt, relevant view metadata and any data returned to the model leave this machine for the exact endpoint/model above.</label>
    <button id="agent-egress-confirm" type="button" disabled>Confirm egress and continue</button>
    <button id="agent-egress-cancel" type="button">Cancel — send nothing</button>
  </dialog>`;
  document.body.append(root);
  el('chat-examples').textContent=[
    {tool:'set_view',args:{sort:'asc',tier:'2'}},
    {tool:'highlight_events',args:{scope:'current_analysis',filters:{grade:3}}},
    {tool:'query_data',args:{scope:'current_analysis',unit:'patients',filters:{grade:3}}}
  ].map(x=>JSON.stringify(x)).join('\n');
  let history=[], initial=null, signature=null, audit=[], connected=null, pending=null, working=false, configVersion=0, testSecret='';
  const clean = x => {const secret=connected?.credential||testSecret;return secret ? String(x).split(secret).join('[REDACTED]') : String(x);};
  const fullSnapshot=()=>({display:copy(bridge.snapshot()),analysis:bridge.analysisSnapshot()});
  async function restoreFull(saved){
    if(JSON.stringify(saved.analysis)!==JSON.stringify(bridge.analysisSnapshot()))await bridge.setAnalysis(saved.analysis);
    await bridge.restore(saved.display);
  }
  function record(tool,before,result){
    const after=fullSnapshot(), diff={};
    for(const key of ['display','analysis'])if(JSON.stringify(before[key])!==JSON.stringify(after[key]))diff[key]={before:before[key],after:after[key]};
    audit.push({tool,diff,result,record_ids:result.record_ids||[],undo:'Use Undo for the most recent executed action; Reset returns to the session baseline.'});
    el('chat-history').textContent=clean(JSON.stringify(audit,null,2));
  }
  const object = x => x && typeof x==='object' && !Array.isArray(x);
  const keys = (x,allowed) => {if(!object(x)||Object.keys(x).some(k=>!allowed.includes(k)))throw Error('Unsupported fields. Use only the documented tool arguments.');};
  function parse(text) {
    const a=text.trim().match(/^count grade ([1-5]) AE records in current analysis$/i);
    const b=text.trim().match(/^count patients with a grade ([1-5]) AE in current analysis$/i);
    if(a||b)return {tool:'query_data',args:{scope:'current_analysis',unit:a?'AE records':'patients',filters:{grade:+(a||b)[1]}}};
    try{return JSON.parse(text);}catch{throw Error('Unsupported or ambiguous request. Which counting unit (patients or AE records), date window and anchor? Use an explicit documented command; nothing changed.');}
  }
  function validateView(args) {
    keys(args,['sort','focus','subset','layers','tier','camera']);
    if(!Object.keys(args).length)throw Error('Which view property should change?');
    if('sort' in args&&!['duration','asc','desc','response','pd','reason'].includes(args.sort))throw Error('Unsupported sort order.');
    if('tier' in args&&!['auto','0','1','2'].includes(args.tier))throw Error('Choose tier auto, 0, 1 or 2 as a string.');
    if('focus' in args && args.focus!==null && bridge.roster().filter(p=>p[1]===args.focus).length!==1)throw Error('Choose one unambiguous roster patient ID, or null for all.');
    if('subset' in args && ('focus' in args||!Array.isArray(args.subset)||!args.subset.length||new Set(args.subset).size!==args.subset.length||args.subset.some(id=>bridge.roster().filter(p=>p[1]===id).length!==1)))throw Error('Choose an explicit unique display subset of roster IDs, without focus.');
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
  function report(text,ids=[]) {el('chat-result').textContent=clean(text);el('chat-records').textContent=ids.length?clean(ids.join('\n')):'None';}
  function buttons(){el('chat-undo').disabled=working||!history.length;el('chat-reset').disabled=working||!initial;el('agent-send').disabled=working||!connected||!!pending;el('agent-test').disabled=working;el('agent-confirm').disabled=working;}
  async function run(work) {
    if(bridge.busy()||working)return;
    working=true;buttons();
    el('chat-tool-status').textContent='Tool execution: validating locally…';
    try {await bridge.lock(async()=>{
      if(signature!==bridge.signature()){history=[];initial=null;pending=null;el('agent-proposal').hidden=true;signature=bridge.signature();}
      await work();
      signature=bridge.signature();
    });el('chat-tool-status').textContent='Tool execution: completed locally. See action history for display/analysis diffs.';}
    catch(e){el('chat-tool-status').textContent='Tool execution: refused; rejected action changed nothing. Earlier completed actions remain undoable.';report(e.message);}
    testSecret='';working=false;buttons();
  }
  el('chat-toggle').onclick=()=>{const open=el('chat-body').hidden;el('chat-body').hidden=!open;el('chat-toggle').setAttribute('aria-expanded',String(open));if(open)el('chat-request').focus();};
  root.addEventListener('keydown',e=>{if(e.key==='Escape'&&!el('agent-egress-dialog').open){el('chat-body').hidden=true;el('chat-toggle').setAttribute('aria-expanded','false');el('chat-toggle').focus();}});
  el('chat-form').onsubmit=e=>{e.preventDefault();run(async()=>{
    const cmd=parse(el('chat-request').value);keys(cmd,['tool','args']);
    if(!['set_view','highlight_events','query_data'].includes(cmd.tool))throw Error('Unsupported tool. Choose set_view, highlight_events or query_data.');
    let result;
    if(cmd.tool==='set_view')validateView(cmd.args);
    else {
      keys(cmd.args,cmd.tool==='query_data'?['scope','unit','filters']:['scope','filters']);
      result=await bridge.query({...cmd.args,...(cmd.tool==='highlight_events'?{unit:'AE records'}:{})});
    }
    const before=fullSnapshot();
    if(cmd.tool==='set_view') {
      await bridge.setView(cmd.args);
      result={record_ids:bridge.records()};
    } else if(cmd.tool==='highlight_events') bridge.highlight(result.record_ids);
    history.push(before);if(!initial)initial=copy(before);
    record(cmd.tool,before,result);
    const detail=cmd.tool==='query_data'?`${result.count} ${result.unit}; read-only, view unchanged`:
      cmd.tool==='highlight_events'?`Highlight overlay replaced: ${result.record_ids.length} AE records`:`View changed: ${JSON.stringify(cmd.args)}`;
    report(`${detail}. Analysis unchanged.${result.note?' '+result.note+' Missing grade excluded: '+result.excluded_missing_grade+'; incomplete onset excluded: '+result.excluded_incomplete_onset+'.':''}`,
      [...result.record_ids,...(result.linked_record_ids||[]).map(id=>id+' (linked CM evidence)')]);
  });};
  el('chat-undo').onclick=()=>run(async()=>{if(!history.length)throw Error('No history for this analysis.');const before=fullSnapshot(),previous=history.at(-1);await restoreFull(previous);history.pop();pending=null;el('agent-proposal').hidden=true;record('Undo',before,{record_ids:previous.display.highlights});report('Undo: previous view and analysis restored exactly.',previous.display.highlights);});
  el('chat-reset').onclick=()=>run(async()=>{if(!initial)throw Error('No session baseline for this analysis.');const before=fullSnapshot();await restoreFull(initial);record('Reset',before,{record_ids:initial.display.highlights});report('Reset: pre-session view and analysis restored exactly.',initial.display.highlights);history=[];initial=null;pending=null;el('agent-proposal').hidden=true;});

  function disconnect(){configVersion++;connected=null;el('agent-key').value='';el('agent-consent').checked=false;el('agent-record-consent').checked=false;el('agent-status').textContent='No model is connected. Local rule/parser commands remain available; not an AI agent.';buttons();}
  function destination(){el('agent-destination').textContent=`Endpoint: ${el('agent-endpoint').value || '(unset)'} | Model: ${el('agent-model').value || '(unset)'} | Dataset: ${bridge.dataset()} (synthetic)`;}
  for(const id of ['agent-endpoint','agent-model'])el(id).addEventListener('input',()=>{disconnect();destination();});
  el('agent-key').addEventListener('input',()=>{configVersion++;connected=null;el('agent-consent').checked=false;el('agent-status').textContent='No model is connected. Test the new credential.';buttons();});
  el('agent-disconnect').onclick=disconnect;
  destination();
  function confirmEgress(config,prompt=null){
    const dialog=el('agent-egress-dialog');
    el('agent-egress-details').textContent=prompt===null
      ? 'Before the first request for this loaded dataset: the connection test sends a test prompt and capabilities, not patient rows. Later requests send your prompt and aggregate/view metadata; returned tool data is aggregate-only unless separately confirmed.'
      : 'Per-request record-level egress: source record IDs and returned records may be sent during this request, including its tool-result follow-ups. This permission expires when this request ends.';
    el('agent-egress-destination').textContent=`Endpoint: ${config.endpoint}\nModel: ${config.model}\nDataset: ${config.dataset} (synthetic)`;
    el('agent-egress-request').textContent=prompt===null?'Connection test; no patient rows.':`Request: ${prompt}`;
    el('agent-consent').checked=false;el('agent-egress-confirm').disabled=true;
    el('agent-consent').onchange=()=>{el('agent-egress-confirm').disabled=!el('agent-consent').checked;};
    return new Promise(resolve=>{
      const finish=allowed=>{dialog.close();resolve(allowed);};
      el('agent-egress-confirm').onclick=()=>{if(el('agent-consent').checked)finish(true);};
      el('agent-egress-cancel').onclick=()=>finish(false);
      dialog.oncancel=e=>{e.preventDefault();finish(false);};
      dialog.showModal();
    });
  }
  el('agent-test').onclick=()=>run(async()=>{
    const config={endpoint:el('agent-endpoint').value,model:el('agent-model').value,credential:el('agent-key').value,dataset:bridge.dataset(),acknowledged:true};
    const version=configVersion;
    connected=null;testSecret=config.credential;el('agent-key').value='';
    el('agent-status').textContent='No model is connected. Awaiting egress confirmation.';
    if(!await confirmEgress(config)){report('Connection cancelled. No model request sent. Re-enter credential to test again.');return;}
    if(version!==configVersion||config.dataset!==bridge.dataset())throw Error('Configuration or dataset changed; reconnect explicitly.');
    el('agent-status').textContent='No model is connected. Testing…';
    const result=await bridge.agent({...config,mode:'test',messages:[]});
    if(version!==configVersion||config.dataset!==bridge.dataset())throw Error('Configuration or dataset changed; self-test response discarded.');
    if(result.connected!==true)throw Error('Self-test did not confirm a model connection.');
    connected=config;
    el('agent-status').textContent=`Model-driven agent — tested ${config.model} at ${config.endpoint}. Tool execution is separately validated locally.`;
    report('Configured endpoint/model connection test succeeded. No patient rows were sent.');
  });
  async function execute(call,recordEgress){
    keys(call,['tool','args']);
    const before=fullSnapshot();let result;
    if(call.tool==='set_view'){
      validateView(call.args);await bridge.setView(call.args);
      result={status:'executed',note:'View changed; analysis unchanged.',record_ids:bridge.records()};
    } else if(call.tool==='get_view_state'){
      keys(call.args,[]);result={status:'read_only',view:bridge.snapshot(),record_ids:bridge.records()};
    } else {
      result=await bridge.agentTool(call.tool,call.args,recordEgress);
      if(call.tool==='set_alignment' && result.status==='resolved'){
        bridge.setAlignment(result);result={...result,status:'executed'};
      }
      if(call.tool==='highlight_events')bridge.highlight(result.record_ids);
      if(call.tool==='propose_analysis_subset'){
        pending={result,signature:bridge.signature(),before:fullSnapshot()};
        el('agent-consequence').textContent=JSON.stringify(result,null,2);
        el('agent-proposal').hidden=false;
      }
    }
    history.push(before);if(!initial)initial=copy(before);record(call.tool,before,result);
    const summary=call.tool==='query_data'?`${result.count} ${result.unit}; read-only, view unchanged`:
      call.tool==='highlight_events'?`Highlight overlay replaced: ${result.record_ids.length} AE records; analysis unchanged`:
      result.note||`${call.tool}: ${result.status||'capabilities returned'}`;
    report(summary,result.record_ids||[]);
    return result;
  }
  el('agent-send').onclick=()=>run(async()=>{
    if(!connected||connected.dataset!==bridge.dataset()){disconnect();throw Error('No tested model/consent for this dataset. Reconnect explicitly.');}
    if(pending)throw Error('Confirm or cancel the pending analysis proposal first.');
    const prompt=el('chat-request').value.trim();if(!prompt)throw Error('Enter a request.');
    const config=connected,version=configVersion,recordEgress=el('agent-record-consent').checked;
    el('agent-record-consent').checked=false;
    if(recordEgress&&!await confirmEgress(config,prompt)){report('Record-level request cancelled. No model request sent.');return;}
    if(version!==configVersion||config.dataset!==bridge.dataset())throw Error('Configuration or dataset changed; request cancelled.');
    const messages=[{role:'user',content:prompt}];let executed=false;
    for(let turn=0;turn<6;turn++){
      const response=await bridge.agent({...config,record_egress:recordEgress,mode:'turn',messages});
      if(connected!==config||version!==configVersion||config.dataset!==bridge.dataset())throw Error('Configuration or dataset changed; response discarded.');
      const message=response.message;messages.push(message);
      if(!message.tool_calls?.length){
        const note=message.content?`Unverified model message (not data evidence): ${message.content}`:'Please clarify the counting unit, window, anchor or requested view property.';
        if(!executed)report(`Model returned no validated tool action. No changes. ${note}`);
        else if(message.content)el('chat-result').textContent+=clean(`\n${note}`);
        return;
      }
      // Require one action per turn: avoids partial application of ambiguous batches.
      if(message.tool_calls.length!==1)throw Error('Model requested multiple actions at once. Refused; request one explicit action per turn.');
      const call=message.tool_calls[0];let result;
      try {result=await execute({tool:call.function.name,args:JSON.parse(call.function.arguments)},recordEgress);executed=true;}
      catch(e){result={status:'refused',note:clean(e.message)};report(result.note);record('refused tool',fullSnapshot(),result);}
      messages.push({role:'tool',tool_call_id:call.id,content:JSON.stringify(result)});
      if(pending||['clarification_required','development_proposal','refused','unsupported'].includes(result.status))return;
    }
    report('Model tool-turn limit reached. Completed actions remain in history; no further actions executed.');
  });
  el('agent-confirm').onclick=()=>run(async()=>{
    if(!pending||pending.signature!==bridge.signature())throw Error('Analysis changed; proposal expired.');
    const proposal=pending,before=fullSnapshot();
    await bridge.setPopulation(proposal.result.population);
    history.push(before);if(!initial)initial=copy(before);
    record('confirm_analysis_subset',before,{status:'executed_after_user_confirmation',record_ids:proposal.result.record_ids});
    pending=null;el('agent-proposal').hidden=true;report('Analysis subset executed after explicit confirmation; counts recomputed. Undo restores the previous analysis and display.',proposal.result.record_ids);
  });
  el('agent-cancel').onclick=()=>run(async()=>{pending=null;el('agent-proposal').hidden=true;record('cancel_analysis_proposal',fullSnapshot(),{status:'cancelled',record_ids:[]});report('Analysis proposal cancelled. Nothing changed.');});
};
