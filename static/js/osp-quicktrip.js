/* osp-quicktrip.js
   Handles Quick Trip flow: modal, optimistic in-progress card, timer,
   offline queue, CSRF handling, undo toast, pull-to-refresh.
   Expects `window.ospConfig` with `csrfToken` and `apiAddTrip` set from Jinja.
*/
(function(){
  'use strict';

  const QUEUE_KEY = 'osp_quick_queue_v1';
  const INPROG_KEY = 'osp_in_progress_v1';

  // DOM helpers
  const $ = (sel, root=document) => root.querySelector(sel);
  const create = (tag, attrs={}, txt='') => { const el = document.createElement(tag); for(const k in attrs) el.setAttribute(k, attrs[k]); if(txt) el.textContent=txt; return el; };

  // Elements (existing in dashboard.html)
  const activeCard = $('#activeTripCard');
  const activeVehicle = $('#activeTripVehicle');
  const activePurpose = $('#activeTripPurpose');
  const activeTimer = $('#activeTripTimer');
  const quickSheet = $('#quickTripSheet');
  const quickBackdrop = $('#quickTripBackdrop');
  const quickConfirmBtn = $('#quickTripConfirmBtn');
  const purposeCustomWrap = $('#quickPurposeCustomWrap');
  const purposeCustomInput = $('#quickPurposeCustom');
  const purposeChips = document.querySelectorAll('.purpose-chip');
  const quickOdo = $('#quickOdoStart');

  let timerInterval = null;

  function nowISO(){ return new Date().toISOString(); }
  function startTimer(ts){
    if(timerInterval) clearInterval(timerInterval);
    function upd(){
      const elapsed = Math.floor((Date.now() - ts)/1000);
      const h = String(Math.floor(elapsed/3600)).padStart(2,'0');
      const m = String(Math.floor((elapsed%3600)/60)).padStart(2,'0');
      const s = String(elapsed%60).padStart(2,'0');
      if(activeTimer) activeTimer.textContent = `${h}:${m}:${s}`;
    }
    upd();
    timerInterval = setInterval(upd,1000);
  }

  function showActive(trip){
    if(!trip) return;
    if(activeVehicle) activeVehicle.textContent = trip.vehicle_name || '—';
    if(activePurpose) activePurpose.textContent = trip.purpose || '—';
    if(activeCard) activeCard.classList.remove('hidden');
    startTimer(new Date(trip.start_ts).getTime());
    localStorage.setItem(INPROG_KEY, JSON.stringify(trip));
  }
  function clearActive(){
    if(activeCard) activeCard.classList.add('hidden');
    if(timerInterval) { clearInterval(timerInterval); timerInterval=null; }
    localStorage.removeItem(INPROG_KEY);
  }

  function toast(msg, {undoLabel, undoFn, timeout=6000}={}){
    const t = create('div', {role:'status','aria-live':'polite'});
    t.className = 'toast fixed left-1/2 -translate-x-1/2 bottom-24 z-60 bg-black text-white px-4 py-2 rounded shadow';
    t.textContent = msg;
    if(undoLabel && undoFn){
      const b = create('button', {type:'button'});
      b.className = 'underline ml-3 text-sm';
      b.textContent = undoLabel;
      b.addEventListener('click', ()=>{ undoFn(); document.body.removeChild(t); });
      t.appendChild(b);
    }
    document.body.appendChild(t);
    setTimeout(()=>{ if(document.body.contains(t)) document.body.removeChild(t); }, timeout);
    return t;
  }

  function saveToQueue(formObj){
    const q = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    q.push(formObj);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  }

  async function flushQueue(){
    const q = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    if(!q.length) return;
    for(let i=0;i<q.length;i++){
      try{
        const form = new FormData();
        for(const k in q[i]) form.append(k, q[i][k]);
        form.append('_csrf_token', window.ospConfig.csrfToken || '');
        const resp = await fetch(window.ospConfig.apiAddTrip, {method:'POST', body: form});
        if(resp.ok){ q.shift(); i--; }
        else break;
      }catch(e){ break; }
    }
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  }

  async function postQuickTrip(formObj){
    const form = new FormData();
    for(const k in formObj) form.append(k, formObj[k]);
    form.append('_csrf_token', window.ospConfig.csrfToken || '');
    try{
      const res = await fetch(window.ospConfig.apiAddTrip, {method:'POST', body: form});
      if(res.ok) return await res.json();
      else throw new Error('Server error');
    }catch(e){ throw e; }
  }

  // Wire purpose chips
  purposeChips.forEach(ch => {
    ch.addEventListener('click', () => {
      const val = ch.dataset.value || '';
      if(val === '__inne__'){
        purposeCustomWrap.classList.remove('hidden');
        purposeCustomInput.focus();
      } else {
        purposeCustomWrap.classList.add('hidden');
        purposeCustomInput.value = '';
      }
      // toggle visual — keep compatibility with existing 'selected' classname
      purposeChips.forEach(c=>{ c.classList.remove('active'); c.classList.remove('selected'); });
      ch.classList.add('active'); ch.classList.add('selected');
    });
  });

  // Confirm quick trip
  async function handleConfirmQuickTrip(){
    // determine chosen vehicle from sheet label, or from page context
    const vehicleName = (document.getElementById('quickVehicleLabel')||{}).textContent || '';
    // driver from server-rendered session username
    const driver = (window.ospConfig && window.ospConfig.currentUser) || '';
    let purposeSel = '';
    const activeChip = document.querySelector('.purpose-chip.active, .purpose-chip.selected');
    if(activeChip) purposeSel = activeChip.dataset.value || '';
    const purpose = purposeSel === '__inne__' ? (purposeCustomInput.value || '') : purposeSel || '';
    const odo_start = quickOdo ? quickOdo.value || '' : '';

    const payload = {
      vehicle_id: (quickConfirmBtn && quickConfirmBtn.dataset && quickConfirmBtn.dataset.vehicleId) || (document.querySelector('[data-vehicle-id]') && document.querySelector('[data-vehicle-id]').dataset.vehicleId) || '',
      driver: driver,
      purpose_select: purposeSel || '',
      purpose_custom: purposeSel === '__inne__' ? (purposeCustomInput.value || '') : '',
      odo_start: odo_start || '',
      date: new Date().toISOString().slice(0,10),
      time_start: new Date().toISOString().slice(11,19),
    };

    // optimistic UI
    const startTs = Date.now();
    const localTrip = { vehicle_name: vehicleName, purpose: purpose || '—', start_ts: new Date(startTs).toISOString(), trip_id: 'local-'+startTs };
    showActive(localTrip);
    if(quickSheet) quickSheet.classList.add('hidden'); if(quickBackdrop) quickBackdrop.classList.add('hidden');

    // toast with undo
    const undo = () => { clearActive(); /* remove from queue if present */
      const q = JSON.parse(localStorage.getItem(QUEUE_KEY)||'[]').filter(item=> item._local_id !== localTrip.trip_id);
      localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
    };
    toast('Wyjazd rozpoczęty', {undoLabel:'Cofnij', undoFn:undo, timeout:7000});

    // attempt POST, on failure enqueue
    try{
      await postQuickTrip(payload);
      // success: try flush any queue
      await flushQueue();
    }catch(e){
      // enqueue for later sync
      payload._local_id = localTrip.trip_id;
      saveToQueue(payload);
    }
    // persist in-progress
    localStorage.setItem(INPROG_KEY, JSON.stringify(localTrip));
    startTimer(startTs);
  }

  // expose global function used by inline onclick attribute
  window.confirmQuickTrip = handleConfirmQuickTrip;
  if(quickConfirmBtn) quickConfirmBtn.addEventListener('click', handleConfirmQuickTrip);

  // restore in-progress on load
  document.addEventListener('DOMContentLoaded', ()=>{
    const inprog = JSON.parse(localStorage.getItem(INPROG_KEY) || 'null');
    if(inprog) showActive(inprog);
    // flush queue when online
    window.addEventListener('online', ()=> flushQueue());
    // initial attempt to flush
    flushQueue();
  });

  // Pull-to-refresh (mobile)
  let touchStartY=0, pulling=false;
  document.addEventListener('touchstart', e=>{ if(document.scrollingElement.scrollTop===0) touchStartY = e.touches[0].clientY; });
  document.addEventListener('touchmove', e=>{
    const dy = e.touches[0].clientY - touchStartY;
    if(dy>100 && !pulling && document.scrollingElement.scrollTop===0){ pulling=true; if(navigator.vibrate) navigator.vibrate(20); location.reload(); }
  });

  // Expose some functions for inline buttons
  window.showQuickSheet = function(vehicleName, vehicleId){
    // set vehicle label and dataset
    const lbl = document.getElementById('quickVehicleLabel'); if(lbl) lbl.textContent = vehicleName || '—';
    if(quickConfirmBtn) quickConfirmBtn.dataset.vehicleId = vehicleId || '';
    quickSheet.classList.remove('hidden'); quickBackdrop.classList.remove('hidden');
    if(navigator.vibrate) navigator.vibrate(10);
  };
  window.closeQuickSheet = function(){ quickSheet.classList.add('hidden'); quickBackdrop.classList.add('hidden'); };

})();
