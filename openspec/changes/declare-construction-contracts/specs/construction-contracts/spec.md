## ADDED Requirements

### Requirement: Construction authority is explicit and bounded

The proposed interface SHALL bind each function contract to authored obligations,
an exact revision and permitted writable cells/paths. Admission SHALL be atomic,
preserve immutable obligations and support shared references without duplicating
definitions. Unsupported structure SHALL return a named refusal without writes.

#### Scenario: A candidate changes an immutable obligation
- **WHEN** a reply fills permitted code and also changes an authored prohibition
- **THEN** the entire reply is refused and the original contract and files remain unchanged

#### Scenario: Several callers use one owned helper
- **WHEN** the approved contract declares one helper definition and multiple valid references
- **THEN** admission preserves those references without imposing a single-caller tree

### Requirement: Interpreter and import semantics are declared

The proposed validator SHALL identify its supported grammar/interpreter basis and
import binding, location and lifetime constraints. Unsupported capability SHALL be
distinguished from an invalid contract; it SHALL NOT silently hoist local imports.

#### Scenario: A grammar field is unsupported
- **WHEN** the contract requires an AST field outside the declared supported dialect
- **THEN** the real admission entry returns an unsupported-capability outcome and writes no admitted artifact

#### Scenario: An optional dependency is intentionally lazy
- **WHEN** a permitted local import avoids import-time dependency loading
- **THEN** construction retains that scope/timing or explicitly refuses the unsupported constraint

### Requirement: Wesker owns the policy-qualified catalog

Wesker's proposed export SHALL distinguish theory declaration, implementation,
applicability and observation capability under an identified policy and producer
version. It SHALL retain unsupported obligations and SHALL NOT treat a category
name or syntactic visitor as evidence of semantic completeness.

#### Scenario: A declared operator lacks an implementation
- **WHEN** the contract requests a declared family that the current engine cannot generate or observe
- **THEN** the export names that unavailability and Detective retains the obligation unresolved

### Requirement: Evidence warrants remain separate

Detective SHALL retain separate structural admission, load validity, observation
validity, scoped specification standing, intent acceptance and action authority.
Its proposed records SHALL bind source/test/contract/policy/context identities and
distinguish absence, unknown, observed empty, observed value, unsupported and invalid.

#### Scenario: Code compiles but its observation is invalid
- **WHEN** structural admission succeeds and execution exceeds its valid containment or budget boundary
- **THEN** the observation cannot support certification despite successful compilation

#### Scenario: The output alphabet is fully exercised
- **WHEN** tests return every declared decision code without establishing each input-to-code obligation
- **THEN** alphabet coverage alone does not establish intended selector correctness

#### Scenario: Evidence is absent rather than observed empty
- **WHEN** one invocation supplies no observation and another supplies a valid empty observation
- **THEN** their records and applicable decisions retain that distinction

### Requirement: Decisions reach real consumers without invented remedies

Each proposed code/field SHALL have a production consumer or a reviewed exemption
naming the alternate consumer. Applicable consumer branches SHALL preserve distinct
remedies or explicitly justify a collapse. Reflective/dynamic consumption SHALL be
accounted for without treating static-reference absence as proof of deadness.

#### Scenario: A field is declared but the live path bypasses it
- **WHEN** a fixture and helper consume a field but the production decision ignores it
- **THEN** contract acceptance does not count that helper's existence as live consumption

#### Scenario: An unexplained refusal has no warranted next command
- **WHEN** a run supplies no established refusal cause
- **THEN** no renderer invents a cause, a certified count bound or a rerun remedy

### Requirement: Conditional actions share one decision basis

Detective SHALL derive actions once and preserve their applicable evidence and
premises across CLI, full report, JSON, ledger and certificate projections. An outer
controller SHALL receive bounded argv/scope and a named hand-back when execution
premises change. Legitimate surface-specific omissions SHALL be declared.

#### Scenario: Several gate blockers hold simultaneously
- **WHEN** shape capability, containment and identity blockers are all present
- **THEN** each applicable surface retains their structured reasons and no isolated rerun is presented as guaranteed success

#### Scenario: Source or policy changes after the action was issued
- **WHEN** the controller attempts the action against a different applicable basis
- **THEN** the execution boundary revalidates that basis and refuses stale authority rather than blindly executing

### Requirement: Construction metadata does not replace independent acceptance

Generated scaffolds SHALL carry construction provenance and SHALL NOT use their
candidate's behavior as the sole oracle of authored intent. Existing CLI use SHALL
remain supported without a contract. New deletion, effect-world or equivalence-proof
authority SHALL NOT be inferred from this interface.

#### Scenario: Candidate and generated characterization agree on a bug
- **WHEN** a candidate violates an independent authored intent expectation but passes its generated characterization
- **THEN** acceptance fails and the characterization does not override intent

#### Scenario: Tests share structural or coverage metadata
- **WHEN** a contract catalog shows overlapping lines, outputs or AST categories
- **THEN** the tests remain until the existing authorized removal contract is independently satisfied
