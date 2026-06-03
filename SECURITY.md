# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| latest `main` / newest release | :white_check_mark: |
| older releases | :x: |

We provide security fixes for the most recent minor release. Please upgrade before reporting.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Please use **GitHub's private vulnerability reporting**:
[Report a vulnerability](https://github.com/Casius999/decroche-mcp/security/advisories/new).

Alternatively, email **julien@novaquantix.tech**. If you need encryption, request our PGP key in your
first message.

Please include:
- A description of the issue and its impact.
- Steps to reproduce or a proof of concept.
- Affected version(s) / commit SHA.
- Any suggested remediation.

## Our commitment

- **Acknowledgement** within **72 hours**.
- **Triage and severity assessment** within **7 days**.
- We will coordinate a fix and a [GitHub Security Advisory (GHSA)](https://github.com/Casius999/decroche-mcp/security/advisories),
  request a CVE where appropriate, and credit you (unless you prefer to remain anonymous).
- Please allow **90 days** for coordinated disclosure before publicizing details.

## Scope

This policy covers the code in this repository. Vulnerabilities in third-party dependencies should
be reported upstream; we monitor them via Dependabot/Renovate, `dependency-review-action`, and
SBOM-based scanning (grype / osv-scanner).
