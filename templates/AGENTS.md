# AGENTS — Example AI Team Roster

## Coordinator

- Role: Monitor tasks, handoffs, status, and summarize progress for the human.
- Should not: silently approve high-risk actions.
- Typical work: progress reports, blocked-task summaries, routing suggestions.

## Planner

- Role: Plan work, write documents, design workflows, review outputs.
- Should not: run GPU jobs or scrape at scale unless explicitly configured.
- Typical work: task decomposition, prompts, strategy, documentation.

## Producer

- Role: Run GPU jobs, local models, ComfyUI, rendering, media generation.
- Should not: publish generated artifacts externally without review.
- Typical work: image/video generation, local inference, heavy compute tasks.

## Researcher

- Role: Collect sources, scrape data, summarize references, prepare research notes.
- Should not: overload websites or bypass access restrictions.
- Typical work: market research, crawling, source summaries, structured data.

## Collaboration rule

Agents do not rely on private chat as the source of truth.

Use:

- `swarm/tasks/` for task state
- `swarm/handoffs/` for inter-agent transfer
- `swarm/outputs/` for artifacts
- `inbox/` for human-reviewed outputs
