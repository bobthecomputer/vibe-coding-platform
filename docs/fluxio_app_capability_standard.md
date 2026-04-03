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
