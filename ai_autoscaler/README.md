# AI Autoscaler (Reinforcement Learning Prototype)

This module implements a reinforcement-learning (RL) control loop that monitors
Docker Swarm nodes via Prometheus (with CLI fallbacks) and reacts to load by
rebalancing services or toggling standby nodes hosted on ESXi.

## Components

- `config.py` – default configuration and hyper-parameters.
- `state.py` – collects node observations using Prometheus or Docker CLI.
- `agent.py` – epsilon-greedy tabular Q-learning agent.
- `actions.py` – executes cluster actions (rebalance, power on/off placeholders).
- `logger.py` – persists events and Q-table snapshots to CSV/JSON under
  `logs/ai_autoscaler/`.
- `runner.py` – main RL loop: observe → decide → act → learn.
- `main.py` – CLI entrypoint.

## Running the autoscaler

```bash
python3 -m ai_autoscaler.main \
  --prom-url http://localhost:9090 \
  --interval 30 \
  --epsilon 0.1 \
  --iterations 100
```

The command above performs 100 iterations (otherwise it runs indefinitely),
observing the cluster every 30 seconds. Each iteration:

1. Pulls node CPU/memory utilisation and service placement.
2. Classifies nodes into `high`, `normal`, `idle` buckets.
3. Chooses an action (`noop`, `rebalance`, `power_on`, `power_off`).
4. Executes the action using `docker service update` and placeholder ESXi hooks.
5. Evaluates the reward based on how much the load deviated from thresholds.
6. Updates the Q-table and appends an event to `logs/ai_autoscaler/events.csv`.

## Extending actions

- Implement actual ESXi interactions inside `ClusterActions.power_on_node` and
  `ClusterActions.power_off_node`.
- Populate `_next_available_node` to choose which standby node to start.
- The `rebalance` action currently pins services to the least-loaded node; adapt
  it if you prefer weight-based scheduling or service-specific constraints.

## Notes

- Prometheus failures fallback to Docker CLI metrics, but the RL agent needs at
  least `min_samples` nodes to make decisions.
- CSV logs intentionally mirror previous workflows so you can ingest them into
  your existing reporting pipeline.
- This is a prototype: tune hyper-parameters (alpha, gamma, epsilon) and
  reward shaping before production use.
