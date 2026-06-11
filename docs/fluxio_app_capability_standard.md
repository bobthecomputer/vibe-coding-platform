# Fluxio App Capability Standard

This draft defines how a local app can expose agent-native capabilities to Fluxio without embedding a full autonomous-agent control plane.

## Core Pieces

1. App Manifest
   Declares app identity, bridge transport, auth requirements, permissions, supported tasks, context surfaces, action hooks, and UI hints.

2. Local Bridge
   A localhost or IPC endpoint for handshake, health, task execution, event streaming, and approval callbacks.

3. Capability Grants
   Explicit grants that scope what Fluxio is allowed to do inside the app. Fluxio should not assume unrestricted code execution.

## Design Principles

- Capability-scoped control only
- Local-first transport
- Reviewable permissions and approval requirements
- App-native workflows remain in the app
- Fluxio stays the orchestration shell

## Phase Plan

- Phase A: schema and mock registry only
- Phase B: one reference integration for one owned app
- Phase C: developer kit and public docs

## Current Status

The current implementation ships:

- a manifest schema draft
- example manifests in `config/connected_apps.json`
- a bridge handshake shape
- bridge-lab registry snapshots in the control room

It does not yet ship broad third-party app execution.

## Operator Handoff Contract

Connected app cards should support two safe handoffs:

1. `Use in Agent`
   Seeds the Agent composer with the app name, bridge role, aliases, requested task, current context preview, status, and bridge health. The Agent then chooses the runtime/provider route and reports what is ready or missing before any app write.

2. `Make skill`
   Seeds a Skill Studio draft prompt from the app context. The draft must name the trigger, required context, allowed actions, approval rules, tests, and conditions where the skill must not run.

Both actions are explicit user actions. They do not execute app writes silently.

## Follow-On Personal Manager Apps

`Mind Tower` is registered as a follow-on personal manager/time-management bridge. It is intentionally `manifest_only` until a real local bridge exposes health, context, task execution, and approval callbacks. The manifest carries aliases such as `tower`, `time manager`, and `JBHABCN` so rough operator wording can still route to the right app context.

This keeps the app visible to Agent and Skill Studio without pretending the bridge is already live.
