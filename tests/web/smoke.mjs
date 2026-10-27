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

check("access_request drafts a generic letter for an unlisted institution", () => {
  const result = call("access_request", {
    details: JSON.stringify({ student: { name: "Alex Example", email: "alex@student.example" } }),
    profile: "", jurisdiction: "co", institution: "Instituto Sintético", on: "2026-10-27",
  });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.subject, "co/other / co");
  assert.match(result.markdown, /Instituto Sintético/);
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

check("a PDF that is not a report DraftWitness reads is refused, not crashed on", () => {
  const dir = api.workdir();
  api.pdf.callKwargs({ markdown: "# Hello", out: `${dir}/other.pdf`, title: "x", language: "en" });
  const result = call("audit", { report: `${dir}/other.pdf` });
  assert.equal(result.ok, false);
  assert.match(result.error, /Compilatio/);
  api.discard(dir);
});

check("audit reads a synthetic Compilatio report and states its AI result", () => {
  const dir = api.workdir();
  // fpdf2 is in the build: draw the report's first page and one passage in the AI colour.
  pyodide.runPython(`
from fpdf import FPDF
from draftwitness.core.render.pdf import _font_path
pdf = FPDF()
pdf.add_font("L", fname=_font_path("LiberationSerif-Regular.ttf"))
pdf.set_font("L", size=8)
pdf.add_page()
for line in ["INFORME DE ANÁLISIS", "magister", "12%Similitudes",
             "40%Textos potencialmente generados por la IA",
             "Fuentes principales detectadas",
             "1 www.example.org 12% Palabras idénticas:12%(30 palabras)"]:
    pdf.cell(text=line)
    pdf.ln()
pdf.add_page()
pdf.set_text_color(0, 191, 255)
pdf.cell(text="Un pasaje sintético en el color de la IA.")
pdf.output("${dir}/informe.pdf")
`);
  const result = call("audit", { report: `${dir}/informe.pdf`, language: "es", on: "2026-10-27" });
  api.discard(dir);
  assert.equal(result.ok, true, result.error);
  assert.match(result.markdown, /Compilatio\*\* atribuye a IA el \*\*40/);
  assert.match(result.markdown, /Un pasaje sintético en el color de la IA/);
  assert.equal(JSON.parse(result.report_json).tool.name, "compilatio");
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
