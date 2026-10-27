// The page's main thread: forms, language, and drawing results (ADR 007).
//
// Python runs in worker.js. Everything that comes back from it is drawn with textContent,
// never as HTML, so nothing in a student's file or a report can inject markup.

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

let strings = {};
let lang = "en";
let choices = { profiles: [], countries: [], tools: {} };
const UNLISTED = "other:"; // value prefix of the "not listed" options, followed by a pack id
let current = null; // the result on screen, kept only in memory

function rememberLanguage(value) {
  try {
    localStorage.setItem("draftwitness-language", value);
  } catch {
    // Private windows may refuse storage; the choice then lasts until the tab closes.
  }
}

function savedLanguage() {
  try {
    return localStorage.getItem("draftwitness-language");
  } catch {
    return null;
  }
}

function t(key, values = {}) {
  const text = strings[lang]?.[key] ?? strings.en?.[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in values ? values[name] : match));
}

function applyLanguage() {
  document.documentElement.lang = lang;
  for (const element of $$("[data-i18n]")) element.textContent = t(element.dataset.i18n);
  for (const button of $$("[data-lang]")) {
    button.setAttribute("aria-pressed", String(button.dataset.lang === lang));
  }
  fillChoices();
}

// --- The worker -----------------------------------------------------------------------

const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
const pending = new Map();
let nextId = 1;
let loaded = false;

function call(action, args = {}, files = {}) {
  const id = nextId++;
  const transfer = Object.values(files).flatMap((file) => (file ? [file.data] : []));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, action, args, files }, transfer);
  });
}

worker.addEventListener("message", ({ data }) => {
  if (data.type === "ready") {
    loaded = true;
    void onReady();
    return;
  }
  if (data.type === "failed") {
    setStatus(t("loading_failed", { error: data.error }), "error");
    return;
  }
  const waiting = pending.get(data.id);
  pending.delete(data.id);
  if (data.error) waiting?.reject(new Error(data.error));
  else waiting?.resolve(data.result);
});

worker.addEventListener("error", (event) => {
  setStatus(t("loading_failed", { error: event.message ?? "" }), "error");
});

async function onReady() {
  choices = await call("choices");
  fillChoices();
  setStatus(t("ready"), "ok");
  for (const button of $$("form button[type=submit]")) button.disabled = false;
}

function setStatus(text, kind = "") {
  const status = $("#status");
  status.textContent = text;
  status.dataset.kind = kind;
}

// --- Forms ----------------------------------------------------------------------------

function countryName(country) {
  const key = `country_${country.id}`;
  return strings[lang]?.[key] ?? strings.en?.[key] ?? country.name;
}

// The access form also offers a generic letter per country, for institutions with no profile.
function fillProfiles(select, optional, unlisted = false) {
  const chosen = select.value;
  select.replaceChildren();
  if (optional) select.append(new Option(t("none"), ""));
  for (const profile of choices.profiles) {
    const label = profile.unverified
      ? `${profile.name} (${t("profile_unverified", { count: profile.unverified })})`
      : profile.name;
    select.append(new Option(label, profile.id));
  }
  if (unlisted && choices.countries.length) {
    const group = document.createElement("optgroup");
    group.label = t("other_institutions");
    for (const country of choices.countries) {
      group.append(new Option(t("other_in", { country: countryName(country) }), UNLISTED + country.id));
    }
    select.append(group);
  }
  if (chosen) select.value = chosen;
}

function showUnlisted(form) {
  const box = $("#unlisted", form);
  if (!box) return;
  const unlisted = $("select.profiles", form).value.startsWith(UNLISTED);
  box.hidden = !unlisted;
  box.disabled = !unlisted; // a disabled fieldset's required field is not checked
}

function fillPaths(form) {
  const select = $("select.paths", form);
  const profile = choices.profiles.find((p) => p.id === $("select.profiles", form).value);
  const chosen = select.value;
  select.replaceChildren(new Option(t("whole_institution"), ""));
  for (const item of profile?.paths ?? []) select.append(new Option(item.label, item.path));
  select.value = chosen;
  if (select.value !== chosen) select.value = "";
  select.disabled = !profile;
  showUnlisted(form);
}

function fillTools() {
  const box = $("#tools");
  const checked = new Set($$("input:checked", box).map((input) => input.value));
  box.replaceChildren();
  for (const [id, name] of Object.entries(choices.tools)) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "request.tools";
    input.value = id;
    input.checked = checked.has(id);
    label.append(input, ` ${name}`);
    box.append(label);
  }
}

function fillChoices() {
  fillProfiles($("#form-audit select.profiles"), true);
  fillProfiles($("#form-access select.profiles"), false, true);
  fillPaths($("#form-audit"));
  fillPaths($("#form-access"));
  fillTools();
}

async function readFile(input) {
  const file = input.files?.[0];
  return file ? { name: file.name, data: await file.arrayBuffer() } : null;
}

function today() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function accessDetails(form) {
  const details = { student: {}, request: {} };
  for (const element of form.elements) {
    const [group, field] = element.name?.split(".") ?? [];
    if (!field || !(group in details) || element.type === "checkbox") continue;
    const value = element.value.trim();
    if (!value) continue;
    details[group][field] =
      field === "extra_items"
        ? value.split("\n").map((line) => line.trim()).filter(Boolean)
        : value;
  }
  details.request.tools = $$("input[name='request.tools']:checked", form).map((i) => i.value);
  return details;
}

async function submit(form, work) {
  const button = $("button[type=submit]", form);
  button.disabled = true;
  setStatus(t("working"));
  try {
    const result = await work();
    if (result.ok) {
      show(result);
      setStatus(t("done"), "ok");
    } else {
      setStatus(result.error, "error");
    }
  } catch (error) {
    setStatus(t("unexpected_error", { error: error.message }), "error");
  } finally {
    button.disabled = !loaded;
  }
}

$("#form-inspect").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  void submit(form, async () =>
    call("inspect", { language: lang, on: today() }, { path: await readFile(form.elements.file) }),
  );
});

$("#form-audit").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  void submit(form, async () =>
    call(
      "audit",
      { profile: form.elements.profile.value || null, path: form.elements.path.value || null, language: lang, on: today() },
      {
        report: await readFile(form.elements.report),
        document: await readFile(form.elements.document),
        declarations: await readFile(form.elements.declarations),
      },
    ),
  );
});

$("#form-access").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const chosen = form.elements.profile.value;
  const unlisted = chosen.startsWith(UNLISTED)
    ? {
        jurisdiction: chosen.slice(UNLISTED.length),
        institution: form.elements["unlisted.institution"].value,
        office: form.elements["unlisted.office"].value || null,
        office_email: form.elements["unlisted.office_email"].value || null,
      }
    : {};
  void submit(form, async () =>
    call("access_request", {
      details: JSON.stringify(accessDetails(form)),
      profile: unlisted.jurisdiction ? "" : chosen,
      path: form.elements.path.value || null,
      language: form.elements.language.value || null,
      interface: lang,
      on: today(),
      ...unlisted,
    }),
  );
});

for (const form of $$("#form-audit, #form-access")) {
  $("select.profiles", form).addEventListener("change", () => fillPaths(form));
}

// --- Tabs and language ----------------------------------------------------------------

for (const tab of $$("[role=tab]")) {
  tab.addEventListener("click", () => {
    for (const other of $$("[role=tab]")) {
      const selected = other === tab;
      other.setAttribute("aria-selected", String(selected));
      $(`#${other.getAttribute("aria-controls")}`).hidden = !selected;
    }
  });
}

for (const button of $$("[data-lang]")) {
  button.addEventListener("click", () => {
    lang = button.dataset.lang;
    rememberLanguage(lang);
    applyLanguage();
    setStatus(loaded ? t("ready") : t("loading"), loaded ? "ok" : "");
  });
}

// --- Results --------------------------------------------------------------------------

// Text with **bold** spans, as the PDF renderer draws it.
function inline(element, text) {
  text.split("**").forEach((part, index) => {
    if (!part) return;
    if (index % 2) {
      const strong = document.createElement("strong");
      strong.textContent = part;
      element.append(strong);
    } else {
      element.append(part);
    }
  });
  return element;
}

function make(tag, text) {
  return inline(document.createElement(tag), text ?? "");
}

// Draw the blocks that draftwitness.core.render.pdf.markdown_blocks produces.
function drawBlocks(container, blocks) {
  container.replaceChildren();
  let list = null; // the open <ul>/<ol> and its nested list
  let quote = null;
  const close = () => {
    list = null;
  };
  for (const [kind, text] of blocks) {
    const inQuote = ["quote", "qli", "qli2", "qbreak"].includes(kind);
    if (!inQuote) quote = null;
    if (inQuote && !quote) {
      quote = document.createElement("blockquote");
      container.append(quote);
      close();
    }
    const parent = quote ?? container;
    if (kind === "li" || kind === "qli" || /^ol\d+$/.test(kind)) {
      const tag = kind.startsWith("ol") ? "ol" : "ul";
      if (!list || list.tag !== tag) {
        list = { tag, element: document.createElement(tag), nested: null };
        parent.append(list.element);
      }
      const item = make("li", text);
      if (tag === "ol") item.value = Number(kind.slice(2));
      list.element.append(item);
      list.nested = null;
    } else if (kind === "li2" || kind === "qli2") {
      if (!list) {
        list = { tag: "ul", element: document.createElement("ul"), nested: null };
        parent.append(list.element);
      }
      if (!list.nested) {
        list.nested = document.createElement("ul");
        (list.element.lastElementChild ?? list.element).append(list.nested);
      }
      list.nested.append(make("li", text));
    } else {
      close();
      if (/^h[1-3]$/.test(kind)) parent.append(make(`h${Number(kind[1]) + 2}`, text));
      else if (kind === "hr" || kind === "pagebreak") parent.append(document.createElement("hr"));
      else if (kind === "qbreak") continue;
      else parent.append(make("p", text));
    }
  }
}

function download(name, data, type) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function downloadButton(label, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", action);
  return button;
}

async function downloadPdf(result) {
  setStatus(t("working"));
  try {
    const { pdf } = await call("pdf", {
      markdown: result.markdown,
      title: result.title,
      language: result.language,
      subject: result.subject ?? null,
      on: today(),
    });
    download(`${result.stem}.pdf`, pdf, "application/pdf");
    setStatus(t("done"), "ok");
  } catch (error) {
    setStatus(t("unexpected_error", { error: error.message }), "error");
  }
}

function show(result) {
  current = result;
  $("#result").hidden = false;
  $("#result-title").textContent = result.title;
  $("#result-summary").replaceChildren(...result.summary.map((line) => make("p", line)));
  $("#result-warnings").replaceChildren(
    ...(result.warnings ?? []).map((line) => make("li", line)),
  );
  const buttons = [
    downloadButton(t("download_pdf"), () => downloadPdf(current)),
    downloadButton(t("download_md"), () =>
      download(`${current.stem}.md`, current.markdown, "text/markdown"),
    ),
  ];
  if (result.json) {
    buttons.push(
      downloadButton(t("download_json"), () =>
        download(`${current.stem}.json`, current.json, "application/json"),
      ),
    );
  }
  if (result.report_json) {
    buttons.push(
      downloadButton(t("download_report_json"), () =>
        download(`${current.report_stem}.json`, current.report_json, "application/json"),
      ),
    );
  }
  $("#downloads").replaceChildren(...buttons);
  drawBlocks($("#result-body"), result.blocks);
  $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
}

// --- Start ----------------------------------------------------------------------------

async function start() {
  const [loadedStrings, build] = await Promise.all([
    fetch("strings.json").then((response) => response.json()),
    fetch("build.json").then((response) => response.json()),
  ]);
  strings = loadedStrings;
  const wanted = savedLanguage() ?? navigator.language ?? "en";
  lang = wanted.toLowerCase().startsWith("es") ? "es" : "en";
  applyLanguage();
  $("#build").textContent = t("build_info", {
    version: build.draftwitness,
    commit: build.commit.slice(0, 7),
    pyodide: build.pyodide,
  });
  setStatus(loaded ? t("ready") : t("loading"), loaded ? "ok" : "");
}

void start();
