// Runs Pyodide and DraftWitness off the page's main thread (ADR 007).
//
// The page sends {id, action, files, args}. Files arrive as {name, data: ArrayBuffer}; they
// are written to Pyodide's in-memory file system, in a folder that is deleted as soon as
// the action finishes. Nothing is stored anywhere else and nothing is sent anywhere.

import { loadPyodide } from "./pyodide/pyodide.mjs";

const ACTIONS = ["choices", "inspect", "audit", "access_request", "pdf"];

const ready = (async () => {
  const pyodide = await loadPyodide({
    indexURL: new URL("./pyodide/", import.meta.url).href,
    stdout: () => {},
    stderr: (line) => console.warn(line),
  });
  // The trimmed lock file lists only the packages DraftWitness needs, each with its
  // SHA-256, so Pyodide checks every wheel it loads.
  await pyodide.loadPackage("draftwitness", { messageCallback: () => {}, checkIntegrity: true });
  const api = pyodide.pyimport("draftwitness.web");
  const functions = Object.fromEntries(
    [...ACTIONS, "workdir", "discard"].map((name) => [name, api[name]]),
  );
  return { pyodide, functions };
})();

ready.then(
  () => postMessage({ type: "ready" }),
  (error) => postMessage({ type: "failed", error: String(error) }),
);

// Keep only the last path component, so a file name cannot point outside the folder.
function basename(name) {
  const base = String(name).split(/[\\/]/).pop().replace(/[\u0000-\u001f]/g, "");
  return base && base !== "." && base !== ".." ? base : "file";
}

async function run(action, files, args) {
  if (!ACTIONS.includes(action)) throw new Error(`unknown action ${action}`);
  const { pyodide, functions } = await ready;
  const dir = functions.workdir();
  try {
    const paths = {};
    for (const [role, file] of Object.entries(files)) {
      if (!file) continue;
      pyodide.FS.mkdirTree(`${dir}/${role}`);
      paths[role] = `${dir}/${role}/${basename(file.name)}`;
      pyodide.FS.writeFile(paths[role], new Uint8Array(file.data));
    }
    if (action === "pdf") {
      const out = `${dir}/out.pdf`;
      functions.pdf.callKwargs({ ...args, out });
      return { ok: true, pdf: pyodide.FS.readFile(out) };
    }
    return JSON.parse(functions[action].callKwargs({ ...args, ...paths }));
  } finally {
    functions.discard(dir);
  }
}

addEventListener("message", async ({ data }) => {
  const { id, action, files = {}, args = {} } = data;
  try {
    const result = await run(action, files, args);
    postMessage({ id, result }, result.pdf ? [result.pdf.buffer] : []);
  } catch (error) {
    postMessage({ id, error: String(error) });
  }
});
