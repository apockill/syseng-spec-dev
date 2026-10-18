<!-- syseng: written by `spec init`, which rewrites everything up to the closing marker -->
## Requirements and design decisions

This repository keeps its needs, requirements, verification items and design decisions in `spec/`, managed
with the syseng toolkit. For every change, follow the `syseng` skill:

- open a change with `.syseng/spec change start "<what was asked>"`;
- change the spec only with `.syseng/spec edit`, never by editing files under `spec/`;
- run `.syseng/spec check` before reporting a change as done.

`.syseng/spec status` shows what's open and what awaits the engineer.
<!-- /syseng -->
