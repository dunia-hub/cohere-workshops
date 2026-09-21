# Data and Ethics Plan

## Status

Draft plan. It must be finalized before any participant research data is collected.

## Data sources

The research may use two distinct data sources:

1. Public open-source repository history
2. Optional data from consenting workshop participants

These sources must remain separate in collection, storage and analysis.

## Public repository data

The primary technical evaluation will use public Python repositories and historical merged pull requests.

For every repository case, record:

- Repository URL
- Repository license
- Repository commit
- Pull-request identifier
- Pre-change commit
- Change-request text
- Changed-file paths
- Relevant diff metadata
- Date collected

Repository source code must not be presented as Dunia Hub content.

Published datasets should prefer repository references, commit identifiers and derived metadata over redistributing complete source files.

Repositories without a clear license or stable public history should be excluded.

## Workshop attendance

Attending a workshop does not require participation in the research.

Everyone must receive the same:

- Workshop access
- Learning materials
- Exercises
- Technical support
- Opportunity to ask questions

Declining research participation must not affect the attendee’s workshop experience.

## Voluntary research participation

Research participation must require a separate consent process.

Before consenting, participants must be told:

- The purpose of the study
- What data will be collected
- How the data will be used
- Whether responses may appear in a paper
- How privacy will be protected
- How to withdraw
- The withdrawal deadline
- Who can access the data
- How long the data will be retained

Consent must be recorded before participant data enters the research dataset.

## Data minimization

Collect only information required to answer the research questions.

Do not collect:

- API keys
- Passwords
- Wallet credentials
- Government identifiers
- Private repository content
- Confidential project information
- Unnecessary names or email addresses
- Unrelated demographic information

## Participant identifiers

Research records should use randomly generated participant codes.

Names, email addresses and registration details must not appear in the analysis dataset.

If a code-to-identity mapping is required for withdrawal requests, it must be:

- Stored separately
- Access restricted
- Encrypted
- Deleted when the withdrawal period ends

## Workshop-generated data

With consent, the study may collect:

- Task responses
- System predictions
- Participant corrections
- Completion time
- Usefulness ratings
- Confidence ratings
- Error reports
- Optional written feedback

The system must distinguish participant-authored text from model-generated text.

## Recordings, images and quotations

Workshop research consent does not automatically authorize:

- Audio recording
- Video recording
- Screenshots
- Photography
- Public attribution
- Direct quotations

Each of these requires separate, explicit permission.

Participants must be able to join the workshop without appearing in public media.

## Withdrawal

Participants may withdraw without penalty.

The consent form must provide:

- A withdrawal contact
- The participant code
- A clear withdrawal deadline
- A description of data that can be deleted
- An explanation of data that cannot be removed after irreversible anonymization or publication

No withdrawal deadline may be invented after data collection begins.

## Data storage

Participant research data must be stored separately from workshop registration information.

Access should be limited to named research personnel.

Research data must not be stored in:

- Public GitHub repositories
- Public shared drives
- Workshop chat exports
- Application logs containing identifiers
- Source-code fixtures

API keys and secrets must remain in local environment variables.

## Retention

A final retention period must be approved and disclosed before participant enrollment.

The planned default is:

- Identity mappings: delete after the withdrawal period
- Raw participant data: retain until 12 months after publication
- Anonymized aggregate findings: retain with the published research
- Public repository identifiers and derived benchmark metadata: retain for reproducibility where licenses permit

Any change to this schedule must be documented.

## Use of Cohere services

Participants must be informed when their submitted text will be sent to a Cohere API.

Before transmission:

- Remove direct identifiers
- Remove secrets
- Avoid private repository content
- Send only the minimum required context
- Record the model and purpose of the request

The research documentation must distinguish local deterministic processing from external model processing.

## Risks

Potential risks include:

- Accidental disclosure of project information
- Re-identification in a small participant group
- Incorrect AI recommendations
- Participant overconfidence in model output
- Repository-license violations
- Exposure of secrets embedded in source files
- Misinterpretation of workshop feedback as causal evidence

## Risk controls

Controls include:

- Data minimization
- Separate consent
- Pseudonymous participant codes
- Secret detection before API transmission
- Human review
- Evidence-linked model output
- Explicit uncertainty and abstention
- Aggregate reporting
- Separate storage for contact and research data
- No automatic application of model recommendations

## Research reporting

Published results must:

- Avoid identifying participants
- Report sample size
- State recruitment and consent procedures
- Separate technical benchmark results from participant feedback
- Report exclusions and withdrawals
- Disclose model usage
- Report limitations
- Avoid causal claims unsupported by the study design

## Ethics review

Before collecting participant research data, Dunia Hub must determine whether independent or institutional ethics review is required for the intended study and publication venue.

No participant research data should be collected until the protocol, consent language, retention schedule and responsible research contacts are finalized.