---
name: create-pr
description: Creates a GitHub pull request from the current branch to develop (or main for hotfixes). Follows the SDS MCP Server git workflow rules — pushes the branch if needed, derives the ClickUp task ID from the branch name, and uses the standard PR description template. Use when the user says "create a PR", "open a pull request", or "submit this branch".
argument-hint: [optional: custom PR title override]
---

You are creating a GitHub pull request for this repository following the rules in `.claude/rules/git-workflow.md`.

## Gathered Context

Current branch and recent commits:
```
!`git rev-parse --abbrev-ref HEAD`
```

Commits on this branch not yet in develop:
```
!`git log origin/develop..HEAD --oneline 2>/dev/null || git log develop..HEAD --oneline 2>/dev/null`
```

Files changed vs develop:
```
!`git diff origin/develop...HEAD --stat 2>/dev/null || git diff develop...HEAD --stat 2>/dev/null`
```

Remote origin:
```
!`git remote get-url origin`
```

Stored GitHub credentials (for API auth):
```
!`git credential fill <<< $'protocol=https\nhost=github.com\n' 2>/dev/null | grep password | cut -d= -f2`
```

Branch push status (empty = not yet pushed):
```
!`git ls-remote --heads origin $(git rev-parse --abbrev-ref HEAD) 2>/dev/null`
```

---

## Instructions

Follow these steps exactly:

### Step 1 — Validate the branch

- Confirm the current branch is NOT `develop`, `rc`, or `main`. If it is, stop and tell the user PRs must come from a feature branch.
- Determine the target base branch:
  - If the branch starts with `hotfix/` → target is **`main`**
  - Otherwise → target is **`develop`**

### Step 2 — Derive the ClickUp task ID and PR title

Extract the ClickUp task ID from the branch name:
- `feature/86c8wfknn` → task ID is `86c8wfknn`
- `bugfix/KJtjywtf` → task ID is `KJtjywtf`

Title format: `{scope}: {imperative description}` — e.g., `tools: add get_sds_by_id MCP tool`

If `$ARGUMENTS` was provided, use that as the title instead.

If no task ID can be derived, stop and ask the user for the ClickUp task ID.

### Step 3 — Check commit count

The git workflow rule is **1 PR = 1 commit**.

If there are 2 or more commits, warn the user:

> "This branch has N commits. The workflow requires squashing to 1 commit before opening a PR (`git rebase -i origin/develop`). Proceed anyway or squash first?"

Wait for their confirmation.

### Step 4 — Push the branch if needed

```bash
git push origin {current-branch-name}
```

### Step 5 — Build the PR description

```
## ClickUp Task
{task-id} — https://app.clickup.com/t/{task-id}

## Description
[What changed and why]

## New / Changed Tools
[List any MCP tools added or modified — include tool name and brief description, or "None"]

## Root Cause
[Only for `bugfix/` or `hotfix/` branches. Omit for feature/chore branches.]

## Migration / CLI steps
[Any required env var changes or deployment steps, or "None"]

## QA Testing
[How to verify the tool works — include example tool calls or test prompts for the AI client]
```

### Step 6 — Create the PR via GitHub CLI

```bash
gh pr create \
  --title "{pr-title}" \
  --base "{target-branch}" \
  --body "$(cat <<'EOF'
{pr-description}
EOF
)"
```

Report the PR URL on success, or the full error message on failure.

### Step 7 — Confirm

Tell the user the PR URL, number, and base branch.

### Step 8 — Post a comment on the ClickUp task

After the PR is created, post a comment using `mcp__claude_ai_ClickUp__clickup_create_task_comment`. Fetch the schema first via `ToolSearch("select:mcp__claude_ai_ClickUp__clickup_create_task_comment")`.

```
## PR: {pr-title}
**Link:** {pr-html-url}

---

{pr-description-body-without-clickup-task-section}
```

If ClickUp MCP tools are unavailable, skip and inform the user.
