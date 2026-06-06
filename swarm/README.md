# Swarm work layer

This layer handles task assignment and inter-agent handoff. It does not replace the governance layer.

- `CORE.md` / `AGENTS.md`: governance and identity, normally read-only.
- `projects/` / `skills/`: project context and reusable procedures.
- `swarm/`: mutable work state: tasks, handoffs, status, outputs.

## Directory shape

```text
swarm/
  tasks/
    inbox/      # new tasks not yet active
    active/     # assigned and in progress
    blocked/    # blocked, needs human decision or external condition
    done/       # completed task records
  handoffs/
    pending/    # Agent A handed work to Agent B; B has not accepted yet
    accepted/   # B has accepted
    done/       # handoff completed
  status/       # agent heartbeat / current state
  outputs/      # task artifacts, optionally grouped by TASK-ID
  templates/    # JSON templates
```

## Rules

1. Agents do not use private chat as the source of truth.
2. Inter-agent transfer must be written as `handoffs/*.json`.
3. The coordinator reads `tasks/`, `handoffs/`, `status/`, and `inbox/` to report progress.
4. The human keeps final decision authority.
5. Do not automatically modify `CORE.md`, `AGENTS.md`, or formal `projects/*.md` files.
6. Do not delete central shared-folder data by default.

## Commands

Create a task:

```bash
python swarm_create_task.py --path . --project demo --title "Collect demo market references" --assignee Researcher --goal "Collect competitor references and write a markdown summary"
```

Create a handoff:

```bash
python swarm_create_handoff.py --path . --from-agent Planner --to-agent Producer --task TASK-YYYYMMDD-001 --summary "Visual direction is ready" --next-action "Generate 3 candidate images"
```

Check an agent's work:

```bash
python swarm_check.py --path . --agent Producer
```

Coordinator global view:

```bash
python swarm_check.py --path . --agent Coordinator --all
```
