# Scoring: exp-2026-11-22-demo-agent

Scored on 2026-11-22 by Fatuma Yattani against answer key demo-repo-agent-v1,
using the scoring rule committed before the run (unchanged).

| Question | Target | Result |
| --- | --- | --- |
| q1 transfer fee | v2 | correct |
| q1 transfer fee | v1 | correct |
| q2 phone check | v2 | correct |
| q2 phone check | v1 | incomplete: omits "send_payment raises ValueError if validation fails"; no stale facts |
| q3 API version | v2 | correct |
| q3 API version | v1 | correct |
| q4 fee on 500 | v2 | correct |
| q4 fee on 500 | v1 | correct |

Totals: 7 of 8 correct, 1 incomplete, 0 stating stale facts, 0 declined.
Searches: 8 (one per question); top-ranked result was the wrong version in 4.

Notes:
- Agent model was command-a-03-2025. Command A+ was capped (see the attempt2 records).
- "Stale references: none" holds by construction, because only Git-validated
  evidence reaches the model. Answer text against the answer key is the real test.
- Embed scores varied slightly between stages for the same query
  (0.5622 vs 0.5629), so single-run scores should not be reported as exact.
