---
name: repo-portfolio-auditor
description: >
  Audits GitHub repositories and entire user/organization portfolios against RepoPilot's
  5-dimension credit-score model (Safety 30%, Trust 25%, Maintenance 20%, Maturity 15%, Documentation 10%).
  Calculates 0-100 scorecards, detects onboarding friction, identifies pending gaps,
  and provides remediation plans.
---

# RepoPilot Portfolio Auditor

Audits single repositories or full GitHub portfolios against the RepoPilot architectural framework.
Produces an executive 0-100 scorecard, grades (A/B/C/D/F), and isolates pending gaps across 5 weighted dimensions.

## Core Scoring Architecture

The engine computes a weighted credit score:

$$\text{Overall Score} = (\text{Safety} \times 0.30) + (\text{Trust} \times 0.25) + (\text{Maintenance} \times 0.20) + (\text{Maturity} \times 0.15) + (\text{Documentation} \times 0.10)$$

### 1. The 5 Evaluation Dimensions

| Dimension | Weight | Target Criteria | Impact / Deductions |
|:---|:---:|:---|:---|
| **Safety** | **30%** | Zero malicious patterns, no committed credentials, clean `.gitignore` | • Committed `.env` or keys: -40 pts (CRITICAL)<br>• Dangerous shell execution (`curl \| bash`): -35 pts (CRITICAL)<br>• Missing `.gitignore`: -15 pts |
| **Trust & Governance** | **25%** | OSI license (MIT, Apache-2.0, GPL, BSD), meaningful description, repository topics | • Standard OSI License: +50 pts (No license: 0 pts)<br>• Clear description: +25 pts<br>• Repository topics ($\ge 2$): +25 pts |
| **Maintenance** | **20%** | Recency of commits, issue velocity, active maintenance | • Pushed $< 30$ days: 100 pts<br>• Pushed $< 90$ days: 85 pts<br>• Pushed $< 180$ days: 65 pts<br>• Pushed $< 365$ days: 40 pts<br>• Archived: 25 pts max |
| **Maturity & Testing** | **15%** | CI/CD automation pipelines, automated test suites | • GitHub Actions / CI workflow: +50 pts<br>• Automated test suite (`tests/`, unit tests): +50 pts |
| **Documentation** | **10%** | Quality README, onboarding friction reduction, `.env.example` | • Comprehensive README: +50 pts<br>• `.env.example` present for apps with manifests: +50 pts |

### 2. Hard Capping Gates (Failure Modes)
- **CRITICAL Security Issue:** Caps overall score at **39 (Grade F)**. Regardless of test coverage or documentation, key exposure or untrusted execution fails the audit.
- **Missing Open Source License:** Caps non-fork repositories at **74 (Grade C)**.
- **Missing README:** Caps repository at **59 (Grade D)**.

---

## Grade Rubric

| Range | Grade | Classification | Action Required |
|:---:|:---:|:---|:---|
| **90 - 100** | **A** | **Excellent / Production Ready** | Maintain active dependencies and patch cadence. |
| **75 - 89** | **B** | **Good / Minor Gaps** | Add repository topics, fill in `.env.example` templates. |
| **60 - 74** | **C** | **Needs Attention / Governance Gaps** | Add OSI License, implement GitHub Actions CI workflow. |
| **40 - 59** | **D** | **High Friction / Incomplete** | Add README, write unit test suites, set up build scripts. |
| **0 - 39** | **F** | **Critical Risk / Flawed** | Remediate leaked secrets, purge untrusted script hooks. |

---

## CLI Execution

Run the bundled CLI tool:

```bash
# Audit an entire GitHub user portfolio
python .agents/skills/repo-portfolio-auditor/scripts/audit_repos.py --user <username>

# Output markdown report to file
python .agents/skills/repo-portfolio-auditor/scripts/audit_repos.py --user <username> --format markdown --out portfolio_audit.md

# Audit a single repository
python .agents/skills/repo-portfolio-auditor/scripts/audit_repos.py --repo owner/repo --format table
```
