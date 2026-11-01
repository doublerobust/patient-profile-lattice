import * as THREE from 'three';
import {gsap} from 'gsap';

// View adapter only. It receives the existing engine's immutable response and
// delegates all picking/evidence to app.js. No clinical rules or counts here.
const $=id=>document.getElementById(id);
const scene=new THREE.Scene(); scene.background=new THREE.Color('#101b2a');
const camera=new THREE.OrthographicCamera(-900,900,700,-700,1,12000);
const view={x:880,y:-680,span:1520,yaw:0,pitch:0,peel:0};
let renderer, model, atlas, material, axes, baseline, tiers=[], marks=[], locations=new Map();
let pending=0,tween=null,frames=0,lastTier=-1,lastAnnotation=-1,pan=null,geometryVersion=0;
let lastSymbolScale=-1, atlasKey='';
const symbolScale=()=>Math.min(1,view.span/el.clientHeight);
const metrics={cpu:[],gpu:[]}; let measure=false;
const raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2();
const grammar=window.ClinicalGrammar, symbols=grammar.sentinels;
let minDate=0,maxDate=1,fullSpan=1520;
const day=d=>Date.parse(d+'T00:00:00Z');
const worldX=d=>d?120+(day(d)-minDate)/(maxDate-minDate)*1640:1860;
const el=document.createElement('canvas');el.id='scene';el.tabIndex=0;el.setAttribute('aria-label','GPU patient timeline; drag to pan, Shift-drag to rotate. Source selector below is keyboard accessible.');
$('timeline').hidden=true;$('timeline').parentElement.append(el);
const sceneFrame=document.createElement('div');sceneFrame.className='scene-frame';el.before(sceneFrame);sceneFrame.append(el);
const annotationLayer=grammar.svg('svg',{class:'annotation-layer scene-annotations','aria-hidden':true});sceneFrame.append(annotationLayer);
const toolbar=document.createElement('div');toolbar.className='scene-toolbar';
for(const [id,label] of [['front','Clinical front'],['oblique','Depth view'],['peel','Peel tiers'],['readable','Read detail']]) {const b=document.createElement('button');b.id=id;b.textContent=label;toolbar.append(b);}
sceneFrame.before(toolbar);
const info=document.createElement('p');info.id='scene-info';sceneFrame.after(info);
const tooltip=document.createElement('p');tooltip.id='scene-tooltip';tooltip.setAttribute('role','status');sceneFrame.after(tooltip);
$('zoom-help').textContent='Drag to pan both axes · Shift-drag or right-drag to rotate · wheel/pinch to zoom · camera buttons ease into place. Any pointer-down or wheel immediately stops the tween at its current position. Peel separates display tiers in depth without changing counts. Full-cohort overview is dense: use Read detail or focus a patient to read endpoints.';
document.querySelector('h1').textContent='Clinical timelines · GPU depth study';
const description=document.createElement('p');description.className='small';description.textContent='Vertical cap = recorded end. Dashed/open > = ongoing at documented follow-up. ? = end unknown, no inferred duration. Domain symbols stay alongside sentinel signs; hover/select for full details. Labels appear at 2× / 5× and are suppressed where crowded. Tier depth is display priority, not a clinical value. No bloom/fog.';sceneFrame.after(description);

function stop(){if(tween){tween.kill();tween=null;}gsap.ticker.sleep();}
function invalidate(){if(!pending)pending=requestAnimationFrame(render);}
function animate(next){stop();if(matchMedia('(prefers-reduced-motion: reduce)').matches){Object.assign(view,next);invalidate();return;}tween=gsap.to(view,{...next,duration:0.9,ease:'power3.inOut',onUpdate:invalidate,onComplete:()=>{tween=null;invalidate();gsap.ticker.sleep();}});}
function applyCamera(){
  const aspect=el.clientWidth/el.clientHeight;
  camera.left=-view.span*aspect/2;camera.right=view.span*aspect/2;camera.top=view.span/2;camera.bottom=-view.span/2;
  const direction=new THREE.Vector3(Math.sin(view.yaw)*Math.cos(view.pitch),Math.sin(view.pitch),Math.cos(view.yaw)*Math.cos(view.pitch));
  camera.position.set(view.x,view.y,0).addScaledVector(direction,5000);camera.up.set(0,1,0);camera.lookAt(view.x,view.y,0);camera.updateProjectionMatrix();camera.updateMatrixWorld();
  tiers.forEach((mesh,i)=>{mesh.position.z=i*view.peel;});scene.updateMatrixWorld(true);
}
function maxTier(){if(model.tierMode!=='auto')return +model.tierMode;const days=(maxDate-minDate)/86400000*view.span/fullSpan;return days<=model.state.display_config.close_zoom_max_days?2:days<=model.state.display_config.mid_zoom_max_days?1:0;}
function render(){
  pending=0;if(!renderer||!model)return;
  const start=performance.now();
  const tier=maxTier();if(tier!==lastTier||lastAnnotation!==grammar.level(fullSpan/view.span)||lastSymbolScale!==symbolScale())rebuild();
  applyCamera();
  renderer.render(scene,camera);frames++;
  drawAnnotations();
  if(measure){const submit=performance.now();renderer.getContext().finish();metrics.cpu.push(submit-start);metrics.gpu.push(performance.now()-start);}
  $('zoom-level').textContent=`${(fullSpan/view.span).toFixed(2)}× · tiers 0–${lastTier} · annotation level ${grammar.level(fullSpan/view.span)} · ${view.peel.toFixed(0)} depth separation · view only`;
  info.textContent=`${renderer.info.render.calls} batched draws · ${renderer.info.render.triangles} triangles · ${marks.length} marks · idle rendering pauses`;
}
function dispose(mesh){if(mesh){scene.remove(mesh);mesh.geometry.dispose();}}
function drawAnnotations(){
  const width=el.clientWidth,height=el.clientHeight;
  annotationLayer.setAttribute('viewBox',`0 0 ${width} ${height}`);
  const candidates=[];
  for(const p of locations.values()) {
    const v=new THREE.Vector3(p.x,p.y,p.z+p.tier*view.peel).project(camera);
    candidates.push({mark:p.mark,x:(v.x+1)*width/2,y:(1-v.y)*height/2,selected:p.mark.mark_id===model.state.spec.view_state.selection?.mark_id});
  }
  grammar.paint(annotationLayer,candidates,{left:8,right:width-8,top:8,bottom:height-8},grammar.level(fullSpan/view.span));
}
// One locally-generated atlas contains clinical glyphs and labels. No remote font/image.
function makeAtlas(texts){
  const canvas=document.createElement('canvas');canvas.width=2048;canvas.height=4096;
  const ctx=canvas.getContext('2d'), slots=new Map();
  let index=0;
  function add(key,text,glyph=false){if(slots.has(key))return;const n=index++,x=(n%4)*512,y=Math.floor(n/4)*32;
    ctx.fillStyle='white';ctx.font=glyph?'bold 26px system-ui':'22px system-ui';ctx.textBaseline='middle';
    if(key==='solid')ctx.fillRect(x,y,32,32);
    else if(grammar.domains[key]) {ctx.save();ctx.translate(x+16,y+16);ctx.scale(1.6,1.6);ctx.fill(new Path2D(grammar.domains[key].path));ctx.restore();}
    else if(grammar.endpoints[key]) {const e=grammar.endpoints[key];ctx.save();ctx.translate(x+16,y+16);ctx.scale(1.6,1.6);ctx.strokeStyle='white';ctx.lineWidth=2;const path=new Path2D(e.path);if(e.fill)ctx.fill(path);else ctx.stroke(path);ctx.restore();}
    else ctx.fillText(text,x+3,y+16);
    const width=key==='solid'?32:glyph?32:Math.min(510,Math.ceil(ctx.measureText(text).width)+6);
    slots.set(key,{u:x/2048,v:1-(y+32)/4096,w:width/2048,h:32/4096,ratio:width/32});
  }
  add('solid','',true);for(const symbol of new Set([...Object.keys(grammar.domains),...Object.keys(grammar.endpoints),...Object.values(symbols),'?','>']))add(symbol,symbol,true);
  for(const text of texts)add(text,text);
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.minFilter=THREE.LinearFilter;texture.generateMipmaps=false;
  return {texture,slots};
}
class Batch{
  constructor(){this.pos=[];this.uv=[];this.col=[];this.detail=[];this.owners=[];}
  quad(x,y,z,w,h,color,key='solid',owner=null,detail=0){
    // Keep source glyphs/end shapes readable rather than growing into giant blocks on short-span focus.
    if(owner){h*=symbolScale();if(key!=='solid'||w<=1.5)w*=symbolScale();}
    const slot=atlas.slots.get(key);const c=new THREE.Color(color);const points=[[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]];
    for(const [a,b] of points){this.pos.push(x+(a-.5)*w,y+(b-.5)*h,z);this.uv.push(slot.u+a*slot.w,slot.v+b*slot.h);this.col.push(c.r,c.g,c.b);this.detail.push(detail);}
    this.owners.push(owner,owner);
  }
  text(x,y,z,h,color,text,detail=0,owner=null){this.quad(x+atlas.slots.get(text).ratio*h/2,y,z,atlas.slots.get(text).ratio*h,h,color,text,owner,detail);}
  mesh(){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(this.pos,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(this.uv,2));g.setAttribute('color',new THREE.Float32BufferAttribute(this.col,3));g.setAttribute('detail',new THREE.Float32BufferAttribute(this.detail,1));g.computeBoundingSphere();const mesh=new THREE.Mesh(g,material);mesh.userData.owners=this.owners;scene.add(mesh);return mesh;}
}
function rebuild(){
  if(!model)return;
  geometryVersion++;
  [axes,baseline,...tiers].forEach(dispose);
  lastTier=maxTier();lastAnnotation=grammar.level(fullSpan/view.span);lastSymbolScale=symbolScale();marks=[...model.state.marks,...model.state.sentinels].filter(m=>grammar.visible(m,lastTier,model.state.display_config));locations=new Map();
  const row=new Map(model.patients.map((p,i)=>[p.join('/'),-i*14]));
  const dates=Array.from({length:7},(_,i)=>new Date(minDate+(maxDate-minDate)*i/6).toISOString().slice(0,10));
  const texts=[...model.patients.map(p=>p[1]),...dates,'Incomplete date'];
  if(atlasKey!==JSON.stringify(texts)){
    if(material)material.dispose();if(atlas)atlas.texture.dispose();atlasKey=JSON.stringify(texts);
    atlas=makeAtlas(texts);
    material=new THREE.MeshBasicMaterial({map:atlas.texture,vertexColors:true,alphaTest:0.25,side:THREE.DoubleSide,toneMapped:false});
  }

  const labels=new Batch(),lines=new Batch();
  for(const [i,p] of model.patients.entries()){const y=-i*14;labels.text(-12,y,0,10,'#c9d8e9',p[1]);lines.quad(940,y,-10,1640,.65,'#2e455e');}
  for(const date of dates){const x=worldX(date);labels.text(x-40,25,0,12,'#b3cbe6',date);lines.quad(x,-model.patients.length*7,-11,.65,model.patients.length*14,'#26394f');}
  labels.text(1810,25,0,10,'#b3cbe6','Incomplete date');axes=labels.mesh();baseline=lines.mesh();
  const batches=[new Batch(),new Batch(),new Batch()];
  const groups=new Map();for(const m of marks){const key=m.patient_key.join('/')+'/'+m.date;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(m);}
  for(const m of marks){
    const b=batches[m.tier], x=worldX(m.date), y=row.get(m.patient_key.join('/'));
    const group=groups.get(m.patient_key.join('/')+'/'+m.date);const slot=group.indexOf(m);
    // Small depth offsets keep co-dated marks distinct without fabricating dates.
    const z=slot*3+2, domain=grammar.domains[m.lane];
    const lowEmphasis=['AE','CM'].includes(m.lane)&&m.tier!==0&&m.mark_id!==model.state.spec.view_state.selection?.mark_id;
    const color=lowEmphasis?new THREE.Color(domain.color).lerp(scene.background,.35).getStyle():domain.color;
    const interval=m.is_interval&&['recorded','ongoing'].includes(m.end_state)&&m.date&&m.end_date;
    if(interval){
      const end=worldX(m.end_date);
      if(domain.line==='dashed'&&lastAnnotation>0) {for(let start=x;start<end;start+=9){const stop=Math.min(end,start+5);b.quad((start+stop)/2,y,z,stop-start,lowEmphasis?1.25:2.5,color,'solid',m);}}
      else for(const dy of domain.line==='double'?[-2,2]:[0]) b.quad((x+end)/2,y+dy,z,Math.max(1,end-x),lowEmphasis?1.25:domain.line==='double'?1.2:2.5,color,'solid',m);
      b.quad(end,y,z+.2,16,16,color,m.end_state,m);
    }else{
      if(m.is_interval)b.quad(x+14*symbolScale(),y,z,16,16,color,'unknown',m);
    }
    b.quad(x,y,z+.3,13,13,color,m.lane,m);
    if(symbols[m.display_kind])b.quad(x+12*symbolScale(),y,z+.4,11,11,'#ffffff',symbols[m.display_kind],m);
    if(m.mark_id===model.state.spec.view_state.selection?.mark_id){b.quad(x,y-6*symbolScale(),z+.5,13*symbolScale(),1.5,'#ffffff','solid',m);}
    if(!locations.has(m.record_id)||m.display_kind==='death')locations.set(m.record_id,{x,y,z,tier:m.tier,mark:m});
  }
  tiers=batches.map(b=>b.mesh());
  $('mark-counts').textContent=`${marks.length} logical display marks across ${model.patients.length} patient lines; analysis totals above are unchanged.`;
  const selected=model.state.spec.view_state.selection?.source_record_ids[0];
  if(selected&&!locations.has(selected))$('selection').textContent=`Selected ${selected} · hidden by display tier; logical selection retained.`;
}
function update(next){
  const initial=!model, rosterChanged=model&&model.patients.length!==next.patients.length;model=next;
  if(rosterChanged){stop();fullSpan=Math.max(1400,model.patients.length*14+100);Object.assign(view,{span:fullSpan,y:-model.patients.length*7,x:880});}
  if(initial){
    const dates=[...model.state.marks,...model.state.sentinels].flatMap(m=>[m.date,m.end_date]).filter(Boolean).map(day);minDate=Math.min(...dates);maxDate=Math.max(...dates);fullSpan=Math.max(1400,model.patients.length*14+100);view.span=fullSpan;view.y=-model.patients.length*7;
    try{renderer=new THREE.WebGLRenderer({canvas:el,antialias:true,alpha:false,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;}
    catch(error){$('error').textContent='WebGL unavailable. Use the unchanged 2D clinical view. '+error.message;return;}
    new ResizeObserver(()=>{renderer.setSize(el.clientWidth,el.clientHeight,false);invalidate();}).observe(el);
  }
  rebuild();invalidate();window.clinical3d.ready=true;
}
function hits(clientX,clientY){const r=el.getBoundingClientRect();pointer.set((clientX-r.left)/r.width*2-1,-(clientY-r.top)/r.height*2+1);raycaster.setFromCamera(pointer,camera);return raycaster.intersectObjects(tiers).map(hit=>hit.object.userData.owners[hit.faceIndex]).filter(Boolean);}
el.addEventListener('contextmenu',e=>e.preventDefault());
el.addEventListener('pointerdown',e=>{if(!renderer||![0,2].includes(e.button))return;model.cancelFocus();tooltip.textContent='';pan={id:e.pointerId,x:e.clientX,y:e.clientY,moved:false,rotate:e.shiftKey||e.button===2};el.setPointerCapture(e.pointerId);});
el.addEventListener('pointermove',e=>{
  if(!renderer)return;
  if(!pan){const m=hits(e.clientX,e.clientY)[0];tooltip.textContent=m?`${m.patient_key[1]} · ${m.record_id} · ${grammar.lines(m,2).join(' · ')}`:'';return;}
  const dx=e.clientX-pan.x,dy=e.clientY-pan.y;
  if(Math.abs(dx)+Math.abs(dy)>0)pan.moved=true;
  if(pan.rotate){view.yaw=THREE.MathUtils.clamp(view.yaw+dx*.004,-.85,.85);view.pitch=THREE.MathUtils.clamp(view.pitch+dy*.003,-.55,.55);}
  else {const scale=view.span/el.clientHeight;const right=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,0),up=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,1);view.x+=(-dx*right.x+dy*up.x)*scale;view.y+=(-dx*right.y+dy*up.y)*scale;}
  pan.x=e.clientX;pan.y=e.clientY;invalidate();
});
el.addEventListener('pointerup',e=>{if(!pan)return;const click=!pan.moved;pan=null;el.releasePointerCapture(e.pointerId);if(click){applyCamera();const choices=[...new Map(hits(e.clientX,e.clientY).flatMap(m=>m.related_death_record_ids?m.related_death_record_ids.map(id=>model.state.marks.find(s=>s.record_id===id)).filter(Boolean):[m]).map(m=>[m.record_id,m])).values()];if(choices.length===1)model.activateMark(choices[0]);else if(choices.length){const panel=$('coincident-events');panel.replaceChildren();panel.hidden=false;for(const m of choices){const b=document.createElement('button');b.textContent=`${m.record_id} · ${model.dateLabel(m)}`;b.onclick=()=>model.activateMark(m);panel.append(b);}panel.querySelector('button').focus();}}});
el.addEventListener('pointercancel',()=>{pan=null;});el.addEventListener('lostpointercapture',()=>{pan=null;});
el.addEventListener('wheel',e=>{if(!renderer)return;e.preventDefault();model.cancelFocus();const unit=e.deltaMode===1?16:e.deltaMode===2?el.clientHeight:1;view.span=THREE.MathUtils.clamp(view.span*Math.exp(e.deltaY*unit*(e.ctrlKey?.01:.002)),35,fullSpan*2);invalidate();},{passive:false});
$('front').onclick=()=>animate({yaw:0,pitch:0,peel:0});$('oblique').onclick=()=>animate({yaw:.38,pitch:.15});
$('peel').onclick=()=>animate({peel:view.peel>100?0:180});
$('readable').onclick=()=>{
  const selected=model.state.spec.view_state.selection?.source_record_ids[0];
  const p=locations.get(selected)||[...locations.values()].find(p=>p.mark.patient_key.join('/')===model.patients[0]?.join('/')&&!p.mark.sentinel_copy);
  animate({span:fullSpan/5,x:p?.x??880,y:p?.y??-120,yaw:0,pitch:0,peel:0});
};
function focus(mark){
  const aspect=el.clientWidth/el.clientHeight;
  const range=grammar.focusRange(mark,model.state.display_config,fullSpan,worldX(mark.date),worldX(mark.end_date||mark.date),aspect);
  const row=model.patients.findIndex(p=>p.join('/')===mark.patient_key.join('/'));
  animate({x:(range.start+range.end)/2,y:-row*14,span:(range.end-range.start)/aspect,yaw:0,pitch:0,peel:0});
}
window.clinical3d={ready:false,update,stop,focus,reset:()=>animate({x:880,y:-model.patients.length*7,span:fullSpan,yaw:0,pitch:0,peel:0}),zoom:factor=>animate({span:THREE.MathUtils.clamp(view.span*factor,35,fullSpan*2)}),
  // Audit submitted triangles, not the model list: owners intersecting the clip volume.
  auditGeometry:()=>{
    applyCamera();const owners=new Map();
    for(const mesh of tiers){const positions=mesh.geometry.attributes.position;
      for(let face=0;face<mesh.userData.owners.length;face++){
        const m=mesh.userData.owners[face];if(!m)continue;
        const vs=[0,1,2].map(i=>new THREE.Vector3().fromBufferAttribute(positions,face*3+i).applyMatrix4(mesh.matrixWorld).project(camera));
        if(['x','y','z'].every(k=>Math.max(...vs.map(v=>v[k]))>=-1&&Math.min(...vs.map(v=>v[k]))<=1))owners.set(m.display_id,m);
      }
    }
    return {marks:[...owners.values()].map(m=>({display_id:m.display_id,record_id:m.record_id,lane:m.lane,keys:m.related_death_record_ids||[m.record_id]})),view:{...view},fullSpan,minDate,maxDate,width:el.clientWidth,height:el.clientHeight,patients:model.patients,lastTier};
  },
  stats:()=>({frames,drawCalls:renderer?.info.render.calls,triangles:renderer?.info.render.triangles,marks:marks.length,geometryVersion,animating:!!tween,view:{...view},endStates:marks.reduce((a,m)=>{a[m.end_state]=(a[m.end_state]||0)+1;return a;},{}),patientOrder:model?.patients.map(p=>p[1]),renderer:renderer?.getContext().getParameter(renderer.getContext().RENDERER)}),
  projectRecord:record=>{const p=locations.get(record);applyCamera();const v=new THREE.Vector3(p.x,p.y,p.z+p.tier*view.peel).project(camera),r=el.getBoundingClientRect();return {x:r.left+(v.x+1)*r.width/2,y:r.top+(1-v.y)*r.height/2};},
  startMeasure:()=>{metrics.cpu=[];metrics.gpu=[];measure=true;},endMeasure:()=>{measure=false;return structuredClone(metrics);}
};
gsap.ticker.sleep();
