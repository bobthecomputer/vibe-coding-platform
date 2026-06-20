# Model Hardness And Routing Notes

Date: 2026-06-20

## Purpose

Fluxio should route model work by task hardness, verification risk, and cost sensitivity instead of by brand preference or a single leaderboard. Public coding and agent benchmarks are useful calibration signals, but they measure different things: single-shot coding, patch editing, long-horizon repo work, terminal autonomy, GUI control, tool-policy compliance, and human-time task duration.

This note is a docs-only routing reference for Fluxio/JBHEAVEN. It does not change runtime defaults.

## Source Grounding

Primary and near-primary sources reviewed:

| Source | What It Measures | Useful Routing Signal |
| --- | --- | --- |
| [METR Task-Completion Time Horizons](https://metr.org/time-horizons/) | 50% and 80% success time horizons, measured by human expert task duration; current page last updated May 8, 2026. | Use human-time duration as a hardness proxy. A 10-minute task and a 6-hour task should not share the same default route. |
| [METR RE-Bench](https://metr.org/blog/2024-11-22-evaluating-r-d-capabilities-of-llms/) | Seven open-ended ML research-engineering environments with human expert attempts and fixed time budgets. | Hard research/debug loops need stronger models, repeated attempts, and proof artifacts. |
| [SWE-bench](https://www.swebench.com/) | Real GitHub issue resolution, with Full, Verified, Lite, Multilingual, and Multimodal variants; leaderboards include resolved rate, cost, cost limits, and step limits. | Repo patch work is agent-scaffold sensitive; use resolved-per-dollar and step-limit behavior, not score alone. |
| [SWE-Bench Pro public leaderboard](https://labs.scale.com/leaderboard/swe_bench_pro_public) | Long-horizon professional software tasks across public/private/held-out subsets. The public page says Pro is much harder than Verified and includes 1,865 total tasks across 41 repositories. | Treat industrial multi-file changes as a separate hard tier from benchmark-style issue fixing. |
| [Terminal-Bench](https://www.tbench.ai/) | Terminal agents on software engineering, ML, security, data science, file operations, and related tasks. Terminal-Bench 2.0 lists 89 high-quality tasks; 2.1 and 3.0 are active/in progress. | Terminal autonomy, environment setup, and shell reliability should raise hardness even when the prompt sounds simple. |
| [Aider LLM leaderboards](https://aider.chat/docs/leaderboards/) | Code editing with percent correct, cost, edit format correctness, prompt/completion tokens, seconds per case, and run date. | Use as a practical signal for code-editing efficiency and malformed edit risk. |
| [LiveCodeBench](https://livecodebench.github.io/) | Contamination-resistant coding tasks collected over time, including code generation, self-repair, code execution, and test-output prediction. | Good signal for fresh algorithmic coding and self-repair, less direct for large repo surgery. |
| [BigCodeBench](https://github.com/bigcode-project/bigcodebench) | 1,140 practical programming tasks involving diverse function calls from 139 libraries across 7 domains. | Raises hardness when the task requires library composition rather than plain syntax. |
| [GAIA via HAL](https://hal.cs.princeton.edu/gaia) | General assistant tasks requiring reasoning, multimodality, browsing, and tool use across three difficulty levels; HAL also reports total cost. | Useful for non-code research agents and tool-use routing. |
| [OSWorld](https://os-world.github.io/) | 369 real computer tasks across web/desktop apps, file I/O, and cross-application workflows with execution-based evaluation. | GUI grounding and multi-app workflows are their own hard route, even if the text task is short. |
| [tau-bench](https://github.com/sierra-research/tau-bench) | Tool-agent-user interaction with simulated users, APIs, and domain policies; the repo now points users to newer tau benchmark versions. | Use for policy-following, customer-service-like tool flows, and error attribution patterns. |

## Practical Hardness Taxonomy

Use these signals before choosing a model:

| Signal | Low Hardness | High Hardness |
| --- | --- | --- |
| Human task duration | Human can finish in under 10 minutes. | Human expert needs hours or days. |
| Repo scope | One file, clear local edit, existing tests obvious. | Multi-file architecture, migration, hidden contracts, generated artifacts, or ambiguous acceptance criteria. |
| Tool horizon | One or two tool calls. | Long terminal/browser/GUI loop with state recovery. |
| Verification | Deterministic lint/test or simple visual check. | Flaky environment, private data, manual review, browser proof, or security-sensitive result. |
| Cost of failure | Easy rollback, no user-visible damage. | Could corrupt data, leak secrets, ship broken runtime behavior, or mislead a human reviewer. |
| Benchmark analog | Aider/BigCodeBench/LiveCodeBench style. | SWE-Bench Pro, Terminal-Bench hard, RE-Bench, OSWorld, GAIA level 3 style. |

## What `F8` Could Mean Operationally

`F8` should not mean "use the most expensive model always." It should mean Fluxio has classified the task as a frontier-hard, high-assurance route:

- The task likely requires long-horizon planning, repo-wide context, tool use, and recovery from failed attempts.
- A cheap probe is allowed only for classification, context packing, and risk scanning.
- The executor should be a strong coding/agent model with enough context and reasoning budget for the whole loop.
- The verifier should be independent from the executor when practical, preferably a different model or a deterministic test/browser harness.
- The run must save route metadata: hardness tier, provider, model, effort setting, route reason, estimated cost band, verification command, artifacts, and downgrade/upgrade decisions.
- The human should see why `F8` was selected before destructive or expensive steps.

Suggested interpretation:

| Fluxio Tier | Meaning | Route Pattern |
| --- | --- | --- |
| F0-F2 | Short, reversible, low-risk text or code assistance. | Low-cost model, deterministic checks when available. |
| F3-F4 | Normal implementation or research with clear acceptance criteria. | Balanced model; escalate only after failed tests or uncertainty. |
| F5-F6 | Complex repo work, multi-step terminal/browser tasks, or safety-sensitive analysis. | Stronger model for planning/execution, cheap model for summaries and probes, explicit proof. |
| F7 | Long-horizon agent task with ambiguous state, multiple subsystems, or high cost of failure. | Strong model plus independent verifier, checkpointing, and human approval gates. |
| F8 | Frontier-hard mission: SWE-Bench Pro/RE-Bench/Terminal-Bench hard style, or anything where bad automation would mislead operators. | Strongest available route for execution; cheap models only for bounded probes; independent verification required. |

## Cheap Probe Lane

Low-cost models are useful when the output is bounded, reversible, and checked before execution:

- classify task type, hardness, risk, and needed tools;
- extract files, symbols, test commands, and likely ownership areas from repo text;
- summarize benchmark pages or local logs with citations;
- draft a checklist, acceptance criteria, or verification matrix;
- generate candidate search queries;
- produce a non-authoritative first-pass route recommendation;
- inspect known-safe artifacts and flag missing metadata.

Cheap probes should not:

- make final architecture decisions for F7/F8 work;
- edit production code without review;
- run destructive commands;
- decide that a task is safe just because it found no obvious risk;
- fabricate benchmark results, provider availability, run receipts, or proof artifacts.

## Strong Model Lane

Route directly to a stronger model when any of these are true:

- The task maps to SWE-Bench Pro, RE-Bench, Terminal-Bench hard, OSWorld, GAIA level 3, or a similar long-horizon benchmark family.
- The repo state is dirty or multiple workers are active and merge mistakes are likely.
- The requested change touches runtime routing, secrets, auth, file deletion, migrations, or external APIs.
- The user expects a complete patch, not just a plan.
- The cheap probe reports low confidence, conflicting evidence, missing tests, or unclear acceptance criteria.
- The task has already failed once with a low-cost route.

For F8 work, do not optimize for cheapest first completion. Optimize for lowest total cost to a verified result. Repeated cheap failures can cost more than one strong execution pass plus a deterministic verifier.

## Routing Algorithm Sketch

1. Classify the request into domain: coding, terminal agent, GUI/browser, research, safety/red-team, data/doc, or mixed.
2. Estimate hardness from task duration, repo scope, tool horizon, verification clarity, and cost of failure.
3. Run a cheap probe only if it can reduce uncertainty without changing state.
4. Select executor:
   - F0-F2: low-cost/general model.
   - F3-F4: balanced coding/reasoning model.
   - F5-F6: strong model for the main loop, cheap model for summaries.
   - F7-F8: strongest available model route with checkpointing and independent verification.
5. Select verifier:
   - deterministic tests first;
   - browser/UI proof for frontend behavior;
   - independent model review only for reasoning-heavy artifacts that cannot be fully tested.
6. Log the route decision and final outcome so local Fluxio results can become more important than public benchmark priors.

## Benchmark-To-Fluxio Mapping

| Fluxio Work Type | Closest Benchmark Family | Routing Implication |
| --- | --- | --- |
| Small code edit with tests | Aider, BigCodeBench | Cheap/balanced model can be enough if tests are deterministic. |
| Algorithmic coding or self-repair | LiveCodeBench | Balanced or strong model depending on novelty and test visibility. |
| Real GitHub issue repair | SWE-bench Verified/Lite/Full | Strong coding model if multi-file or test discovery is needed. |
| Industrial repo task | SWE-Bench Pro, SWE-Lancer | F7/F8 route; require route metadata and proof. |
| Terminal setup/debug/data task | Terminal-Bench | Raise tier for environment setup, shell state, or opaque failures. |
| ML research engineering | RE-Bench | F8 when the task involves experiments, GPUs, performance targets, or long loops. |
| Browser/desktop automation | OSWorld, WebArena family | Strong multimodal/tool agent plus UI proof. |
| Research assistant with tools | GAIA | Route by level: easy lookup can be cheap; multi-hop tool work should escalate. |
| Policy/API/customer workflow | tau-bench | Prioritize tool correctness, policy checks, and error attribution. |

## Safe Recommendations

- Keep public leaderboards as priors, not policy. Fluxio should record local success, cost, retries, and proof quality per route.
- Prefer cost-normalized measures when available: resolved-per-dollar, pass-per-dollar, seconds per case, malformed edit rate, and retry count.
- Do not compare scores across benchmarks as if they are the same unit. A high LiveCodeBench score does not prove OSWorld or SWE-Bench Pro competence.
- Treat agent scaffold as part of the model. SWE-bench and Terminal-Bench results depend heavily on scaffolding, tools, step limits, and context retrieval.
- For JBHEAVEN/red-team proof, keep cheap models on safe probe classification and transcript summarization. Route boundary-sensitive analysis and final scoring to a stronger model or a human-reviewed deterministic rubric.
- Always expose route reason in the UI for F6-F8: "long-horizon terminal task," "multi-file repo edit," "security-sensitive proof," "GUI grounding required," or similar.

## Open Questions For Future Runtime Work

- Define the exact numeric hardness features Fluxio should log for each mission.
- Add a local route scorecard: success, human interventions, total tokens, wall time, retry count, test result, and proof artifact completeness.
- Decide whether `F8` should be a user-visible label, an internal policy flag, or both.
- Add a periodic docs refresh because benchmark leaderboards and provider prices change frequently.
