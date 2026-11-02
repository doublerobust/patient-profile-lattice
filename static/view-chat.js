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
    <section id="agent-scope-proposal" hidden aria-label="Approve display scope"><p>Proposed mapping only — nothing changed. Verify the exact request, intent and patient IDs/source filters below. Approval applies once to this action, not future requests. Analysis confirmation is separate.</p><pre id="agent-scope-mapping"></pre><button id="agent-scope-confirm" type="button">Approve this display scope</button><button id="agent-scope-cancel" type="button">Cancel display scope</button></section>
    <p>Model selections require a scope proposal and approval. Supported explicit requests include “Show only patients SYN-001”, “Focus on SYN-001”, “Show all patients”, “Highlight source IDs AE-001-1”, “Highlight grade 3 AE records”, “Highlight exact term SYNTHETIC NAUSEA”, or an exact JSON set_view/highlight_events command. Other phrasing needs clarification; clinical inference is unsupported.</p>
    <div><button id="chat-undo" disabled>Undo</button> <button id="chat-reset" disabled>Reset</button></div>
    <p id="chat-result" role="status" aria-live="polite"></p>
    <details open><summary>Matched source record IDs</summary><pre id="chat-records">None</pre></details>
    <details><summary>In-page action history (session only)</summary><pre id="chat-history">[]</pre></details>
    <details><summary>Local development tasks (not external tickets; Undo/Reset do not delete tasks)</summary><pre id="chat-tasks">[]</pre></details>
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
  let signature=null, connected=null, working=false, configVersion=0, testSecret='', pendingScope=null;
  const clean = x => {const secret=connected?.credential||testSecret;return secret ? String(x).split(secret).join('[REDACTED]') : String(x);};
  const fullSnapshot=()=>({display:copy(bridge.snapshot()),analysis:bridge.analysisSnapshot()});
  const session=new ViewTools.ToolSession({snapshot:fullSnapshot,roster:bridge.roster,
    resolve:bridge.agentTool,apply:bridge.applySnapshot,records:bridge.records,dataset:bridge.dataset});
  function syncHistory(){
    el('agent-scope-proposal').hidden=!pendingScope;
    el('agent-scope-mapping').textContent=pendingScope?clean(JSON.stringify({request:pendingScope.prompt,...pendingScope.proposal},null,2)):'';
    el('chat-history').textContent=clean(JSON.stringify(session.audit,null,2));
    el('chat-tasks').textContent=clean(JSON.stringify(session.tasks,null,2));
    el('agent-proposal').hidden=!session.pending;
    el('agent-consequence').textContent=session.pending?JSON.stringify(session.pending.result,null,2):'';
  }

  const object = x => x && typeof x==='object' && !Array.isArray(x);
  const keys = (x,allowed) => {if(!object(x)||Object.keys(x).some(k=>!allowed.includes(k)))throw Error('Unsupported fields. Use only the documented tool arguments.');};
  function parse(text) {
    const a=text.trim().match(/^count grade ([1-5]) AE records in current analysis$/i);
    const b=text.trim().match(/^count patients with a grade ([1-5]) AE in current analysis$/i);
    if(a||b)return {tool:'query_data',args:{scope:'current_analysis',unit:a?'AE records':'patients',filters:{grade:+(a||b)[1]}}};
    try{return JSON.parse(text);}catch{throw Error('Unsupported or ambiguous request. Which counting unit (patients or AE records), date window and anchor? Use an explicit documented command; nothing changed.');}
  }
  function report(text,ids=[]) {el('chat-result').textContent=clean(text);el('chat-records').textContent=ids.length?clean(ids.join('\n')):'None';}
  function buttons(){el('chat-undo').disabled=working||!session.stack.length;el('chat-reset').disabled=working||!session.initial;el('agent-send').disabled=working||!connected||!!session.pending||!!pendingScope;el('agent-test').disabled=working;el('agent-confirm').disabled=working;el('agent-scope-confirm').disabled=working;}
  function cancelScope(){pendingScope=null;syncHistory();buttons();}
  el('chat-request').addEventListener('input',cancelScope);
  async function run(work) {
    if(bridge.busy()||working)return;
    working=true;buttons();
    el('chat-tool-status').textContent='Tool execution: validating locally…';
    try {await bridge.lock(async()=>{
      if(signature!==bridge.signature()||JSON.stringify(session.history.snapshot().state)!==JSON.stringify(ViewStateCore.createState(fullSnapshot()))){
        const pending=!!session.pending||!!pendingScope;pendingScope=null;session.clear();syncHistory();signature=bridge.signature();
        if(pending)throw Error('State changed; pending proposal expired. Request a new proposal.');
      }
      await work();
      signature=bridge.signature();
    });el('chat-tool-status').textContent='Tool execution: completed locally. See action history for display/analysis diffs.';}
    catch(e){el('chat-tool-status').textContent='Tool execution: refused; rejected action changed nothing. Earlier completed actions remain undoable.';report(e.message);}
    syncHistory();testSecret='';working=false;buttons();
  }
  el('chat-toggle').onclick=()=>{const open=el('chat-body').hidden;el('chat-body').hidden=!open;el('chat-toggle').setAttribute('aria-expanded',String(open));if(open)el('chat-request').focus();};
  root.addEventListener('keydown',e=>{if(e.key==='Escape'&&!el('agent-egress-dialog').open){el('chat-body').hidden=true;el('chat-toggle').setAttribute('aria-expanded','false');el('chat-toggle').focus();}});
  el('chat-form').onsubmit=e=>{e.preventDefault();run(async()=>{
    cancelScope();
    await execute(parse(el('chat-request').value),false);
  });};
  el('chat-undo').onclick=()=>run(async()=>{cancelScope();const result=await session.undo();report('Undo: previous view and analysis restored exactly.',result.record_ids);});
  el('chat-reset').onclick=()=>run(async()=>{cancelScope();const result=await session.reset();report('Reset: pre-session view and analysis restored exactly.',result.record_ids);});

  function disconnect(){configVersion++;connected=null;cancelScope();el('agent-key').value='';el('agent-consent').checked=false;el('agent-record-consent').checked=false;el('agent-status').textContent='No model is connected. Local rule/parser commands remain available; not an AI agent.';buttons();}
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
    cancelScope();
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
    const result=await session.dispatch(call.tool,call.args,{recordEgress});
    syncHistory();
    const summary=call.tool==='query_data'?`${result.count} ${result.unit}; read-only, view unchanged`:
      call.tool==='highlight_events'?`Highlight overlay replaced: ${result.record_ids.length} AE records; analysis unchanged`:
      result.note||`${call.tool}: ${result.status||'capabilities returned'}`;
    report(summary,[...(result.record_ids||[]),...(result.linked_record_ids||[]).map(id=>id+' (linked CM evidence)')]);
    return result;
  }
  el('agent-send').onclick=()=>run(async()=>{
    if(pendingScope)throw Error('Approve or cancel the pending display scope first.');
    if(!connected||connected.dataset!==bridge.dataset()){disconnect();throw Error('No tested model/consent for this dataset. Reconnect explicitly.');}
    if(session.pending)throw Error('Confirm or cancel the pending analysis proposal first.');
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
      try {
        const action={tool:call.function.name,args:JSON.parse(call.function.arguments)};
        const context={roster:bridge.roster(),renderer:bridge.snapshot().renderer};
        if(action.tool==='propose_display_scope'){
          const proposal=ViewTools.validateScopeProposal(prompt,action.args,context);
          if(el('chat-request').value.trim()!==prompt)throw Error('Request changed; scope proposal expired.');
          pendingScope={prompt,proposal,version,config,before:copy(fullSnapshot())};
          syncHistory();report('Display scope approval required. Review the request-to-action mapping; nothing changed.');
          return; // Never continue a model turn after human approval, or reuse its permission.
        }
        ViewTools.validateCall(action.tool,action.args,context);
        if(ViewTools.selectsDisplay(action.tool,action.args))ViewTools.scopeFailure(prompt);
        result=await execute(action,recordEgress);executed=true;
      }
      catch(e){result={status:'refused',note:clean(e.message)};report(result.note);}
      messages.push({role:'tool',tool_call_id:call.id,content:JSON.stringify(result)});
      if(session.pending||['clarification_required','development_proposal','refused','unsupported'].includes(result.status))return;
    }
    report('Model tool-turn limit reached. Completed actions remain in history; no further actions executed.');
  });
  el('agent-scope-confirm').onclick=()=>run(async()=>{
    const p=pendingScope;cancelScope(); // One-shot, including failures.
    if(!p||p.config!==connected||p.version!==configVersion||p.config.dataset!==bridge.dataset()||p.prompt!==el('chat-request').value.trim()||JSON.stringify(p.before)!==JSON.stringify(fullSnapshot()))throw Error('Display scope expired; request and approve a new proposal.');
    const proposal=ViewTools.validateScopeProposal(p.prompt,p.proposal,{roster:bridge.roster(),renderer:bridge.snapshot().renderer});
    await execute(proposal.action,false);
    el('chat-result').textContent+=' Display scope explicitly approved for this action only.';
  });
  el('agent-scope-cancel').onclick=()=>{cancelScope();report('Display scope cancelled. Nothing changed.');};
  el('agent-confirm').onclick=()=>run(async()=>{
    const result=await session.confirm(session.pending?.id);
    report('Analysis subset executed after explicit confirmation; counts recomputed. Undo restores the previous analysis and display.',result.record_ids);
  });
  el('agent-cancel').onclick=()=>run(async()=>{session.cancel();report('Analysis proposal cancelled. Nothing changed.');});
};
