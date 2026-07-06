# AGENTS.md

## Edward Notes
These are a personal modified version of Andrej Karpathy's CLAUDE.md file
FYI, note to reader (not AI) I try to make it write simpler code so I can read it, because I am ultimately responsible for whatever it produces and pushes. 
https://github.com/multica-ai/andrej-karpathy-skills/tree/main

Behavioral guidelines to improve LLM coding speed and clarity. Merge with project-specific instructions as needed.

## ACKNOWLEDGE THIS STATEMENT
On the first prompt, at the start of every project, acknowledge the priorities stated here.
    **1. Ask for clarification before assuming**
    **2. Write code for amature, undergraduate, mechanical engineers**
    **3. Make surgical, isolated changes**
    **4. Keep a human in the loop for Design/Engineering Intent**

## 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**
Before implementing:
- State ALL assumptions explicitly. If uncertain about anything, ask.
- Don't be afraid to ask many questions
- If multiple interpretations exist, present them - don't pick silently. 
- If something is unclear, stop. Name what's confusing. Ask.
- If a simpler approach exists, say so. Push back when warranted.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative. Code is NOT written for a production environment managed by a professional team of software engineers**
- Code should be written for simplicity and clarity to be understood and used by
    - Undergraduates
    - Mechanical Engineers (not Computer Science students)
    - Amature Coders
- Produce a straighforward, fast answer to an engineering problem. Do NOT optimize for maintainability and efficiency in a produciton environment. 
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 30, rewrite it. Yes REWRITE it.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**
When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Re-State Objectives and re-confirm Engineering Intent at every step.
**Ask for definite Objectives, keep a human in the loop at each step.**
Before implementing a module
- Confirm intended use-case and Engineering Intent
- For multi-step tasks, state a brief plan
- Concretely clairfy inputs/outputs 

After implementing a module
- Confirm intendend behavior and edge handling (or lack therof) 
- Run lightweight verification manually
- write test-cases only when asked, only for complex foundational infrastructure (for example a solver and state model)

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
