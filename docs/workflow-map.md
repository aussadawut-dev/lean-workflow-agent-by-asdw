# Workflow map

[Back to README](../README.md)

Every path a task can take through Lean, from the contract to the Quality Gate. The phases are described in the [workflow guide](workflow.md); the rules behind each branch live in the policies linked below.

```mermaid
flowchart TD
  P(["prompt"]) --> C{"trivial?"}
  C -->|"yes"| CT["Contract: trivial"]
  CT --> IT["implement"]
  IT --> EV["evidence: a passing check or a stated reason"]
  EV --> D
  C -->|"no"| CN["Contract: risk, quality, acceptance"]
  CN --> S{"mode"}
  S -->|"standard"| SC["scope"]
  S -->|"tracker"| TR["lean tracker new"]
  TR --> SC
  S -->|"full"| TR2["tracker + queue claim"]
  TR2 --> SC
  SC --> AQ{"wait for approval?"}
  AQ -->|"ambiguous, HIGH risk or open decision"| W["lean-scope, lean-grill, lean-research"]
  W --> SC
  AQ -->|"clear request"| X{"execution"}
  X -->|"direct"| IM["implement"]
  X -->|"direct + spawn"| SP["one sized agent, 3S to 3XL"]
  SP --> IM
  X -->|"delegated"| DL["Controller assigns a worker"]
  DL --> IM
  X -->|"/lean-agents"| PA["parallel agents for independent tasks"]
  PA --> IM
  IM --> T["test: lean test --changed"]
  T --> V["validate: PROJECT.md checks"]
  V --> R{"review depth"}
  R -->|"LOW"| RL["self-check"]
  R -->|"MEDIUM"| RM["focused diff review"]
  R -->|"HIGH"| RH["independent reviewer records a receipt"]
  RL --> RV{"verdict"}
  RM --> RV
  RH --> RV
  RV -->|"REWORK"| IM
  RV -->|"second REWORK"| LP["one last pass with only those fixes"]
  LP -->|"REWORK again"| B
  RV -->|"PASS"| G{"gate mode"}
  LP -->|"PASS"| G
  G -->|"auto"| GR["lean gate run at Stop"]
  G -->|"manual"| MA["NOT_RUN until the user authorizes"]
  MA --> GR
  GR -->|"pass"| D(["DONE"])
  GR -->|"this task's failure"| FX["fix and rerun; fixloop modes repeat without asking"]
  FX --> GR
  GR -->|"pre-existing failure or missing tool"| B(["BLOCKED"])
  GR -->|"lock busy"| U(["UNVERIFIED after three Stops"])
  GR -->|"gate controls changed"| AC["covering HIGH receipt or lean gate accept-controls"]
  AC --> GR
  classDef done stroke:#5a8f00,stroke-width:2px
  classDef stop stroke:#c0392b,stroke-width:2px
  classDef warn stroke:#c77c00,stroke-width:2px
  class D done
  class B stop
  class U warn
```

## Reading the branches

- **Trivial or not.** A task is trivial when risk is `LOW`, the goal is clear, and it touches one file or makes a mechanical edit across a few. Trivial tasks skip scope, trackers and formal review but still need evidence ([WORKFLOW.md](../.lean/policy/WORKFLOW.md#trivial-task)).
- **Mode.** `standard` keeps session records, `tracker` adds one `docs/tracking/TCKNNN.md` per workset, and `full` adds a claimed queue item for each task ([workflow guide](workflow.md)).
- **Approval.** A clear implementation request is approval of its scope. Lean waits only when the request is ambiguous, risk is `HIGH`, a material decision is open, or the scope grows ([lean-scope](../.lean/skills/lean-scope/SKILL.md)).
- **Execution.** `direct` works in the session and spawns at most one sized agent when that costs less; `delegated` makes the active agent a Controller; `/lean-agents` runs parallel agents for independent tasks ([agents and models](agents-and-models.md)).
- **Review depth.** The deeper of risk and quality floor. `HIGH` needs an independent reviewer, never a fork, and only the reviewer records the receipt. A `PASS` ends review; a second `REWORK` gets one last pass with only those fixes, and the task is `BLOCKED` if that pass is also `REWORK` ([REVIEW.md](../.lean/policy/REVIEW.md)).
- **Gate.** `auto` modes run the gate at Stop; `manual` modes report `NOT_RUN` until the user authorizes a run. A busy lock, an unwritable marker or a pending review releases the Stop as `UNVERIFIED`, which is never a pass. Changed gate controls need a covering `HIGH` review or `lean gate accept-controls` with the user's approval ([quality and runtime](quality-and-runtime.md)).

Only the Quality Gate sets `DONE`. `FAILED` is a tracker state for work that cannot continue ([RECOVERY.md](../.lean/policy/RECOVERY.md)).
