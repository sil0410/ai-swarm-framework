# Architecture

AI Swarm Framework is a file-based coordination layer for multiple AI agents running on different machines.

## Non-goals

This project is not:

- a group chat system
- a model router
- a database-backed task server
- a fully autonomous multi-agent platform
- a replacement for human review

It is a simple, inspectable protocol that works with folders and files.

## Layers

### 1. Governance layer

Stable files:

- `CORE.md`
- `AGENTS.md`
- `projects/*.md`
- `skills/*.md`

These define rules, identities, project truth, and reusable procedures.

### 2. Work-state layer

Mutable files:

- `swarm/tasks/*/*.json`
- `swarm/handoffs/*/*.json`
- `swarm/status/*.json`
- `swarm/outputs/**`
- `inbox/*.md`

These define current work, handoffs, status, and artifacts.

### 3. Agent runtime layer

Any agent runtime can use the framework:

- Hermes Agent
- Claude Code
- OpenAI Codex CLI
- local scripts
- custom bots
- web UIs

The runtime reads context and writes files. The framework does not require a specific AI provider.

## Handoff principle

Agents should not rely on private chat as the source of truth.

Instead:

1. Agent A finishes a step.
2. Agent A creates `swarm/handoffs/pending/HANDOFF-*.json`.
3. The coordinator or receiving agent sees the handoff.
4. Agent B accepts and works.
5. Results go to `swarm/outputs/` or `inbox/`.

This makes work auditable, recoverable, and resilient to offline machines.

## Coordinator pattern

One machine can act as coordinator:

- scans tasks
- scans handoffs
- checks stale status
- summarizes progress
- asks the human for decisions

The coordinator should not become an unchecked boss. It reports and suggests; the human retains final authority for high-risk actions.
