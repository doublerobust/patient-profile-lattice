'use strict';
// The sole domain grammar for SVG marks, GPU atlas glyphs, and the compact legend.
// Colors encode domains, never severity. Okabe-Ito Color Universal Design values:
window.ClinicalGrammar = (() => {
  const domains = Object.freeze({
    AE: {name:'Adverse event', color:'#D55E00', symbol:'circle', path:'M 7 0 A 7 7 0 1 0 -7 0 A 7 7 0 1 0 7 0', line:'round'},
    CM: {name:'Concomitant medication', color:'#009E73', symbol:'square', path:'M -6 -6 H 6 V 6 H -6 Z', line:'dashed'},
    EX: {name:'Treatment exposure', color:'#0072B2', symbol:'diamond', path:'M 0 -8 L 8 0 L 0 8 L -8 0 Z', line:'double'},
    RS: {name:'Response / assessment', color:'#E69F00', symbol:'triangle', path:'M 0 -8 L 8 7 H -8 Z', line:null},
    DS: {name:'Disposition', color:'#CC79A7', symbol:'cross', path:'M -2 -8 H 2 V -2 H 8 V 2 H 2 V 8 H -2 V 2 H -8 V -2 H -2 Z', line:null}
  });
  const sentinels = Object.freeze({treatment_start:'▶',first_response:'R',first_pd:'P',death:'†',last_dose:'■',treatment_discontinuation:'D',trial_withdrawal:'W',subsequent_therapy:'N'});
  const NS='http://www.w3.org/2000/svg';
  function svg(tag,attrs={},text) {const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el;}
  function symbol(domain,x,y,size=1) {const d=domains[domain];return svg('path',{d:d.path,transform:`translate(${x} ${y}) scale(${size})`,fill:d.color,stroke:'white','stroke-width':1.2,class:'domain-symbol','data-symbol':d.symbol});}
  function legend(container) {
    container.replaceChildren();
    for(const [domain,d] of Object.entries(domains)) {
      const item=document.createElement('span');item.dataset.legendDomain=domain;
      const icon=svg('svg',{viewBox:'0 0 48 24',width:48,height:24,'aria-hidden':true});
      if(d.line) {
        const ys=d.line==='double'?[9,15]:[12];
        for(const y of ys)icon.append(svg('line',{x1:10,x2:44,y1:y,y2:y,stroke:d.color,'stroke-width':d.line==='double'?2:4,'stroke-dasharray':d.line==='dashed'?'4 3':'none','stroke-linecap':d.line==='round'?'round':'butt'}));
      }
      icon.append(symbol(domain,10,12,.8));item.append(icon,document.createTextNode(`${domain} · ${d.symbol}${d.line?' / '+d.line+' interval':''}`));item.title=d.name;container.append(item);
    }
  }
  // Independent of manual tier overrides: all-tiers overview is still label-free.
  function level(ratio) {return ratio>=5?2:ratio>=2?1:0;}
  function dates(m) {
    const start=m.raw_date||'start unknown';
    if(!m.is_interval)return m.raw_date||'date unknown';
    if(m.end_state==='ongoing')return `${start} → ongoing at last observed ${m.end_date} (${m.end_source})`;
    if(m.end_state==='recorded')return `${start} → ${m.raw_end_date}`;
    return `${start} → end unknown${m.raw_end_date?' (raw '+m.raw_end_date+'; '+m.interval_status.replaceAll('_',' ')+')':''}; no duration imputed`;
  }
  function lines(m,detail=2) {
    const a=m.annotation||{term:m.lane+' term not recorded',fields:{}},f=a.fields;
    let title=`${m.lane} · ${a.term}`;
    if(m.lane==='RS')title+=` · ${f.RSORRES??'result not recorded'}`;
    if(sentinels[m.display_kind])title+=` · ${m.display_kind.replaceAll('_',' ')}`;
    if(detail===1)return [title];
    let clinical='';
    if(m.lane==='AE')clinical=`Severity ${f.AESEV??'not recorded'} · serious ${f.AESER==='Y'?'yes':f.AESER==='N'?'no':f.AESER??'not recorded'} · grade ${f.AETOXGR??'not recorded'}`;
    if(m.lane==='EX'||m.lane==='CM') {
      const dose=f[m.lane+'DOSE'],unit=f[m.lane+'DOSU'],freq=f[m.lane+'DOSFRQ'];
      clinical=`Dose ${dose??'not recorded'}${unit?' '+unit:''}${freq?' · '+freq:''}`;
      if(m.lane==='EX')clinical+=` · ${f.EXADJ??'adjustment not recorded'}`;
    }
    if(m.lane==='DS')clinical=f.DSREAS||'';
    return [title,...(clinical?[clinical]:[]),dates(m)];
  }
  const measureCanvas=document.createElement('canvas'),ctx=measureCanvas.getContext('2d');
  function fit(text,width) {ctx.font='11px system-ui';if(ctx.measureText(text).width<=width)return text;let s=text;while(s&&ctx.measureText(s+'…').width>width)s=s.slice(0,-1);return s+'…';}
  const overlaps=(a,b)=>a.x<b.x+b.w+4&&a.x+a.w+4>b.x&&a.y<b.y+b.h+3&&a.y+a.h+3>b.y;
  function layout(candidates,bounds,detail) {
    if(!detail)return [];
    const chosen=[],perPatient=new Map(),seen=new Set();
    // Only visible anchors; labels never imply an offscreen event is on-screen.
    const visible=candidates.filter(c=>c.x>=bounds.left&&c.x<=bounds.right&&c.y>=bounds.top&&c.y<=bounds.bottom);
    const obstacles=visible.map(c=>({x:c.x-9,y:c.y-9,w:18,h:18}));
    for(const c of [...visible].sort((a,b)=>Number(b.selected)-Number(a.selected)||a.mark.tier-b.mark.tier||a.mark.record_id.localeCompare(b.mark.record_id))) {
      const key=c.mark.patient_key.join('/'),id=c.mark.display_id;
      if(seen.has(id)||(perPatient.get(key)||0)>=(detail===2?4:2))continue;
      const full=lines(c.mark,detail),w=Math.min(310,Math.max(150,bounds.right-bounds.left-20)),h=full.length*15+8;
      const options=[{x:c.x+14,y:c.y-h-16},{x:c.x+14,y:c.y+16},{x:c.x-w-14,y:c.y-h-16},{x:c.x-w-14,y:c.y+16}];
      const place=options.map(p=>({...p,w,h})).find(p=>p.x>=bounds.left&&p.x+p.w<=bounds.right&&p.y>=bounds.top&&p.y+p.h<=bounds.bottom&&!chosen.some(b=>overlaps(p,b))&&!obstacles.some(b=>overlaps(p,b)));
      if(!place)continue;
      chosen.push({...place,...c,anchorX:c.x,anchorY:c.y,x:place.x,y:place.y,lines:full.map(s=>fit(s,w-12)),full});
      seen.add(id);perPatient.set(key,(perPatient.get(key)||0)+1);
      if(chosen.length>=160)break;
    }
    return chosen;
  }
  function paint(layer,candidates,bounds,detail) {
    layer.replaceChildren();layer.dataset.annotationLevel=detail;
    const placed=layout(candidates,bounds,detail);
    for(const p of placed) {
      const group=svg('g',{class:'annotation','data-annotation-for':p.mark.record_id,'data-level':detail});
      group.append(svg('line',{x1:p.anchorX,y1:p.anchorY,x2:p.x+(p.x>p.anchorX?0:p.w),y2:p.y+p.h/2,class:'annotation-leader'}));
      group.append(svg('rect',{x:p.x,y:p.y,width:p.w,height:p.h,rx:4,class:'annotation-bg'}));
      const text=svg('text',{x:p.x+6,y:p.y+15,class:'event-label','data-label-for':p.mark.record_id,opacity:1});
      p.lines.forEach((line,i)=>text.append(svg('tspan',{x:p.x+6,dy:i?15:0},line)));group.append(text);layer.append(group);
    }
    return placed;
  }
  // Visual-layer map owns readable scale; camera units may be dates or GPU world units.
  const visible = (m,tier,config) => !m.display_suppressed && (m.tier<=tier || config.overview_geometry_domains.includes(m.lane));
  function focusRange(m,config,fullSpan,start,end,aspect=1) {
    const layer=config.tiers.find(t=>t.kinds.includes(m.display_kind));
    const readable=fullSpan/layer.detail_zoom*aspect, margin=config.focus_margin_fraction;
    const interval=m.is_interval&&['complete','ongoing'].includes(m.interval_status);
    const duration=interval?Math.max(0,end-start):0, fit=duration/(1-2*margin);
    const startOnly=interval&&fit>readable;
    const span=interval&&duration>0&&!startOnly?fit:readable;
    return {start:startOnly?start-margin*span:start+(duration-span)/2,end:startOnly?start+(1-margin)*span:start+(duration+span)/2,startOnly,detailZoom:layer.detail_zoom};
  }
  function selectionLines(m) {
    const result=lines(m,2);
    if(m.is_interval) {
      const duration=['complete','ongoing'].includes(m.interval_status)?(Date.parse(m.end_date)-Date.parse(m.date))/86400000:null;
      result.push(duration===null?'Duration unknown; no duration imputed':`${m.end_state==='ongoing'?'Observed duration':'Full duration'}: ${duration} days (end − start)`);
      result.push(`End status: ${m.end_state==='recorded'?'recorded end':m.end_state==='ongoing'?'ongoing through documented follow-up':'unknown'}`);
    }
    return result;
  }
  const endpoints=Object.freeze({recorded:{path:'M -1.5 -6 H 1.5 V 6 H -1.5 Z',fill:true},ongoing:{path:'M -5 -6 L 1 0 L -5 6',fill:false},unknown:{path:'M -6 2 Q -3 -5 0 0 Q 3 5 6 -2',fill:false}});
  function terminus(status,x,y,color) {const e=endpoints[status];return svg('path',{d:e.path,transform:`translate(${x} ${y})`,fill:e.fill?color:'none',stroke:color,'stroke-width':e.fill?0:2,'vector-effect':'non-scaling-stroke',class:'end-terminus','data-end-state':status});}
  return Object.freeze({domains,sentinels,symbol,svg,legend,level,lines,dates,layout,paint,visible,focusRange,selectionLines,endpoints,terminus});
})();
