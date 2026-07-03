/* ==========================================================
 * Mediatrix — shared client state bus
 *
 * Public API:
 *   Mediatrix.setMode("day" | "vigil")
 *   Mediatrix.toggleMode()
 *   Mediatrix.getMode()
 *   Mediatrix.pushRecent({slug, title, subtitle, vestment, scrollRatio})
 *   Mediatrix.getRecents()
 *   Mediatrix.setResume({slug, scrollRatio})
 *   Mediatrix.getResume()
 *
 * Hard rule: every interactive page calls Mediatrix.pushRecent with the
 * required { slug, title, subtitle, vestment, scrollRatio } shape on load.
 * Legacy shapes silently no-op.
 *
 * Cross-tab sync: storage event mirrors mode + recents across tabs.
 * ========================================================== */

(function () {
  "use strict";

  var STORE_MODE = "mediatrix.mode";
  var STORE_RECENTS = "mediatrix.recents";
  var STORE_RESUME = "mediatrix.resume";
  var RECENTS_CAP = 6;

  function ls(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw == null ? fallback : JSON.parse(raw);
    } catch (e) { return fallback; }
  }
  function ssave(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { /* private mode */ }
  }

  // Browser-chrome color per mode. Mirrors --m-blue (day) and the vigil
  // page background from mediatrix.css :root; manifest.json carries the
  // same day value. Keep the three in step if the palette ever moves.
  var THEME_COLOR = { day: "#1E3A6E", vigil: "#0A1628" };

  function applyMode(m) {
    document.documentElement.setAttribute("data-mode", m);
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) {
      metas[i].setAttribute("content", THEME_COLOR[m] || THEME_COLOR.day);
    }
    // The mast toggle's label names the mode you would switch TO. Kept
    // here so cross-tab storage sync re-labels the button as well.
    var btn = document.getElementById("mode-toggle");
    if (btn) btn.textContent = m === "vigil" ? "Day" : "Vigil";
  }

  function setMode(m) {
    if (m !== "day" && m !== "vigil") return;
    ssave(STORE_MODE, m);
    applyMode(m);
  }

  function getMode() {
    return ls(STORE_MODE, "day");
  }

  function toggleMode() {
    setMode(getMode() === "vigil" ? "day" : "vigil");
  }

  function getRecents() {
    var arr = ls(STORE_RECENTS, []);
    return Array.isArray(arr) ? arr : [];
  }

  function pushRecent(entry) {
    if (!entry || typeof entry !== "object") return;
    if (typeof entry.slug !== "string" || !entry.slug) return;
    var clean = {
      slug: entry.slug,
      title: typeof entry.title === "string" ? entry.title : "",
      subtitle: typeof entry.subtitle === "string" ? entry.subtitle : "",
      vestment: typeof entry.vestment === "string" ? entry.vestment : "blue",
      scrollRatio: typeof entry.scrollRatio === "number" ? entry.scrollRatio : 0,
      at: Date.now(),
    };
    var arr = getRecents().filter(function (r) { return r.slug !== clean.slug; });
    arr.unshift(clean);
    if (arr.length > RECENTS_CAP) arr.length = RECENTS_CAP;
    ssave(STORE_RECENTS, arr);
  }

  function setResume(entry) {
    if (!entry || typeof entry !== "object") return;
    if (typeof entry.slug !== "string") return;
    ssave(STORE_RESUME, {
      slug: entry.slug,
      scrollRatio: typeof entry.scrollRatio === "number" ? entry.scrollRatio : 0,
      at: Date.now(),
    });
  }

  function getResume() { return ls(STORE_RESUME, null); }

  /* --- cross-tab sync --- */
  window.addEventListener("storage", function (e) {
    if (e.key === STORE_MODE && e.newValue) {
      try { applyMode(JSON.parse(e.newValue)); } catch (err) {}
    }
  });

  /* --- initial mode application (early, before paint where possible) --- */
  applyMode(getMode());

  /* --- mast toggle wiring (shared by every page; replaces the per-page
         inline copies). The script loads in <head>, so the button does
         not exist yet at module time; wire on DOMContentLoaded. --- */
  function initToggle() {
    var btn = document.getElementById("mode-toggle");
    if (!btn) return;
    btn.addEventListener("click", toggleMode);
    btn.textContent = getMode() === "vigil" ? "Day" : "Vigil";
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initToggle);
  } else {
    initToggle();
  }

  /* --- service worker registration (PWA install + offline) --- */
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () {
        /* Silent: SW failure should never break the page. */
      });
    });
  }

  /* --- expose --- */
  window.Mediatrix = {
    setMode: setMode,
    toggleMode: toggleMode,
    getMode: getMode,
    pushRecent: pushRecent,
    getRecents: getRecents,
    setResume: setResume,
    getResume: getResume,
  };
})();
