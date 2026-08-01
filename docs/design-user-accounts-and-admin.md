# Design — User Accounts, Per-User Projects, Sharing, and Admin Dashboard

**Status:** Draft for review — design only, nothing implemented.
**Location:** `docs/design-user-accounts-and-admin.md` (this file — source of truth)
**Date:** 2026-08-01
**Scope:** Cognito authentication across all three services, per-user project ownership,
sharing a project by email address, and an admin-only user list restricted to
`orkerem8@gmail.com`.

> Every claim about current behaviour below cites a file and line. Where a claim could
> not be verified from the code (chiefly what the AWS Academy Learner Lab permits for
> Cognito), it is marked **UNVERIFIED** with a command that settles it.

---

## 1. Current state

### 1.1 There is no authentication anywhere

- **Login is fake.** `frontend/src/pages/LoginPage.js:13-25` — `handleLogin` checks only
  that both fields are non-empty and then calls `navigate('/dashboard')`. No request is
  made, no credential is checked, no token is produced. The page itself admits the
  surrounding flows do not exist (`LoginPage.js:109-113`: "Password recovery and
  self-service sign-up are not available yet").
- **No route guard.** `frontend/src/App.js:14-25` declares `/login`, `/dashboard`,
  `/slack`, `/chats` as plain routes. Anyone who types `/dashboard` is in.
- **Logout is a redirect.** `frontend/src/components/layout/AppSidebar.jsx:112-121` —
  the Log Out button calls `navigate('/login')`. There is nothing to clear.
- **No `Authorization` header is ever sent.** `frontend/src/api/axios.js:11-26` creates
  three bare axios clients (`projectsApi`, `aiApi`, `slackApi`) whose only configuration
  is `baseURL` (from `REACT_APP_PROJECTS_API_URL` / `REACT_APP_AI_API_URL` /
  `REACT_APP_SLACK_API_URL`) and a timeout. There are no interceptors.
- **No auth dependency in any FastAPI app.** `projects_service/.../main.py:78-89` adds
  only `CORSMiddleware` and three routers; `ai_conversation_service/.../main.py:133-146`
  the same; `slack_service/.../main.py:12-20` the same. `dependencies.py` in both Python
  services (`projects_service/.../dependencies.py:18-33`,
  `ai_conversation_service/.../dependencies.py:19-41`) resolves services off
  `app.state` and nothing else — there is no `CurrentUser` concept to extend.
- **No user model.** The only trace of a user anywhere in the data model is
  `Task.assignee: Optional[str]  # user ID` (`projects_service/.../models/task.py:13`),
  which nothing writes and nothing reads for access control.

### 1.2 Endpoints that would become user-authenticated

`projects_service` (port 8000, ALB default target):

| Route | File:line |
|---|---|
| `POST /projects/` | `api/v1/projects.py:24-29` |
| `GET /projects/` — currently returns **every project in the database** | `api/v1/projects.py:32-34`, via `ProjectService.list_projects` (`services/project_service.py:64-82`) → `ProjectRepository.list_all` → `Project.find_all()` (`data/project_repository.py:45-51`) |
| `GET /projects/{project_id}` | `api/v1/projects.py:37-45` |
| `PUT /projects/{project_id}` | `api/v1/projects.py:48-57` |
| `DELETE /projects/{project_id}` — cascades nodes, conversations, tasks | `api/v1/projects.py:60-96` |
| `POST /context-tree/projects/{project_id}/nodes` | `api/v1/context_tree.py:23-29` |
| `GET /context-tree/projects/{project_id}/nodes` | `api/v1/context_tree.py:32-39` |
| `GET /context-tree/nodes/{node_id}` | `api/v1/context_tree.py:42-50` |
| `PUT /context-tree/nodes/{node_id}` | `api/v1/context_tree.py:71-80` |
| `DELETE /context-tree/nodes/{node_id}` | `api/v1/context_tree.py:83-100` |
| `POST /tasks/projects/{project_id}/tasks` | `api/v1/tasks.py:14-20` |
| `GET /tasks/projects/{project_id}/tasks` | `api/v1/tasks.py:23-28` |
| `GET|PUT|DELETE /tasks/{task_id}` | `api/v1/tasks.py:31-62` |

`ai_conversation_service` (port 8001, ALB `/ai/*`; routers mounted under `/ai` at
`main.py:145-146`):

| Route | File:line | Note |
|---|---|---|
| `POST /ai/ai-conversations/` | `api/v1/ai_conversations.py:30-47` | **takes `project_id` and `context_node_id` straight from the request body** (`schemas/ai_conversation_schemas.py:5-8`) |
| `POST /ai/ai-conversations/{conversation_id}/messages` | `api/v1/ai_conversations.py:50-70` | project is derived from the stored conversation (`services/.../service.py:367`) — good, but the *conversation id* itself is unchecked |
| `GET /ai/ai-conversations/{conversation_id}` | `api/v1/ai_conversations.py:73-96` | |
| `GET /ai/ai-conversations/node/{context_node_id}` | `api/v1/ai_conversations.py:99-116` | |
| `GET /ai/ai-conversations/project/{project_id}` | `api/v1/ai_conversations.py:119-134` | client-supplied `project_id` |
| `POST /ai/ai-conversations/context-retrieval/search` | `api/v1/ai_conversations.py:137-152` | debug only, gated by `enable_retrieval_debug_api` (default `False`, `core/config.py:56`); returns snippets from a **client-supplied** `project_id` (`schemas/retrieval_schemas.py:30-34`) |
| `POST /ai/ai-conversations/context-retrieval/reindex/{conversation_id}` | `api/v1/ai_conversations.py:155-169` | |
| `DELETE /ai/ai-conversations/{conversation_id}` | `api/v1/ai_conversations.py:172-192` | |
| `POST /ai/tree-analysis/organize-node` | `api/v1/tree_analysis.py:14-39` | takes `node_id`, `conversation_id` and a whole `current_tree` from the client (`schemas/tree_analysis_schemas.py:15-18`) |

`slack_service` (port 8002, ALB `/slack/*`) — `api/v1/slack.py`:

- Browser-facing and **must become user-authenticated**: `POST /slack/connection-check`
  (`:10-12`), `POST /slack/channels` (`:15-17`), `GET /slack/list-channels` (`:20-22`),
  `GET /slack/channels/{channel_id}/messages` (`:25-27`), `POST /slack/messages`
  (`:30-32`). These are exactly the five the console page calls
  (`frontend/src/pages/SlackConsolePage.js:66,87,106,177,197`).
- **Must stay unauthenticated by Cognito** because Slack calls them:
  `POST /slack/events` (`:35-55`), `POST /slack/commands` (`:58-83`),
  `POST /slack/interactions` (`:86-107`). They already authenticate the *caller* with
  Slack's HMAC signature (`services/slack_signature_service.py`, invoked at `:41-48`,
  `:64-71`, `:92-99`). A Cognito check here would break Slack.
- Health checks must also stay open — the ALB target groups check `/health`
  (`setup_aws_infrastructure.py:35-37,544`), and the deploy smoke tests curl
  `/health`, `/ai/health`, `/slack/health` unauthenticated
  (`deploy-backend.yml:195,387`, `deploy-slack-service.yml:190`).

### 1.3 Server-to-server calls (not a browser user)

`ai_conversation_service` calls `projects_service` over plain HTTP with **no credential
of any kind** — `services/projects_service_client.py`:

- `push_sibling_scores` → `PUT {base}/context-tree/nodes/{node_id}/sibling-scores` (`:40-54`)
- `get_node_id_for_conversation` → `GET {base}/context-tree/projects/{project_id}/nodes` (`:82-85`)
- `get_project_node_ids` → same URL (`:108-111`)
- `get_sibling_node_ids` → `GET {base}/context-tree/nodes/{node_id}` (`:126-129`)
- `get_project_metadata` → `GET {base}/projects/{project_id}` (`:22,150-157`)

`base_url` is `PROJECTS_API_URL` (`core/config.py:29`), which the deploy workflow sets
to the **public** ALB DNS (`deploy-backend.yml:247-253,286-288`). Three of these five
run with **no user request in flight**:

1. `ReindexTrigger._refresh_graph_links` (`services/reindex_trigger.py:66-140`) calls
   `get_project_node_ids`, `get_sibling_node_ids` and `push_sibling_scores`. It is
   reached from a debounced/idle flush inside the AI service
   (`services/.../service.py:872-915`).
2. The startup backfill `reindex_stale_conversations`
   (`services/reindex_backfill.py:8-79`), launched as a bare `asyncio.create_task` in
   the lifespan (`main.py:96-106`) — no request context at all.
3. `TreeAnalysisService` (constructed at `main.py:75-79`) reached from
   `POST /ai/tree-analysis/organize-node`, which *does* have a user request but is
   currently called with a client-supplied tree.

There is also a `projects_service → ai_conversation_service` direction implied by
`AI_SERVICE_URL` (`projects_service/core/config.py:13`, set at
`deploy-backend.yml:64,94-96` and refreshed by
`setup_aws_infrastructure.py:826-934`); the cascading project delete removes
conversations through the context-tree service (`api/v1/projects.py:75-85`).

### 1.4 Where data lives

- **Mongo `pami`** database, Beanie documents: `projects` (`models/project.py:22-23`),
  `tasks` (`models/task.py:19-23`), `context_tree` (`models/context_tree.py:43-51`),
  `conversation_chunks` (`models/conversation_chunk.py:22-34`),
  `conversation_index_state` (`models/conversation_index_state.py:22-35`).
- **S3 transcripts**, flat and *not* namespaced by project or user:
  `conversations/{conversation_id}.json`
  (`ai_conversation_service/.../service.py:207,276,784`), in bucket
  `pami-ai-conversations-us-east-1` (`setup_aws_infrastructure.py:404`).
- `list_conversations_for_project` (`service.py:750-772`) works by calling
  `_load_all_conversations` (`service.py:647-700`), which does
  `list_objects_v2(Prefix="conversations/")` over the **whole bucket** and then filters
  in-process on `project_id` (`service.py:764`). Every user's transcript is read to
  answer one user's list request. This is a correctness-and-cost problem today and an
  authorization smell once there are tenants (see §4.4).
- The one and only project scoping in retrieval is the vector-search filter
  `{"project_id": project_id}` at
  `ai_conversation_service/.../services/chunk_index_service.py:102` (and the in-process
  fallback at `:294-296`).

### 1.5 Transport reality (matters for tokens)

- The ALB listener is **HTTP on port 80 only**
  (`setup_aws_infrastructure.py:582-587`), and it is `internet-facing`
  (`setup_aws_infrastructure.py:487-494`). HTTPS is provided by an API Gateway HTTP API
  in front of it (`setup_aws_infrastructure.py:628-751`), whose `$default` route is an
  `HTTP_PROXY` integration to `http://{lb_dns}` (`:717-723`).
- Consequence: the **ALB is reachable directly, over plaintext HTTP, by anyone on the
  internet**. Any authorization enforced only at API Gateway can be bypassed by
  addressing the ALB. This is the single most important constraint on the design in §5.
- API Gateway CORS already allows the `Authorization` header
  (`setup_aws_infrastructure.py:785-791`), and all three FastAPI apps use
  `allow_headers=["*"]` with `allow_credentials=True`
  (`projects_service/main.py:78-84`, `ai_conversation_service/main.py:133-139`,
  `slack_service/main.py:12-18`). Origins are an explicit list, deliberately not `*`
  (`projects_service/core/config.py:15-22`).

---

## 2. Cognito design

### 2.1 User pool only — no identity pool

A Cognito **user pool** is needed (sign-up, sign-in, JWTs). A Cognito **identity pool**
is *not* needed and should not be created. Identity pools exist to exchange a user's
token for temporary AWS IAM credentials so the browser can call AWS services directly.
Nothing in this app does that: the browser talks only to the three FastAPI services
(`frontend/src/api/axios.js:11-26`), and S3 access happens server-side inside the AI
service with the task role (`ai_conversation_service/core/config.py:19-25`). Adding an
identity pool would also require creating IAM roles, which the Learner Lab forbids
(§10.3).

### 2.2 Pool configuration

| Setting | Value | Why |
|---|---|---|
| Sign-in alias | **email** (`UsernameAttributes: ["email"]`) | The requirement is "add another user **by email address**". With email as the username alias, email is unique in the pool and is the natural identifier. |
| Required attributes | `email` | |
| Auto-verified attributes | `email` | Verification link/code by Cognito's default email sender (50 msgs/day, no SES setup) — sufficient for an academic project. |
| MFA | Off | Out of scope. |
| Password policy | min 8, upper + lower + digit, symbols **not** required | Cognito's default minus symbols; keeps demo accounts usable. |
| Self sign-up | **Enabled** | Otherwise nobody but the owner can ever get an account, and sharing by email is pointless. See §12 for the alternative (admin-created users only). |
| Account recovery | Verified email | Makes the "forgot password" flow the login page currently disclaims (`LoginPage.js:109-113`) actually buildable. |
| Groups | one group, `admins` | See §8. |
| App client | **public SPA client, no client secret**, `ALLOW_USER_SRP_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` | A browser cannot keep a secret. SRP means the raw password never leaves the browser. |
| Token validity | ID 60 min, access 60 min, refresh **30 days** | Long refresh so a demo session survives; short ID/access limits the blast radius of a stolen token. |
| `PreventUserExistenceErrors` | `ENABLED` | Login failures do not disclose whether an email is registered. Relevant again in §7.4. |

### 2.3 Hosted UI vs custom form — recommendation: keep the custom form

**Recommendation: keep `LoginPage.js` and drive Cognito from the SPA with the Amplify v6
auth module (`aws-amplify@^6`, `signIn` / `fetchAuthSession` / `signOut`).** Do not
adopt the Hosted UI.

Reasons:

- The login page is already fully built and styled — logo, password reveal button with
  correct `aria-pressed`, inline `role="alert"` errors, the assistant tip bubble
  (`LoginPage.js:27-124`, `LoginPage.css`). The Hosted UI throws all of that away and
  replaces it with an AWS-branded page that can only be restyled with a CSS upload.
- Hosted UI needs a Cognito domain plus exact callback/logout URLs. The Amplify frontend
  URL is `https://main.{defaultDomain}` derived at deploy time
  (`setup_aws_infrastructure.py:1068,1124`) and the CORS list currently hardcodes
  `https://main.d3f2b6kjsfplgr.amplifyapp.com` (`projects_service/core/config.py:21`).
  Every lab rebuild would mean re-registering callback URLs — one more thing to go stale,
  in a project that already has a documented history of stale-URL breakage
  (`slack_service/core/config.py:11-13`).
- The SPA needs no redirect round-trip, so `/dashboard` deep links keep working with the
  existing SPA rewrite rule (`setup_aws_infrastructure.py:946-952`).

What you give up by not using Hosted UI: ready-made sign-up, confirm-code,
forgot-password and social-IdP screens. Those must be built as three small pages
(`/signup`, `/confirm`, `/forgot`) calling `signUp` / `confirmSignUp` /
`resetPassword`. That is roughly a day of frontend work and is the honest cost of
keeping the designed login page.

If Amplify v6 feels too heavy for a CRA app (it is a large dependency and CRA 5 +
Amplify 6 needs no polyfills but does add ~200 KB gzipped), the narrower alternative is
`amazon-cognito-identity-js` alone: same SRP login, no Amplify config object, but you
hand-roll token refresh. **Verdict: `aws-amplify@6`** — automatic refresh via
`fetchAuthSession()` is worth the bytes, because hand-rolled refresh is the classic
source of "randomly logged out" bugs. Note the frontend currently has only four runtime
dependencies besides React (`frontend/package.json:5-14`), so this is the single
biggest dependency addition in the project.

### 2.4 Token storage in the browser

Amplify v6 stores tokens in `localStorage` by default. **Recommendation: accept the
default, and document the tradeoff.**

- `localStorage` is readable by any JavaScript that runs on the origin, so an XSS bug
  becomes a full account takeover with a 30-day refresh token.
- In-memory only (Amplify's `sessionStorage`/custom store) removes that, at the cost of
  logging the user out on every page refresh — unacceptable for a demo where the grader
  reloads the page.
- The genuinely safe option — httpOnly `Secure` cookies — requires a backend
  token-exchange endpoint and same-site cookie handling across the API Gateway origin
  and the Amplify origin. That is a disproportionate amount of machinery here.
- Mitigating facts, verified: the app has **no** `dangerouslySetInnerHTML` anywhere in
  `frontend/src` (grepped), so React's default escaping holds; and the app already
  stores non-secret state in `localStorage`
  (`AppSidebar.jsx:31`, `ChatViewPage.js:84,142`, `GraphCanvas.jsx:18,132`).
- **Logout must clear more than the tokens.** `signOut()` clears Amplify's keys, but
  `pami.assistantAvatar` (`HomePage.js:603,714,723`, read in `AppSidebar.jsx:29-35`) and
  the graph pin keys (`useForceGraph.js:37,48`) are not user-scoped and would bleed from
  one account to the next on a shared browser. Logout should remove the `pami.*` keys.

---

## 3. Token verification in FastAPI

### 3.1 Verify the ID token, not the access token

Cognito issues three tokens. The **access token** carries `sub`, `client_id`, `scope`,
`username` and `cognito:groups` — but **not `email`**. The **ID token** carries `sub`,
`aud` (= app client id), `email`, `email_verified` and `cognito:groups`.

This design needs the email on every request (sharing resolves people by email, §7; the
admin gate is defined in terms of an email address, §8). Getting email from an access
token means an `AdminGetUser` call per request — an extra AWS round trip on a path where
Learner Lab permissions are already uncertain (§10.3).

**Recommendation: services verify the Cognito *ID token*** (`token_use == "id"`,
`aud == COGNITO_CLIENT_ID`). The usual objection — "ID tokens are for the client, access
tokens are for APIs" — applies to third-party APIs; here the SPA and the API are one
application with one audience, which is the standard Cognito-with-your-own-backend
pattern. The `users` mirror collection (§4.3) stores `sub → email`, so switching to
access tokens later is a one-file change in the auth module, not a data migration.

### 3.2 Validation rules

For every request:

1. Extract the bearer token from `Authorization: Bearer <jwt>`.
2. Read the unverified header's `kid`; look it up in the JWKS from
   `https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json`.
3. Verify the **RS256 signature** against that key.
4. Verify `iss == https://cognito-idp.{region}.amazonaws.com/{user_pool_id}`.
5. Verify `aud == cognito_client_id` (ID token) — the guard against a token minted by a
   different app client in the same pool.
6. Verify `token_use == "id"` — the guard against an access token being replayed where an
   ID token is expected, and vice versa.
7. Verify `exp` / `iat` with **`leeway=60` seconds** for clock skew. Fargate clocks are
   NTP-synced, so 60 s is generous; without any leeway a token minted at the boundary can
   be rejected as "not yet valid".
8. Require `email_verified is True` before trusting `email` for anything that grants
   access (the admin gate, invite claiming). An unverified email is an unproven claim to
   an identity.

### 3.3 Library recommendation

**`PyJWT[crypto] >= 2.9`** — `jwt.PyJWKClient` does JWKS fetch, `kid` lookup and caching
in one small class, and PyJWT is already the most common transitive JWT library so it
adds little. (`python-jose` also works but is less actively maintained; `authlib` is
heavier than needed.)

**JWKS caching and cold start.** `PyJWKClient` is synchronous and does a blocking HTTPS
GET on the first token it sees. In an async FastAPI worker that blocks the event loop for
the length of that request. Two mitigations, use both:

- Prime the cache in the `lifespan` (`projects_service/.../main.py:23-67`,
  `ai_conversation_service/.../main.py:40-117`) — fetch the JWKS once at startup, before
  `yield`, and log a warning rather than failing to boot if Cognito is unreachable
  (the ALB health check must still pass, `setup_aws_infrastructure.py:544`).
- Construct the client with `cache_keys=True, lifespan=3600` and call it via
  `starlette.concurrency.run_in_threadpool` so a cache miss (key rotation) never blocks
  the loop.

Note the ECS deploy already rolls tasks with a circuit breaker and a `/health` smoke
check (`deploy-backend.yml:180-204`), so a boot-time JWKS failure that *did* fail the
health check would auto-roll-back — which is why the warning-not-crash behaviour matters.

### 3.4 The shared dependency

One new module per service, identical in shape:

- `projects_service/src/projects_service/core/auth.py`
- `ai_conversation_service/src/ai_conversation_service/core/auth.py`
- `slack_service/src/slack_service/core/auth.py`

Exporting `CurrentUserDep` from each service's existing `dependencies.py`
(`projects_service/.../dependencies.py:33` already establishes the
`Annotated[..., Depends(...)]` house style with `ContextTreeServiceDep`).

Illustrative sketch (not a patch):

```python
# core/auth.py
class AuthSubject(BaseModel):
    user_id: str          # Cognito `sub` - the durable identity
    email: str            # verified email, lowercased
    groups: list[str] = []
    is_admin: bool = False

_jwks = PyJWKClient(settings.cognito_jwks_url, cache_keys=True, lifespan=3600)

async def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> AuthSubject:
    try:
        key = await run_in_threadpool(_jwks.get_signing_key_from_jwt, credentials.credentials)
        claims = jwt.decode(
            credentials.credentials, key.key, algorithms=["RS256"],
            audience=settings.cognito_client_id, issuer=settings.cognito_issuer,
            leeway=60,
        )
    except PyJWTError:
        raise HTTPException(401, "Not authenticated")
    if claims.get("token_use") != "id" or not claims.get("email_verified"):
        raise HTTPException(401, "Not authenticated")
    groups = claims.get("cognito:groups") or []
    email = claims["email"].strip().lower()
    return AuthSubject(
        user_id=claims["sub"], email=email, groups=groups,
        is_admin="admins" in groups or email in settings.admin_emails_list,
    )

CurrentUserDep = Annotated[AuthSubject, Depends(current_user)]
```

Note `HTTPException(401, ...)` with a fixed detail string, matching the existing habit of
never returning internal messages to callers
(`ai_conversation_service/api/v1/ai_conversations.py:41-47`).

---

## 4. Data model changes

### 4.1 Option A — embedded members on `Project` (recommended)

```python
class ProjectRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"

class ProjectMember(BaseModel):
    user_id: str            # Cognito sub
    email: str              # lowercased, for display and revoke-by-email
    role: ProjectRole
    added_at: datetime
    added_by: str           # user_id of the inviter

class PendingInvite(BaseModel):
    email: str              # lowercased; no account yet
    role: ProjectRole = ProjectRole.MEMBER
    invited_by: str
    invited_at: datetime

class Project(Document):
    name: str
    goal: str
    status: ProjectStatus
    color: Optional[str] = None
    owner_id: str                                   # NEW - denormalised, always == the OWNER member
    members: list[ProjectMember] = []               # NEW - includes the owner
    pending_invites: list[PendingInvite] = []       # NEW
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "projects"
        indexes = [
            IndexModel([("members.user_id", ASCENDING)], name="member_user"),
            IndexModel([("pending_invites.email", ASCENDING)], name="pending_email"),
        ]
```

The owner is **also** a row in `members` with `role=owner`. That single decision makes
"list my projects" one query with one multikey index:

```python
Project.find({"members.user_id": caller.user_id})
```

`owner_id` is kept as a scalar because "am I the owner" is checked on every destructive
operation and reading a scalar is clearer than scanning the array.

Note `Project` currently declares **no `Settings.indexes` at all**
(`models/project.py:22-23`) — unlike `Task` (`models/task.py:19-23`) and
`ContextTreeNode` (`models/context_tree.py:43-51`), which both have project indexes with
comments explaining that the un-indexed version was a full collection scan. So this adds
the first indexes the collection has ever had, and the same reasoning applies: without
`member_user`, every dashboard load scans `projects`.

### 4.2 Option B — a separate `project_members` collection

```
{ _id, project_id, user_id, email, role, added_at, added_by }
indexes: unique (project_id, user_id); (user_id)
```

"List my projects" becomes two round trips: query `project_members` by `user_id`, then
`Project.find({"_id": {"$in": ids}})`.

| | A (embedded) | B (separate collection) |
|---|---|---|
| "list my projects" | 1 query, 1 index | 2 queries |
| Membership change | atomic single-document `$push`/`$pull` | separate doc; project + membership can diverge |
| Project delete cleanup | free — membership dies with the document | must also delete membership rows; the cascade at `api/v1/projects.py:75-91` grows another step that can be forgotten |
| Scales to | tens of members per project | thousands |
| "who is a member of X" | read one document | indexed query |

**Recommendation: Option A.** The 16 MB document limit permits tens of thousands of
members; this app has 2 projects and single-digit users. Option B's only real advantage
is very large membership lists, which will never happen, and it costs an extra
cross-collection consistency obligation in a codebase that has already been bitten by
partial cascades (see the comment at `api/v1/projects.py:67-74` explaining that the
delete used to leave nodes, tasks, transcripts and chunks orphaned).

### 4.3 New `users` mirror collection

```python
class User(Document):            # projects_service owns it
    user_id: str                 # Cognito sub
    email: str                   # lowercased
    created_at: datetime         # first time we saw them
    last_seen_at: datetime
    class Settings:
        name = "users"
        indexes = [
            IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique"),
            IndexModel([("email", ASCENDING)], unique=True, name="email_unique"),
        ]
```

Upserted by `POST /users/me/session` which the SPA calls once right after login. Its jobs:

1. **Resolve email → user_id for sharing without calling Cognito at all** (§7) — this is
   what removes the hard dependency on `cognito-idp:ListUsers` permissions.
2. Power the admin dashboard's project counts (§8) with a `$unwind`-free aggregation over
   `projects.members.user_id`.
3. Let the AI service render "who said this" later without a Cognito call.

It is a **mirror, not the source of truth**: Cognito owns identity. A user who signs up
but never logs in exists in Cognito and not here — which is exactly why §8 prefers
Cognito `ListUsers` for the admin list when the permission allows it.

### 4.4 Knock-on effects: nodes, tasks, conversations, chunks

**No new user field on any of them.** They all already carry `project_id`
(`ContextTreeNode.project_id` `models/context_tree.py:35`, `Task.project_id`
`models/task.py:15`, `ConversationChunk.project_id`
`models/conversation_chunk.py:13`, `ConversationIndexState.project_id`
`models/conversation_index_state.py:13`, and the S3 transcript body
`service.py:199`). Access is **inherited from the project**. Duplicating an owner onto
every child means five places to keep in sync on transfer and five places to get wrong.

The security property this design rests on is therefore exactly one sentence:

> **`project_id` is never taken from a client without a membership check, and every
> resource lookup by child id resolves to a `project_id` that is then checked.**

Per query path:

- **`GET /context-tree/projects/{project_id}/nodes`, `GET|POST /tasks/projects/{project_id}/tasks`,
  `POST /context-tree/projects/{project_id}/nodes`** — `project_id` is in the path.
  Check membership on that id before the handler body runs. Repository queries are
  unchanged.
- **`GET|PUT|DELETE /context-tree/nodes/{node_id}` and `/tasks/{task_id}`** — no project
  in the path. Load the document, read `project_id`, check membership, then act. This is
  one extra read on the delete path, which already does several
  (`api/v1/context_tree.py:83-100`).
- **Vector search filter (`chunk_index_service.py:102`)** — unchanged:
  `{"project_id": project_id}`. It stays correct *because* `project_id` now arrives from
  the stored conversation (`services/.../service.py:367`) after an authorization check,
  never from the request body. Same for the in-process fallback (`:294-296`) and
  `chunks_for_conversations` (`:169-172`). No new field, no new index. The existing
  `project_conversation` index (`models/conversation_chunk.py:30-33`) is still the right
  one.
- **`read_window` (`chunk_index_service.py:188-207`)** — already takes an optional
  `project_id` to "enforce scoping here" (`:195`). Once auth exists, callers should
  **always** pass it, and the parameter should stop being optional.
- **`conversation_similarities`, `conversation_ids_for_nodes`, `headers_for_nodes`
  (`chunk_index_service.py:209-269`)** — all already filter by `project_id`. Unchanged.
- **S3 key layout** — **keep `conversations/{conversation_id}.json` flat.** Re-keying to
  `projects/{project_id}/conversations/{id}.json` would require copying every object and
  updating three code sites (`service.py:207,276,784`) and buys nothing: S3 is never the
  authorization boundary here, the API is. What *should* change is the listing path.
  `list_conversations_for_project` (`service.py:750-772`) currently scans the entire
  bucket via `_load_all_conversations` (`service.py:647-700`) and filters in memory. With
  tenants that means one user's request reads every other user's transcript into the
  service process. Replace it with a query over `ConversationIndexState` filtered by
  `project_id` (the `project` index already exists,
  `models/conversation_index_state.py:30`) and fetch only the matching objects. This is a
  performance fix and an authorization-hygiene fix in one, and it is a **prerequisite**,
  not a nice-to-have.

---

## 5. Authorization enforcement

### 5.1 The rule

> A caller may read or write a project-scoped resource if and only if there is an entry
> in that project's `members` with the caller's `user_id`. Additionally, operations
> marked *owner-only* require that entry's `role == owner`.

### 5.2 Role capabilities

| Operation | Owner | Member |
|---|---|---|
| See the project in `GET /projects/` | yes | yes |
| Read nodes, tasks, conversations | yes | yes |
| Create nodes, tasks, conversations; send messages | yes | yes |
| Update node/task content, colours, sibling scores | yes | yes |
| Rename the project / change goal, status, colour (`PUT /projects/{id}`) | yes | **no** |
| Delete the project (`DELETE /projects/{id}`) | yes | **no** |
| Invite another user | yes | **no** |
| Remove a member | yes | **no** — but a member may remove *themselves* (leave) |
| Transfer ownership | yes | no |

Rationale: the requirement says "both can work in it", which is about the content, not
about the project's existence. A member who can delete the project can destroy the
owner's data and its whole cascade (`api/v1/projects.py:60-96`) — including S3
transcripts, which are not recoverable from the app. Invite-others is owner-only for the
same reason: it keeps the membership graph a star, so "who can see my data" is answerable
by looking at one list. Both are cheap to relax later; neither is cheap to un-relax.

Deleting a *node* is allowed for members even though it destroys a conversation, because
node lifecycle is the working surface (`api/v1/context_tree.py:83-100`) — a member who
cannot delete a node they created cannot really "work in" the project.

### 5.3 Where it is enforced, so it cannot be forgotten

Three layers, deliberately redundant:

1. **Authentication by default, at router inclusion.** In each `main.py`, attach the auth
   dependency to the router rather than to individual endpoints:

   ```python
   app.include_router(projects_router, dependencies=[Depends(current_user)])
   ```

   A newly added endpoint is then authenticated whether or not its author remembered.
   `/health` stays outside (it is declared on `app`, not a router:
   `projects_service/main.py:92-94`, `ai_conversation_service/main.py:152-171`,
   `slack_service/main.py:26-28`). In `slack_service` the Slack-callback routes must be
   split into a **second router with no auth dependency** — `POST /slack/events`,
   `/commands`, `/interactions` (`api/v1/slack.py:35,58,86`) — since they authenticate
   via Slack's signature instead.

2. **Authorization as an explicit dependency on the resource.** A small module
   `core/authz.py` in `projects_service`:

   ```python
   async def require_project_member(project_id: str, caller: CurrentUserDep, ...) -> ProjectMember
   async def require_project_owner(project_id: str, caller: CurrentUserDep, ...) -> ProjectMember
   async def require_node_access(node_id: str, ...)   # loads node -> project_id -> member check
   async def require_task_access(task_id: str, ...)
   ```

   FastAPI binds `project_id` / `node_id` from the path automatically, so the endpoint
   signature grows one line and the handler body is untouched. Returning 404 (not 403)
   for a project the caller is not a member of is preferable: 403 confirms the project
   exists.

3. **Threaded into the service layer for the queries that must be scoped.**
   `ProjectService.list_projects()` (`services/project_service.py:64-82`) becomes
   `list_projects(user_id)` and the repository's `list_all()`
   (`data/project_repository.py:45-51`) becomes `list_for_user(user_id)`. `find_all()`
   should be **deleted**, not left available — the admin dashboard needs a different
   query anyway (§8), and leaving an unscoped lister in the repository is how the
   scoping gets bypassed by the next feature.

4. **A route-inventory test that fails on omission.** An integration test that walks
   `app.routes`, and for every route not on an explicit allowlist
   (`/health`, `/slack/events`, `/slack/commands`, `/slack/interactions`, `/`,
   `/docs`, `/openapi.json`) asserts that (a) the route's dependant tree contains
   `current_user`, and (b) if any path parameter is named `project_id`, `node_id`,
   `task_id` or `conversation_id`, it also contains one of the `require_*` dependencies.
   This is the mechanism that makes "cannot be forgotten" true rather than aspirational,
   and it is cheap: one test, no infrastructure.

### 5.4 The AI service, specifically

The AI service is where the IDOR risk actually lives, because it takes ids from clients
and has no membership data of its own.

- `POST /ai/ai-conversations/` (`api/v1/ai_conversations.py:30-47`) trusts
  `request.project_id` **and** `request.context_node_id`
  (`schemas/ai_conversation_schemas.py:5-8`). Both must be validated: the caller must be
  a member of `project_id`, **and** the node must belong to that project. The second
  check matters — without it a member of project A can attach a conversation to a node in
  project B, which then pollutes B's graph via the sibling-score push
  (`services/reindex_trigger.py:121-136`).
- `POST /ai/ai-conversations/{conversation_id}/messages` (`:50-70`),
  `GET /ai/ai-conversations/{conversation_id}` (`:73-96`),
  `DELETE` (`:172-192`), `reindex/{conversation_id}` (`:155-169`): load the transcript
  first, take `conversation.project_id` from it (the code already does this internally at
  `service.py:367,445`), then authorize. Conversation ids are UUIDs
  (`service.py:245-254`), so they are not enumerable — but "unguessable" is not
  "authorized".
- `GET /ai/ai-conversations/project/{project_id}` (`:119-134`) and
  `POST /ai/ai-conversations/context-retrieval/search` (`:137-152`) take `project_id`
  directly. Authorize before the call. The search endpoint should also stay behind
  `enable_retrieval_debug_api` (default `False`, `core/config.py:56`) — defence in depth,
  since its whole purpose is to dump snippets from across a project.
- `GET /ai/ai-conversations/node/{context_node_id}` (`:99-116`) — resolve the node to its
  project via `projects_service` (there is already a client method shaped for this,
  `projects_service_client.py:98-119`), then authorize.
- `POST /ai/tree-analysis/organize-node` (`api/v1/tree_analysis.py:14-39`) accepts
  `node_id`, `conversation_id` **and a whole `current_tree`** from the client
  (`schemas/tree_analysis_schemas.py:15-18`). Authorize on the conversation's project,
  and treat `current_tree` as untrusted input that must not be used to reach content —
  it is only prompt material, so the worst case is the caller poisoning their own prompt,
  but the node ids in the response should be intersected with the project's real nodes
  before anything is written.

**How the AI service performs the check.** It has no `projects` collection. Add one
service-authenticated endpoint on `projects_service`:

```
POST /internal/authz/check        (service credential, not a user token)
body:  { "user_id": "...", "project_id": "..." }
200:   { "allowed": true, "role": "member" }
```

The AI service calls it through `ProjectsServiceClient` (a sixth method alongside the
five at `projects_service_client.py:24-174`) with a short TTL cache
(60 s, keyed on `user_id + project_id`) so a chat turn does not make the same call five
times. Cache TTL is the revocation lag; 60 s is acceptable and must be stated in §7.5.

Rejected alternative: mirroring membership into the AI service's Mongo (it shares the
same `pami` database, `ai_conversation_service/core/config.py:32-33`, so it *could* read
the `projects` collection directly). Rejected because it makes the AI service depend on
another service's schema — the sort of coupling that turns a `Project` field rename into
a cross-service outage. The HTTP check keeps ownership of the rule in one service.

---

## 6. Service-to-service authentication

### 6.1 Options

| Option | Works with no user in flight | New AWS surface | Complexity |
|---|---|---|---|
| **Shared secret header** (`X-Service-Key`) | yes | none | trivial |
| Cognito **client-credentials** (resource server + confidential app client) | yes | resource server, second app client, token cache | moderate; **UNVERIFIED** whether the lab allows `CreateResourceServer` |
| On-behalf-of: forward the user's ID token | **no** | none | low, but does not cover the background paths |

### 6.2 Recommendation: shared secret header, with the user token forwarded where one exists

**Use a shared secret.** Add `SERVICE_KEY` to both services' settings
(`projects_service/core/config.py`, `ai_conversation_service/core/config.py`), sourced
from a new GitHub secret and injected into both task definitions exactly like
`MONGODB_URL` and `OPENAI_API_KEY` are today (`deploy-backend.yml:88-97,276-293`).
`projects_service` accepts it on:

- the five endpoints `ProjectsServiceClient` already calls
  (`projects_service_client.py:40,82,108,126,150`), and
- the new `POST /internal/authz/check`.

The dependency is `AuthSubjectDep`-shaped: a single `require_caller` that returns either
a user `AuthSubject` (valid Cognito ID token) or a `ServiceCaller` (valid `X-Service-Key`,
compared with `hmac.compare_digest`). Endpoints that must accept both — chiefly
`PUT /context-tree/nodes/{node_id}/sibling-scores`
(`api/v1/context_tree.py:53-68`), which is only ever called by the AI service today
(`projects_service_client.py:40`) — declare the union type. `POST /internal/authz/check`
accepts **service only**; a user must never be able to ask "is someone else a member".

Why not client-credentials: it needs a Cognito resource server plus a second (confidential)
app client, a token cache with refresh, and it adds a Cognito API dependency to the
background paths — all to solve a problem the shared secret already solves in a
same-account, single-team, academic deployment. The honest cost of the shared secret is
that it is a bearer credential with no expiry and no audience binding, travelling over
**plaintext HTTP** because `PROJECTS_API_URL` is the ALB's HTTP endpoint
(`deploy-backend.yml:252`, listener at `setup_aws_infrastructure.py:582-587`). Within one
VPC and one account that is an acceptable academic risk; it must be written down, and the
key must be rotated whenever the lab is rebuilt (the `NEW_LAB_CHECKLIST.md` already exists
for exactly this class of chore).

**Where the user token is also forwarded.** For the one call chain that *does* have a user
request in flight — `organize-node` → `get_project_node_ids` — forward the user's ID token
as well, so `projects_service` can double-check membership rather than trusting the AI
service's word. Cheap, and it means a bug in the AI service's authorization cannot
silently grant cross-project reads.

### 6.3 Background tasks

Three paths run with no user request and therefore run **as the service**:

| Path | Code | Auth |
|---|---|---|
| Debounced/idle reindex → sibling-score push | `services/.../service.py:872-915` → `services/reindex_trigger.py:66-140` | service key |
| Startup backfill | `services/reindex_backfill.py:8-79`, launched at `main.py:96-106` | service key |
| AI organize (tree analysis) | `services/tree_analysis_service.py`, from `api/v1/tree_analysis.py:14-39` | service key **plus** forwarded user token |

None of them needs to know *which* user triggered the work — they operate on a
`conversation_id`/`project_id` that was already authorized when the message was accepted.
This is the argument for the service key over on-behalf-of forwarding: the startup
backfill literally has no user to be on behalf of, and giving it a long-lived user token
would be worse than a service key in every respect.

---

## 7. Sharing by email

### 7.1 API

```
POST   /projects/{project_id}/members       owner only   body { "email": "...", "role": "member" }
GET    /projects/{project_id}/members       member       -> members + pending_invites
DELETE /projects/{project_id}/members/{user_id}   owner only (or self = leave)
DELETE /projects/{project_id}/invites/{email}     owner only  (revoke a pending invite)
POST   /users/me/session                    any user     upsert users mirror + claim invites
```

`ProjectResponse` (`schemas/project_schemas.py:27-35`) gains `role` (the caller's own
role) and `member_count`, so the frontend can hide owner-only controls without a second
request. `role` is per-caller, which is the correct shape — the same project is "owner"
to one user and "member" to another.

### 7.2 Resolving an email to a user

**Recommendation: resolve against the `users` mirror (§4.3), not Cognito.**

```
lowercase(email) -> users.find_one({"email": email})
  found     -> $push into project.members  (idempotent: skip if user_id already present)
  not found -> $push into project.pending_invites (idempotent on email)
```

This needs **zero AWS permissions**, which is decisive given §10.3. The cost is that a
user who has signed up in Cognito but never logged in is not in the mirror, so inviting
them produces a pending invite instead of immediate membership — and the pending-invite
mechanism then resolves it on their first login anyway. The user-visible behaviour is
identical.

The Cognito alternatives, for the record:

- `ListUsers` with `Filter='email = "x@y.com"'` — needs `cognito-idp:ListUsers`.
- `AdminGetUser` — needs `cognito-idp:AdminGetUser`, and only works when username *is*
  the email (true here, §2.2), but throws `UserNotFoundException` for absent users, which
  is a permissions-and-error-handling path for no benefit over the mirror.

Both are **UNVERIFIED** for `LabRole` (§10.3). Use them only as an enhancement, behind a
try/except that falls back to the mirror.

### 7.3 Pending invites and claiming

`POST /users/me/session`, called by the SPA immediately after login:

1. Upsert `users` from the verified token claims (`sub`, `email`).
2. `Project.find({"pending_invites.email": caller.email})` — indexed
   (`pending_email`, §4.1).
3. For each match: `$push` a `ProjectMember` with the now-known `user_id` and `$pull` the
   invite. Atomic per project document — the key advantage of the embedded model (§4.2).
4. Return `{ user_id, email, is_admin, claimed_projects: [...] }`.

Also run the same claim inside `GET /projects/` as a belt-and-braces measure, so a client
that skips the session call still converges. It is one indexed query on a collection with
two documents.

An invite is claimed **only against a verified email** (`email_verified` is checked in
`current_user`, §3.2). Without that, anyone could sign up as `victim@example.com`, skip
verification, and inherit invites addressed to the victim.

Invites do not expire. For an academic project, an expiry timer is machinery with no
grader-visible payoff; say so rather than half-building it.

### 7.4 Information disclosure

`POST /projects/{id}/members` must return **the same response whether or not the email has
an account**: `201` with `{ "status": "added" }` vs `{ "status": "invited" }` tells the
caller whether that email is registered, which is an account-enumeration oracle — and one
that contradicts `PreventUserExistenceErrors=ENABLED` on the login path (§2.2).

**Recommendation: accept the disclosure, deliberately.** Return the distinct statuses,
because the owner genuinely needs to know whether the person can act now or has to sign
up first, and hiding it makes the UI lie ("invited" for someone who is already in). The
population is the project owner's own collaborators, and the owner already knows their
email addresses — that is how they typed them in. Write the decision down; do not let it
be an accident. If it must be closed later, the fix is a uniform `202 { "status":
"invitation recorded" }` and a members list that shows pending entries.

Second-order leak to avoid: `GET /projects/{id}/members` returns emails of everyone in the
project, to every member. That is inherent to the feature.

### 7.5 Revocation

`DELETE /projects/{project_id}/members/{user_id}` `$pull`s from `members`. Effects:

- The project disappears from that user's `GET /projects/` on their next load.
- Their existing conversations **stay in the project** — the content belongs to the
  project, not the person. This must be stated in the UI confirm dialog, because the
  alternative (deleting their conversations) silently destroys the project's memory, which
  is the entire product.
- Revocation is **not instant in the AI service**: the authz cache (§5.4) means up to 60 s
  of continued access. Acceptable; document it.
- The owner cannot be removed. Removing the last member is impossible because the owner is
  always a member.
- Any tokens the removed user holds remain valid until `exp` (≤60 min) — but they no longer
  pass the membership check, so this is not a hole.

### 7.6 UI

The project switcher already exists (`frontend/src/pages/HomePage.js:1194-1230`). Add a
"Share" entry to its per-project row (owner-only, driven by the `role` field from §7.1)
that opens a small modal: an email input, a role select fixed to "member", and a list of
current members and pending invites each with a remove button. Reuse the existing toast
provider for success/failure (`components/feedback/ToastProvider.jsx`, used at
`HomePage.js:77,81`).

---

## 8. Admin dashboard

### 8.1 The gate

**Recommendation: a Cognito group named `admins`, read from the `cognito:groups` claim,
checked server-side — with `ADMIN_EMAILS` as a configured bootstrap that defaults to
`orkerem8@gmail.com`.**

| | Hardcoded email in source | Cognito group in the token |
|---|---|---|
| Changing who is admin | code change + redeploy of all services | one `AdminAddUserToGroup` call |
| Where the truth lives | three source files | the user pool |
| Depends on lab IAM | no | needs `CreateGroup` / `AdminAddUserToGroup` at setup time (**UNVERIFIED**, §10.3) |
| Tamperable by the client | no | no — the claim is inside the signed JWT |

The group is the better design and the token already carries it, so the check costs
nothing at request time. The `ADMIN_EMAILS` setting is not a second mechanism competing
with it — it is the seed that guarantees the feature works on day one even if group
creation turns out to be blocked in the lab, and it is why `is_admin` in §3.4 is
`"admins" in groups or email in settings.admin_emails_list`. Default value:
`admin_emails: str = "orkerem8@gmail.com"` in `projects_service/core/config.py`, parsed
with the same comma-split property style as `cors_allowed_origins`
(`projects_service/core/config.py:15-30`).

Enforcement is `Depends(require_admin)` on the admin router — a 403 if `is_admin` is
false. **The client-side check is cosmetic**: hiding the sidebar item only stops an honest
user from clicking it. Anyone can `curl` the endpoint. The server check is the control.

### 8.2 Endpoints

```
GET /admin/users?limit=50&cursor=<token>     admin only
    -> { users: [ { user_id, email, email_verified, status, created_at,
                    last_sign_in_at | null, project_count, owned_count } ],
         next_cursor: "..." | null,
         source: "cognito" | "mirror" }
```

Lives in a new `projects_service/src/projects_service/api/v1/admin.py`, mounted with
`dependencies=[Depends(require_admin)]` so no individual endpoint can forget the gate.

### 8.3 Where the user list comes from

**Recommendation: Cognito `ListUsers` as the primary source, the Mongo mirror as fallback,
project counts always joined from Mongo.**

- Cognito is the only place that knows about users who signed up and never logged in, and
  the only place with `UserStatus` (`CONFIRMED` / `UNCONFIRMED` / `FORCE_CHANGE_PASSWORD`)
  and `UserCreateDate`.
- `ListUsers` is paginated with `PaginationToken` and a max `Limit` of 60. The endpoint
  passes the token straight through as `cursor` rather than looping server-side, so the
  page never blocks on a large pool.
- **`last_sign_in_at` is not available from Cognito.** `ListUsers` returns
  `UserLastModifiedDate`, which changes on password change, attribute update and
  admin action — it is *not* a sign-in timestamp. Do not label it as one. Instead show
  `last_seen_at` from the `users` mirror (§4.3), which is truthful: "last time this user
  used PAMI". This is the kind of field that quietly becomes a lie if copied from the
  wrong source.
- If the Cognito call raises `AccessDeniedException` (the LabRole risk, §10.3), fall back
  to the mirror and set `source: "mirror"`, with the UI showing a banner explaining that
  the list covers users who have signed in at least once. Degrading visibly beats failing.
- `project_count` / `owned_count` come from one aggregation over `projects`:
  `$unwind: "$members"`, `$group` by `members.user_id`, counting all and counting where
  `role == "owner"`. With two projects this is trivial; the `member_user` index (§4.1)
  keeps it sane if it grows.

### 8.4 Frontend

- New page `frontend/src/pages/AdminUsersPage.js` at route `/admin/users`, added to
  `App.js:14-25`.
- Sidebar entry in the existing `items` array
  (`AppSidebar.jsx:67-73`) — the array is already the single source of nav truth and
  `active` is matched by `item.id` (`AppSidebar.jsx:86,95`), so:

  ```js
  const items = [
      { id: 'dashboard', label: 'Neural Dashboard', onClick: () => navigate('/dashboard') },
      { id: 'chats', label: 'Chat View', onClick: () => navigate('/chats') },
      { id: 'slack', label: 'Slack', icon: SLACK_LOGO, onClick: () => navigate('/slack') },
      { id: 'jira', label: 'Jira', icon: JIRA_LOGO, onClick: openJira },
      ...(isAdmin ? [{ id: 'admin', label: 'All Users', onClick: () => navigate('/admin/users') }] : []),
      { id: 'settings', label: 'Settings', disabled: true },
  ];
  ```

  `isAdmin` comes from an `AuthContext` populated by `POST /users/me/session` (§7.1) —
  **not** from decoding the token in the browser, so there is exactly one definition of
  "admin" and it is the server's.
- Route guards: `<RequireAuth>` wraps every route except `/login` (and the new
  `/signup`, `/confirm`, `/forgot`); `<RequireAdmin>` additionally wraps `/admin/users`
  and renders a "not available" panel rather than redirecting, so a shared link produces
  an explanation instead of a confusing bounce. Both are **cosmetic**; §8.1 is the control.
- `frontend/src/api/axios.js` gains one shared interceptor pair applied to all three
  clients (`axios.js:11-26`): a request interceptor that attaches
  `Authorization: Bearer <idToken>` from `fetchAuthSession()` (which refreshes
  transparently), and a response interceptor that on `401` clears the session and
  navigates to `/login`. Doing it in this one file means no page needs to know auth
  exists.

---

## 9. Migrating existing data

Reported current volume (**UNVERIFIED** — from the requester, not read from the database):
~2 projects, ~19 context nodes, ~34 conversations, plus their chunks and index state.

Because nodes, tasks, conversations and chunks all inherit access from the project (§4.4),
**the entire migration is: give each existing project an owner.** Nothing else needs a
new field.

Procedure:

1. The owner signs up in the new Cognito pool as `orkerem8@gmail.com` and logs in once, so
   `users` has their `sub` (§4.3).
2. Run a one-shot script `scripts/backfill_project_owners.py`, in the established style of
   `scripts/migrate_uuid_to_objectid.py` — `--dry-run` by default, `--apply` required to
   write, `--mongo-uri`/`--db-name` flags, and a printed plan
   (`scripts/migrate_uuid_to_objectid.py:1-31`). For every project with no `owner_id`:

   ```
   $set owner_id = <sub>
   $set members = [ { user_id: <sub>, email: <email>, role: "owner",
                      added_at: now, added_by: <sub> } ]
   ```

3. Create the indexes (`member_user`, `pending_email`, `users.user_id_unique`,
   `users.email_unique`). Beanie creates `Settings.indexes` on `init_beanie`
   (`projects_service/main.py:33-36`), so a deploy does this; the script should verify
   rather than assume.
4. Verify: `GET /projects/` as the owner returns 2 projects; as a second test account
   returns `[]`.

**Anything unclaimed.** A project with no `owner_id` after the backfill (created between
deploy and backfill, or belonging to nobody) is **invisible to every user**, because the
list query is `{"members.user_id": caller}`. That is the right failure mode — fail closed,
not open. It is also not silent: the admin dashboard should surface an `orphaned_projects`
count so the state is visible rather than mysterious. Do **not** add a fallback like
"projects with no owner are visible to everyone"; that is a data leak wearing a
convenience costume.

Orphaned *children* (a node whose `project_id` points at a deleted project) are already
possible today and unchanged by this design — they were the subject of the cascade fix
described at `api/v1/projects.py:67-74`. They stay unreachable through the API, which is
correct.

S3 transcripts need **no migration at all** — keys stay flat (§4.4) and the body already
carries `project_id` (`service.py:199`).

---

## 10. Infrastructure and deployment

### 10.1 `setup_aws_infrastructure.py`

Add one function, called from `main()` (`setup_aws_infrastructure.py:1292-1359`) between
`create_s3_bucket()` (`:1321`) and the load-balancer block, and a `cognito-idp` client in
`init_aws_clients` (`:78-138`, which currently builds `ecs, ec2, ecr, elbv2, logs, s3,
amplify, apigateway`):

```python
def create_cognito_user_pool() -> Optional[dict]:
    """Idempotent: find pami-users by name, else create it. Returns ids or None."""
    # list_user_pools(MaxResults=60) -> match Name == "pami-users"
    # create_user_pool(...)          -> UsernameAttributes=["email"], AutoVerifiedAttributes=["email"],
    #                                   Policies={PasswordPolicy: ...},
    #                                   AccountRecoverySetting=verified_email
    # create_user_pool_client(...)   -> GenerateSecret=False,
    #                                   ExplicitAuthFlows=[ALLOW_USER_SRP_AUTH,
    #                                                      ALLOW_REFRESH_TOKEN_AUTH],
    #                                   PreventUserExistenceErrors="ENABLED",
    #                                   IdTokenValidity=60, AccessTokenValidity=60,
    #                                   RefreshTokenValidity=30
    # create_group(GroupName="admins", ...)   # tolerate GroupExistsException / AccessDenied
    # returns {"user_pool_id": ..., "client_id": ...}
```

It must follow the file's established idempotency-and-degrade pattern: look up by name
first, tolerate "already exists", print via `print_success`/`print_error` (`:140-159`),
and **return `None` on failure without aborting the run** — exactly as
`create_api_gateway` does (`:748-751`: "Continuing without HTTPS"). If Cognito is
unavailable in the lab, the rest of the infrastructure must still come up.

Then extend `create_amplify_app` (`:937-1132`) so both the update path (`:978-988`) and
the create path (`:1087-1093`) set three more environment variables:

```
REACT_APP_COGNITO_USER_POOL_ID
REACT_APP_COGNITO_CLIENT_ID
REACT_APP_AWS_REGION
```

(CRA only exposes `REACT_APP_*` to the bundle, which is why the existing three follow that
prefix — `frontend/src/api/axios.js:12,18,24`. These are **not secrets**: a user pool id
and a public SPA client id are designed to be public.)

Also update `frontend/.env.example` (currently 4 lines, and note line 2 already has a bug
— `REACT_APP_SLACK_API_URL=http://127.0.0.1:8001` points at the AI service's port, not
8002) and `print_summary` (`:1135-1254`) to list the pool and the new GitHub secrets.

### 10.2 Workflows and task definitions

`deploy-backend.yml`:

- **projects-service** task def (`:88-97`) gains `COGNITO_USER_POOL_ID`,
  `COGNITO_CLIENT_ID`, `COGNITO_REGION`, `SERVICE_KEY`, `ADMIN_EMAILS`.
- **ai-conversation-service** task def (`:276-293`) gains the same Cognito three plus
  `SERVICE_KEY`.
- Resolve the pool ids from AWS at deploy time rather than storing them as secrets, in the
  same spirit as the ALB DNS lookup at `:247-253` and the account-id resolution at
  `:40-44` (whose comment explains exactly why hardcoding lab-specific ids goes stale):

  ```bash
  POOL_ID=$(aws cognito-idp list-user-pools --max-results 60 \
    --query "UserPools[?Name=='pami-users'].Id | [0]" --output text --region us-east-1)
  CLIENT_ID=$(aws cognito-idp list-user-pool-clients --user-pool-id "$POOL_ID" \
    --max-results 60 --query "UserPoolClients[?ClientName=='pami-web'].ClientId | [0]" \
    --output text --region us-east-1)
  ```

  This keeps the "one authoritative lookup, never a stale literal" pattern the file
  already commits to, and means a lab rebuild needs no secret edits for Cognito.

`deploy-slack-service.yml`:

- The slack task def (`:60-107`) gains the Cognito three plus `SLACK_SIGNING_SECRET`
  (already there, `:90-93`).
- **Pre-existing bug to fix while touching this file:** the heredoc at `:60` is
  `cat > task-def.json << 'EOF'` — **quoted**, so the shell does not expand
  `${ACCOUNT_ID}` in the `executionRoleArn`, `taskRoleArn` and `image` fields
  (`:67,68,72`). `${{ github.sha }}` still works because GitHub Actions substitutes it
  before the shell runs, but the account id is written literally. The backend workflow uses
  an **unquoted** `<< EOF` (`:67`, `:255`) and therefore expands correctly. Adding env vars
  here without fixing the quoting will produce the same silent breakage for the new
  variables. (Whether the slack deploy currently succeeds despite this was not verified —
  it may be that the service simply has not been redeployed since.)

New GitHub secrets required: `SERVICE_KEY` (§6.2). `ADMIN_EMAILS` can be a plain value in
the workflow, not a secret. The repo already documents the rotate-the-lab-credentials chore
(`setup_aws_infrastructure.py:1186-1197`, `docs/NEW_LAB_CHECKLIST.md`,
`.github/skills/pami-update-github-secrets/SKILL.md`), so `SERVICE_KEY` should be added to
that checklist.

### 10.3 Learner Lab constraints — and what is genuinely unknown

Three constraints are certain from the code and the environment:

1. **Credentials rotate every ~4 hours.** Both workflows read
   `AWS_ACCESS_KEY_ID`/`SECRET`/`SESSION_TOKEN` as secrets
   (`deploy-backend.yml:32-34`, `deploy-slack-service.yml:31-33`), and the summary shouts
   that they must be refreshed (`setup_aws_infrastructure.py:1186-1192`). Creating the
   user pool is a one-time act, so this mostly affects redeploys, not Cognito.
2. **`LabRole` is the only usable role.** Both task definitions hardcode
   `arn:aws:iam::${ACCOUNT_ID}:role/LabRole` as *both* execution and task role
   (`deploy-backend.yml:74-75,262-263`, `deploy-slack-service.yml:67-68`). No new role can
   be created, so any AWS API the services call at runtime must be permitted by `LabRole`
   as-is. This is why §7.2 recommends resolving emails from Mongo and §8.3 has a mirror
   fallback: **the design must work with zero Cognito permissions on `LabRole`.**
3. **No identity pool** (§2.1) — good, because it would need new IAM roles.

**UNVERIFIED, and the user must check:** whether the Learner Lab account permits Amazon
Cognito at all. AWS Academy Learner Labs restrict the usable service list via a policy
boundary, and I could not determine from this repository whether `cognito-idp` is inside
it. Nothing in the repo uses Cognito today, so there is no evidence either way.

Run these, in order, with lab credentials exported:

```bash
# 1. Can you even see Cognito?  AccessDenied here means the service is blocked.
aws cognito-idp list-user-pools --max-results 5 --region us-east-1

# 2. Can you create one?  (Delete it right after; this is a probe.)
aws cognito-idp create-user-pool --pool-name pami-cognito-probe \
  --region us-east-1 --query 'UserPool.Id' --output text

# 3. App client with no secret, SRP auth:
aws cognito-idp create-user-pool-client --user-pool-id <POOL_ID> \
  --client-name probe --no-generate-secret \
  --explicit-auth-flows ALLOW_USER_SRP_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --region us-east-1

# 4. Groups (needed for the preferred admin gate, §8.1):
aws cognito-idp create-group --group-name admins --user-pool-id <POOL_ID> --region us-east-1

# 5. Admin/list APIs (needed only for the ListUsers enhancement, §7.2 / §8.3):
aws cognito-idp list-users --user-pool-id <POOL_ID> --limit 5 --region us-east-1

# 6. Clean up the probe:
aws cognito-idp delete-user-pool --user-pool-id <POOL_ID> --region us-east-1
```

Separately, **UNVERIFIED**: whether the services running under `LabRole` inside ECS can
call `cognito-idp:ListUsers` at runtime (step 5 above tests the *lab user's* permissions,
not the task role's). Settle it by shelling into a running task, or simply by treating the
first `AccessDeniedException` at runtime as the answer — which the §8.3 fallback already
does.

**If Cognito turns out to be blocked**, the contingency is self-hosted auth inside
`projects_service`: a `users` collection with bcrypt password hashes and HS256 JWTs signed
with a secret from GitHub Actions. Everything downstream of §3.4 — `AuthSubject`,
`CurrentUserDep`, the membership model, sharing, the admin gate — is unchanged, because
none of it depends on *who issued* the token, only on the claims. That is the main
architectural reason to put the `AuthSubject` abstraction in `core/auth.py` rather than
sprinkling `jwt.decode` through the routers.

### 10.4 One transport gap to close

Because the ALB is internet-facing on plain HTTP (§1.5), bearer tokens travel in cleartext
on the API Gateway → ALB hop, and the ALB itself can be addressed directly. Two things
follow:

- Verification step: confirm that API Gateway's `HTTP_PROXY` integration
  (`setup_aws_infrastructure.py:717-723`) actually forwards the `Authorization` header to
  the ALB. HTTP APIs generally do, but a stripped header would present as "every request
  is 401 in production, fine locally" — an expensive thing to debug late. Test with
  `curl -H "Authorization: Bearer probe" https://<api-id>.execute-api.us-east-1.amazonaws.com/health`
  against a temporary endpoint that echoes whether the header arrived.
- Optionally attach a Cognito **JWT authorizer** to the API Gateway HTTP API as defence in
  depth. It is genuinely cheap (`aws apigatewayv2 create-authorizer --authorizer-type JWT
  --jwt-configuration Audience=<client_id>,Issuer=<issuer>`). It does **not** replace
  in-service verification, because it can be bypassed by hitting the ALB directly and it
  knows nothing about project membership. Recommended, but only after §11 Phase 2 works.

---

## 11. Implementation plan

Each phase leaves `main` deployable and the app usable.

### Phase 1 — Verify Cognito is possible (XS, ~1 hour)

Run the probes in §10.3. **Outcome:** a written yes/no on Cognito in the lab, on groups,
and on `ListUsers`. If no, switch to the §10.3 contingency before writing any code. Nothing
else in this plan is safe to start before this.

### Phase 2 — Pool + login, no enforcement (M, ~1 day)

`create_cognito_user_pool()` in `setup_aws_infrastructure.py`; Amplify env vars; new
`REACT_APP_COGNITO_*`; `aws-amplify` added to `frontend/package.json`; real `signIn` in
`LoginPage.js` replacing the `navigate('/dashboard')` at `:24`; `/signup`, `/confirm`,
`/forgot` pages; `signOut` wired to the sidebar button (`AppSidebar.jsx:112-121`) plus the
`pami.*` localStorage cleanup (§2.4); axios interceptors in `api/axios.js`; `<RequireAuth>`
in `App.js`.

**Outcome:** users really log in, tokens are attached to every request, and the backends
ignore them entirely. Nothing is broken; nothing is protected yet. This is the phase that
proves the whole Cognito path end-to-end before any data model changes.

### Phase 3 — Authenticate the backends (M, ~1 day)

`core/auth.py` + `CurrentUserDep` in all three services; routers included with the auth
dependency (§5.3); slack callbacks split into an unauthenticated router; `/health` left
open; the route-inventory test.

**Outcome:** every browser-facing endpoint returns 401 without a valid token. Data is still
shared by everyone who *has* an account. Sequenced deliberately after Phase 2 so the
frontend is already sending tokens when the backends start requiring them.

### Phase 4 — Ownership and the migration (M, ~1 day)

`Project.owner_id` / `members` / `pending_invites`; `users` mirror;
`POST /users/me/session`; `list_for_user` replacing `list_all`; `require_project_member` /
`require_project_owner` / `require_node_access` / `require_task_access` on all
`projects_service` routes; `scripts/backfill_project_owners.py`.

**Outcome:** a user sees only their own projects, and the two existing projects belong to
`orkerem8@gmail.com`. The AI service is still permissive.

### Phase 5 — Service-to-service + the AI service (M–L, ~1.5 days)

`SERVICE_KEY` in both configs, both task definitions and the new secret;
`POST /internal/authz/check`; `ProjectsServiceClient.check_access` with a 60 s cache; authz
on all nine AI endpoints (§5.4); replace `list_conversations_for_project`'s bucket scan with
a `ConversationIndexState` query (§4.4); tighten `read_window`'s `project_id` to required.

**Outcome:** no IDOR remains. Passing someone else's `project_id` or `conversation_id`
returns 404. Background reindexing and the startup backfill still work, now authenticated
as the service.

### Phase 6 — Sharing (M, ~1 day)

The five member/invite endpoints; `role` on `ProjectResponse`; the share modal in the
project switcher; invite claiming in `/users/me/session` and `GET /projects/`.

**Outcome:** the owner adds `someone@example.com`; the project appears for that person on
their next login and both can work in it.

### Phase 7 — Admin dashboard (S–M, ~0.5–1 day)

`admins` group (or `ADMIN_EMAILS`); `require_admin`; `GET /admin/users` with the Cognito
call, the mirror fallback and the project-count aggregation; `AdminUsersPage`; the sidebar
entry; `<RequireAdmin>`.

**Outcome:** `orkerem8@gmail.com` sees every user; everyone else gets 403 from the API and
no nav entry.

### Phase 8 — Hardening (S, ~0.5 day)

API Gateway JWT authorizer (§10.4); the `Authorization`-forwarding verification; the
`${ACCOUNT_ID}` heredoc fix in `deploy-slack-service.yml:60`; `SERVICE_KEY` added to
`docs/NEW_LAB_CHECKLIST.md`; `orphaned_projects` count on the admin page.

### Testing strategy

Match what the repo does — and note that the two suites differ, so match each in its own
place:

- **`projects_service`** currently mixes mock-based service tests
  (`tests/test_project_service.py:16-60`, `MagicMock(spec=ProjectRepository)`) with route-
  level tests through a real `FastAPI` app and `TestClient` over in-memory repositories
  (`tests/test_context_tree_e2e.py:60-70`). The `*_e2e.py` style is the one to extend:
  build the app, include the router, override `dependencies` (the existing test overrides
  `get_context_tree_service` — the new tests additionally override `current_user` with a
  fixed `AuthSubject`), and assert through real HTTP. CI runs these with nothing external
  (`validate.yml:60-77`).
- **`ai_conversation_service`** runs end-to-end against a real Atlas database (`pami_test`)
  with a deterministic embedder, skipping when Mongo is unreachable
  (`tests/conftest.py:26-54,96-119`; CI at `validate.yml:79-98`). New authz tests belong
  here, exercised through the real route → service → DB path.
- **Do not run the two suites concurrently** — `validate.yml:9-12` already documents that
  the AI tests share one Atlas database and must not overlap.

The tests that must exist (all integration, all through routes):

1. No token → 401 on one endpoint per router.
2. Expired token, wrong `aud`, wrong `iss`, `token_use=access`, `email_verified=false` →
   401. Sign these with a locally generated RSA key and a stubbed JWKS so no Cognito call
   is needed.
3. User A creates a project; user B's `GET /projects/` does not contain it; B's
   `GET /projects/{A_id}` is 404; B's `GET /context-tree/projects/{A_id}/nodes` is 404.
4. Member can create a node; member cannot `PUT`/`DELETE` the project (403); member can
   leave.
5. Invite an email with no account → `pending_invites`; that user signs up, calls
   `/users/me/session`, and the project appears with `role=member`.
6. AI service: B cannot `POST /ai/ai-conversations/` with A's `project_id`; cannot read
   A's conversation by id; cannot reindex it; retrieval for A's project never returns B's
   chunks (extend the existing retrieval e2e tests, which already build multi-conversation
   fixtures — `tests/conftest.py:169-189`).
7. `GET /admin/users` → 200 for the admin subject, 403 for a normal one.
8. The route-inventory test from §5.3.
9. Backfill script: a project with no `owner_id` becomes owned and listable; `--dry-run`
   writes nothing.

Also add `SERVICE_KEY` and dummy `COGNITO_*` values to `projects_service/.env.example`
(currently 11 lines) and `ai_conversation_service/.env.example` — and per house rule, do
not delete the commented-out alternatives already in those files.

---

## 12. Risks, unknowns, and decisions the user must make

### Must be decided by the user

1. **Self sign-up: open or invite-only?** §2.2 assumes open sign-up. Open means anyone
   with the Amplify URL can create an account (they see nothing until invited, but they
   consume the pool and appear in the admin list). Invite-only means the owner must
   `AdminCreateUser` each collaborator, which needs `cognito-idp:AdminCreateUser` on the
   lab credentials and makes "share by email with someone who has no account" a
   two-person chore. **Recommendation: open sign-up**, because the sharing requirement
   reads much better in a demo when the invitee can self-serve.
2. **Does the email-existence disclosure in §7.4 stay?** Recommended: yes, deliberately.
3. **May members invite others?** §5.2 says no. Say so out loud, because it is the kind of
   thing a grader asks about.
4. **What happens to a removed member's conversations?** §7.5 says they stay with the
   project. The alternative (delete them) destroys project memory and is almost certainly
   wrong, but it is the user's call.
5. **Is a 60 s revocation lag in the AI service acceptable?** (§5.4 cache.) Setting the TTL
   to 0 removes the lag and adds one HTTP call per AI request.

### Unknowns I could not settle from the code

1. **Whether Amazon Cognito is usable in this Learner Lab account at all** — the single
   largest risk. Probes in §10.3. Contingency in §10.3.
2. **Whether `LabRole` can call `cognito-idp:ListUsers` / `AdminGetUser` / `CreateGroup`
   at runtime.** The design is built to work without them (mirror-based email resolution,
   `ADMIN_EMAILS` fallback), so this degrades the admin page rather than blocking the
   feature.
3. **Whether API Gateway forwards `Authorization` to the ALB** (§10.4). Almost certainly
   yes for HTTP APIs; verify before Phase 3, not after.
4. **The exact current data volume** (~2 / ~19 / ~34) was given to me, not read from the
   database. The backfill script's `--dry-run` prints the real numbers before anything is
   written, which is the check.
5. **Whether `deploy-slack-service.yml` currently deploys successfully at all**, given the
   quoted heredoc at `:60` that leaves `${ACCOUNT_ID}` unexpanded in the role ARNs and
   image URI. This is a pre-existing condition, not caused by this design, but it sits
   directly on the path of adding env vars to that file.

### Residual risks

- **Plaintext HTTP to an internet-facing ALB** (§1.5, §10.4): tokens and the service key
  are exposed on that hop, and the ALB can be hit directly, so API-Gateway-level controls
  are decorative. Mitigated only by in-service verification. Properly fixing it means an
  ACM certificate and an HTTPS listener on the ALB, which needs a domain — out of scope
  for a lab account, and worth stating as a known limitation in the same spirit as
  `docs/sdd-conversation-context-retrieval.md`'s "Known limitation" section.
- **XSS ⇒ account takeover** via `localStorage` tokens (§2.4), bounded by no
  `dangerouslySetInnerHTML` anywhere in `frontend/src`.
- **A forgotten authz dependency on a new route.** The route-inventory test (§5.3) is the
  countermeasure; it is the difference between a rule and a hope.
- **Shared secret with no expiry** (§6.2). Rotate with the lab.
- **The `users` mirror can drift** from Cognito (a user deleted in Cognito lingers in
  Mongo and keeps their project memberships). Low impact at this scale; a periodic
  reconcile is not worth building now. Worth one sentence in the admin UI: the list is
  "users known to PAMI", not "users in Cognito", when `source == "mirror"`.
- **`aws-amplify` is a large new frontend dependency** in an app that currently has four
  (`frontend/package.json:5-14`), and CI builds the frontend on every push
  (`validate.yml:100-126`). Watch the build time.
