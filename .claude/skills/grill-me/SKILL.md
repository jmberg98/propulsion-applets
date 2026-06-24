---
name: grill-me
description: "Interview the user relentlessly about a plan or design, resolving the full decision tree. Use when user says \\\"grill me\\\" or asks for rigorous design review. Activates a structured interview that maps dependencies between decisions and batches independent questions together to minimize turns. Always provide a recommended answer with each question. Terminate with a structured decision summary doc."
---
 
# Grill Me
 
Rigorous design/plan interview that resolves a full decision tree efficiently.
 
## Phase 0 — Intake (1 turn)
 
Ask user for:
1. The plan/design doc, or a paste of it (required — don't proceed without it)
2. Depth: **shallow** (top-level decisions only) or **deep** (full tree incl. implementation)
3. Context: is a codebase accessible? (affects whether you can resolve questions by exploration)
 
If codebase accessible (Claude Code context): explore it silently before Phase 1 — answer any questions you can from code directly, remove them from the tree.
 
## Phase 1 — Map the decision tree (internal, 1 turn)
 
Before asking anything, build the full dependency graph internally:
- Identify all open decisions
- Label each node with its dependencies (which other decisions must be resolved first)
- Find the **independent set**: decisions with no unresolved dependencies
- Find **depth**: how many serial rounds the full tree requires
 
Show user the tree as a brief outline (not the questions yet):
```
Decision tree (~N rounds):
  Round 1 [independent]: A, B, C
  Round 2 [depends on A]: D, E
  Round 3 [depends on B, D]: F
  ...
```
Ask: "Scope look right? Anything to skip or add before we start?"
 
## Phase 2 — Interview loop
 
Each round:
1. **Batch** all currently-unblocked questions (no unresolved dependencies) into a single message
2. For each question, provide: **recommended answer** + 1-line reasoning + confidence [H/M/L]
3. Low confidence → flag explicitly: "Low confidence — this needs your call"
4. Wait for user responses
5. Mark resolved nodes, unlock next batch, repeat
 
**Question format per item:**
```
Q[N]: <question>
→ Rec: <recommended answer>
   Reason: <one line>
   Confidence: H/M/L
```
 
**Codebase questions** (Claude Code only): explore silently, answer yourself, note "resolved from codebase" — don't ask user unless ambiguous.
 
**Depth control:**
- Shallow: only Round 1 (top-level independent decisions) + any hard blockers
- Deep: full tree
 
## Phase 3 — Exit & summary
 
When all nodes resolved (or user says "done"), output a structured decision doc:
 
```
## Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| ...      | ...    | ...       |
 
## Open items / risks flagged
- ...
 
## Recommended next action
...
```
 
## Notes
 
- Never ask one question when multiple are independent — always batch independent questions
- Never re-ask a resolved question
- If user's answer resolves multiple downstream dependencies, acknowledge and skip those
- Graceful degradation: "explore codebase" step silently skipped on Claude.ai (no file access)
