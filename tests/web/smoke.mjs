// Smoke test of the in-browser build (ADR 007): runs draftwitness.web inside the real
// Pyodide of a built site, with synthetic fixtures, and with fetch disabled.
//
// Usage: node tests/web/smoke.mjs build/web

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const site = resolve(process.argv[2] ?? "build/web");
const fixtures = join(dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "audit");

// The site must not need the network: any fetch fails the test.
globalThis.fetch = async (url) => {
  throw new Error(`network request attempted: ${url}`);
};

const { loadPyodide } = await import(pathToFileURL(join(site, "pyodide", "pyodide.mjs")).href);
const pyodide = await loadPyodide({ indexURL: join(site, "pyodide") + "/", stdout: () => {} });
await pyodide.loadPackage("draftwitness", { messageCallback: () => {}, checkIntegrity: true });
const api = pyodide.pyimport("draftwitness.web");
const call = (name, args = {}) => JSON.parse(api[name].callKwargs(args));

function put(dir, name, data) {
  pyodide.FS.mkdirTree(dir);
  pyodide.FS.writeFile(`${dir}/${name}`, data);
  return `${dir}/${name}`;
}

const checks = [];
function check(name, run) {
  checks.push([name, run]);
}

check("the CLI layer is not installed", () => {
  assert.equal(pyodide.runPython("import importlib.util; importlib.util.find_spec('typer')"), undefined);
});

check("choices lists the bundled profiles and tools", () => {
  const { profiles, tools } = call("choices");
  assert.deepEqual(profiles.map((p) => p.id).sort(), ["co/luisamigo", "es/uah", "us/utexas"]);
  assert.equal(tools.turnitin, "Turnitin");
});

check("inspect reads a Markdown file", () => {
  const dir = api.workdir();
  const path = put(dir, "essay.md", readFileSync(join(fixtures, "essay.md")));
  const result = call("inspect", { path, language: "es", on: "2026-10-27" });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.language, "es");
  assert.ok(result.blocks.length > 3);
  assert.equal(JSON.parse(result.json).file.filename, "essay.md");
  api.discard(dir);
  assert.equal(pyodide.FS.analyzePath(dir).exists, false);
});

check("audit applies discounts and returns the report JSON", () => {
  const dir = api.workdir();
  const report = put(`${dir}/report`, "report.json", readFileSync(join(fixtures, "report.json")));
  const document = put(`${dir}/document`, "essay.md", readFileSync(join(fixtures, "essay.md")));
  put(`${dir}/declarations`, "brief.txt", readFileSync(join(fixtures, "brief.txt")));
  const declarations = put(
    `${dir}/declarations`,
    "declarations.yaml",
    readFileSync(join(fixtures, "declarations.yaml")),
  );
  const result = call("audit", {
    report, document, declarations, profile: "es/uah", language: "en", on: "2026-10-27",
  });
  assert.equal(result.ok, true, result.error);
  const audit = JSON.parse(result.json);
  assert.ok(audit.adjusted_percent < audit.overall_percent);
  assert.equal(JSON.parse(result.report_json).tool.name, "turnitin");
  api.discard(dir);
});

let letter;
check("access_request drafts a letter", () => {
  const details = {
    student: { name: "Alex Example", email: "alex@student.example" },
    request: { submission_title: "The water cycle", tools: ["turnitin"] },
  };
  letter = call("access_request", {
    details: JSON.stringify(details), profile: "es/uah", interface: "es", on: "2026-10-27",
  });
  assert.equal(letter.ok, true, letter.error);
  assert.equal(letter.language, "es");
  assert.match(letter.markdown, /Alex Example/);
});

check("access_request reports an invalid form", () => {
  const result = call("access_request", { details: '{"student": {"name": ""}}', profile: "es/uah" });
  assert.equal(result.ok, false);
  assert.match(result.error, /student\.name/);
});

check("pdf renders, and the inspector reads the PDF back", () => {
  const dir = api.workdir();
  api.pdf.callKwargs({
    markdown: letter.markdown, out: `${dir}/letter.pdf`, title: letter.title,
    language: letter.language, on: "2026-10-27",
  });
  const pdf = pyodide.FS.readFile(`${dir}/letter.pdf`);
  assert.equal(new TextDecoder().decode(pdf.subarray(0, 5)), "%PDF-");
  const result = call("inspect", { path: `${dir}/letter.pdf`, on: "2026-10-27" });
  assert.equal(result.ok, true, result.error);
  assert.equal(JSON.parse(result.json).file.format, "pdf");
  api.discard(dir);
});

check("a PDF that is not a Turnitin report is refused, not crashed on", () => {
  const dir = api.workdir();
  api.pdf.callKwargs({ markdown: "# Hello", out: `${dir}/other.pdf`, title: "x", language: "en" });
  const result = call("audit", { report: `${dir}/other.pdf` });
  assert.equal(result.ok, false);
  api.discard(dir);
});

let failed = 0;
for (const [name, run] of checks) {
  try {
    run();
    console.log(`ok - ${name}`);
  } catch (error) {
    failed += 1;
    console.log(`not ok - ${name}\n  ${String(error.stack ?? error).replaceAll("\n", "\n  ")}`);
  }
}
console.log(`${checks.length - failed}/${checks.length} passed`);
process.exit(failed ? 1 : 0);
