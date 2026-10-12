# Glossary

*Adopted in round 4 (Q18, DR-11) and updated in round 5.* INCOSE asks for one defined term per concept, used consistently. Each entry gives our meaning first, then the systems-engineering (SE) equivalent.

## Structure

- **System:** the whole product being specified, which is the root of the system breakdown. *SE: system of interest.*
- **System element:** a part of the system that you state requirements about as a unit. It is a logical part at any level, with a purpose, one parent and its dependencies. It isn't a code module; code relates to it loosely. *SE term (ISO/IEC/IEEE 15288). Replaces "component".*
- **Parent / child:** "is part of". The tree of system elements is the *system breakdown structure*.
- **Dependency:** "uses". System element A relies on the behavior of system element B. *SE: an interface between elements.*
- **Implementation:** one realization of the whole spec in one language, for example "the C++ build". *SE: realization.*
- **Related code:** the files that realize a system element within one implementation. The link is loose and many-to-many.
- **Harness:** the agent application that runs the agents, such as Claude Code or Antigravity.

## Spec items

Spec items are the things with IDs that the engineer approves (MODEL-25).

- **Spec item:** a need, a requirement, a verification item, a decision record, or a system element's definition (its purpose, parent and dependencies).
- **Need:** an outcome the engineer wants, stated in the engineer's terms, with its context (reasoning and scenarios of use) in paraphrase. Needs are validated, not verified. Agents draft them only from what the engineer says. *SE: stakeholder need.*
- **Requirement:** a single "shall" statement that can be checked. *SE: requirement statement; with its attributes, a requirement expression.*
  - **System requirement:** a requirement on the system as a whole. It serves one or more needs.
  - **System-element requirement:** a requirement on one system element. It refines one system requirement and never restates it (MODEL-33).
  - **Constraint:** a requirement the engineer imposes on the solution, such as the implementation language. It need not trace to a need.
  - **Derived requirement:** a requirement that traces to nothing above it because it records a design choice. Review these first. *SE and DO-178C term.*
- **Trace (↑):** the link from an item to what it serves. *SE: traceability. Assigning a system requirement to system elements is allocation; writing their requirements from it is flow-down.*
- **Rationale:** why a requirement exists.
- **Decision record:** a dated record of a past decision about one or more system elements, with its reasoning (paraphrased) and the alternatives considered. *Software: ADR. SE: trade-study record or design rationale.*

## Verification and validation

- **Verification:** checking that the product meets its requirements ("did we build it right?"). Agents can do this.
- **Validation:** checking that the requirements, once met, deliver the needs ("did we build the right thing?"). This is the engineer's judgment.
- **Verification item (VI):** how one or more requirements are checked. A VI has a method, a technique, a language-independent description, success criteria, and test links for each implementation. *SE: verification activity (INCOSE).*
- **Verification method:** one of four, which each VI names (MODEL-30).
  - **Test:** run it and measure.
  - **Analysis:** reason or model about it.
  - **Demonstration:** show it working in use.
  - **Inspection:** examine it, for example by reviewing its code.
- **Technique:** how a method is carried out here: unit test, integration test or reasoning check. Replaces "modality".
- **Run:** one execution of a set of verification items. A **full run** executes all of them. *SE: verification event.*
- **Tier:** cheap, or expensive in tokens or time. *Our own term; SE has no equivalent.*
- **Importance:** how much an item matters, as judged by an agent at the moment it acts. The judgment comes from the item's recorded history: whether the engineer stated it, its decision records, how often it changed, and what depends on it. Importance isn't stored as a flag, and the agent states its reasons (DR-20). *Replaces "criticality".*

## Change and configuration

- **Approval:** the engineer's acceptance of a spec item's current content, recorded with a fingerprint and the approved text. Approved items form the baseline.
- **Baseline:** the set of approved spec items. *SE term.*
- **Change:** one unit of work on the spec, the code or both, done in spec-first or code-first mode. *SE: engineering change.*
- **Change record:** what a change asked for, its mode, the reason for each spec difference, and its open decisions. *SE: change request or change notice.*
- **Open decision:** a question waiting for the engineer, with options and one marked as recommended (CHANGE-10). An open decision is pending; a decision record is history.
- **Deferral:** a recorded, reasoned acceptance that a requirement isn't yet met in an implementation. *SE: deviation.*
- **Onboarding:** bringing an existing project into the toolkit by extracting its spec and the reasons behind it. Onboarding ends with the engineer confirming the needs and approving the rest (DR-21).
