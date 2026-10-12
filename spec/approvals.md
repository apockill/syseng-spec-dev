# Approvals

*Kept by hand until the toolkit exists (DR-5).* Each row records your approval of one spec item. The fingerprint is a SHA-256 hash, first 12 hex characters, of the item's text with whitespace normalized: the requirement statement, or for a decision record the whole record without its 🔒 marker. When the text changes, the fingerprint stops matching and the item counts as unapproved again (CHECK-14).

| Item | Approved | Your words | Fingerprint | Approved text |
|---|---|---|---|---|
| SYS-4 | 2026-10-11, in chat (round 5) | SGTM. | `e5596f1f8221` | The toolkit shall read every project-specific setting from the host repository. |
| SYS-5 | 2026-10-11, in chat (round 5) | Clarify what 'installs' means. If it means 'sets up the spec/ file and other things upon 'initiating a project into this system', SGTM. | `1e779de31649` | The toolkit shall set up a host repository for use in one step. |
| SYS-21 | 2026-10-11, in chat (round 5) | SGTM (additions captured as CHANGE-10 to CHANGE-12) | `bf0edf0a29ee` | The toolkit shall find requirements and verification items that are ambiguous, unverifiable or too weak to catch a wrong implementation. |
| SYS-23 | 2026-10-11, in chat (round 5) | SGTM | `ef3a70ef0281` | The toolkit shall be adoptable by a repository that already contains code and tests. |
| DR-2 | 2026-10-11, in chat (round 5) | SGTM. | `656ec1f2e9dd` | spec files are YAML. To make several edits, an agent writes them as one small YAML document and pipes it into a single CLI command, usually as a heredoc. That avoids passing each field as a command-line argument. |
| DR-17 | 2026-10-11, in chat (round 7) | LGTM | `5112b51aa963` | checks come from fresh-context auditors that didn't author the change. One auditor examines only the tests and verification items that the change modified or deleted. |
