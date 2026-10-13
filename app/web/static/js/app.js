const state = {
  index: -1,
  revision: -1,
  running: false,
  lastLogKey: "",
};

const $ = (id) => document.getElementById(id);

function setPill(el, text, cls) {
  el.textContent = text;
  el.className = "pill" + (cls ? " " + cls : "");
}

function updateFlags(s) {
  const flag = (id, on, cls) => {
    const el = $(id);
    el.classList.remove("on", "bad", "pause-on");
    if (on) el.classList.add(cls || "on");
  };
  flag("flag-armed", s.armed);
  flag("flag-pointer", s.pointer_enabled);
  flag("flag-presenting", s.presenting);
  flag("flag-paused", s.paused, "pause-on");
  flag("flag-reliable", s.tracking_reliable !== false, s.tracking_reliable === false ? "bad" : "on");
  if (s.tracking_reliable === false) {
    const el = $("flag-reliable");
    el.classList.remove("on");
    el.classList.add("bad");
  }
}

function applySlideView(s) {
  const img = $("slide");
  const viewport = $("viewport");
  const zoom = s.zoom || 1;
  const scroll = s.scroll || 0;
  $("zoom-value").textContent = Math.round(zoom * 100) + "%";
  $("scroll-value").textContent = Math.round(scroll * 100) + "%";

  if (!img.naturalWidth) {
    img.style.transform = `scale(${zoom})`;
    return;
  }
  const renderedHeight = img.clientHeight * zoom;
  const overflow = Math.max(0, renderedHeight - viewport.clientHeight);
  const offset = -scroll * overflow;
  img.style.transform = `translateY(${offset}px) scale(${zoom})`;
}

function refreshSlide(s) {
  const img = $("slide");
  const hasDeck = s.page_count > 0;
  $("stage-empty").style.display = hasDeck ? "none" : "block";
  $("deck-title").textContent = s.title || "No presentation loaded";
  $("slide-index").textContent = hasDeck ? s.index + 1 : 0;
  $("slide-count").textContent = s.page_count || 0;
  if (!hasDeck) {
    img.removeAttribute("src");
    state.index = -1;
    state.revision = -1;
    return;
  }
  if (s.index !== state.index || s.revision !== state.revision || !img.src) {
    state.index = s.index;
    state.revision = s.revision;
    img.onload = () => applySlideView(s);
    img.src = `/api/slide/${s.index}?r=${s.revision}`;
  }
  applySlideView(s);
}

function updateLog(events) {
  if (!events || events.length === 0) {
    $("log").innerHTML = '<li>No actions yet.</li>';
    return;
  }
  const key = events.map((e) => e.timestamp + e.action).join("|");
  if (key === state.lastLogKey) return;
  state.lastLogKey = key;
  $("log").innerHTML = events
    .map((e) => {
      const t = new Date(e.timestamp * 1000).toLocaleTimeString();
      const detail = e.detail ? ` <b>${e.detail}</b>` : "";
      return `<li>${t} &middot; ${e.action}${detail}</li>`;
    })
    .join("");
}

function render(s) {
  $("global-message").textContent = s.message || "";

  const camPill = $("pill-camera");
  if (s.running) setPill(camPill, "Camera: live", "ok");
  else setPill(camPill, "Camera: idle", "");

  const trackPill = $("pill-tracking");
  if (!s.running) setPill(trackPill, "Tracking: idle", "");
  else if (s.tracking_reliable === false) setPill(trackPill, "Tracking: unreliable", "bad");
  else setPill(trackPill, "Tracking: active", "ok");

  setPill($("pill-pause"), s.paused ? "Paused" : "Active", s.paused ? "warn" : "ok");

  $("hud-gesture").textContent = s.gesture || "NONE";
  updateFlags(s);

  $("start-btn").disabled = s.running || s.page_count === 0;
  $("stop-btn").disabled = !s.running;
  document.querySelectorAll("[data-action]").forEach((b) => {
    b.disabled = s.page_count === 0;
  });

  if (s.running && $("video").getAttribute("src") !== "/api/video") {
    $("video").src = "/api/video";
    $("cam-off").classList.add("hidden");
  } else if (!s.running) {
    $("video").removeAttribute("src");
    $("cam-off").classList.remove("hidden");
  }

  refreshSlide(s);
  updateLog(s.events);
}

async function poll() {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (res.ok) render(await res.json());
  } catch (err) {
    /* server restarting */
  }
}

async function post(url, options = {}) {
  const res = await fetch(url, { method: "POST", ...options });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

$("file-input").addEventListener("change", (e) => {
  const name = e.target.files[0] ? e.target.files[0].name : "No file selected";
  $("file-name").textContent = name;
});

$("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("file-input");
  if (!input.files.length) {
    $("upload-message").textContent = "Select a .pptx or .pdf file first.";
    $("upload-message").classList.add("error");
    return;
  }
  const form = new FormData();
  form.append("file", input.files[0]);
  const btn = $("upload-btn");
  btn.disabled = true;
  $("upload-message").classList.remove("error");
  $("upload-message").textContent = "Validating and loading...";
  try {
    const info = await post("/api/upload", { body: form });
    $("upload-message").textContent = info.message;
    state.index = -1;
    state.revision = -1;
    await poll();
  } catch (err) {
    $("upload-message").textContent = err.message;
    $("upload-message").classList.add("error");
  } finally {
    btn.disabled = false;
  }
});

$("start-btn").addEventListener("click", async () => {
  try {
    await post("/api/session/start");
  } catch (err) {
    $("global-message").textContent = err.message;
  }
  poll();
});

$("stop-btn").addEventListener("click", async () => {
  await post("/api/session/stop");
  poll();
});

document.querySelectorAll("[data-action]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    try {
      await post(`/api/action/${btn.dataset.action}`);
    } catch (err) {
      $("global-message").textContent = err.message;
    }
    poll();
  });
});

document.addEventListener("keydown", async (e) => {
  const map = {
    ArrowRight: "next",
    ArrowLeft: "prev",
    ArrowUp: "scroll_up",
    ArrowDown: "scroll_down",
    "+": "zoom_in",
    "=": "zoom_in",
    "-": "zoom_out",
    p: "toggle_pointer",
    P: "toggle_pointer",
    " ": "toggle_pause",
  };
  const action = map[e.key];
  if (!action) return;
  e.preventDefault();
  try {
    await post(`/api/action/${action}`);
  } catch (err) {
    /* ignore */
  }
  poll();
});

window.addEventListener("resize", () => poll());

poll();
setInterval(poll, 700);
