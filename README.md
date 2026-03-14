# CodeDocs

CodeDocs is an Enterprise-Grade Codebase Intelligence & PR Analysis Platform. It provides advanced semantic RAG search, architectural blast radius analysis, and zombie code detection to help engineering teams manage risk and navigate complex codebases.

## API Documentation

This document provides a comprehensive overview of all available endpoints in the CodeDocs API (v1.0.0). Base URL is assumed to be `http://localhost:8000` for local development.

Many endpoints are protected and require a Bearer token in the Authorization header (`Authorization: Bearer <token>`).

---

## 🔐 Authentication (`/api/auth`)

### `POST /api/auth/register`
**Summary**: Register a new user account.
* **Request Body (JSON)**: `RegisterRequest`
  * `email` (string, email, required)
  * `name` (string, 1-100 chars, required)
  * `password` (string, 8-128 chars, required)
* **Responses**:
  * `201 Created`: Returns `TokenResponse` containing `access_token`, `refresh_token`, and user details.
  * `422 Unprocessable Entity`: Validation Error.

### `POST /api/auth/login`
**Summary**: Login to an existing account.
* **Request Body (JSON)**: `LoginRequest`
  * `email` (string, email, required)
  * `password` (string, required)
* **Responses**:
  * `200 OK`: Returns `TokenResponse` containing `access_token`, `refresh_token`, and user details.
  * `422 Unprocessable Entity`: Validation Error.

### `POST /api/auth/refresh`
**Summary**: Get a new access token using a refresh token.
* **Request Body (JSON)**: `RefreshRequest`
  * `refresh_token` (string, required)
* **Responses**:
  * `200 OK`: Returns `AccessTokenResponse` containing a new `access_token`.

### `POST /api/auth/logout`
**Summary**: Blacklist the current refresh token to logout.
* **Request Body (JSON)**: `LogoutRequest`
  * `refresh_token` (string, required)
* **Responses**:
  * `200 OK`: Successful logout message.

### `GET /api/auth/me`
**Summary**: Get current authenticated user profile.
* **Security**: Bearer Token required.
* **Responses**:
  * `200 OK`: Returns current `UserResponse`.

### `PATCH /api/auth/users/{user_id}/role`
**Summary**: Update a team member's role (Owner-only endpoint). Owners cannot demote themselves to prevent admin lockout.
* **Security**: Bearer Token required (Owner role).
* **Path Parameters**:
  * `user_id` (UUID, required)
* **Request Body (JSON)**: `RoleUpdateRequest`
  * `role` (string, Enum: `"owner", "admin", "member", "viewer"`, required)
* **Responses**:
  * `200 OK`: Returns updated `UserResponse`.

### OAuth Endpoints
* `GET /api/auth/google` & `GET /api/auth/google/callback` - Google SSO flow.
* `GET /api/auth/github` & `GET /api/auth/github/callback` - GitHub SSO flow.

---

## 📦 Repositories (`/api/repos`)

### `GET /api/repos/`
**Summary**: List all repositories owned by the current user.
* **Security**: Bearer Token required.
* **Responses**:
  * `200 OK`: List of `RepoResponse` objects.

### `POST /api/repos/`
**Summary**: Add a new GitHub repository for analysis. Automatically registers a GitHub webhook if the user has connected their GitHub account.
* **Security**: Bearer Token required (min role: Member).
* **Request Body (JSON)**: `RepoCreate`
  * `github_url` (string, required)
  * `connection_type` (string, default: "public")
  * `git_username` (string, optional)
  * `git_password` (string, optional)
* **Responses**:
  * `201 Created`: Returns the newly created `RepoResponse`.

### `GET /api/repos/{repo_id}`
**Summary**: Get a specific repository by ID.
* **Security**: Bearer Token required.
* **Path Parameters**: `repo_id` (UUID)
* **Responses**: `200 OK` (`RepoResponse`)

### `DELETE /api/repos/{repo_id}`
**Summary**: Delete a repository and its associated webhooks from GitHub.
* **Security**: Bearer Token required (min role: Admin/Owner).
* **Path Parameters**: `repo_id` (UUID)
* **Responses**: `204 No Content`

### `POST /api/repos/{repo_id}/scan`
**Summary**: Manually trigger a codebase analysis/ingestion scan job.
* **Security**: Bearer Token required.
* **Path Parameters**: `repo_id` (UUID)
* **Responses**: `200 OK`

### `GET /api/repos/{repo_id}/jobs`
**Summary**: List all scan jobs for a given repository.
* **Security**: Bearer Token required.
* **Path Parameters**: `repo_id` (UUID)
* **Responses**: `200 OK` (List of `JobSummary`)

---

## ⚙️ Jobs (`/api/jobs`)

### `GET /api/jobs/{job_id}`
**Summary**: Get the exact status/progress of an asynchronous Celery scan job.
* **Security**: Bearer Token required.
* **Path Parameters**: `job_id` (UUID)
* **Responses**: `200 OK` (`JobResponse`)

### `GET /api/jobs/{job_id}/stream`
**Summary**: Server-Sent Events (SSE) endpoint to stream real-time job status updates.
* **Security**: Bearer Token required.
* **Path Parameters**: `job_id` (UUID)
* **Responses**: `200 OK` (text/event-stream)

---

## 📚 Documentation & Intelligence (`/api/docs`)

### `GET /api/docs/{repo_id}/overview`
**Summary**: Get a high-level overview of the entire repository documentation.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/docs/{repo_id}/functions`
**Summary**: List paginated, filterable functions from the repository.
* **Security**: Bearer Token required.
* **Query Parameters**:
  * `page` (integer, default: 1)
  * `limit` (max 100, default: 50)
  * `sort_by` (string, "name" or "complexity", default: "name")
  * `filter_pii` (boolean)
  * `filter_unprotected` (boolean)
  * `filter_high_complexity` (boolean)
  * `search` (string, optional)
* **Responses**: `200 OK` (List of `FunctionResponse` objects containing complexity, PII tags, code snippets, etc).

### `GET /api/docs/{repo_id}/functions/{function_id}`
**Summary**: Get detailed AST analysis for a specific function.
* **Security**: Bearer Token required.
* **Responses**: `200 OK` (`FunctionResponse`)

### `GET /api/docs/{repo_id}/blast-radius/{function_id}`
**Summary**: Calculate the downstream impact "blast radius" if this specific function is modified.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `POST /api/docs/{repo_id}/blast-radius/pr-check`
**Summary**: Analyze a raw Git Pull Request diff and return a full blast radius impact report (including risk scoring and Mermaid diagrams).
* **Security**: Bearer Token required (min role: Member).
* **Request Body (JSON)**: `PRCheckRequest`
  * `diff` (string, required - the raw git diff)
* **Responses**: `200 OK` (Returns Risk Level, affected counts, and Markdown summary)

### `GET /api/docs/{repo_id}/zombie-code`
**Summary**: Detect and return zombie (unreachable) functions in the repository that are safe to delete.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/docs/{repo_id}/diagrams`
**Summary**: List available AI-generated architecture and dependency diagrams.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/docs/{repo_id}/diagrams/{diagram_type}`
**Summary**: Get a specific generated diagram (Mermaid syntax) by type (e.g., architecture, flowchart).
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/docs/{repo_id}/entry-points`
**Summary**: List discovered API routes, CLI commands, and main application entry points.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/docs/{repo_id}/external-interfaces`
**Summary**: List all outbound external HTTP API calls made by the application codebase.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/docs/{repo_id}/file-tree`
**Summary**: Hierarchical directory map of the scanned repository.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

---

## 🛡️ Security Analysis (`/api/security`)

### `GET /api/security/{repo_id}/audit`
**Summary**: Full security audit of potential vulnerabilities.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/security/{repo_id}/auth-map`
**Summary**: A map of which endpoints are authenticated vs. unprotected.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

### `GET /api/security/{repo_id}/pii-flow`
**Summary**: Traces the flow of Personally Identifiable Information (PII) through the application.
* **Security**: Bearer Token required.
* **Responses**: `200 OK`

---

## 🔎 RAG Semantic Search (`/api/search`)

### `POST /api/search/{repo_id}/semantic`
**Summary**: Natural language codebase querying via vector embeddings. Uses `pgvector` cosine similarity to find the most relevant functions.
* **Security**: Bearer Token required.
* **Request Body (JSON)**: `SemanticSearchRequest`
  * `query` (string, required - e.g. "Where do we process user payments?")
  * `top_k` (integer, default: 5)
* **Responses**: `200 OK` (List of `SemanticSearchResult` with relevance scores, code snippets, and git blame history).

---

## 🖨️ Export (`/api/export`)

### `GET /api/export/{repo_id}/markdown`
**Summary**: Export the entire codebase documentation as a single Markdown file.
* **Security**: Bearer Token required.
* **Responses**: `200 OK` (File download)

### `GET /api/export/{repo_id}/pdf`
**Summary**: Export the entire codebase documentation as a PDF.
* **Security**: Bearer Token required.
* **Responses**: `200 OK` (File download)

---

## 🔗 GitHub Webhooks (`/api/webhooks`)

### `POST /api/webhooks/github`
**Summary**: Incoming webhook handler for GitHub events.
* Verifies `x-hub-signature-256`.
* **Events Handled**:
  * `push`: Triggers an automatic incremental scan if `auto_scan_on_push` is enabled.
  * `pull_request` (opened, synchronize): Automatically calculates Blast Radius for the diff and posts the report as a PR comment.
* **Responses**: `200 OK`
