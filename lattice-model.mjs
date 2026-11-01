// View-only projections over engine-supplied marks. No clinical rules are inferred.
export const DAY = 86400000;
export const LAYERS = ['AE', 'CM', 'EX', 'RS', 'DS'];
export const dateNumber = d => Date.parse(d + 'T00:00:00Z');
export const iso = t => new Date(t).toISOString().slice(0, 10);
export function visibleMarks(state, tier) {
  return [...state.marks, ...state.sentinels].filter(m => !m.display_suppressed && m.tier <= tier);
}
export function uniqueSources(marks) {
  return [...new Map(marks.map(m => [m.record_id, m])).values()];
}
// Calendar bins: starts only, not prevalence, duration, person-time, or incidence.
// An incomplete start belongs only to the separate undated bucket.
export function summaries(marks, patients, minDate, mode, sourceMarks = marks) {
  const cells = new Map();
  // A sentinel can reuse a source at a different display date (e.g. last dose).
  // Summaries group source STARTS and end states, never the sentinel's glyph date.
  const sources = new Map(sourceMarks.map(m => [m.record_id, m]));
  for (const displayed of uniqueSources(marks)) {
    const source = sources.get(displayed.record_id) || displayed;
    // Preserve the displayed glyph for picking/focus (last dose, death, etc.),
    // but never use its overridden date or point end state as source metadata.
    const interval = source.source_interval || source;
    const mark = {...displayed, source_interval: interval};
    const bin = interval.date ? Math.floor((dateNumber(interval.date) - minDate) / (30 * DAY)) : null;
    const patientKey = mode === 'patient-layer' ? mark.patient_key : null;
    const id = JSON.stringify([mode, patientKey, mark.lane, mode === 'layer-time' ? bin : null]);
    if (!cells.has(id)) cells.set(id, {id, mode, lane:mark.lane, patientKey,
      bin:mode === 'layer-time' ? bin : null, records:[]});
    cells.get(id).records.push(mark);
  }
  return [...cells.values()].map(c => ({...c,
    recordIds:c.records.map(m=>m.record_id).sort(), recordCount:c.records.length,
    patientCount:new Set(c.records.map(m=>JSON.stringify(m.patient_key))).size,
    denominator:patients.length,
    start:c.mode === 'layer-time' && c.bin !== null ? iso(minDate+c.bin*30*DAY) : null,
    end:c.mode === 'layer-time' && c.bin !== null ? iso(minDate+(c.bin+1)*30*DAY-DAY) : null,
    endStates:c.records.reduce((counts,m)=>{const end=m.source_interval.end_state;counts[end]=(counts[end]||0)+1;return counts;},{}),
    displayKinds:[...new Set(marks.filter(m=>c.records.some(r=>r.record_id===m.record_id)).map(m=>m.display_kind))].filter(Boolean).sort()
  }));
}
// Both signs of every normal work. No mode state is set by the camera buttons.
export function projection(yaw, pitch) {
  const direction = [Math.sin(yaw)*Math.cos(pitch), Math.sin(pitch), Math.cos(yaw)*Math.cos(pitch)];
  const absolute = direction.map(Math.abs), peak = Math.max(...absolute), axis = absolute.indexOf(peak);
  const start = Math.cos(24*Math.PI/180), end = Math.cos(12*Math.PI/180);
  const t = Math.max(0, Math.min(1, (peak-start)/(end-start)));
  const strength = t*t*(3-2*t);
  return {axis, strength, mode:strength >= .5 ? ['patient-layer','layer-time','patient-time'][axis] : 'full'};
}
