'use strict';
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const grammar = window.ClinicalGrammar;
grammar.legend(document.querySelector('.legend'));
const storageKey = 'synthetic-lane-review-v1';
const temporalRule = {anchor_domain:'EX',anchor_variable:'EXSTDTC',anchor_occurrence:'first',event_variable:'AESTDTC',direction:'after',lower_days:0,upper_days:30,lower_inclusive:true,upper_inclusive:true,date_policy:'exclude_incomplete_with_diagnostic',missing_anchor_policy:'exclude_patient_with_diagnostic'};
let state = null;
let busy = false;
let displaySort = 'duration';
let tierMode = 'auto';
let highlightIds = [];
const json = value => JSON.stringify(value, null, 2);
async function api(path, body) {
  const options = body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)};
  const response = await fetch('/api/' + path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
async function action(work) {
  if (busy) return;
  busy = true;
  $('error').textContent = '';
  for (const el of document.querySelectorAll('fieldset, #event-selector, .replay button, .replay input')) el.disabled = true;
  try { await work(); }
  catch (error) { $('error').textContent = error.message; if (state) syncControls(); }
  finally {
    busy = false;
    for (const el of document.querySelectorAll('fieldset, #event-selector, .replay button, .replay input')) el.disabled = false;
  }
}
function svgElement(tag, attrs, text) {
  const el = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  if (text !== undefined) el.textContent = text;
  return el;
}
function syncControls() {
  const a = state.spec.analysis_state, v = state.spec.view_state;
  $('severity').value = a.ae_predicate ? a.ae_predicate.value : 'all';
  $('temporal').value = a.temporal_window ? 'explicit' : 'none';
  const populationValue = a.population.length === state.roster.length ? 'all' : JSON.stringify(a.population);
  // Replay may carry any valid subset, including zero patients; don't mislabel it as all.
  if (![...$('population').options].some(o => o.value === populationValue)) {
    $('population').add(new Option('Saved subset (' + a.population.length + ' roster patients)', populationValue));
  }
  $('population').value = populationValue;
  $('sort').value = displaySort;
  const focusValue = v.focus_patient_keys.length ? JSON.stringify(v.focus_patient_keys) : 'all';
  if (![...$('focus').options].some(o => o.value === focusValue)) $('focus').add(new Option('Saved focus subset', focusValue));
  $('focus').value = focusValue;
  for (const input of $('lanes').querySelectorAll('input')) input.checked = v.hidden_lanes.includes(input.value);
  const selector = $('event-selector');
  selector.replaceChildren(new Option('No selected event', ''));
  for (const mark of state.marks) selector.add(new Option(`${mark.patient_key[1]} · ${mark.record_id} · ${grammar.lines(mark,1)[0]} · ${dateLabel(mark)}`, mark.record_id));
  const selected = v.selection?.source_record_ids[0] || '';
  if (selected && ![...selector.options].some(o=>o.value===selected)) selector.add(new Option(`${selected} · hidden; selection retained`, selected));
  selector.value = selected;
}
function render() {
  syncControls();
  const a = state.analysis, spec = state.spec, selection = spec.view_state.selection;
  $('pins').textContent = `Data snapshot: ${spec.snapshot_id} · Rule bundle: ${spec.rule_bundle_id} ${spec.rule_bundle_version} · Contract: ${spec.contract_version}`;
  $('priority-wording').textContent = state.display_config.wording;
  $('priority-config').textContent = `${state.display_config.name} v${state.display_config.version}`;
  $('tier-table').textContent = json(state.display_config);
  $('counts').textContent = `${a.qualifying_patient_count} qualifying patients · ${a.qualifying_ae_record_count} qualifying AE source records`;
  $('denominator').textContent = `Analysis roster denominator: ${a.population_patient_count} patients, ${a.population_ae_record_count} AE source records before qualification. Visible patients: ${state.visible_patient_keys.length}. AE records are not unique clinical episodes.`;
  $('definition').textContent = `AE filter: ${spec.analysis_state.ae_predicate ? 'AESEV = ' + spec.analysis_state.ae_predicate.value : 'none'}. Temporal filter: ${spec.analysis_state.temporal_window ? 'AESTDTC 0–30 days after first complete EXSTDTC, both endpoints inclusive' : 'none'}.`;
  $('diagnostics').textContent = json({analysis_signature:state.analysis_signature,diagnostics:a.diagnostics});
  $('spec').textContent = json(spec);
  $('selection').textContent = selection ? `Selected ${selection.source_record_ids.join(', ')} · ${state.selection_visible ? 'visible' : 'not visible; logical selection retained, mark not pickable'}` : 'No selected event.';
  $('open-source').disabled = !selection;
  const selectedMark = [...state.marks,...state.sentinels].find(m=>m.mark_id===selection?.mark_id);
  $('selected-annotation').textContent = selectedMark ? grammar.selectionLines(selectedMark).join('\n') : '';
  $('sources').replaceChildren();
  $('sources').hidden = true;
  $('coincident-events').hidden = true;
  $('coincident-events').replaceChildren();
  $('empty').textContent = state.visible_patient_keys.length ? '' : 'No visible patients. Check analysis criteria and view-only focus separately.';
  drawTimeline();
}
// Camera is presentation-only, deliberately outside the pinned v1 analysis/spec schema.
const DAY = 86400000, LEFT = 180, RIGHT = 940, UNKNOWN = 1055;
let camera = null, overview = null, targetCamera = null, frame = null;
let animationFrom = null, animationStart = 0;
let inputGeneration=0, focusRecord=null;
function cancelFocus() {
  inputGeneration++;focusRecord=null;
  if(frame!==null)cancelAnimationFrame(frame);
  frame=null;if(camera)targetCamera={...camera};$('timeline').dataset.animating='false';
  window.clinical3d?.stop();
}
function focusMark(mark) {
  if(window.clinical3d)return window.clinical3d.focus(mark);
  // Incomplete dates stay in their dedicated column; never fabricate an onset.
  if(!mark.date){$('status').textContent+=' Date incomplete; full record shown in selection panel.';return;}
  const range=grammar.focusRange(mark,state.display_config,overview.end-overview.start,dateTime(mark.date),dateTime(mark.end_date||mark.date));
  focusRecord=mark.record_id;animateCamera(range);
}
const dateTime = date => Date.parse(date + 'T00:00:00Z');
const smooth = value => { const t = Math.max(0, Math.min(1, value)); return t*t*(3-2*t); };
function initCamera() {
  const dates = [...state.marks,...state.sentinels].flatMap(m => [m.date, m.end_date]).filter(Boolean).map(dateTime);
  const lo = dates.length ? Math.min(...dates) : Date.UTC(2025,0,1);
  const hi = dates.length ? Math.max(lo + DAY, ...dates) : lo + DAY;
  overview = {start:lo-2*DAY, end:hi+2*DAY};
  camera = {...overview}; targetCamera = {...overview};
}
function animateCamera(next) {
  if (window.clinical3d) return window.clinical3d.reset();
  targetCamera = next;
  animationFrom = {...camera}; animationStart = performance.now();
  $('timeline').dataset.animating = 'true';
  if (frame !== null) return;
  const tick = () => {
    const progress = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 1 : Math.min(1,(performance.now()-animationStart)/180);
    const ease = smooth(progress);
    camera.start = animationFrom.start + (targetCamera.start-animationFrom.start)*ease;
    camera.end = animationFrom.end + (targetCamera.end-animationFrom.end)*ease;
    if (progress === 1) camera = {...targetCamera};
    drawTimeline();
    if (progress === 1) { frame = null; $('timeline').dataset.animating = 'false';
      if(focusRecord){const id=focusRecord;focusRecord=null;[...$('timeline').querySelectorAll('.mark')].find(e=>(e.dataset.recordId||e.dataset.sourceRecordId)===id)?.scrollIntoView({block:'center',inline:'nearest'});}
    }
    else frame = requestAnimationFrame(tick);
  };
  frame = requestAnimationFrame(tick);
}
function zoom(factor, fraction=0.5) {
  if (window.clinical3d) return window.clinical3d.zoom(factor);
  if (!camera || busy) return;
  const base = targetCamera;
  const span = base.end-base.start;
  // Click-focus may fit an interval more tightly than the manual two-day floor.
  // Do not turn a subsequent zoom-in into a zoom-out; let zoom-out grow smoothly.
  const minimumSpan = Math.min(2*DAY, span);
  const nextSpan = Math.max(minimumSpan, Math.min(overview.end-overview.start, span*factor));
  // Anchor the date currently under the cursor, even when it moves mid-animation.
  const anchor = camera.start + fraction*(camera.end-camera.start);
  // No boundary clamping: it would move the date under the pointer. Reset restores extent.
  animateCamera({start:anchor-fraction*nextSpan, end:anchor+(1-fraction)*nextSpan});
}
function activateMark(mark) {
  const generation=inputGeneration;
  return action(async () => {
    const evidence = await api('pick',{spec:state.spec,mark_id:mark.mark_id});
    const next = structuredClone(state.spec);
    next.view_state.selection = {mark_id:mark.mark_id,source_record_ids:[mark.record_id]};
    state = await api('evaluate',{spec:next}); render();
    showEvidence(evidence);
    $('status').textContent = `Selected ${mark.record_id}. Source records below show original values and relationship evidence. Analysis unchanged.`;
    if(generation===inputGeneration)focusMark(mark);
  });
}
function dateLabel(mark) {
  const kind = mark.display_kind.replaceAll('_',' ');
  if (!mark.is_interval) return `${kind} ${mark.raw_date || 'date unknown'}`;
  if (mark.end_state==='ongoing') return `${mark.raw_date} → ongoing at ${mark.end_date} (source ${mark.end_source}=${mark.end_date})`;
  if (mark.end_state==='unknown') return `${mark.raw_date || 'start unknown'} → end unknown; no duration imputed${mark.raw_end_date ? ' (raw end '+mark.raw_end_date+')' : ''}`;
  return `${mark.raw_date || 'missing start'} → ${mark.raw_end_date || 'missing end'}${mark.interval_status==='complete' ? '' : ' ('+mark.interval_status.replaceAll('_',' ')+')'}`;
}
function sortedPatients() {
  const summaries = new Map(state.patient_summaries.map(s=>[JSON.stringify(s.patient_key),s]));
  const metric = p => {
    const s = summaries.get(JSON.stringify(p));
    if (displaySort==='duration') return s.treatment_duration===null ? null : -s.treatment_duration;
    if (displaySort==='pd') return s.time_to_pd;
    if (displaySort==='response') return s.best_response===null ? null : state.display_config.response_order.indexOf(s.best_response);
    if (displaySort==='reason') return s.discontinuation_reason;
    return p[1];
  };
  return [...state.visible_patient_keys].sort((a,b)=>{
    const x=metric(a),y=metric(b);
    if(x===null && y!==null) return 1;
    if(y===null && x!==null) return -1;
    const order = typeof x==='number' ? x-y : String(x).localeCompare(String(y));
    return (displaySort==='desc' ? -order : order) || a.join('/').localeCompare(b.join('/'));
  });
}
function clickable(el, callback) {
  el.addEventListener('click',callback);
  el.addEventListener('keydown',event => { if (['Enter',' '].includes(event.key)) { event.preventDefault(); callback(); } });
}
function showCoincident(marks) {
  const panel = $('coincident-events'); panel.replaceChildren(); panel.hidden = false;
  const title = document.createElement('p');
  title.textContent = `${marks[0].patient_key[1]} · ${marks[0].date || 'incomplete dates (not a shared day)'} · ${marks.length} source records. Choose a record or zoom in to separate dated marks.`;
  panel.append(title);
  for (const mark of marks) {
    const button = document.createElement('button'); button.type = 'button';
    button.textContent = `${mark.selectable?'Select':'Inspect'} ${mark.record_id}`;
    button.addEventListener('click',()=>activateMark(mark)); panel.append(button);
  }
  panel.querySelector('button').focus();
}
function drawTimeline() {
  if (window.clinical3d) return window.clinical3d.update({state, patients:sortedPatients(), tierMode, activateMark, dateLabel, cancelFocus, highlightIds});
  if (!camera) initCamera();
  const svg = $('timeline'); svg.replaceChildren();
  if (frame === null) svg.dataset.animating = 'false';
  svg.dataset.start = camera.start; svg.dataset.end = camera.end;
  const span = camera.end-camera.start, pixelsPerDay = (RIGHT-LEFT)*DAY/span;
  const maxTier = tierMode==='auto' ? (span>=overview.end-overview.start ? 0 : span/DAY<=state.display_config.close_zoom_max_days ? 2 : span/DAY<=state.display_config.mid_zoom_max_days ? 1 : 0) : Number(tierMode);
  svg.dataset.maxTier=maxTier;
  const annotationLevel = grammar.level((overview.end-overview.start)/span);
  svg.dataset.annotationLevel=annotationLevel;
  const annotationCandidates=[];
  const detail = smooth((pixelsPerDay-32)/48), spread = smooth((pixelsPerDay-50)/50);
  const width = 1160, blockHeight = state.visible_patient_keys.length > 10 ? 40+72*spread+annotationLevel*24 : 112+annotationLevel*22;
  const height = Math.max(120, 60 + state.visible_patient_keys.length*blockHeight);
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  const x = date => LEFT + (dateTime(date)-camera.start)/span*(RIGHT-LEFT);
  $('zoom-level').textContent = `${(span/DAY).toFixed(1)} days in view · tiers 0–${maxTier} · ${maxTier===0 ? 'sentinel overview' : maxTier===1 ? 'mid detail' : 'close detail'} · view only`;
  const defs = svgElement('defs',{}), clip = svgElement('clipPath',{id:'date-clip'});
  clip.append(svgElement('rect',{x:LEFT-10,y:40,width:RIGHT-LEFT+20,height:height-40})); defs.append(clip); svg.append(defs);
  // Whole-day ticks; never imply sub-day precision in this date-only fixture.
  const tickDays = Math.max(1, Math.ceil(span/DAY/5));
  for (let time = Math.ceil(camera.start/(tickDays*DAY))*tickDays*DAY; time <= camera.end; time += tickDays*DAY) {
    const px = LEFT + (time-camera.start)/span*(RIGHT-LEFT);
    svg.append(svgElement('line',{x1:px,y1:42,x2:px,y2:height,stroke:'#e5ecef'}));
    svg.append(svgElement('text',{x:px,y:27,'text-anchor':'middle'},new Date(time).toISOString().slice(0,10)));
  }
  svg.append(svgElement('text',{x:UNKNOWN,y:27,'text-anchor':'middle'},'Incomplete date'));
  const patientMarks = new Map();
  const allMarks = [...state.marks,...state.sentinels].filter(m=>!m.display_suppressed);
  const displayMarks = allMarks.filter(m=>grammar.visible(m,maxTier,state.display_config));
  for (const mark of displayMarks) {
    const key = JSON.stringify(mark.patient_key);
    if (!patientMarks.has(key)) patientMarks.set(key, []);
    patientMarks.get(key).push(mark);
  }
  for (const [index, patient] of sortedPatients().entries()) {
    const y = 60 + blockHeight/2 + index*blockHeight;
    svg.append(svgElement('text',{x:14,y:y+4,class:'patient','data-patient':patient.join('/')},patient[1]));
    svg.append(svgElement('line',{x1:LEFT,y1:y,x2:RIGHT,y2:y,class:'patient-line',stroke:'#a4b8c3','stroke-width':2}));
    const marks = patientMarks.get(JSON.stringify(patient)) || [];
    const groups = new Map();
    for (const mark of marks) { const key = mark.date || 'incomplete'; if (!groups.has(key)) groups.set(key,[]); groups.get(key).push(mark); }
    const dated = svgElement('g',{'clip-path':'url(#date-clip)'}); svg.append(dated);
    for (const group of groups.values()) {
      // Stable source order, not domain rows. Offsets are local to a coincident date only.
      group.sort((a,b)=>a.record_id.localeCompare(b.record_id));
      const px = group[0].date ? x(group[0].date) : UNKNOWN;
      const parent = group[0].date ? dated : svg;
      // Context first, AE above context, current selection last for overview picking.
      const paintOrder = [...group].sort((a,b)=>Number(a.mark_id===state.spec.view_state.selection?.mark_id)-Number(b.mark_id===state.spec.view_state.selection?.mark_id) || Number(a.lane==='AE')-Number(b.lane==='AE'));
      for (const mark of paintOrder) {
        const hasInterval = ['complete','ongoing'].includes(mark.interval_status);
        const endX = hasInterval ? x(mark.end_date) : px;
        if (mark.date && (endX < LEFT || px > RIGHT)) continue;
        const slot = group.indexOf(mark);
        const offset = group.length > 1 && mark.date ? (slot-(group.length-1)/2)*Math.min(22,72/(group.length-1))*spread : 0;
        const py = y + offset, selected = state.spec.view_state.selection?.mark_id===mark.mark_id;
        const lowEmphasis = ['AE','CM'].includes(mark.lane) && mark.tier!==0 && !selected;
        const opacity = lowEmphasis ? 0.65+0.35*detail : selected || mark.tier===0 ? 1 : 0.35+0.65*detail;
        const r = 6 + 2*detail;
        const domain = grammar.domains[mark.lane], color = domain.color;
        const attrs = {fill:color,color,opacity,class:'mark'+(selected?' selected':''),tabindex:0,role:'button','aria-label':`Select ${mark.record_id}, ${dateLabel(mark)}`,'data-mark-id':mark.mark_id,'data-display-id':mark.display_id,'data-patient-key':patient.join('/'),'data-tier':mark.tier,'data-kind':mark.display_kind,[mark.sentinel_copy?'data-source-record-id':'data-record-id']:mark.record_id,'data-domain':mark.lane,'data-x':px,'data-end-x':endX,'data-y':py,'data-interval-status':mark.interval_status};
        let shape;
        if (hasInterval) {
          shape = svgElement('g',attrs);
          const start = Math.max(LEFT,px), end = Math.min(RIGHT,endX);
          const body=svgElement('g',{class:'interval-body','data-line-treatment':domain.line});
          for(const dy of domain.line==='double'?[-3,3]:[0]) body.append(svgElement('line',{x1:start,x2:end,y1:py+dy,y2:py+dy,stroke:color,'stroke-width':lowEmphasis?1.25:domain.line==='double'?2:5,'vector-effect':'non-scaling-stroke','stroke-linecap':domain.line==='round'?'round':'butt','stroke-dasharray':domain.line==='dashed'&&annotationLevel>0?'5 3':'none'}));
          shape.append(body);
          if(endX>=LEFT&&endX<=RIGHT)shape.append(grammar.terminus(mark.end_state,endX,py,color));
          // A larger transparent target does not imply additional elapsed time.
          shape.append(svgElement('rect',{x:start-3,y:py-8,width:Math.max(6,end-start+6),height:16,fill:'transparent',stroke:'none'}));
        }
        else shape = svgElement('g',attrs);
        if(!mark.date || (px>=LEFT&&px<=RIGHT)) shape.append(grammar.symbol(mark.lane,px,py,r/7));
        const sentinel=grammar.sentinels[mark.display_kind];
        if(sentinel) shape.append(svgElement('text',{class:'sentinel-symbol',x:px+10,y:py+4},sentinel));
        if(mark.is_interval&&!hasInterval) shape.append(grammar.terminus('unknown',px+14,py,color));
        if(highlightIds.includes(mark.record_id)) shape.append(svgElement('rect',{x:px-12,y:py-12,width:24,height:24,fill:'none',stroke:'#a60095','stroke-width':3,'pointer-events':'none','data-highlight-record':mark.record_id}));
        shape.setAttribute('data-symbol',domain.symbol);
        shape.setAttribute('aria-label',`Select ${mark.record_id}, ${grammar.lines(mark,2).join('; ')}`);
        shape.append(svgElement('title',{},`${grammar.lines(mark,2).join(' · ')} · ${mark.record_id} · source row ${mark.source_ref.row_number}`));
        shape.dataset.recordKeys=JSON.stringify(mark.related_death_record_ids||[mark.record_id]);
        clickable(shape,event=>{
          // Use the painted hit geometry, including overlapping interval bodies, not just shared dates.
          let hits=[mark];
          if(event?.clientX!==undefined&&event.detail!==0){
            const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());
            hits=[...svg.querySelectorAll('.mark')].filter(e=>Math.abs(+e.dataset.y-point.y)<=8 && point.x>=Math.max(LEFT,+e.dataset.x)-8 && point.x<=Math.min(RIGHT,Math.max(+e.dataset.x,+e.dataset.endX))+8).flatMap(e=>JSON.parse(e.dataset.recordKeys).map(id=>state.marks.find(m=>m.record_id===id))).filter(Boolean);
          }else if(mark.related_death_record_ids)hits=mark.related_death_record_ids.map(id=>state.marks.find(m=>m.record_id===id));
          hits=[...new Map(hits.map(m=>[m.record_id,m])).values()];
          if(hits.length>1)showCoincident(hits);else activateMark(mark);
        }); parent.append(shape);
        annotationCandidates.push({mark,x:Math.max(LEFT,px),y:py,selected});
      }
      if (group.length > 1 && (!group[0].date || (px>=LEFT && px<=RIGHT))) {
        const badge = svgElement('text',{x:px+12,y:y-blockHeight/2+12,tabindex:0,role:'button',class:'cluster','aria-label':`${group.length} records for ${patient[1]} on ${group[0].date || 'incomplete dates'}`,'data-cluster':patient.join('/')+'/'+(group[0].date || 'incomplete')},`+${group.length-1}`);
        badge.append(svgElement('title',{},'Choose any coincident source record'));
        clickable(badge,()=>showCoincident(group)); parent.append(badge);
      }
    }
  }
  // Layout in screen-sized units; identical collision policy is used by the GPU overlay.
  const scale=svg.getBoundingClientRect().width/width;
  const annotationLayer=svgElement('g',{class:'annotation-layer',transform:`scale(${1/scale})`,'pointer-events':'none'});
  svg.append(annotationLayer);
  grammar.paint(annotationLayer,annotationCandidates.map(c=>({...c,x:c.x*scale,y:c.y*scale})),{left:LEFT*scale,right:(width-8)*scale,top:42*scale,bottom:height*scale},annotationLevel);
  const selectedId = state.spec.view_state.selection?.mark_id;
  const counts = state.visible_patient_keys.map(p=>svg.querySelectorAll(`[data-patient-key="${p.join('/')}"]`).length);
  $('mark-counts').textContent = `${svg.querySelectorAll('.mark').length} displayed marks · per line ${counts.length?Math.min(...counts):0}–${counts.length?Math.max(...counts):0} · ${(counts.reduce((a,b)=>a+b,0)/(counts.length||1)).toFixed(2)} mean. Marks count logical events/intervals, not SVG primitives; analytical totals above are unchanged.`;
  const visible = [...svg.querySelectorAll('.mark')].some(el=>el.dataset.markId===selectedId);
  if (selectedId) $('selection').textContent = `Selected ${state.spec.view_state.selection.source_record_ids.join(', ')} · ${state.selection_visible ? 'visible' : 'not visible; logical selection retained, mark not pickable'}`;
  if (selectedId && state.selection_visible && !visible) $('selection').textContent = `Selected ${state.spec.view_state.selection.source_record_ids.join(', ')} · hidden by display tier or outside zoom viewport; logical selection retained.`;
}
function sourceCard(source) {
  const card = document.createElement('details'); card.className = 'source-card'; card.open = true;
  const heading = document.createElement('summary');
  heading.textContent = `${source.ref.record_id} · ${source.ref.dataset} original row ${source.ref.row_number}`;
  const pre = document.createElement('pre'); pre.textContent = json(source);
  card.append(heading,pre); return card;
}
function showEvidence(evidence) {
  const container = $('sources'); container.replaceChildren(); container.hidden=false;
  for (const source of evidence.source_records) container.append(sourceCard(source));
  for (const supplement of evidence.supplements) {
    const label = document.createElement('p'); label.textContent = `Supplement to ${supplement.parent_source_record_ids.join(', ')}. Not an additional AE record.`;
    container.append(label,sourceCard(supplement.source_record));
  }
  for (const relationship of evidence.relationships) {
    const card = document.createElement('details'); card.className='evidence-card';
    const heading = document.createElement('summary'); heading.textContent=`Relationship evidence: ${relationship.evidence.source_relid}`;
    const text = document.createElement('p'); text.textContent=relationship.explanation;
    const pre = document.createElement('pre'); pre.textContent=json({relationship:relationship.evidence,semantics_documents:relationship.semantics_documents});
    card.append(heading,text,pre);
    for (const source of relationship.source_records) card.append(sourceCard(source));
    container.append(card);
  }
}
async function change(analytical, mutate, message) {
  const next=structuredClone(state.spec); mutate(next);
  state=await api('evaluate',{spec:next,analysis_change:analytical}); render();
  $('replay-result').textContent='';
  $('status').textContent=message + (state.selection_cleared_reason ? ' Selection cleared: analysis_excluded; never retargeted.' : '');
}
function bind() {
  const plot = $('timeline');
  window.ViewGestures.bind(plot, {
    ready:()=>!busy && !!camera && !window.clinical3d,
    interrupt:cancelFocus,
    transform:({from,to,factor})=>{
      const inverse=plot.getScreenCTM().inverse();
      const a=new DOMPoint(from.x,from.y).matrixTransform(inverse);
      const b=new DOMPoint(to.x,to.y).matrixTransform(inverse);
      const span=camera.end-camera.start;
      const nextSpan=Math.max(Math.min(2*DAY,span),Math.min(overview.end-overview.start,span*factor));
      const anchor=camera.start+(a.x-LEFT)/(RIGHT-LEFT)*span;
      const start=anchor-(b.x-LEFT)/(RIGHT-LEFT)*nextSpan;
      camera={start,end:start+nextSpan};targetCamera={...camera};
      // Vertical touch drag navigates the roster inside its scroll container;
      // native page scrolling remains available everywhere outside the plot.
      plot.parentElement.scrollTop-=to.y-from.y;
      drawTimeline();
    },
    tap:(event,target)=>target.dispatchEvent(new MouseEvent('click',{
      bubbles:true,cancelable:true,detail:1,clientX:event.clientX,clientY:event.clientY}))
  });
  $('event-selector').addEventListener('change',()=>{
    const mark = state.marks.find(m=>m.record_id===$('event-selector').value);
    if (mark) activateMark(mark);
    else if (!$('event-selector').value) action(()=>change(false,s=>{s.view_state.selection=null;},'Event selection cleared. Analysis unchanged.'));
  });
  $('timeline').addEventListener('wheel',event => {
    cancelFocus();
    if (!camera || busy) return;
    const matrix = $('timeline').getScreenCTM();
    if (!matrix) return;
    const point = new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());
    if (point.x < LEFT || point.x > RIGHT || !event.deltaY) return;
    event.preventDefault();
    const unit = event.deltaMode===1 ? 16 : event.deltaMode===2 ? 600 : 1;
    const delta = Math.max(-1200,Math.min(1200,event.deltaY*unit));
    zoom(Math.exp(delta*(event.ctrlKey ? 0.012 : 0.0025)),(point.x-LEFT)/(RIGHT-LEFT));
  },{passive:false});
  $('zoom-in').addEventListener('click',()=>zoom(0.65));
  $('zoom-out').addEventListener('click',()=>zoom(1/0.65));
  $('reset-zoom').addEventListener('click',()=>{ if (!busy) animateCamera({...overview}); });
  for (const patient of state.roster) {
    $('population').add(new Option(patient[1],JSON.stringify([patient])));
    $('focus').add(new Option(patient[1],JSON.stringify([patient])));
  }
  for (const lane of ['AE','CM','EX','RS']) {
    const label=document.createElement('label'), input=document.createElement('input');
    input.type='checkbox';input.value=lane;input.id='hide-'+lane;
    label.append(input,document.createTextNode(' Hide '+lane));$('lanes').append(label);
    input.addEventListener('change',()=>action(()=>change(false,s => {s.view_state.hidden_lanes=[...$('lanes').querySelectorAll('input:checked')].map(i=>i.value);},`${lane} marks ${input.checked?'hidden':'shown'} in this view. No patients or records were removed from the analysis.`)));
  }
  $('population').addEventListener('change',()=>action(()=>change(true,s=>{s.analysis_state.population=$('population').value==='all'?state.roster:JSON.parse($('population').value);},'Analysis population updated; patient and AE source-record counts recomputed.')));
  $('severity').addEventListener('change',()=>action(()=>change(true,s=>{s.analysis_state.ae_predicate=$('severity').value==='all'?null:{variable:'AESEV',operator:'eq',value:$('severity').value};},'Analysis filter updated; patient and AE source-record counts recomputed.')));
  $('temporal').addEventListener('change',()=>action(()=>change(true,s=>{s.analysis_state.temporal_window=$('temporal').value==='none'?null:temporalRule;},'Analysis temporal rule updated; counts and exclusion diagnostics recomputed.')));
  $('sort').addEventListener('change',()=>{displaySort=$('sort').value;drawTimeline();$('status').textContent='View-only patient sort changed. Analysis unchanged.';});
  $('tiers').addEventListener('change',()=>{tierMode=$('tiers').value;drawTimeline();$('status').textContent='Display tiers changed. Analysis unchanged; all source records remain selectable.';});
  $('focus').addEventListener('change',()=>action(()=>change(false,s=>{s.view_state.focus_patient_keys=$('focus').value==='all'?[]:JSON.parse($('focus').value);},'View-only focus changed. Analysis unchanged.')));
  $('open-source').addEventListener('click',()=>action(async()=>{ const packageData=await api('export',{spec:state.spec});showEvidence(packageData.selection_evidence); }));
  $('save').addEventListener('click',()=>action(async()=>{ const packageData=await api('export',{spec:state.spec});localStorage.setItem(storageKey,JSON.stringify(packageData));$('replay-result').textContent='Saved exact normalized review locally in this browser.'; }));
  async function replay(packageData) {
    const restored=await api('replay',{package:packageData});state=restored;
    if (frame !== null) cancelAnimationFrame(frame);
    frame=null; camera={...overview}; targetCamera={...overview}; displaySort=state.display_config.default_sort; tierMode='auto'; $('tiers').value='auto'; render();
    if (window.clinical3d) window.clinical3d.reset();
    $('replay-result').textContent=`Replay verified: exact specification restored; analysis and provenance reproduced. Snapshot ${state.spec.snapshot_id}; rule ${state.spec.rule_bundle_id} ${state.spec.rule_bundle_version}.`;
    $('status').textContent='Saved review restored. Snapshot and rule pins verified; no silent fallback.';
  }
  $('replay').addEventListener('click',()=>action(async()=>{ const saved=localStorage.getItem(storageKey);if (!saved) throw new Error('No saved review in this browser. Save a view or import a review JSON.');await replay(JSON.parse(saved)); }));
  $('download').addEventListener('click',()=>action(async()=>{
    const packageData=await api('export',{spec:state.spec});
    const url=URL.createObjectURL(new Blob([json(packageData)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='synthetic-lane-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }));
  $('import').addEventListener('change',()=>action(async()=>{
    const file=$('import').files[0];if (!file) return;
    try {if(file.size>1000000) throw new Error('Review JSON exceeds 1 MB limit.');await replay(JSON.parse(await file.text()));}
    finally {$('import').value='';}
  }));
}
function mountChat() {
  const snapshot=()=>({view:structuredClone(state.spec.view_state),sort:displaySort,tier:tierMode,
    camera:window.clinical3d?window.clinical3d.chatSnapshot():{...camera},highlights:[...highlightIds]});
  const applyCamera=c=>{cancelFocus();if(window.clinical3d)window.clinical3d.chatRestore(c);else {camera={...c};targetCamera={...c};drawTimeline();}};
  async function restore(saved) {
    const spec=structuredClone(state.spec);spec.view_state=structuredClone(saved.view);
    const next=await api('evaluate',{spec});
    state=next;displaySort=saved.sort;tierMode=saved.tier;highlightIds=[...saved.highlights];$('tiers').value=tierMode;
    render();applyCamera(saved.camera);
  }
  window.viewChatBridge={snapshot,restore,roster:()=>state.roster,is3d:()=>!!window.clinical3d,
    busy:()=>busy,signature:()=>state.analysis_signature,
    lock:async work=>{busy=true;const controls=[...document.querySelectorAll('fieldset, .replay button, .replay input, #event-selector')];controls.forEach(e=>e.disabled=true);try{await work();}finally{busy=false;controls.forEach(e=>e.disabled=false);}},
    query:args=>api('view-query',{spec:state.spec,args}),
    records:()=>[...new Set(state.marks.map(m=>m.record_id))].sort(),
    highlight:ids=>{highlightIds=[...ids];drawTimeline();},
    setView:async args=>{
      const saved=snapshot();
      if('sort' in args)saved.sort=args.sort;
      if('tier' in args)saved.tier=args.tier;
      if('focus' in args)saved.view.focus_patient_keys=args.focus===null?[]:state.roster.filter(p=>p[1]===args.focus);
      if('layers' in args)saved.view.hidden_lanes=['AE','CM','EX','RS'].filter(l=>!args.layers.includes(l));
      if(args.camera){
        if(!window.clinical3d)saved.camera=args.camera;
        else {const c=args.camera,d=c.position.map((v,i)=>v-c.target[i]),distance=Math.hypot(...d);
          saved.camera={...saved.camera,x:c.target[0],y:c.target[1],z:c.target[2],yaw:Math.atan2(d[0],d[2]),pitch:Math.asin(d[1]/distance),distance,span:c.span};}
      }
      await restore(saved);
    }
  };
  window.mountViewChat(window.viewChatBridge);
}
action(async()=>{state=await api('initial');displaySort=state.display_config.default_sort;bind();render();mountChat();$('status').textContent=`Deterministic synthetic cohort loaded: ${state.roster.length} patients. No real trial data.`;});
