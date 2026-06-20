#!/usr/bin/env node

const target =
  process.argv[2] ||
  process.env.FLUXIO_CONTROL_URL ||
  "http://127.0.0.1:47880/control?preview-control=1&fixture=live_review";

function fail(message) {
  console.error(`control route smoke failed: ${message}`);
  process.exit(1);
}

async function main() {
  let response;
  try {
    response = await fetch(target, { redirect: "follow" });
  } catch (error) {
    fail(`could not fetch ${target}: ${error instanceof Error ? error.message : String(error)}`);
  }

  if (!response.ok) {
    fail(`${target} returned HTTP ${response.status}`);
  }

  const body = await response.text();
  const requiredFragments = ['id="root"', "Syntelos"];
  const missing = requiredFragments.filter(fragment => !body.includes(fragment));
  if (missing.length > 0) {
    fail(`${target} did not look like the built control shell; missing ${missing.join(", ")}`);
  }

  if (body.includes("grand-public-page") || body.includes("fluxos-shell")) {
    fail(`${target} returned the public page or removed reference skin instead of the current control app`);
  }

  const hasBuiltAssets = body.includes("/assets/");
  const hasViteDevEntrypoint = body.includes("/@vite/client") || body.includes("/src/main");
  if (!hasBuiltAssets && !hasViteDevEntrypoint) {
    fail(`${target} did not expose a built asset or Vite dev entrypoint`);
  }

  console.log(`control route smoke passed: ${target}; browser proof must render .fluxio-shell and reject .fluxos-shell/.grand-public-page`);
}

main().catch(error => fail(error instanceof Error ? error.message : String(error)));
