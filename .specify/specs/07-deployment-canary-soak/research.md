# 07 — Research

## Existing assets reused

- `research_institution/research_institution/cli.py` —
  production launcher (`research start`, `research doctor`,
  `research status`, etc.).
- `research-institution/launchd-templates/kaplansky-pi-monitor.plist.xml`
  — rendered under `--macos-isolated-label=<unique>`.
- `research-institution/config-templates/kaplansky-pi-monitor.toml`
  — supervisor config.
- `~/.pi/agent/auth.json` (per `@ADR-0001` — kaplansky uses pi
  OAuth).
- `math/src/mathlint/self_test/sample_program/` (entry 04).
- `pi_monitor/tests/substrate/` (entry 05).
- `research_institution/gates/verify_simulation/` (entry 06).
- `.specify/memory/constitution-verify.md` §3, §5, §10.

## Rejected parallel approaches (with reasons)

- **R1.** A real-provider soak on the operator's real kaplansky
  data. REJECTED: violates FR-5's "never mutates production."
- **R2.** A sub-shell wrapper that hides the launchctl call.
  REJECTED: per §9.2, one canonical CLI.
- **R3.** Importing pi_monitor internals into the canary runner
  for a "fast path." REJECTED: per §6, no second supervisor.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does canary `BLOCKED` ever become `PASS`? | Never without a real credential-backed run. The `BLOCKED` status is a terminal release state if credentials are absent. |
| Soak is required at every release? | Yes per master guide §5 + constitution §5 action matrix. |

## Open risks

- **R-A.** Provider canary leaks credentials via env. Mitigation:
  the runner sanitizes env; `transcript_oracle` rejects
  `OPENAI_API_KEY` substrings.
- **R-B.** macOS deployment leaves a stub LaunchAgent. Mitigation:
  `try/finally` + `launchctl bootout` always.

## Cross-references

- `@ADR-0001` (kaplansky uses pi OAuth).
- pi_monitor `@ADR-0004` (macOS background service).
