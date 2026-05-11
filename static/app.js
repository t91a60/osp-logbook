// OSP Logbook - Core JS (iOS-style interactions)

const Haptics = {
  light: () => { if(navigator.vibrate) navigator.vibrate(5); },
  success: () => { if(navigator.vibrate) navigator.vibrate([10, 30, 20]); },
  error: () => { if(navigator.vibrate) navigator.vibrate([20, 40, 20, 40, 30]); },
  longPress: () => { if(navigator.vibrate) navigator.vibrate(40); }
};

function _hapticSuccess() { Haptics.success(); }
function _hapticError() { Haptics.error(); }

function _spinnerArcSVG() {
  return '<svg class="spinner-arc" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6"></circle></svg>';
}

function _checkmarkSVG() {
  return '<svg class="checkmark-svg" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5l4 4L16 6.5"></path></svg>';
}

function _toastIcon(type) {
  var map = {
    success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5"></path></svg>',
    error: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M18 6L6 18"></path><path d="M6 6l12 12"></path></svg>',
    info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 10v6"></path><path d="M12 7h.01"></path></svg>'
  };
  return map[type] || map.info;
}

// Toast System
function showToast(message, type, duration) {
  if (duration === undefined) duration = type === "error" ? 3800 : 2600;
  var container = document.getElementById("toastContainer");
  if (!container) return;

  var toast = document.createElement("div");
  toast.className = "toast " + (type || "info");
  toast.setAttribute("role", "alert");
  toast.innerHTML =
    '<span class="toast-icon">' + _toastIcon(type || "info") + '</span>' +
    '<span class="toast-message">' + String(message || "") + '</span>' +
    '<div class="toast-progress"></div>';

  container.appendChild(toast);

  var toasts = container.querySelectorAll(".toast");
  if (toasts.length > 3) {
    toasts[0].classList.add("dismiss");
    setTimeout(function () {
      if (toasts[0] && toasts[0].parentElement) toasts[0].remove();
    }, 220);
  }

  var progress = toast.querySelector(".toast-progress");
  if (progress && duration) {
    progress.style.transition = "transform " + duration + "ms linear";
    requestAnimationFrame(function () {
      progress.style.transform = "scaleX(0)";
    });
  }

  var startY = 0;
  var deltaY = 0;
  toast.addEventListener("touchstart", function (e) {
    startY = e.touches[0].clientY;
    deltaY = 0;
  }, { passive: true });

  toast.addEventListener("touchmove", function (e) {
    deltaY = e.touches[0].clientY - startY;
    if (deltaY < 0) {
      toast.style.transform = "translateY(" + deltaY + "px)";
      toast.style.opacity = String(Math.max(0.25, 1 + deltaY / 120));
    }
  }, { passive: true });

  toast.addEventListener("touchend", function () {
    if (deltaY < -36) {
      toast.classList.add("dismiss");
      setTimeout(function () {
        if (toast.parentElement) toast.remove();
      }, 220);
      return;
    }
    toast.style.transform = "";
    toast.style.opacity = "";
  }, { passive: true });

  if (duration) {
    setTimeout(function () {
      toast.classList.add("dismiss");
      setTimeout(function () {
        if (toast.parentElement) toast.remove();
      }, 220);
    }, duration);
  }
}

function _setButtonLoading(btn) {
  if (!btn) return "";
  var orig = btn.innerHTML;
  btn.disabled = true;
  btn.classList.add("loading");
  btn.innerHTML = _spinnerArcSVG() + " Zapisywanie...";
  return orig;
}

function _flashButtonSuccess(btn, done) {
  if (!btn) {
    if (typeof done === "function") done();
    return;
  }
  btn.classList.remove("loading");
  btn.classList.add("btn-success-flash");
  btn.innerHTML = _checkmarkSVG() + " Zapisano";
  _hapticSuccess();
  setTimeout(function () {
    if (typeof done === "function") done();
  }, 1500);
}

function _resetSubmitButton(btn, original) {
  if (!btn) return;
  btn.disabled = false;
  btn.classList.remove("loading", "btn-success-flash");
  btn.innerHTML = original;
}

// AJAX Form Submit (with X-CSRFToken)
function submitForm(formId, endpoint, onSuccess) {
  var form = document.getElementById(formId);
  if (!form) return false;

  var btn = form.querySelector('button[type="submit"]');
  var original = _setButtonLoading(btn);

  var csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute("content") : "";

  // Background Sync / Offline Queue intercept
  if (!navigator.onLine && 'serviceWorker' in navigator && 'SyncManager' in window) {
    var formDataObj = {};
    new FormData(form).forEach((value, key) => { formDataObj[key] = value; });
    
    _saveToOfflineQueue({
      endpoint: endpoint,
      payload: formDataObj,
      csrfToken: csrfToken
    }).then(() => {
      return navigator.serviceWorker.ready;
    }).then(reg => {
      return reg.sync.register('sync-logbook-entries');
    }).then(() => {
      showToast("Jesteś offline. Zapisano w kolejce. Wpis zsynchronizuje się automatycznie.", "info", 4500);
      clearFormAutosave(formId);
      form.reset();
      _flashButtonSuccess(btn, function () { _resetSubmitButton(btn, original); });
      if (typeof onSuccess === "function") onSuccess();
    }).catch(() => {
      showToast("Nie udało się zapisać offline.", "error");
      _resetSubmitButton(btn, original);
    });
    return false;
  }

  fetch(endpoint, {
    method: "POST",
    body: new FormData(form),
    headers: {
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    },
  })
    .then(function (r) {
      return r
        .json()
        .catch(function () {
          return {};
        })
        .then(function (payload) {
          if (!r.ok) throw new Error(payload.message || "Blad zapisywania.");
          return payload;
        });
    })
    .then(function (data) {
      if (!data.success) throw new Error(data.message || "Blad");

      showToast(data.message || "Zapisano", "success", 2600);
      clearFormAutosave(formId);
      form.reset();

      var purposeSelect = document.getElementById("purposeSelect");
      if (purposeSelect) purposeSelect.value = "";
      var purposeCustom = document.getElementById("purposeCustomWrap");
      if (purposeCustom) purposeCustom.classList.add("hidden");

      _flashButtonSuccess(btn, function () {
        _resetSubmitButton(btn, original);
      });

      if (typeof onSuccess === "function") onSuccess();
    })
    .catch(function (err) {
      _hapticError();
      showToast(err.message || "Blad sieci", "error", 3800);
      _resetSubmitButton(btn, original);
    });

  return false;
}

// IndexedDB Helper for Offline Queue
function _saveToOfflineQueue(item) {
  return new Promise((resolve, reject) => {
    var req = indexedDB.open('osp-offline-db', 1);
    req.onupgradeneeded = function(e) {
      e.target.result.createObjectStore('sync-queue', { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = function() {
      var db = req.result;
      var tx = db.transaction('sync-queue', 'readwrite');
      var addReq = tx.objectStore('sync-queue').add(item);
      addReq.onsuccess = () => resolve();
      addReq.onerror = () => reject();
    };
    req.onerror = () => reject();
  });
}

// Auto-save
function setupAutoSave(formId) {
  var form = document.getElementById(formId);
  if (!form) return;
  var key = "form_" + formId;

  try {
    var saved = JSON.parse(localStorage.getItem(key));
    if (saved) {
      Object.entries(saved).forEach(function (entry) {
        var name = entry[0];
        var value = entry[1];
        var field = form.elements[name];
        if (!field) return;
        if (field.type === "date" || field.type === "hidden" || String(name).startsWith("_")) return;
        field.value = value;
      });
    }
  } catch (e) {}

  form.addEventListener("change", function () {
    var obj = {};
    for (var row of new FormData(form)) {
      var k = row[0];
      var v = row[1];
      var f = form.elements[k];
      if (!f) continue;
      if (f.type === "date" || f.type === "hidden" || String(k).startsWith("_")) continue;
      obj[k] = v;
    }
    try {
      localStorage.setItem(key, JSON.stringify(obj));
    } catch (e) {}
  });
}

function clearFormAutosave(formId) {
  try {
    localStorage.removeItem("form_" + formId);
  } catch (e) {}
}

// Odometer calc
function calculateKm() {
  var start = parseInt((document.getElementById("odo_start") || {}).value || 0, 10);
  var end = parseInt((document.getElementById("odo_end") || {}).value || 0, 10);
  var hint = document.getElementById("kmHint");
  if (hint && start && end && end > start) {
    hint.textContent = end - start + " km";
    hint.className = "form-hint success";
  } else if (hint) {
    hint.textContent = "";
    hint.className = "form-hint";
  }
}

function _skeletonLine() {
  return '<span class="skeleton skeleton-line" style="display:block;height:12px;"></span>';
}

// Last-km hint
function loadLastKm(vehicleId, hintId) {
  var hint = document.getElementById(hintId);
  if (!hint || !vehicleId) {
    if (hint) hint.textContent = "";
    return;
  }

  hint.innerHTML = _skeletonLine();

  fetch("/api/vehicle/" + vehicleId + "/last_km")
    .then(function (r) {
      return r.json();
    })
    .then(function (d) {
      if (d.km !== null && d.km !== undefined) {
        var kmFmt = Number(d.km).toLocaleString("pl-PL");
        var daysTxt = d.days_ago === 0 ? "dzisiaj" : d.days_ago === 1 ? "wczoraj" : d.days_ago + " dni temu";
        hint.textContent = "Ostatni odczyt: " + kmFmt + " km - " + daysTxt;
        hint.className = "form-hint info";
      } else {
        hint.textContent = "Brak danych o przebiegu";
        hint.className = "form-hint";
      }
    })
    .catch(function () {
      hint.textContent = "";
      hint.className = "form-hint";
    });
}

// Driver datalist
function loadDrivers(datalistId) {
  var dl = document.getElementById(datalistId);
  if (!dl) return;

  dl.innerHTML = '<option class="skeleton" value="Ladowanie..."></option>';

  fetch("/api/drivers")
    .then(function (r) {
      return r.json();
    })
    .then(function (names) {
      dl.innerHTML = "";
      names.forEach(function (name) {
        var opt = document.createElement("option");
        opt.value = name;
        dl.appendChild(opt);
      });
    })
    .catch(function () {
      dl.innerHTML = "";
    });
}

// Purpose combo
function onPurposeChange(sel) {
  var wrap = document.getElementById("purposeCustomWrap");
  var input = document.getElementById("purposeCustom");
  if (!wrap) return;

  if (sel.value === "__inne__") {
    wrap.classList.remove("hidden");
    if (input) input.required = true;
  } else {
    wrap.classList.add("hidden");
    if (input) {
      input.required = false;
      input.value = "";
    }
  }
}

// Vehicle memory
function rememberVehicle(vehicleId, section) {
  try {
    sessionStorage.setItem("vehicle_" + section, vehicleId);
  } catch (e) {}
}

function restoreVehicle(selectId, section) {
  var select = document.getElementById(selectId);
  if (!select) return;
  var saved = sessionStorage.getItem("vehicle_" + section);
  if (saved) select.value = saved;
}

// Keyboard shortcuts
function setupFormKeyboardShortcuts(formId) {
  var form = document.getElementById(formId);
  if (!form) return;

  form.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.click();
    }
  });
}

// Flash -> Toast
document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("flashMessages");
  if (!el || !el.textContent.trim() || el.textContent.trim() === "[]") return;

  try {
    JSON.parse(el.textContent).forEach(function (pair) {
      var type = pair[0] === "error" ? "error" : pair[0] === "success" ? "success" : "info";
      showToast(pair[1], type);
    });
  } catch (e) {}
});

function _setupTopbarShadow() {
  var topbar = document.querySelector(".topbar");
  if (!topbar) return;

  window.addEventListener("scroll", function () {
    topbar.classList.toggle("scrolled", window.scrollY > 0);
  }, { passive: true });
}

function _setupNavHaptics() {
  var links = document.querySelectorAll(".nav-link");
  links.forEach(function (link) {
    link.addEventListener("click", function () {
      _hapticSuccess();
    }, { passive: true });
  });
}

function _setupCountUp() {
  var candidates = document.querySelectorAll(".stat-number, .card div[style*='font-size:1.8rem']");
  if (!candidates.length) return;

  var animate = function (el) {
    var target = parseInt(String(el.textContent || "").replace(/\s+/g, "").replace(/[^0-9-]/g, ""), 10);
    if (!Number.isFinite(target) || target < 0) return;

    var start = performance.now();
    var duration = 600;

    var tick = function (now) {
      var p = Math.min(1, (now - start) / duration);
      var eased = 1 - Math.pow(1 - p, 3);
      var value = Math.round(target * eased);
      el.textContent = value.toLocaleString("pl-PL");
      if (p < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  };

  var observer = new IntersectionObserver(function (entries, obs) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        animate(entry.target);
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.35 });

  candidates.forEach(function (el) {
    observer.observe(el);
  });
}

function _setupPullToRefresh() {
  var indicator = document.createElement("div");
  indicator.className = "pull-indicator";
  indicator.innerHTML = _spinnerArcSVG();
  document.body.appendChild(indicator);

  var startY = 0;
  var pull = 0;
  var armed = false;

  document.body.addEventListener("touchstart", function (e) {
    if (window.scrollY <= 0) {
      startY = e.touches[0].clientY;
      pull = 0;
      armed = false;
      document.body.style.transition = 'none';
    }
  }, { passive: true });

  document.body.addEventListener("touchmove", function (e) {
    if (window.scrollY > 0 || !startY) return;
    pull = (e.touches[0].clientY - startY) * 0.45; // Spring resistance
    if (pull > 0) {
      document.body.style.transform = "translateY(" + pull + "px)";
    }
    if (pull > 8) indicator.classList.add("visible");
    if (pull > 65) armed = true;
  }, { passive: false });

  document.body.addEventListener("touchend", function () {
    if (!startY) return;
    document.body.style.transition = 'transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
    document.body.style.transform = '';
    
    if (armed) {
      indicator.classList.add("visible");
      Haptics.success();
      setTimeout(function () {
        window.location.reload();
      }, 500);
    } else {
      indicator.classList.remove("visible");
    }
    startY = 0;
    pull = 0;
    armed = false;
  }, { passive: true });
}

function _setupSwipeToDelete() {
  var entries = document.querySelectorAll(".entry");
  entries.forEach(function (entry) {
    var deleteBtn = entry.querySelector(".btn-danger");
    if (!deleteBtn) return;

    var startX = 0;
    var deltaX = 0;
    var active = false;

    entry.addEventListener("touchstart", function (e) {
      startX = e.touches[0].clientX;
      deltaX = 0;
      active = true;
      entry.classList.add("swiping");
    }, { passive: true });

    entry.addEventListener("touchmove", function (e) {
      if (!active) return;
      deltaX = e.touches[0].clientX - startX;
      if (deltaX < 0) {
        var x = Math.max(-88, deltaX);
        entry.style.transform = "translateX(" + x + "px)";
      }
    }, { passive: true });

    entry.addEventListener("touchend", function () {
      if (!active) return;
      entry.classList.remove("swiping");
      if (deltaX < -80) {
        entry.classList.add("swiped");
        entry.style.transform = "translateX(-84px)";
        _hapticError();
      } else {
        entry.classList.remove("swiped");
        entry.style.transform = "";
      }
      active = false;
    }, { passive: true });
  });
}

// Page init
document.addEventListener("DOMContentLoaded", function () {
  var vp = document.querySelector('meta[name="viewport"]');
  if (vp && vp.content.indexOf("viewport-fit") === -1) vp.content += ", viewport-fit=cover";

  var wantsRefresh = document.body.getAttribute("data-autorefresh") === "true";
  var lastHidden = null;

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      lastHidden = Date.now();
    } else if (document.visibilityState === "visible" && wantsRefresh && lastHidden) {
      if (Date.now() - lastHidden > 10000) window.location.reload();
    }
  });

  _setupTopbarShadow();
  _setupNavHaptics();
  _setupCountUp();
  _setupPullToRefresh();
  _setupSwipeToDelete();

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function(event) {
      if (event.data && event.data.type === 'SYNC_SUCCESS') {
        showToast(event.data.message, 'success', 5000);
        Haptics.success();
        // Optional: reload to show new entries
        setTimeout(() => window.location.reload(), 2000);
      }
    });
  }
});
