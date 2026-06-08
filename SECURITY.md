# Security Policy

## Supported Versions

This is an open-source portfolio project. Security fixes are applied to the latest commit on `main`.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities, as that exposes the flaw before a fix is available.

Instead, report vulnerabilities privately:

1. Email: **areebmehdi54@gmail.com**
2. Subject line: `[SECURITY] IntelliGate — <brief description>`
3. Include:
   - A description of the vulnerability and affected component
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if you have one)

You will receive a response within **72 hours** acknowledging receipt. I will keep you updated on progress and credit you in the fix commit (unless you prefer to remain anonymous).

## Security Design Notes

### Credential Handling
- Facility API keys are stored **hashed** in the database (not plain text).
- API keys can be rotated at any time via `POST /api/facilities/{id}/rotate-key`.
- JWT tokens expire after 24 hours by default (`JWT_EXPIRE_MINUTES=1440`).

### Biometric Data
- Face embeddings (512-dim ArcFace vectors) are stored in PostgreSQL with `pgvector`.
- Raw face images are stored in Cloudflare R2 (external storage) — not in the database.
- Embeddings are **never returned** in API responses that don't require them.
- The `my_face_embedding.json` file and `captures/` directory are excluded from this repository.

### Access Control
- Row-Level Security (RLS) is enabled on all facility-scoped tables — guards cannot query data outside their facility.
- The `/api/scan/` endpoint is authenticated by API key only (no JWT) to support edge nodes.
- Swagger UI (`/docs`) is disabled when `APP_ENV=production`.

### Known Limitations (Portfolio Project)
- RLS policies are enabled at the schema level but application-level enforcement is the primary guard — full RLS policy expressions are not yet defined.
- RTSP camera streams are not authenticated in the current implementation.
- The Celery task queue does not use TLS in the default Docker Compose setup.
