# Agent folder

Working record of Claude Code's own plans, decisions, and prompts for this
repository — kept separately from `docs/` (user-facing project docs).

- `decisions/` — one file per non-trivial decision, named
  `YYYY-MM-DD-short-slug.md`, dated and timestamped (UTC) at the time the
  decision was made.
- `plans/` — implementation plans for larger changes.
- `prompts/` — prompts or context worth preserving verbatim.

## Decision log

- [2026-09-23-remove-edge-addition-deletion.md](decisions/2026-09-23-remove-edge-addition-deletion.md) — removed the `edge_addition_deletion` perturbation (deprecated, unused).
- [2026-09-23-remove-triangle-injection-removal.md](decisions/2026-09-23-remove-triangle-injection-removal.md) — removed the `triangle_injection_removal` perturbation (deprecated, unused).
- [2026-09-23-remove-imdb-binary.md](decisions/2026-09-23-remove-imdb-binary.md) — removed IMDB-BINARY and its generic TU-format loader (uninformative per Coupette et al. 2025).
