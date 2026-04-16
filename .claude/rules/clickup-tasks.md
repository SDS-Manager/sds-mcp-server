## ClickUp Task Management

When creating ClickUp tasks (e.g., to track work, bugs, or features), use the MCP ClickUp integration tools. These are deferred tools with the prefix `mcp__claude_ai_ClickUp__`. You MUST fetch their schemas via ToolSearch before calling them (e.g., `ToolSearch("select:mcp__claude_ai_ClickUp__clickup_create_task")`).

**NOTE**: The ClickUp MCP tools are only available when running Claude Code through the **VS Code extension** (they are provided by the Claude.ai managed MCP integration). If these tools are not in your deferred tools list, you are likely running outside VS Code — inform the user that ClickUp task creation requires a VS Code Claude Code session.

### Two Task Creation Modes

**Mode 1 — Post-coding task (skip interview):** When a task is created to document work already done by Claude (code written, PR exists), skip the RIRE scoring, interview process, and acceptance criteria. Just create the task with a clear description of what was done, link to the PR, and files changed. Prefix title with `CLAUDE CODE:` and set status to `ADD NEW TASKS HERE`.

**Mode 2 — Request-phase task (full process):** When someone is requesting NEW work that hasn't started yet, follow the full process below. This is the default. Do NOT prefix the title with `CLAUDE CODE:` — that prefix is only for tasks documenting Claude-written code.

### Request-Phase Task Creation Process — MANDATORY

Before creating a request-phase development task, you MUST follow the guidelines in `CLICKUP_TASK_GUIDELINES.md`. The process is:

1. **Read `CLICKUP_TASK_GUIDELINES.md`** to understand the required fields and quality standards.
2. **Interview the user** — do NOT create the task from a one-liner. Ask clarifying questions until you have at minimum:
   - **Problem statement**: Who is affected, what's the issue, what's the impact
   - **Desired outcome**: What the end result should look like, with examples
   - **Acceptance criteria**: At least 3 specific, testable criteria
   - **Scope**: What is in scope AND what is explicitly out of scope
   - **Module**: Which module from the ClickUp dropdown (see custom fields below)
   - **RIRE ratings**: Reach (1–5), Impact (1–5), Revenue (1–5), Effort (1–5)
   - **Priority**: Auto-proposed by Claude based on RIRE score (see mapping below), user confirms or overrides
3. **Flag database/package changes** — if the task will likely need new DB columns or new packages, call this out prominently at the top of the description with `⚠️ DATABASE CHANGES REQUIRED` or `⚠️ NEW PACKAGES REQUIRED`.
4. **Show the user a preview** of the task (title + full description) and get confirmation before creating it.
5. **Create the task** using the structured format from the guidelines.

### Interviewing Rules

- If the user gives a vague request like "fix the SDS page" or "add validation", do NOT proceed. Ask: what specifically is broken? which page? which fields need validation? what are the rules?
- Keep asking until a stranger could pick up the task and understand what to build.
- Suggest acceptance criteria based on what you know about the codebase — the user can confirm or adjust.
- If the user mentions something that sounds like multiple tasks, suggest splitting them.

### Priority Auto-Proposal

After collecting RIRE ratings, calculate the score and **propose** a priority level. The user confirms or overrides. Exception: if the user explicitly says "production bug" or "deal blocked", use P0/P1 regardless of score.

| RIRE Score | Proposed Priority |
|------------|-------------------|
| 15–25 | P1 - BIG DEAL BLOCKED (or P0 if production bug) |
| 8–15 | P2 - CUSTOMER ESCALATION |
| 3–8 | P3 - NICE VALUE |
| 1–3 | P4 - LOW VALUE |
| < 1 | P6 - IDEA FOR SOMEDAY |

Always show the user: "Based on your RIRE score of X, I'd suggest **PY**. Does that look right, or would you like to override?"

### Task Title Convention

**Two rules depending on mode:**
- **Request-phase tasks** (new work, no code yet): Do NOT prefix with `CLAUDE CODE:`. Just use a concise description with action verbs (Add, Fix, Update, Remove, Implement, Refactor). Example: `Fix mobile Tasks menu to show submenu instead of auto-navigating`
- **Post-coding tasks** (documenting work done by Claude with a PR): Prefix with `CLAUDE CODE:`. Example: `CLAUDE CODE: Add Norwegian translations for dashboard V2`

### Task Description Format

Use `markdown_description` with this structure:

```markdown
## Problem
[Who is affected and what's the issue — include impact/business context]

## Desired Outcome
[What the end result should look like — with specific examples or user flows]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
- [ ] ...

## Scope
**In scope:** [specific changes to deliver]
**Out of scope:** [related things NOT part of this task]

## Affected Area
[Frontend / Backend / Full stack / Admin panel / etc.]

## Dependencies & Blockers
[Prerequisites, related tasks, external dependencies — or "None"]

## Edge Cases & Risks
[What could go wrong, performance concerns, permission issues]

## Technical Context
[Relevant endpoints, tables, components, related PRs/tasks — if known]
```

### How to Create a Task (Technical Steps)

**Board:** [SDS Manager Dev Project](https://app.clickup.com/90152360809/v/b/6-901521246467-2)

1. **Fetch the tool schema first**: use ToolSearch with query `select:mcp__claude_ai_ClickUp__clickup_create_task` to load the tool definition
2. **Always use list `901521246467`** (SDS Manager Dev Project). Do not ask the user which list — this is the only list for dev tasks.
3. Use `mcp__claude_ai_ClickUp__clickup_create_task` with:
   - `name`: For request-phase tasks, NO prefix — e.g., `"Fix login redirect bug"`. For post-coding tasks with Claude-written code, prefix with `CLAUDE CODE:`
   - `list_id`: `"901521246467"`
   - `status`: `"ADD NEW TASKS HERE"` — always set this so tasks land in the triage column
   - `markdown_description`: Full structured description per the format above
   - `assignees`: Use `mcp__claude_ai_ClickUp__clickup_resolve_assignees` if you need to convert emails/usernames to IDs
   - `custom_fields`: **MUST** include RIRE scores, Module, and Priority. Use these field IDs:

     ```json
     "custom_fields": [
       {"id": "aa90401a-2d94-43dc-8ea2-23846be9aabb", "value": <Reach 1-5>},
       {"id": "54644afa-57f9-407c-bf80-72f4dbdf9a3c", "value": <Impact 1-5>},
       {"id": "28eaa87d-c80a-4199-a20e-80d3ad247d6e", "value": <Revenue 1-5>},
       {"id": "de12716d-c559-4844-9f75-9d2266006dac", "value": <Effort 1-5>},
       {"id": "7f5e3124-85dc-4afe-a416-48b2a2071ba6", "value": "<Module option ID>"},
       {"id": "0fc2af06-ebc8-472c-84f3-8e1aece6396d", "value": "<Priority option ID>"}
     ]
     ```

     **Module option IDs:**
     | Module | Option ID |
     |--------|-----------|
     | Inventory Manager - Improvements | `d5fc41c5-27b6-42fd-9df8-181b85d04dd6` |
     | Inventory Manager - UX | `2d69e691-8e9f-4107-bbf5-8cfd8168c4ce` |
     | Inventory Manager - New feature | `15cbb1ac-6b04-42e4-998e-81f9ada5b7d5` |
     | Inventory Manager - Bugs | `9e2b95ae-43bf-4eb4-832f-ecae11f57b2a` |
     | APP (progressive web app) | `de881275-dc4e-4e06-a19b-75f1ac126362` |
     | APP (FLUTTER) | `6ad14751-0108-455e-9463-9384e9547aa7` |
     | Extraction pipeline | `fb592eeb-8ec7-4474-82a7-561a946df893` |
     | Website & Landing pages | `72624edd-9b17-4328-98b8-fc64b8591a94` |
     | Website Discovery & Search | `e8a48dd1-8bd9-43ef-94fd-ca73b786564b` |
     | FAQ | `54e0a4f2-38d7-4207-ae03-9da454844c69` |
     | Authoring | `62666ed0-0a12-45a6-98c1-9b83de7281cc` |
     | SDS Admin - CRM/MSG | `be6b294a-a344-4068-a110-e4f76c430242` |
     | SDS Admin - Harvesting & Quality support tools | `72774641-c51d-4374-852f-981ec7f549a8` |
     | SDS Admin - Misc | `4e2d1ecc-5c63-459b-9580-995da72395cf` |
     | SDS Admin - SDS Validation | `55c03d32-87c2-4730-9e65-a447100e9e44` |
     | SDS Distribution | `fa77e261-c6e7-490e-b00a-54714e28febf` |
     | Demo API | `86d86efa-8591-4290-837a-9b4d03b47c0a` |
     | NON-CODING TASK | `e35aa861-e9e0-4f48-b694-323c2f991bb0` |
     | Other | `12806006-ee36-4cbd-ac59-f2de82e69d4a` |

     **Priority option IDs:**
     | Priority | Option ID |
     |----------|-----------|
     | P0 - PRODUCTION BUG | `bac03c54-e4a9-4f55-8f94-210f6cbdd263` |
     | P1 - BIG DEAL BLOCKED | `13b43a02-b610-45a9-897e-90c5c23b8933` |
     | P2 - CUSTOMER ESCALATION | `33b40e79-7c31-426e-b189-9a5b7aa080de` |
     | P3 - NICE VALUE | `15ffa755-7103-4859-ac32-7d34ad2c0dd6` |
     | P4 - LOW VALUE | `ba2cedc3-fb1b-4d65-8677-98bb096e61ca` |
     | P6 - IDEA FOR SOMEDAY | `d79cb980-fdbb-44bf-919f-4f9525316f9c` |
     | Not sure | `00a7852d-165f-4377-8a07-c4841e112fa4` |

4. The **SCORE (RIRE)** field (`04cd210c-b0f3-464f-90c5-1ff10aaf9898`) is a formula field — do NOT set it manually. ClickUp auto-calculates it from the four RIRE inputs.
5. Other useful ClickUp tools (all prefixed with `mcp__claude_ai_ClickUp__`):
   - `clickup_search` — find existing tasks
   - `clickup_update_task` — update status, assignees, etc.
   - `clickup_create_task_comment` — add comments to existing tasks
   - `clickup_get_task` — get task details
