"use strict";

const state = { files: [], formats: {} };

function byId(id) { return document.getElementById(id); }

function normalizeFormat(name) {
  const extension = name.includes(".") ? name.split(".").pop().toLowerCase() : name.toLowerCase();
  return ({ jpeg: "jpg", yml: "yaml", markdown: "md", htm: "html" })[extension] || extension;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function toast(message) {
  const element = byId("toast");
  element.textContent = message;
  element.classList.add("visible");
  window.setTimeout(() => element.classList.remove("visible"), 2600);
}

function updateThemeToggle() {
  const button = byId("theme-toggle");
  const dark = document.documentElement.dataset.theme === "dark";
  const label = dark ? "切换浅色模式" : "切换深色模式";
  button.setAttribute("aria-label", label);
  button.setAttribute("title", label);
  button.querySelector("span").textContent = dark ? "☀" : "◐";
}

function availableTargets(source) {
  const targets = new Set();
  Object.values(state.formats).forEach((sources) => {
    (sources[source] || []).forEach((target) => targets.add(target));
  });
  return Array.from(targets).sort();
}

function refreshTargets() {
  const select = byId("target-format");
  if (!select) return;
  select.replaceChildren();
  if (!state.files.length) return;
  const shared = state.files
    .map((file) => new Set(availableTargets(normalizeFormat(file.name))))
    .reduce((left, right) => new Set(Array.from(left).filter((item) => right.has(item))));
  Array.from(shared).forEach((target) => {
    const option = document.createElement("option");
    option.value = target;
    option.textContent = target.toUpperCase();
    select.append(option);
  });
  if (!select.options.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "没有共同的输出格式";
    select.append(option);
  }
  updateOptionVisibility();
}

function renderFiles() {
  const workspace = byId("workspace");
  const list = byId("file-list");
  if (!workspace || !list) return;
  workspace.classList.toggle("hidden", state.files.length === 0);
  byId("file-count").textContent = `已选择 ${state.files.length} 个文件`;
  list.replaceChildren();
  state.files.forEach((file, index) => {
    const row = document.createElement("li");
    row.className = "file-row";
    const badge = document.createElement("span");
    badge.className = "file-badge";
    badge.textContent = normalizeFormat(file.name).toUpperCase().slice(0, 4);
    const meta = document.createElement("div");
    meta.className = "file-meta";
    const name = document.createElement("strong");
    name.textContent = file.name;
    const detected = document.createElement("span");
    detected.textContent = `已识别：${normalizeFormat(file.name).toUpperCase()}`;
    meta.append(name, detected);
    const size = document.createElement("span");
    size.className = "file-size";
    size.textContent = formatBytes(file.size);
    const remove = document.createElement("button");
    remove.className = "remove-file";
    remove.type = "button";
    remove.setAttribute("aria-label", `移除 ${file.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      state.files.splice(index, 1);
      renderFiles();
    });
    row.append(badge, meta, size, remove);
    list.append(row);
  });
  refreshTargets();
}

function addFiles(files) {
  const known = new Set(state.files.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
  Array.from(files).forEach((file) => {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (!known.has(key)) state.files.push(file);
  });
  renderFiles();
  if (document.body.dataset.tool === "table" && state.files.length === 1) inspectTable();
}

async function inspectTable() {
  const form = new FormData();
  form.append("file", state.files[0]);
  const selectedSheet = byId("sheet-select").value;
  if (selectedSheet) form.append("sheet", selectedSheet);
  try {
    const response = await fetch("/api/table/preview", { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "无法预览表格。请检查文件内容。");
    const result = byId("result");
    result.textContent = `${payload.filename} · ${payload.rows} 行 × ${payload.columns} 列 · 字段：${payload.column_names.join("、")}`;
    result.classList.remove("hidden", "error");
    const sheetControl = byId("sheet-control");
    const sheetSelect = byId("sheet-select");
    sheetControl.classList.toggle("hidden", payload.sheets.length < 2);
    if (payload.sheets.length && sheetSelect.options.length === 0) {
      payload.sheets.forEach((sheet) => {
        const option = document.createElement("option");
        option.value = sheet;
        option.textContent = sheet;
        sheetSelect.append(option);
      });
    }
  } catch (error) {
    toast(error instanceof Error ? error.message : "无法预览表格。请检查文件内容。");
  }
}

function updateOptionVisibility() {
  const source = state.files[0] ? normalizeFormat(state.files[0].name) : "";
  const target = byId("target-format")?.value || "";
  const image = ["jpg", "png", "webp", "bmp", "tiff"].includes(source);
  byId("quality-control")?.classList.toggle("hidden", !image || !["jpg", "webp"].includes(target));
  byId("width-control")?.classList.toggle("hidden", !image);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.replace(/[\\/:*?"<>|]/g, "_");
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function responseFilename(response, fallback) {
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename\*?=(?:UTF-8''|\")?([^";]+)/i);
  return match ? decodeURIComponent(match[1].replace(/"/g, "")) : fallback;
}

async function convertFiles() {
  const button = byId("convert-button");
  const result = byId("result");
  const target = byId("target-format").value;
  if (!state.files.length || !target) return toast("请先选择格式兼容的文件。");
  button.disabled = true;
  button.classList.add("is-loading");
  byId("convert-button-label").textContent = "正在转换…";
  result.className = "result hidden";
  const form = new FormData();
  const isBatch = state.files.length > 1;
  if (isBatch) state.files.forEach((file) => form.append("files", file));
  else form.append("file", state.files[0]);
  form.append("target", target);
  form.append("quality", byId("quality").value || "85");
  if (byId("max-width").value) form.append("max_width", byId("max-width").value);
  if (byId("sheet-select").value) form.append("sheet", byId("sheet-select").value);
  try {
    const response = await fetch(isBatch ? "/api/batch" : "/api/convert", { method: "POST", body: form });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.detail || "转换失败，请检查文件格式。");
    }
    const blob = await response.blob();
    const fallback = isBatch ? "pyautobox-results.zip" : `${state.files[0].name.split(".")[0]}.${target}`;
    const filename = responseFilename(response, fallback);
    result.replaceChildren();
    const grid = document.createElement("div");
    grid.className = "result-grid";
    const summary = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = "转换完成，可以下载了";
    const detail = document.createElement("div");
    const original = state.files.reduce((sum, file) => sum + file.size, 0);
    const reduction = original ? Math.round((1 - blob.size / original) * 100) : 0;
    detail.textContent = `${formatBytes(original)} → ${formatBytes(blob.size)} · 体积变化 ${reduction}%`;
    summary.append(heading, detail);
    const download = document.createElement("button");
    download.className = "button primary";
    download.type = "button";
    download.textContent = "下载文件";
    download.addEventListener("click", () => downloadBlob(blob, filename));
    grid.append(summary, download);
    result.append(grid);
    result.classList.remove("hidden", "error");
    downloadBlob(blob, filename);
  } catch (error) {
    result.textContent = error instanceof Error ? error.message : "转换失败，请稍后重试。";
    result.classList.remove("hidden");
    result.classList.add("error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
    byId("convert-button-label").textContent = "开始转换";
  }
}

async function inspectAudio() {
  const button = byId("convert-button");
  const result = byId("result");
  if (state.files.length !== 1) return toast("请选择一个音频文件。");
  button.disabled = true;
  button.classList.add("is-loading");
  byId("convert-button-label").textContent = "正在读取…";
  const form = new FormData();
  form.append("file", state.files[0]);
  try {
    const response = await fetch("/api/audio/metadata", { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "无法读取音频信息。");
    const serialized = JSON.stringify(payload.metadata, null, 2);
    result.replaceChildren();
    const grid = document.createElement("div");
    grid.className = "result-grid";
    const pre = document.createElement("pre");
    pre.textContent = serialized;
    const download = document.createElement("button");
    download.className = "button primary";
    download.type = "button";
    download.textContent = "下载 JSON";
    download.addEventListener("click", () => downloadBlob(new Blob([serialized], { type: "application/json" }), "audio-metadata.json"));
    grid.append(pre, download);
    result.append(grid);
    result.classList.remove("hidden", "error");
  } catch (error) {
    result.textContent = error instanceof Error ? error.message : "无法读取音频信息。";
    result.classList.remove("hidden");
    result.classList.add("error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
    byId("convert-button-label").textContent = "读取音频信息";
  }
}

async function setupEditor() {
  const button = byId("editor-convert");
  if (!button) return;
  let resultBlob = null;
  let resultName = "result.yaml";
  button.addEventListener("click", async () => {
    const source = byId("editor-source").value;
    const target = source === "json" ? "yaml" : "json";
    const file = new File([byId("editor-input").value], `input.${source}`, { type: "text/plain" });
    const form = new FormData();
    form.append("file", file);
    form.append("target", target);
    const response = await fetch("/api/convert", { method: "POST", body: form });
    if (!response.ok) {
      const payload = await response.json();
      return toast(payload.detail || "转换失败，请检查输入内容。");
    }
    resultBlob = await response.blob();
    resultName = `result.${target}`;
    byId("editor-output").value = await resultBlob.text();
  });
  byId("editor-copy").addEventListener("click", async () => {
    await navigator.clipboard.writeText(byId("editor-output").value);
    toast("已复制到剪贴板。");
  });
  byId("editor-download").addEventListener("click", () => {
    if (resultBlob) downloadBlob(resultBlob, resultName);
  });
}

function setupToolBrowser() {
  const search = byId("tool-search");
  if (!search) return;
  const cards = Array.from(document.querySelectorAll("[data-tool-card]"));
  const filters = Array.from(document.querySelectorAll("[data-tool-filter]"));
  const count = byId("tool-result-count");
  const empty = byId("tool-empty");
  let activeFilter = "all";

  const applyFilters = () => {
    const query = search.value.trim().toLocaleLowerCase("zh-CN");
    let visible = 0;
    cards.forEach((card) => {
      const categoryMatches = activeFilter === "all" || card.dataset.category === activeFilter;
      const textMatches = !query || card.textContent.toLocaleLowerCase("zh-CN").includes(query);
      card.hidden = !(categoryMatches && textMatches);
      if (!card.hidden) visible += 1;
    });
    document.querySelectorAll("[data-tool-group]").forEach((group) => {
      const hasVisibleCard = Array.from(group.querySelectorAll("[data-tool-card]"))
        .some((card) => !card.hidden);
      group.hidden = !hasVisibleCard;
      const heading = document.querySelector(`[data-tool-group-heading="${group.dataset.toolGroup}"]`);
      if (heading) heading.hidden = !hasVisibleCard;
    });
    count.textContent = query || activeFilter !== "all" ? `找到 ${visible} 项工具` : `共 ${visible} 项工具`;
    empty.hidden = visible !== 0;
  };

  search.addEventListener("input", applyFilters);
  filters.forEach((button) => button.addEventListener("click", () => {
    activeFilter = button.dataset.toolFilter;
    filters.forEach((item) => item.classList.toggle("active", item === button));
    applyFilters();
  }));
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      search.focus();
      search.select();
    }
  });
  document.querySelectorAll("[data-copy-command]").forEach((button) => {
    button.addEventListener("click", async () => {
      await navigator.clipboard.writeText(button.dataset.copyCommand);
      const previous = button.textContent;
      button.textContent = "已复制";
      toast(`已复制：${button.dataset.copyCommand}`);
      window.setTimeout(() => { button.textContent = previous; }, 1600);
    });
  });
  applyFilters();
}

async function initialize() {
  const savedTheme = localStorage.getItem("pyautobox-theme");
  if (["light", "dark"].includes(savedTheme)) document.documentElement.dataset.theme = savedTheme;
  updateThemeToggle();
  byId("theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("pyautobox-theme", next);
    updateThemeToggle();
  });
  setupToolBrowser();
  const response = await fetch("/api/formats");
  state.formats = (await response.json()).formats;
  const input = byId("file-input");
  const dropZone = byId("drop-zone");
  if (!input || !dropZone) return;
  byId("choose-files").addEventListener("click", (event) => { event.stopPropagation(); input.click(); });
  dropZone.addEventListener("click", () => input.click());
  dropZone.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) input.click(); });
  input.addEventListener("change", () => addFiles(input.files));
  ["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  }));
  dropZone.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));
  byId("remove-all").addEventListener("click", () => { state.files = []; renderFiles(); });
  byId("target-format").addEventListener("change", updateOptionVisibility);
  byId("sheet-select").addEventListener("change", inspectTable);
  const isAudio = document.body.dataset.tool === "audio";
  if (isAudio) {
    byId("target-format").closest("label").classList.add("hidden");
    byId("quality-control").classList.add("hidden");
    byId("width-control").classList.add("hidden");
    byId("convert-button-label").textContent = "读取音频信息";
  }
  byId("convert-button").addEventListener("click", isAudio ? inspectAudio : convertFiles);
  setupEditor();
}

document.addEventListener("DOMContentLoaded", () => initialize().catch(() => toast("PyAutoBox 初始化失败，请刷新页面。")));
