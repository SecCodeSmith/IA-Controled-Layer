# Feature contract: resource scope (path, row, column filtering)

Binding for the backend and the Workbench dashboard. Fine-grained resource authorization beyond role-to-server mapping: per-role file-path scopes on tool arguments and row/column visibility on tool results.

## How it works

### Two-stage resource control

The Authorization stage (after role provisioning) evaluates resource scope on tool calls and results:

1. **Tool call:** `resource_scope` rule (block) checks that the tool is provisioned AND the arguments (file path, query filters) are within the role's granted scope. Mismatch → 403 `Authorization · resource_scope`.
2. **Tool result:** `resource_projection` rule (mask) filters tool results (rows matched to row-scope predicates, columns in deny list redacted). Mismatch → MASKED `Authorization · resource_projection`, reason "N row(s) filtered, M column(s) redacted: col1, col2".

### Resource configuration

In `policy.yaml`, the `resources:` section defines fine-grained grants per role and server:

```yaml
resources:
  - id: github_repo_files
    server: github
    tools: [read_file]
    path_argument: path
    roles:
      developer: { paths: { allow: ["src/**", "docs/**", "README.md"], deny: ["**/.env", "secrets/**", "**/*.pem"] } }
      "*": {}  # wildcard role (default) grants no access
  
  - id: hr_directory_rows
    server: hr-db
    tools: [query]
    records: rows
    roles:
      hr: { columns: { deny: [salary] }, rows: { region: "$identity.region" } }
  
  - id: hr_employee_record
    server: hr-db
    tools: [get_employee]
    roles:
      hr: { columns: { deny: [salary] }, rows: { region: "$identity.region" } }
```

**Fields:**

- `id`: Unique resource identifier (name)
- `server`: MCP server name (github, hr-db, ci, etc.)
- `tools`: List of tool names this grant covers; empty list means all tools on this server
- `path_argument`: Name of the argument holding the file path (e.g., `path` in `read_file(repo, path)`)
- `records`: Key holding the list of records in the result (e.g., `rows` in `{"rows": [...]}`); omit if the whole result is one record
- `roles`: Dict of role → grant mappings. A grant specifies:
  - `paths`: `{allow: [glob patterns], deny: [glob patterns]}`
    - `allow` defaults to `[]` (no restriction)
    - `deny` defaults to `[]` (no restriction)
    - **Deny wins:** If a path matches both allow and deny, it is denied
    - **Allow required:** If `allow` is non-empty, the path must match an allow pattern to pass
    - Globs: `src/**` matches `src/app.py` and `src/views/login.py`; `**/.env` matches `.env` at any level; `secrets/**` matches `secrets/key.pem`
  - `columns`: `{allow: [names] | null, deny: [names]}`
    - `allow = null` means all columns (default)
    - `allow = []` means no columns
    - `deny` defaults to `[]` (no columns redacted)
    - Applied to each record in the result
  - `rows`: Dict of `{attribute: value | [values]}` predicates
    - Matched against fields in each record
    - Supports `$identity.region`, `$identity.role`, `$identity.sub`, `$identity.location` (substituted per caller)
    - A record lacking the attribute does not match
    - Empty `rows` dict means no row filtering

### Path scope evaluation

`path_allowed(path: str, scope: PathScope) -> PathDecision`:

1. Normalize path: convert `\` to `/`, reject absolute paths and drive letters, reject `..` components, apply `posixpath.normpath`
2. Compile allow patterns (if non-empty) as regexes via `glob.translate(..., recursive=True, include_hidden=True)`
3. Compile deny patterns (same)
4. For each pattern: if allow is non-empty and path does not match, deny; if deny pattern matches, deny; else allow
5. Case-insensitive (Windows file systems)

**Returns:**

```python
PathDecision(allowed: bool, path: str, pattern: str | None, reason: str)
```

Example reasons:
- "allowed" (matches allow and no deny)
- "path denied by pattern: secrets/**"
- "path not allowed by any pattern"
- "absolute path rejected"
- "contains '..', rejected"

### Column scope evaluation

Columns in the deny list are redacted from all records. If allow is set, only those columns are preserved.

### Row scope evaluation

For each record, check if all row predicates match:

```python
record = {"name": "alice", "region": "PL", "salary": 50000}
predicate = {"region": "$identity.region"}  # caller from region PL

# After substitution:
predicate = {"region": "PL"}

# Match: record["region"] == "PL" → included
```

Multi-value predicates:

```python
predicate = {"region": ["PL", "DE"]}
# Match if record["region"] in ["PL", "DE"]
```

Missing attribute:

```python
record = {"name": "alice", "salary": 50000}  # no region
predicate = {"region": "$identity.region"}
# Mismatch: record does not have 'region' → filtered out
```

### Result projection

`project_result(data: Any, config: ResourceConfig, grant: ResourceGrant, identity: Identity) -> ProjectionResult`:

1. If `config.records` is None, treat whole `data` as one record
2. Otherwise, extract `data[config.records]` as the list of records
3. For each record:
   - Check row predicates; filter out records that do not match all predicates
   - For each column: if `grant.columns.deny` includes it, redact (→ null or omit based on format)
   - If all columns are redacted, omit the record (unreachable by this role)
4. Return `ProjectionResult(data=filtered, rows_filtered=N, columns_redacted=["col1", "col2"], changed=True|False)`

**Changed flag:** Set to True if any row was filtered or any column redacted.

**Violation reason wording:**

```
"3 row(s) filtered, 2 column(s) redacted: salary, ssn"
```

## Configuration

### Demo data

**GitHub MCP (read_file tool):**

```python
GITHUB_FILES = {
  "web-app": {
    "README.md": "...",
    "src/app.py": "...",
    "docs/runbook.md": "...",
    ".env": "DATABASE_URL=...\nAPI_KEY=sk-demo-...",
    "secrets/deploy.pem": "-----BEGIN DEMO KEY-----..."
  }
}
```

**HR Database (query and get_employee tools):**

Employees:
- E-1042: `name: "Alice", role: "junior", region: "PL"` (no salary in `get_employee`)
- E-2001: `name: "Bob", region: "PL"` (salary in query result)
- E-2101: `name: "Charlie", region: "DE"` (salary in query result)

**Policy grants:**

```yaml
- id: github_repo_files
  server: github
  tools: [read_file]
  path_argument: path
  roles:
    developer: { paths: { allow: ["src/**", "docs/**", "README.md"], deny: ["**/.env", "secrets/**", "**/*.pem"] } }

- id: hr_directory_rows
  server: hr-db
  tools: [query]
  records: rows
  roles:
    hr: { columns: { deny: [salary] }, rows: { region: "$identity.region" } }

- id: hr_employee_record
  server: hr-db
  tools: [get_employee]
  roles:
    hr: { columns: { deny: [salary] }, rows: { region: "$identity.region" } }
```

## Endpoints

Both rules live in the Authorization stage and are evaluated during normal tool-call processing. No separate endpoints; behavior is visible in:

- `/api/workbench/trace` (tool_call kind) → `stages[].violations[{rule_id: "resource_scope" | "resource_projection", reason, evidence}]`
- `/api/audit` logs with `stage: authorization, rule_id: resource_scope` or `resource_projection`
- `/api/workbench/resources` → `ResourceMatrixResponse` showing all resource configs and per-role grants

## Dashboard

### Resource Matrix card (Workbench)

Shows all resources, servers, tools, and per-role grants in a table:

| Resource | Server | Tools | Developer Grant | HR Grant | * (default) |
|----------|--------|-------|-----------------|----------|------------|
| github_repo_files | github | read_file | `src/**, docs/**, README.md (deny: **/.env, secrets/**, **/*.pem)` | (none) | (none) |
| hr_directory_rows | hr-db | query | (none) | `deny salary; rows: region=$identity.region` | (none) |
| hr_employee_record | hr-db | get_employee | (none) | `deny salary; rows: region=$identity.region` | (none) |

### Resource Simulator card (Workbench)

- **Form:** Actor (dropdown), Server, Tool, Arguments (JSON)
- **Submit:** POST /api/workbench/trace with kind=tool_call
- **Result:** Status badge (ALLOWED | BLOCKED `Authorization · resource_scope` | MASKED `Authorization · resource_projection`)
- **Side-by-side JSON:** raw_result (left) vs delivered_result (right), with redacted columns struck and filtered-row count highlighted
- **Audit link:** Click to view the same call in the audit log

## Tests & verification

### Scenarios

1. **dev_reads_allowed_repo_file** (positive)
   - Actor: anna.kowalska (developer)
   - Tool: `github.read_file("web-app", "src/app.py")`
   - Expected: ALLOWED
   - Path matches allow pattern `src/**`

2. **dev_reads_env_file_blocked** (negative)
   - Actor: anna.kowalska (developer)
   - Tool: `github.read_file("web-app", ".env")`
   - Expected: BLOCKED, rule_id: `resource_scope`
   - Path matches deny pattern `**/.env`

3. **hr_query_projected** (negative)
   - Actor: marek.nowak (hr, region PL)
   - Tool: `hr-db.query({"sql_like": "SELECT * FROM employees"})`
   - Expected: MASKED, rule_id: `resource_projection`
   - Result: E-2001 (PL) visible without salary, E-2101 (DE) filtered out, E-1042 visible without salary

### Unit tests

- `test_path_scope.py`: Glob patterns (allow/deny), normalization (backslash, .., absolute), case-insensitivity, deny-wins, allow-required
- `test_projection.py`: Row predicates with `$identity.*` substitution, missing attributes, multi-value predicates, column denial, records key extraction, changed flag

### Integration tests

- Tool call denied: response status 403, violation recorded, audit shows rule_id `resource_scope`, reason in evidence
- Tool result masked: response status 200, result projected, audit shows rule_id `resource_projection`, reason "N row(s) filtered, M column(s) redacted: ..."
- Hot reload: add `src/**/*.py` to deny list in policy.yaml, anna's `src/app.py` read → 403; revert, anna's read → ALLOWED

## Limitations & gotchas

### Path normalization

Glob patterns use forward slashes and `**`. Paths are normalized (backslash → forward slash) before matching, so `secrets\key.pem` and `secrets/key.pem` match the same deny pattern `secrets/**`.

### Absolute path rejection

Paths starting with `/` (Unix) or `C:\` (Windows) are rejected. MCP tools should pass relative paths only; the backend does not resolve them against a filesystem root.

### Column visibility

Redacting a column means the value is replaced with null in JSON. If a client UI expects a column to be absent rather than null, the frontend must handle it. The reason wording ("N column(s) redacted: col1, col2") does not indicate which records were affected.

### Row filtering

A record that fails all row predicates is completely filtered out (not visible to the caller). If a tool returns a single record per call (like `get_employee`), the result is `{"redacted": "outside row scope"}` when filtered.

### Cross-identity cache-key fix

The decision cache key is now computed after authorization stage, including the resolved role and post-authorization `current_text`. This prevents user B from reading user A's projected data from a cached DLP/Policy bundle.

### Structured content fix

When a tool result is masked due to projection, the `structured_content` field is re-derived from the `masked_text` (projected JSON) to prevent clients from parsing the unmasked data.

---

See also: [Workbench Trace](feature-workbench.md) for live testing · [Architecture](architecture.md) for Authorization stage details · [OWASP Mapping](owasp-mapping.md) for threat evidence (ASI03, LLM02, LLM06).
