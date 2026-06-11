import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const referencePath = path.join(root, "web", "src", "fluxio", "FluxioReferenceShell.jsx");
const shellPath = path.join(root, "web", "src", "fluxio", "FluxioShell.jsx");

const referenceSource = fs.readFileSync(referencePath, "utf8");
const shellSource = fs.readFileSync(shellPath, "utf8");

const emittedActions = new Set();
const actionPatterns = [
  /fluxioAction\(onRequestAction,\s*([`'"])([^`'"]+)\1/g,
  /onRequestAction\?\.\(\s*([`'"])([^`'"]+)\1/g,
  /onRequestAction\(\s*([`'"])([^`'"]+)\1/g,
  /\{\s*id:\s*([`'"])([^`'"]+)\1\s*,\s*label:/g,
];

for (const pattern of actionPatterns) {
  let match;
  while ((match = pattern.exec(referenceSource))) {
    const action = String(match[2] || "").trim();
    if (action && !action.includes("${") && (match[0].includes("onRequestAction") || match[0].includes("fluxioAction") || action.includes(":"))) {
      emittedActions.add(action);
    }
  }
}

const nativeLocalActions = new Set([
  "live:refresh-preview",
]);

function shellHandles(action) {
  if (nativeLocalActions.has(action)) {
    return true;
  }
  const escaped = action.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const exactPattern = new RegExp(`normalizedAction\\s*===\\s*["'\`]${escaped}["'\`]`);
  if (exactPattern.test(shellSource)) {
    return true;
  }
  const startsWithPatterns = [
    new RegExp(`normalizedAction\\.startsWith\\(\\s*["'\`]${escaped.replace(/:$/, "")}:`),
    new RegExp(`normalizedAction\\.startsWith\\(\\s*["'\`]${escaped}`),
  ];
  return startsWithPatterns.some(pattern => pattern.test(shellSource));
}

const emitted = [...emittedActions].sort();
const missing = emitted.filter(action => !shellHandles(action));

const forbiddenCopy = [
  "action is not configured",
  "not available in the current shell",
  "coming soon",
  "available in the next UI pass",
  "not configured yet",
  "not available yet",
];
const forbiddenMatches = forbiddenCopy.filter(fragment =>
  [referenceSource, shellSource].some(source => source.toLowerCase().includes(fragment)),
);

const result = {
  emittedCount: emitted.length,
  missingCount: missing.length,
  missing,
  forbiddenCopy: forbiddenMatches,
};

console.log(JSON.stringify(result, null, 2));

if (missing.length || forbiddenMatches.length) {
  process.exit(1);
}
