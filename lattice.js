import * as THREE from 'three';
import {gsap} from 'gsap';
import {DAY, LAYERS, dateNumber, iso, visibleMarks, uniqueSources, summaries, projection, alignedTime, alignmentRoster} from './lattice-model.mjs';

// Independent interaction implementation; external reference code is not used.
// app.js remains the sole owner of engine state, analytical actions and provenance.
const $ = id => document.getElementById(id);
const colors = {AE:'#ff9b87',CM:'#69d5c3',EX:'#c7b0ff',RS:'#ffd17c',DS:'#8dc9ff'};
const symbols = {treatment_start:'▶',first_response:'R',first_pd:'P',death:'†',last_dose:'■',treatment_discontinuation:'D',trial_withdrawal:'W',subsequent_therapy:'N'};
const names = {'full':'Patient × time × visual layer', 'patient-time':'Patient × time · layers collapsed',
  'patient-layer':'Patient × visual layer · time collapsed', 'layer-time':'Visual layer × time · patients collapsed'};
const scene = new THREE.Scene(); scene.background = new THREE.Color('#101b2a');
const camera = new THREE.OrthographicCamera(-1000,1000,800,-800,1,12000);
const view = {yaw:.62,pitch:.38,span:1600,x:0,y:0,z:0};
let model, renderer, atlas, material, mesh, lineMesh, pending=0, tween=null;
let marks=[], cells=[], ptCells=[], ltCells=[], frames=0, tier=-1, mode='full', hitTargets=[], minDate=0,maxDate=DAY;
let row=new Map(), layer=new Map(), fullSpan=1600, currentProjection=projection(view.yaw,view.pitch);
let controlKey='', chosenCell=null, navigationEpoch=0;
const right=new THREE.Vector3(), up=new THREE.Vector3();
const canvas=document.createElement('canvas');canvas.id='scene';canvas.tabIndex=0;
canvas.setAttribute('aria-label','Patient time layer lattice. Drag to rotate; Shift-drag to pan; wheel to zoom. Arrow keys rotate; Home resets.');
$('timeline').hidden=true; $('timeline').after(canvas);
const shell=document.createElement('div');shell.className='lattice-shell';canvas.before(shell);shell.append(canvas);
const annotation=document.createElement('div');annotation.id='lattice-annotation';annotation.hidden=true;shell.append(annotation);
const toolbar=document.createElement('div');toolbar.className='scene-toolbar';toolbar.setAttribute('aria-label','Lattice camera destinations');
for (const key of Object.keys(names)) {
  const b=document.createElement('button');b.id='lattice-'+key;b.textContent=names[key];
  b.onclick=()=>snap(key);toolbar.append(b);
}
shell.before(toolbar);
const info=document.createElement('p');info.id='scene-info';info.setAttribute('role','status');shell.after(info);
const tooltip=document.createElement('p');tooltip.id='scene-tooltip';info.after(tooltip);
const note=document.createElement('p');note.className='small';note.id='lattice-semantics';tooltip.after(note);
const alignmentLabel=document.createElement('p');alignmentLabel.id='lattice-alignment';alignmentLabel.setAttribute('role','status');note.after(alignmentLabel);
const unalignedList=document.createElement('details');unalignedList.id='lattice-unaligned';alignmentLabel.after(unalignedList);
const cellLabel=document.createElement('label');cellLabel.textContent='Projection cell (keyboard drill-down) ';
cellLabel.className='lattice-cell-control';
const cellSelect=document.createElement('select');cellSelect.id='lattice-cell';cellLabel.append(cellSelect);
const openCell=document.createElement('button');openCell.textContent='Inspect contributors';openCell.id='lattice-inspect';
openCell.onclick=()=>showCell(cells.find(c=>c.id===cellSelect.value));cellLabel.append(openCell);note.after(cellLabel);
const contributors=document.createElement('div');contributors.id='lattice-contributors';contributors.hidden=true;
contributors.setAttribute('aria-label','Projection contributing source records');$('coincident-events').after(contributors);
$('zoom-help').textContent='Touch: one finger rotates (or choose Pan); two fingers pan; pinch zooms around your fingers. Tap selects and focuses; overlaps open a chooser. Scroll the page outside the canvas. Mouse: drag to rotate; Shift-drag / right-drag to pan; wheel to zoom. Arrow keys rotate; Home resets. Near an axis, geometry collapses and summaries appear. Any gesture stops focus animation. Camera buttons honour reduced motion.';
document.querySelector('h1').textContent='Patient × time × visual layer';
document.querySelector('.legend').textContent='Domain colors, NOT severity: salmon AE ● · mint CM □ · lilac EX ◆ · amber RS ▲ · blue DS ◆. Sentinel symbols are unchanged; PD P and death † remain explicit. Solid capped interval = recorded end; dashed/open > = documented ongoing follow-up; ? = unknown end, no inferred duration. Hover/select for exact source dates.';
// The common page's last timeline paragraph describes the original 2D geometry.
const timelineSection=canvas.closest('section');
timelineSection.querySelector(':scope > p:last-child').textContent='Axes: calendar date (X), current sorted patient roster (Y), and source-domain visual layer (Z). Display priority tiers are NOT the layer axis. One row per patient when layers collapse. Incomplete dates occupy a separate labeled strip. Blank summary cells mean zero displayed source records, not absence of disease. Focus, hidden domains, zoom and tiers affect these DISPLAY summaries only; authoritative analysis totals stay above.';

function stop(){navigationEpoch++;if(tween){tween.kill();tween=null;}}
function invalidate(){if(!pending)pending=requestAnimationFrame(render);}
function animate(next){
  stop();
  // Do not sleep GSAP's global ticker inside its callbacks: a new tween can
  // wake/render the timeline synchronously before its handle is assigned.
  // GSAP owns ticker auto-sleep; rendering remains invalidation-driven.
  if(matchMedia('(prefers-reduced-motion: reduce)').matches){
    Object.assign(view,next);invalidate();return;
  }
  const active=gsap.to(view,{...next,paused:true,duration:.8,ease:'power3.inOut',
    onUpdate:invalidate,onComplete:()=>{if(tween===active)tween=null;invalidate();}});
  tween=active;active.play();
}
function snap(key){
  const angles={full:[.62,.38],'patient-time':[0,0],'patient-layer':[-Math.PI/2,0],'layer-time':[0,Math.PI/2]};
  const [yaw,pitch]=angles[key];animate({yaw,pitch,x:0,y:0,z:0,span:fullSpan});
}
function focusMark(mark, intent){
  if(intent!==navigationEpoch || !model.state.marks.some(m=>m.record_id===mark.record_id))return;
  // Summary selections return to an uncollapsed view to focus one event.
  const aggregate=['patient-layer','layer-time'].includes(projection(view.yaw,view.pitch).mode);
  const angles=aggregate?{yaw:.62,pitch:.38}:{};
  const targetProjection=aggregate?projection(.62,.38):projection(view.yaw,view.pitch);
  const p=[markX(mark.date,mark),row.get(mark.patient_key.join('/')),layer.get(mark.lane)];
  p[targetProjection.axis]*=1-targetProjection.strength;
  animate({...angles,x:p[0],y:p[1],z:p[2],span:Math.max(8,Math.min(120,fullSpan*model.state.display_config.close_zoom_max_days/((maxDate-minDate)/DAY)*.8))});
}
function applyCamera(){
  const aspect=canvas.clientWidth/canvas.clientHeight;
  camera.left=-view.span*aspect/2;camera.right=view.span*aspect/2;camera.top=view.span/2;camera.bottom=-view.span/2;
  const sy=Math.sin(view.yaw),cy=Math.cos(view.yaw),sp=Math.sin(view.pitch),cp=Math.cos(view.pitch);
  const direction=new THREE.Vector3(sy*cp,sp,cy*cp);
  // An analytic up vector avoids the lookAt pole singularity; pitch is unrestricted.
  up.set(-sy*sp,cp,-cy*sp);right.set(cy,0,-sy);
  camera.up.copy(up);camera.position.set(view.x,view.y,view.z).addScaledVector(direction,view.distance||5000);
  camera.lookAt(view.x,view.y,view.z);camera.updateProjectionMatrix();camera.updateMatrixWorld();
}
const relative=()=>!!model?.alignment && model.alignment.anchor!=='calendar';
const timeX=t=>t===null?730:-600+(t-minDate)/(maxDate-minDate)*1200;
const wx=d=>timeX(d?dateNumber(d):null);
const bucketX=b=>b==='no_qualifying_event'?940:b==='event_date_unresolved'?1180:730;
function markX(d,m){
  const p=model.alignment?.patients.find(p=>p.patient_key.join('/')===m.patient_key.join('/'));
  if(relative() && p?.status!=='resolved')return bucketX(p?.status||'no_qualifying_event');
  return timeX(alignedTime(d,m.patient_key,model.alignment));
}
const tick=i=>minDate+(maxDate-minDate)*i/6;
const tickLabel=i=>relative()?String(Math.round(tick(i)/DAY)):iso(tick(i));
const bucketLabel=b=>b==='no_qualifying_event'?'Unaligned: no qualifying event recorded':b==='event_date_unresolved'?'Unaligned: event recorded but date unresolved':'Incomplete start';
function maxTier(){return model.tierMode!=='auto'?+model.tierMode:
  view.span>=fullSpan?0:(maxDate-minDate)/DAY*view.span/fullSpan<=model.state.display_config.close_zoom_max_days?2:
  (maxDate-minDate)/DAY*view.span/fullSpan<=model.state.display_config.mid_zoom_max_days?1:0;}
function cellText(c){return c.mode==='patient-layer'?`${c.patientKey[1]} · ${c.lane} · ${c.recordCount} source records`:
  `${c.lane} · ${c.start?c.start+' to '+c.end:bucketLabel(c.bucket)} · ${c.patientCount}/${c.denominator} ${relative()&&c.bin!==null?'anchor-resolved visible':'visible group'} patients · ${c.recordCount} source records`;}
function cellPosition(c){return c.mode==='patient-layer'?[0,row.get(c.patientKey.join('/')),layer.get(c.lane)]:
  [c.bin===null?bucketX(c.bucket):timeX((relative()?0:minDate)+(c.bin*30+14.5)*DAY),0,layer.get(c.lane)];}
function makeAtlas(texts){
  const el=document.createElement('canvas');el.width=4096;el.height=4096;
  const ctx=el.getContext('2d'),slots=new Map();let index=0;
  for(const text of new Set(['solid',...Object.values(symbols),'●','□','◆','▲','?','>',...texts])){
    const x=(index%8)*512,y=Math.floor(index/8)*32;index++;
    ctx.fillStyle='white';ctx.font='24px system-ui';ctx.textBaseline='middle';
    if(text==='solid')ctx.fillRect(x,y,32,32);else ctx.fillText(text,x+3,y+16);
    const width=text==='solid'?32:Math.min(510,Math.ceil(ctx.measureText(text).width)+6);
    slots.set(text,{u:x/4096,v:1-(y+32)/4096,w:width/4096,h:32/4096,ratio:width/32});
  }
  if(index>1024)throw new Error('Lattice text atlas capacity exceeded');
  const texture=new THREE.CanvasTexture(el);texture.colorSpace=THREE.SRGBColorSpace;texture.minFilter=THREE.LinearFilter;texture.generateMipmaps=false;
  return {texture,slots};
}
function rebuild(){
  tier=maxTier();marks=visibleMarks(model.state,tier);
  row=new Map(model.patients.map((p,i)=>[p.join('/'),(model.patients.length-1)*6-i*12]));
  // Keep domain coordinates fixed even if a domain is hidden.
  layer=new Map(LAYERS.map((d,i)=>[d,(i-2)*220]));
  ptCells=summaries(marks,model.patients,minDate,'patient-layer',model.state.marks,model.alignment);ltCells=summaries(marks,model.patients,minDate,'layer-time',model.state.marks,model.alignment);
  if(material)material.dispose();if(atlas)atlas.texture.dispose();
  const texts=[...model.patients.map(p=>p[1]),...LAYERS,'Calendar date →','Sorted patients','Visual layers','Incomplete date',
    'Unaligned: no event','Unaligned: unresolved','Days from anchor',
    ...Array.from({length:7},(_,i)=>tickLabel(i)),
    ...ptCells.map(c=>String(c.recordCount)),...ltCells.map(c=>`${c.patientCount}/${c.denominator}`)];
  atlas=makeAtlas(texts);
  material=new THREE.MeshBasicMaterial({map:atlas.texture,vertexColors:true,transparent:true,depthTest:false,side:THREE.DoubleSide,toneMapped:false});
  controlKey=''; chosenCell=null; contributors.hidden=true;invalidate();
}
class Batch{
  constructor(){this.pos=[];this.uv=[];this.col=[];}
  text(p,h,color,key){
    const slot=atlas.slots.get(key),w=slot.ratio*h,c=new THREE.Color(color);
    for(const [a,b] of [[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]]){
      const point=new THREE.Vector3(...p).addScaledVector(right,(a-.5)*w).addScaledVector(up,(b-.5)*h);
      this.pos.push(...point.toArray());this.uv.push(slot.u+a*slot.w,slot.v+b*slot.h);this.col.push(c.r,c.g,c.b);
    }
  }
  geometry(){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(this.pos,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(this.uv,2));g.setAttribute('color',new THREE.Float32BufferAttribute(this.col,3));return g;}
}
function remove(object){if(object){scene.remove(object);object.geometry.dispose();}}
function showRecords(records,title){
  contributors.replaceChildren();contributors.hidden=false;
  const heading=document.createElement('p');heading.textContent=title;contributors.append(heading);
  for(const m of uniqueSources(records).sort((a,b)=>a.record_id.localeCompare(b.record_id))){
    const b=document.createElement('button');b.textContent=`${m.patient_key[1]} · ${m.record_id} · ${m.display_kind} (tier ${m.tier}) · glyph: ${model.dateLabel(m)}${m.source_interval ? ' · source: '+model.dateLabel({...m,...m.source_interval,display_kind:'source_record'}) : ''}`;
    b.onclick=()=>model.activateMark(m);contributors.append(b);
  }
}
function showCell(cell){if(!cell)return;chosenCell=cell.id;cellSelect.value=cell.id;
  showRecords(cell.records,cellText(cell)+` · Source interval end states: ${JSON.stringify(cell.endStates)} · Display kinds: ${cell.displayKinds.join(', ')}. Each source is listed once; sentinel copies are deduplicated. These are display summaries, not analytical endpoints.`);}
function render(){
  pending=0;if(!renderer||!model)return;if(tier!==maxTier())rebuild();
  applyCamera();currentProjection=projection(view.yaw,view.pitch);mode=currentProjection.mode;
  const {axis,strength}=currentProjection, aggregate=axis!==2&&strength>=.5;
  cells=aggregate?(axis===0?ptCells:ltCells):[];
  const scale=[1,1,1];scale[axis]=1-strength;
  const collapse=p=>p.map((v,i)=>v*scale[i]);
  const batch=new Batch(),positions=[],lineColors=[];hitTargets=[];
  const line=(a,b,color)=>{const c=new THREE.Color(color);positions.push(...a,...b);lineColors.push(c.r,c.g,c.b,c.r,c.g,c.b);};
  const h=Math.max(8,view.span/95);
  const glyph=(p,key,color,owner,size=h)=>{batch.text(p,size,color,key);if(owner)hitTargets.push({point:p,owner,radius:Math.max(5,size/view.span*canvas.clientHeight/2)});};
  // The same lattice lines shrink continuously as a coordinate collapses.
  if(!aggregate){
    for(const [patient,y] of row){for(const [lane,z] of layer){
      if(!model.state.lane_order.includes(lane))continue;
      if(axis===2&&strength===1&&lane!==model.state.lane_order[0])continue;
      line(collapse([-600,y,z]),collapse([600,y,z]),'#263d55');
    }}
  }else if(axis===0){for(const y of row.values())line([0,y,-440],[0,y,440],'#263d55');}
  else {for(const z of layer.values())line([-600,0,z],[600,0,z],'#263d55');}
  if(!aggregate){
    // Stable screen-depth ordering is only occlusion handling, never a date offset.
    const ordered=[...marks].sort((a,b)=>Number(a.display_kind==='death'||a.display_kind==='first_pd')-Number(b.display_kind==='death'||b.display_kind==='first_pd'));
    for(const m of ordered){
      const p=collapse([markX(m.date,m),row.get(m.patient_key.join('/')),layer.get(m.lane)]), color=m.display_kind==='death'?'#ffffff':colors[m.lane];
      const end=m.is_interval&&m.date&&m.end_date&&['recorded','ongoing'].includes(m.end_state)&&alignedTime(m.date,m.patient_key,model.alignment)!==null;
      if(end){
        const q=collapse([markX(m.end_date,m),row.get(m.patient_key.join('/')),layer.get(m.lane)]);
        line(p,q,color);hitTargets.push({point:p,end:q,owner:m,radius:5});
        const cap=right.clone().multiplyScalar(0).addScaledVector(up,h*.38);
        line(new THREE.Vector3(...p).sub(cap).toArray(),new THREE.Vector3(...p).add(cap).toArray(),color);
        if(m.end_state==='recorded')line(new THREE.Vector3(...q).sub(cap).toArray(),new THREE.Vector3(...q).add(cap).toArray(),color);
        else {
          glyph(q,'>',color,m);
          // Dashed/open terminus is restricted to documented follow-up, not an extrapolation.
          for(let d=1;d<=3;d++){const a=new THREE.Vector3(...q).addScaledVector(right,-d*h*.25).addScaledVector(up,h*.35);
            line(a.toArray(),a.clone().addScaledVector(right,h*.12).toArray(),color);}
        }
      }else {glyph(p,symbols[m.display_kind]||{AE:'●',CM:'□',EX:'◆',RS:'▲',DS:'◆'}[m.lane],color,m);
        if(m.is_interval)batch.text(new THREE.Vector3(...p).addScaledVector(right,h).toArray(),h,color,'?');}
      if(model.highlightIds?.includes(m.record_id)){
        const corners=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>new THREE.Vector3(...p).addScaledVector(right,x*h).addScaledVector(up,y*h));
        corners.forEach((c,i)=>line(c.toArray(),corners[(i+1)%4].toArray(),'#ff5cdb'));
      }
      if(m.record_id===model.state.spec.view_state.selection?.source_record_ids[0]){
        const a=new THREE.Vector3(...p).addScaledVector(up,-h*.6);line(a.clone().addScaledVector(right,-h*.6).toArray(),a.clone().addScaledVector(right,h*.6).toArray(),'#ffffff');
      }
    }
  }else{
    for(const c of cells){const p=cellPosition(c);if(c.records.some(m=>model.highlightIds?.includes(m.record_id)))glyph(p,'□','#ff5cdb',c,h*2.2);glyph(p,c.mode==='patient-layer'?String(c.recordCount):`${c.patientCount}/${c.denominator}`,colors[c.lane],c,axis===0?Math.min(h,10):h*1.6);}
  }
  // Labels are billboards anchored in the same coordinate system as their axis.
  if(!aggregate||axis===0){
    const stride=view.span<650?1:Math.max(1,Math.ceil(model.patients.length/18));
    for(const [i,p] of model.patients.entries())if(i%stride===0){const pos=aggregate?[0,row.get(p.join('/')),-510]:collapse([-690,row.get(p.join('/')),-440]);batch.text(pos,h*.8,'#c9d8e9',p[1]);}
  }
  if(!aggregate||axis===1){
    for(let i=0;i<=6;i++){const d=tickLabel(i);batch.text(aggregate?[timeX(tick(i)),0,-530]:collapse([timeX(tick(i)),(model.patients.length-1)*6+65,-440]),h*.8,'#c9d8e9',d);}
    batch.text(aggregate?[730,0,-530]:collapse([730,(model.patients.length-1)*6+65,-440]),h*.7,'#c9d8e9','Incomplete date');
    if(relative())for(const [x,label] of [[940,'Unaligned: no event'],[1180,'Unaligned: unresolved']])batch.text(aggregate?[x,0,-530]:collapse([x,(model.patients.length-1)*6+65,-440]),h*.7,'#c9d8e9',label);
    batch.text(aggregate?[0,0,-600]:collapse([0,(model.patients.length-1)*6+110,-440]),h*.8,'#c9d8e9',relative()?'Days from anchor':'Calendar date →');
  }
  if(mode!=='patient-time')for(const [d,z] of layer)if(model.state.lane_order.includes(d)){
    batch.text(aggregate?(axis===0?[0,(model.patients.length-1)*6+45,z]:[-690,0,z]):[-670,(model.patients.length-1)*6+30,z],h,colors[d],d);
  }
  remove(mesh);remove(lineMesh);mesh=new THREE.Mesh(batch.geometry(),material);mesh.renderOrder=2;scene.add(mesh);
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('color',new THREE.Float32BufferAttribute(lineColors,3));
  lineMesh=new THREE.LineSegments(geometry,lineMaterial);scene.add(lineMesh);
  renderer.render(scene,camera);frames++;
  const selected=model.state.spec.view_state.selection?.source_record_ids[0];
  const target=hitTargets.find(t=>t.owner.record_id===selected);
  const detailDays=(maxDate-minDate)/DAY*view.span/fullSpan;
  annotation.hidden=!target || detailDays>model.state.display_config.close_zoom_max_days;
  if(!annotation.hidden){
    const p=project(target.point),rect=canvas.getBoundingClientRect(),m=target.owner;
    annotation.textContent=`${m.patient_key[1]} · ${m.lane} · ${m.annotation||m.display_kind} · ${m.record_id} · ${model.dateLabel(m)}`;
    annotation.style.left=`${Math.max(8,Math.min(rect.width-330,p.x-rect.left+12))}px`;
    annotation.style.top=`${Math.max(8,Math.min(rect.height-100,p.y-rect.top+14))}px`;
    annotation.hidden=p.x<rect.left||p.x>rect.right||p.y<rect.top||p.y>rect.bottom;
  }
  info.textContent=`${names[mode]} · axis-collapse ${Math.round(strength*100)}% · ${renderer.info.render.calls} batched draws · drag to leave this projection`;
  note.textContent=mode==='patient-layer'?'Each cell = distinct contributing source records for this patient and layer, across all displayed dates. Sentinel copies count once. Click to inspect original records and end states. Blank = 0 displayed records.':
    mode==='layer-time'?'Each cell = patients with a displayed record START in this 30-calendar-day bin / current visible patient denominator. This is NOT prevalence, incidence, an arm comparison, or person-time. Repeated starts for a patient count once per cell; patients can appear in multiple bins. Incomplete starts are separate. Click for distinct source records.':
    'Calendar date × sorted patient × source domain. Interval ends remain recorded, documented ongoing, or unknown. Hover/select for exact dates; overlapping records open a chooser. Rotate toward a labeled axis to collapse it; zoom or focus for clinical detail.';
  if(relative())note.textContent=mode==='layer-time'?'Each cell = patients with a displayed source START in a 30 elapsed-calendar-day bin, divided by anchor-resolved visible patients. Unaligned groups have their own denominators. Not incidence, prevalence or an analytical endpoint. Source dates are unchanged.':model.alignment.axis_label+' × sorted patient × source domain. Unaligned events occupy labeled strips, not inferred dates/durations. Original dates remain available on selection. Display only; analysis unchanged.';
  $('zoom-level').textContent=`${(fullSpan/view.span).toFixed(2)}× · tiers 0–${tier} · view only`;
  $('mark-counts').textContent=`${marks.length} display marks · ${uniqueSources(marks).length} distinct displayed source records · ${model.patients.length} visible patients. Analysis totals above are unchanged.`;
  for(const key of Object.keys(names))$('lattice-'+key).setAttribute('aria-pressed',String(key===mode));
  const key=mode+':'+tier+':'+cells.length;
  if(controlKey!==key){controlKey=key;cellLabel.hidden=!aggregate;cellSelect.replaceChildren();
    for(const c of cells)cellSelect.add(new Option(cellText(c),c.id));
    openCell.disabled=!cells.length;
    if(chosenCell&&!cells.some(c=>c.id===chosenCell)){contributors.hidden=true;chosenCell=null;}
  }
}
const lineMaterial=new THREE.LineBasicMaterial({vertexColors:true,depthTest:false,toneMapped:false});
function update(next){
  const first=!model,alignmentChanged=JSON.stringify(model?.alignment)!==JSON.stringify(next.alignment),rosterChanged=model&&JSON.stringify(model.patients)!==JSON.stringify(next.patients);model=next;
  if(first||alignmentChanged){
    const dates=[...model.state.marks,...model.state.sentinels].flatMap(m=>[m.date,m.end_date].map(d=>alignedTime(d,m.patient_key,model.alignment))).filter(d=>d!==null);
    if(relative())dates.push(0);
    minDate=dates.length?Math.min(...dates):Date.UTC(2025,0,1);maxDate=dates.length?Math.max(minDate+DAY,...dates):minDate+DAY;
  }
  if(first){
    try{renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;}
    catch(error){$('error').textContent='WebGL unavailable; use the unchanged 2D route. '+error.message;return;}
    new ResizeObserver(()=>{renderer.setSize(canvas.clientWidth,canvas.clientHeight,false);invalidate();}).observe(canvas);
  }
  if(rosterChanged){contributors.hidden=true;chosenCell=null;}
  const roster=alignmentRoster(model.alignment,model.patients);
  alignmentLabel.textContent=relative()?`${model.alignment.axis_label}; elapsed calendar days, anchor = 0 (not SDTM study day). ${roster.counts.resolved}/${model.patients.length} visible patients resolved; ${roster.counts.no_qualifying_event} no qualifying event recorded; ${roster.counts.event_date_unresolved} event recorded but date unresolved. All remain visible; analysis unchanged.`:'Calendar date (absolute); analysis unchanged.';
  unalignedList.hidden=!relative();unalignedList.replaceChildren();
  if(relative()){
    const summary=document.createElement('summary');summary.textContent='Unaligned patient groups (not excluded or imputed)';unalignedList.append(summary);
    for(const status of ['no_qualifying_event','event_date_unresolved']){
      const p=document.createElement('p');p.textContent=bucketLabel(status)+': '+(model.patients.filter(p=>roster.map.get(JSON.stringify(p))?.status===status).map(p=>p[1]).join(', ')||'None');unalignedList.append(p);
    }
  }
  rebuild();invalidate();window.lattice.ready=true;
  const selected=model.state.spec.view_state.selection?.source_record_ids[0];
  if(selected&&!marks.some(m=>m.record_id===selected))$('selection').textContent=`Selected ${selected} · hidden by view or tier; logical selection retained.`;
}
function project(p){const v=new THREE.Vector3(...p).project(camera),r=canvas.getBoundingClientRect();return {x:r.left+(v.x+1)*r.width/2,y:r.top+(1-v.y)*r.height/2};}
function hits(x,y){
  return hitTargets.filter(t=>{
    const a=project(t.point),b=t.end?project(t.end):a,dx=b.x-a.x,dy=b.y-a.y;
    const fraction=dx||dy?THREE.MathUtils.clamp(((x-a.x)*dx+(y-a.y)*dy)/(dx*dx+dy*dy),0,1):0;
    return Math.hypot(x-a.x-fraction*dx,y-a.y-fraction*dy)<=t.radius;
  }).map(t=>t.owner);
}
canvas.addEventListener('contextmenu',e=>e.preventDefault());
const touchMode=window.ViewGestures.modeToggle(toolbar,()=>model?.cancelFocus());
window.ViewGestures.bind(canvas, {
  ready:()=>!!renderer,
  interrupt:()=>{model.cancelFocus();tooltip.textContent='';},
  touchMode,
  mouseMode:e=>e.shiftKey||e.button===2?'pan':'rotate',
  hover:e=>{if(!renderer)return;const item=hits(e.clientX,e.clientY)[0];tooltip.textContent=item?(item.records?cellText(item):`${item.patient_key[1]} · ${item.record_id} · ${model.dateLabel(item)}`):'';},
  transform:g=>{
    if(g.mode==='rotate'){view.yaw+=(g.to.x-g.from.x)*.005;view.pitch+=(g.to.y-g.from.y)*.005;}
    else {applyCamera();window.ViewGestures.orthographic(view,canvas,right,up,g,THREE.MathUtils.clamp(view.span*g.factor,Math.min(8,view.span),fullSpan*3));}
    invalidate();
  },
  tap:e=>{const choices=hits(e.clientX,e.clientY);const cell=choices.find(c=>c.records);
    if(cell){
      const overlapping=choices.filter(c=>c.records);
      if(overlapping.length>1)showRecords(overlapping.flatMap(c=>c.records),'Overlapping summary cells: choose any contributing source record.');else showCell(cell);
    }else{const records=uniqueSources(choices);if(records.length===1)model.activateMark(records[0]);else if(records.length)showRecords(records,'Overlapping displayed records: choose a source. No dates or patient identities have been displaced.');}}
});
canvas.addEventListener('wheel',e=>{if(!renderer)return;e.preventDefault();stop();const unit=e.deltaMode===1?16:e.deltaMode===2?canvas.clientHeight:1;view.span=THREE.MathUtils.clamp(view.span*Math.exp(e.deltaY*unit*(e.ctrlKey?.01:.002)),8,fullSpan*3);invalidate();},{passive:false});
canvas.addEventListener('keydown',e=>{const directions={ArrowLeft:[-.06,0],ArrowRight:[.06,0],ArrowUp:[0,-.06],ArrowDown:[0,.06]};
  if(e.key==='Home'){e.preventDefault();snap('full');}else if(directions[e.key]){e.preventDefault();stop();view.yaw+=directions[e.key][0];view.pitch+=directions[e.key][1];invalidate();}});
window.lattice={ready:false,update,stop,
  chatSnapshot:()=>({yaw:view.yaw,pitch:view.pitch,span:view.span,x:view.x,y:view.y,z:view.z,distance:view.distance||5000}),
  chatRestore:v=>{stop();Object.assign(view,v);rebuild();invalidate();}, focus:mark=>focusMark(mark,navigationEpoch),focusIntent:()=>navigationEpoch,focusMark,reset:()=>snap('full'),zoom:factor=>animate({span:THREE.MathUtils.clamp(view.span*factor,8,fullSpan*3)}),
  stats:()=>({frames,projection:mode,orthographic:camera.isOrthographicCamera,collapse:{...currentProjection},animating:!!tween,view:{yaw:view.yaw,pitch:view.pitch,span:view.span,x:view.x,y:view.y,z:view.z},marks:marks.length,tier,drawCalls:renderer?.info.render.calls,lines:renderer?.info.render.lines,
    patientOrder:model?.patients.map(p=>p[1]),endStates:marks.reduce((a,m)=>{a[m.end_state]=(a[m.end_state]||0)+1;return a;},{}),
    alignment:model?.alignment?.anchor||'calendar',axisLabel:alignmentLabel.textContent,
    coordinates:marks.map(m=>({record_id:m.record_id,display_kind:m.display_kind,date:m.date,end_date:m.end_date,time:alignedTime(m.date,m.patient_key,model.alignment),x:markX(m.date,m)})),
    cells:cells.map(({records,...c})=>c)}),
  projectRecord:id=>{const t=hitTargets.find(t=>t.owner.record_id===id);return t?project(t.point):null;},
  projectCell:id=>{const t=hitTargets.find(t=>t.owner.id===id);return t?project(t.point):null;}
};
// Existing app.js adapter protocol; the old /3d implementation is untouched.
window.clinical3d=window.lattice;
