/* The review page (SYS-45, SYS-46, SYS-51, REVIEW-20 to REVIEW-27). Plain JavaScript; nothing from the network. */
(() => {
  "use strict";
  const DATA = JSON.parse(document.getElementById("review-data").textContent);
  const ITEMS = DATA.items;
  const META = DATA.meta;
  const LEVELS = META.levels;
  const LEVEL_WORDS = { explicit: "explicit · locked", stated: "stated", guided: "guided", derived: "derived", added: "added" };
  const CLASS_WORDS = { added: "added", removed: "removed", moved: "moved", meaning: "changed in meaning",
    reworded: "reworded", intent: "intent only", details: "details only" };
  const ID_RE = /\b([A-Z][A-Z0-9]*-V?\d+|[A-Z]{2,}[A-Z0-9]*)\b/g;

  // ---------------------------------------------------------------- tiny DOM helpers
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "html") el.innerHTML = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const ICONS = {
    lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    unlock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    comment: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    undo: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    compare: '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><path d="M11 18H8a2 2 0 0 1-2-2V9"/>',
    sparkles: '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.14-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0l1.58 6.14a2 2 0 0 0 1.44 1.44l6.14 1.58a.5.5 0 0 1 0 .96l-6.14 1.58a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    graph: '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/>',
    list: '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
    reply: '<polyline points="15 10 20 15 15 20"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    pencil: '<path d="M21.17 6.81a1 1 0 0 0-3.99-3.99L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"/>',
  };
  function fill(el, ...kids) {
    el.replaceChildren(...kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false));
  }
  function icon(name, cls) {
    const span = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    span.setAttribute("viewBox", "0 0 24 24");
    span.setAttribute("class", "icon" + (cls ? " " + cls : ""));
    span.setAttribute("aria-hidden", "true");
    span.innerHTML = ICONS[name] || "";
    return span;
  }
  function brief(text, n) {
    const words = String(text || "").split(/\s+/).filter(Boolean);
    return words.slice(0, n || 10).join(" ") + (words.length > (n || 10) ? "…" : "");
  }
  function label(id) {
    const it = ITEMS[id];
    return it ? `${id} (${brief(it.title || it.text, 9)})` : id;
  }

  // ---------------------------------------------------------------- feedback state (REVIEW-23)
  const KEY = "syseng-feedback:" + META.repository;
  function load() {
    try {
      const s = JSON.parse(localStorage.getItem(KEY) || "null");
      if (s && typeof s === "object") return Object.assign({ items: {}, decisions: {}, general: "" }, s);
    } catch (e) { /* storage may be unavailable; the page still works without it */ }
    return { items: {}, decisions: {}, general: "", person: null };
  }
  let state = load();
  // feedback already applied isn't sent again (REVIEW-23): a review this page copied that the agent has since applied
  if ((state.copied || []).some((r) => (META.applied || []).includes(r)))
    state = { items: {}, decisions: {}, general: "", person: state.person };
  const person = () => state.person || META.person;
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* see load */ }
    renderBar();
  }
  function itemState(id) {
    const s = state.items[id] || (state.items[id] = {});
    s.fingerprint = ITEMS[id] ? ITEMS[id].fingerprint : s.fingerprint;
    return s;
  }
  function answeredWording(id, s) { return s.wording !== undefined && s.wording !== ((ITEMS[id] || {}).text || ""); }
  function answered(id) {
    const s = state.items[id] || {};
    return s.lock !== undefined || !!s.comment || !!s.alteration || answeredWording(id, s);
  }
  function prune(id) {
    const s = state.items[id];
    if (!s) return;
    const meaningful = s.lock !== undefined || s.comment !== undefined || s.alteration || s.wording !== undefined ||
      (s.intent && Object.keys(s.intent).length);
    if (!meaningful) delete state.items[id];
  }

  // ---------------------------------------------------------------- theme
  function applyTheme(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    const btn = document.getElementById("theme");
    if (btn) { btn.replaceChildren(icon(currentTheme() === "dark" ? "sun" : "moon")); }
  }
  function currentTheme() { return document.documentElement.getAttribute("data-theme") || "dark"; }
  try { applyTheme(localStorage.getItem("syseng-theme") || "dark"); } catch (e) { applyTheme("dark"); }

  // ---------------------------------------------------------------- IDs (REVIEW-15, REVIEW-28, REVIEW-29)
  // Clicking an ID opens the item in the side pane, without moving the reader's place; pointing at an ID or an
  // item's card highlights it in the graph.
  function idButton(id) {
    return h("button", { class: "id", type: "button", "data-id": id,
      onclick: (e) => { e.stopPropagation(); openItem(id); } }, id);
  }
  function linkify(text) {
    const frag = document.createDocumentFragment();
    let last = 0;
    String(text || "").replace(ID_RE, (m, id, at) => {
      if (!ITEMS[id]) return m;
      frag.append(text.slice(last, at), idButton(id));
      last = at + m.length;
      return m;
    });
    frag.append(String(text || "").slice(last));
    return frag;
  }
  const tip = h("div", { class: "tip", hidden: true });
  document.body.append(tip);
  function showTip(id, e) {
    const it = ITEMS[id];
    tip.replaceChildren(h("div", { class: "item-head" }, h("span", { class: "mono" }, id), levelChip(id), statusChips(id)),
      h("div", { class: "item-text" }, brief(it.title || it.text, 30)));
    tip.hidden = false;
    const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const y = e.clientY + 16 + tip.offsetHeight > window.innerHeight ? e.clientY - tip.offsetHeight - 10 : e.clientY + 16;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  function hideTip() { tip.hidden = true; }

  // ---------------------------------------------------------------- shared pieces
  function levelChip(id, level) {
    const it = level ? null : ITEMS[id];
    const lv = level || (it && it.level);
    if (!lv) return null;
    if (it && it.given)  // given for an earlier version and not kept since: it counts one level lower (DR-68)
      return h("span", { class: "lv stale", title: `counts as ${lv} until you keep it` }, h("span", { class: `sw lv-${lv} ${lv}` }),
        icon("unlock", "sm"), it.label);
    return h("span", { class: "lv", title: "level of intent" }, h("span", { class: `sw lv-${lv} ${lv}` }), LEVEL_WORDS[lv] || lv);
  }
  function triage(card, done) {  // an item the person has acted on shows as answered (REVIEW-31)
    const check = () => card.classList.toggle("done", done());
    check();
    return check;
  }
  function statusChips(id) {
    const it = ITEMS[id];
    const out = [];
    if (it && it.changed && !it.given) out.push(h("span", { class: "status warning", title: "changed since a person gave it" }, icon("alert", "sm"), "changed since"));
    if (it && it.under && (it.level === "derived" || it.level === "added"))
      out.push(h("span", { class: "small" }, "under ", idButton(it.under)));
    return out;
  }
  function intentBlock(id, rec, index, editable) {
    const box = h("div", { class: "intent" },
      h("div", { class: "row small" }, icon("user", "sm"), h("span", {}, rec.by), h("span", { class: "mono" }, rec.when),
        h("span", { class: "chip" }, rec.basis)),
      h("div", { class: "said" }, linkify(rec.said)),
      rec.context ? h("div", { class: "ctx" }, linkify(rec.context)) : null);
    if (editable && index !== null) box.append(intentActions(id, index));
    return box;
  }
  function intentActions(id, index) {
    const s = () => itemState(id);
    const cur = () => (s().intent || {})[index] || {};
    const wrap = h("div", {});
    function draw() {
      const c = cur();
      fill(wrap, h("div", { class: "actions" },
        h("button", { class: "act" + (c.action === "correct" ? " on" : ""), onclick: () => set(c.action === "correct" ? null : "correct") },
          icon("pencil", "sm"), "Correct"),
        h("button", { class: "act danger" + (c.action === "remove" ? " on danger" : ""), onclick: () => set(c.action === "remove" ? null : "remove") },
          icon("trash", "sm"), "Not what I meant")),
        c.action === "correct" ? h("textarea", { class: "note", placeholder: "What you meant, in your words. The agent rewrites the summary.",
          oninput: (e) => { cur().correction = e.target.value; save(); } }, c.correction || "") : null);
    }
    function set(action) {
      const st = s();
      st.intent = st.intent || {};
      if (action) st.intent[index] = { action, correction: (st.intent[index] || {}).correction || "" };
      else delete st.intent[index];
      prune(id); save(); draw();
    }
    draw();
    return wrap;
  }
  function itemActions(id, opts) {
    const it = ITEMS[id];
    const wrap = h("div", {});
    const set = (fn) => { const st = itemState(id); fn(st); prune(id); save(); draw(); if (opts && opts.onchange) opts.onchange(); };
    function draw() {
      const s = state.items[id] || {};
      const locked = it.level === "explicit" && !it.changed;
      const row = h("div", { class: "actions" });
      if (opts && opts.alteration) {
        row.append(h("button", { class: "act" + (s.alteration === "keep" ? " on" : ""), "aria-pressed": s.alteration === "keep",
          onclick: () => set((st) => { if (st.alteration === "keep") delete st.alteration; else st.alteration = "keep"; }) },
        icon("check", "sm"), s.alteration === "keep" ? "Kept" : "Keep"),
        h("button", { class: "act" + (s.alteration === "roll back" ? " on danger" : ""), "aria-pressed": s.alteration === "roll back",
          onclick: () => set((st) => { if (st.alteration === "roll back") delete st.alteration; else st.alteration = "roll back"; }) },
        icon("undo", "sm"), "Roll back"));
      } else {
        const want = !locked;
        const on = s.lock === want;
        row.append(h("button", { class: "act" + (on ? " on" : ""), "aria-pressed": on,
          onclick: () => set((st) => { if (on) delete st.lock; else st.lock = want; }) },
        icon(on ? "check" : locked ? "unlock" : "lock", "sm"), on ? (locked ? "Unlocking" : "Locking") : (locked ? "Unlock" : "Lock")));
      }
      row.append(h("button", { class: "act" + (s.wording !== undefined ? " on" : ""),
        onclick: () => set((st) => { if (st.wording !== undefined) delete st.wording; else st.wording = it.text || ""; }) },
      icon("pencil", "sm"), "Suggest wording"),
      h("button", { class: "act" + (s.comment !== undefined ? " on" : ""),
        onclick: () => set((st) => { if (st.comment !== undefined && !st.comment) delete st.comment; else if (st.comment === undefined) st.comment = ""; }) },
      icon("comment", "sm"), "Comment"));
      fill(wrap, row,
        s.wording !== undefined ? h("textarea", { class: "note wording", "aria-label": `Your wording for ${id}`,
          oninput: (e) => { itemState(id).wording = e.target.value; save(); if (opts && opts.onchange) opts.onchange(); } }, s.wording) : null,
        s.comment !== undefined ? h("textarea", { class: "note", placeholder: "Your comment, a question, or the change you want. The agent answers each one.",
          oninput: (e) => { itemState(id).comment = e.target.value; save(); if (opts && opts.onchange) opts.onchange(); } }, s.comment) : null);
    }
    draw();
    return wrap;
  }
  // what changed on each item since the person last looked: the first comparison, then unanswered alterations (REVIEW-33)
  const CHANGE = {};
  const RANK = ["added", "meaning", "moved", "reworded", "intent", "details"];
  const CHIP_WORDS = { added: "new", meaning: "edited", moved: "moved", reworded: "reworded", intent: "intent changed", details: "details changed" };
  if (DATA.changes.length) for (const d of DATA.changes[0].items)
    if (!d.classes.includes("removed")) CHANGE[d.id] = { cls: d.classes.slice().sort((a, b) => RANK.indexOf(a) - RANK.indexOf(b))[0],
      before: d.before || {}, after: d.after || {}, since: DATA.changes[0].older.label };
  for (const a of DATA.awaiting.alterations) {
    if (CHANGE[a.id]) continue;
    const before = {}, after = {};
    for (const e of a.entries) {
      for (const [k, v] of Object.entries(e.before || {})) if (!(k in before)) before[k] = v;
      Object.assign(after, e.after || {});
    }
    CHANGE[a.id] = { cls: a.entries.every((e) => e.rewording) ? "reworded" : "meaning", before, after, since: `before ${a.change}` };
  }
  // diff mode: each item's own toggle (REVIEW-34), on top of one switch for every item (REVIEW-35)
  let diffAll = false;
  try { diffAll = localStorage.getItem("syseng-diff") === "1"; } catch (e) { /* fine */ }
  const diffOne = {};
  const bodies = new Set();
  const TEXT_KEYS = ["text", "description", "purpose"];
  const showsDiff = (id) => !!CHANGE[id] && CHANGE[id].cls !== "added" && (id in diffOne ? diffOne[id] : diffAll);
  function changeChip(id, redraw) {
    const c = CHANGE[id];
    if (!c) return null;
    const words = CHIP_WORDS[c.cls] || c.cls;
    if (c.cls === "added") return h("span", { class: "cls cls-added", title: `Added since ${c.since}` }, words);
    const on = showsDiff(id);
    return h("button", { type: "button", class: `cls cls-${c.cls} toggle` + (on ? " on" : ""), "aria-pressed": on,
      title: `Changed since ${c.since}. ${on ? "Hide" : "Show"} what changed.`,
      onclick: () => { diffOne[id] = !on; redraw(); } }, icon("compare", "sm"), words);
  }
  function itemBody(id) {  // the head, title and text; in diff mode, what changed in each
    const it = ITEMS[id];
    const box = h("div", { class: "body" });
    function draw() {
      const c = CHANGE[id], on = showsDiff(id);
      const has = (k) => on && (k in c.before || k in c.after);
      const textKey = on ? TEXT_KEYS.find(has) : null;
      const rest = on ? [...new Set([...Object.keys(c.before), ...Object.keys(c.after)])].filter((k) => k !== "title" && k !== textKey) : [];
      fill(box, h("div", { class: "item-head" }, idButton(id), levelChip(id), changeChip(id, draw), ...statusChips(id), h("span", { class: "small" }, it.kind)),
        has("title") ? h("div", { class: "item-text" }, h("b", {}, wordDiff(c.before.title, c.after.title)))
          : it.title ? h("div", { class: "item-text" }, h("b", {}, it.title)) : null,
        textKey ? h("div", { class: "item-text" }, wordDiff(c.before[textKey], c.after[textKey]))
          : it.text ? h("div", { class: "item-text" }, linkify(it.text)) : null,
        on ? h("div", { class: "fields" }, h("div", { class: "small muted" }, `Changes since ${c.since}`),
          ...rest.map((k) => fieldDiff(k, c.before[k], c.after[k]))) : null);
    }
    draw();
    bodies.add({ box, draw });
    return box;
  }
  function setDiffAll(on) {
    diffAll = on;
    for (const k of Object.keys(diffOne)) delete diffOne[k];
    try { localStorage.setItem("syseng-diff", on ? "1" : "0"); } catch (e) { /* fine */ }
    for (const b of [...bodies]) { if (b.box.isConnected) b.draw(); else bodies.delete(b); }
    const btn = document.getElementById("diffs");
    if (btn) { btn.classList.toggle("on", on); btn.setAttribute("aria-pressed", on); }
  }
  function itemCard(id, opts) {
    const it = ITEMS[id];
    if (!it) return h("div", { class: "card" }, id, " (no longer in the spec)");
    const card = h("div", { class: "card", "data-item": id }, itemBody(id));
    if (opts && opts.extra) card.append(opts.extra);
    if (opts && opts.details) card.append(details(id));
    const mark = triage(card, () => answered(id));
    card.append(itemActions(id, { ...(opts || {}), onchange: () => { mark(); if (opts && opts.onchange) opts.onchange(); } }));
    return card;
  }
  function details(id) {
    const it = ITEMS[id];
    const kv = h("dl", { class: "kv" });
    const add = (k, v) => { if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return;
      kv.append(h("dt", {}, k), h("dd", {}, Array.isArray(v) ? v.map((x, i) => [i ? ", " : "", ITEMS[x] ? idButton(x) : x]) : linkify(String(v)))); };
    add("under", it.parents);
    add("refined by", CHILDREN[id] || []);
    add("why", it.why);
    add("basis", it.basis);
    for (const k of ["status", "context", "decision", "alternatives", "consequences", "method", "technique"]) add(k, it[k]);
    for (const l of it.locks || []) add("locked", `${l.locked_at || l.approved_at || l.approved_on || ""} by ${l.by || "a person"} via ${l.via}`);
    const box = h("div", {}, kv);
    it.intent.forEach((r, i) => box.append(intentBlock(id, r, i, true)));
    return box;
  }
  const CHILDREN = {};
  for (const [id, it] of Object.entries(ITEMS)) for (const p of it.parents || []) (CHILDREN[p] = CHILDREN[p] || []).push(id);

  // word-level diff of two texts (longest common subsequence of words)
  function wordDiff(a, b) {
    const x = String(a || "").split(/(\s+)/), y = String(b || "").split(/(\s+)/);
    if (x.length * y.length > 250000) return h("span", {}, h("del", {}, a), " ", h("ins", {}, b));
    const m = x.length, n = y.length, L = Array.from({ length: m + 1 }, () => new Int32Array(n + 1));
    for (let i = m - 1; i >= 0; i--) for (let j = n - 1; j >= 0; j--) L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const out = h("span", {});
    let i = 0, j = 0;
    while (i < m && j < n) {
      if (x[i] === y[j]) { out.append(x[i]); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) { out.append(h("del", {}, x[i])); i++; }
      else { out.append(h("ins", {}, y[j])); j++; }
    }
    while (i < m) out.append(h("del", {}, x[i++]));
    while (j < n) out.append(h("ins", {}, y[j++]));
    return out;
  }
  function fieldDiff(key, before, after) {
    const show = (v) => typeof v === "string" ? v : JSON.stringify(v);
    let v;
    if (key === "intent") {
      const old = (before || []).map(JSON.stringify);
      const recs = (after || []).filter((r) => !old.includes(JSON.stringify(r)));
      v = h("div", {}, recs.length ? recs.map((r) => intentBlock(null, r, null)) : h("span", { class: "muted" }, "records removed or reordered"));
    } else if (typeof before === "string" || typeof after === "string") v = wordDiff(before === undefined ? "" : show(before), after === undefined ? "" : show(after));
    else v = h("span", {}, before !== undefined ? h("del", {}, show(before)) : null, " ", after !== undefined ? h("ins", {}, show(after)) : null);
    return h("div", { class: "field" }, h("div", { class: "k" }, key), h("div", { class: "v" }, v));
  }

  // ---------------------------------------------------------------- sections
  const main = document.getElementById("main");
  const blocks = {};
  function block(id, title, iconName, lede) {
    const el = h("section", { class: "block", id }, h("h2", {}, icon(iconName), title), lede ? h("p", { class: "lede" }, lede) : null);
    blocks[id] = el;
    main.append(el);
    return el;
  }

  // 1. For you: the agent's recommendations, the decisions waiting, the responses to your feedback (REVIEW-20, REVIEW-30)
  function renderForYou() {
    const el = block("awaiting", "For you", "sparkles",
      "What the agent recommends you look at, then the decisions waiting for you, then its answers to your feedback. Each one shows as answered once you act on it; what you leave stays.");
    renderOverview(el);
    // the agent's judgment leads (AGENT-51)
    const all = DATA.proposals.filter((p) => p.from !== "computed");
    const latest = META.change;  // proposals from older changes are earlier recommendations (REVIEW-37)
    const judged = all.filter((p) => p.change === latest && ITEMS[p.id]);
    el.append(h("h3", { class: "subhead" }, icon("lock", "sm"), "Recommended by the agent"));
    if (!judged.length) el.append(h("div", { class: "empty" }, "Nothing recommended right now."));
    const groups = [];
    for (const p of judged) {  // one recommendation can name several items: its reason shows once
      const g = groups.find((x) => x.why === p.why);
      if (g) g.ids.push(p.id); else groups.push({ why: p.why, ids: [p.id] });
    }
    for (const g of groups) {
      const card = h("div", { class: "card" });
      const lockAll = h("button", { class: "act" });
      const list = h("div", { class: "subs" });
      const mark = triage(card, () => g.ids.every(answered));
      const refresh = () => {  // the button and the answered mark; the items redraw themselves
        const n = g.ids.filter((id) => (state.items[id] || {}).lock === true).length;
        fill(lockAll, icon(n === g.ids.length ? "check" : "lock", "sm"), n === g.ids.length ? `All ${n} locking` : `Lock all ${g.ids.length}`);
        lockAll.classList.toggle("on", n === g.ids.length);
        mark();
      };
      const rebuild = () => { list.replaceChildren(...g.ids.map((id) => subItem(id, {}, refresh))); refresh(); };
      lockAll.addEventListener("click", () => {
        const every = g.ids.every((id) => (state.items[id] || {}).lock === true);
        for (const id of g.ids) { const st = itemState(id); if (every) delete st.lock; else st.lock = true; prune(id); }
        save(); rebuild();
      });
      rebuild();
      card.append(h("div", { class: "reason why-agent", style: "margin-top:0" }, icon("sparkles", "sm"),
        h("b", {}, " Why the agent recommends " + (g.ids.length > 1 ? "these: " : "it: ")), linkify(g.why)),
      h("div", { class: "actions" }, lockAll), list);
      el.append(card);
    }
    const earlier = all.filter((p) => p.change !== latest && ITEMS[p.id]);
    const computed = DATA.proposals.filter((p) => p.from === "computed" && ITEMS[p.id]);
    if (earlier.length) {
      const box = h("details", { class: "counted" }, h("summary", { class: "small" }, `Earlier recommendations, still unlocked (${earlier.length})`));
      for (const p of earlier) box.append(itemCard(p.id, { extra: h("div", { class: "reason why-agent" }, h("b", {}, `Why (${p.change}): `), linkify(p.why)) }));
      el.append(box);
    }
    if (computed.length) {
      const box = h("details", { class: "counted" }, h("summary", { class: "small" },
        `Also: ${computed.length} items the most of the tree hangs from (counted, not judged by an agent)`));
      for (const p of computed) box.append(itemCard(p.id, { extra: h("div", { class: "reason" }, h("b", {}, "Counted: "), linkify(p.why)) }));
      el.append(box);
    }

    // decisions waiting: conflicts first; each involved item answerable on its own (REVIEW-30)
    const { decisions } = DATA.awaiting;
    const altIds = new Set(DATA.awaiting.alterations.map((a) => a.id));
    el.append(h("h3", { class: "subhead" }, icon("scale", "sm"), "Decisions waiting"));
    if (!decisions.length) el.append(h("div", { class: "empty" }, "No decisions waiting."));
    for (const d of decisions) {
      const key = `${d.change} ${d.id}`;
      const s = () => state.decisions[key] || (state.decisions[key] = { fingerprint: d.fingerprint });
      const involved = (d.involves || []).filter((i) => ITEMS[i]);
      const progress = h("span", { class: "small" });
      const card = h("div", { class: "card" + (d.kind === "conflict" ? " conflict" : "") });
      const mark = triage(card, () => !!(state.decisions[key] || {}).choose || (involved.length > 0 && involved.every(answered)));
      const count = () => { const n = involved.filter(answered).length;
        progress.replaceChildren(involved.length ? `${n} of ${involved.length} answered` : ""); mark(); };
      card.append(h("div", { class: "item-head" }, d.kind === "conflict" ? h("span", { class: "status critical" }, icon("alert", "sm"), "conflict") : h("span", { class: "chip" }, "decision"),
          h("span", { class: "mono small" }, `${d.id} · ${d.change}`), h("span", { class: "grow" }), progress),
        h("div", { class: "item-text" }, h("b", {}, linkify(d.question))),
        d.importance ? h("div", { class: "reason" }, h("b", {}, "Why it ranks here: "), linkify(d.importance)) : null);
      if (involved.length) {
        const list = h("div", { class: "subs" }, involved.map((id) => subItem(id, { alteration: altIds.has(id) }, count)));
        card.append(h("details", { class: "involved", open: true }, h("summary", { class: "small" }, `Each item, on its own (${involved.length})`), list));
      }
      const opts = h("div", { class: "options", role: "radiogroup" });
      const redraw = () => { opts.querySelectorAll(".option").forEach((o, n) => o.classList.toggle("on", (state.decisions[key] || {}).choose === n + 1)); mark(); };
      (d.options || []).forEach((o, n) => {
        opts.append(h("label", { class: "option" },
          h("input", { type: "radio", name: key, checked: (state.decisions[key] || {}).choose === n + 1,
            onclick: (e) => { const st = s(); if (st.choose === n + 1) { delete st.choose; e.target.checked = false; } else st.choose = n + 1; save(); redraw(); } }),
          h("div", {}, h("div", {}, h("b", {}, o.label), o.recommended ? h("span", { class: "rec" }, "recommended") : null),
            o.detail ? h("div", { class: "detail" }, linkify(o.detail)) : null)));
      });
      card.append(h("div", { class: "small", style: "margin-top:12px" }, involved.length ? "Or answer the whole decision at once:" : "Your answer:"),
        opts, h("textarea", { class: "note", placeholder: "Anything to add (optional).",
          oninput: (e) => { s().comment = e.target.value; save(); } }, (state.decisions[key] || {}).comment || ""));
      redraw();
      count();
      el.append(card);
    }

    // the agent's answers to your feedback (SYS-52)
    if (DATA.responses.length) {
      el.append(h("h3", { class: "subhead" }, icon("reply", "sm"), "Answers to your feedback"));
      for (const r of DATA.responses.slice().reverse()) el.append(h("div", { class: "card" },
        h("div", { class: "item-head" }, r.id ? idButton(r.id) : h("span", { class: "chip" }, r.decision || "general"), h("span", { class: "chip" }, r.kind),
          h("span", { class: "small mono" }, `${r.n} · ${r.change}`)),
        h("div", { class: "item-text muted" }, r.comment),
        h("div", { class: "reason" }, h("b", {}, "Answer: "), r.response ? linkify(r.response) : h("span", { class: "status warning" }, icon("alert", "sm"), "not answered yet"))));
    }
  }
  // the overview the page opens on: what changed, the health measures, the intent mix (REVIEW-32, DR-69)
  function renderOverview(el) {
    const o = DATA.overview;
    if (!o) return;
    const fmt = (m, v) => (v === null || v === undefined ? "–" : (m.percent ? v.toFixed(1) + "%" : Number(v).toLocaleString()));
    const signed = (m) => (m.delta > 0 ? "+" : "") + (m.percent ? m.delta.toFixed(1) + " pts" : m.delta.toLocaleString());
    const box = h("div", { class: "overview" });
    // what changed since the last review, by kind
    const words = { added: "added", removed: "removed", meaning: "changed", reworded: "reworded", moved: "moved", intent: "intent only", details: "details only" };
    const kinds = { need: "needs", system: "system requirements", constraint: "constraints", requirement: "requirements", vi: "verification items", decision: "decisions", element: "elements" };
    const counts = Object.entries(o.changes || {});
    box.append(h("div", { class: "since" }, h("span", { class: "small" }, `Since ${o.since || "the last commit"}`),
      counts.length ? counts.map(([c, n]) => h("span", { class: "cls cls-" + c }, `${n} ${words[c] || c}`)) : h("span", { class: "small" }, "nothing changed"),
      Object.keys(o.by_kind || {}).length ? h("span", { class: "small muted kinds" }, Object.entries(o.by_kind).map(([k, cs]) =>
        `${kinds[k] || k}: ${Object.entries(cs).map(([c, n]) => `${n} ${words[c] || c}`).join(", ")}`).join(" · ")) : null));
    // tiles: what got worse first, then the few that matter most (no more than six)
    const tiles = o.measures.filter((m) => m.worse || m.tile).slice(0, 6);
    box.append(h("div", { class: "tiles" }, tiles.map((m) => h("div", { class: "tile" + (m.worse ? " worse" : "") },
      h("div", { class: "tile-label" }, m.label),
      h("div", { class: "tile-value" }, fmt(m, m.now)),
      h("div", { class: "tile-delta" }, m.delta === null ? h("span", { class: "muted" }, "no baseline")
        : m.delta === 0 ? h("span", { class: "muted" }, "no change")
        : m.worse ? h("span", { class: "status critical" }, icon("alert", "sm"), `${signed(m)} · worse`)
        : m.improved ? h("span", { class: "status good" }, icon("check", "sm"), `${signed(m)} · better`)
        : h("span", { class: "muted" }, signed(m)))))));
    // the intent mix: how the needs and requirements split across the levels (one ordinal ramp)
    const mix = o.now.mix, total = Object.values(mix).reduce((a, b) => a + b, 0) || 1;
    const before = (o.was || {}).mix || {};
    box.append(h("div", { class: "mix" }, h("div", { class: "small" }, "Intent mix of needs and requirements"),
      h("div", { class: "mixbar", role: "img", "aria-label": LEVELS.map((l) => `${mix[l]} ${l}`).join(", ") },
        LEVELS.filter((l) => mix[l]).map((l) => h("span", { class: `seg lv-${l}`, style: `flex:${mix[l]}`,
          title: `${mix[l]} ${LEVEL_WORDS[l]} (${Math.round((100 * mix[l]) / total)}%)` }))),
      h("div", { class: "legend" }, LEVELS.map((l) => h("span", { class: "lv" }, h("span", { class: `sw lv-${l} ${l}` }),
        `${LEVEL_WORDS[l]} ${mix[l]}`, before[l] !== undefined && before[l] !== mix[l]
          ? h("span", { class: "muted" }, ` (${mix[l] - before[l] > 0 ? "+" : ""}${mix[l] - before[l]})`) : null)))));
    // every measure, as a table (the accessible view)
    box.append(h("details", { class: "allmeasures" }, h("summary", { class: "small" }, `All measures, compared with ${o.against || "nothing"}`),
      h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Measure"), h("th", {}, "Then"), h("th", {}, "Now"), h("th", {}, "Change"))),
        h("tbody", {}, o.measures.map((m) => h("tr", { class: m.worse ? "worse" : "" }, h("td", {}, m.label), h("td", { class: "num" }, fmt(m, m.was)),
          h("td", { class: "num" }, fmt(m, m.now)), h("td", { class: "num" }, m.delta ? signed(m) + (m.worse ? " worse" : m.improved ? " better" : "") : "–")))))));
    el.append(box);
  }

  // one involved or recommended item, with its own answers
  function subItem(id, opts, onchange) {
    const it = ITEMS[id];
    const sub = h("div", { class: "sub", "data-item": id });
    const mark = triage(sub, () => answered(id));
    fill(sub, itemBody(id),
      itemActions(id, { ...opts, onchange: () => { mark(); if (onchange) onchange(); } }));
    return sub;
  }

  // 2. your items, changed: alterations you haven't seen yet, one per item (CHANGE-14, DR-68)
  function renderYourItems() {
    const el = block("altered", "Your items, changed", "alert",
      "Items you locked, stated or guided that an agent changed since. Keep the new text, roll it back, or leave it: once you've seen it here and sent a review, it stops asking and shows as locked to an earlier version.");
    const alts = DATA.awaiting.alterations;
    if (!alts.length) { el.append(h("div", { class: "empty" }, "None of your items changed since you last looked.")); return; }
    for (const a of alts) {
      const what = h("div", {});
      for (const e of a.entries) {
        what.append(h("div", { class: "reason" }, h("b", {}, "Why: "), linkify(e.reason || "")));
        const f = h("div", { class: "fields" });
        for (const k of new Set([...Object.keys(e.before || {}), ...Object.keys(e.after || {})])) f.append(fieldDiff(k, (e.before || {})[k], (e.after || {})[k]));
        what.append(f);
      }
      const card = itemCard(a.id, { alteration: true, extra: h("details", {}, h("summary", { class: "small" },
        `What changed, in ${a.change} (${a.entries.length} edit${a.entries.length > 1 ? "s" : ""})`), what) });
      el.append(card);
    }
  }

  // 3. what changed (DIFF; REVIEW-24)
  function renderChanges() {
    const el = block("changes", "What changed", "compare", "The spec's differences, with each change's reason. Pick what to compare against.");
    if (!DATA.changes.length) { el.append(h("div", { class: "empty" }, "No comparison was available when this page was made.")); return; }
    const sel = h("select", { class: "cmp", "aria-label": "Compare against" },
      DATA.changes.map((c, i) => h("option", { value: i }, `${c.older.label} → ${c.newer.label}` + (c.older.note ? ` (${c.older.note})` : ""))));
    const filters = h("div", { class: "filters" }, h("span", { class: "small" }, "Against"), sel);
    const classBox = h("div", { class: "filters" });
    const list = h("div", {});
    const ORDER = ["removed", "meaning", "added", "moved", "reworded", "intent", "details"];
    let active = new Set(), limit = 25;
    el.append(filters, classBox, list);
    function draw() {
      const set = DATA.changes[+sel.value];
      classBox.replaceChildren(...Object.entries(set.counts).map(([c, n]) => h("button", {
        class: "act" + (active.has(c) ? " on" : ""), onclick: () => { active.has(c) ? active.delete(c) : active.add(c); limit = 25; draw(); } },
      `${CLASS_WORDS[c] || c} `, h("span", { class: "mono" }, n))));
      list.replaceChildren();
      const rank = (d) => ((d.flags || []).length ? 0 : 10) + Math.min(...d.classes.map((c) => ORDER.indexOf(c)));
      const shown = set.items.filter((d) => !active.size || d.classes.some((c) => active.has(c)))
        .sort((a, b) => rank(a) - rank(b) || (a.element || "").localeCompare(b.element || "") || a.id.localeCompare(b.id, undefined, { numeric: true }));
      if (!shown.length) list.append(h("div", { class: "empty" }, "No differences."));
      let element = null, count = 0;
      for (const d of shown) {
        if (count++ >= limit) {
          list.append(h("button", { class: "act", onclick: () => { limit += 80; draw(); } }, `Show more (${shown.length - limit} left)`));
          break;
        }
        if (d.element !== element) { element = d.element; list.append(h("h3", { class: "small mono", style: "margin:14px 0 6px" }, element)); }
        const lvl = d.level_before && d.level_after && d.level_before !== d.level_after
          ? h("span", { class: "lv" }, levelChip(null, d.level_before), " → ", levelChip(null, d.level_after)) : levelChip(null, d.level_after || d.level_before);
        const card = h("div", { class: "card" },
          h("div", { class: "item-head" }, ITEMS[d.id] ? idButton(d.id) : h("span", { class: "mono" }, d.id), lvl,
            ...d.classes.map((c) => h("span", { class: "cls cls-" + c }, CLASS_WORDS[c] || c))),
          h("div", { class: "item-text" }, linkify(d.title)),
          ...(d.flags || []).map((f) => h("div", { class: "flag" }, h("span", { class: "status warning" }, icon("alert", "sm"), f))),
          ...(d.reasons || []).map((r) => h("div", { class: "reason" }, h("b", {}, "Why: "), linkify(r))));
        const keys = [...new Set([...Object.keys(d.before || {}), ...Object.keys(d.after || {})])];
        if (keys.length) {
          const f = h("div", { class: "fields" });
          const meaningFirst = keys.sort((a, b) => (a === "text" || a === "description" ? -1 : 0) - (b === "text" || b === "description" ? -1 : 0));
          for (const k of meaningFirst) f.append(fieldDiff(k, (d.before || {})[k], (d.after || {})[k]));
          card.append(h("details", {}, h("summary", { class: "small" }, `${keys.length} field${keys.length > 1 ? "s" : ""}: ${keys.join(", ")}`), f));
        }
        if (ITEMS[d.id]) card.append(itemActions(d.id));
        list.append(card);
      }
    }
    sel.addEventListener("change", () => { active = new Set(); limit = 25; draw(); });
    draw();
  }

  // 4. intent captured since your last review (REVIEW-25)
  function renderCaptured() {
    const el = block("captured", "What I captured from our conversations", "sparkles",
      "What people said, recorded as intent on the items it directly expresses. Correct anything that isn't what was meant.");
    if (!DATA.captured.length) { el.append(h("div", { class: "empty" }, "Nothing new since your last review.")); return; }
    const list = h("div", {});
    el.append(list);
    let limit = 12;
    function draw() {
      list.replaceChildren();
      for (const c of DATA.captured.slice(0, limit)) {
        list.append(h("div", { class: "card" }, h("div", { class: "item-head" }, idButton(c.id), levelChip(c.id),
          h("span", { class: "item-text grow" }, brief(ITEMS[c.id] ? ITEMS[c.id].title || ITEMS[c.id].text : "", 16))),
        intentBlock(c.id, c.record, c.index, true)));
      }
      if (DATA.captured.length > limit)
        list.append(h("button", { class: "act", onclick: () => { limit += 40; draw(); } }, `Show more (${DATA.captured.length - limit} left)`));
    }
    draw();
  }

  // 6. the system, beside every section (REVIEW-21, REVIEW-27, REVIEW-29)
  const Graph = (() => {
    const box = document.getElementById("graphbox");
    const content = h("div", { class: "graph" });
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "links");
    let showVI = false, selected = null, hovered = null;
    const dots = {}, rows = {};
    const usedBy = {};
    for (const e of DATA.graph.elements) for (const d of e.depends_on) (usedBy[d] = usedBy[d] || []).push(e.id);
    // REVIEW-4, REVIEW-6: an element whose requirements changed since the first comparison is highlighted brightly
    const changedEls = new Set();
    for (const d of (DATA.changes[0] || { items: [] }).items)
      if (d.classes.some((c) => ["added", "removed", "meaning", "moved"].includes(c)) && d.kind !== "vi" && d.element) changedEls.add(d.element);
    const legend = h("div", { class: "legend" }, LEVELS.map((l) => h("span", { class: "lv" }, h("span", { class: `sw lv-${l} ${l}` }), LEVEL_WORDS[l])),
      h("span", { class: "status warning" }, icon("alert", "sm"), "ring: changed since"),
      h("span", { class: "status warning" }, icon("compare", "sm"), "requirements changed"),
      h("label", { class: "small" }, h("input", { type: "checkbox", onchange: (e) => { showVI = e.target.checked; draw(); } }), " verification items"));
    function draw() {
      content.replaceChildren(svg);
      for (const k in dots) delete dots[k];
      for (const e of DATA.graph.elements) {
        const row = h("div", { class: "erow" + (changedEls.has(e.id) ? " changed" : ""), "data-el": e.id, style: `margin-left:${e.depth * 14}px` });
        rows[e.id] = row;
        if (e.depth) row.append(h("span", { class: "tree-guide", style: "left:-8px" }));
        const name = h("div", { class: "ename", "data-id": e.id, onclick: () => openItem(e.id) }, h("span", { class: "eid" }, e.id),
          changedEls.has(e.id) ? h("span", { class: "status warning", title: "its requirements changed" }, " ", icon("compare", "sm")) : null,
          h("span", { class: "et" }, e.title));
        const dotbox = h("div", { class: "dots" });
        for (const id of e.items) {
          const it = ITEMS[id];
          if (!it || (it.kind === "vi" && !showVI)) continue;
          const b = h("button", { class: `dot lv-${it.level} kind-${it.kind}${it.level === "added" ? " added" : ""}${it.changed ? " changed" : ""}`,
            "aria-label": `${id}, ${it.level}`, "data-id": id, onclick: () => openItem(id),
            onmousemove: (ev) => showTip(id, ev), onmouseleave: hideTip });
          dots[id] = b;
          dotbox.append(b);
        }
        if (!dotbox.childNodes.length) dotbox.append(h("span", { class: "small" }, "no items"));
        row.append(name, dotbox);
        content.append(row);
      }
      paint(false);
    }
    function related(id) {
      const up = new Set(), down = new Set();
      (function walkUp(i) { for (const p of (ITEMS[i] || {}).parents || []) if (!up.has(p)) { up.add(p); walkUp(p); } })(id);
      (function walkDown(i) { for (const c of CHILDREN[i] || []) if (!down.has(c)) { down.add(c); walkDown(c); } })(id);
      return { up, down };
    }
    function reveal(node) {
      const b = box.getBoundingClientRect(), r = node.getBoundingClientRect();
      if (r.top < b.top + 60 || r.bottom > b.bottom - 10)
        box.scrollTo({ top: box.scrollTop + (r.top - b.top) - box.clientHeight / 2, behavior: "smooth" });
    }
    function paint(scroll) {
      svg.replaceChildren();
      Object.values(rows).forEach((r) => r.classList.remove("dep", "sel"));
      Object.values(dots).forEach((d) => d.classList.remove("sel", "lit", "dim"));
      const id = hovered || selected;
      if (!id || !ITEMS[id]) return;
      if (ITEMS[id].kind === "element") {
        const deps = new Set([...(ITEMS[id].depends_on || []), ...(usedBy[id] || [])]);
        for (const [eid, r] of Object.entries(rows)) { if (eid === id) r.classList.add("sel"); else if (deps.has(eid)) r.classList.add("dep"); }
        if (scroll && rows[id]) reveal(rows[id]);
        return;
      }
      if (!dots[id]) {  // a verification item while they're hidden: show where it sits
        const r = rows[ITEMS[id].element];
        if (r) { r.classList.add("sel"); if (scroll) reveal(r); }
        return;
      }
      const { up, down } = related(id);
      Object.entries(dots).forEach(([d, b]) => b.classList.add(d === id ? "sel" : up.has(d) || down.has(d) ? "lit" : "dim"));
      const base = content.getBoundingClientRect();
      const center = (d) => { const r = dots[d].getBoundingClientRect(); return [r.left + r.width / 2 - base.left, r.top + r.height / 2 - base.top]; };
      const line = (a, b, strong) => {
        if (!dots[a] || !dots[b]) return;
        const [x1, y1] = center(a), [x2, y2] = center(b);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const my = (y1 + y2) / 2;
        path.setAttribute("d", `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`);
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", strong ? "var(--accent)" : "var(--text-muted)");
        path.setAttribute("stroke-width", strong ? "2" : "1.25");
        path.setAttribute("stroke-opacity", strong ? "0.9" : "0.55");
        svg.append(path);
      };
      for (const p of ITEMS[id].parents || []) line(id, p, true);
      for (const u of up) for (const p of (ITEMS[u] || {}).parents || []) if (up.has(p)) line(u, p, true);
      for (const c of CHILDREN[id] || []) line(id, c, false);
      if (scroll) reveal(dots[id]);
    }
    box.append(legend, content);
    window.addEventListener("resize", () => paint(false));
    draw();
    return {
      hover(id, scroll) { if (hovered === id) return; hovered = id; paint(scroll); },
      select(id) { selected = id; hovered = null; paint(true); },
    };
  })();

  // the item in focus, beside what the person is reading (REVIEW-28)
  const side = document.getElementById("side");
  const focus = document.getElementById("focus");
  function openItem(id) {
    if (!ITEMS[id]) return;
    fill(focus, h("div", { class: "focus-head" }, h("span", { class: "small" }, "In focus"), h("span", { class: "grow" }),
      h("button", { class: "iconbtn", "aria-label": "Close", onclick: closeItem }, icon("x", "sm"))),
    itemCard(id, { details: true, alteration: DATA.awaiting.alterations.some((a) => a.id === id) }));
    focus.scrollTop = 0;
    Graph.select(id);
    side.classList.add("open");
  }
  function closeItem() { focus.replaceChildren(); Graph.select(null); }
  (function splitter() {
    const bar = document.getElementById("splitter");
    const set = (px) => {
      const max = side.clientHeight - 200;
      const hgt = Math.max(120, Math.min(px, max));
      focus.style.height = hgt + "px";
      try { localStorage.setItem("syseng-split", String(hgt)); } catch (e) { /* fine */ }
    };
    try { const saved = +localStorage.getItem("syseng-split"); if (saved) focus.style.height = saved + "px"; } catch (e) { /* fine */ }
    bar.addEventListener("pointerdown", (e) => {
      bar.setPointerCapture(e.pointerId);
      const top = focus.getBoundingClientRect().top;
      const move = (ev) => set(ev.clientY - top);
      const up = () => { bar.removeEventListener("pointermove", move); bar.removeEventListener("pointerup", up); };
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", up);
    });
    bar.addEventListener("keydown", (e) => {
      if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); set(focus.offsetHeight + (e.key === "ArrowDown" ? 40 : -40)); }
    });
  })();
  document.addEventListener("click", (e) => {
    if (e.target.closest("button, a, input, textarea, select, label, summary, .option, #graphbox, #focus")) return;
    if (window.getSelection && String(window.getSelection())) return;  // selecting text isn't opening
    const t = e.target.closest("[data-item]");
    if (t && ITEMS[t.dataset.item]) openItem(t.dataset.item);
  });
  let lastHover = null;
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest("[data-id],[data-item]");
    const id = t ? (t.dataset.id || t.dataset.item) : null;
    if (id === lastHover) return;
    lastHover = id;
    Graph.hover(id && ITEMS[id] ? id : null, !(t && t.closest("#graphbox")));  // the graph doesn't scroll under the pointer
  });

  // 7. the full spec
  function renderItems() {
    const el = block("items", "The full spec", "list", "Every item, grouped by system element. Verification items are hidden until you ask for them.");
    const q = h("input", { type: "search", placeholder: "Search IDs and text", "aria-label": "Search" });
    const lvOn = new Set(LEVELS);
    let showVI = false, changedOnly = false;
    const chips = LEVELS.map((l) => h("button", { class: "act on", onclick: (e) => { lvOn.has(l) ? lvOn.delete(l) : lvOn.add(l); e.currentTarget.classList.toggle("on"); draw(); } },
      h("span", { class: `sw lv-${l} ${l}` }), l));
    const extras = [h("button", { class: "act", onclick: (e) => { changedOnly = !changedOnly; e.currentTarget.classList.toggle("on"); draw(); } }, icon("alert", "sm"), "changed since"),
      h("button", { class: "act", onclick: (e) => { showVI = !showVI; e.currentTarget.classList.toggle("on"); draw(); } }, "verification items")];
    const list = h("div", {});
    el.append(h("div", { class: "filters" }, icon("search"), q), h("div", { class: "filters" }, chips, extras), list);
    q.addEventListener("input", () => draw());
    function draw() {
      const needle = q.value.trim().toLowerCase();
      list.replaceChildren();
      let n = 0;
      for (const e of DATA.graph.elements) {
        const ids = [e.id, ...e.items].filter((id) => {
          const it = ITEMS[id];
          if (!it || (it.kind === "vi" && !showVI) || !lvOn.has(it.level) || (changedOnly && !it.changed)) return false;
          return !needle || id.toLowerCase().includes(needle) || (it.text + " " + it.title).toLowerCase().includes(needle);
        });
        if (!ids.length) continue;
        list.append(h("h3", { class: "small mono", style: "margin:16px 0 6px;margin-left:" + e.depth * 14 + "px" }, `${e.id} · ${e.title}`));
        for (const id of ids) {
          if (n++ > 600) break;
          const it = ITEMS[id];
          const body = h("div", {});
          const card = h("div", { class: "card", "data-item": id },
            h("div", { class: "item-head" }, idButton(id), levelChip(id), ...statusChips(id), h("span", { class: "small" }, it.kind),
              h("span", { class: "grow" }), h("button", { class: "iconbtn", "aria-label": "Details", onclick: () => { body.childNodes.length ? body.replaceChildren() : body.append(details(id), itemActions(id)); } }, icon("list", "sm"))),
            it.title ? h("div", { class: "item-text" }, h("b", {}, it.title)) : null,
            it.text ? h("div", { class: "item-text" }, linkify(it.text)) : null, body);
          list.append(card);
        }
      }
      if (!list.childNodes.length) list.append(h("div", { class: "empty" }, "Nothing matches."));
    }
    draw();
  }
  // ---------------------------------------------------------------- header, nav, feedback bar
  function renderHeader() {
    const inp = h("input", { value: person(), "aria-label": "Reviewing as", title: "Who this feedback is from: Name <email>",
      onchange: (e) => { state.person = e.target.value.trim() || null; save(); } });
    document.getElementById("person").replaceChildren(icon("user", "sm"), inp);
    document.getElementById("repo").textContent = META.repository;
    document.getElementById("when").textContent = `${META.generated} · ${META.revision.slice(0, 7)}${META.dirty ? " + uncommitted" : ""}`;
    const t = document.getElementById("theme");
    const changed = Object.values(CHANGE).filter((c) => c.cls !== "added").length;
    t.before(h("button", { class: "act diffs" + (diffAll ? " on" : ""), id: "diffs", type: "button", "aria-pressed": diffAll,
      title: `Show what changed on every edited item (${changed}), or hide it. Key: D`, onclick: () => setDiffAll(!diffAll) },
    icon("compare", "sm"), "Diffs"));
    document.addEventListener("keydown", (e) => {
      if (e.key !== "d" && e.key !== "D") return;
      if (e.ctrlKey || e.metaKey || e.altKey || e.target.closest("input, textarea, select, [contenteditable]")) return;
      setDiffAll(!diffAll);
    });
    t.addEventListener("click", () => { const n = currentTheme() === "dark" ? "light" : "dark"; applyTheme(n); try { localStorage.setItem("syseng-theme", n); } catch (e) { /* fine */ } });
    applyTheme();
    const recs = DATA.proposals.filter((p) => p.from !== "computed");
    const judged = recs.filter((p) => p.change === META.change).length;
    const counts = { awaiting: judged + DATA.awaiting.decisions.length,
      altered: DATA.awaiting.alterations.length, captured: DATA.captured.length,
      changes: DATA.changes.length ? DATA.changes[0].items.length : 0, items: Object.keys(ITEMS).length };
    // most signal on the left; the further right, the more mechanical (REVIEW-20)
    const names = { awaiting: "For you", altered: "Your items, changed", captured: "Captured intent", changes: "What changed", items: "Full spec" };
    const nav = document.getElementById("nav");
    for (const k of Object.keys(names)) nav.append(h("button", { type: "button", "data-tab": k, onclick: () => showTab(k) }, names[k],
      h("span", { class: "n" + ((k === "awaiting" || k === "altered") && counts[k] ? " hot" : "") }, counts[k])));
    nav.append(h("button", { type: "button", class: "side-toggle", onclick: () => side.classList.toggle("open") }, icon("graph", "sm"), "The system"));
    showTab.first = "awaiting";
  }
  function showTab(name) {
    for (const [k, el] of Object.entries(blocks)) el.hidden = k !== name;
    document.querySelectorAll("#nav [data-tab]").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    try { sessionStorage.setItem("syseng-tab", name); } catch (e) { /* fine */ }
    window.scrollTo({ top: 0 });
  }
  function headerHeight() {
    document.documentElement.style.setProperty("--head-h", document.querySelector("header.top").offsetHeight + "px");
  }

  function feedbackEntries() {
    const items = Object.entries(state.items).filter(([id, s]) => s.lock !== undefined || s.comment || s.alteration ||
      answeredWording(id, s) || (s.intent && Object.keys(s.intent).length));
    const decisions = Object.entries(state.decisions).filter(([, s]) => s.choose || s.comment);
    return { items, decisions };
  }
  const bar = h("div", { class: "bar", role: "region", "aria-label": "Your feedback" });
  function renderBar() {
    const { items, decisions } = feedbackEntries();
    const n = items.length + decisions.length + (state.general ? 1 : 0);
    const stale = items.filter(([id, s]) => !ITEMS[id] || ITEMS[id].fingerprint !== s.fingerprint).length;
    bar.replaceChildren(h("div", { class: "count", title: "Copy and send even with no feedback: an empty review marks this one done." },
      n ? `${n} piece${n > 1 ? "s" : ""} of feedback` : "No feedback yet",
      stale ? h("span", { class: "status warning" }, " ", icon("alert", "sm"), `${stale} on items that changed since`) : null),
    h("button", { class: "act", onclick: general }, icon("comment", "sm"), h("span", { class: "lbl" }, "General")),
    h("button", { class: "act", onclick: clearAll, title: "Clear all feedback" }, icon("x", "sm"), h("span", { class: "lbl" }, "Clear")),
    h("button", { class: "act primary", onclick: openCopy }, icon("copy", "sm"), "Copy feedback"));
  }
  function general() {
    const d = h("dialog", {}, h("h3", { style: "margin-top:0" }, "General feedback"),
      h("textarea", { class: "note", style: "min-height:140px", oninput: (e) => { state.general = e.target.value; save(); } }, state.general || ""),
      h("div", { class: "actions" }, h("button", { class: "act primary", onclick: () => d.close() }, "Done")));
    document.body.append(d);
    d.addEventListener("close", () => d.remove());
    d.showModal();
  }
  function clearAll() {
    if (!confirm("Clear all the feedback on this page?")) return;
    state = { items: {}, decisions: {}, general: "", person: state.person };
    save();
    location.reload();
  }

  // the block a person pastes to the agent or posts as review notes (SYS-51, SYS-53)
  function feedbackBlock() {
    const { items, decisions } = feedbackEntries();
    const who = person();
    const L = [];
    const group = (title, list) => { if (list.length) { L.push(`${title}:`); list.forEach((x) => L.push(`- ${x}`)); L.push(""); } };
    L.push(`## Spec review by ${who}`, "");
    L.push(`Review ${META.review} of ${META.repository} at ${META.revision.slice(0, 7)}${META.dirty ? " with uncommitted changes" : ""}, made ${META.generated}.`, "");
    group("Locked", items.filter(([, s]) => s.lock === true).map(([id]) => label(id)));
    group("Unlocked", items.filter(([, s]) => s.lock === false).map(([id]) => label(id)));
    group("Kept", items.filter(([, s]) => s.alteration === "keep").map(([id]) => label(id)));
    group("Rolled back", items.filter(([, s]) => s.alteration === "roll back").map(([id]) => label(id)));
    group("Decisions", decisions.filter(([, s]) => s.choose).map(([k, s]) => {
      const [change, id] = k.split(" ");
      const d = DATA.awaiting.decisions.find((x) => x.change === change && x.id === id);
      return `${id} (${change}): ${d ? d.options[s.choose - 1].label : "option " + s.choose}` + (s.comment ? `. ${s.comment}` : "");
    }));
    const fixes = [];
    for (const [id, s] of items) for (const [idx, f] of Object.entries(s.intent || {}))
      fixes.push(`${label(id)}, intent record ${+idx + 1}: ` + (f.action === "remove" ? "not what was meant; remove it" : `meant: ${f.correction || "(see comment)"}`));
    group("Intent to correct", fixes);
    group("Wording suggested", items.filter(([id, s]) => answeredWording(id, s)).map(([id, s]) => `${id}: ${s.wording}`));
    group("Comments", items.filter(([, s]) => s.comment).map(([id, s]) => `${label(id)}: ${s.comment}`));
    if (state.general) { L.push("General:", state.general, ""); }
    if (!items.length && !decisions.length && !state.general) L.push("Reviewed, with nothing to add.", "");
    // the part the CLI applies: JSON strings are valid YAML
    const Y = ["```syseng-feedback", `review: ${JSON.stringify(META.review)}`, `by: ${JSON.stringify(who)}`,
      `repository: ${JSON.stringify(META.repository)}`, `revision: ${JSON.stringify(META.revision)}`, `dirty: ${META.dirty}`,
      `generated: ${JSON.stringify(META.generated)}`];
    Y.push(items.length ? "items:" : "items: []");
    for (const [id, s] of items) {
      Y.push(`  - id: ${JSON.stringify(id)}`, `    fingerprint: ${JSON.stringify(s.fingerprint || "")}`);
      if (s.lock !== undefined) Y.push(`    lock: ${s.lock}`);
      if (s.alteration) Y.push(`    alteration: ${JSON.stringify(s.alteration)}`);
      if (s.comment) Y.push(`    comment: ${JSON.stringify(s.comment)}`);
      if (answeredWording(id, s)) Y.push(`    wording: ${JSON.stringify(s.wording)}`);
      const fx = Object.entries(s.intent || {});
      if (fx.length) {
        Y.push("    intent:");
        for (const [idx, f] of fx) {
          const rec = (ITEMS[id] && ITEMS[id].intent[+idx]) || {};
          Y.push(`      - record: ${+idx}`, `        action: ${JSON.stringify(f.action)}`,
            `        when: ${JSON.stringify(rec.when || "")}`, `        by: ${JSON.stringify(rec.by || "")}`);
          if (f.correction) Y.push(`        correction: ${JSON.stringify(f.correction)}`);
        }
      }
    }
    Y.push(decisions.length ? "decisions:" : "decisions: []");
    for (const [k, s] of decisions) {
      const [change, id] = k.split(" ");
      Y.push(`  - change: ${JSON.stringify(change)}`, `    id: ${JSON.stringify(id)}`, `    fingerprint: ${JSON.stringify(s.fingerprint || "")}`);
      if (s.choose) Y.push(`    choose: ${s.choose}`);
      if (s.comment) Y.push(`    comment: ${JSON.stringify(s.comment)}`);
    }
    if (state.general) Y.push(`general: ${JSON.stringify(state.general)}`);
    Y.push("```");
    return L.join("\n") + "\n" + Y.join("\n") + "\n";
  }
  function openCopy() {  // copies at once; the block is what the person pastes (SYS-51)
    const text = feedbackBlock();
    const { items, decisions } = feedbackEntries();
    const n = items.length + decisions.length + (state.general ? 1 : 0);
    state.copied = [...new Set([...(state.copied || []), META.review])];
    save();
    copy(text, n ? `Copied ${n} piece${n > 1 ? "s" : ""} of feedback. Paste it to your agent, or post it as your review.`
      : "Copied an empty review: paste it to your agent to mark this one done.");
  }
  function showBlock(text) {  // when the browser won't copy, the block is shown to copy by hand
    const pre = h("pre", {}, text);
    const d = h("dialog", {}, h("h3", { style: "margin-top:0" }, "Your feedback"),
      h("p", { class: "small" }, "Paste it to your agent, or post it on the pull request as your review. It names you and what each piece acts on."),
      pre, h("div", { class: "actions" }, h("button", { class: "act", onclick: () => d.close() }, "Close")));
    document.body.append(d);
    d.addEventListener("close", () => d.remove());
    d.showModal();
  }
  function copy(text, message) {
    const done = () => toast(message || "Copied. Paste it to your agent or into the review.");
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, () => fallback(text, done));
    else fallback(text, done);
  }
  function fallback(text, done) {
    const ta = h("textarea", { style: "position:fixed;opacity:0" }, text);
    document.body.append(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    if (ok) done(); else showBlock(text);
  }
  function toast(msg) { const t = h("div", { class: "toast", role: "status" }, msg); document.body.append(t); setTimeout(() => t.remove(), 2600); }

  // ---------------------------------------------------------------- go
  renderHeader();
  renderForYou();
  renderYourItems();
  renderCaptured();
  renderChanges();
  renderItems();
  document.body.append(bar);
  renderBar();
  let tab = null;
  try { tab = sessionStorage.getItem("syseng-tab"); } catch (e) { /* fine */ }
  showTab(blocks[tab] ? tab : showTab.first);
  document.getElementById("side-close").addEventListener("click", () => side.classList.remove("open"));
  headerHeight();
  window.addEventListener("resize", headerHeight);
})();
