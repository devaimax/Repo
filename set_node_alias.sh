#!/bin/bash
# Script: set_node_alias.sh
# وظيفة: يولد NODE_ALIAS_MAP تلقائي من docker node inspect

# عقد الـ swarm
NODES=("Master" "node-01" "node-02" "node-03" "node-04")

MAP=""

for NODE in "${NODES[@]}"; do
  IP=$(docker node inspect "$NODE" --format '{{ .Status.Addr }}')
  if [ -z "$IP" ]; then
    echo "❌ لم أستطع جلب IP للعقدة $NODE"
    exit 1
  fi
  if [ -z "$MAP" ]; then
    MAP="$IP=$NODE"
  else
    MAP="$MAP,$IP=$NODE"
  fi
done

export NODE_ALIAS_MAP="$MAP"
echo "✅ تم تعيين NODE_ALIAS_MAP:"
echo "$NODE_ALIAS_MAP"
