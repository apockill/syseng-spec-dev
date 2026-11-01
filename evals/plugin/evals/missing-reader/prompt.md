---
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

This repository has a spec/ directory with spec/toolkit.yaml. Our test tool is called nodecheck and writes its results as a binary log. `spec results add` says it has no reader for that format. Can you sort this out so our results get into the spec?
