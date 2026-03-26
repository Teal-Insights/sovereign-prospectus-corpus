# Documentation Governance

## File Roles

| File | Purpose | Who updates |
|------|---------|-------------|
| `CLAUDE.md` | Agent quick-start (~80 lines) | Teal only |
| `SESSION-HANDOFF.md` | Current task | Teal only |
| `docs/RATIFIED-DECISIONS.md` | Architecture decisions | After council rounds |
| `docs/DOMAIN.md` | Domain rules and sources | When domain changes |
| `docs/ARCHITECTURE.md` | Directory structure | When structure changes |
| `planning/tasks/*.md` | Task specs | Each new task |

## Rules

1. **CLAUDE.md stays slim.** Under 100 lines. Extract to docs/ if it grows.
2. **SESSION-HANDOFF.md is the entry point.** One file says what to do next.
3. **Stale docs go to archive/.** No competing instructions.
4. **No sensitive content in committable files.** No names, funding, strategy.
5. **Phase 1 scripts are read-only reference.** Implementation goes in src/corpus/.

## Branch Strategy

- **main:** Protected. No direct commits.
- **feature/*:** All work. Merge via PR or fast-forward.