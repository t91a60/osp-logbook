// OSP Logbook v2 – Core JS

// ── Toast System ──────────────────────────────────────────────

function showToast(message, type, duration) {
  // type: 'success' | 'error' | 'info'
  if (duration === undefined) duration = type === "error" ? null : 2500;
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast " + (type || "info");
  toast.setAttribute("role", "alert");

  const icons = { success: "✓", error: "✗", info: "ℹ" };
  const iconEl = document.createElement("span");
  iconEl.className = "toast-icon";
  iconEl.textContent = icons[type] || "•";

  const messageEl = document.createElement("span");
  messageEl.style.flex = "1";
  messageEl.textContent = String(message || "");

  toast.appendChild(iconEl);
  toast.appendChild(messageEl);

  container.appendChild(toast);

  if (duration) {
    setTimeout(function () {
      toast.style.animation = "slideUp 0.3s ease-out reverse";
      setTimeout(function () {
        if (toast.parentElement) toast.remove();
      }, 260);
    }, duration);
  }
}

// ── AJAX Form Submit (z X-CSRFToken) ─────────────────────────

function submitForm(formId, endpoint, onSuccess) {
  var form = document.getElementById(formId);
  if (!form) return false;

  var btn = form.querySelector('button[type="submit"]');
  var orig = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Zapisywanie…';
  }

  var csrfToken = document.querySelector('meta[name="csrf-token"]');
  csrfToken = csrfToken ? csrfToken.getAttribute("content") : "";

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
        .then(function (p) {
          if (!r.ok) throw new Error(p.message || "Błąd zapisywania.");
          return p;
        });
    })
    .then(function (data) {
      if (data.success) {
        showToast(data.message || "Zapisano", "success");
        clearFormAutosave(formId);
        form.reset();
        var ps = document.getElementById("purposeSelect");
        if (ps) ps.value = "";
        var pc = document.getElementById("purposeCustomWrap");
        if (pc) pc.classList.add("hidden");
        if (typeof onSuccess === "function") onSuccess();
      } else {
        showToast(data.message || "Błąd", "error");
      }
    })
    .catch(function (err) {
      showToast(err.message || "Błąd sieci", "error");
    })
    .finally(function () {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = orig;
      }
    });

  return false;
}

// ── Auto-save ─────────────────────────────────────────────────

function setupAutoSave(formId) {
  var form = document.getElementById(formId);
  if (!form) return;
  var key = "form_" + formId;
  try {
    var saved = JSON.parse(localStorage.getItem(key));
    if (saved) {
      Object.entries(saved).forEach(function (pair) {
        var name = pair[0],
          value = pair[1];
        var field = form.elements[name];
        if (!field) return;
        if (
          field.type === "date" ||
          field.type === "hidden" ||
          String(name).startsWith("_")
        )
          return;
        field.value = value;
      });
    }
  } catch (e) {}
  form.addEventListener("change", function () {
    var obj = {};
    for (var entry of new FormData(form)) {
      var k = entry[0],
        v = entry[1];
      var field = form.elements[k];
      if (!field) continue;
      if (
        field.type === "date" ||
        field.type === "hidden" ||
        String(k).startsWith("_")
      )
        continue;
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

// ── Odometer calc ─────────────────────────────────────────────

function calculateKm() {
  var start = parseInt((document.getElementById("odo_start") || {}).value || 0);
  var end = parseInt((document.getElementById("odo_end") || {}).value || 0);
  var hint = document.getElementById("kmHint");
  if (hint && start && end && end > start) {
    hint.textContent = end - start + " km";
    hint.className = "form-hint success";
  } else if (hint) {
    hint.textContent = "";
    hint.className = "form-hint";
  }
}

// ── Last-km hint ──────────────────────────────────────────────

function loadLastKm(vehicleId, hintId) {
  var hint = document.getElementById(hintId);
  if (!hint || !vehicleId) {
    if (hint) hint.textContent = "";
    return;
  }
  fetch("/api/vehicle/" + vehicleId + "/last_km")
    .then(function (r) {
      return r.json();
    })
    .then(function (d) {
      if (d.km !== null && d.km !== undefined) {
        var kmFmt = d.km.toLocaleString("pl-PL");
        var daysTxt =
          d.days_ago === 0
            ? "dzisiaj"
            : d.days_ago === 1
              ? "wczoraj"
              : d.days_ago + " dni temu";
        hint.textContent = "Ostatni odczyt: " + kmFmt + " km · " + daysTxt;
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

// ── Driver datalist ───────────────────────────────────────────

function loadDrivers(datalistId) {
  fetch("/api/drivers")
    .then(function (r) {
      return r.json();
    })
    .then(function (names) {
      var dl = document.getElementById(datalistId);
      if (!dl) return;
      names.forEach(function (name) {
        var opt = document.createElement("option");
        opt.value = name;
        dl.appendChild(opt);
      });
    })
    .catch(function () {});
}

// ── Purpose combo ─────────────────────────────────────────────

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

// ── Vehicle memory ────────────────────────────────────────────

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

// ── Keyboard shortcuts ────────────────────────────────────────

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

// ── Flash → Toast on load ─────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("flashMessages");
  if (!el || !el.textContent.trim() || el.textContent.trim() === "[]") return;
  try {
    JSON.parse(el.textContent).forEach(function (pair) {
      var type =
        pair[0] === "error"
          ? "error"
          : pair[0] === "success"
            ? "success"
            : "info";
      showToast(pair[1], type);
    });
  } catch (e) {}
});

// ── Pull-to-Refresh & tab focus reload ────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  // Ensure notch/safe-area viewport-fit=cover is set
  var vp = document.querySelector('meta[name="viewport"]');
  if (vp && !vp.content.includes("viewport-fit"))
    vp.content += ", viewport-fit=cover";

  var wantsRefresh = document.body.getAttribute("data-autorefresh") === "true";
  var lastHidden = null;

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      lastHidden = Date.now();
    } else if (
      document.visibilityState === "visible" &&
      wantsRefresh &&
      lastHidden
    ) {
      if (Date.now() - lastHidden > 10000) location.reload();
    }
  });

  // Touch pull-to-refresh (manual swipe-down gesture)
  var touchStartY = 0;
  document.body.addEventListener(
    "touchstart",
    function (e) {
      if (window.scrollY === 0) touchStartY = e.touches[0].clientY;
    },
    { passive: true },
  );
  document.body.addEventListener(
    "touchend",
    function (e) {
      if (window.scrollY === 0 && wantsRefresh && touchStartY > 0) {
        if (e.changedTouches[0].clientY - touchStartY > 150) location.reload();
      }
    },
    { passive: true },
  );
});
