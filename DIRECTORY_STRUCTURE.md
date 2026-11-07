# Directory structure — Kubernetes Multi-Agent Troubleshooter (mulat)

This document describes the recommended layout for the **mulat** project: a FastAPI service plus LangGraph orchestration that runs read-only Kubernetes and Prometheus tools through three specialist agents.

For product architecture and LangGraph design, see [k8s-multi-agent-troubleshooter.md](./k8s-multi-agent-troubleshooter.md). For tool inputs, outputs, and RBAC, see [Tool_API.md](./Tool_API.md).

---

## Overview

The codebase is organized in four runtime layers (inside the agent pod) plus deployment and tests:

| Layer | Role |
| --- | --- |
| **API** | HTTP triggers: `/ask`, `/alert`, `/approve` |
| **Orchestration** | LangGraph: supervisor → specialists → synthesizer → human approval |
| **Tools** | Eleven read-only `@tool` functions with a shared JSON envelope |
| **Clients** | Kubernetes, Prometheus, LLM, and checkpoint storage |

Everything under `src/mulat/` is importable Python package code. `deploy/kubernetes/` holds manifests; `tests/` holds unit and integration tests.

---

## Full tree

```text
mulat/
├── README.md
├── pyproject.toml                        # or requirements.txt — dependencies & scripts
├── .env.example                          # local-only secrets template (do not commit real keys)
├── Dockerfile
├── DIRECTORY_STRUCTURE.md                # this file
├── k8s-multi-agent-troubleshooter.md     # architecture & LangGraph design
├── Tool_API.md                           # tool contracts & RBAC
│
├── src/
│   └── mulat/
│       ├── __init__.py
│       ├── main.py                       # process entry (e.g. uvicorn target)
│       ├── config.py                     # settings from env / ConfigMap
│       │
│       ├── api/                          # API layer
│       ├── orchestration/                # LangGraph graph & agents
│       ├── prompts/                      # system prompts (markdown)
│       ├── tools/                        # read-only tool implementations
│       ├── clients/                      # external service wrappers
│       └── notifications/              # Slack / email report delivery
│
├── tests/
├── deploy/
│   └── kubernetes/
└── scripts/                              # local dev & smoke-test helpers
```

---

## Root files

| Path | Purpose |
| --- | --- |
| `README.md` | How to run locally, configure cluster access, and deploy. |
| `pyproject.toml` | Package metadata, dependencies (`langgraph`, `kubernetes`, `fastapi`, etc.), and CLI scripts. |
| `.env.example` | Documents `LLM_API_KEY`, `PROMETHEUS_URL`, `DATABASE_URL` for local dev. |
| `Dockerfile` | Builds the agent-api image (FastAPI + LangGraph + tools). |
| `k8s-multi-agent-troubleshooter.md` | High-level design, example runs, K8s objects list. |
| `Tool_API.md` | Per-tool API, result envelope, error codes, ClusterRole rules. |

---

## `src/mulat/` — application package

### `main.py` and `config.py`

- **`main.py`** — Starts the ASGI app (typically `uvicorn mulat.main:app`).
- **`config.py`** — Centralizes configuration: Prometheus URL, model name, API timeouts, list size limits (aligned with Tool_API defaults), checkpointer DSN, Slack webhook URL.

### `api/` — API layer

Maps to **§5.2** in the architecture doc: only this layer exposes HTTP; it invokes the compiled LangGraph app.

```text
api/
├── __init__.py
├── app.py                    # FastAPI instance, middleware, lifespan (clients init)
└── routes/
    ├── ask.py                # POST /ask — user or CLI investigation request
    ├── alert.py              # POST /alert — Alertmanager webhook → same graph entry
    └── approve.py            # POST /approve — resume run paused at interrupt()
```

Each route should pass a **thread/run id** so `POST /approve` can call `Command(resume=...)` against the same checkpointer record.

### `orchestration/` — LangGraph

Maps to **§4** (StateGraph, `Send`, reducer on `findings`, `interrupt()`).

```text
orchestration/
├── __init__.py
├── state.py                  # TypedDict: request, targets, findings (operator.add), report
├── graph.py                  # add_node / edges / compile(checkpointer=...)
├── supervisor.py             # LLM or rules: which agents to run; returns targets for Send
├── synthesizer.py            # Merge findings into one severity-ranked report
├── approval.py               # interrupt({ report, ask }) — human gate
└── agents/
    ├── __init__.py
    ├── node_health.py        # create_react_agent(llm, node_tools, prompt=...)
    ├── right_sizing.py       # create_react_agent + Prometheus tools
    └── pod_security.py       # create_react_agent + security tools
```

| Module | Architecture piece |
| --- | --- |
| `state.py` | Shared graph state |
| `supervisor.py` | Orchestrator |
| `agents/*` | Node health, right-sizing, pod security ReAct sub-agents |
| `synthesizer.py` | Synthesizer |
| `approval.py` | Human approval gate |
| `graph.py` | Wires START → supervisor → parallel agents → synthesize → approval → END |

### `prompts/` — system prompts

Keep prompts out of Python for easier review and diffing.

```text
prompts/
├── supervisor.md             # Routing: which specialists for which requests
├── node_health.md              # Disk/memory/PID pressure, events, pod density
├── right_sizing.md             # Compare requests/limits vs Prometheus usage
└── pod_security.md             # PSS baseline/restricted, image tags
```

Loaded at agent construction time (e.g. read file → string passed to `create_react_agent`).

### `tools/` — tool layer

Maps to **§6** and **Tool_API.md**. Each tool is a LangChain `@tool` that returns the standard envelope (`ok`, `tool`, `data`, `truncated`, `error`).

```text
tools/
├── __init__.py
├── registry.py               # node_health_tools, sizing_tools, security_tools lists
├── envelope.py               # success/error builders, truncation helpers
├── errors.py                 # Error codes: INVALID_INPUT, NOT_FOUND, FORBIDDEN, ...
├── node_health/
│   ├── list_nodes.py
│   ├── describe_node.py
│   ├── node_events.py
│   └── pods_per_node.py
├── right_sizing/
│   ├── get_requests_limits.py
│   ├── query_cpu_usage.py
│   └── query_memory_usage.py
└── pod_security/
    ├── list_pods.py
    ├── get_pod_spec.py
    ├── check_security_context.py   # PSS rule engine (no direct K8s API beyond get/list)
    └── find_latest_tags.py         # Uses list_pods / spec data
```

| Folder | Agent | Tool count |
| --- | --- | --- |
| `node_health/` | Node health | 4 |
| `right_sizing/` | Right-sizing | 3 |
| `pod_security/` | Pod security | 4 |

**`registry.py`** is the single place that assigns tool lists to each agent so orchestration stays unaware of individual tool modules.

### `clients/` — client layer

Thin wrappers used by tools and/or the graph (LLM and checkpointer are shared by all nodes).

```text
clients/
├── __init__.py
├── kubernetes.py             # CoreV1Api, metrics.k8s.io; in-cluster SA or kubeconfig
├── prometheus.py             # GET /api/v1/query, timeouts, PROMETHEUS_ERROR handling
├── llm.py                    # Chat model from Secret / env
└── checkpointer.py           # MemorySaver (local) vs PostgresSaver (deployed)
```

Tools should depend on clients, not on raw HTTP or global SDK singletons, so tests can inject fakes.

### `notifications/`

Optional delivery after approval or when sending the final report.

```text
notifications/
├── __init__.py
└── slack.py                  # Webhook from ConfigMap; email adapter can be added later
```

---

## `tests/`

```text
tests/
├── unit/
│   ├── test_envelope.py              # JSON envelope and error codes
│   ├── test_check_security_context.py
│   └── test_find_latest_tags.py      # Rule engines without a live cluster
├── integration/
│   └── test_tools_against_kind.py    # kind / minikube + optional Prometheus
└── graph/
    └── test_supervisor_routing.py    # Which agents run for sample requests
```

Unit tests focus on parsers, PSS rules, image tag logic, and PromQL builders. Integration tests validate RBAC and real API responses against a test cluster.

---

## `deploy/kubernetes/`

Maps to **§7** (Kubernetes objects). Target namespace example: `ai-agents`.

```text
deploy/kubernetes/
├── namespace.yaml
├── serviceaccount.yaml
├── clusterrole.yaml              # Rules from Tool_API.md § Permissions
├── clusterrolebinding.yaml
├── configmap.yaml                # PROMETHEUS_URL, model name, non-secret config
├── secret.yaml.example           # LLM key, Postgres password — copy & apply locally
├── deployment.yaml               # agent-api pod: FastAPI + LangGraph
├── service.yaml                  # ClusterIP :8000
├── networkpolicy.yaml            # Egress: K8s API, Prometheus, Postgres, LLM, Slack
├── postgres/
│   ├── statefulset.yaml
│   └── service.yaml
└── optional/
    ├── cronjob-daily-check.yaml  # HTTP POST to /ask on a schedule
    └── alertmanager-receiver.md  # How to point Alertmanager at /alert
```

The Deployment must mount the ServiceAccount used by `clients/kubernetes.py`. Secrets and ConfigMaps mirror keys documented in `config.py` and `.env.example`.

---

## `scripts/`

Helper commands for developers (not shipped in the container unless needed).

```text
scripts/
├── run_local.sh                  # MemorySaver + KUBECONFIG
└── invoke_ask.ps1                # Smoke test POST /ask (Windows-friendly)
```

---

## Data flow (where code lives)

```text
  POST /ask|/alert          POST /approve
        │                         │
        ▼                         ▼
   api/routes/*  ──────►  orchestration/graph.py
                                │
                    supervisor.py (Send fan-out)
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        agents/node_*    agents/right_*    agents/pod_*
              │                 │                 │
              └────────► tools/* ◄────────────────┘
                              │
                    clients/kubernetes.py
                    clients/prometheus.py
                              │
              synthesizer.py ──► approval.py (interrupt)
                              │
                    notifications/slack.py (optional)
```

---

## Suggested implementation order

1. **`clients/`** + **`tools/envelope.py`** — Implement the eleven tools per Tool_API.md.
2. **`prompts/`** + **`orchestration/agents/`** — Wire ReAct agents to `registry.py` tool lists.
3. **`orchestration/graph.py`** — Supervisor routing, parallel runs, synthesizer, approval.
4. **`api/`** — Expose endpoints and thread ids for checkpoint resume.
5. **`Dockerfile`** + **`deploy/kubernetes/`** — RBAC, Postgres checkpointer, NetworkPolicy.
6. **`notifications/`** + **`optional/`** manifests — Slack, CronJob, Alertmanager.

---

## Naming notes

- **`mulat`** — Short folder/repo name for this POC; the Python package under `src/mulat/` should match the import name you choose in `pyproject.toml`.
- **Read-only guarantee** — Enforced by ClusterRole verbs and tool design, not by directory layout; do not add write or exec tools under `tools/` without a deliberate design change.

---

## Related documents

| Document | Contents |
| --- | --- |
| [k8s-multi-agent-troubleshooter.md](./k8s-multi-agent-troubleshooter.md) | Agents, LangGraph skeleton, deployment diagram, design decisions |
| [Tool_API.md](./Tool_API.md) | Tool parameters, JSON shapes, PromQL, PSS rules, RBAC YAML |
