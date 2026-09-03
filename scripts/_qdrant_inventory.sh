#!/usr/bin/env bash
set -e
BRAIN=$(docker ps -qf name=vibemind_brain-core | head -1)

COLLECTIONS=$(docker exec "$BRAIN" sh -c 'curl -s http://qdrant:6333/collections' | python3 -c '
import json, sys
d = json.load(sys.stdin)
for c in d["result"]["collections"]:
    print(c["name"])
')

for c in $COLLECTIONS; do
  info=$(docker exec "$BRAIN" sh -c "curl -s http://qdrant:6333/collections/$c")
  echo "$info" | python3 -c "
import json, sys
data = json.load(sys.stdin)['result']
pts = data.get('points_count', 0)
indexed = data.get('indexed_vectors_count', 0)
vec = data.get('config', {}).get('params', {}).get('vectors', {})
if isinstance(vec, dict) and 'size' in vec:
    dim = vec['size']
    dist = vec.get('distance', '?')
else:
    # named vectors
    names = list(vec.keys()) if isinstance(vec, dict) else []
    if names:
        first = vec[names[0]]
        dim = f'{first.get(\"size\", \"?\")} ({len(names)} named: {\",\".join(names)})'
        dist = first.get('distance', '?')
    else:
        dim = '?'
        dist = '?'
print(f'  $c: points={pts}  indexed={indexed}  dim={dim}  dist={dist}  status={data.get(\"status\")}')
"
done

echo ""
echo "=== Sample point from each collection (with payload keys) ==="
for c in $COLLECTIONS; do
  echo "--- $c ---"
  docker exec "$BRAIN" sh -c "curl -s -X POST http://qdrant:6333/collections/$c/points/scroll -H 'content-type: application/json' -d '{\"limit\": 1, \"with_payload\": true, \"with_vector\": false}'" | python3 -c "
import json, sys
data = json.load(sys.stdin)
points = data.get('result', {}).get('points', [])
if points:
    p = points[0]
    payload = p.get('payload', {})
    keys = sorted(payload.keys())
    print(f'  payload keys: {keys}')
    # show small subset of payload
    for k in keys[:5]:
        v = payload[k]
        if isinstance(v, str) and len(v) > 80:
            v = v[:80] + '...'
        print(f'    {k}: {v}')
else:
    print('  (no points)')
"
done
