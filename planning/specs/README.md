# Specs (SpecFlow-style Planning)

This folder uses a brainstorm → spec → tasks workflow inspired by SpecFlow.

## Workflow

1. **BRAINSTORM.md** — Unstructured thinking. Dump ideas, questions, constraints.
   Teal describes what they want. Claude asks Socratic questions to clarify.
   
2. **SPEC.md** — Structured specification derived from the brainstorm.
   Clear problem statement, proposed solution, scope boundaries, decision log.
   
3. **TASKS.md** — Ordered implementation tasks with completion criteria.
   Each task is a single-session unit of work. Maps to a GitHub issue.

## Naming Convention

```
planning/specs/
├── README.md                           # This file
├── 2026-03-25_clean-architecture/      # One folder per spec
│   ├── BRAINSTORM.md
│   ├── SPEC.md
│   └── TASKS.md
└── YYYY-MM-DD_short-name/             # Next spec
    ├── BRAINSTORM.md
    ├── SPEC.md
    └── TASKS.md
```

## Rules

- Brainstorm before specifying. Specify before tasking.
- Each task must have clear completion criteria (testable).
- Tasks map 1:1 to GitHub issues and feature branches.
- Specs are living documents — update as you learn.