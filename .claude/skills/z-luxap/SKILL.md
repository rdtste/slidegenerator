---
name: z-luxap
description: Zero-Loss UX Audit Protocol — comprehensive UX/UI audit with parallel analysis agents. Run this after major UI changes or periodically to catch UX regressions. Triggers on "/z-luxap", "UX audit", "UX review", or "run Z-LUXAP". Produces actionable findings with guaranteed zero functionality loss.

---

# Z-LUXAP — Zero-Loss UX Audit Protocol

You are the executor of the Z-LUXAP protocol. Your core, unbreakable directive is **ZERO FUNCTIONALITY LOSS** — every suggestion must preserve all existing functionality.

## Execution Strategy

This protocol runs in 4 phases. Phases 2's four parts run as **parallel agents** for speed.

```
Phase 0: Context Ingestion (you, from codebase)
Phase 1: Feature-Function Mapping → [T1] Matrix (you, sequential — foundation for everything)
Phase 2: Generative Audit (4 parallel agents, each gets [T1])
  ├─ Agent A: User Flow & Journey Analysis
  ├─ Agent B: Screen-by-Screen Deep Dive
  ├─ Agent C: Cross-Platform & Accessibility
  └─ Agent D: Performance & Scalability
Phase 3: Red-Team Self-Correction (you, synthesize agent results)
Phase 4: Final Report & Sign-Off
```

## Phase 0: Context Ingestion

State: **"Z-LUXAP Initialized. Core Directive: Zero Functionality Loss. Ingesting codebase context."**

Auto-detect from the codebase (do NOT ask the user):

1. **Read CLAUDE.md** for architecture overview
2. **Read the frontend template** (`frontend/src/app/app.html`) — every button, input, link, modal
3. **Read feature components** — scan `frontend/src/app/features/*/` for all component templates (`.html` files)
4. **Read the main component** (`frontend/src/app/app.ts`) — all methods, signals, state
5. **Read ChatState** (`frontend/src/app/core/services/chat.ts`) — all state signals
6. **Read models** (`frontend/src/app/core/models.ts`) — all data types
7. **Read styles** (`frontend/src/app/app.scss`) — layout patterns, responsive breakpoints

From this, build a structured understanding of:
- Application name, purpose, target audience
- All screens/steps (the wizard flow)
- Every interactive element (buttons, inputs, selects, modals, links)
- All user-facing features and their triggers
- Known UI patterns (responsive breakpoints, accessibility features)

## Phase 1: Feature-Function Mapping

Create table **[T1] Functionality-UI Mapping Matrix** as markdown:

| Function_ID | Function_Description | Mapped_UI_Elements | Screen/Step |
|-------------|---------------------|--------------------|-------------|
| F01 | User starts new presentation | "Neue Praesentation" button in header | All steps |
| F02 | ... | ... | ... |

**Be exhaustive.** Every button, every link, every form interaction, every keyboard shortcut, every modal trigger must appear. Include:
- Direct actions (button clicks)
- State changes (signal updates)
- Navigation (step transitions)
- Conditional UI (elements that appear/disappear based on state)
- Implicit functions (auto-save, auto-load, retry logic)

After creating [T1], state: **"[T1] locked. This matrix is the single source of truth for Zero Functionality Loss validation."**

## Phase 2: Parallel Audit Agents

Launch **4 agents in a single message** using the Agent tool. Each agent gets:
1. The complete [T1] matrix (copy it into each prompt)
2. Instructions to read the relevant frontend files themselves
3. The Z-LUXAP validation requirement

### Agent A: User Flow & Journey Analysis

```
prompt: |
  You are running Part I of a Z-LUXAP UX audit for the Slidegenerator app.
  
  YOUR TASK: Analyze all user flows — both happy paths and unhappy paths.
  
  CONTEXT: Read these files to understand the UI:
  - frontend/src/app/app.html (main template, all steps)
  - frontend/src/app/app.ts (component logic)
  - frontend/src/app/features/chat/chat.html and chat.ts
  - frontend/src/app/features/preview/preview.html and preview.ts
  - frontend/src/app/features/export-panel/export-panel.html and export-panel.ts
  - frontend/src/app/features/template-management/template-management.html
  - frontend/src/app/features/settings/settings.html
  
  [T1] FUNCTIONALITY MATRIX:
  {paste the full [T1] table here}
  
  ANALYZE:
  1. Map primary user flows for core tasks:
     - Creating a presentation via chat
     - Creating from notes
     - Importing markdown + pimp
     - Reviewing and refining slides
     - Exporting (V1 and V2)
     - Managing templates
  2. Map UNHAPPY paths:
     - What happens with empty input?
     - Network errors during generation?
     - LLM timeouts?
     - Invalid markdown import?
     - Template upload failures?
     - Where are dead ends?
  3. Identify friction points and propose optimizations.
  
  FORMAT each finding as:
  - **Issue:** [description]
  - **Principle:** [UX principle violated]
  - **Suggestion:** [specific, actionable fix with file:line references]
  - **Z-LUXAP Validation:** "Preserves [Function_ID(s)]"
  
  Be specific — reference actual code, actual element names, actual signal names.
```

### Agent B: Screen-by-Screen Deep Dive

```
prompt: |
  You are running Part II of a Z-LUXAP UX audit for the Slidegenerator app.
  
  YOUR TASK: Deep-dive every screen/step for layout, clarity, consistency, and microinteractions.
  
  CONTEXT: Read these files:
  - frontend/src/app/app.html and app.scss (main layout + styles)
  - frontend/src/app/app.ts (all signals, methods)
  - All feature component .html and .scss files in frontend/src/app/features/
  - frontend/src/styles.scss (global styles, CSS variables)
  
  [T1] FUNCTIONALITY MATRIX:
  {paste the full [T1] table here}
  
  FOR EACH SCREEN (Step 1-4, modals, overlays):
  1. **Layout & Hierarchy** — Is visual hierarchy clear? Any alignment issues?
  2. **Clarity & Simplicity** — Are all elements understandable? Any jargon?
  3. **Consistency** — Same patterns used everywhere? Font sizes, spacing, colors consistent?
  4. **Microinteractions & Feedback** — Loading states, success/error feedback, hover states, transitions?
  5. **Content & Copywriting** — Is German text clear, concise? Any untranslated strings?
  
  FORMAT each finding as:
  - **Issue:** [description with file:line reference]
  - **Principle:** [UX principle violated]
  - **Suggestion:** [specific fix — include CSS changes, HTML restructuring, etc.]
  - **Z-LUXAP Validation:** "Preserves [Function_ID(s)]"
```

### Agent C: Cross-Platform & Accessibility

```
prompt: |
  You are running Part III of a Z-LUXAP UX audit for the Slidegenerator app.
  
  YOUR TASK: Audit responsive behavior and accessibility.
  
  CONTEXT: Read these files:
  - frontend/src/app/app.scss (look for @media queries, responsive patterns)
  - frontend/src/app/app.html (semantic HTML, ARIA attributes)
  - All feature component .html and .scss files
  - frontend/src/styles.scss (CSS variables, global resets)
  
  [T1] FUNCTIONALITY MATRIX:
  {paste the full [T1] table here}
  
  ANALYZE:
  1. **Responsive Design:**
     - How does each step adapt at 768px breakpoint?
     - Are there elements that break on mobile?
     - Touch targets (min 44px)?
     - Grid layouts that might overflow?
  2. **Accessibility (WCAG 2.1 AA):**
     - Color contrast (check CSS variable values)
     - Keyboard navigation (tab order, focus styles)
     - Screen reader: ARIA labels, roles, live regions
     - Form labels and error announcements
     - Focus management after dynamic content changes (modals, step transitions)
  3. **Missing semantic HTML** — divs that should be buttons, missing headings hierarchy, etc.
  
  FORMAT each finding as:
  - **Issue:** [description with file:line reference]
  - **Principle:** [WCAG criterion or responsive best practice]
  - **Suggestion:** [specific fix]
  - **Z-LUXAP Validation:** "Preserves [Function_ID(s)]"
```

### Agent D: Performance & Scalability

```
prompt: |
  You are running Part IV of a Z-LUXAP UX audit for the Slidegenerator app.
  
  YOUR TASK: Audit perceived performance and design scalability.
  
  CONTEXT: Read these files:
  - frontend/src/app/app.ts and app.html (loading states, async patterns)
  - frontend/src/app/core/services/api.ts (API calls, error handling)
  - frontend/src/app/core/services/chat.ts (state management)
  - frontend/src/app/features/export-panel/ (SSE progress tracking)
  - frontend/src/app/features/chat/ (chat interaction patterns)
  
  [T1] FUNCTIONALITY MATRIX:
  {paste the full [T1] table here}
  
  ANALYZE:
  1. **Perceived Performance:**
     - Are there skeleton loaders or loading indicators for all async operations?
     - Optimistic UI updates — where could they be applied?
     - Are long-running operations (LLM calls) properly communicated to the user?
     - Are there operations that block the UI unnecessarily?
  2. **State Management:**
     - Are signals used efficiently? Any unnecessary re-renders?
     - Memory leaks (subscriptions not cleaned up)?
     - State consistency after errors?
  3. **Design Scalability:**
     - Can new wizard steps be added without refactoring?
     - Can new slide types / features be added to existing screens?
     - Are components properly encapsulated?
     - Will the current layout handle 50+ slides in the preview panel?
  
  FORMAT each finding as:
  - **Issue:** [description with file:line reference]
  - **Principle:** [performance/scalability principle]
  - **Suggestion:** [specific fix]
  - **Z-LUXAP Validation:** "Preserves [Function_ID(s)]"
```

## Phase 3: Red-Team Self-Correction

After all 4 agents return, state: **"Initiating Phase 3: Red-Team Self-Correction Mode."**

Synthesize all agent results into a single report. Then critically challenge it:

1. "Did any agent's suggestion conflict with another agent's findings?"
2. "Looking at [T1], is there any function whose trigger becomes less obvious from the combined suggestions?"
3. "Are suggestions feasible for the team? Are any over-engineered?"
4. "Could any suggestion negatively impact a specific user flow?"
5. "Is there a simpler solution to any identified problem?"

If the critique reveals issues, revise the affected findings. Mark revised items with **[REVISED after Red-Team]**.

## Phase 4: Final Report

Produce the final report structured as:

1. **Executive Summary** — Top 5 most critical findings
2. **Part I: User Flows** (from Agent A)
3. **Part II: Screen Deep-Dive** (from Agent B)
4. **Part III: Accessibility** (from Agent C)
5. **Part IV: Performance** (from Agent D)
6. **[T1] Validation Checklist** — Confirm every Function_ID is preserved
7. **Implementation Priority** — Ranked list: quick wins, medium effort, major refactors

End with: **"Z-LUXAP execution complete. The final report has been validated against the Zero Functionality Loss directive. All functions have been preserved. Protocol terminated."**

## Important Notes

- Do NOT make any code changes during the audit. This is analysis only.
- Reference specific files and line numbers in every finding.
- Each suggestion must include the Z-LUXAP Validation line.
- If the user provides a focus area (e.g., "just Step 3"), still run the full protocol but weight analysis toward that area.
- The [T1] matrix must be complete BEFORE launching agents — it is their shared contract.
