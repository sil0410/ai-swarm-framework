# AI Swarm Framework

Version: 0.1.0
License: MIT

AI Swarm Framework is a local-first, file-based coordination layer for multiple AI agents running on different machines.

It is not an AI group chat.

Agents do not rely on private chats as the source of truth. They coordinate through tasks, handoffs, status files, outputs, and human-reviewed inbox files in a shared folder such as a NAS, Samba share, OneDrive folder, or mounted network volume.

## What this solves

If you have multiple machines, for example:

- a Mac mini as coordinator
- a Windows workstation as planner
- a Linux GPU box as producer
- another PC as researcher/crawler

this framework gives them a simple shared protocol:

```text
Human
  -> Coordinator checks shared state
  -> Planner / Researcher / Producer do their work locally
  -> Agents create task and handoff files
  -> Outputs are written to shared folders
  -> Coordinator reports progress back to the human
```

## Core idea

```text
AI_ControlCenter/
  CORE.md
  AGENTS.md
  projects/
  skills/
  inbox/
  swarm/
    tasks/
      inbox/
      active/
      blocked/
      done/
    handoffs/
      pending/
      accepted/
      done/
    status/
    outputs/
```

- `CORE.md`: team rules and operating principles.
- `AGENTS.md`: agent roles and capability boundaries.
- `projects/`: project truth.
- `skills/`: reusable procedures.
- `inbox/`: agent outputs waiting for human review.
- `swarm/tasks/`: task state.
- `swarm/handoffs/`: explicit work transfers between agents.
- `swarm/status/`: heartbeat/status files.
- `swarm/outputs/`: artifacts and deliverables.

## Safety model

This framework is intentionally conservative:

- NAS/shared-folder sync is one-way by default: shared folder -> local working copy.
- No `rsync --delete` or deletion-propagating sync is used.
- Core governance files are not automatically overwritten.
- Agents should write outputs to `inbox/` or `swarm/outputs/` for human review.
- High-risk actions and external publishing should require human confirmation.

## Quick start

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Configure this machine:

```bash
python ai_framework.py install
```

You will be asked for:

1. the shared folder / NAS path as this machine sees it
2. the local working copy path
3. this machine's agent identity

Start sync:

```bash
python ai_framework.py start
```

Check status:

```bash
python ai_framework.py status
```

Create context for an agent:

```bash
python ai_framework.py context --project demo --copy
```

Create a task:

```bash
python ai_framework.py task --project demo --title "Collect market references" --assignee Researcher --goal "Write market_research.md" --next-agent Planner
```

Create a handoff:

```bash
python ai_framework.py handoff --to-agent Producer --task TASK-YYYYMMDD-001 --summary "Prompts are ready" --next-action "Generate 3 candidate images"
```

Coordinator global view:

```bash
python ai_framework.py status --all
```

## Cross-platform NAS paths

Each machine can use the path format native to its OS.

Windows:

```text
//server/share/AI_ControlCenter
\\server\share\AI_ControlCenter
C:/AI_ControlCenter
```

macOS:

```text
/Volumes/AI_ControlCenter
```

Linux:

```text
/mnt/AI_ControlCenter
/home/user/AI_ControlCenter
```

The paths do not need to look the same across machines. Each machine only needs to know how it reaches the shared folder.

## Default agent roles

The open-source example uses generic roles:

- `Coordinator`: gateway, monitoring, summaries, routing suggestions.
- `Planner`: architecture, decomposition, writing, prompts, review.
- `Producer`: GPU tasks, local models, image/video/rendering work.
- `Researcher`: web research, scraping, data collection, source summaries.

You can rename these roles in your own configuration.

## Documentation

- `INSTALL_RUN_GUIDE.md`: operator guide.
- `docs/architecture.md`: design overview.
- `docs/hermes_integration.md`: using this with Hermes Agent or other AI agents.
- `examples/four_agents.example.json`: example configuration.

## Roadmap

Planned after 0.1.0:

- task state update helper
- handoff state update helper
- heartbeat writer
- coordinator monitor summaries
- Telegram/Discord gateway examples
- optional local model / ComfyUI endpoint integration

## License

MIT License. See `LICENSE`.
