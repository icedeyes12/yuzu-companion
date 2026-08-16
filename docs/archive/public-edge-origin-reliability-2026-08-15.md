# Public Edge / Cloudflare / Origin Reliability Audit

Date: 2026-08-15
Scope: shared public edge, tunnel, origin, routes, provider/model refresh

## Executive finding

The observed failure is not currently attributable to `yuzu_portal` or its model catalog.

Strongest evidence: `companion.yuzuki.space` consistently returns a Cloudflare-generated HTTP 502 for both `/health` and `/api/v1/config`, while unrelated `llm.yuzuki.space` traffic reaches an application response (`401` JSON) and `yuzuki.space` returns cached HTML or Cloudflare challenge responses. The configured tunnel routes `companion.yuzuki.space` and `login.yuzuki.space` to `http://localhost:5000`; this machine has no listener on `127.0.0.1:5000`.

The likely boundary is:

`client/browser -> Cloudflare edge -> Cloudflare Tunnel -> unavailable/unreachable companion origin`

This is evidence for a hostname/origin availability problem on the companion route, not a provider-specific model-refresh problem. It is not proof of the historical failure's exact timestamp or of the remote origin's internal cause.

## Request path and CORS

The frontend makes the affected request with browser `fetch`:

`POST /api/v1/proxy/models/{provider}/refresh`

Source: `static/js/config.js`, `fetchModelsForProvider()`.

The backend then makes a server-side request to the provider model endpoint. For `yuzu_portal`, the backend uses:

`GET http://localhost:20128/v1/models`

Source: `app/providers/yuzu_portal.py`.

Therefore two separate HTTP boundaries exist:

1. Browser -> public Yuzu API (`POST /api/v1/proxy/models/yuzu_portal/refresh`). Browser CORS can matter here.
2. Yuzu backend -> Yuzu Portal model endpoint (`GET .../v1/models`). Browser CORS is irrelevant here.

The observed Cloudflare message is an edge/origin response, not a browser CORS diagnostic. Do not classify it as CORS without browser console evidence showing a CORS policy rejection.

## Public probes

All probes used `curl` without credentials. No authorization headers or secrets were logged.

| Host / path | Result | Evidence |
|---|---:|---|
| `https://companion.yuzuki.space/health` | HTTP 502 | Cloudflare `server`, 16-byte body `error code: 502`, CF-Ray present |
| `https://companion.yuzuki.space/api/v1/config` | HTTP 502 | Same Cloudflare-generated response shape |
| `https://login.yuzuki.space/api/v1/config` | HTTP 502 | Same configured origin target; Cloudflare-generated response |
| `https://llm.yuzuki.space/api/v1/config` | HTTP 401 | `application/json`, `cf-cache-status: DYNAMIC`; request reached an application/auth boundary |
| `https://yuzuki.space/api/v1/config` | HTTP 200 | `text/html`, `cf-cache-status: HIT`; this is cached HTML, not the JSON API response |
| `https://yuzuki.space/health` | HTTP 403 | Cloudflare `Just a moment...` challenge |
| `https://companion.yuzuki.space/health` repeated 3x | HTTP 502 each | 0.316–0.400s, 16 bytes, distinct CF-Ray IDs |
| `https://llm.yuzuki.space/api/v1/config` repeated 3x | HTTP 401 each | 0.361–0.409s, 50 bytes, distinct CF-Ray IDs |

Timing sample for companion 502: DNS 0.063s, connect 0.113s, TLS 0.220s, total 0.310s. This is a fast edge failure, not an application timeout or truncated long response.

HTTP method probes against the public model-refresh and streaming paths returned HTTP 405 with zero-byte bodies because authentication/method routing was not satisfied. They do not reproduce the intended authenticated POST path and are not evidence about provider behavior.

## Origin and tunnel evidence

Local probe results:

- `127.0.0.1:5000/health`: connection refused.
- `127.0.0.1:5000/health/ready`: connection refused.
- `127.0.0.1:5000/`: connection refused.
- `cloudflared tunnel run` is running.

Cloudflared configuration:

- `companion.yuzuki.space` -> `http://localhost:5000`
- `login.yuzuki.space` -> `http://localhost:5000`
- `llm.yuzuki.space` -> `http://localhost:20128`
- final ingress -> HTTP 404

The tunnel process is active, but the configured companion origin is not listening in this execution environment. This explains a Cloudflare 502 at the companion hostname. It does not establish whether the production Termux host also lacked its backend at the original incident timestamp.

## Code path audit

- `main.py` exposes `/health`, `/health/ready`, `/static`, and mounts API routes under `/api/v1`.
- `app/api/main.py` registers auth, chat, profile, stream, sessions, memory, presets, and static routers on the same FastAPI origin.
- `app/api/endpoints/profile.py` performs the provider model refresh transport and converts all unexpected exceptions to HTTP 502 with generic detail.
- `app/providers/yuzu_portal.py` performs a direct `httpx.AsyncClient().get()` to `/v1/models`, timeout 10s, with the request-scoped bearer key.
- `app/api/endpoints/chat.py` exposes non-streaming and SSE streaming application endpoints. SSE headers currently include `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
- `main.py` has browser CORS middleware restricted to `https://yuzuki.space`, but it allows only `GET`, `HEAD`, and `OPTIONS`; it does not allow the frontend's authenticated `POST` model-refresh or chat requests. This is a separate, concrete browser-side issue to verify/fix only after the public route is healthy. It cannot explain a server-side Yuzu -> provider Cloudflare failure.

## Failure classification

| Failure class | Finding |
|---|---|
| Browser CORS | Possible separate issue: current CORS method/header policy excludes POST and BYOK headers. Not the evidence for the Cloudflare 502. |
| DNS | DNS resolves `companion.yuzuki.space` through Cloudflare. No DNS failure observed. |
| TCP/TLS to edge | Successful. Low connect/TLS timings. |
| Cloudflare edge | Generated HTTP 502 for companion route; CF-Ray IDs available. |
| Tunnel/origin connection | Most likely failing boundary; local configured origin port is refused. |
| Origin timeout | Not observed in current probe; response is immediate. |
| Truncated response/reset | Not observed; body is a complete 16-byte Cloudflare error. |
| Provider/upstream model catalog | Not reached by current companion public probes; no basis to blame `yuzu_portal`. |
| Application validation | Not evaluated for the intended authenticated POST because companion origin is unavailable. |

## Cross-provider / cross-endpoint conclusion

A full authenticated cross-provider comparison could not be completed because the shared companion API origin is unavailable from this environment and requires user authentication/BYOK data. The available unauthenticated comparison is still decisive enough to elevate scope:

- Both lightweight health and config routes fail on `companion.yuzuki.space`, unrelated to any provider.
- Both companion and login hostnames fail through the same configured `localhost:5000` origin.
- The separate `llm.yuzuki.space` route reaches its own service and returns an application JSON response.
- Static/primary `yuzuki.space` results are contaminated by cached HTML and Cloudflare challenge behavior; they are not valid API health checks.

Classification: route/origin-specific to the companion Cloudflare Tunnel ingress, with potential shared impact across every application endpoint routed through `localhost:5000`. Not edge-wide across all Cloudflare hostnames. Not provider-specific based on current evidence.

## Temporal correlation

No production timestamp, Cloudflare dashboard export, tunnel log, or origin log covering the original incident was available. Therefore deployment/load/upstream correlation is undetermined. Current repeated probes show a stable immediate failure, not an intermittent timeout.

## Existing resilience

- `yuzu_portal` has a 600-second in-process model cache after a successful fetch.
- The frontend invalidates the provider's cached catalog on refresh failure; it does not retain last-known-good data in that path.
- Generic model refresh errors are mapped to HTTP 502, but unexpected causes are not classified or exposed with safe structured diagnostics.
- Existing provider retry logic is for selected LLM/provider flows and is not a justified fix for a shared Cloudflare/origin outage.

## Answers to requested questions

1. Exact request: browser `POST /api/v1/proxy/models/yuzu_portal/refresh`; backend then `GET /v1/models` on the configured Yuzu Portal base URL.
2. Initial affected call is browser -> public Yuzu API; provider fetch is server-side.
3. CORS is relevant only to the first boundary. It is irrelevant to backend -> provider.
4. Current direct evidence: Cloudflare generated the companion HTTP 502. The companion origin was not reached successfully.
5. Current local configured origin did not receive the request because port 5000 refused connections.
6. No origin response was observed for companion.
7. No truncation evidence; complete Cloudflare 502 body.
8. Unrelated companion health/config routes reproduce the same failure. Provider cross-comparison is blocked by the unavailable shared API origin.
9. Companion API routes share FastAPI origin port 5000 and the companion tunnel ingress.
10. Route/origin-specific for `companion.yuzuki.space` / `localhost:5000`; not proven edge-wide.
11. CF-Ray-backed repeated 502s, tunnel config, active tunnel, and local port refusal.
12. Model cache exists; no safe last-known-good retention on frontend refresh failure; no justified shared-origin retry.
13. Smallest justified fix: restore and verify the service behind the `companion.yuzuki.space` tunnel on port 5000, then capture request IDs and origin logs. Separately correct/verify CORS policy for browser POST/BYOK requests only if browser evidence confirms it.

## Recommended next evidence collection

1. On the production Termux host, verify the backend listener and process logs at the incident timestamp: `ss -ltnp`, `curl http://127.0.0.1:5000/health`, and application logs.
2. Run `cloudflared tunnel --config <config> ingress validate` and inspect tunnel logs for the CF-Ray-correlated requests.
3. In Cloudflare, inspect the matching CF-Ray IDs and confirm whether the 502 was tunnel connection refusal, origin reset, or another edge classification.
4. After origin recovery, test authenticated `POST /api/v1/proxy/models/{provider}/refresh` for at least three configured providers, `/api/v1/config`, `/api/v1/providers/list`, and `/api/v1/send_message_stream`; record status, duration, response bytes, content type, CF-Ray, and application `X-Request-ID`.
5. Do not add provider-specific retries or bypass Cloudflare until those measurements identify a provider/upstream boundary.

## Code changes

None made. This report intentionally precedes implementation changes.

Verification note: `ruff check` passed for inspected Python files. Targeted pytest execution was blocked by the environment's broken global pytest/pluggy installation (`ImportError: cannot import name 'HookimplMarker' from 'pluggy'`); no test result is claimed.

## Follow-up: actual `yuzu_portal` refresh destination

This section supersedes the earlier assumption that the observed provider refresh necessarily traversed `companion.yuzuki.space`.

Configuration trace:

1. `app/providers/__init__.py` registers `YuzuPortalProvider()` under `yuzu_portal`.
2. `app/core/byok.py` defines `DEFAULT_YUZU_PORTAL_BASE_URL = "http://localhost:20128/v1"`.
3. `app/providers/yuzu_portal.py` imports that constant as `DEFAULT_BASE_URL`.
4. `YuzuPortalProvider.fetch_live_models()` ignores its `base_url` argument and constructs:

   `f"{DEFAULT_BASE_URL.rstrip('/')}/models"`

5. Effective backend request:

   `GET http://localhost:20128/v1/models`

   with an `Authorization: Bearer ...` header. The credential value was not logged.

6. The browser first calls the Yuzu application endpoint:

   `POST /api/v1/proxy/models/yuzu_portal/refresh`

   on whatever public hostname serves the frontend. `app/api/endpoints/profile.py` passes only `X-Provider-Key` into `fetch_live_models()` for this provider. It does not pass a provider base URL for `yuzu_portal`.

7. `static/js/config.js` explicitly deletes `providerConfig.base_url` for `yuzu_portal`, so browser BYOK configuration cannot redirect this official provider to `companion.yuzuki.space` or `llm.yuzuki.space`.

Runtime probe evidence from this environment:

- `http://127.0.0.1:20128/v1/models` → HTTP 200, JSON model catalog, 38,497 bytes.
- `http://localhost:20128/v1/models` → HTTP 200, same catalog size.
- `https://llm.yuzuki.space/v1/models` → HTTP 401 JSON (`API key required for remote API access`).
- `https://companion.yuzuki.space/v1/models` → HTTP 404 JSON from the companion application, not the portal catalog.

Revised conclusion:

The failing backend provider request, if it was the model-refresh HTTP request, targeted local `localhost:20128/v1/models`, not `companion.yuzuki.space` and not `llm.yuzuki.space`. Therefore the companion 502 is not evidence for the `yuzu_portal` model-refresh failure. It is a separate public companion-route/origin problem unless additional incident-time evidence links the two processes or hosts.

The public browser-to-companion request can still fail independently before the backend performs the provider fetch. Exact incident classification requires the browser request hostname, its CF-Ray, and backend request/application logs. Current code alone establishes the provider destination, not the original failure timestamp's network trace.

No code changes made.

~ Reina ฅ^•ﻌ•^ฅ
