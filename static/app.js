// ═══════════════════════════════════════════════════════════════// OSP Logbook v2 – Core JS (inline, no external dependencies)
// ═══════════════════════════════════════════════════════════════

// ── Toast System ──────────────────────────────────────────────

function showToast(message, type, duration) {
  // type: 'success' | 'error' | 'info'
  // duration: ms (null = stays until dismissed)
  if (duration === undefined) {
    duration = type === 'error' ? null : 2500;
  }
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast ' + (type || 'info');
  toast.setAttribute('role', 'alert');

  const icons = {
    success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>',
    error:   '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    info:    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
  };

  toast.innerHTML =
    (icons[type] || icons.info) +
    '<span style="flex:1">' + message + '</span>' +
    '<button class="toast-close" aria-label="Zamknij" onclick="dismissToast(this.parentElement)">✕</button>';

  container.prepend(toast);

  if (duration && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    setTimeout(function() { dismissToast(toast); }, duration);
  } else if (duration) {
    // reduced-motion: just remove
    setTimeout(function() { if (toast.parentElement) toast.remove(); }, duration);
  }
}

function dismissToast(toast) {
  if (!toast || !toast.parentElement) return;
  const rm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (rm) { toast.remove(); return; }
  toast.classList.add('toast-out');
  setTimeout(function() { if (toast.parentElement) toast.remove(); }, 260);
}

// ── Auto-save ─────────────────────────────────────────────────

function setupAutoSave(formId) {
  const form = document.getElementById(formId);
  if (!form) return;
  const key = 'form_' + formId;
  try {
    const saved = JSON.parse(localStorage.getItem(key));
    if (saved) {
      Object.entries(saved).forEach(function([name, value]) {
        const field = form.elements[name];
        if (!field) return;
        if (field.type === 'date' || field.type === 'hidden' || String(name).startsWith('_')) return;
        field.value = value;
      });
    }
  } catch(e) {}
  form.addEventListener('change', function() {
    const obj = {};
    for (const [k, v] of new FormData(form)) {
      const field = form.elements[k];
      if (!field) continue;
      if (field.type === 'date' || field.type === 'hidden' || String(k).startsWith('_')) continue;
      obj[k] = v;
    }
    try { localStorage.setItem(key, JSON.stringify(obj)); } catch(e) {}
  });
}

function clearFormAutosave(formId) {
  try { localStorage.removeItem('form_' + formId); } catch(e) {}
}

// ── AJAX Form Submit ──────────────────────────────────────────

function submitForm(formId, endpoint, onSuccess) {
  const form = document.getElementById(formId);
  if (!form) return false;
  const btn = form.querySelector('button[type="submit"]');
  const orig = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Zapisywanie…'; }

  fetch(endpoint, {
    method: 'POST',
    body: new FormData(form),
    headers: { 'Accept': 'application/json' }
  })
  .then(function(r) {
    return r.json().catch(function() { return {}; }).then(function(p) {
      if (!r.ok) throw new Error(p.message || 'Błąd zapisywania.');
      return p;
    });
  })
  .then(function(data) {
    if (data.success) {
      showToast(data.message || 'Zapisano', 'success');
      clearFormAutosave(formId);
      form.reset();
      // reset purpose combo if present
      var ps = document.getElementById('purposeSelect');
      if (ps) { ps.value = ''; }
      var pc = document.getElementById('purposeCustomWrap');
      if (pc) { pc.classList.add('hidden'); }
      if (typeof onSuccess === 'function') onSuccess();
    } else {
      showToast(data.message || 'Błąd', 'error');
    }
  })
  .catch(function(err) { showToast(err.message || 'Błąd sieci', 'error'); })
  .finally(function() { if (btn) { btn.disabled = false; btn.innerHTML = orig; } });

  return false;
}

// ── Vehicle memory ────────────────────────────────────────────

function rememberVehicle(vehicleId, section) {
  try { sessionStorage.setItem('vehicle_' + section, vehicleId); } catch(e) {}
}
function restoreVehicle(selectId, section) {
  const select = document.getElementById(selectId);
  if (!select) return;
  const saved = sessionStorage.getItem('vehicle_' + section);
  if (saved) select.value = saved;
}

// ── Pull-to-Refresh & Sync ────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Check if current page wants auto-refresh
  const wantsRefresh = document.body.getAttribute('data-autorefresh') === 'true';
  let lastRefresh = Date.now();
  
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && wantsRefresh) {
      if (Date.now() - lastRefresh > 300000) { // 5 minutes max wait
        location.reload();
      } else {
        // Soft refresh could go here, for now just reload if it's been over 10s
        if (Date.now() - lastRefresh > 10000) {
            location.reload();
        }
      }
    } else if (document.visibilityState === 'hidden') {
      lastRefresh = Date.now();
    }
  });

  // Support for manual refresh hint (swiping down un-scrollable content)
  let touchStartAreaY = 0;
  document.body.addEventListener('touchstart', (e) => {
    if(window.scrollY === 0) {
      touchStartAreaY = e.touches[0].clientY;
    }
  }, {passive: true});
  
  document.body.addEventListener('touchend', (e) => {
    if (window.scrollY === 0 && wantsRefresh && touchStartAreaY > 0) {
      let touchEndAreaY = e.changedTouches[0].clientY;
      if (touchEndAreaY - touchStartAreaY > 150) { // Pull down threshold
        location.reload();
      }
    }
  }, {passive: true});
});


// ── Odometer calc ─────────────────────────────────────────────

function calculateKm() {
  const start = parseInt(document.getElementById('odo_start')?.value || 0);
  const end   = parseInt(document.getElementById('odo_end')?.value || 0);
  const hint  = document.getElementById('kmHint');
  if (hint && start && end && end > start) {
    hint.textContent = (end - start) + ' km';
    hint.className = 'form-hint success';
  } else if (hint) {
    hint.textContent = '';
    hint.className = 'form-hint';
  }
}

// ── Last-km hint ──────────────────────────────────────────────

function loadLastKm(vehicleId, hintId) {
  const hint = document.getElementById(hintId);
  if (!hint || !vehicleId) { if (hint) hint.textContent = ''; return; }
  fetch('/api/vehicle/' + vehicleId + '/last_km')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.km !== null && d.km !== undefined) {
        const kmFmt = d.km.toLocaleString('pl-PL');
        const daysTxt = d.days_ago === 0 ? 'dzisiaj'
                      : d.days_ago === 1 ? 'wczoraj'
                      : d.days_ago + ' dni temu';
        hint.textContent = 'Ostatni odczyt: ' + kmFmt + ' km · ' + daysTxt;
        hint.className = 'form-hint info';
      } else {
        hint.textContent = 'Brak danych o przebiegu';
        hint.className = 'form-hint';
      }
    })
    .catch(function() { hint.textContent = ''; hint.className = 'form-hint'; });
}

// ── Driver datalist ───────────────────────────────────────────

function loadDrivers(datalistId) {
  fetch('/api/drivers')
    .then(function(r) { return r.json(); })
    .then(function(names) {
      const dl = document.getElementById(datalistId);
      if (!dl) return;
      names.forEach(function(name) {
        const opt = document.createElement('option');
        opt.value = name;
        dl.appendChild(opt);
      });
    })
    .catch(function() {});
}

// ── Purpose combo ─────────────────────────────────────────────

function onPurposeChange(sel) {
  const wrap  = document.getElementById('purposeCustomWrap');
  const input = document.getElementById('purposeCustom');
  if (!wrap) return;
  if (sel.value === '__inne__') {
    wrap.classList.remove('hidden');
    if (input) input.required = true;
  } else {
    wrap.classList.add('hidden');
    if (input) { input.required = false; input.value = ''; }
  }
}

// ── Keyboard shortcuts ────────────────────────────────────────

function setupFormKeyboardShortcuts(formId) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      form.querySelector('button[type="submit"]')?.click();
    }
  });
}

// ── Flash → Toast on load ─────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  const el = document.getElementById('flashMessages');
  if (!el || !el.textContent.trim() || el.textContent.trim() === '[]') return;
  try {
    JSON.parse(el.textContent).forEach(function(pair) {
      const type = pair[0] === 'error' ? 'error' : pair[0] === 'success' ? 'success' : 'info';
      showToast(pair[1], type);
    });
  } catch(e) {}
});
