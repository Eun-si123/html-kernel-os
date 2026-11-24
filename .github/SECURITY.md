# Security Policy

## Report vulnerabilities privately

This public experimental repository has **GitHub Private Vulnerability Reporting** enabled. Use the [Security tab](https://github.com/Eun-si123/html-kernel-os/security) → **Advisories** → **Report a vulnerability** to share a report without publishing exploit details.

Please do not disclose active credentials, token values, private personal information, unpatched proof-of-concept exploits or third-party systems' data through public GitHub Issues, PR comments or CI logs.

Include the affected commit, precise HTML-like source snippet (with no secrets), target (compiler / x86-64 QEMU kernel / Ring 3 user application / browser boot lab), reproduction steps, expected and actual behavior, and the smallest available evidence. A local test using synthetic content is preferred.

## Supported scope

HTML Kernel OS is a **research compiler and minimal native boot experiment, not a secure general-purpose operating system or a supported production OS**. The GitHub Pages boot lab executes an emulator in the user's browser; do not confuse test-mode QEMU behavior with physical-hardware security guarantees. See [STATUS.md](../docs/STATUS.md) and [VALIDATION.md](../docs/VALIDATION.md) for implementation and evidence limits.

Research and proof-of-concept testing must remain within infrastructure and accounts the reporter owns or is expressly authorized to test. Do not disrupt the public Pages service or compromise other visitors.

## Coordination

The maintainer will review security reports, reproduce credible issues if feasible, prioritize remediation and coordinate disclosure. No fixed response-time SLA, financial bounty or universal patch support is promised. GitHub CodeQL, Gitleaks, Dependabot and build-artifact scanning are defense-in-depth checks and do not establish complete security.

If credentials have leaked, promptly revoke/rotate them at the provider; removing source history by itself is insufficient.
