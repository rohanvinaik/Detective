# Reference reconciliation — 2026-09-07

The three manifest drifts were compared to the exact historical files matching their
recorded SHA-256 hashes. The hashes were refreshed after reading those differences.
This reconciles source identity; it is not a new proof or independent replication of
every historical implementation claim in the referenced documents.

| Reference | Recorded version | Reviewed change and relevance |
|---|---|---|
| ARC glossary | `04b1736ad27d094178bfa8b8ee84e258ff0efc36` | Adds the execution/story distinction, kernel/flipbook, frame-of-frames and learning from wins. Preserves the glossary entry structure and proposal/admissibility separation Detective cites. |
| Parsimony advisory | `b3986f66b79a21263ccd2726f1cfcb9ec6cc241f` | Changes its status from pre-build to implemented and names the wiring. The cited no-write, advisory/proof separation remains intact. |
| Negative specification | `59919303349454bde6336cae3613df34a57100c9` | Records recursive dataclass construction and the explicit opaque-fixture design boundary, supersedes monoid generation with footprint adequacy, distinguishes argument/state perturbations from output recodings, and records the earlier Lean axiom audit. |

The complete comparison is in `/tmp/detective-reference-diffs.txt`. The reference checker
now resolves all 12 recorded priors. Its six historical unverified external citations
remain marked unverified; their status was not changed or silently treated as source verification.
No publication or external submission is part of this repair.
