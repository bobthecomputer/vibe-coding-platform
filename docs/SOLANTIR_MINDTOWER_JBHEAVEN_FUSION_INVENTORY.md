# Solantir / Mind Tower / JBH-EAVEN Fusion Inventory

Date: 2026-06-21 Europe/Paris
Worker: D
Scope: documentation and integration inventory only

## Result

This inventory defines the first safe migration path for fusing Solantir, Mind Tower, and JBH-EAVEN concepts into Fluxio/JBHEAVEN without copying stale mirrors, seeded prototype claims, or unsafe live-action behavior.

Recommended source-of-truth order:

1. Local git clones under `C:\Users\paul\projects\...` for code extraction.
2. NAS mirrors under `Y:\projects\...` for runtime proof, historical artifacts, and recovery only.
3. `Y:\projects\solantir-mindtower-fusion` as a prior prototype and proof ledger, not as the first code source.

## Paths Inspected

| Project | Path | Status | Role |
| --- | --- | --- | --- |
| Solantir local | `C:\Users\paul\projects\Solantir` | clean git repo at `a902a91c6575` | Primary source for contracts, terminal model, market/intel/forecast schemas, and legacy signal scoring |
| Mind Tower local | `C:\Users\paul\projects\mind-tower` | clean git repo at `21d40c7a058e` | Primary source for Synology admin model, managed resources, SQLite records/events runtime, and monitoring worker |
| JBH-EAVEN local | `C:\Users\paul\projects\Jbheaven` | clean git repo at `0b94dedea6ed` | Primary source for local-first Tauri runtime, signed event log, prompt lab, synthetic red-team harness, and release automation |
| Solantir NAS mirror | `Y:\projects\Projects\Solantír` | no `.git`; older `worldmonitor` + `osint-platform` layout | Dead/stale mirror for recovery and old layout comparison |
| Mind Tower NAS mirror | `Y:\projects\mind-tower` | no `.git`; package manifest matches local hash | Runtime mirror, likely useful for deployed data and NAS config |
| JBH-EAVEN NAS mirror | `Y:\projects\Jbheaven` | no `.git`; much larger than local; package manifest differs | Artifact-heavy runtime mirror with many proof logs and generated bundles |
| Prior fusion prototype | `Y:\projects\solantir-mindtower-fusion` | no `.git`; Vite app plus mission/proof artifacts | Useful prototype and proof ledger, but contains seeded placeholders and failed image-generation notes |

## Mirror And Duplicate Findings

| Finding | Evidence | Decision |
| --- | --- | --- |
| Local Solantir is authoritative | Clean git clone with unified `apps/terminal`, `packages/contracts`, `services/*`, `storage/*`, and `legacy/osint-platform` layout | Use local clone for source extraction |
| NAS Solantir is stale/dead as a code source | NAS path has no `.git`, uses old top-level `worldmonitor` and `osint-platform`, and README hash differs from local | Keep as reference only |
| Local Mind Tower and NAS Mind Tower are close but not identical | Package hash matches, but file counts and app files differ; NAS has runtime data under `data/` | Use local for code, NAS for deployed SQLite/config evidence |
| Local JBH-EAVEN and NAS JBH-EAVEN diverged | Package hash differs; NAS tree has 1830 scanned files and 2.7 GB, local has 516 scanned files and 321 MB | Use local for code; use NAS for historical proof and generated artifacts only |
| Prior fusion app is not source-of-truth | Its own docs say seed data and placeholder image assets are present; no `.git` | Mine architecture/proof ideas, do not port as-is |

## Valuable Modules

### Solantir

Primary value: canonical market-intelligence vocabulary and explainable signal modeling.

| Module | Why It Matters | Migration Use |
| --- | --- | --- |
| `packages/contracts/src/solantir.ts` | Defines canonical IDs, provenance records, entities, observations, market snapshots, narratives, flow observations, geo events, forecasts, evaluations, source status, harness context, and terminal workspace state | First contract bridge into Fluxio inventory model |
| `packages/contracts/src/services.ts` | Defines service boundaries for market, intel, research, prediction, and workspace loading/search | Adapter interface template |
| `services/ingestion/DATA_SOURCE_CATALOG.md` | Lists ready source families: FRED, SEC EDGAR, GDELT, Polymarket, CoinGecko, USGS, NASA EONET, research scraper, wallet observations, camera observations | Source capability catalog for Fluxio runtime lanes |
| `legacy/osint-platform/backend/solantir_api/models.py` | Concrete SQLAlchemy model for assets, quotes, signals, news, social pulse, wallets, cameras, watchlists, provider health, external markets, macro, filings, documents, prediction runs, forecasts, evaluations, model routes | Read-only import mapping and schema reconciliation |
| `legacy/osint-platform/backend/solantir_api/signals.py` | Real deterministic weighted signal scoring with drivers and confidence | Safe first demo for explainable scores, with no trading execution |
| `apps/terminal` | Mature terminal shell, map harnesses, tests, sidecar packaging, and API patterns | Later UI reference, not first migration target |

### Mind Tower

Primary value: Synology-first monitoring operations and operator-controlled ingestion.

| Module | Why It Matters | Migration Use |
| --- | --- | --- |
| `packages/shared/src/models.ts` | Managed resource contracts for sources, watch rules, digests, alerts, delivery targets, credentials, operators, connection sessions, summary jobs, system health, normalized events, and dashboard snapshots | First source/status schema for Fluxio operator runtime |
| `packages/shared/src/defaults.ts` | Default source, watch-rule, schedule, delivery, credential, and setup seed shapes | Fixture source for non-secret local tests |
| `apps/admin/src/lib/db.ts` | SQLite records/events/runtime_state tables with WAL mode and resource seeding | Read-only adapter target and persistence bridge |
| `apps/admin/src/components/*` | Admin dashboard, control center, connection center, workbench home | UI pattern reference for operator setup and connection state |
| `services/monitor-worker/src/mindtower_worker/*` | Web/RSS/X/Telegram source collection, digest jobs, runtime, connection bridge, AI catalog, summary worker | Later ingestion worker adapter |
| `infra/synology/docker-compose.yml` and deploy scripts | NAS deployment posture | Deployment reference once Fluxio has a real adapter |
| `skills/mindtower-*` | UI, signal ops, and Hermes/Synology operational instructions | Skill metadata source for future platform skill import |

### JBH-EAVEN

Primary value: local-first desktop/runtime mechanics, signed social/event substrate, controlled red-team proof, and release discipline.

| Module | Why It Matters | Migration Use |
| --- | --- | --- |
| `src-tauri/src/agent_runtime.rs` | Runtime lane, run records, reward examples, memory, policy checkpoints, optimizer jobs, provider availability, browser agent status, and learning summaries | Runtime proof vocabulary, not direct first port |
| `scripts/red-team-harness.mjs` | Synthetic red-team scenario scorer with deterministic seed, guardrail/detector coverage, and summarized findings | Safe defensive testing artifact for Fluxio proof lanes |
| `scripts/safety.mjs` | Explicit safety toggles for moderation on rewrites/evaluation | Small pattern for visible safety settings |
| `tests/red-team-harness.test.mjs` | Node tests prove deterministic harness shape | First imported test pattern if harness is ported |
| `src-tauri` + README architecture | Tauri, sled, libp2p, signed event log, identity export/import, live event stream | Later local-first runtime or event-log design reference |
| `scripts/bootstrap.cjs`, `release-*.mjs`, `publish-update.mjs` | Local-first build/release automation | Release workflow reference |
| `ETHICAL_LOOP_CONTEXT.md` | Scope guardrail for authorized local-model red-team work | Documentation boundary for controlled lab workflows |

### Prior NAS Fusion Prototype

Primary value: already captured architecture direction and UI/proof scaffolding.

| Module | Why It Matters | Migration Use |
| --- | --- | --- |
| `docs/source-inventory.md` | Prior source inventory for Solantir + Mind Tower | Historical reference only; superseded by this Fluxio inventory |
| `docs/architecture.md` | First vertical slice definition and read-only model direction | Good stability principle: read-only first, no live trading |
| `src/types.ts` | Simple MonitorSignal, TradingSignal, ReviewItem, SourceHealth, ProvenanceItem, MissionProofItem model | Possible fixture seed, not production contract |
| `src/data/fusionSeed.ts` | Seeded monitor/trading/review/provenance rows | Useful copy deck for fixtures only; label as seeded if reused |
| `scripts/smoke.mjs`, `audit-proof.mjs`, `verify-proof.mjs` | Proof commands for prior prototype | Reference for Fluxio proof artifact shape |

## Risk Flags

| Risk | Source | Impact | Control |
| --- | --- | --- | --- |
| Stale mirrors | NAS Solantir and no-git NAS mirrors | Wrong module could be copied over newer local git work | Use local git clones for code and record hashes in artifacts |
| Seeded prototype data | Prior fusion `fusionSeed.ts` and docs | Could make Fluxio look live when it is seeded | Require provenance fields: `seeded`, `read-only-adapter`, `live`, `blocked` |
| Trading-action ambiguity | Solantir score model and fusion prototype trading panel | Users could infer live trading or advice | Keep first slices read-only and label no broker/order routing |
| Secrets and credentials | Mind Tower docs and connection models mention bot tokens, passwords, API keys | Risk of copying secret storage or examples into UI | Mask credentials, do not commit env files, inventory only shapes |
| Red-team content scope | JBH-EAVEN Gandalf/prompt/red-team files | Unsafe if copied as general-purpose attack tooling | Port only defensive synthetic harness and ethical scope docs first |
| Massive generated artifacts | NAS JBH-EAVEN and fusion trees contain logs, zips, JSON runs, build outputs | Bloats PR and obscures review | Do not import artifacts into code; reference only needed proof paths |
| Runtime coupling | JBH-EAVEN Tauri/sled/libp2p and Mind Tower Synology stack differ from Fluxio | Large migration could destabilize app | Start with contracts and read-only adapters, then prove each runtime slice |
| Placeholder image/proof | Prior fusion docs record failed image-generation fallback and placeholder asset | False proof risk | Do not treat prototype placeholder as a product feature |

## Ordered PR-Ready Migration Slices

### PR 1 - Fusion Inventory And Capability Map

Status: this documentation slice.

Files to create or update:

- `docs/SOLANTIR_MINDTOWER_JBHEAVEN_FUSION_INVENTORY.md`
- `docs/SOLANTIR_MINDTOWER_JBHEAVEN_FUSION_INVENTORY_DATA.json`
- `artifacts/integration-inventory/solantir-mindtower-jbheaven-fusion-inventory-20260621.json`

Acceptance checks:

- Inventory names source-of-truth paths.
- Inventory names stale/dead mirrors.
- Inventory lists valuable modules and risk controls.
- No app code is touched.

### PR 2 - Canonical Fusion Contract Fixture

Goal: define Fluxio-side types and fixture rows that can represent Solantir assets/observations/forecasts, Mind Tower sources/events/jobs, and JBH-EAVEN runtime proof without live connectors.

Proposed files:

- `web/src/fluxio/fusion/fusionTypes.ts`
- `web/src/fluxio/fusion/fusionFixtures.ts`
- `tests/test_fusion_inventory_contract.py` or a frontend typecheck/build gate, depending on current repo pattern

Source inputs:

- `C:\Users\paul\projects\Solantir\packages\contracts\src\solantir.ts`
- `C:\Users\paul\projects\mind-tower\packages\shared\src\models.ts`
- `Y:\projects\solantir-mindtower-fusion\src\types.ts`

Acceptance checks:

- Every fixture row carries `sourceProject`, `sourcePath`, `collectionMode`, `riskLabel`, and `lastVerifiedAt`.
- Collection mode enum includes at least `seeded`, `read-only-adapter`, `live`, and `blocked`.
- No live trading, credential, or write-back action exists.

### PR 3 - Read-Only Mind Tower Adapter Shape

Goal: add a read-only bridge contract for Mind Tower records/events/runtime_state and show the status in Fluxio without mutating NAS or local Mind Tower data.

Proposed files:

- backend adapter under the existing Fluxio bridge/service pattern after inspection
- fixture or integration artifact based on `apps/admin/src/lib/db.ts`
- UI status row in the existing runtime/workbench surface

Source inputs:

- `C:\Users\paul\projects\mind-tower\apps\admin\src\lib\db.ts`
- `C:\Users\paul\projects\mind-tower\packages\shared\src\models.ts`
- Optional NAS data path: `Y:\projects\mind-tower\data\mindtower.sqlite`

Acceptance checks:

- Adapter is read-only.
- Missing NAS mount produces an explicit unavailable state, not fake data.
- Secret fields are masked or omitted.

### PR 4 - Solantir Explainable Signal Importer

Goal: expose a safe, read-only Solantir signal snapshot in Fluxio using local fixture/import data and driver attribution.

Source inputs:

- `C:\Users\paul\projects\Solantir\legacy\osint-platform\backend\solantir_api\models.py`
- `C:\Users\paul\projects\Solantir\legacy\osint-platform\backend\solantir_api\signals.py`
- `C:\Users\paul\projects\Solantir\packages\contracts\src\solantir.ts`

Acceptance checks:

- Scores render with factors, drivers, confidence, and timestamp.
- UI explicitly says sandbox/read-only/no order routing.
- Tests assert the score payload cannot be promoted to an execution command.

### PR 5 - Defensive JBH-EAVEN Harness Proof Lane

Goal: port the synthetic, deterministic defensive red-team harness into Fluxio proof reporting.

Source inputs:

- `C:\Users\paul\projects\Jbheaven\scripts\red-team-harness.mjs`
- `C:\Users\paul\projects\Jbheaven\tests\red-team-harness.test.mjs`
- `C:\Users\paul\projects\Jbheaven\ETHICAL_LOOP_CONTEXT.md`

Acceptance checks:

- Harness remains synthetic and defensive.
- Runs are deterministic by seed.
- Results summarize coverage gaps and do not produce operational abuse steps.
- Proof artifact records scenarios sampled, guardrails selected, pass rate, and vector gaps.

### PR 6 - Operator Fusion Workbench UI

Goal: add the first Fluxio surface that combines source health, Solantir signal snapshots, Mind Tower review jobs, and JBH-EAVEN proof results.

Source inputs:

- Fluxio current workbench and runtime surfaces.
- Mind Tower admin/workbench component patterns.
- Prior fusion `src/data/fusionSeed.ts` only as copy/fixture reference.

Acceptance checks:

- First viewport shows source status, review queue, signal drivers, and proof state.
- Every live-looking row shows provenance and collection mode.
- User-like browser smoke clicks through source health, signal detail, review queue, and proof panel.

### PR 7 - NAS Mirror Cleanup Decision

Goal: document or automate which NAS mirrors are authoritative, archival, or dead.

Proposed output:

- A mirror policy doc or sync manifest.
- Optional one-way verification script that checks hashes and reports drift without copying files.

Acceptance checks:

- NAS Solantir old layout is marked archival.
- NAS Mind Tower runtime data is separate from local code source.
- NAS JBH-EAVEN artifact-heavy mirror is not treated as a code source.

## First Implementation Guardrails

- Do not copy build outputs, `node_modules`, `target`, generated zips, logs, `.agent_runs`, or mission result JSON into Fluxio code.
- Do not use NAS files as authoritative code unless a later task explicitly verifies their drift and source ownership.
- Do not implement trading execution, broker connectors, or advice flows in the first slices.
- Do not import prompt attack scripts wholesale. Start with deterministic defensive harness summaries only.
- Do not show seeded fixture rows without visible provenance.
- Prefer narrow contract tests and one user-like UI smoke over broad repetitive tests once UI work begins.

## Lightweight Validation Performed

The tracked JSON companion under `docs/` records file counts, key hashes, and mirror comparisons from the inspection pass. A duplicate local proof copy also exists under `artifacts/integration-inventory/`, but `artifacts/` is globally ignored in this repo, so reviewers should use the `docs/` JSON in a PR.
