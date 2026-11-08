# Task WB-VIDEO-001 — Bootstrap the Vidova → Jianying → QA pipeline

- Task ID: WB-VIDEO-001
- Status: ready
- Priority: high
- Scope: read-only discovery plus a tiny non-destructive capability test only
- Repository: swdscsc/yaodao-agent
- Target workflow: AI director → Vidova generation → asset validation → Jianying/CapCut editing → export → automated QA

## Goal

Establish a reliable GitHub-based handoff with ChatGPT, then investigate whether the local Vidova app and Jianying (CapCut China desktop) can be orchestrated into one repeatable video-production pipeline.

## Step 1 — Establish GitHub handoff

1. Read `docs/ai-collaboration/README.md`.
2. Confirm this repository remote, current branch, authentication, and push access.
3. Fetch/pull before making changes.
4. Read this inbox task and write progress only to the designated outbox/status paths.
5. Never commit credentials, tokens, private media, or large generated video files.

## Step 2 — Read-only local discovery

On the Windows machine, inspect and report:

- Vidova process, version, install path, local listening port, and whether the previously observed `127.0.0.1:17373` service still exists.
- The actual MCP endpoint and actual tool list/schema, if discoverable.
- Whether Vidova can create a test generation task, poll status, and return a local result path. Do not spend paid credits; if unclear whether a test consumes credits, ask first.
- Jianying/CapCut process, version, install path, and available automation methods.
- Whether Jianying can be controlled through a documented interface, UI Automation, or desktop control.
- Whether a harmless empty test project can be created without touching existing projects.

Do not infer that an endpoint or tool works merely because a port is open. Verify each capability separately.

## Step 3 — Design the handoff contract

Propose a JSON manifest for each shot with at least:

```json
{
  "shot_id": "S001",
  "purpose": "storyboard purpose",
  "prompt": "generation prompt",
  "source_type": "vidova|local|stock|manual",
  "asset_path": null,
  "duration_seconds": null,
  "width": null,
  "height": null,
  "fps": null,
  "generation_status": "pending",
  "qa_status": "not_checked",
  "notes": []
}
```

Propose a task state model and bounded retry policy. Keep all machine-specific absolute paths in local config, not in public GitHub files.

## Step 4 — Report

Create:

- `docs/ai-collaboration/outbox/WB-VIDEO-001-report.md`
- `docs/ai-collaboration/status/pipeline-status.json`

The report must distinguish:
- confirmed working;
- detected but not tested;
- unavailable;
- blocked by permissions;
- not attempted.

Include exact app versions, test evidence, safe command snippets, relevant log excerpts with secrets redacted, and next-step recommendations.

## Acceptance criteria

This task is complete only when:
1. WorkBuddy can read this task from GitHub.
2. WorkBuddy can commit and push a report.
3. Vidova and Jianying capabilities are individually documented with evidence.
4. No existing user project or source asset was modified.
5. No paid service or credit was used without approval.

After pushing, report the commit SHA and exact GitHub links. Then stop and wait for review.
