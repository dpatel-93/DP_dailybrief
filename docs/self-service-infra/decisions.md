# Decisions & environment constraints

Running log of decisions that shape the design. Treat these as fixed unless
explicitly revisited.

## D1 — Cloud

Azure only. Landing zone already established; its facts (vnets, subscriptions,
policies, monitoring, backup) are documented in Confluence.

## D2 — IaC and module source of control

Terraform + Terragrunt. Curated private modules live in **Azure DevOps Repos**
(git), owned by Cloud Engineering. Consumers pin modules by released git tag.
Optionally (later phase) tagged releases are also published to the JFrog
Artifactory Terraform module registry for immutable, provenance-tracked
distribution.

## D3 — Artifact management

Private **JFrog Artifactory** instance is the artifact system for application
stacks (Java, Node.js, etc.). Candidate host for the Terraform module registry
(see D2) — not required for MVP.

## D4 — ServiceNow integration style

**REST API (Table API / Change Management API), not MCP — for now.** The
ServiceNow MCP server may be adopted later for conversational status queries,
but all record creation/updates in the deployment flow are machine-to-machine
API calls from the orchestration layer. Rationale: determinism, and the audit
record must be created by the platform, not by an LLM tool call that might not
happen.

## D5 — ServiceNow lifecycle gate (CMDB-driven)

The CMDB CI operational status of the target application decides the process:

- **`Live` / `Operational`** → the application is in production service. Infra
  additions are *enhancements to a live service*: create a **normal change
  request**, **wait for ServiceNow approval**, and only then proceed with
  deployment. Close the change with deployment results.
- **Anything else (non-operational)** → the application is still being built.
  Create a **task record** for documentation/audit and **proceed immediately**
  (no approval wait).

## D6 — Developer interface

**GitHub Copilot** — IDE chat (VS Code/JetBrains, agent mode) and **Copilot
CLI**. No new portal UI is being built for this flow; Port's portal remains
available but chat is the primary interface.

## D7 — LeanIX role

LeanIX is consumed (via its built-in MCP server + REST/GraphQL API server-side)
for **fact sheets and architecture-approval data only** — which infra components
are approved for which project, and the disposition/decision references. LeanIX
is not a deployment trigger.

## D8 — Port IDP is in the environment

Port is already deployed and is the existing glue: ServiceNow, Azure, and other
systems are ingested into Port's catalog, and **Port's action backend is the
established mechanism for triggering Azure DevOps pipelines**. Design choice
(see design §5.6): use **Port as the execution and state backbone** rather than
calling ADO directly, to reuse its run history, RBAC, approval hooks, and
existing ServiceNow/Azure wiring.

## D9 — Standards live in Confluence

Landing zone setup, backup procedures, monitoring procedures, authentication
standards, etc. are documented in Confluence. These must inform every generated
blueprint. Consumption path: **Atlassian (Rovo) remote MCP server** for
conversational/advisory context, plus a **derived machine-readable
"platform facts" layer** for anything that must be enforced (see design §5.3 and
§6 — prose is never the enforcement mechanism).

## D10 — Absolute adherence requirement

There must be minimal room for LLM interpretation:

- Only *our* MCP servers may be used → enforced with GitHub Copilot
  **organization MCP registry + "Registry only" allowlist policy**, not by
  instruction text.
- Only LeanIX-approved architecture may be deployed → enforced server-side in
  the CloudOps MCP / Port action pre-checks, re-verified at submit time.
- Standards (backup, vnet selection, monitoring, auth) come only from our
  documented standards → enforced by baking them into modules, the platform-facts
  store, and policy-as-code gates.
- Note on temperature: temperature is not directly settable in GitHub Copilot
  chat, and temperature 0 does not guarantee correctness or compliance — it only
  reduces sampling variance. Adherence is achieved architecturally (the LLM
  proposes a structured request; deterministic code validates and executes).
  See design §6.
