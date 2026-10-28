/*
 * Conversion Agent widget (A84). Plain JavaScript, no build step.
 *
 * Add it to a page with a script tag (the API address is built in; data-api is only for local testing):
 *   <script src="https://<our host>/widget.js" data-site-key="..." async></script>
 *
 * Before a chat, the widget asks the API for the teaser, the title, the default questions and the quick actions (from the
 * bundles). data-greeting is only used if that request fails. A click on a quick question sends its action key: the server
 * answers with the request form (a card), or the business's link, and calls no model. A form is checked here and again by the
 * server when it is sent (POST /chat/form).
 *
 * What it keeps, and where:
 *   localStorage    ca_session_<site key>     the chat's session ID (shared by every tab of the site)
 *   localStorage    ca_block_token            the block token, sent on every request (A83)
 *   localStorage    ca_consent                the visitor's choice and the notice version (A54 b)
 *   localStorage    ca_visitor                the visitor ID, only after the visitor accepts
 *   localStorage    ca_chat_log               each chat: its messages, times and the thumbs up or down on each reply
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var SITE_KEY = script.dataset.siteKey;
  var API = (script.dataset.api || "http://localhost:8000").replace(/\/$/, "");
  var FALLBACK_TEASER = script.dataset.greeting || "Hi, I'm an AI assistant. How can I help you?";
  // Demo mode (data-mode="demo"): no calls to the chat API. The config and the replies come from the built-in mock below.
  var DEMO = script.dataset.mode === "demo";
  var PLAY_URL = script.dataset.playground || "";  // demo: the dashboard's answer engine (blank: the canned replies)
  var DEMO_WAIT_MS = 0;      // demo only: no wait before the reply (the typing dots show until it arrives)
  var DEMO_PRINT_MS = 2000;  // then the reply is printed over this long
  var REPLY_LIMIT_MS = 30000; // no reply in this time: unlock the box and ask the visitor to repeat the question
  var MIN_TYPING_MS = 2000;   // a reply is shown after at least this long with the typing dots, so a fixed reply does not look instant
  var DEMO_SLOW_MS = 40000;   // demo only: a question with the word "slow" gets a reply after this long
  var NOTICE_VERSION = script.dataset.noticeVersion || "draft-1";
  // Page activity (the visit, its page views, clicks and time): only where the site turns it on, and the server agrees.
  var PAGE_TRACKING = script.dataset.pageTracking === "on";
  var VISIT_IDLE_MS = 30 * 60 * 1000;   // a visit ends after 30 minutes with no activity
  var BEAT_MS = 15000;                  // how often the widget sends its events
  var NOTICE = "This chat is recorded, and the business receives the details you share. " +
               "We may also record which pages you visit, if you accept.";
  var UNAVAILABLE = "This chat isn't available right now.";
  var POLL_MS = 1000;
  var POP_MS = 3000;
  var TEASER_MS = 5000;
  var MINUTE = 60 * 1000;

  var K_SESSION = "ca_session_" + SITE_KEY;
  var K_BLOCK = "ca_block_token";
  var K_CONSENT = "ca_consent";
  var K_VISITOR = "ca_visitor";
  var K_LOG = "ca_chat_log";
  var K_VISIT = "ca_visit";

  function store(area, key, value) { try { area.setItem(key, value); } catch (e) {} }
  function load(area, key) { try { return area.getItem(key); } catch (e) { return null; } }
  function drop(area, key) { try { area.removeItem(key); } catch (e) {} }

  function newId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "id-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  function consent() {
    try { return JSON.parse(load(localStorage, K_CONSENT) || "null"); } catch (e) { return null; }
  }

  function chooseConsent(accepted) {
    store(localStorage, K_CONSENT, JSON.stringify({ choice: accepted ? "accepted" : "declined", version: NOTICE_VERSION }));
    if (accepted && !load(localStorage, K_VISITOR)) store(localStorage, K_VISITOR, newId());
  }

  // --- the page: a launcher, a teaser, a notice and a panel, inside a shadow root so the host page's CSS cannot reach them ---
  var host = document.createElement("div");
  host.id = "conversion-agent";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });
  root.innerHTML =
    '<style>' +
    ':host { all: initial; --brand: #7a2e1d; --brand-2: #a2432b; --ink: #1f1a17; --muted: #877a71; --line: #eee6df; --paper: #f8f5f2; }' +
    '@keyframes ca-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }' +
    '@keyframes ca-bounce { 0%, 80%, 100% { transform: translateY(0); opacity: .35; } 40% { transform: translateY(-4px); opacity: 1; } }' +
    '@keyframes ca-ring { 0% { transform: scale(.92); opacity: .55; } 100% { transform: scale(1.35); opacity: 0; } }' +
    '.launch { position: fixed; right: 20px; bottom: 20px; width: 60px; height: 60px; border-radius: 50%; border: 0;' +
    '  background: linear-gradient(135deg, var(--brand-2), var(--brand)); display: flex; align-items: center; justify-content: center;' +
    '  cursor: pointer; box-shadow: 0 8px 22px rgba(90,30,15,.35); transition: transform .15s ease; z-index: 2147483000; }' +
    '.launch::before { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 2px solid var(--brand-2);' +
    '  animation: ca-ring 2s ease-out 3; pointer-events: none; }' +
    '.launch:hover { transform: scale(1.06); }' +
    '.launch svg { width: 27px; height: 27px; fill: #fff; }' +
    '.teaser { position: fixed; right: 20px; bottom: 96px; max-width: 270px; background: #fff; color: var(--ink);' +
    '  border-radius: 16px 16px 4px 16px; padding: 12px 15px; box-shadow: 0 10px 28px rgba(0,0,0,.18); cursor: pointer;' +
    '  font: 14px/1.45 system-ui, sans-serif; border: 1px solid rgba(0,0,0,.05); z-index: 2147483000;' +
    '  opacity: 0; visibility: hidden; transform: translateY(12px) scale(.96);' +
    '  transition: opacity .45s ease, transform .45s cubic-bezier(.2,.8,.2,1), visibility .45s; }' +
    '.teaser.show { opacity: 1; visibility: visible; transform: none; }' +
    '.badge-n { position: absolute; top: -5px; right: -5px; min-width: 22px; height: 22px; padding: 0 6px; border-radius: 11px;' +
    '  background: #d2553c; color: #fff; font: 700 12px system-ui, sans-serif; display: flex; align-items: center; justify-content: center;' +
    '  box-shadow: 0 0 0 2px #fff; }' +
    '.badge-n[hidden] { display: none; }' +
    '.badge-n.dot-only { min-width: 12px; width: 12px; height: 12px; padding: 0; top: -2px; right: -2px; }' +
    '@keyframes ca-shake { 0%, 100% { transform: none; } 25% { transform: rotate(-9deg); } 75% { transform: rotate(9deg); } }' +
    '.launch.ring { animation: ca-shake .6s ease 2; }' +
    '.notice { position: fixed; right: 20px; bottom: 96px; max-width: 270px; background: #fff; color: var(--ink);' +
    '  border-radius: 16px 16px 4px 16px; padding: 11px 14px; box-shadow: 0 10px 28px rgba(0,0,0,.18); cursor: pointer;' +
    '  font: 13.5px/1.45 system-ui, sans-serif; border: 1px solid rgba(0,0,0,.05); z-index: 2147483000; }' +
    '.notice[hidden] { display: none; }' +
    '.notice b { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .07em; color: var(--brand-2); margin-bottom: 2px; }' +
    '.panel { position: fixed; right: 20px; bottom: 96px; width: 370px; max-width: calc(100vw - 24px); height: 600px;' +
    '  max-height: calc(100vh - 110px); display: none; flex-direction: column; background: #fff; color: var(--ink);' +
    '  border-radius: 18px; box-shadow: 0 16px 48px rgba(0,0,0,.28); border: 1px solid rgba(0,0,0,.06);' +
    '  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; z-index: 2147483000; overflow: hidden; }' +
    '.panel.open { display: flex; animation: ca-in .2s ease-out; }' +
    '.head { background: linear-gradient(135deg, var(--brand-2), var(--brand)); color: #fff; padding: 14px 16px;' +
    '  display: flex; align-items: center; gap: 12px; box-shadow: 0 2px 10px rgba(90,30,15,.25); }' +
    '.avatar { width: 40px; height: 40px; border-radius: 50%; background: #fff; color: var(--brand); display: flex;' +
    '  align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex: none; }' +
    '.titles { flex: 1; min-width: 0; }' +
    '.title { font-weight: 600; font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }' +
    '.sub { font-size: 12px; opacity: .92; display: flex; align-items: center; gap: 6px; margin-top: 1px; }' +
    '.dot { width: 7px; height: 7px; border-radius: 50%; background: #4ade80; box-shadow: 0 0 0 3px rgba(74,222,128,.28); }' +
    '.head button.close { background: rgba(255,255,255,.12); border: 0; color: #fff; width: 30px; height: 30px; border-radius: 50%;' +
    '  font-size: 20px; line-height: 1; cursor: pointer; }' +
    '.head button.close:hover { background: rgba(255,255,255,.22); }' +
    '.msgs { flex: 1; overflow-y: auto; padding: 14px 14px 14px; display: flex; flex-direction: column; gap: 10px; background: var(--paper); }' +
    '.row { display: flex; align-items: flex-end; gap: 8px; align-self: flex-start; max-width: 100%; animation: ca-in .18s ease-out; }' +
    '.mini { width: 26px; height: 26px; border-radius: 50%; background: linear-gradient(135deg, var(--brand-2), var(--brand));' +
    '  color: #fff; font-size: 10px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex: none; }' +
    '.col { display: flex; flex-direction: column; gap: 3px; max-width: 265px; min-width: 0; animation: ca-in .18s ease-out; }' +
    '.col.col-me { align-self: flex-end; align-items: flex-end; }' +
    '.bubble { max-width: 100%; padding: 10px 13px; border-radius: 16px; white-space: pre-wrap; line-height: 1.5;' +
    '  box-shadow: 0 1px 3px rgba(0,0,0,.07); }' +
    '.bot { background: #fff; color: var(--ink); border-bottom-left-radius: 5px; }' +
    '.me { background: linear-gradient(135deg, var(--brand-2), var(--brand)); color: #fff; border-bottom-right-radius: 5px;' +
    '  box-shadow: 0 2px 6px rgba(90,30,15,.22); }' +
    '.meta { font-size: 11px; color: var(--muted); padding: 0 4px; }' +
    '.fb { display: flex; gap: 4px; padding-left: 2px; }' +
    '.fb button { background: #fff; border: 1px solid var(--line); border-radius: 999px; width: 30px; height: 24px; font-size: 13px;' +
    '  cursor: pointer; padding: 0; line-height: 1; }' +
    '.fb button:hover { border-color: var(--brand-2); }' +
    '.fb button.on { background: var(--brand); border-color: var(--brand); color: #fff; }' +
    '.reasons { display: flex; flex-wrap: wrap; gap: 4px; padding-left: 2px; max-width: 265px; }' +
    '.reasons[hidden] { display: none; }' +
    '.mapcard { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff; }' +
    '.mapcard iframe { display: block; width: 100%; height: 150px; border: 0; }' +
    '.mapcard a { display: block; font-size: 11.5px; color: var(--brand); padding: 5px 10px; text-decoration: none; }' +
    '.mapcard a.gdir { background: linear-gradient(135deg, var(--brand-2), var(--brand)); color: #fff; font-weight: 600; font-size: 12.5px;' +
    '  text-align: center; padding: 8px 10px; }' +
    '.mapcard a:hover { text-decoration: underline; }' +
    '.fbnote { font-size: 11px; color: var(--muted); padding-left: 2px; }' +
    '.fbnote[hidden] { display: none; }' +
    '.rchip { background: #fff; border: 1px solid var(--line); color: var(--ink); border-radius: 999px; padding: 3px 9px;' +
    '  font: inherit; font-size: 11.5px; cursor: pointer; }' +
    '.rchip:hover { border-color: var(--brand-2); }' +
    '.rchip.on { background: var(--brand); border-color: var(--brand); color: #fff; }' +
    '.other { display: flex; gap: 4px; width: 100%; }' +
    '.other[hidden] { display: none; }' +
    '.other textarea { flex: 1; min-width: 0; border: 1px solid var(--line); border-radius: 12px; padding: 4px 10px; font: inherit; font-size: 12px; resize: none; }' +
    '.other button { background: var(--brand); color: #fff; border: 0; border-radius: 999px; padding: 4px 10px; font: inherit; font-size: 12px; cursor: pointer; }' +
    '.typing { display: flex; gap: 5px; align-items: center; padding: 12px 14px; }' +
    '.typing span { width: 7px; height: 7px; border-radius: 50%; background: var(--muted);' +
    '  animation: ca-bounce 1.2s infinite ease-in-out; }' +
    '.typing span:nth-child(2) { animation-delay: .15s; }' +
    '.typing span:nth-child(3) { animation-delay: .3s; }' +
    '.chips { display: none; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; padding: 6px 12px 10px; background: var(--paper);' +
    '  border-top: 1px solid var(--line); }' +
    '.chips.show { display: grid; }' +
    '.chip { background: #fff; border: 1px solid #e7d9cf; color: var(--brand); border-radius: 999px; padding: 5px 8px;' +
    '  font: inherit; font-size: 12px; font-weight: 500; cursor: pointer; box-shadow: 0 1px 2px rgba(0,0,0,.05);' +
    '  transition: background .15s ease, color .15s ease, border-color .15s ease; width: 100%; text-align: center; line-height: 1.25;' +
    '  white-space: normal; line-height: 1.25; text-align: center; }' +
    '.chip:hover { background: var(--brand); border-color: var(--brand); color: #fff; }' +
    '.chip:disabled { opacity: .5; cursor: default; }' +
    '.consent { padding: 13px 15px; border-top: 1px solid var(--line); font-size: 13px; background: #fff; }' +
    '.consent[hidden] { display: none; }' +
    '.consent button, .send { background: linear-gradient(135deg, var(--brand-2), var(--brand)); color: #fff; border: 0;' +
    '  border-radius: 9px; padding: 7px 13px; cursor: pointer; font: inherit; }' +
    '.consent button.alt { background: var(--line); color: var(--ink); margin-left: 6px; }' +
    '.input { display: flex; gap: 9px; align-items: center; padding: 11px 13px; border-top: 1px solid var(--line); background: #fff; }' +
    '.input input { flex: 1; min-width: 0; border: 1px solid var(--line); border-radius: 999px; padding: 10px 15px;' +
    '  font: inherit; outline: none; color: var(--ink); background: #fff; transition: border-color .15s ease, box-shadow .15s ease; }' +
    '.input input:focus { border-color: var(--brand-2); box-shadow: 0 0 0 3px rgba(162,67,43,.14); }' +
    '.input input:disabled { background: #f5f2ef; }' +
    '.send { width: 40px; height: 40px; border-radius: 50%; padding: 0; display: flex; align-items: center; justify-content: center; flex: none; }' +
    '.send svg { width: 18px; height: 18px; fill: #fff; margin-left: 2px; }' +
    '.send:disabled { opacity: .45; cursor: default; }' +
    '.fcard { width: 285px; max-width: 100%; background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 12px 13px;' +
    '  box-shadow: 0 1px 3px rgba(0,0,0,.07); animation: ca-in .18s ease-out; }' +
    '.fcard h4 { margin: 0 0 8px; font-size: 14px; font-weight: 600; color: var(--ink); }' +
    '.fstep { font-size: 11px; color: var(--muted); margin: -4px 0 8px; }' +
    '.ffield { margin-bottom: 7px; }' +
    '.ffield label { display: block; font-size: 12.5px; font-weight: 600; margin-bottom: 3px; color: var(--ink); }' +
    '.ffield input, .ffield textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--line); border-radius: 10px;' +
    '  padding: 8px 10px; font: inherit; font-size: 13.5px; color: var(--ink); background: #fff; outline: none; }' +
    '.ffield textarea { resize: vertical; min-height: 64px; }' +
    '.ffield input:focus, .ffield textarea:focus { border-color: var(--brand-2); box-shadow: 0 0 0 3px rgba(162,67,43,.14); }' +
    '.ffield.bad input, .ffield.bad textarea { border-color: #c0392b; }' +
    '.fhelp { font-size: 11px; line-height: 1.3; color: var(--muted); margin-top: 2px; }' +
    '.ferr { font-size: 12px; color: #c0392b; margin-top: 3px; }' +
    '.ferr[hidden] { display: none; }' +
    '.fnav { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }' +
    '.fnav button { border: 0; border-radius: 9px; padding: 7px 14px; font: inherit; font-size: 13px; cursor: pointer; }' +
    '.fnav .fgo { background: linear-gradient(135deg, var(--brand-2), var(--brand)); color: #fff; }' +
    '.fnav .fback { background: var(--line); color: var(--ink); }' +
    '.fnav .fcancel { background: none; color: var(--muted); padding: 7px 4px; margin-right: auto; text-decoration: underline; }' +
    '.fnav button:disabled { opacity: .5; cursor: default; }' +
    '.fnote { font-size: 12px; color: #c0392b; margin-top: 6px; }' +
    '.fdone { font-size: 13px; color: var(--muted); }' +
    '</style>' +
    '<button class="launch" aria-label="Open chat">' +
    '  <svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>' +
    '  <span class="badge-n" hidden></span>' +
    '</button>' +
    '<div class="teaser" role="button" tabindex="0"></div>' +
    '<div class="notice" role="button" tabindex="0" hidden></div>' +
    '<div class="panel" role="dialog" aria-label="Chat">' +
    '  <div class="head">' +
    '    <div class="avatar" aria-hidden="true">AI</div>' +
    '    <div class="titles"><div class="title"></div>' +
    '      <div class="sub"><span class="dot"></span><span>Online</span></div></div>' +
    '    <button class="close" aria-label="Close chat">&times;</button>' +
    '  </div>' +
    '  <div class="msgs" aria-live="polite"></div>' +
    '  <div class="consent" hidden></div>' +
    '  <div class="chips"></div>' +
    '  <div class="input"><input type="text" maxlength="500" placeholder="Type your message" />' +
    '  <button class="send" aria-label="Send"><svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg></button></div>' +
    '</div>';

  var launch = root.querySelector(".launch");
  var teaser = root.querySelector(".teaser");
  var notice = root.querySelector(".notice");
  var badge = root.querySelector(".badge-n");
  var panel = root.querySelector(".panel");
  var msgs = root.querySelector(".msgs");
  var chipsBox = root.querySelector(".chips");
  var consentBox = root.querySelector(".consent");
  var input = root.querySelector("input");
  var sendBtn = root.querySelector(".send");
  var titleEl = root.querySelector(".title");

  var pollTimer = null;
  var autoTimer = null;
  var unread = 0;
  var typingEl = null;
  var greeted = false;
  var config = null;
  var teaserText = FALLBACK_TEASER;
  var quickList = [];      // the quick questions shown under the chat
  var actionByLabel = {};  // quick question label -> action key (from the config); a click sends the key
  var replyToken = 0;      // changes for each question sent; a reply to an older question is dropped
  var replyTimer = null;   // the 30-second limit for the current question
  var current = null;      // the chat being logged: { id, started, ended, messages }

  titleEl.textContent = "Chat";

  // ---- the chat log: each chat with its messages, times and thumbs up or down (kept in this browser) ----
  function readLog() {
    try { return JSON.parse(load(localStorage, K_LOG) || "[]"); } catch (e) { return []; }
  }

  function saveLog() {
    if (!current) return;
    var all = readLog().filter(function (c) { return c.id !== current.id; });
    all.push(current);
    store(localStorage, K_LOG, JSON.stringify(all));
  }

  function startChat() {
    if (!current) current = { id: newId(), started: new Date().toISOString(), ended: null, lastTopic: null, messages: [] };
  }

  function endChat() {
    if (!current) return;
    current.ended = new Date().toISOString();
    saveLog();
    current = null;
  }

  function record(who, text) {
    startChat();
    var rec = { id: newId(), who: who, text: text, at: new Date().toISOString(), feedback: null };
    current.messages.push(rec);
    saveLog();
    return rec;
  }

  // ---- time under each message: "Just now", then "2 min ago" up to five minutes, then the clock time ----
  function timeLabel(iso) {
    var at = new Date(iso);
    var age = Date.now() - at.getTime();
    if (age < MINUTE) return "Just now";
    if (age < 5 * MINUTE) return Math.floor(age / MINUTE) + " min ago";
    return at.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }

  function refreshTimes() {
    msgs.querySelectorAll(".meta").forEach(function (m) { m.textContent = timeLabel(m.dataset.at); });
  }
  setInterval(refreshTimes, 15000);

  // ---- messages ----
  // Keeps the newest message in view, just above the quick questions. Called after anything that changes the chat's height.
  function scrollToLatest() {
    requestAnimationFrame(function () { msgs.scrollTop = msgs.scrollHeight; });
  }

  // A bot message sits in a row with a small avatar; the visitor's messages do not.
  function botRow(inner) {
    var row = document.createElement("div");
    row.className = "row";
    var mini = document.createElement("span");
    mini.className = "mini";
    mini.setAttribute("aria-hidden", "true");
    mini.textContent = "AI";
    row.appendChild(mini);
    row.appendChild(inner);
    return row;
  }

  // The thumbs up and down under a reply: one choice per reply; a second press clears it.
  // A thumbs down asks why: quick choices, or the visitor's own words under "Other".
  var REASONS = ["Wrong answer", "Did not answer my question", "Too long", "Hard to understand"];
  // Saves a thumbs up or down on one reply to the server (the reply ratings table). Demo mode keeps it local.
  function sendRating(rec) {
    if (DEMO || !rec.feedback) return;
    var reason = rec.reason || null;
    var note = null;
    if (reason && reason.indexOf("Other: ") === 0) { note = reason.slice(7); reason = "Other"; }
    post("/chat/feedback", {
      site_key: SITE_KEY, domain: location.host, session_id: load(localStorage, K_SESSION) || null,
      rating: rec.feedback, reason: reason, reason_note: note, reply: rec.text,
    }).catch(function () {});
  }

  function feedbackRow(rec) {
    var wrap = document.createElement("div");
    wrap.className = "fbwrap";
    var row = document.createElement("div");
    row.className = "fb";
    var up = document.createElement("button");
    var down = document.createElement("button");
    up.type = down.type = "button";
    up.textContent = "👍";
    down.textContent = "👎";
    up.setAttribute("aria-label", "Helpful");
    down.setAttribute("aria-label", "Not helpful");
    row.appendChild(up);
    row.appendChild(down);
    wrap.appendChild(row);

    var reasons = document.createElement("div");
    reasons.className = "reasons";
    REASONS.concat(["Other"]).forEach(function (label) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "rchip";
      b.textContent = label;
      b.onclick = function () {
        if (label === "Other") {
          other.hidden = !other.hidden;
          if (!other.hidden) otherInput.focus();
          return;
        }
        rec.reason = rec.reason === label ? null : label;
        paint();
        saveLog();
        sendRating(rec);
      };
      reasons.appendChild(b);
    });
    var other = document.createElement("div");
    other.className = "other";
    other.hidden = true;
    var otherInput = document.createElement("textarea"); // a textarea, so the chat's own input stays the only <input>
    otherInput.rows = 1;
    otherInput.maxLength = 200;
    otherInput.placeholder = "Tell us what was wrong";
    var otherSend = document.createElement("button");
    otherSend.type = "button";
    otherSend.textContent = "Send";
    otherSend.onclick = function () {
      var words = otherInput.value.trim();
      if (!words) return;
      rec.reason = "Other: " + words;
      other.hidden = true;
      paint();
      saveLog();
      sendRating(rec);
    };
    other.appendChild(otherInput);
    other.appendChild(otherSend);
    reasons.appendChild(other);
    wrap.appendChild(reasons);
    var note = document.createElement("div");
    note.className = "fbnote";
    wrap.appendChild(note);

    function paint() {
      up.className = rec.feedback === "up" ? "on" : "";
      down.className = rec.feedback === "down" ? "on" : "";
      // The reasons are shown only while a thumbs down is waiting for its reason; after that they fold away.
      reasons.hidden = rec.feedback !== "down" || !!rec.reason;
      note.textContent = rec.reason ? "Thanks. Noted: " + rec.reason.replace(/^Other: /, "") : (rec.feedback === "up" ? "Thanks for the feedback." : "");
      note.hidden = !note.textContent;
      if (!reasons.hidden) {
        // The options open below the last message: scroll the messages so they are in view, above the quick questions.
        scrollToLatest();
      }
      reasons.querySelectorAll(".rchip").forEach(function (b) {
        b.className = "rchip" + (rec.reason && (rec.reason === b.textContent || (b.textContent === "Other" && rec.reason.indexOf("Other: ") === 0)) ? " on" : "");
      });
    }
    up.onclick = function () {
      rec.feedback = rec.feedback === "up" ? null : "up";
      rec.reason = null;
      other.hidden = true;
      paint();
      saveLog();
      sendRating(rec);
    };
    down.onclick = function () {
      rec.feedback = rec.feedback === "down" ? null : "down";
      if (!rec.feedback) rec.reason = null;
      paint();
      saveLog();
      sendRating(rec);
    };
    paint();
    return wrap;
  }

  // One message: the text bubble, the time under it, and (for a reply) the thumbs up and down.
  function buildMessage(rec, div) {
    var col = document.createElement("div");
    col.className = rec.who === "me" ? "col col-me" : "col col-bot";
    col.dataset.id = rec.id;
    col.appendChild(div);
    var meta = document.createElement("div");
    meta.className = "meta";
    meta.dataset.at = rec.at;
    meta.textContent = timeLabel(rec.at);
    col.appendChild(meta);
    if (rec.who === "bot") col.appendChild(feedbackRow(rec));
    return col;
  }

  // Draws one saved message (a visitor's or the assistant's) at the end of the chat.
  function appendRecord(rec) {
    var div = document.createElement("div");
    div.className = "bubble " + rec.who;
    if (rec.who === "bot") div.innerHTML = richUpTo(richSegments(rec.text), plainText(rec.text).length);
    else div.textContent = rec.text;
    var col = buildMessage(rec, div);
    msgs.appendChild(rec.who === "bot" ? botRow(col) : col);
    scrollToLatest();
    return col;
  }

  // A bot reply may hold **bold** labels and line breaks. These helpers turn it into HTML safely, and let the
  // printing show the first characters of the plain text.
  function plainText(text) { return text.split("**").join(""); }
  function richSegments(text) {
    var out = [];
    text.split("**").forEach(function (part, i) { if (part) out.push({ text: part, bold: i % 2 === 1 }); });
    return out;
  }
  function escapeHtml(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function richUpTo(segs, count) {
    var html = "", left = count;
    segs.forEach(function (s) {
      if (left <= 0) return;
      var part = s.text.slice(0, left);
      left -= part.length;
      var safe = escapeHtml(part).replace(/\n/g, "<br>");
      html += s.bold ? "<b>" + safe + "</b>" : safe;
    });
    return html;
  }

  function bubble(text, who) {
    var col = appendRecord(record(who, text));
    if (who === "bot" && !panel.classList.contains("open")) {
      unread += 1;
      showUnread(text);
    }
    return col;
  }

  // ---- the request form: a card in the chat. The server sends its fields, pages and rules; nothing is saved until Send ----
  function todayISO() {
    var d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // The same rules as the server (shared/field_rules.py). The server checks again when the form is sent.
  function checkField(spec, raw, msg) {
    var v = (raw || "").trim();
    if (!v) return spec.required ? msg.required : "";
    if (spec.type === "integer" || spec.type === "number") {
      var n = Number(v);
      if (isNaN(n) || (spec.type === "integer" && n % 1 !== 0)) return spec.type === "integer" ? msg.integer : msg.number;
      if ((spec.min != null && n < spec.min) || (spec.max != null && n > spec.max)) {
        return msg.range.replace("{min}", spec.min != null ? spec.min : "-").replace("{max}", spec.max != null ? spec.max : "-");
      }
      return "";
    }
    var form = spec.format || "text";
    if (form === "phone") return /^[0-9]{7,15}$/.test(v.replace(/^\+/, "").replace(/[\s().\-]/g, "")) ? "" : msg.phone;
    if (form === "email") return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v) && v.length <= (spec.max || 120) ? "" : msg.email;
    if (form === "date") {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return msg.date;
      return v < todayISO() ? msg.date_past : "";
    }
    if (form === "time") return /^([01]\d|2[0-3]):[0-5]\d$/.test(v) ? "" : msg.time;
    if (form !== "name" && spec.min_length && v.length < spec.min_length) return msg.too_short.replace("{n}", spec.min_length);
    if (v.length > (spec.max || 300)) return msg.too_long.replace("{n}", spec.max || 300);
    return "";
  }

  function showForm(card) {
    var msg = card.messages || {};
    var labels = card.labels || { send: "Send", next: "Next", back: "Back", cancel: "Cancel", cancelled: "No problem, nothing was sent." };
    var values = {};
    Object.keys(card.values || {}).forEach(function (k) { values[k] = String(card.values[k]); });
    var errors = {};
    var page = 0;
    var busy = false;
    var box = el("div", "fcard");
    var row = botRow(box);
    msgs.appendChild(row);
    chipsBox.classList.remove("show");   // the quick questions give their room to the form while it is open

    function fieldsOf(p) { return card.pages[p].fields; }

    function keep() {   // what is typed on this page, kept when the visitor goes to another page
      box.querySelectorAll("[data-key]").forEach(function (f) { values[f.dataset.key] = f.value; });
    }

    // The errors of this page: each field's own rules, and the either groups that sit on this page.
    function checkPage() {
      var found = {};
      fieldsOf(page).forEach(function (spec) {
        var e = checkField(spec, values[spec.key], msg);
        if (e) found[spec.key] = e;
      });
      (card.any_of || []).forEach(function (group) {
        var here = fieldsOf(page).map(function (s) { return s.key; });
        if (!group.every(function (k) { return here.indexOf(k) >= 0; })) return;
        var any = group.some(function (k) { return (values[k] || "").trim(); });
        if (!any) group.forEach(function (k) { found[k] = msg.either.replace("{keys}", group.join(" or ")); });
      });
      return found;
    }

    function render(note) {
      box.innerHTML = "";
      box.appendChild(el("h4", "", card.title));
      if (card.pages.length > 1) box.appendChild(el("div", "fstep", "Step " + (page + 1) + " of " + card.pages.length));
      fieldsOf(page).forEach(function (spec) {
        var wrap = el("div", "ffield" + (errors[spec.key] ? " bad" : ""));
        var id = "ca-f-" + card.action_key + "-" + spec.key;
        var label = el("label", "", spec.label + (spec.required ? " *" : ""));
        label.htmlFor = id;
        var f = spec.input === "textarea" ? el("textarea") : el("input");
        if (spec.input !== "textarea") f.type = spec.input === "checkbox" ? "checkbox" : spec.input;
        f.id = id;
        f.dataset.key = spec.key;
        f.value = values[spec.key] || "";
        if (spec.max && spec.type == null) f.maxLength = spec.max;
        if (spec.input === "tel") { f.inputMode = "tel"; f.autocomplete = "tel"; }
        if (spec.input === "email") f.autocomplete = "email";
        if (spec.key === "name") f.autocomplete = "name";
        if (spec.input === "date") f.min = todayISO();
        if (spec.input === "number") { if (spec.min != null) f.min = spec.min; if (spec.max != null) f.max = spec.max; }
        if (errors[spec.key]) f.setAttribute("aria-invalid", "true");
        if (spec.input === "tel") f.oninput = function () { f.value = f.value.replace(/[^0-9+()\-. ]/g, ""); };   // digits only
        wrap.appendChild(label);
        wrap.appendChild(f);
        if (spec.help) wrap.appendChild(el("div", "fhelp", spec.help));
        var err = el("div", "ferr", errors[spec.key] || "");
        err.hidden = !errors[spec.key];
        err.setAttribute("role", "alert");
        wrap.appendChild(err);
        box.appendChild(wrap);
      });
      if (note) box.appendChild(el("div", "fnote", note));
      var nav = el("div", "fnav");
      var cancel = el("button", "fcancel", labels.cancel);   // on every page: nothing is sent
      cancel.type = "button";
      cancel.disabled = busy;
      cancel.onclick = function () { finish("cancelled"); bubble(labels.cancelled, "bot"); };
      nav.appendChild(cancel);
      if (page > 0) {
        var back = el("button", "fback", labels.back);
        back.type = "button";
        back.onclick = function () { keep(); errors = {}; page -= 1; render(); };
        nav.appendChild(back);
      }
      var last = page === card.pages.length - 1;
      var go = el("button", "fgo", last ? labels.send : labels.next);
      go.type = "button";
      go.disabled = busy;
      go.onclick = function () { keep(); errors = checkPage(); if (Object.keys(errors).length) render(); else if (last) send_(); else { page += 1; render(); } };
      nav.appendChild(go);
      box.appendChild(nav);
      // Show the top of the card (the title and the first field), not its end: a tall card must not be cut off at the top.
      requestAnimationFrame(function () {
        msgs.scrollTop = Math.max(0, row.getBoundingClientRect().top - msgs.getBoundingClientRect().top + msgs.scrollTop - 8);
      });
    }

    function finish(text) {
      box.innerHTML = "";
      box.appendChild(el("div", "fdone", card.title + ": " + text));
      renderChips();   // the quick questions are back
    }

    function send_() {
      busy = true;
      render();
      var c = consent();
      var body = base();
      body.action_key = card.action_key;
      body.values = values;
      body.consent = !!(c && c.choice === "accepted");
      if (body.consent) body.visitor_id = load(localStorage, K_VISITOR) || "";
      var sentAt = Date.now();
      showTyping();
      post("/chat/form", body).then(function (data) {
        return new Promise(function (resolve) { setTimeout(function () { resolve(data); }, Math.max(0, MIN_TYPING_MS - (Date.now() - sentAt))); });
      }).then(function (data) {
        hideTyping();
        busy = false;
        if (data.session_id) store(localStorage, K_SESSION, data.session_id);
        if (data.state === "form_errors" && data.errors) {   // the server did not accept some values: back to the first page with one
          errors = data.errors;
          for (var p = 0; p < card.pages.length; p++) {
            if (card.pages[p].fields.some(function (s) { return errors[s.key]; })) { page = p; break; }
          }
          render();
          return;
        }
        if (data.state === "stopped" || data.state === "blocked") drop(localStorage, K_SESSION);
        finish(data.state === "reply" ? "sent" : "not sent");
        bubble(data.reply || UNAVAILABLE, "bot");
      }).catch(function () {
        hideTyping();
        busy = false;
        render("Sorry, we couldn't send that. Please try again.");
      });
    }

    render();
  }

  // The whole chat again, from the log: after a page load, or when another tab changed it.
  function renderChat() {
    msgs.innerHTML = "";
    typingEl = null;
    current.messages.forEach(appendRecord);
    quickList = current.lastTopic ? quickAfter(current.lastTopic) : DEFAULT_QUESTIONS;
  }

  function idleTooLong(chat) {
    var last = chat.messages.length ? chat.messages[chat.messages.length - 1].at : chat.started;
    return Date.now() - new Date(last).getTime() >= 30 * MINUTE;
  }

  // A chat ends only when the visitor closes it, or after 30 minutes with no activity.
  function checkIdle() {
    if (!current || !idleTooLong(current)) return;
    endChat();
    msgs.innerHTML = "";
    typingEl = null;
    hideTyping();
    greeted = false;
    quickList = DEFAULT_QUESTIONS;
    setInput(true);
    if (panel.classList.contains("open")) {
      startChat();
      greeted = true;
      bubble(teaserText, "bot");
    }
  }
  setInterval(checkIdle, 30000);

  // On every page load, the open chat comes back as it was (it stays open until closed or idle for 30 minutes).
  function restoreChat() {
    var open = readLog().filter(function (c) { return !c.ended; });
    if (!open.length) return;
    current = open[open.length - 1];
    if (idleTooLong(current)) { endChat(); return; }
    greeted = current.messages.length > 0;
    renderChat();
  }

  // Another tab changed the chat: show the same chat here.
  window.addEventListener("storage", function (e) {
    if (e.key !== K_LOG) return;
    var open = readLog().filter(function (c) { return !c.ended; });
    var latest = open.length ? open[open.length - 1] : null;
    if (latest && (!current || latest.id === current.id)) {
      current = latest;
      greeted = current.messages.length > 0;
      renderChat();
    } else if (!latest && current) {
      current = null;
      msgs.innerHTML = "";
      greeted = false;
    }
  });

  // A reply that arrived while the widget was minimised: a count on the launcher, and a notice with its start.
  function showUnread(text) {
    badge.classList.remove("dot-only");
    badge.textContent = unread;
    badge.hidden = false;
    notice.textContent = "";
    var label = document.createElement("b");
    label.textContent = "New message";
    notice.appendChild(label);
    notice.appendChild(document.createTextNode(text.length > 90 ? text.slice(0, 87) + "…" : text));
    notice.hidden = false;
    launch.classList.remove("ring");
    void launch.offsetWidth; // restart the shake
    launch.classList.add("ring");
  }

  function clearUnread() {
    unread = 0;
    badge.classList.remove("dot-only");
    badge.hidden = true;
    notice.hidden = true;
  }

  function showTyping() {
    if (typingEl) return;
    var dots = document.createElement("div");
    dots.className = "bubble bot typing";
    dots.innerHTML = "<span></span><span></span><span></span>";
    typingEl = botRow(dots);
    typingEl.setAttribute("aria-label", "Assistant is typing");
    msgs.appendChild(typingEl);
    scrollToLatest();
  }

  function hideTyping() {
    if (typingEl) typingEl.remove();
    typingEl = null;
  }

  // The text box, the send button and the quick questions are off while the assistant is busy.
  function setInput(enabled) {
    input.disabled = !enabled;
    sendBtn.disabled = !enabled;
    chipsBox.querySelectorAll(".chip").forEach(function (b) { b.disabled = !enabled; });
  }

  // Three seconds after the page loads, the greeting pops up as a bubble for five seconds, then fades away.
  // Once it has gone, a red dot on the launcher shows there is a message, until the visitor opens the chat.
  function popUp() {
    if (host.style.display === "none" || panel.classList.contains("open")) return;
    teaser.textContent = teaserText;
    teaser.classList.add("show");
    autoTimer = setTimeout(function () {
      hideTeaser();
      if (!panel.classList.contains("open")) showDot();
    }, TEASER_MS);
  }

  function showDot() {
    badge.classList.add("dot-only");
    badge.textContent = "";
    badge.hidden = false;
  }

  function hideTeaser() {
    if (autoTimer) clearTimeout(autoTimer);
    autoTimer = null;
    teaser.classList.remove("show");
  }

  // ---- quick questions: always under the chat; after an answer, the questions most likely to come next ----
  var DEFAULT_QUESTIONS = ["Book a table", "View the menu", "Opening hours", "Directions", "Online ordering"];
  // After a reply, the quick questions to show next. The customer's own map comes first (customer table), then the
  // category's map (category table). A topic in neither map gets the defaults, except the question just asked.
  var TOPIC_QUESTION = {
    menu: "View the menu",
    hours: "Opening hours",
    booking: "Book a table",
    directions: "Directions",
    ordering: "Online ordering"
  };
  function quickAfter(topic) {
    var customerMap = (config && config.customer_quick_map) || {};
    var categoryMap = (config && config.category_quick_map) || {};
    if (customerMap[topic]) return customerMap[topic];
    if (categoryMap[topic]) return categoryMap[topic];
    var asked = TOPIC_QUESTION[topic];
    return ((config && config.default_questions) || DEFAULT_QUESTIONS).filter(function (q) { return q !== asked; });
  }

  function renderChips() {
    chipsBox.innerHTML = "";
    if (!quickList.length) { chipsBox.classList.remove("show"); scrollToLatest(); return; }
    chipsBox.style.gridTemplateColumns = "repeat(" + (quickList.length === 4 ? 2 : 3) + ", minmax(0, 1fr))";
    quickList.forEach(function (q) {
      var b = document.createElement("button");
      b.className = "chip";
      b.type = "button";
      b.textContent = q;
      b.disabled = input.disabled;
      b.onclick = function () { send(q, actionByLabel[q]); };
      chipsBox.appendChild(b);
    });
    chipsBox.classList.add("show");
    scrollToLatest(); // the quick questions take room from the messages: keep the newest message above them
  }

  function showConsent() {
    consentBox.hidden = false;
    consentBox.innerHTML = "";
    var p = document.createElement("div");
    p.textContent = NOTICE;
    var yes = document.createElement("button");
    yes.textContent = "Accept";
    var no = document.createElement("button");
    no.className = "alt";
    no.textContent = "Decline";
    consentBox.appendChild(p);
    consentBox.appendChild(yes);
    consentBox.appendChild(no);
    yes.onclick = function () { chooseConsent(true); consentBox.hidden = true; };
    no.onclick = function () { chooseConsent(false); consentBox.hidden = true; };
  }

  function post(path, body) {
    return fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) { return r.json(); });
  }

  function base() {
    var sid = load(localStorage, K_SESSION);
    var block = load(localStorage, K_BLOCK);
    var body = { site_key: SITE_KEY, domain: location.host };
    if (sid) body.session_id = sid;
    if (block) body.block_token = block;
    if (PAGE_TRACKING) body.activity_id = currentVisit();
    return body;
  }

  function handle(data) {
    if (data.state !== "waiting") clearReplyLimit(); // the reply is here (or the chat has stopped)
    if (data.session_id) store(localStorage, K_SESSION, data.session_id);
    if (data.block_token) store(localStorage, K_BLOCK, data.block_token);
    if (data.state === "waiting") { startPolling(); return; }
    stopPolling();
    hideTyping();
    if (data.state === "reply" && data.reply) {
      bubble(data.reply, "bot");
      if (data.card) showForm(data.card);
      setInput(true);
    } else if (data.state === "stopped" || data.state === "blocked") {
      bubble(data.reply || UNAVAILABLE, "bot");
      drop(localStorage, K_SESSION); // the next message starts a new chat
      setInput(data.state === "stopped"); // an ended chat can start again; a blocked visitor cannot
    } else {
      setInput(true);
    }
  }

  function startPolling() {
    if (pollTimer) return;
    setInput(false);
    var token = replyToken;
    pollTimer = setInterval(function () {
      var body = base();
      post("/chat/poll", body).then(function (data) { if (token === replyToken) handle(data); }).catch(function () {
        stopPolling();
        hideTyping();
        bubble("Sorry, we couldn't reach the chat. Please try again.", "bot");
        setInput(true);
      });
    }, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  // ---- the demo: mock replies from the mock Spice Garden data, with the same timing as the real chat ----
  var MOCK_CONFIG = {
    enabled: true,
    title: "Spice Garden",
    teaser: "Hi, I'm an AI assistant for Spice Garden. I'm here to help you.",
    default_questions: DEFAULT_QUESTIONS,
    // The quick-question map: the customer's own map is read first, then the category's (demo: the customer has none yet).
    customer_quick_map: {},
    category_quick_map: {
      menu: ["Book a table", "Opening hours", "Directions", "Online ordering"],
      hours: ["Book a table", "Directions", "Online ordering", "View the menu"],
      booking: ["Opening hours", "Directions", "View the menu", "Online ordering"],
      directions: ["Opening hours", "Book a table", "View the menu", "Online ordering"],
      ordering: ["View the menu", "Opening hours", "Book a table", "Directions"]
    },
    // Chef's specials and the full menu link: set by the business in the admin page when the widget is enabled.
    chef_specials: ["Chicken Biryani", "Paneer Tikka", "Vegetable Korma"],
    menu_url: "https://spicegarden.example/menu",
    theme: null
  };

  // Returns the reply and the topic it answers (the topic picks the next quick questions).
  function mockReply(text) {
    var t = text.toLowerCase();
    function reply(topic, words) { return { topic: topic, text: words }; }
    if (/menu|dish|eat/.test(t)) {
      // The full menu is not listed in the chat: the chef's specials, and a link to the full menu.
      var specials = (config && config.chef_specials) || MOCK_CONFIG.chef_specials;
      var link = (config && config.menu_url) || MOCK_CONFIG.menu_url;
      return reply("menu", "Our chef's specials today:\n- " + specials.join("\n- ") + "\n\nView the full menu: " + link);
    }
    if (/hour|open|close|time/.test(t)) return reply("hours", "We're open Monday to Friday from 11:00 to 22:00, and Saturday and Sunday from 12:00 to 23:00.");
    if (/direction|where|located|address|get to/.test(t)) return reply("directions", "You can find us at 12 Market Street, Austin, TX.");
    if (/book|table|reserv/.test(t)) return reply("booking", "You can book a table here: https://www.google.com");
    if (/order|takeaway|deliver/.test(t)) return reply("ordering", "For online orders, please contact us at hello@spicegarden.example or +1 555 0123.");
    if (/vegetarian|veg\b|vegan/.test(t)) return reply("dietary", "Yes, the Paneer Tikka and the Vegetable Samosa are vegetarian.");
    if (/park/.test(t)) return reply("parking", "I don't have parking details yet. Would you like me to pass your question to Spice Garden?");
    if (/thank|cheers/.test(t)) return reply("thanks", "You're welcome! Is there anything else I can help you with?");
    if (/bye|goodbye|see you/.test(t)) return reply("bye", "Goodbye, and thanks for visiting Spice Garden!");
    if (/bot|human|real person|who are you|your name/.test(t)) return reply("ai", "I'm an AI assistant for Spice Garden, not a person.");
    if (/person|someone|manager|call me/.test(t)) return reply("person", "I can pass this to Spice Garden, and they will contact you soon.");
    if (/^(hi|hello|hey|good (morning|afternoon|evening))\b/.test(t)) return reply("greeting", "Hi, I'm here to help with Spice Garden. What would you like to know?");
    return reply("other", "I'm sorry, I can't answer that yet. Would you like me to pass your question to Spice Garden?");
  }

  // The reply prints word by word over DEMO_PRINT_MS. Both controls come back on when the printing starts.
  // A map for the business's location (demo: an OpenStreetMap view of the mock address, centred on Austin).
  // Placeholder coordinates for the demo. The business's real latitude and longitude go in its data.
  var MAP = { lat: 30.2672, lon: -97.7431 };
  function mapCard() {
    var box = document.createElement("div");
    box.className = "mapcard";
    var frame = document.createElement("iframe");
    var d = 0.006;
    frame.src = "https://www.openstreetmap.org/export/embed.html?bbox=" + (MAP.lon - d) + "%2C" + (MAP.lat - d) + "%2C" +
      (MAP.lon + d) + "%2C" + (MAP.lat + d) + "&layer=mapnik&marker=" + MAP.lat + "%2C" + MAP.lon;
    frame.title = "Map to the restaurant";
    frame.loading = "lazy";
    var directions = document.createElement("a");
    // The same point as the map, so both show one place (the address text alone is looked up and can land elsewhere).
    directions.href = "https://www.google.com/maps/dir/?api=1&destination=" + MAP.lat + "," + MAP.lon;
    directions.target = "_blank";
    directions.rel = "noopener";
    directions.className = "gdir";
    directions.textContent = "Get directions on Google Maps";
    var link = document.createElement("a");
    link.href = "https://www.openstreetmap.org/?mlat=" + MAP.lat + "&mlon=" + MAP.lon + "#map=16/" + MAP.lat + "/" + MAP.lon;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Open the map";
    box.appendChild(frame);
    box.appendChild(directions);
    box.appendChild(link);
    return box;
  }

  function printReply(text, topic) {
    var rec = record("bot", text);
    var div = document.createElement("div");
    div.className = "bubble bot";
    var col = buildMessage(rec, div);
    if (topic === "directions") col.insertBefore(mapCard(), col.querySelector(".meta"));
    msgs.appendChild(botRow(col));
    setInput(true); // the visitor can type again as soon as the reply starts to print
    var steps = Math.max(1, Math.round(DEMO_PRINT_MS / 40));
    var segs = richSegments(text), total = plainText(text).length;
    var perStep = Math.ceil(total / steps);
    var shown = 0;
    var timer = setInterval(function () {
      shown = Math.min(total, shown + perStep);
      div.innerHTML = richUpTo(segs, shown);
      scrollToLatest();
      if (shown >= total) {
        clearInterval(timer);
        current.lastTopic = topic || null;
        quickList = quickAfter(topic);
        renderChips();
        saveLog();
      }
    }, 40);
    if (!panel.classList.contains("open")) {
      unread += 1;
      showUnread(plainText(text));
    }
  }

  // After a reply the bot could not answer: Yes or No to sharing the question with the business.
  function showOffer() {
    var box = document.createElement("div");
    box.className = "offer";
    box.style.cssText = "display:flex;gap:8px;padding:0 4px 4px;";
    box.innerHTML = '<button type="button" data-choice="yes" style="border:1px solid #d9cfc6;border-radius:999px;background:#fff;padding:6px 16px;font:inherit;cursor:pointer">Yes</button>' +
      '<button type="button" data-choice="no" style="border:1px solid #d9cfc6;border-radius:999px;background:#fff;padding:6px 16px;font:inherit;cursor:pointer">No</button>';
    box.addEventListener("click", function (e) {
      var b = e.target.closest("[data-choice]"); if (!b) return;
      var yes = b.dataset.choice === "yes";
      box.remove();
      bubble(yes ? "Yes" : "No", "me");
      var title = (config && config.title) || "Spice Garden";
      var reply = yes ? "Thank you. Please share your name and an email or phone number, and " + title + " will get back to you."
                      : "No problem. What else can I help you with?";
      showTyping();
      setTimeout(function () { hideTyping(); printReply(reply, null); }, 1200);
    });
    msgs.appendChild(box);
    scrollToLatest();
  }

  // The 30-second limit: no reply in time, the box unlocks and the visitor is asked to repeat the question.
  // A reply that comes later to that question is dropped, so the visitor does not get two answers.
  function startReplyLimit() {
    var token = ++replyToken;
    if (replyTimer) clearTimeout(replyTimer);
    replyTimer = setTimeout(function () {
      replyTimer = null;
      if (token !== replyToken) return;
      replyToken++;            // the late reply, if any, is dropped
      stopPolling();
      hideTyping();
      bubble("Sorry, this is taking longer than usual. Can you repeat the question?", "bot");
      setInput(true);
    }, REPLY_LIMIT_MS);
    return token;
  }

  function clearReplyLimit() {
    if (replyTimer) clearTimeout(replyTimer);
    replyTimer = null;
  }

  function send(preset, actionKey) {
    var text = (typeof preset === "string" ? preset : input.value).trim();
    if (!text) return;
    input.value = "";
    bubble(text, "me");
    showTyping(); // shown from the first message on, until the reply arrives
    setInput(false);
    var token = startReplyLimit();
    if (DEMO) {
      var canned = mockReply(text);
      var wait = new Promise(function (resolve) { setTimeout(resolve, /slow/i.test(text) ? DEMO_SLOW_MS : DEMO_WAIT_MS); });
      // With the dashboard's address, the answer comes from the same engine as the dashboard's Playground.
      var fromEngine = PLAY_URL ? fetch(PLAY_URL, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text })
      }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (j) { return { topic: canned.topic, text: j.answer, offer: !!j.offer }; })
        .catch(function () { return canned; }) : Promise.resolve(canned);
      Promise.all([wait, fromEngine]).then(function (both) {
        if (token !== replyToken) return; // too late: the visitor was asked to repeat
        clearReplyLimit();
        hideTyping();
        printReply(both[1].text, both[1].topic);
        if (both[1].offer) showOffer();
      });
      return;
    }
    var c = consent();
    var body = base();
    body.text = text;
    if (actionKey) body.action_key = actionKey;   // a quick-question click: the server needs no model for it
    body.msg_id = newId();
    body.consent = !!(c && c.choice === "accepted");
    if (body.consent) body.visitor_id = load(localStorage, K_VISITOR) || "";
    var sentAt = Date.now();
    post("/chat/message", body).then(function (data) {
      // The typing dots stay until MIN_TYPING_MS has passed since the question was sent (a waiting turn is polled, not shown).
      setTimeout(function () { if (token === replyToken) handle(data); }, Math.max(0, MIN_TYPING_MS - (Date.now() - sentAt)));
    }).catch(function () {
      if (token !== replyToken) return;
      clearReplyLimit();
      hideTyping();
      bubble("Sorry, we couldn't send that. Please try again.", "bot");
      setInput(true);
    });
  }

  function open() {
    panel.classList.add("open");
    if (!document.hidden && !widgetSince) widgetSince = Date.now();
    track("widget_open");
    launch.style.display = "none";
    clearUnread();
    hideTeaser();
    startChat();
    if (!greeted) {
      bubble(teaserText, "bot");
      greeted = true;
    }
    renderChips();
    if (!consent()) showConsent();
    input.focus();
  }

  // Minimise: hide the panel but keep the chat and its history, as the visitor left it (the X ends the chat).
  function minimise() {
    panel.classList.remove("open");
    stopWidgetTimer();
    launch.style.display = "";
  }

  function close() {
    panel.classList.remove("open");
    stopWidgetTimer();
    launch.style.display = "";
    clearUnread();
    var sid = load(localStorage, K_SESSION);
    stopPolling();
    if (sid) {
      if (!DEMO) post("/chat/close", { site_key: SITE_KEY, domain: location.host, session_id: sid }).catch(function () {});
      drop(localStorage, K_SESSION);
    }
    endChat();
    msgs.innerHTML = "";
    typingEl = null;
    greeted = false;
    quickList = (config && config.default_questions) || DEFAULT_QUESTIONS;
    setInput(true);
  }

  // The greeting text comes from the bundle (the teaser text).
  function applyConfig(c) {
    config = c;
    if (!c.enabled) { host.style.display = "none"; return; }
    // The colours this domain was given in the dashboard (widget settings). Set on the host, they win over :host.
    if (c.theme) {
      host.style.setProperty("--brand", c.theme.primary);
      host.style.setProperty("--brand-2", c.theme.accent);
    }
    titleEl.textContent = c.title;
    panel.setAttribute("aria-label", c.title);
    teaserText = c.teaser;
    actionByLabel = {};
    (c.quick_actions || []).forEach(function (a) { actionByLabel[a.label] = a.key; });
    // A restored chat keeps its own quick questions; a new chat starts with the defaults.
    if (!current || !current.lastTopic) quickList = c.default_questions || DEFAULT_QUESTIONS;
  }

  function loadConfig() {
    if (DEMO) { applyConfig(MOCK_CONFIG); return; }
    fetch(API + "/chat/config?site_key=" + encodeURIComponent(SITE_KEY) + "&domain=" + encodeURIComponent(location.host))
      .then(function (r) { if (!r.ok) throw new Error("config " + r.status); return r.json(); })
      .then(applyConfig)
      .catch(function () {
        // The API is not reachable or does not know this domain: the widget still works, with the fallback text.
      });
  }

  // --- page activity -----------------------------------------------------------------------------------------
  // A visit is one stretch of activity on the site: a new one starts after 30 minutes with no activity. The widget
  // counts page views, clicks and time (on the page and in the widget). It does not record addresses or text.
  var visit = null;               // {id, last} for the visit this page belongs to
  var pending = [];               // events not sent yet
  var lastPath = location.pathname;
  var visibleMs = 0;
  var visibleSince = document.hidden ? null : Date.now();
  var widgetMs = 0;
  var widgetSince = null;

  function currentVisit() {
    if (!visit || Date.now() - visit.last > VISIT_IDLE_MS) {
      var stored = null;
      try { stored = JSON.parse(load(localStorage, K_VISIT) || "null"); } catch (e) {}
      visit = stored && stored.id && Date.now() - stored.last <= VISIT_IDLE_MS ? stored : { id: newId(), last: Date.now() };
    }
    visit.last = Date.now();
    store(localStorage, K_VISIT, JSON.stringify(visit));
    return visit.id;
  }

  function track(kind) {
    if (PAGE_TRACKING) pending.push({ type: kind });
  }

  function visibleNow() { return visibleMs + (visibleSince ? Date.now() - visibleSince : 0); }
  function widgetNow() { return widgetMs + (widgetSince ? Date.now() - widgetSince : 0); }
  function stopWidgetTimer() {
    if (widgetSince) { widgetMs += Date.now() - widgetSince; widgetSince = null; }
  }

  // Sends the events in one small request. keepalive lets it finish while the page is closing.
  function flush() {
    if (!PAGE_TRACKING || (document.hidden && !pending.length)) return;
    pending.push({ type: "heartbeat", visible_seconds: Math.round(visibleNow() / 1000), widget_seconds: Math.round(widgetNow() / 1000) });
    var events = pending.splice(0, pending.length);
    fetch(API + "/activity", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({ site_key: SITE_KEY, domain: location.host, activity_id: currentVisit(), events: events }),
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (data.visit === "ended") startNewVisit();
    }).catch(function () {});
  }

  // The server ended this visit (30 minutes with no activity): the next events belong to a new visit.
  function startNewVisit() {
    visit = null;
    drop(localStorage, K_VISIT);
    visibleMs = 0;
    widgetMs = 0;
    visibleSince = document.hidden ? null : Date.now();
    widgetSince = panel.classList.contains("open") && !document.hidden ? Date.now() : null;
    track("page_view");
  }

  function pageChanged() {
    if (location.pathname === lastPath) return;
    lastPath = location.pathname;
    track("page_view");
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      if (visibleSince) { visibleMs += Date.now() - visibleSince; visibleSince = null; }
      stopWidgetTimer();
      flush();
    } else {
      visibleSince = Date.now();
      if (panel.classList.contains("open")) widgetSince = Date.now();
    }
  });

  // A click on the host page (not inside the widget). Only the fact of the click is counted.
  document.addEventListener("click", function (e) {
    if (e.composedPath().indexOf(host) === -1) track("click");
  });

  // A click anywhere outside the widget minimises it. A click inside it has the host in its path.
  document.addEventListener("click", function (e) {
    if (!panel.classList.contains("open")) return;
    if (e.composedPath().indexOf(host) !== -1) return;
    minimise();
  });

  launch.addEventListener("click", function () { open(); });
  teaser.addEventListener("click", function () { open(); });
  teaser.addEventListener("keydown", function (e) { if (e.key === "Enter") open(); });
  notice.addEventListener("click", function () { open(); });
  notice.addEventListener("keydown", function (e) { if (e.key === "Enter") open(); });

  restoreChat();
  setTimeout(popUp, POP_MS);
  root.querySelector(".close").addEventListener("click", close);
  sendBtn.addEventListener("click", function () { send(); });
  input.addEventListener("keydown", function (e) { if (e.key === "Enter") send(); });
  if (PAGE_TRACKING) {
    track("page_view");
    ["pushState", "replaceState"].forEach(function (name) {
      var original = history[name];
      history[name] = function () { var result = original.apply(this, arguments); pageChanged(); return result; };
    });
    window.addEventListener("popstate", pageChanged);
    window.addEventListener("pagehide", flush);
    setTimeout(flush, 2000);
    setInterval(flush, BEAT_MS);
  }
  loadConfig();
})();
