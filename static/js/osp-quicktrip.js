/* osp-quicktrip.js
   Quick Trip: optimistic active-trip UI, server sync with CSRF,
   offline queue (localStorage), and undo toast.
*/
(function () {
  'use strict';

  var QUEUE_KEY = 'osp_quick_queue_v2';
  var INTERMEDIATE_QUEUE_KEY = 'osp_quicktrip_queue_v2';
  // Legacy key kept for backwards-compatible localStorage migration.
  var LEGACY_QUEUE_KEY = 'osp_quick_queue_v1';
  var PENDING_UNDO_ID = null;

  function formatLocalTime(now) {
    return String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
  }

  function formatLocalDate(now) {
    return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
  }

  function buildLocalId() {
    return 'quick-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
  }

  function getCsrfToken() {
    if (window.ospConfig && window.ospConfig.csrfToken) {
      var fromConfig = String(window.ospConfig.csrfToken || '').trim();
      if (fromConfig) return fromConfig;
    }

    var meta = document.querySelector('meta[name="csrf-token"]');
    var fromMeta = meta ? (meta.getAttribute('content') || '').trim() : '';
    if (fromMeta) return fromMeta;

    var hidden = document.querySelector('input[name="_csrf_token"]');
    return hidden ? (hidden.value || '').trim() : '';
  }

  function getCurrentDriver() {
    var quickDriverSelect = document.getElementById('quickDriverSelect');
    if (quickDriverSelect) {
      var selected = String(quickDriverSelect.value || '').trim();
      if (selected && selected !== '__manual__') return selected;
    }

    var quickDriverInput = document.getElementById('quickDriver');
    if (quickDriverInput) {
      var fromInput = String(quickDriverInput.value || '').trim();
      if (fromInput) return fromInput;
    }

    if (window.ospConfig && window.ospConfig.currentUser) {
      return String(window.ospConfig.currentUser).trim();
    }
    var topbarName = document.querySelector('.topbar-user span');
    return topbarName ? String(topbarName.textContent || '').trim() : '';
  }

  function getApiEndpoint() {
    if (window.ospConfig && window.ospConfig.apiAddTrip) {
      return window.ospConfig.apiAddTrip;
    }
    return '/api/add_trip';
  }

  function loadQueue() {
    try {
      var parsed = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (_err) {
      return [];
    }
  }

  function saveQueue(queue) {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  }

  function migrateLegacyQueue() {
    if (localStorage.getItem(QUEUE_KEY)) return;

    var legacy;
    try {
      legacy = JSON.parse(localStorage.getItem(INTERMEDIATE_QUEUE_KEY) || localStorage.getItem(LEGACY_QUEUE_KEY) || '[]');
    } catch (_err) {
      legacy = [];
    }
    if (!Array.isArray(legacy) || !legacy.length) return;

    var migrated = legacy.map(function (item, index) {
      var payload = item && item.payload ? item.payload : item;
      // Legacy payloads may contain `_local_id` from older quick-trip drafts.
      var localId = item && (item.localId || item._localId || item._local_id);
      return {
        localId: localId || ('legacy-' + Date.now() + '-' + index),
        payload: payload || {},
        queuedAt: item && item.queuedAt ? item.queuedAt : Date.now()
      };
    }).filter(function (item) {
      return item && item.payload && Object.keys(item.payload).length;
    });

    if (!migrated.length) return;
    saveQueue(migrated);
    localStorage.removeItem(INTERMEDIATE_QUEUE_KEY);
    localStorage.removeItem(LEGACY_QUEUE_KEY);
  }

  function enqueue(payload) {
    var queue = loadQueue();
    queue.push(payload);
    saveQueue(queue);
  }

  function removeFromQueueById(localId) {
    var queue = loadQueue().filter(function (item) {
      return item && item.localId !== localId;
    });
    saveQueue(queue);
  }

  function showUndoToast(localId) {
    var container = document.getElementById('toastContainer');
    if (!container) {
      if (typeof showToast === 'function') showToast('Wyjazd rozpoczęty.', 'success', 2600);
      return;
    }

    var toast = document.createElement('div');
    toast.className = 'toast success';
    toast.setAttribute('role', 'status');

    var text = document.createElement('span');
    text.className = 'toast-message';
    text.textContent = 'Wyjazd rozpoczęty.';

    var undoBtn = document.createElement('button');
    undoBtn.type = 'button';
    undoBtn.className = 'btn btn-sm';
    undoBtn.style.minHeight = '36px';
    undoBtn.style.marginLeft = '6px';
    undoBtn.style.width = 'auto';
    undoBtn.style.padding = '0 12px';
    undoBtn.textContent = 'Cofnij';

    undoBtn.addEventListener('click', function () {
      removeFromQueueById(localId);
      if (window.ActiveTrip && typeof window.ActiveTrip.clear === 'function') {
        window.ActiveTrip.clear();
      }
      if (toast.parentElement) toast.remove();
      PENDING_UNDO_ID = null;
      if (typeof showToast === 'function') showToast('Cofnięto szybki wyjazd.', 'info', 2400);
    });

    toast.appendChild(text);
    toast.appendChild(undoBtn);
    container.appendChild(toast);

    PENDING_UNDO_ID = localId;
    setTimeout(function () {
      if (PENDING_UNDO_ID === localId) PENDING_UNDO_ID = null;
      if (toast.parentElement) {
        toast.classList.add('dismiss');
        setTimeout(function () {
          if (toast.parentElement) toast.remove();
        }, 220);
      }
    }, 7000);
  }

  function syncCardActions(activeData) {
    var completeLink = document.getElementById('activeTripCompleteLink');
    var finishLink = document.getElementById('activeTripFinishLink');
    if (!completeLink && !finishLink) return;

    var vehicleId = activeData && activeData.vehicleId ? String(activeData.vehicleId) : '';
    var base = '/wyjazdy?complete=1';
    var href = vehicleId ? (base + '&vehicle_id=' + encodeURIComponent(vehicleId)) : base;

    if (completeLink) completeLink.setAttribute('href', href);
    if (finishLink) finishLink.setAttribute('href', href + '#trip_time_end');
  }

  function getQuickTripPayload() {
    var sheet = document.getElementById('quickTripSheet');
    if (!sheet) return null;

    var purposeInput = document.getElementById('quickPurposeInput');
    var purposeCustom = purposeInput ? String(purposeInput.value || '').trim() : '';
    if (!purposeCustom) {
      if (typeof showToast === 'function') showToast('Opisz cel wyjazdu.', 'error', 3200);
      if (window.Haptics && typeof window.Haptics.error === 'function') window.Haptics.error();
      return null;
    }
    var purpose = purposeCustom;

    var now = new Date();
    var vehicleId = String(sheet.dataset.vehicleId || '').trim();
    var vehicleName = String(sheet.dataset.vehicleName || '—');
    var quickVehicleSelect = document.getElementById('quickVehicleSelect');
    if (quickVehicleSelect) {
      var selectedOption = quickVehicleSelect.options[quickVehicleSelect.selectedIndex];
      vehicleId = String(quickVehicleSelect.value || '').trim();
      vehicleName = selectedOption
        ? String(selectedOption.dataset.name || selectedOption.textContent || '—').trim()
        : vehicleName;
    }

    if (!vehicleId) {
      if (typeof showToast === 'function') showToast('Brak pojazdu do szybkiego wyjazdu.', 'error', 3200);
      return null;
    }

    var driver = getCurrentDriver();
    if (!driver) {
      if (typeof showToast === 'function') showToast('Podaj kierowcę.', 'error', 3200);
      if (window.Haptics && typeof window.Haptics.error === 'function') window.Haptics.error();
      return null;
    }

    return {
      localId: buildLocalId(),
      vehicleId: vehicleId,
      vehicleName: vehicleName,
      purpose: purpose,
      purpose_select: '__inne__',
      purpose_custom: purposeCustom,
      odoStart: '',
      driver: driver,
      dateStr: formatLocalDate(now),
      timeStartStr: formatLocalTime(now),
      timeStartMs: now.getTime()
    };
  }

  function toRequestBody(activeData) {
    return {
      vehicle_id: activeData.vehicleId,
      date: activeData.dateStr,
      time_start: activeData.timeStartStr,
      driver: activeData.driver || '',
      odo_start: activeData.odoStart || '',
      purpose_select: activeData.purpose_select || '',
      purpose_custom: activeData.purpose_custom || ''
    };
  }

  async function postQuickTrip(payload) {
    var csrf = getCsrfToken();
    var form = new FormData();
    Object.keys(payload).forEach(function (key) {
      var value = payload[key];
      if (value !== undefined && value !== null) form.append(key, value);
    });
    form.append('_csrf_token', csrf);

    var response = await fetch(getApiEndpoint(), {
      method: 'POST',
      body: form,
      headers: {
        Accept: 'application/json',
        'X-CSRFToken': csrf
      }
    });

    var data = {};
    try {
      data = await response.json();
    } catch (_err) {
      data = {};
    }

    if (!response.ok || data.success === false) {
      throw new Error(data.message || 'Nie udało się zapisać wyjazdu.');
    }

    return data;
  }

  async function flushQueue() {
    if (!navigator.onLine) return;

    var queue = loadQueue();
    if (!queue.length) return;

    var remaining = [];
    for (var i = 0; i < queue.length; i++) {
      var item = queue[i];
      if (!item || !item.payload) continue;

      if (PENDING_UNDO_ID && item.localId === PENDING_UNDO_ID) {
        remaining.push(item);
        continue;
      }

      try {
        await postQuickTrip(item.payload);
      } catch (_err) {
        remaining.push(item);
      }
    }

    saveQueue(remaining);
  }

  function queueForRetry(localId, payload) {
    enqueue({
      localId: localId,
      payload: payload,
      queuedAt: Date.now()
    });
  }

  async function handleQuickTripConfirm() {
    var activeData = getQuickTripPayload();
    if (!activeData) return;

    var requestPayload = toRequestBody(activeData);

    if (window.ActiveTrip && typeof window.ActiveTrip.save === 'function') {
      window.ActiveTrip.save(activeData);
      window.ActiveTrip.renderCard();
    }
    syncCardActions(activeData);

    if (typeof closeQuickSheet === 'function') closeQuickSheet();
    if (window.Haptics && typeof window.Haptics.success === 'function') window.Haptics.success();

    showUndoToast(activeData.localId);

    try {
      await postQuickTrip(requestPayload);
      if (typeof showToast === 'function') {
        showToast('Szybki wyjazd zapisany.', 'success', 2600);
      }
      await flushQueue();
    } catch (_err) {
      queueForRetry(activeData.localId, requestPayload);
      if (typeof showToast === 'function') {
        showToast('Brak połączenia — zapisano do kolejki offline.', 'info', 4200);
      }
    }
  }

  function bootstrapQuickTrip() {
    window.confirmQuickTrip = handleQuickTripConfirm;
    migrateLegacyQueue();

    var quickVehicleSelect = document.getElementById('quickVehicleSelect');
    if (quickVehicleSelect) {
      quickVehicleSelect.addEventListener('change', function () {
        var selected = quickVehicleSelect.options[quickVehicleSelect.selectedIndex];
        var nextId = String(quickVehicleSelect.value || '').trim();
        var nextName = selected ? String(selected.dataset.name || selected.textContent || '').trim() : '';
        var sheet = document.getElementById('quickTripSheet');
        if (sheet) {
          sheet.dataset.vehicleId = nextId;
          sheet.dataset.vehicleName = nextName;
        }
        var label = document.getElementById('quickVehicleLabel');
        if (label) label.textContent = nextName || '—';
      });
      quickVehicleSelect.dispatchEvent(new Event('change'));
    }

    var quickDriverSelect = document.getElementById('quickDriverSelect');
    var quickDriver = document.getElementById('quickDriver');
    if (quickDriverSelect && quickDriver) {
      var syncDriverInput = function () {
        var selectedValue = String(quickDriverSelect.value || '').trim();
        if (selectedValue && selectedValue !== '__manual__') {
          quickDriver.value = selectedValue;
          quickDriver.readOnly = true;
          quickDriver.classList.add('quick-trip-readonly');
          return;
        }
        quickDriver.readOnly = false;
        quickDriver.classList.remove('quick-trip-readonly');
        if (!quickDriver.value.trim()) quickDriver.focus();
      };
      quickDriverSelect.addEventListener('change', syncDriverInput);
      syncDriverInput();
    }

    var active = window.ActiveTrip && typeof window.ActiveTrip.load === 'function'
      ? window.ActiveTrip.load()
      : null;
    syncCardActions(active);

    flushQueue();
    window.addEventListener('online', flushQueue);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapQuickTrip);
  } else {
    bootstrapQuickTrip();
  }
})();
