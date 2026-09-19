---
id: ADR-0001
kind: decision
status: accepted
title: Kaplansky authenticates via pi OAuth, not an OpenAI API key
date: 2026-09-13
related:
  - math/docs/semantic/adr/adr-0008-evidence-before-paired-live-readiness.md
  - catalog/programs.toml
  - math/src/mathlint/local_readiness/system.py
supersedes: []
---

# ADR-0001: Kaplansky authenticates via pi OAuth, not an OpenAI API key

## Context

`catalog/programs.toml` declares `live_credential_env_vars = ["MATHLINT_MODEL_ROUTE", "OPENAI_API_KEY"]` for the kaplansky program. The intent is to require the operator's shell to export the credentials a live readiness check needs.

The reality on the operator's machine (per `~/.zshrc` and `~/.pi/agent/auth.json`):

- No `OPENAI_API_KEY` exists; pi uses an `openai-codex` OAuth grant
  (`type: oauth`, JWT access + refresh tokens, accountId-bound).
- No OpenAI Platform API key has been issued for this account.

Mathlint's own auth path for any `openai-codex/*` model route already delegates to `pi auth check --model <route> --no-refresh` and requires only the OAuth token in `~/.pi/agent/auth.json`. The `OPENAI_API_KEY` env var is checked only for non-OAuth routes (`math/src/mathlint/local_readiness/system.py:470-484`).

Continuing to require `OPENAI_API_KEY` in `live_credential_env_vars` is a false gate: mathlint does not consume it, and the operator cannot satisfy it.

## Decision

Kaplansky authenticates to the model provider via pi's OAuth grant, stored at `~/.pi/agent/auth.json`. The `OPENAI_API_KEY` env var is dropped from kaplansky's `live_credential_env_vars`. `MATHLINT_MODEL_ROUTE` is retained and must equal the operator's chosen `openai-codex/*` route (currently `openai-codex/gpt-5.6-luna`).

`live_credentials_required` remains `true` so `--live` still performs the OAuth round-trip via `mathlint agent-smoke`.

## Rationale

- Mathlint source already implements OAuth-via-pi as the canonical auth for `openai-codex/*` routes; the catalog was a stale mirror of an earlier API-key assumption.
- Forcing the operator to obtain a Platform API key to satisfy a check that does not use it is a false-green / false-red surface.
- The OAuth token in `~/.pi/agent/auth.json` is refreshable by `pi auth check --model ...` without operator action, so this aligns with the institution's "fully autonomous" goal.

## Alternatives considered

- **Issue an OpenAI Platform API key and add it to `~/.zshrc`.** Rejected: mathlint does not consume it for `openai-codex/*` routes, and adds a credential the operator does not otherwise need.
- **Change mathlint's auth path to API-key-only.** Rejected: that is a math-engine architectural change outside this repo's scope and would break existing operator setups.
- **Switch kaplansky's `model_route` to a non-OpenAI provider (e.g. `openrouter/...`).** Deferred: would require editing `~/.config/mathlint/local.toml` and a math-engine ADR. Open as a follow-up ADR if OAuth-via-pi becomes unavailable.

## Consequences

- `--live` green-gate will pass with only `MATHLINT_MODEL_ROUTE` exported (plus the existing OAuth token in `~/.pi/agent/auth.json`).
- `scripts/launch-program.sh`'s credential check no longer requires `OPENAI_API_KEY` for kaplansky.
- Future programs added to `catalog/programs.toml` MUST be evaluated against the actual auth path their `model_route` triggers in mathlint; the schema does not enforce OAuth-vs-API-key alignment.

## Change triggers

Revisit if:

- mathlint changes its auth path for `openai-codex/*` routes away from `pi auth check`.
- pi's OAuth grant becomes unreliable (e.g. refresh-token rotation breaks).
- The institution onboards a provider that requires a Platform API key (e.g. Anthropic, Google) — extend `live_credential_env_vars` per program, do not reintroduce it on kaplansky.
