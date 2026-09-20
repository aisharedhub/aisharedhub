# Updated V376 — build workspace

Working tree for the final unified MT5 bot ("Updated V376").

- `build/` — the bot source and pinned full-history seed (DEFAULT auto-discovery variant).
  Baseline imported from the verified V389 r4 DEFAULT release
  (source sha256 083435eabce32a85a0b4ee28a183b855d52027b026384fb6b45c26bfca5d22ca;
  strategy AST verified byte-identical to trusted V376
  07516a8cd8d500532231d0e8050ced32413592a3475147bfef3b4a714afb9a97).
- `tests/` — offline test campaign (inert fake MT5; zero broker sends, proven by counter).
- `tools/` — deterministic packaging and manifest tooling.
- `docs/` — change report, handoff instructions, release README sources.

Live account state evidence (bot_state_v12.json and .bak) is deliberately NOT
committed: it contains account identity and balances. Tests that require it read
`UPDATED_V376_EVIDENCE_DIR` and are skipped when the directory is absent.
