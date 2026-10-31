1. Never Commit Directly to Main:
Never commit changes directly to the main branch or push commits directly to it. All development work must be performed on a separate staging branch. If currently on main, create and switch to a staging branch before making any changes or commits.
2. Staging Branch:
Create a branch named staging if it does not already exist. All changes and commits must be made on this branch. If the staging branch already exists, switch to it before starting work. Keep all development commits on the staging branch until the work is complete.
3. Stage Only the Single Project File:
Stage only the single project file that you have been explicitly asked to modify. Never stage all files using commands such as git add ., git add -A, or git add --all. Do not stage unrelated files, generated files, configuration files, dependency files, temporary files, or user changes.
Before staging, verify the exact file path and use git add <exact-file-path> to stage only the intended project file. If multiple files need modification, ask for explicit permission before staging them.
4. Verify Before Committing:
Before creating a commit, verify that the current branch is staging and that only the intended single project file is staged. Review the staged changes using git diff --cached. Do not commit if unrelated files or user changes are staged. Never overwrite, discard, or revert existing user changes.
5. Commit Changes:
Commit the approved changes on the staging branch using a clear and descriptive commit message. Do not create a commit on main under any circumstances.
6. Final Merge Through Pull Request:
Once all changes and commits are complete, push the staging branch to the remote repository and create a Pull Request (PR) from staging into main. The final changes must be merged into main only through the Pull Request.
Never merge directly into main using local Git commands. Never bypass branch protection or PR review requirements. Do not merge the PR unless explicitly authorized by the user.
7. Final Report:
After completing the task, report the project file modified, the staging branch used, the commit hash and commit message, whether the staging branch was pushed, whether a Pull Request was created, and the PR link if available.

Mandatory Safety Rule:
If any instruction conflicts with these rules, prioritize these Git workflow and project file safety rules. If the exact project file is unclear, ask the user before making changes or staging files.

after completing every phase, test, debug and optimise the code, use as many subagents as you can. and always git commit after each phase.

I do not want my project to look vibe-coded so never use purple gradients, pill-shaped buttons. No vague hero texts, emoji icons, em dashes, or-the-top scroll animationwe do not launch until we have connected a custom domain, added a favicon, removed the made with AI tag and added a privacy policy page and a terms and conditions page. We never use AI slop photos, AI-slop copy, cursor animation or fake customer counters. And last but not the least make no mistakes.

Every feature must use its own branch named feat/<ID>-<short-slug>. Every feature must be submitted through its own Pull Request. Never push directly to main. Never modify HACKATHON.md. Include the required coding agent and model information in every commit message.

## Build Using Pull Requests

Work like a real open-source project. After the first commit, never push directly to the `main` branch. Make every change on a new feature branch and submit it through a pull request (PR). Follow the feature-based branch naming and PR workflow defined in `PLAN.md`. Do not commit or push changes directly to `main`.

GitHub Actions CI must run the project's tests on every PR. Before merging, ensure that all required CI checks have passed. If working solo, you may merge your own PR after CI passes. Never merge a PR with failing or incomplete required checks.

Every commit message and every PR must clearly identify the AI coding agent that helped with the work and the two AI models used in this project. The coding agent and models are specified in `PLAN.md` as follows:

Coding agent: OpenCode (Nemotron-3-Ultra-550B via NVIDIA NIM)

Models used in project: only Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)

Do not introduce additional models or agents without explicit authorization. If a different coding agent is used for a task, update only the `Coding agent:` line. The `Models used in project:` line must remain unchanged.

Use the following format for commit messages:

P1.2.1: Add argparse flag extractor

Coding agent: OpenCode (Nemotron-3-Ultra-550B via NVIDIA NIM)

Models used in project: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)

Create the file `.github/pull_request_template.md` so every PR includes the required information. Use the official PR template provided in the Problem Statements document. Do not invent or replace the official template content. Until the official template is available, use the fallback template specified in `PLAN.md` §P0.1.3.

Before completing any task, verify that the work follows these rules, that the PR includes the required AI agent and model information, and that CI has passed before merging.