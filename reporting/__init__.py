"""Report pipeline: builder (pure model) → render (HTML) → export
(portable HTML / PDF). Named `reporting` — NOT `reports/` — because
reports/ is the gitignored OUTPUT directory for generated files
(CLAUDE.md: PRIVACY); the package must never collide with it."""
