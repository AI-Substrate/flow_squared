#!/usr/bin/env python3
"""Test semantic search capabilities using fs2 search.

Runs semantic queries for obscure concepts and saves results for analysis.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Semantic search queries - concept phrases (not questions)
QUERIES = [
    # RestrictedUnpickler - security against malicious pickle
    ("protect against malicious pickle deserialization", "RestrictedUnpickler"),
    ("prevent code execution when loading serialized data", "RestrictedUnpickler"),

    # overlap_tokens - chunking with context preservation
    ("preserve context at chunk boundaries", "overlap_tokens"),
    ("overlapping content when splitting for embeddings", "overlap_tokens"),

    # prior_nodes / hash-based skip
    ("incremental scan optimization", "prior_nodes"),
    ("skip reprocessing unchanged content", "content_hash skip"),

    # FixtureIndex - test doubles for LLM
    ("deterministic test doubles for embedding", "FixtureIndex"),
    ("precomputed embeddings lookup table", "FixtureIndex"),
]


def run_fs2_search(pattern: str, limit: int = 5, mode: str = "semantic", detail: str = "min") -> dict:
    """Run fs2 search and return results.

    Per Subtask 003: fs2 search now returns envelope format:
    {"meta": {...}, "results": [...]}
    """
    cmd = [
        "uv", "run", "fs2", "search",
        pattern,
        "--mode", mode,
        "--limit", str(limit),
        "--detail", detail,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            # Parse envelope format
            envelope = json.loads(result.stdout) if result.stdout.strip() else {"meta": {}, "results": []}
            return {
                "success": True,
                "results": envelope.get("results", []),
                "meta": envelope.get("meta", {}),
                "stderr": result.stderr,
            }
        else:
            return {
                "success": False,
                "error": result.stderr or "Unknown error",
                "returncode": result.returncode,
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse error: {e}", "raw": result.stdout[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_result_quality(results: list, expected_keyword: str) -> dict:
    """Check if results contain the expected concept."""
    found_in_top_1 = False
    found_in_top_3 = False
    found_in_top_5 = False
    found_at_rank = None

    for i, r in enumerate(results[:5]):
        node_id = r.get("node_id", "")
        smart_content = r.get("smart_content", "")
        snippet = r.get("snippet", "")

        # Check if expected keyword appears anywhere
        combined = f"{node_id} {smart_content} {snippet}".lower()
        if expected_keyword.lower() in combined:
            if found_at_rank is None:
                found_at_rank = i + 1
            if i == 0:
                found_in_top_1 = True
            if i < 3:
                found_in_top_3 = True
            if i < 5:
                found_in_top_5 = True

    return {
        "found_in_top_1": found_in_top_1,
        "found_in_top_3": found_in_top_3,
        "found_in_top_5": found_in_top_5,
        "found_at_rank": found_at_rank,
    }


def main():
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_queries": len(QUERIES),
            "successful": 0,
            "found_in_top_1": 0,
            "found_in_top_3": 0,
            "found_in_top_5": 0,
        },
        "queries": [],
    }

    print("=" * 70)
    print("FS2 SEMANTIC SEARCH TEST")
    print("=" * 70)
    print()

    for query, expected in QUERIES:
        print(f"Query: {query[:50]}...")
        print(f"  Expected: {expected}")

        result = run_fs2_search(query, limit=5, mode="semantic", detail="max")

        query_result = {
            "query": query,
            "expected_keyword": expected,
            "result": result,
        }

        if result["success"]:
            output["summary"]["successful"] += 1
            results = result["results"]
            quality = check_result_quality(results, expected)
            query_result["quality"] = quality

            if quality["found_in_top_1"]:
                output["summary"]["found_in_top_1"] += 1
                print(f"  Result: FOUND at rank 1")
            elif quality["found_in_top_3"]:
                output["summary"]["found_in_top_3"] += 1
                print(f"  Result: FOUND at rank {quality['found_at_rank']}")
            elif quality["found_in_top_5"]:
                output["summary"]["found_in_top_5"] += 1
                print(f"  Result: FOUND at rank {quality['found_at_rank']}")
            else:
                print(f"  Result: NOT FOUND in top 5")

            # Show top result
            if results:
                top = results[0]
                print(f"  Top hit: {top.get('node_id', '?')[:60]} (score: {top.get('score', '?')})")
        else:
            print(f"  ERROR: {result.get('error', 'unknown')}")

        output["queries"].append(query_result)
        print()

    # Save full results
    output_path = Path("scripts/semantic_search_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    s = output["summary"]
    print(f"Total queries:    {s['total_queries']}")
    print(f"Successful:       {s['successful']}")
    print(f"Found in top 1:   {s['found_in_top_1']}")
    print(f"Found in top 3:   {s['found_in_top_3']} (cumulative: {s['found_in_top_1'] + s['found_in_top_3']})")
    print(f"Found in top 5:   {s['found_in_top_5']} (cumulative: {s['found_in_top_1'] + s['found_in_top_3'] + s['found_in_top_5']})")
    print()
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
