# Scoring: exp-2026-11-22-demo-agent-nofilter

Scored on 2026-11-22 by Fatuma Yattani against answer key demo-repo-agent-v1,
using the same scoring rule as exp-2026-11-22-demo-agent (unchanged).

Configuration 7: the agent without the Git filter. Evidence was labelled with
the revisions it exists in, and the prompts named the target revision and commit.

| Question | Target | Result |
| --- | --- | --- |
| q1 transfer fee | v2 | correct |
| q1 transfer fee | v1 | correct |
| q2 phone check | v2 | correct |
| q2 phone check | v1 | correct |
| q3 API version | v2 | correct |
| q3 API version | v1 | correct |
| q4 fee on 500 | v2 | correct |
| q4 fee on 500 | v1 | correct |

Totals: 8 of 8 correct, 0 incomplete, 0 stating wrong-version facts, 0 declined.
Citations not valid at the target: 0 of 10.

Wrong-version evidence sent to Command: 2 of 4 pieces in every run, 16 of 32
in total, always the matching function from the other revision.

Comparison with exp-2026-11-22-demo-agent (configuration 8, Git filter on):
7 of 8 correct, 1 incomplete, 0 wrong-version. The one difference (q2 at v1)
is a single run and is not treated as a finding.

Notes:
- Agent model was command-a-03-2025.
- On this practice repository, with two short files and revisions named v1 and
  v2, Command A used the revision labels without error. The Git filter made no
  measurable difference here. Whether that holds on real repositories, with
  more similar chunks and less obvious revision names, is what the final
  evaluation tests (H4).
