# Skill slicing — de-over-specifying agent instructions

Method for cutting skills, CLAUDE.md files, and agent prompts. Frame (per
Boris Cherny / Claude Code): **describe the task, the guardrails, and the exit
criteria — then let the model cook.** Everything else is choreography, and the
model pays to read it on every single invocation. Only add an instruction
after *observed repeated failure*, never preemptively; delete aggressively
with each model generation, because most instructions correct behaviors the
previous model lacked and the current one has.

## Order of operations

1. **Usage audit before any editing.** Count real invocations per skill
   (transcript grep). A skill with ~zero uses gets uninstalled, not polished —
   deleting dead weight is the best slice, and polishing it is ceremony.
2. **Classify every line**, then act by class:

   | Class | Action |
   |---|---|
   | Machine/infra fact the model can't know | keep |
   | Incident-derived rule | keep, compressed to one line + `(measured: X)` tag |
   | Interface: template, schema, command syntax, output contract | keep — structure is what licenses prose deletion |
   | Explicit override of a platform default | keep, marked as an override |
   | Taste a current-gen model already has | cut |
   | Restatement of anything above it, or of another layer | cut — one canonical home, pointers elsewhere |
   | Choreography: step-by-step how, phase narration, hand-holding | cut |
3. **Hunt the self-correcting machinery.** The strongest over-specification
   tell is layer N+1 existing to clean up layer N's output (a verification
   panel that refutes the review panel's findings; a validator that checks the
   fixer). Don't compress those layers — delete them and fix layer N's
   incentive instead.
4. **Install an evidence bar where findings flow.** Any blocker/claim must
   name a concrete observable failure — a failing test, a repro command, a
   verified broken invariant at file:line. No evidence → advisory, triggers
   nothing. This kills phantom work at the source instead of downstream.
5. **Ledger every cut that changes architecture**: decision, evidence, and a
   reopen condition ("re-add when X actually bites — as a mechanism, not
   prose"). Deletion is an experiment, not a verdict.

## Boundary conditions — where minimalism inverts

- **Minimalism is for the expensive judgment model.** A cheap or cross-vendor
  builder tier often needs the opposite edit: explicit mechanical rules,
  stated close to the action. Never let a byte count make the acting tier the
  thin one.
- **Delegate-read rules inline into the spawn prompt** (delegate context is
  empty — the bytes are free there); orchestrator-read reference goes behind a
  pointer. A pointer handed to a delegate is only a probability of delivery.
- **Irreversible-action gates survive verbatim** — never-merge, worktree-or-
  abort, destructive-delete proofs. Compress the wording, never the condition.
- **`(measured: ...)` tags are load-bearing** on rules governing delegates —
  the citation is what stops a model arguing its way out mid-run.
- **Frontmatter descriptions are always-on cost** — every installed skill's
  description is in context every turn. Shrink them with the same knife.

## Smell tests

- Does this line change what a competent model would do? No → cut.
- Can this rule name the failure it prevents? No → cut.
- Is this the second place this rule lives? Cut all but the canonical one.
- Is this prose describing what a script could do deterministically? Write
  the script, delete the prose.
- Would you have to guess whether it helps? Don't guess — run the A/B.
