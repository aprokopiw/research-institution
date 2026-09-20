# Mental Model: How the Four Repos Fit Together

> A picture for thinking about research-institution, math-engine,
> pi_monitor, and a research program like kaplansky as one system.
> This is a mental model, not a contract. It helps you predict
> where new code belongs; it does not replace the ADRs that
> define each piece.

## The one-line picture

The institution is a small machine:

```
                +---------------------------+
                |     research-institution  |
                |       (the orchestrator)  |
                +-------------+-------------+
                              |
                              | catalogs, dispatches, decides work
                              v
+---------------------+   +-------------------+   +---------------------+
|      math-engine    |   |     pi_monitor    |   |  research program    |
|  (kernel + runtime) |   | (process driver) |   | (kaplansky: state)  |
+---------------------+   +-------------------+   +---------------------+
        ^                        ^                        ^
        | generic math services  | worker supervision     | domain content
        |                        |                        | (proofs, audit,
        +----- one OS only ------+--- one worker -------+  roadmap)
```

The four repos are roles in this machine. The rest of this doc
explains each role and how data moves between them.

## The four roles

### `math-engine` is the kernel and runtime

It provides generic, program-agnostic services:

- A **kernel** surface: `ProgramProviders`, `WorkSourceProviderError`,
  error codes (`SOURCE_*`, `CONFIG0*`, `PROVIDER0*`), entry-point
  groups (`mathlint.providers`). The kernel permits exactly one
  installed provider per machine — that is `research-institution`.
- A **runtime library**: validators, receipts, audit chains,
  pairing logic, source-decision semantics, the `mathlint roadmap`
  / `mathlint live-run` / `mathlint research-stop` / `mathlint
  research-status` CLIs. Any program can call these without
  knowing about other programs.

What it deliberately does **not** know: which research programs
exist, where their repos live, what the supervisor should do next,
how to model Kaplansky's roadmap, or who the operator is. All
of those questions are the OS's job. Anchored by
`@ADR-0014` (mathlint does not import program-named modules),
`@ADR-0091` (mathlint does not ship program launchers), and
`@CTR-0020` (the three-repo wire contract).

### `research-institution` is the orchestrator

It owns the four things that let the rest of the system be useful:

- **The catalog** (`catalog/programs.toml`): what programs exist,
  where each repo lives, how each program is invoked. The catalog
  is the single source of truth for "what is in flight at this
  institution." (`@CTR-0088`.)
- **The bootstrap** (`scripts/bootstrap-institution.sh`): clone and
  install every catalog entry from a fresh checkout. Idempotent.
- **The green gate** (`green-gate/check-institution.sh`): the one
  command that prints `GREEN INSTITUTION READY` when the machine
  is wired. Operator-facing. (`@INV-0093`.)
- **The dispatcher CLI** (`research_institution/`): a thin shell
  that takes operator commands and routes them to the right binary
  (`mathlint ...` or `pi-monitor ...`). Every command is a thin
  subprocess wrapper; no logic, no parsing, no persistence.

Plus, since `@ADR-0007`: the **work-decision** for the supervisor.
When `mathlint-source` asks "what should the supervisor dispatch
next?", the answer comes from the orchestrator's
`select_next_work_for_supervisor`. The orchestrator reads the
catalog, the supervisor state directory, and the model's route
(all things it already owns) and emits a dispatch envelope.

The orchestrator never runs math work itself. It only routes.

### `pi_monitor` is the process driver

It owns one running worker process:

- Spawns and supervises a single `pi --mode rpc` worker.
- Manages the worker's stdin/stdout pipes (`pi_monitor/rpc.py`).
- Persists state files the orchestrator reads
  (`~/.local/state/mathlint/pi-monitor/`).
- Exposes a Textual TUI (`pi-monitor watch`) so the operator can
  drive the worker interactively.
- Runs `pi-monitor doctor` so the institution green gate can
  verify the driver is healthy.

The driver doesn't decide what to compute or when. The
orchestrator decides what to queue; the kernel decides the
math-shape of the work; the driver owns the worker's lifecycle.

### The research program is the persistent state

Kaplansky is the example. The repo is not "the work" — it is
**where the work is written down**. The orchestrator reads its
roadmap to know what to dispatch; the kernel writes receipts
into it after every iteration; the driver keeps the worker alive
while it produces theorem content. The repo holds:

- The roadmap (`programs/kaplansky-roadmap.toml`): what the
  program intends to prove, in what order.
- The audit reports and obligation labels the kernel consumes
  via `ProgramProviders` content slots.
- The proofs, lemmas, certificates the worker writes — the
  artifact the institution is producing.

If you install a second program (say, a different conjecture),
its repo follows the same shape: roadmap + content. The
orchestrator doesn't change. The kernel doesn't change. The
driver doesn't change. Only the catalog grows by one entry.

## How a `research start kaplansky` flows

```
operator:  research start kaplansky
              |
              v
   research-institution (the dispatcher):
     1. load catalog (programs.toml) -> Program("kaplansky")
     2. read mathlint's roadmap via `mathlint roadmap`
        -> GateVerdict(task_kind=RESEARCH, status=OPEN)
     3. verify credentials via resolve_model_route()
     4. exec: `pi-monitor run --config <cfg>`
              |
              v
       pi_monitor (the driver):
         spawns the worker:
              |
              v
            pi --mode rpc
              |
              v
         at every supervisor tick:
            mathlint-source asks "what next?"
              |
              v
         research-institution's select_next_work_for_supervisor:
            reads catalog[kaplansky].roadmap_path
            reads pi_monitor_state_dir/health.json
            reads resolve_model_route() for the model identity
            returns a Dispatch envelope (or Wait when no roadmap reader yet)
              |
              v
         worker runs the work, writes a receipt back into
         kaplansky/ via the kernel's audit-chain path
```

Notice where the boundaries are:

- The orchestrator never speaks Pi-internals or math-specifics.
- The kernel never reads the catalog.
- The driver never decides what to compute.
- The research program never decides when to run.

Each role has one job. Code that crosses a boundary belongs in
the role that owns the receiving side.

## How to use the model

When you're about to add code and don't know where it goes, ask
three questions:

1. **Is it generic math?** (Validators, audit logic, source
   decisions, error codes, the work-decision interface.) → kernel.
2. **Is it about which programs exist, how they're wired, or
   when they run?** (Catalog, bootstrap, dispatcher, scheduler,
   gate check.) → orchestrator.
3. **Is it about a single worker's process lifecycle?** (Pipes,
   restart logic, TUI, state files.) → driver.
4. **Is it content for a specific research program?** (A proof
   strategy, an obligation, a roadmap tick.) → that program's
   repo.

If the answer is two of these, the code is probably wrong:
split it. The boundary violations are how the system got into
the 5a/5b deadlock that `@ADR-0007` resolved.

## Where the analogy breaks (and why that's fine)

The kernel/OS/driver/state model is a mental scaffold, not a
claim that these repos implement a literal operating system.
Three places it strains:

- **The kernel ships Python libraries.** A pure kernel doesn't
  carry application code. `math-engine` does — the validators,
  receipts, and source-decision semantics are runtime libraries
  glued to the kernel. Treat it as "kernel + runtime," the way
  you might treat Linux + glibc.
- **The orchestrator doesn't execute anything.** A real OS has
  a scheduler, memory manager, and IO. `research-institution`
  has a dispatcher that shells out; it never runs math work.
  Treat it as a control plane (Kubernetes / systemd shaped),
  not a full OS.
- **The driver is one process.** Real device drivers manage many
  devices. `pi_monitor` manages exactly one worker per
  supervisor process. The `watch` command exposes a TUI; the
  `run` command is the daemon.

When in doubt, follow the ADR citations above. They are the
durable record of what each role actually does today.

## Cross-references

The durable records that anchor each role:

| Role | Anchor records |
|---|---|
| Kernel + runtime (`math-engine`) | `@ADR-0014` (no program imports), `@ADR-0091` (no program launchers), `@CTR-0020` (three-repo wire contract) |
| Orchestrator (`research-institution`) | `@ADR-0006` (scope), `@CTR-0088` (catalog), `@INV-0093` (green gate), `@ADR-0007` (work-decision), `@CTR-0094` (dispatch envelope) |
| Driver (`pi_monitor`) | pi_monitor's `@ADR-0001` (source owns domain meaning; monitor owns execution) + `pi_monitor/supervisor.py` |
| Program content (kaplansky) | `@ADR-0014` + the per-program `mathlint_plugin.py` docstring |

Some research-institution ADRs cite `@INV-0091` and `@INV-0092`
as cross-repo anchors for "mathlint is program-agnostic" and
"pi_monitor is program-agnostic." Those IDs are aspirational —
math-engine's invariants only run up to `@INV-0088` today. The
semantically equivalent records that DO exist are:

- For "mathlint is program-agnostic": math-engine `@ADR-0014`.
- For "pi_monitor is program-agnostic": pi_monitor `@ADR-0001`
  ("source owns domain meaning; monitor owns execution") which
  says the same thing from the driver's side.

If the operator wants to canonicalize the `@INV-0091` /
`@INV-0092` IDs, that's a future semantic-record work item;
until then, use the ADRs above as the durable anchors.
