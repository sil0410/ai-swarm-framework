# Hermes Integration

AI Swarm Framework works well with Hermes Agent, but it does not require Hermes.

## Basic pattern

For each agent session:

```bash
python ai_framework.py context --project demo --copy
```

Paste the generated context into Hermes, Claude Code, Codex CLI, or another agent runtime.

The context includes:

- `CORE.md`
- `AGENTS.md`
- selected project file
- matched skills
- recent inbox entries
- tasks assigned to this agent
- handoffs addressed to this agent

## Suggested agent startup prompt

```text
You are the agent described in the provided AI Swarm Framework context.
First confirm in three short lines:
1. who you are
2. the project goal
3. the top constraint
Then inspect your assigned tasks and pending handoffs.
Do not modify governance files directly. Write outputs to inbox/ or swarm/outputs/.
```

## Coordinator usage

On the coordinator machine:

```bash
python ai_framework.py status --all
```

The coordinator can summarize:

- active tasks
- blocked tasks
- pending handoffs
- stale status files
- outputs waiting for human review

## Gateway usage

If your agent framework supports Telegram/Discord/Slack, connect the coordinator agent to the gateway and have it run or read the equivalent of:

```bash
python ai_framework.py status --all
```

This gives the human a remote progress console without turning the system into uncontrolled agent-to-agent chat.
