(() => {
  "use strict";
  const root = document.documentElement;
  const el = (id) => document.getElementById(id);
  const form = el("url-form");
  const input = el("video-url");
  const preview = el("preview");
  const findBtn = el("find-btn");
  const downloadBtn = el("download-btn");
  const progressBox = el("job-progress");
  const progressText = el("progress-text");
  const progressPercent = el("progress-percent");
  const progressFill = el("progress-fill");
  const formMessage = el("form-message");
  const jobMessage = el("job-message");
  const readyLink = el("ready-link");
  let resolvedUrl = "";
  let busy = false;
  let jobRunning = false;
  let requestToken = 0;

  // Theme works on the first load and is remembered between visits.
  let theme = "dark";
  try { theme = localStorage.getItem("clipnest-theme") || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"); } catch { /* private browsing */ }
  function applyTheme(next) {
    theme = next;
    root.dataset.theme = next;
    el("theme-label").textContent = next === "dark" ? "Light mode" : "Dark mode";
    el("theme-toggle").setAttribute("aria-label", `Switch to ${next === "dark" ? "light" : "dark"} theme`);
    document.querySelector('meta[name="theme-color"]').setAttribute("content", next === "dark" ? "#0c0d16" : "#f8f9fd");
    try { localStorage.setItem("clipnest-theme", next); } catch { /* private browsing */ }
  }
  applyTheme(theme);
  el("theme-toggle").addEventListener("click", () => applyTheme(theme === "dark" ? "light" : "dark"));
  el("year").textContent = String(new Date().getFullYear());

  function message(node, text) {
    node.textContent = text || "";
    node.hidden = !text;
  }
  function toggleFind(loading) {
    busy = loading;
    findBtn.disabled = loading || jobRunning;
    el("find-text").textContent = loading ? "Finding your video..." : "Find my video";
    el("find-loader").hidden = !loading;
    el("find-arrow").hidden = loading;
  }
  function resetProgress() {
    progressBox.hidden = true;
    progressText.textContent = "Preparing video...";
    progressFill.style.width = "3%";
    progressPercent.textContent = "";
    message(jobMessage, "");
    readyLink.hidden = true;
    readyLink.removeAttribute("href");
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/></svg> Download video';
  }
  function prettyDuration(seconds) {
    if (seconds == null) return "Public video";
    const m = Math.floor(seconds / 60), s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")} duration`;
  }
  async function api(path, body) {
    let response;
    try {
      response = await fetch(path, {method: body ? "POST" : "GET", headers: body ? {"Content-Type": "application/json"} : {}, body: body ? JSON.stringify(body) : undefined});
    } catch { throw Error("Cannot connect to the server. Check your connection and try again."); }
    let data;
    try { data = await response.json(); } catch { throw Error("The server sent an unexpected response. Please try again."); }
    if (!response.ok) {
      let detail = data.detail || "Something went wrong. Please try again.";
      if (Array.isArray(detail)) detail = "Please enter a valid video URL.";
      throw Error(detail);
    }
    return data;
  }
  el("paste-btn").addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (!text) return;
      input.value = text.trim();
      input.dispatchEvent(new Event("input"));
      input.focus();
    } catch { message(formMessage, "Clipboard access is unavailable. Paste using Ctrl+V (or tap and hold on mobile)."); input.focus(); }
  });
  input.addEventListener("input", () => {
    if (input.value.trim() !== resolvedUrl && !jobRunning) {
      requestToken++;
      resolvedUrl = "";
      preview.hidden = true;
      resetProgress();
    }
    message(formMessage, "");
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || jobRunning) return;
    const url = input.value.trim();
    if (!/^https:\/\/.+\..+/.test(url)) return message(formMessage, "Please paste a complete HTTPS video link.");
    message(formMessage, "");
    preview.hidden = true;
    resetProgress();
    toggleFind(true);
    const token = ++requestToken;
    try {
      const data = await api("/api/info", {url});
      if (token !== requestToken) return;
      resolvedUrl = url;
      el("video-platform").textContent = data.platform || "Video";
      el("video-title").textContent = data.title || "Untitled video";
      el("video-meta").textContent = [data.uploader, prettyDuration(data.duration)].filter(Boolean).join(" · ");
      const image = el("video-thumbnail"), fallback = el("thumbnail-fallback");
      image.hidden = true;
      fallback.hidden = false;
      if (data.thumbnail && /^https:\/\//.test(data.thumbnail)) {
        image.onload = () => { if (token === requestToken) { image.hidden = false; fallback.hidden = true; } };
        image.onerror = () => { image.hidden = true; fallback.hidden = false; };
        image.src = data.thumbnail;
      } else image.removeAttribute("src");
      preview.hidden = false;
      preview.scrollIntoView({behavior: "smooth", block: "nearest"});
    } catch (error) {
      if (token === requestToken) message(formMessage, error.message);
    } finally { if (token === requestToken) toggleFind(false); }
  });

  async function pollJob(id) {
    // Poll for up to 8 minutes; platform download limits might reject earlier.
    for (let attempt = 0; attempt < 240; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const data = await api(`/api/jobs/${encodeURIComponent(id)}`);
      if (data.status === "error") throw Error(data.error || "The download failed.");
      if (data.status === "ready") {
        progressFill.style.width = "100%";
        progressText.textContent = "Your video is ready!";
        progressPercent.textContent = "100%";
        el("progress-note").textContent = "Your file is available temporarily; save it to your device.";
        const url = data.download_url;
        readyLink.href = url;
        readyLink.hidden = false;
        readyLink.textContent = "↓ Save video to device";
        // User clicks the visible save link once the file is ready.
        // This is more reliable than a delayed, automatically triggered download.
        return;
      }
      const percent = data.progress;
      const isProcessing = data.status === "processing";
      progressText.textContent = isProcessing ? "Finishing your video..." : data.status === "queued" ? "Waiting for a server slot..." : "Downloading your video...";
      progressPercent.textContent = Number.isFinite(percent) && !isProcessing ? `${percent}%` : "";
      progressFill.style.width = isProcessing ? "95%" : Number.isFinite(percent) ? `${Math.max(3,Math.min(95,percent))}%` : "27%";
    }
    throw Error("This download took too long. Please try a shorter video.");
  }
  downloadBtn.addEventListener("click", async () => {
    if (!resolvedUrl || jobRunning) return;
    jobRunning = true;
    findBtn.disabled = true;
    downloadBtn.disabled = true;
    downloadBtn.textContent = "Preparing download...";
    resetProgress();
    downloadBtn.disabled = true;
    downloadBtn.textContent = "Preparing download...";
    progressBox.hidden = false;
    el("progress-note").textContent = "Please keep this page open while we prepare your file.";
    try {
      const result = await api("/api/download", {url: resolvedUrl, quality: el("quality").value});
      await pollJob(result.job_id);
      downloadBtn.textContent = "Download complete ✓";
    } catch (error) {
      progressBox.hidden = true;
      message(jobMessage, error.message);
      downloadBtn.disabled = false;
      downloadBtn.textContent = "Try downloading again";
    } finally {
      jobRunning = false;
      findBtn.disabled = false;
    }
  });
})();
