"use strict";

const legacyFormatBytes = (bytes) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
};

const legacyResponseFilename = (response) => {
  const disposition = response.headers.get("content-disposition") || "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) return decodeURIComponent(encoded[1]);
  const plain = disposition.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : "pyautobox-download";
};

const legacyMarkdownPreview = (source) => {
  const escaped = source
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const lines = escaped.split("\n");
  let inCode = false;
  let html = "";
  for (const rawLine of lines) {
    let line = rawLine;
    if (line.trim().startsWith("```")) {
      html += inCode ? "</code></pre>" : "<pre><code>";
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      html += `${line}\n`;
      continue;
    }
    line = line
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>");
    if (/^###\s+/.test(line)) html += `<h3>${line.replace(/^###\s+/, "")}</h3>`;
    else if (/^##\s+/.test(line)) html += `<h2>${line.replace(/^##\s+/, "")}</h2>`;
    else if (/^#\s+/.test(line)) html += `<h1>${line.replace(/^#\s+/, "")}</h1>`;
    else if (/^>\s?/.test(line)) html += `<blockquote>${line.replace(/^>\s?/, "")}</blockquote>`;
    else if (/^[-*+]\s+/.test(line)) html += `<p>• ${line.replace(/^[-*+]\s+/, "")}</p>`;
    else if (line.trim()) html += `<p>${line}</p>`;
  }
  return html || '<p class="preview-placeholder">预览会显示在这里。</p>';
};

document.querySelectorAll("[data-api-form]").forEach((form) => {
  const input = form.querySelector("[data-file-input]");
  const zone = form.querySelector("[data-upload-zone]");
  const list = form.querySelector("[data-file-list]");
  const status = form.querySelector("[data-status]");
  const downloadArea = form.querySelector("[data-download]");
  const submitButton = form.querySelector('button[type="submit"]');
  const singleFile = form.dataset.singleFile === "true";
  const orderable = form.dataset.orderable === "true";
  let files = [];
  let objectUrl = null;

  const renderFiles = () => {
    list.replaceChildren();
    files.forEach((file, index) => {
      const row = document.createElement("div");
      row.className = "file-row";

      const name = document.createElement("span");
      name.className = "file-name";
      name.textContent = file.name;
      const size = document.createElement("span");
      size.className = "file-size";
      size.textContent = legacyFormatBytes(file.size);
      const actions = document.createElement("span");
      actions.className = "file-actions";

      if (orderable) {
        [["↑", -1], ["↓", 1]].forEach(([label, delta]) => {
          const move = document.createElement("button");
          move.type = "button";
          move.className = "icon-button";
          move.textContent = label;
          move.title = delta < 0 ? "上移" : "下移";
          move.disabled = index + delta < 0 || index + delta >= files.length;
          move.addEventListener("click", () => {
            [files[index], files[index + delta]] = [files[index + delta], files[index]];
            renderFiles();
          });
          actions.append(move);
        });
      }

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-button";
      remove.textContent = "×";
      remove.title = "删除";
      remove.addEventListener("click", () => {
        files.splice(index, 1);
        renderFiles();
      });
      actions.append(remove);
      row.append(name, size, actions);
      list.append(row);
    });
  };

  const setFiles = (incoming) => {
    const selected = Array.from(incoming);
    files = singleFile ? selected.slice(0, 1) : selected;
    renderFiles();
  };

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => setFiles(input.files));
  ["dragenter", "dragover"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.remove("dragover");
    });
  });
  zone.addEventListener("drop", (event) => setFiles(event.dataTransfer.files));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    status.className = "status visible loading";
    status.textContent = "正在处理，请稍候…";
    downloadArea.replaceChildren();
    submitButton.disabled = true;
    if (objectUrl) URL.revokeObjectURL(objectUrl);

    const payload = new FormData(form);
    payload.delete(form.dataset.fileField);
    files.forEach((file) => payload.append(form.dataset.fileField, file, file.name));
    if (form.querySelector('[name="include_source"]')) {
      const checkbox = form.querySelector('[name="include_source"]');
      payload.set("include_source", checkbox.checked ? "true" : "false");
    }
    const maxWidth = form.querySelector('[name="max_width"]');
    if (maxWidth && !maxWidth.value) payload.delete("max_width");

    try {
      const response = await fetch(form.dataset.endpoint, { method: "POST", body: payload });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.error || `请求失败（${response.status}）`);
      }
      const blob = await response.blob();
      objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.className = "download-button";
      link.href = objectUrl;
      link.download = legacyResponseFilename(response);
      link.textContent = "下载结果";
      downloadArea.append(link);
      status.className = "status visible success";
      status.textContent = "处理成功，文件已准备好。";

      const stats = form.querySelector("[data-compression-stats]");
      if (stats) {
        const original = Number(response.headers.get("x-original-size"));
        const compressed = Number(response.headers.get("x-compressed-size"));
        const saved = response.headers.get("x-saved-percent");
        stats.hidden = false;
        stats.textContent = `原大小 ${legacyFormatBytes(original)} · 压缩后 ${legacyFormatBytes(compressed)} · 节省 ${saved}%`;
      }
    } catch (error) {
      status.className = "status visible error";
      status.textContent = error.message || "处理失败，请检查文件后重试。";
    } finally {
      submitButton.disabled = false;
    }
  });
});

const qualitySlider = document.querySelector("[data-quality-slider]");
if (qualitySlider) {
  const qualityOutput = document.querySelector("[data-quality-output]");
  qualitySlider.addEventListener("input", () => {
    qualityOutput.value = qualitySlider.value;
  });
}

const markdownInput = document.querySelector("[data-markdown-input]");
if (markdownInput) {
  const markdownPreview = document.querySelector("[data-markdown-preview]");
  const updatePreview = () => {
    markdownPreview.textContent = markdownInput.value || "预览会显示在这里。";
  };
  markdownInput.addEventListener("input", updatePreview);
  updatePreview();
}

