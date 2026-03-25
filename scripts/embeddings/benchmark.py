#!/usr/bin/env python3
"""
Benchmark embedding models for fs2 code intelligence.

Tests two SentenceTransformer models on realistic code snippets,
measuring throughput across devices (CUDA > MPS > CPU) and batch sizes.
Includes parallel encoding via multiprocessing pool.

Usage:
    cd scripts/embeddings
    source .venv/bin/activate
    python benchmark.py                # auto-detect best device
    python benchmark.py --device cpu   # force CPU
    python benchmark.py --device mps   # force MPS
    python benchmark.py --device cuda  # force CUDA
    python benchmark.py --parallel     # test parallel encoding
"""

import argparse
import platform
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Models to benchmark
# ---------------------------------------------------------------------------
MODELS = {
    "multilingual-L12": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",  # ~470 MB, dim 384
    "english-L6": "sentence-transformers/all-MiniLM-L6-v2",  # ~90 MB, dim 384
    "bge-small": "BAAI/bge-small-en-v1.5",  # ~130 MB, dim 384, retrieval-optimized
    "codebert": "microsoft/codebert-base",  # ~500 MB, dim 768, code-aware
    "unixcoder": "microsoft/unixcoder-base",  # ~500 MB, dim 768, cross-lang code
}

# ---------------------------------------------------------------------------
# Synthetic code corpus (realistic code snippets of varying length)
# ---------------------------------------------------------------------------
CODE_SNIPPETS = [
    # Short: signatures / one-liners
    "def add(a: int, b: int) -> int: return a + b",
    "class UserRepository(ABC): pass",
    "from typing import List, Dict, Optional",
    "logger = logging.getLogger(__name__)",
    "SELECT u.id, u.name FROM users u WHERE u.active = true",

    # Medium: small functions
    """def fetch_user(user_id: str) -> Optional[User]:
    \"\"\"Retrieve a user by ID from the database.\"\"\"
    with get_session() as session:
        result = session.query(User).filter(User.id == user_id).first()
        if result is None:
            raise UserNotFoundError(f"No user with id={user_id}")
        return result""",

    """class ConsoleAdapter(ABC):
    @abstractmethod
    def print(self, message: str) -> None: ...
    @abstractmethod
    def print_error(self, message: str) -> None: ...
    @abstractmethod
    def print_table(self, headers: List[str], rows: List[List[str]]) -> None: ...""",

    """async def process_batch(items: List[WorkItem], concurrency: int = 4) -> BatchResult:
    semaphore = asyncio.Semaphore(concurrency)
    async def _process(item):
        async with semaphore:
            return await item.execute()
    results = await asyncio.gather(*[_process(i) for i in items])
    return BatchResult(succeeded=[r for r in results if r.ok], failed=[r for r in results if not r.ok])""",

    # Long: class with methods
    """class TreeService:
    \"\"\"Service for querying the code graph as a hierarchical tree.\"\"\"

    def __init__(self, graph_repo: GraphRepository, formatter: TreeFormatter):
        self._graph = graph_repo
        self._formatter = formatter

    def get_tree(self, pattern: str, max_depth: int = 0, detail: str = "min") -> TreeResult:
        nodes = self._graph.find_nodes(pattern)
        if not nodes:
            return TreeResult.empty(pattern)
        roots = self._build_hierarchy(nodes, max_depth)
        return TreeResult(roots=roots, count=len(nodes), detail=detail)

    def _build_hierarchy(self, nodes, max_depth):
        by_parent = defaultdict(list)
        for node in nodes:
            by_parent[node.parent_id].append(node)
        return self._attach_children(by_parent, None, 0, max_depth)

    def _attach_children(self, by_parent, parent_id, depth, max_depth):
        if max_depth and depth >= max_depth:
            return []
        children = by_parent.get(parent_id, [])
        for child in children:
            child.children = self._attach_children(by_parent, child.id, depth + 1, max_depth)
        return sorted(children, key=lambda n: n.start_line)""",

    """class NetworkXGraphStore:
    \"\"\"Persist code graph to NetworkX + pickle format.\"\"\"

    def save(self, graph: CodeGraph, path: Path) -> None:
        G = nx.DiGraph()
        for node in graph.nodes:
            G.add_node(node.id, **node.to_dict())
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target, rel_type=edge.rel_type, metadata=edge.metadata)
        with open(path, 'wb') as f:
            pickle.dump((G, graph.metadata), f, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, path: Path) -> CodeGraph:
        with open(path, 'rb') as f:
            G, metadata = pickle.load(f)
        nodes = [CodeNode.from_dict(G.nodes[n]) for n in G.nodes]
        edges = [CodeEdge(s, t, **G.edges[s, t]) for s, t in G.edges]
        return CodeGraph(nodes=nodes, edges=edges, metadata=metadata)""",
]


def build_corpus(target_size: int) -> list[str]:
    """Repeat snippets to reach target corpus size."""
    corpus = []
    while len(corpus) < target_size:
        corpus.extend(CODE_SNIPPETS)
    return corpus[:target_size]


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------
def detect_device(requested: str = "auto") -> str:
    """Pick best available device: CUDA > MPS > CPU."""
    if requested != "auto":
        if requested == "cuda" and not torch.cuda.is_available():
            print(f"⚠  CUDA requested but not available, falling back to CPU")
            return "cpu"
        if requested == "mps" and not torch.backends.mps.is_available():
            print(f"⚠  MPS requested but not available, falling back to CPU")
            return "cpu"
        return requested

    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"🟢 CUDA detected: {name}")
        return "cuda"
    if torch.backends.mps.is_available():
        print(f"🟢 MPS detected (Apple Silicon)")
        return "mps"
    print(f"⚪ Using CPU")
    return "cpu"


# ---------------------------------------------------------------------------
# Benchmark result
# ---------------------------------------------------------------------------
@dataclass
class BenchResult:
    model_key: str
    model_name: str
    device: str
    corpus_size: int
    batch_size: int
    embedding_dim: int
    total_seconds: float
    per_item_ms: float
    items_per_sec: float
    warmup_seconds: float
    run_times: list[float] = field(default_factory=list)

    def summary_line(self) -> str:
        mean_ms = statistics.mean(self.run_times) * 1000 / self.corpus_size if self.run_times else self.per_item_ms
        return (
            f"  {self.model_key:<20s} | device={self.device:<5s} | "
            f"batch={self.batch_size:<4d} | dim={self.embedding_dim} | "
            f"{self.items_per_sec:>8.1f} items/s | "
            f"{mean_ms:>6.2f} ms/item | "
            f"warmup={self.warmup_seconds:.2f}s"
        )


# ---------------------------------------------------------------------------
# Single-threaded benchmark
# ---------------------------------------------------------------------------
def run_benchmark(
    model_key: str,
    model_name: str,
    device: str,
    corpus: list[str],
    batch_size: int,
    runs: int = 3,
) -> BenchResult:
    """Load model, warm up, then time `runs` full-corpus encodes."""
    print(f"\n{'='*70}")
    print(f"  Model: {model_key} ({model_name})")
    print(f"  Device: {device} | Corpus: {len(corpus)} items | Batch: {batch_size}")
    print(f"{'='*70}")

    # Load model
    t0 = time.perf_counter()
    model = SentenceTransformer(model_name, device=device)
    model.max_seq_length = 512
    load_time = time.perf_counter() - t0
    dim = model.get_sentence_embedding_dimension()
    print(f"  Model loaded in {load_time:.2f}s (dim={dim})")

    encode_kwargs = {
        "batch_size": batch_size,
        "show_progress_bar": False,
        "normalize_embeddings": True,
        "convert_to_numpy": True,
        "device": device,
        "convert_to_tensor": False,
    }
    # Darwin MPS pool workaround (from FastCode)
    if platform.system() == "Darwin":
        encode_kwargs["pool"] = None

    # Warmup (single small batch)
    t0 = time.perf_counter()
    _ = model.encode(corpus[:min(batch_size, len(corpus))], **encode_kwargs)
    warmup_time = time.perf_counter() - t0
    print(f"  Warmup: {warmup_time:.2f}s")

    # Timed runs
    run_times = []
    for i in range(runs):
        t0 = time.perf_counter()
        embeddings = model.encode(corpus, **encode_kwargs)
        elapsed = time.perf_counter() - t0
        run_times.append(elapsed)
        print(f"  Run {i+1}/{runs}: {elapsed:.3f}s  ({len(corpus)/elapsed:.1f} items/s)")

    assert embeddings.shape == (len(corpus), dim), f"Shape mismatch: {embeddings.shape}"

    best = min(run_times)
    return BenchResult(
        model_key=model_key,
        model_name=model_name,
        device=device,
        corpus_size=len(corpus),
        batch_size=batch_size,
        embedding_dim=dim,
        total_seconds=sum(run_times),
        per_item_ms=(best / len(corpus)) * 1000,
        items_per_sec=len(corpus) / best,
        warmup_seconds=warmup_time,
        run_times=run_times,
    )


# ---------------------------------------------------------------------------
# Parallel benchmark (simulate multi-worker ingestion)
# ---------------------------------------------------------------------------
def _worker_encode(args: tuple) -> dict:
    """Worker function for ProcessPoolExecutor (must be top-level for pickling)."""
    model_name, device, texts, batch_size = args

    encode_kwargs = {
        "batch_size": batch_size,
        "show_progress_bar": False,
        "normalize_embeddings": True,
        "convert_to_numpy": True,
        "device": device,
        "convert_to_tensor": False,
    }
    if platform.system() == "Darwin":
        encode_kwargs["pool"] = None

    model = SentenceTransformer(model_name, device=device)
    model.max_seq_length = 512

    t0 = time.perf_counter()
    embeddings = model.encode(texts, **encode_kwargs)
    elapsed = time.perf_counter() - t0

    return {"count": len(texts), "elapsed": elapsed, "shape": embeddings.shape}


def run_parallel_benchmark(
    model_key: str,
    model_name: str,
    device: str,
    corpus: list[str],
    batch_size: int,
    workers: int = 2,
) -> None:
    """Split corpus across workers and measure aggregate throughput."""
    print(f"\n{'='*70}")
    print(f"  PARALLEL: {model_key} | {workers} workers | device={device}")
    print(f"{'='*70}")

    # Split corpus into chunks per worker
    chunk_size = len(corpus) // workers
    chunks = [corpus[i * chunk_size:(i + 1) * chunk_size] for i in range(workers)]
    # Remainder goes to last chunk
    if len(corpus) % workers:
        chunks[-1].extend(corpus[workers * chunk_size:])

    t0 = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_worker_encode, (model_name, device, chunk, batch_size))
            for chunk in chunks
        ]
        for fut in as_completed(futures):
            results.append(fut.result())
    wall_time = time.perf_counter() - t0

    total_items = sum(r["count"] for r in results)
    print(f"  Wall time: {wall_time:.3f}s for {total_items} items")
    print(f"  Aggregate throughput: {total_items / wall_time:.1f} items/s")
    for i, r in enumerate(results):
        print(f"    Worker {i}: {r['count']} items in {r['elapsed']:.3f}s ({r['count']/r['elapsed']:.1f} items/s)")


# ---------------------------------------------------------------------------
# Device comparison
# ---------------------------------------------------------------------------
def run_device_comparison(model_key: str, model_name: str, corpus: list[str], batch_size: int) -> list[BenchResult]:
    """Run the same model on all available devices for comparison."""
    devices = ["cpu"]
    if torch.backends.mps.is_available():
        devices.append("mps")
    if torch.cuda.is_available():
        devices.append("cuda")

    results = []
    for dev in devices:
        r = run_benchmark(model_key, model_name, dev, corpus, batch_size, runs=3)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Benchmark embedding models for fs2")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"],
                        help="Device to use (default: auto-detect)")
    parser.add_argument("--corpus-size", type=int, default=500,
                        help="Number of code snippets to embed (default: 500)")
    parser.add_argument("--batch-sizes", type=str, default="16,32,64,128",
                        help="Comma-separated batch sizes to test (default: 16,32,64,128)")
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of timed runs per config (default: 3)")
    parser.add_argument("--parallel", action="store_true",
                        help="Also test parallel multi-worker encoding")
    parser.add_argument("--parallel-workers", type=int, default=2,
                        help="Number of parallel workers (default: 2)")
    parser.add_argument("--compare-devices", action="store_true",
                        help="Compare all available devices (CPU vs MPS vs CUDA)")
    parser.add_argument("--models", type=str, default=None,
                        help="Comma-separated model keys to test (default: all)")
    args = parser.parse_args()

    device = detect_device(args.device)
    corpus = build_corpus(args.corpus_size)
    batch_sizes = [int(b) for b in args.batch_sizes.split(",")]

    # Filter models if requested
    models = MODELS
    if args.models:
        keys = [k.strip() for k in args.models.split(",")]
        models = {k: v for k, v in MODELS.items() if k in keys}

    print(f"\n{'#'*70}")
    print(f"  fs2 Embedding Benchmark")
    print(f"  Device: {device} | Corpus: {len(corpus)} snippets | Runs: {args.runs}")
    print(f"  Models: {', '.join(models.keys())}")
    print(f"  Batch sizes: {batch_sizes}")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"{'#'*70}")

    all_results: list[BenchResult] = []

    # --- Device comparison mode ---
    if args.compare_devices:
        for model_key, model_name in models.items():
            results = run_device_comparison(model_key, model_name, corpus, batch_sizes[0])
            all_results.extend(results)
    else:
        # --- Standard benchmark: vary batch sizes ---
        for model_key, model_name in models.items():
            for bs in batch_sizes:
                r = run_benchmark(model_key, model_name, device, corpus, bs, runs=args.runs)
                all_results.append(r)

    # --- Parallel benchmark ---
    if args.parallel:
        for model_key, model_name in models.items():
            run_parallel_benchmark(
                model_key, model_name, device, corpus,
                batch_sizes[0], workers=args.parallel_workers,
            )

    # --- Summary ---
    print(f"\n\n{'#'*70}")
    print(f"  SUMMARY")
    print(f"{'#'*70}")
    for r in all_results:
        print(r.summary_line())
    print()

    # Find best config
    if all_results:
        best = max(all_results, key=lambda r: r.items_per_sec)
        print(f"  🏆 Best: {best.model_key} batch={best.batch_size} device={best.device}")
        print(f"     {best.items_per_sec:.1f} items/s ({best.per_item_ms:.2f} ms/item)")
    print()


if __name__ == "__main__":
    main()
