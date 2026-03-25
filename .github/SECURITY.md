# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities via public GitHub Issues.**

Instead, email directly to the maintainer at the address in the repository's contact info. Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

Response timeline: **24–48 hours** for initial triage, **7 days** for proposed fix.

## Security Best Practices (for contributors)

- Never commit API keys or secrets — use \`config.json\` and environment variables
- All database queries must use parameterized queries (no string interpolation)
- Encrypt sensitive data at rest using the project's encryption module
- Validate all external input before processing
