## 2026-10-22 — Reusable Herdr tools live in skill-issue

**Decision:** Keep reusable Herdr plugin code and its tests under `tools/herdr/`
in this repository, with one folder per tool and an index of existing candidates.
Start with `tools/herdr/project-anchors`, a self-contained Linux
plugin for inert project placeholders. Host services, live enrollment records,
and machine-specific deployment evidence remain in the host configuration repo.
Do not add a generic skill that duplicates Herdr's own CLI skill.

**Evidence:** The placeholder passed the isolated real-server gate and a live
session smoke test before extraction. Its close recovery does not preserve workers
after a workspace close. Herdr restart was tested; a full machine reboot was not.
The `serg.project-anchors` plugin ID stays stable so installed state stays attached
to the same plugin when its source location changes.

**Reopen when:** A reusable Herdr workflow needs agent instructions beyond the
built-in skill, or Herdr provides a native protected-tab feature.
