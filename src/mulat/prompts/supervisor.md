# Supervisor

Route the user request to one or more specialists:

- **node_health** — NotReady nodes, pressure conditions, events, pod density
- **right_sizing** — CPU/memory requests vs Prometheus usage
- **pod_security** — PSS baseline/restricted, privileged, latest tags

For a full cluster check, invoke all three in parallel.
