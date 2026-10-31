# HACKATHON.md

## Team name
bits&bytes

## Team members
- Shivam Kumar Singh (Leader)
- Tanmay
- Monti Chaudhary
- Gaurav

## Problem statement
**PROBLEM 05: Automated Documentation Drift Detection**
(Category: Developer Experience | Documentation Engineering | Static Analysis)

### The Problem
Documentation plays an important role in helping developers understand, configure, and contribute to open-source projects. However, documentation frequently becomes outdated when the underlying code changes.

For example:

- A configuration flag gets renamed, but the documentation retains the old name.
- A default value changes, but the documentation still describes the previous behavior.
- An API parameter is modified, but tutorials continue explaining the old implementation.
- A feature is removed, but references to it remain in the documentation.

Existing tools can validate executable code examples in documentation, but they generally cannot determine whether explanatory prose, configuration tables, or tutorial instructions accurately describe the current codebase.

### Your Objective
Build an automated documentation drift detection system that identifies documentation made incorrect by code changes in a pull request.

The system should:

- Analyze code changes introduced through pull requests.
- Identify documentation associated with modified code.
- Detect outdated configuration descriptions and API references.
- Identify incorrect defaults, flags, parameters, and behavioral explanations.
- Highlight the exact documentation sentences affected.
- Link each detected issue to the corresponding code change.
- Integrate with GitHub pull request workflows.

### Research Starting Points

- GitHub's 2024 Open Source Survey.
- Rustdoc documentation tests.
- Python doctest.
- mktestdocs.
- Doc Detective.

### Evaluation Scenarios
The organizers will provide real project histories. These histories include commits that corrected documentation shortly after corresponding code changes. The tool will be evaluated on whether it can identify the original documentation drift before the corrective documentation commit.

### Key Technical Considerations

- How can documentation sentences be connected to relevant source code?
- How can the system identify indirect relationships between code and documentation?
- How can false alarms be minimized?
- How can documentation changes be distinguished from changes that genuinely require documentation updates?
- How can the tool remain useful without generating excessive warnings?

### Expected Deliverable
A working documentation analysis tool that identifies potentially outdated documentation and provides precise references to the responsible code changes.

## Models we use and why

### Qwen 3 4B (local, documentation drift analysis)
- Reads code and explains call paths.
- Reads focused code changes and related documentation, then helps explain call paths and behavior.
- Can flag possible mismatches in documented defaults, configuration flags, API parameters, and behavior.
- Small enough to run locally on a laptop, leaving more memory for the project and development tools.
- Keeps source code local during analysis.
- Supports a 32K-token native context, useful for analyzing a code change alongside relevant documentation.
- Offers a balance of capability, memory use, and speed for a prototype.

### nvidia_nim/nvidia/nemotron-3-ultra-550b-a55b (hosted, coding assistant)
- Analyzes code and helps explain call paths, behavior, and implementation choices.
- Hosted through NVIDIA NIM, so it does not need to run on your laptop.
- Useful for vibe coding, complex coding tasks, and comparing alternative implementations.
- We keep Qwen3 4B as the local model for documentation drift analysis and use Nemotron as a coding assistant.
