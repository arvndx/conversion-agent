/* Shared helpers for the dashboard pages (demo): the header, charts, the side panel and the API calls. */
(function (w, d) {
  "use strict";

  var segs = location.pathname.replace(/\/+$/, "").split("/"); // ["", "c", rid, page?]
  var rid = decodeURIComponent(segs[2] || "");
  var BASE = "/c/" + encodeURIComponent(rid);
  var API = "/api/c/" + encodeURIComponent(rid);
  var DAY = 86400000;
  var PAGES = [["overview", "Overview", ""], ["people", "Leads and hot visitors", "/people"],
               ["replies", "Reply quality", "/replies"], ["admin", "Admin", "/admin"]];
  var uid = 0;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n).toLocaleString("en-US"); }
  function pct(a, b) { return b ? Math.round((a / b) * 100) : 0; }
  function mmss(s) { return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); }
  function when(iso) {
    var x = new Date(iso);
    return x.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + " · " +
      x.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }
  function clock(iso) { return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }); }
  function dayLabel(iso) { return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" }); }
  function ago(iso) {
    var h = Math.round((Date.now() - new Date(iso).getTime()) / 3600000);
    return h < 1 ? "just now" : h < 24 ? h + " h ago" : Math.round(h / 24) + " d ago";
  }

  function toast(text) {
    var el = d.getElementById("toast");
    el.textContent = text; el.classList.add("show");
    clearTimeout(toast.t); toast.t = setTimeout(function () { el.classList.remove("show"); }, 2600);
  }

  // The API. Errors come back as a readable message (FastAPI's detail, or the first validation message).
  function send(method, path, body) {
    return fetch(API + path, {
      method: method, headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) {
          var msg = "Something went wrong. Try again.";
          if (typeof j.detail === "string") msg = j.detail;
          else if (j.detail && j.detail[0] && j.detail[0].msg) msg = "Check the value: " + j.detail[0].msg;
          throw new Error(msg);
        }
        return j;
      });
    });
  }
  function get(path) { return send("GET", path); }

  // ---- header ----
  function hero(opts) {
    // opts: page, title, domain (show the domain list), periods [[value, label]], period (default), onChange(state)
    var state = { domain: "all", period: opts.period };
    var nav = PAGES.map(function (p) {
      return '<a href="' + BASE + p[2] + '"' + (p[0] === opts.page ? ' class="on"' : "") + ">" + p[1] + "</a>";
    }).join("");
    d.getElementById("hero").innerHTML =
      '<div class="wrap"><div class="hero-top"><div class="brand"><div class="logo">CA</div><div>' +
      '<div class="crumb">Conversion Agent · demo dashboard</div><h1 id="hName">' + esc(opts.title || "Loading…") + "</h1>" +
      "</div></div><div class=\"controls\">" +
      (opts.domain ? '<select id="hDomain" class="pill-select" aria-label="Domain"><option value="all">All domains</option></select>' : "") +
      (opts.periods ? '<div class="glass" id="hPeriod">' + opts.periods.map(function (p) {
        return '<button data-v="' + p[0] + '"' + (p[0] === opts.period ? ' class="on"' : "") + ">" + p[1] + "</button>";
      }).join("") + "</div>" : "") +
      '</div></div><nav class="nav">' + nav + "</nav></div>";
    var periodBox = d.getElementById("hPeriod");
    if (periodBox) periodBox.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.period = b.dataset.v === "all" ? "all" : Number(b.dataset.v);
      periodBox.querySelectorAll("button").forEach(function (x) { x.classList.toggle("on", x === b); });
      if (opts.onChange) opts.onChange(state);
    });
    var sel = d.getElementById("hDomain");
    if (sel) sel.addEventListener("change", function () { state.domain = sel.value; if (opts.onChange) opts.onChange(state); });
    return state;
  }
  function setDomains(list) {
    var sel = d.getElementById("hDomain");
    if (!sel) return;
    sel.innerHTML = '<option value="all">All domains (combined)</option>' +
      list.map(function (x) { return '<option value="' + esc(x) + '">' + esc(x) + "</option>"; }).join("");
  }
  function setName(name, page) {
    var h = d.getElementById("hName");
    if (h) h.textContent = name;
    d.title = name + " · " + page + " (demo)";
  }

  // ---- icons (24px line icons) ----
  var ICONS = {
    visitors: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    lead: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    hot: '<path d="M12 2s5 4.5 5 9.5A5 5 0 0 1 7 11.5C7 8 9 6 9 6s0 3 2 4c0-3 1-6 1-8z"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>'
  };
  function icon(name, size) {
    return '<svg viewBox="0 0 24 24" width="' + (size || 19) + '" height="' + (size || 19) + '" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + "</svg>";
  }

  // ---- charts ----
  // A smooth curve through the points (Catmull-Rom turned into Bezier segments).
  function smooth(pts) {
    if (pts.length < 2) return "";
    var dd = "M" + pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2, t = 0.18;
      var c1x = p1[0] + (p2[0] - p0[0]) * t, c1y = p1[1] + (p2[1] - p0[1]) * t;
      var c2x = p2[0] - (p3[0] - p1[0]) * t, c2y = p2[1] - (p3[1] - p1[1]) * t;
      dd += " C" + c1x.toFixed(1) + "," + c1y.toFixed(1) + " " + c2x.toFixed(1) + "," + c2y.toFixed(1) + " " +
        p2[0].toFixed(1) + "," + p2[1].toFixed(1);
    }
    return dd;
  }
  function niceMax(v) {
    if (v <= 0) return 10;
    var p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  }

  // Small line with a soft fill, for the KPI tiles.
  function spark(values, color) {
    var W = 96, H = 34, max = Math.max(1, Math.max.apply(null, values)), min = Math.min.apply(null, values);
    var span = Math.max(1, max - min);
    var pts = values.map(function (v, i) {
      return [(i / Math.max(1, values.length - 1)) * W, H - 3 - ((v - min) / span) * (H - 8)];
    });
    var id = "g" + (++uid);
    return '<svg class="spark" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" aria-hidden="true">' +
      '<defs><linearGradient id="' + id + '" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="' + color + '" stop-opacity=".28"/>' +
      '<stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>' +
      '<path d="' + smooth(pts) + ' L' + W + "," + H + " L0," + H + 'Z" fill="url(#' + id + ')"/>' +
      '<path d="' + smooth(pts) + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linecap="round"/></svg>';
  }

  // Area chart with one or more series, a hover line and a tooltip. rows: [{date, <key>: value}].
  function areaChart(el, rows, opts) {
    var W = 900, H = opts.height || 280, P = { l: 46, r: 16, t: 18, b: 32 };
    var keys = opts.series;
    var max = niceMax(Math.max(1, Math.max.apply(null, [].concat.apply([], keys.map(function (s) {
      return rows.map(function (r) { return r[s.key]; });
    })))));
    var lines = 5;
    var x = function (i) { return P.l + (i / Math.max(1, rows.length - 1)) * (W - P.l - P.r); };
    var y = function (v) { return P.t + (1 - v / max) * (H - P.t - P.b); };
    var out = "", g;
    for (g = 0; g <= lines; g++) {
      var val = (max / lines) * g, gy = y(val);
      out += '<line x1="' + P.l + '" x2="' + (W - P.r) + '" y1="' + gy + '" y2="' + gy + '" stroke="#e8eef8"' +
        (g === 0 ? ' stroke-width="1.4"' : "") + "/>" +
        '<text x="' + (P.l - 10) + '" y="' + (gy + 4) + '" text-anchor="end" font-size="11" fill="#7f716a">' + fmt(Math.round(val)) + "</text>";
    }
    var step = Math.max(1, Math.ceil(rows.length / 7));
    rows.forEach(function (r, i) {
      if (i % step === 0 || i === rows.length - 1) {
        out += '<text x="' + x(i) + '" y="' + (H - 8) + '" text-anchor="' + (i === rows.length - 1 ? "end" : i === 0 ? "start" : "middle") +
          '" font-size="11" fill="#7f716a">' + dayLabel(r.date) + "</text>";
      }
    });
    var defs = "";
    keys.forEach(function (s, k) {
      var id = "a" + (++uid);
      var pts = rows.map(function (r, i) { return [x(i), y(r[s.key])]; });
      defs += '<linearGradient id="' + id + '" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="' + s.color + '" stop-opacity=".30"/>' +
        '<stop offset="1" stop-color="' + s.color + '" stop-opacity="0"/></linearGradient>';
      if (s.fill !== false) {
        out += '<path d="' + smooth(pts) + " L" + x(rows.length - 1) + "," + (H - P.b) + " L" + x(0) + "," + (H - P.b) + 'Z" fill="url(#' + id + ')"/>';
      }
      out += '<path d="' + smooth(pts) + '" fill="none" stroke="' + s.color + '" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>';
    });
    el.innerHTML = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(opts.label || "Chart") + '">' +
      "<defs>" + defs + "</defs>" + out +
      '<line class="hover" x1="0" x2="0" y1="' + P.t + '" y2="' + (H - P.b) + '" stroke="#9dbdf2" stroke-dasharray="4 4" opacity="0"/>' +
      keys.map(function () { return '<circle class="dot" r="5" fill="#fff" stroke-width="2.5" opacity="0"/>'; }).join("") +
      "</svg><div class=\"tip\"></div>";
    var svg = el.querySelector("svg"), tip = el.querySelector(".tip");
    var line = svg.querySelector(".hover"), dots = svg.querySelectorAll(".dot");
    keys.forEach(function (s, k) { dots[k].setAttribute("stroke", s.color); });
    svg.addEventListener("mousemove", function (e) {
      var box = svg.getBoundingClientRect();
      var sx = ((e.clientX - box.left) / box.width) * W;
      var i = Math.max(0, Math.min(rows.length - 1, Math.round(((sx - P.l) / (W - P.l - P.r)) * (rows.length - 1))));
      var r = rows[i];
      line.setAttribute("x1", x(i)); line.setAttribute("x2", x(i)); line.setAttribute("opacity", 1);
      keys.forEach(function (s, k) {
        dots[k].setAttribute("cx", x(i)); dots[k].setAttribute("cy", y(r[s.key])); dots[k].setAttribute("opacity", 1);
      });
      tip.innerHTML = "<b>" + dayLabel(r.date) + "</b>" + keys.map(function (s) {
        return '<div><i style="background:' + s.color + '"></i>' + esc(s.label) + " " + fmt(r[s.key]) + "</div>";
      }).join("");
      tip.style.left = ((x(i) / W) * box.width) + "px";
      tip.style.top = ((Math.min(y(r[keys[0].key]), y(r[keys[keys.length - 1].key])) / H) * box.height) + "px";
      tip.style.opacity = 1;
    });
    svg.addEventListener("mouseleave", function () {
      tip.style.opacity = 0; line.setAttribute("opacity", 0);
      dots.forEach(function (c) { c.setAttribute("opacity", 0); });
    });
  }

  // Donut with an optional centre. parts: [{value, color, label}].
  function donut(parts, opts) {
    var size = opts.size || 150, stroke = opts.stroke || 16, R = (size - stroke) / 2 - 2, C = 2 * Math.PI * R;
    var total = parts.reduce(function (a, p) { return a + p.value; }, 0);
    var offset = 0, arcs = "";
    parts.forEach(function (p) {
      var len = total ? (p.value / total) * C : 0;
      if (len > 0) {
        arcs += '<circle r="' + R + '" cx="' + size / 2 + '" cy="' + size / 2 + '" fill="none" stroke="' + p.color +
          '" stroke-width="' + stroke + '" stroke-linecap="round" stroke-dasharray="' + Math.max(0, len - 3).toFixed(2) + " " + C.toFixed(2) +
          '" stroke-dashoffset="' + (-offset).toFixed(2) + '" transform="rotate(-90 ' + size / 2 + " " + size / 2 + ')"/>';
      }
      offset += len;
    });
    return '<div class="donut" style="position:relative;width:' + size + "px;height:" + size + 'px;flex:none">' +
      '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + " " + size + '" aria-label="' + esc(opts.label || "Chart") + '">' +
      '<circle r="' + R + '" cx="' + size / 2 + '" cy="' + size / 2 + '" fill="none" stroke="#e8eef8" stroke-width="' + stroke + '"/>' + arcs + "</svg>" +
      '<div style="position:absolute;inset:0;display:grid;place-items:center;text-align:center">' + (opts.center || "") + "</div></div>";
  }
  // A ring with a percentage in the middle (visit to lead).
  function ring(p, color, size) {
    var s = size || 120, stroke = 12, R = (s - stroke) / 2 - 2, C = 2 * Math.PI * R;
    return '<div style="position:relative;width:' + s + "px;height:" + s + 'px;flex:none">' +
      '<svg width="' + s + '" height="' + s + '" viewBox="0 0 ' + s + " " + s + '">' +
      '<circle r="' + R + '" cx="' + s / 2 + '" cy="' + s / 2 + '" fill="none" stroke="#e8eef8" stroke-width="' + stroke + '"/>' +
      '<circle r="' + R + '" cx="' + s / 2 + '" cy="' + s / 2 + '" fill="none" stroke="' + color + '" stroke-width="' + stroke +
      '" stroke-linecap="round" stroke-dasharray="' + (C * Math.min(100, p) / 100).toFixed(1) + " " + C.toFixed(1) +
      '" transform="rotate(-90 ' + s / 2 + " " + s / 2 + ')"/></svg>' +
      '<div style="position:absolute;inset:0;display:grid;place-items:center;font-size:' + Math.round(s / 4.2) +
      'px;font-weight:760">' + p + "%</div></div>";
  }

  // ---- side panel ----
  function ensureDrawer() {
    if (d.getElementById("drawer")) return;
    d.body.insertAdjacentHTML("beforeend",
      '<div class="scrim" id="scrim"></div>' +
      '<aside class="drawer" id="drawer" aria-label="Details" aria-hidden="true">' +
      '<div class="dhead"><div><div class="crumb" id="dCrumb"></div><h2 id="dName"></h2></div>' +
      '<button class="x" id="dClose" aria-label="Close">×</button></div><div class="dbody" id="dBody"></div></aside>' +
      '<div class="toast" id="toast"></div>');
    d.getElementById("scrim").addEventListener("click", closeDrawer);
    d.getElementById("dClose").addEventListener("click", closeDrawer);
    d.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawer(); });
  }
  function openDrawer(crumb, title, html) {
    ensureDrawer();
    d.getElementById("dCrumb").textContent = crumb;
    d.getElementById("dName").textContent = title;
    d.getElementById("dBody").innerHTML = html;
    d.getElementById("dBody").scrollTop = 0;
    d.getElementById("drawer").classList.add("open");
    d.getElementById("drawer").setAttribute("aria-hidden", "false");
    d.getElementById("scrim").classList.add("open");
    return d.getElementById("dBody");
  }
  function closeDrawer() {
    var dr = d.getElementById("drawer");
    if (!dr) return;
    dr.classList.remove("open"); dr.setAttribute("aria-hidden", "true");
    d.getElementById("scrim").classList.remove("open");
  }
  // The whole chat. marked: the reply being rated (its text is highlighted with a note).
  function thread(conv, marked) {
    return '<div class="thread">' + conv.map(function (t) {
      var isMarked = marked && t.who === "bot" && t.text === marked.text;
      return '<div class="msg ' + t.who + (isMarked ? " marked" : "") + '"><div class="bub">' + esc(t.text) + "</div>" +
        (isMarked ? '<div class="marker">' + esc(marked.note) + "</div>" : "") +
        '<div class="ts">' + clock(t.at) + "</div></div>";
    }).join("") + "</div>";
  }
  function facts(list) {
    return '<div class="facts">' + list.map(function (f) {
      return '<div class="fact' + (f.wide ? " wide" : "") + '"><div class="k">' + esc(f.k) + '</div><div class="v">' + f.v + "</div></div>";
    }).join("") + "</div>";
  }

  d.addEventListener("DOMContentLoaded", ensureDrawer);
  if (d.readyState !== "loading") ensureDrawer();

  // ---- unsaved changes ----
  // A page can register a guard: dirty() says there are unsaved changes, save() saves them (returns a promise).
  var guard = null;
  function askSave() {
    return new Promise(function (resolve) {
      var back = d.getElementById("modalBack");
      if (!back) {
        d.body.insertAdjacentHTML("beforeend",
          '<div class="modal-back" id="modalBack"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="mTitle">' +
          '<h2 id="mTitle">Would you like to save the changes?</h2>' +
          '<p>Some knowledge changes are not saved yet. They are only saved when you press Save.</p>' +
          '<div class="actions"><button class="btn ghost" data-m="stay" type="button">Stay here</button>' +
          '<button class="btn ghost" data-m="discard" type="button">Leave without saving</button>' +
          '<button class="btn" data-m="save" type="button">Save and continue</button></div></div></div>');
        back = d.getElementById("modalBack");
      }
      back.classList.add("open");
      function done(choice) {
        back.classList.remove("open");
        back.removeEventListener("click", onClick);
        resolve(choice);
      }
      function onClick(e) {
        var b = e.target.closest("[data-m]");
        if (b) done(b.dataset.m);
      }
      back.addEventListener("click", onClick);
    });
  }
  function setGuard(g) { guard = g; }
  function dirty() { return !!(guard && guard.dirty && guard.dirty()); }
  // Runs before leaving the guarded area: asks, saves if asked, and says whether to go on.
  function confirmLeave() {
    if (!dirty()) return Promise.resolve(true);
    return askSave().then(function (choice) {
      if (choice === "stay") return false;
      if (choice === "discard") { if (guard.discard) guard.discard(); return true; }
      return guard.save().then(function () { return true; }).catch(function (err) { toast(err.message); return false; });
    });
  }
  // Nav links to other pages ask first.
  d.addEventListener("click", function (e) {
    var a = e.target.closest("a[href]");
    if (!a || !dirty() || a.target === "_blank" || a.hash && a.pathname === location.pathname) return;
    e.preventDefault();
    var href = a.href;
    confirmLeave().then(function (go) { if (go) location.href = href; });
  });
  w.addEventListener("beforeunload", function (e) {
    if (dirty()) { e.preventDefault(); e.returnValue = ""; }
  });

  w.Dash = {
    rid: rid, BASE: BASE, API: API, DAY: DAY,
    esc: esc, fmt: fmt, pct: pct, mmss: mmss, when: when, clock: clock, dayLabel: dayLabel, ago: ago,
    toast: toast, get: get, send: send, hero: hero, setDomains: setDomains, setName: setName,
    icon: icon, spark: spark, areaChart: areaChart, donut: donut, ring: ring,
    openDrawer: openDrawer, closeDrawer: closeDrawer, thread: thread, facts: facts,
    setGuard: setGuard, confirmLeave: confirmLeave, dirty: dirty
  };
})(window, document);
