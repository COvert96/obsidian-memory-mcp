---
date: 2026-05-28
tags: memory, api, auth
status: active
last_reviewed: 2026-05-28
# superseded_by: Memory/api-auth-decisions-v2.md
# supersedes:
#   - Memory/archive/api-auth-decisions-v1.md
---

# API authentication decisions

## Summary

Access tokens expire after 15 minutes; refresh tokens rotate on each use and are stored server-side only.

## Details

- Chose opaque refresh tokens over long-lived JWTs to simplify revocation.
- Public clients must use PKCE; confidential clients use client secret in the token endpoint.
- Rate limit: 10 failed auth attempts per IP per minute.

## Open Questions

- Whether to add step-up MFA for admin roles in Q3.

## References

- Wiki: `wiki/security/oauth-flow.md`
- Incident postmortem: `Memory/2026-05-20-auth-outage.md`
