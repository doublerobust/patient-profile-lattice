'use strict';
// One pointer state machine for SVG and WebGL. Adapters only supply geometry
// transforms and picking; this module never receives clinical state.
window.ViewGestures = (() => {
  function bind(element, adapter) {
    const pointers = new Map();
    let baseline = null, origin = null, dragged = false, tapAllowed = false;
    let target = null, mouseMode = 'pan', dispatchingTap = false, suppressClick = false;
    const point = e => ({x:e.clientX, y:e.clientY});
    const sample = () => {
      const ps = [...pointers.values()].slice(0, 2);
      return {x:ps.reduce((s,p)=>s+p.x,0)/ps.length,
        y:ps.reduce((s,p)=>s+p.y,0)/ps.length,
        distance:ps.length===2 ? Math.hypot(ps[0].x-ps[1].x,ps[0].y-ps[1].y) : 0};
    };
    function clear() {
      const ids = [...pointers.keys()];
      pointers.clear(); baseline=null; origin=null; tapAllowed=false; dragged=false;
      element.classList.remove('panning');
      for (const id of ids) if (element.hasPointerCapture(id)) element.releasePointerCapture(id);
    }
    element.addEventListener('pointerdown', e => {
      if (!adapter.ready() || (e.pointerType!=='touch' && ![0,2].includes(e.button))) return;
      if (!pointers.size) {
        target=e.target; origin=point(e); dragged=false; tapAllowed=e.button===0;
        mouseMode=adapter.mouseMode?.(e)||'pan'; suppressClick=false;
      } else {tapAllowed=false; dragged=true;}
      adapter.interrupt();
      pointers.set(e.pointerId, {...point(e), touch:e.pointerType==='touch'});
      baseline=sample(); // Membership changes rebase without a transform.
      element.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    element.addEventListener('pointermove', e => {
      if (!pointers.has(e.pointerId)) {
        if (!pointers.size) adapter.hover?.(e);
        return;
      }
      const old=pointers.get(e.pointerId);
      pointers.set(e.pointerId,{...point(e),touch:old.touch});
      const next=sample();
      if (!dragged && Math.hypot(next.x-origin.x,next.y-origin.y)<5) return;
      dragged=true; tapAllowed=false; suppressClick=true;
      element.classList.add('panning');
      const mode=pointers.size>1?'pan':old.touch?(adapter.touchMode?.()||'pan'):mouseMode;
      adapter.transform({from:baseline,to:next,mode,
        factor:pointers.size>1 && baseline.distance>0 && next.distance>0 ? baseline.distance/next.distance : 1});
      baseline=next;
      e.preventDefault();
    });
    element.addEventListener('pointerup', e => {
      if (!pointers.has(e.pointerId)) return;
      const tap=tapAllowed && !dragged && pointers.size===1 &&
        Math.hypot(e.clientX-origin.x,e.clientY-origin.y)<5;
      pointers.delete(e.pointerId);
      // Delete before releasing: lostpointercapture is not a cancellation of the survivor.
      if (element.hasPointerCapture(e.pointerId)) element.releasePointerCapture(e.pointerId);
      baseline=pointers.size?sample():null;
      if (pointers.size) {tapAllowed=false; dragged=true;}
      else {element.classList.remove('panning'); origin=null;}
      suppressClick=true;
      if (tap) {
        dispatchingTap=true;
        try {adapter.tap(e,target);} finally {dispatchingTap=false;}
      }
    });
    // A cancelled stream can never pick. Clear all captures on browser/system interruption.
    element.addEventListener('pointercancel', () => {suppressClick=true;clear();});
    element.addEventListener('lostpointercapture', e => {
      if (pointers.has(e.pointerId)) {suppressClick=true;clear();}
    });
    window.addEventListener('blur', clear);
    document.addEventListener('visibilitychange', () => {if(document.hidden)clear();});
    element.addEventListener('click', e => {
      // Keep keyboard/assistive clicks (detail=0); suppress browser compatibility clicks.
      if (!dispatchingTap && suppressClick && e.detail!==0) {e.preventDefault();e.stopImmediatePropagation();}
    }, true);
    return {clear};
  }
  function modeToggle(container, interrupt) {
    let mode='rotate';
    const group=document.createElement('div');group.className='gesture-modes';
    group.setAttribute('role','group');group.setAttribute('aria-label','One-finger touch action');
    const label=document.createElement('span');label.textContent='One finger: ';group.append(label);
    for(const value of ['rotate','pan']) {
      const button=document.createElement('button');button.type='button';button.id='gesture-'+value;
      button.textContent=value==='rotate'?'Rotate':'Pan';button.setAttribute('aria-pressed',String(value===mode));
      button.onclick=()=>{interrupt();mode=value;for(const b of group.querySelectorAll('button'))b.setAttribute('aria-pressed',String(b===button));};
      group.append(button);
    }
    container.append(group);return ()=>mode;
  }
  // Orthographic screen-centred transform, shared by both GPU adapters. Preserve
  // the world point under the old centroid at the new centroid, even when rotated.
  function orthographic(view, element, right, up, gesture, nextSpan) {
    const rect=element.getBoundingClientRect(), {from,to}=gesture;
    const x0=from.x-rect.left-rect.width/2, y0=from.y-rect.top-rect.height/2;
    const x1=to.x-rect.left-rect.width/2, y1=to.y-rect.top-rect.height/2;
    const dx=(x0*view.span-x1*nextSpan)/rect.height;
    const dy=(-y0*view.span+y1*nextSpan)/rect.height;
    for(const key of ['x','y','z'])view[key]=(view[key]||0)+right[key]*dx+up[key]*dy;
    view.span=nextSpan;
  }
  return {bind,modeToggle,orthographic};
})();
