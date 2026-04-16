# Git & PR Workflow

## Branch Naming

- Format: `{prefix}/{clickup-id}` — e.g., `feature/KJtjywtf`, `bugfix/86c8xu8p0`, `hotfix/86c90bw7u`
- Prefixes: `feature/`, `bugfix/`, `hotfix/`, `chore/`
- The ClickUp task ID comes from the card URL: `https://app.clickup.com/t/{ID}`
- **Do NOT** use generic names like `feature/fix` or `bugfix/issue` — the ClickUp ID is mandatory.

### Branch naming examples

| Prefix | ClickUp URL | Correct branch name |
|--------|-------------|---------------------|
| `feature/` | `https://app.clickup.com/t/KJtjywtf` | `feature/KJtjywtf` |
| `bugfix/` | `https://app.clickup.com/t/86c8xu8p0` | `bugfix/86c8xu8p0` |
| `hotfix/` | `https://app.clickup.com/t/86c90bw7u` | `hotfix/86c90bw7u` |

## Commit Rules

- **1 PR = 1 commit.** If there are 2+ commits, squash with `git rebase -i` before opening the PR.
- Write clear commit messages describing what and why.
- Format: `<scope>: <imperative description>` — e.g., `tools: add search_sds tool with Redis caching`

## Pull Request Rules

- **Target branch:** `develop` (feature/bugfix) or `main` (hotfix)
- PR description **must** include:
  - **ClickUp task ID and full link** — e.g.: `ClickUp: 86c8xu8p0 — https://app.clickup.com/t/86c8xu8p0`
  - Detailed description of the change
  - Any new MCP tools added or changed

### PR description template

```
## ClickUp Task
<task-id> — https://app.clickup.com/t/<task-id>

## Description
<Detailed explanation of what changed and why>

## New / Changed Tools
<List any MCP tools added or modified, or "None">

## Migration / CLI steps
<List any required manual steps, or "None">

## QA Testing
<Steps to verify MCP tool responses — include example tool calls if applicable>
```

> The ClickUp task ID is **required** in every PR. Do not open a PR without it.

## Branch Flow

```
develop  →  rc  →  main
(staging)   (RC)   (production)
```

## Environments

| Branch    | Environment | Notes |
|-----------|-------------|-------|
| `develop` | Staging     | Connected to staging backend |
| `rc`      | RC          | Connected to production backend |
| `main`    | Production  | Live MCP server |
