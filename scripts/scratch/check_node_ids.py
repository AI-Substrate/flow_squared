"""Check node_id formats across all node types in a real graph."""
import pickle
from collections import Counter, defaultdict
from pathlib import Path

graph_path = Path(".fs2/graph.pickle")
if not graph_path.exists():
    print("No graph.pickle found, checking factory methods instead")
    exit(1)

with open(graph_path, "rb") as f:
    metadata, graph = pickle.load(f)

print(f"Graph: {metadata.get('node_count')} nodes, {metadata.get('edge_count')} edges")
print(f"Format: {metadata.get('format_version')}\n")

# Analyze node_id formats
categories = Counter()
colon_counts = Counter()
examples = defaultdict(list)

for node_id in graph.nodes:
    data = graph.nodes[node_id].get("data")
    if data is None:
        continue
    
    cat = data.category
    categories[cat] += 1
    parts = node_id.split(":")
    colon_counts[len(parts)] += 1
    
    # Keep first 2 examples per category
    if len(examples[cat]) < 2:
        examples[cat].append(node_id)

print("=== Categories ===")
for cat, count in categories.most_common():
    print(f"  {cat}: {count}")

print(f"\n=== Colon counts (parts after split(':')) ===")
for n, count in sorted(colon_counts.items()):
    print(f"  {n} parts: {count}")

print(f"\n=== Examples per category ===")
for cat, ids in sorted(examples.items()):
    for nid in ids:
        parts = nid.split(":", 2)
        if len(parts) == 2:
            print(f"  [{cat}] {nid}")
            print(f"    → split(2): category='{parts[0]}', rest='{parts[1]}' (NO file:name split)")
        elif len(parts) == 3:
            print(f"  [{cat}] {nid}")
            print(f"    → split(2): category='{parts[0]}', file='{parts[1]}', name='{parts[2]}'")

# Check: does file path from node_id match parent's file path for containment?
print(f"\n=== Containment edge file-path consistency ===")
mismatches = 0
checked = 0
for parent_id in list(graph.nodes)[:500]:
    parent = graph.nodes[parent_id].get("data")
    if parent is None:
        continue
    for child_id in graph.successors(parent_id):
        child = graph.nodes[child_id].get("data")
        if child is None:
            continue
        checked += 1
        # Extract file path: for file nodes it's parts[1], for others it's parts[1]
        p_parts = parent_id.split(":", 2)
        c_parts = child_id.split(":", 2)
        p_file = p_parts[1] if len(p_parts) >= 2 else "?"
        c_file = c_parts[1] if len(c_parts) >= 2 else "?"
        if p_file != c_file:
            mismatches += 1
            if mismatches <= 5:
                print(f"  MISMATCH: parent={parent_id} → child={child_id}")
                print(f"            p_file={p_file}, c_file={c_file}")

print(f"\n  Checked {checked} containment edges, {mismatches} file-path mismatches")
