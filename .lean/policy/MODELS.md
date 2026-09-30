# Models

Only rules an agent can act on belong here. An agent usually cannot change its own model or reasoning effort mid-session.

## What the agent controls

- **Subagent model** — when spawning a subagent, pick the model for the job:
  - Fast/cheap model — mechanical, well-specified work: search, locating code, renames, formatting.
  - Default model — normal implementation and review.
  - Strongest model — `HIGH` risk review, or work that failed twice with the default.
- **Its own depth of work** — more reading, more checks, a second review pass. Spend this only with a useful reason.

## What the user controls

The session model and effort setting. Recommend a change to the user in one line when:

- The same task failed validation or review twice for reasons that look like reasoning limits.
- Risk is `HIGH` and the current model is a fast/cheap one.
- The work is mechanical and a cheaper model would do.

Do not switch silently and do not stall waiting for an answer; continue with what is available.

## Rules

- Do not use the strongest model by default.
- Do not spend more effort merely because a task is long.
- Escalate one step at a time and record the reason.
- When `REVIEW.md`'s round cap fires, the report may recommend a stronger model for a further
  round. It does not license taking that round unasked.
- Never lower the quality floor to save budget.
