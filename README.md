# mulat — Kubernetes Multi-Agent Troubleshooter

LangGraph orchestration with three read-only specialist agents (node health, right-sizing, pod security), exposed via FastAPI (`/ask`, `/alert`, `/approve`).

## Docs

| Document | Contents |
| --- | --- |
| [DIRECTORY_STRUCTURE.md](./DIRECTORY_STRUCTURE.md) | Layout and implementation order |
| [k8s-multi-agent-troubleshooter.md](./k8s-multi-agent-troubleshooter.md) | Architecture and LangGraph design |
| [Tool_API.md](./Tool_API.md) | Tool contracts and RBAC |

## Quick start (local)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env   # set LLM_API_KEY, PROMETHEUS_URL, KUBECONFIG

uvicorn mulat.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI: http://localhost:8000/docs  
- Postman: import `postman/mulat-agent-api.postman_collection.json`

## Layout

Application code lives under `src/mulat/` (API → orchestration → tools → clients). See **DIRECTORY_STRUCTURE.md** for the full tree.

## Tests

```bash
pytest
```
