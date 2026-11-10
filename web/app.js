// The page's main thread: forms, language, and drawing results (ADR 007).
//
// Python runs in worker.js. Everything that comes back from it is drawn with textContent,
// never as HTML, so nothing in a student's file or a report can inject markup. The
// procedure guides (guides.json, made from docs/ at build time) are drawn the same way.

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

let strings = {};
let lang = "es";
let choices = { profiles: [], countries: [], tools: {} };
const UNLISTED = "other:"; // value prefix of the "not listed" options, followed by a pack id
let current = null; // the result on screen, kept only in memory

function rememberLanguage(value) {
  try {
    localStorage.setItem("descargo-language", value);
  } catch {
    // Private windows may refuse storage; the choice then lasts until the tab closes.
  }
}

function savedLanguage() {
  try {
    // The project was called DraftWitness until 2026-11-05; keep the choice testers made then.
    return localStorage.getItem("descargo-language") ?? localStorage.getItem("draftwitness-language");
  } catch {
    return null;
  }
}

function t(key, values = {}) {
  const text = strings[lang]?.[key] ?? strings.es?.[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in values ? values[name] : match));
}

function applyLanguage() {
  document.documentElement.lang = lang;
  for (const element of $$("[data-i18n]")) element.textContent = t(element.dataset.i18n);
  for (const button of $$("[data-lang]")) {
    button.setAttribute("aria-pressed", String(button.dataset.lang === lang));
  }
  fillChoices();
  fillGuideCountries();
  updateFeedback();
}

// --- The worker -----------------------------------------------------------------------

// The worker starts from a blob: URL that only imports worker.js. A worker loaded from a
// blob: URL inherits this page's Content-Security-Policy, including the <meta> one, so the
// policy also confines Pyodide and every file it reads, even on hosts that cannot send
// the policy as a header (GitHub Pages). A worker loaded from its own URL would take its
// policy from that response's headers only, and without one it could connect anywhere.
const workerURL = new URL("./worker.js", import.meta.url).href;
const workerStart = new Blob([`import ${JSON.stringify(workerURL)};`], { type: "text/javascript" });
const worker = new Worker(URL.createObjectURL(workerStart), { type: "module" });
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
  for (const button of $$("form button[type=submit], #audit-demo")) button.disabled = false;
}

// Set when the page's own texts could not load; the visible error then stays on screen.
let startupError = null;

function setStatus(text, kind = "") {
  if (startupError) return;
  const status = $("#status");
  status.textContent = text;
  status.dataset.kind = kind;
}

// --- Forms ----------------------------------------------------------------------------

function countryName(country) {
  const key = `country_${country.id}`;
  return strings[lang]?.[key] ?? strings.es?.[key] ?? country.name;
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

// A made-up report and essay (web/demo/), so a visitor can see a result without a real file.
async function demoFile(name) {
  const response = await fetch(`demo/${name}-${lang}.${name === "report" ? "json" : name === "essay" ? "md" : "yaml"}`);
  if (!response.ok) throw new Error(`demo ${name}: ${response.status}`);
  return { name: response.url.split("/").pop(), data: await response.arrayBuffer() };
}

$("#audit-demo").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  await submit($("#form-audit"), async () =>
    call(
      "audit",
      { profile: null, path: null, language: lang, on: today() },
      {
        report: await demoFile("report"),
        document: await demoFile("essay"),
        declarations: await demoFile("declarations"),
      },
    ),
  );
  if ($("#status").dataset.kind === "ok") setStatus(t("audit_demo_done"), "ok");
  button.disabled = !loaded;
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

// --- Feedback -------------------------------------------------------------------------

// Where the message can be e-mailed. Empty: the student copies it and sends it to whoever
// shared the page with them.
const FEEDBACK_EMAIL = "";
let buildInfo = "";

function feedbackMessage(form) {
  const answer = (value) => (value.startsWith("feedback_") ? t(value) : value);
  const lines = [t("feedback_subject"), ""];
  const add = (label, value) => {
    if (value) lines.push(`${t(label)}: ${value}`);
  };
  add("feedback_used", $$("input[name=used]:checked", form).map((i) => t(i.value)).join(", "));
  add("feedback_tool", answer(form.elements.tool.value));
  add("feedback_worked", answer(form.elements.worked.value));
  for (const field of ["problem", "wish"]) {
    const text = form.elements[field].value.trim();
    if (text) lines.push("", `${t(`feedback_${field}`)}`, text);
  }
  lines.push("");
  add("feedback_context", form.elements.context.value.trim());
  if (form.elements.status.checked) add("feedback_page_status", $("#status").textContent.trim());
  add("feedback_version", buildInfo);
  add("feedback_page_language", lang);
  return lines.join("\n").trim();
}

function updateFeedback() {
  const form = $("#form-feedback");
  const message = feedbackMessage(form);
  $("#feedback-message").value = message;
  const mail = $("#feedback-mail");
  mail.hidden = !FEEDBACK_EMAIL;
  if (FEEDBACK_EMAIL) {
    const query = `subject=${encodeURIComponent(t("feedback_subject"))}&body=${encodeURIComponent(message)}`;
    mail.href = `mailto:${FEEDBACK_EMAIL}?${query}`;
  }
  $("#feedback-hint").textContent = FEEDBACK_EMAIL
    ? t("feedback_send_email", { email: FEEDBACK_EMAIL })
    : t("feedback_send_shared");
}

$("#form-feedback").addEventListener("input", updateFeedback);
$("#feedback-mail").addEventListener("click", updateFeedback); // runs before the link opens
$("#form-feedback").addEventListener("submit", (event) => event.preventDefault());
$("#feedback-copy").addEventListener("click", async () => {
  updateFeedback();
  const box = $("#feedback-message");
  try {
    await navigator.clipboard.writeText(box.value);
    $("#feedback-hint").textContent = t("feedback_copied");
  } catch {
    box.select();
    $("#feedback-hint").textContent = t("feedback_copy_failed");
  }
});

// --- Tabs and language ----------------------------------------------------------------

for (const tab of $$("[role=tab]")) {
  tab.addEventListener("click", () => {
    for (const other of $$("[role=tab]")) {
      const selected = other === tab;
      other.setAttribute("aria-selected", String(selected));
      $(`#${other.getAttribute("aria-controls")}`).hidden = !selected;
    }
    if (tab.id === "tab-guide") loadGuides().catch(() => {});
  });
}

// The "where do I start" cards open the tab that answers each situation.
for (const card of $$("[data-go]")) {
  card.addEventListener("click", () => {
    const tab = $(`#${card.dataset.go}`);
    tab.click();
    tab.scrollIntoView({ block: "start" });
    tab.focus();
  });
}

// --- Procedure guides -----------------------------------------------------------------

const GUIDE_COUNTRIES = ["es", "co", "mx", "ar", "cl", "pe"];
let guides = null; // guides.json, fetched the first time the tab opens
let guidesLoading = null;

function loadGuides() {
  guidesLoading ??= siteJSON("guides.json").then(
    (loaded) => {
      guides = loaded;
      $("#guide-status").hidden = true;
      drawGuide();
      return loaded;
    },
    (error) => {
      guidesLoading = null; // let the next try fetch again
      const status = $("#guide-status");
      status.textContent = t("guide_failed");
      status.dataset.kind = "error";
      status.hidden = false;
      throw error;
    },
  );
  return guidesLoading;
}

function fillGuideCountries() {
  const select = $("#guide-country");
  const chosen = select.value;
  select.replaceChildren(new Option(t("guide_choose"), ""));
  for (const code of GUIDE_COUNTRIES) select.append(new Option(t(`guide_country_${code}`), code));
  select.value = chosen;
  drawGuide();
}

// Runs of a guide's text, with their style and link.
function guideRuns(element, runs) {
  for (const run of runs) {
    let node = document.createTextNode(run.t);
    if (run.code) node = wrap("code", node);
    if (run.italic) node = wrap("em", node);
    if (run.bold) node = wrap("strong", node);
    if (run.href || run.guide || run.anchor) {
      const link = wrap("a", node);
      if (run.href) {
        link.href = run.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      } else {
        link.href = "#";
        link.addEventListener("click", (event) => {
          event.preventDefault();
          if (run.guide && run.guide !== $("#guide-country").value) {
            $("#guide-country").value = run.guide;
            drawGuide(run.anchor);
          } else {
            scrollToHeading(run.anchor);
          }
        });
      }
      node = link;
    }
    element.append(node);
  }
  return element;
}

function wrap(tag, child) {
  const element = document.createElement(tag);
  element.append(child);
  return element;
}

function scrollToHeading(id) {
  const target = id ? document.getElementById(`guide-${id}`) : $("#guide-body");
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function guideBlocks(container, blocks) {
  for (const block of blocks) {
    if (Array.isArray(block)) {
      guideBlocks(container, block);
    } else if (/^h[1-3]$/.test(block.type)) {
      // The guide's own headings sit under the panel's: h2 → h3, h3 → h4.
      const heading = guideRuns(document.createElement(`h${Number(block.type[1]) + 1}`), block.runs);
      heading.id = `guide-${block.id}`;
      container.append(heading);
    } else if (block.type === "p") {
      container.append(guideRuns(document.createElement("p"), block.runs));
    } else if (block.type === "ul" || block.type === "ol") {
      const list = document.createElement(block.type);
      for (const item of block.items) guideBlocks(list.appendChild(document.createElement("li")), item);
      container.append(list);
    } else if (block.type === "quote") {
      guideBlocks(container.appendChild(document.createElement("blockquote")), block.blocks);
    } else if (block.type === "table") {
      const table = document.createElement("table");
      const head = table.createTHead().insertRow();
      for (const cell of block.head) guideRuns(head.appendChild(document.createElement("th")), cell);
      const body = table.createTBody();
      for (const row of block.rows) {
        const line = body.insertRow();
        for (const cell of row) guideRuns(line.insertCell(), cell);
      }
      // A wide table scrolls inside its box, so the page does not on a phone.
      container.appendChild(document.createElement("div")).append(table);
      container.lastElementChild.className = "table-scroll";
    }
  }
}

function drawGuide(anchor) {
  const code = $("#guide-country").value;
  const body = $("#guide-body");
  const guide = guides?.[lang]?.[code] ?? guides?.es?.[code];
  if (!guide) {
    body.hidden = true;
    body.replaceChildren();
    return;
  }
  body.replaceChildren(make("h2", t("guide_heading", { country: t(`guide_country_${code}`) })));
  guideBlocks(body, guide.blocks);
  const source = document.createElement("p");
  source.className = "guide-source";
  const link = wrap("a", document.createTextNode(t("guide_source")));
  link.href = guide.source;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  source.append(link);
  body.append(source);
  body.hidden = false;
  if (anchor) scrollToHeading(anchor);
}

$("#guide-country").addEventListener("change", () => {
  if (guides) drawGuide();
  else loadGuides().catch(() => {});
});

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

// Draw the blocks that descargo.core.render.pdf.markdown_blocks produces.
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

// Fetch one of the site's own JSON files. A host in the middle of publishing (GitHub Pages)
// can answer with an HTML error page instead, so check the answer and try once more,
// bypassing the cache, before giving up.
async function siteJSON(name) {
  let problem = "";
  for (const cache of ["default", "reload"]) {
    try {
      const response = await fetch(name, { cache });
      const type = response.headers.get("Content-Type") ?? "";
      if (response.ok && type.includes("json")) return await response.json();
      problem = `${response.status} ${type}`;
    } catch (error) {
      problem = String(error);
    }
  }
  throw new Error(`${name}: ${problem}`);
}

// Without its texts the page would show empty headings; say so in both languages instead.
function startFailed(error) {
  console.error(error);
  setStatus(
    "No se pudo cargar la página: recárgala. · The page could not load: please reload it.",
    "error",
  );
  startupError = error;
}

async function start() {
  const [loadedStrings, build] = await Promise.all([
    siteJSON("strings.json"),
    siteJSON("build.json").catch(() => null),
  ]);
  strings = loadedStrings;
  // Spanish first: English only when it was chosen, or the browser asks for it.
  const wanted = savedLanguage() ?? navigator.language ?? "es";
  lang = wanted.toLowerCase().startsWith("en") ? "en" : "es";
  applyLanguage();
  if (build) {
    $("#build").textContent = t("build_info", {
      version: build.descargo,
      commit: build.commit.slice(0, 7),
      pyodide: build.pyodide,
    });
    buildInfo = `${build.descargo} (${build.commit.slice(0, 7)})`;
  }
  updateFeedback();
  setStatus(loaded ? t("ready") : t("loading"), loaded ? "ok" : "");
}

start().catch(startFailed);
