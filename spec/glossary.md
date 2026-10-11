# Glossary (proposed, round 3)

*This vocabulary is not approved yet; see Q18.* Each term gives our meaning first, then the systems-engineering (SE) equivalent where one exists. INCOSE's rule is one defined term per concept, used consistently.

✅ marks a term or concept you introduced. 🟡 marks one I'm proposing.

## Structure

- 🟡 **System**: the whole product being specified, which is the root component. *SE: system of interest.*
- ✅ **Component**: a part of the system that you state requirements about as a unit. It is a logical part, at any level, with a purpose, one parent and its dependencies. It is not a code module; code relates to it loosely. *SE: system element (ISO/IEC/IEEE 15288).* The definition is 🟡.
- 🟡 **Parent / child**: "is part of". The tree of components is SE's *system breakdown structure*.
- 🟡 **Dependency**: "uses". Component A relies on component B's behavior. *SE: an interface between elements.*
- ✅ **Implementation**: one realization of the whole spec in one language, for example "the C++ build". *SE: realization, or physical solution.*
- 🟡 **Related code**: the files that realize a component within one implementation. The link is loose and many-to-many.

## Spec items

These are the things that have IDs and get approved.

- 🟡 **Spec item**: any individually identified entry: a need, a requirement, a verification item, a decision record, or a component's own definition (its purpose, parent and dependencies). Each has an ID and its own approval. *Requirements tools use similar terms: OpenFastTrace's "specification item", DOORS's "object".*
- 🟡 **Need**: an outcome the engineer wants, in the engineer's terms. The engineer validates needs; nothing verifies them. *SE: stakeholder need (INCOSE Needs and Requirements Manual).*
- ✅ **Requirement**: a single "shall" statement about one component that can be checked. *SE: requirement statement. With its attributes (rationale, criticality and so on), INCOSE calls it a requirement expression.*
- 🟡 **Derived requirement**: a requirement that traces to no need and no parent requirement. It records a design choice, so it is a prime candidate for review. *SE and DO-178C term.*
- 🟡 **Rationale**: why a requirement exists. *A standard SE attribute.*
- 🟡 **Scenario**: a concrete sequence of use, such as your CUJs. *SE: operational scenario, part of the concept of operations.* This is a proposed item type; see Q17.
- ✅ **Decision record**: a dated record of a decision about a component. It holds the reasoning (paraphrased, never quoted) and the alternatives considered. *Software: ADR. SE: trade-study record, or design rationale.*

## Verification and validation

- 🟡 **Verification**: checking that the product meets its requirements ("did we build it right?"). Agents can do this. *Standard SE term.*
- 🟡 **Validation**: checking that the requirements, once met, deliver the needs ("did we build the right thing?"). This is the engineer's judgment. *Standard SE term.*
- ✅ **Verification item (VI)**: how one or more requirements are checked. A VI has a method, a language-independent description, success criteria and test links. *SE: INCOSE calls this a verification activity. NASA's verification matrix records the same information per requirement.*
- 🟡 **Verification method**: one of SE's four methods. This is proposed to replace "modality"; see Q18.
  - Test: run it and measure.
  - Analysis: reason or model about it.
  - Demonstration: show that it works in use.
  - Inspection: examine it, for example review its code.
- 🟡 **Technique**: how a method is carried out in this toolkit: unit test, integration test or reasoning check. This is the old "modality".
- 🟡 **Run**: one execution of a set of verification items. *SE: verification event.*
- ✅ **Tier**: cheap, or expensive (in tokens or time). *Our own term; SE has no equivalent.*
- 🟡 **Criticality**: normal or critical. Critical requirements get stronger verification. *SE: a criticality attribute. Compare DO-178C's software levels and ISO 26262's ASILs.*

## Change and configuration

- ✅ **Approval**: the engineer's acceptance of an item's current content, recorded with a fingerprint. *SE: placing the item under baseline.*
- 🟡 **Baseline**: the set of approved items. *Standard SE term.*
- ✅ **Change**: one unit of work on the spec and/or the code, done in spec-first or code-first mode. *SE: engineering change.*
- 🟡 **Change record**: what a change asked for, its mode, its reasons and its open decisions. *SE: change request, or change notice.*
- 🟡 **Deferral**: a recorded, reasoned acceptance that a requirement isn't met yet in an implementation. *SE: deviation.*
