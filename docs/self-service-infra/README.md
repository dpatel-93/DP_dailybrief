# Self-Service Infra via GitHub Copilot + MCP

Design and (eventually) implementation of governed, developer self-service Azure
infrastructure deployment, driven from GitHub Copilot chat / Copilot CLI and
enforced by a platform control plane.

**One-line pitch:** a developer types *"I need a key vault in my resource group"*
into Copilot. The system verifies the request against the LeanIX-approved
architecture for their project, selects the curated Terraform module, gathers the
remaining parameters conversationally, routes through the ServiceNow change/task
process based on the application's CMDB lifecycle state, deploys via Port-triggered
Azure DevOps pipelines, and records everything for audit — with Cloud Engineering
curating modules and guardrails instead of executing tickets.

## Repo contents

| Path | What it is |
|---|---|
| `docs/design.md` | The full architecture design (v2) — start here |
| `docs/decisions.md` | Environment constraints and decisions taken so far |

## Where we are

- [x] Problem framing and feasibility research (all integration layers confirmed GA)
- [x] v1 design (generic): LeanIX-gated entitlements, CloudOps MCP, module catalog, auto ServiceNow records
- [x] v2 design: incorporates environment specifics — Azure DevOps repos for modules, JFrog Artifactory, ServiceNow via REST API with CMDB lifecycle gating, Port IDP as execution backbone, Confluence standards via Atlassian MCP, Copilot MCP allowlisting for adherence
- [ ] Phase 0: LeanIX component taxonomy ↔ module catalog contract; platform-facts extraction from Confluence
- [ ] Phase 1: read-only pilot (LeanIX MCP + Confluence MCP in Copilot, org MCP registry)
- [ ] Phase 2: CloudOps MCP MVP (Key Vault, non-prod, task path)
- [ ] Phase 3: ServiceNow change-gated path for Live/Operational applications
- [ ] Phase 4: full catalog, prod, day-2 operations

## Stack (decided)

Azure · Terraform/Terragrunt · modules in **Azure DevOps Repos** · packages in
**JFrog Artifactory** · **Port IDP** (ties ServiceNow + Azure, triggers ADO
pipelines) · **ServiceNow via REST API** (MCP possible later) · **LeanIX MCP**
(architecture approvals) · **Atlassian/Confluence MCP** (standards context) ·
**GitHub Copilot** IDE chat + CLI as the interface.
