## 2026-10-22 — Reusable Herdr tools live in skill-issue

**Decision:** Keep reusable Herdr plugin code and its tests under `tools/herdr/`
in this repository, with one folder per tool. Publish project placeholders,
state ages, undo, sharing, cache countdown, and quota display as separate packages.
The first publication leaves existing host integrations on their current copies.
Host services, live enrollment records,
and machine-specific deployment evidence remain in the host configuration repo.
Do not add a generic skill that duplicates Herdr's own CLI skill.

**Evidence:** The placeholder passed the isolated real-server gate and a live
session smoke test before extraction. Its close recovery does not preserve workers
after a workspace close. Herdr restart was tested; a full machine reboot was not.
Plugin IDs stay stable. State-age 0.2 deliberately uses per-socket storage;
sharing 0.3 uses random control passwords. A later host migration must stop any
old refresher through its original owner before changing the source link. Package
publication does not authorize a live migration or public terminal exposure.

**Reopen when:** A reusable Herdr workflow needs agent instructions beyond the
built-in skill, or Herdr provides a native protected-tab feature.
