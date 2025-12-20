Optimal Chunk Size and Overlap for Code Embeddings (OpenAI text-embedding-3-small)
Problem Definition

Building a semantic code search system raises a key question: How to split large code files and documents into chunks for embedding? The text-embedding-3-small model has an 8191-token limit
dev.to
, so files exceeding this must be chunked. We need chunking strategies that maximize search accuracy (relevant code snippets retrieved for natural language queries) while staying within limits. In particular, we must determine:

Chunk size – How many tokens per chunk yields the best embeddings for code search?

Overlap – How much overlap between chunks is needed to preserve context at boundaries without redundant data?

Content-specific strategies – Should source code be chunked differently from prose (documentation or AI summaries)?

Trade-offs – How chunk size/overlap affect search precision vs. recall, and storage/performance costs.

Core challenge: Find chunking parameters that preserve semantic context (so queries match the right chunks) without diluting focus or exploding the number of vectors stored.

Context and Constraints

Embedding Model: OpenAI text-embedding-3-small (≈1536-dim output, 8191-token max input)
cookbook.openai.com
 using cl100k_base tokenizer
cookbook.openai.com
platform.openai.com
. This model can embed fairly large text, but extremely large chunks might reduce retrieval effectiveness. All embeddings will be stored (e.g. in NumPy arrays), and search is via cosine similarity (no external vector DB). Thus, more (smaller) chunks = more vectors to store and compare.

Content Types:

Source code (Python, TypeScript): files up to thousands of lines (100–10,000+ tokens). Functions average 30 lines; classes ~100 lines. Code may include structured elements (functions, classes) that have clear boundaries.

AI-generated summaries (“smart content”): typically 100–500 tokens, often already under the limit.

Documentation (Markdown): can be 100–10,000 tokens of narrative text, often structured by sections and paragraphs.

Current approach (to be optimized): A sliding window token chunker with chunk_size = 7500 and chunk_overlap = 500 (tokens). This nearly maxes out the model context per chunk, with ~6.6% overlap. We need to verify if these values are appropriate.

Key Research Findings
Optimal Chunk Size Considerations

General best practices: Many sources suggest moderate chunk sizes (not too small or too close to max limit) for best semantic embedding:

OpenAI’s guidance: ~1000 tokens per chunk is a good starting point, balancing context and efficiency
dev.to
. Smaller, well-structured chunks often yield higher-quality embeddings
dev.to
.

Microsoft (Azure Search): Start with 512 tokens (~2000 chars) per chunk as a baseline
learn.microsoft.com
. This size is “sufficient for semantically meaningful paragraphs” while fitting model limits.

Industry experience: A “Goldilocks” range of 128–512 tokens is often optimal for RAG systems
linkedin.com
. Smaller chunks (e.g. 128–256 tokens) give precise matches for specific queries, whereas larger (256–512) carry more context for complex queries
linkedin.com
. Going beyond ~512 tokens starts to add noise and may dilute the embedding’s focus
linkedin.com
linkedin.com
.

Code vs. text differences: Source code can often be segmented by logical units (functions, classes) rather than uniform token count:

Code tends to be modular. Each function or class could be a natural chunk, often well under 8000 tokens. Embedding whole files (which might contain multiple unrelated functions) can reduce retrieval precision (the embedding mixes multiple topics)
studios.trychroma.com
research.trychroma.com
. It’s generally better to chunk code by function or logical block so each vector represents a coherent piece of functionality.

Documentation or prose may require larger chunks to preserve narrative context, but overly large text chunks can include unrelated subtopics
learn.microsoft.com
research.trychroma.com
. A common heuristic is chunk by paragraph/section or aim for a few hundred tokens per chunk for text.

Empirical insights: Recent evaluations confirm that chunking strategy significantly impacts retrieval performance
research.trychroma.com
research.trychroma.com
:

In a study by Chroma, a simple RecursiveCharacter splitter with chunk size ~200 tokens (no overlap) performed consistently well, achieving high recall and precision across benchmarks
research.trychroma.com
research.trychroma.com
. It outperformed fixed 200-token chunks, indicating the importance of splitting at natural boundaries
research.trychroma.com
research.trychroma.com
. However, extremely small chunks (<100 tokens) can hurt recall by fragmenting context too much
research.trychroma.com
.

OpenAI’s own RAG examples use chunk sizes around 800–1000 tokens. Notably, the default in some OpenAI-guided implementations is ~800 token chunks with 50% overlap
research.trychroma.com
, but research found this default underperformed – yielding below-average recall and the lowest precision in one evaluation
research.trychroma.com
. This suggests 800×2 (with half overlap effectively) was too redundant and perhaps still too large.

A recent NVIDIA study tested token-based chunk sizes of 128, 256, 512, 1024, 2048 on QA tasks. They found factoid queries benefited from smaller chunks (256–512), while more complex questions did well with 1024 or page-sized chunks
developer.nvidia.com
developer.nvidia.com
. Crucially, they observed diminishing returns beyond ~1024 tokens – and recommend testing in the 256–1024 range for optimal balance
developer.nvidia.com
linkedin.com
.

Recommendation: For code search, use smaller, focused chunks rather than near the 8191-token max. Aim for on the order of a few hundred tokens up to ~1000 tokens per chunk:

Code: Often 300–600 tokens (roughly a function or small group of related functions). This often corresponds to a function of ~30-50 lines, which many code indexing tools use as a guideline. For example, LlamaIndex’s CodeSplitter demo chunks code into 40-line blocks (with overlap) capped at ~1500 characters
lancedb.com
lancedb.com
 (~200–300 tokens). This ensures each chunk is a self-contained snippet of code logic.

Documentation: Can tolerate larger chunks. 500–1000 tokens (e.g. a few paragraphs) is a reasonable target
linkedin.com
, especially if using a text splitter that respects paragraph or section boundaries. This keeps related info together for context, which is important for understanding prose.

Summaries: Usually already short (<500 tokens). These can be embedded as single chunks in most cases. If a summary is unusually long, splitting it similar to documentation (paragraph by paragraph or ~500 token chunks) would work, but often not needed.

Overlap (Sliding Window) Considerations

Why overlap: Overlapping content between chunks prevents important context from being “cut off” at chunk boundaries
dev.to
learn.microsoft.com
. Without overlap, a question about text at a boundary might miss context that lies just outside the chunk. A small overlap ensures continuity – the model sees the end of the previous segment again at the start of the next.

Common recommendations:

10–20% overlap is a widely cited rule of thumb
dev.to
qdrant.tech
. This amount is “usually a good balance”
qdrant.tech
, capturing a bit of the prior context without too much redundancy. For example, with 1000-token chunks, overlap ~100–200 tokens (10–20%) is advised
dev.to
. Microsoft’s guidance starts with ~25% overlap (e.g. 128 tokens for a 512-token chunk)
learn.microsoft.com
, which is in the same ballpark. The key is to cover any partial sentence or code block that might otherwise get split.

High-overlap scenarios: In cases where missing even a small detail is very costly (high-recall requirements), overlap can be higher (even 25–50%)
qdrant.tech
. This ensures maximum recall at the expense of many duplicate tokens. Such heavy overlap is usually unnecessary for code search though, and it bloats index size
qdrant.tech
.

No overlap: If storage or speed is critical and some context loss is acceptable, overlap can be 0%. But expect a hit to recall – relevant information right at chunk edges might be missed by the retriever
research.trychroma.com
. Overlap=0 is generally only used when absolutely minimizing chunk count (or using intelligent chunking that naturally aligns boundaries with semantic breaks).

Empirical evidence:

The NVIDIA experiments varied overlap 10%, 15%, 20% (with 1024-token chunks) and found 15% overlap performed best on their benchmark
developer.nvidia.com
developer.nvidia.com
. This aligns with common practice in industry (usually choosing a value in the teens).

Chroma’s study noted that adding overlap improves recall for smaller chunk sizes. For example, with ~250-token chunks, recall jumped from 0.771 to 0.824 when adding 50% overlap (125 tokens)
research.trychroma.com
. However, too much overlap can actually lower precision and “information density” (the Intersection-over-Union metric dropped with more redundancy)
research.trychroma.com
research.trychroma.com
. Essentially, beyond an optimal point, overlap yields diminishing returns and wastes space
qdrant.tech
.

In code-specific contexts, overlap is often less crucial if chunking is done along logical boundaries. E.g. if each function is separate, you don’t need large overlaps. But if a single function is so large that it gets split into multiple chunks, overlapping a few lines between those chunks is wise to ensure the second chunk knows the function signature or preceding logic. LangChain’s CodeTextSplitter by default uses some overlap as well (it inherits from RecursiveCharacterTextSplitter). In one example, Python code was chunked with no overlap when functions were short
medium.com
medium.com
, but for longer code blocks an overlap could be introduced.

Recommendation: Use an overlap ~15% of chunk size for most cases
linkedin.com
. In practice:

For ~500-token chunks, include ~50–75 tokens overlap.

For ~1000-token chunks, ~100–150 token overlap (about 1–2 paragraphs of text, or a few lines of code) is a good starting point.

Adjust if needed: if you notice queries missing context from the very edge of chunks, you might increase overlap to 20%. If you find a lot of duplicate content in search results, you might dial it back toward 10%. The goal is “maintaining continuity while avoiding excessive redundancy.”
linkedin.com

For code chunks, overlap can often be smaller (or even zero) if using structure-aware splitting. Because ideally you end a chunk at a function boundary, the next chunk begins at the next function – in that case, there’s little need to overlap. If splitting code purely by tokens in the middle of a long function, include maybe 1–2 lines overlap (e.g. 20–30 tokens) to ensure the second chunk isn’t missing the context of the function’s start.

Bottom line: start with ~15% overlap for text; for code, strive to chunk at logical breakpoints (minimizing the need for overlap), but if not possible, use a small overlap (~10% or a few lines of code).

Code Chunking vs. Prose Chunking

Code is different from natural text, and chunking should reflect that:

Chunk by syntax or structure when possible for code. Tools like LangChain’s CodeTextSplitter or LlamaIndex’s CodeSplitter attempt to split source code along logical boundaries (e.g. between functions, classes, or after import statements) rather than arbitrarily mid-code
medium.com
lancedb.com
. This yields chunks that make sense on their own. For example, splitting Python code with RecursiveCharacterTextSplitter.from_language(language=Language.PYTHON, ...) will use language-specific separators (e.g. double newlines, indentations) to avoid breaking a code block in half
medium.com
. In the demonstration, a 50-token chunk size was used just for illustration, and it split the code so each chunk contained one logical segment (the function definition vs. the function call in the sample)
medium.com
medium.com
.

Avoid splitting a function’s body into separate chunks if possible. Each function or method can often be a self-contained semantic unit. If a function is extremely long (hundreds of lines), you might chunk within it, but try to do so at natural breakpoints (e.g. between logical sections or loop bodies) and include overlap of a few lines so the reassembled context is intact. Breaking code mid-statement or cutting a function in half without overlap can confuse the embedding (the chunk loses some meaning) and hurt retrieval if the query refers to the function as a whole.

Example: Suppose we have a Python file with two functions:

def authenticate(user, pwd):
    # ... authentication logic ...
    return success

def logout(user):
    # ... logout logic ...
    return result


A token-based splitter with a 1000-token limit might lump both authenticate and logout functions into one chunk if they together stay under 1000 tokens. This single chunk’s embedding mixes two separate topics (auth vs logout). A query “find the logout logic” might still retrieve the chunk (since it contains the word “logout”), but its similarity score could be lower because the chunk also contains lots of authentication logic. A code-aware splitter would produce two chunks – one per function – with clean separation
studios.trychroma.com
studios.trychroma.com
. Each chunk embedding is highly focused, improving precision. Indeed, Sourcegraph’s Cody (a code AI tool) team notes they “chunk at the code level” and try to match chunks to symbols (functions/classes) exactly
studios.trychroma.com
studios.trychroma.com
. This ensures each chunk corresponds to a distinct unit of code for retrieval.

Preserve documentation structure: For markdown or docs, consider splitting by headings or sections. Tools like MarkdownHeaderSplitter (LangChain) or Azure Cognitive Search’s built-in skills use headings as chunk boundaries
learn.microsoft.com
. This way, each chunk might be e.g. a section under a H2 heading. If using a simpler approach, splitting by paragraph with a max token limit works: e.g. chunk at ~500 tokens but ensure you don’t cut paragraphs in half (a “recursive splitter” can try larger chunks, then fall back to sentence boundaries). This keeps semantic coherence in each chunk
learn.microsoft.com
.

Different chunk sizes per content type: It can make sense to configure different chunking for different data:

Code files – If using a function-per-chunk strategy, chunk size might be “unlimited” but logically one function (in practice, maybe a cap of a few thousand tokens if a single function is huge). If using uniform chunks, perhaps choose a smaller token limit (e.g. 400-600 tokens) for code to avoid blending unrelated code.

Summaries – Likely no chunking needed unless they exceed a threshold. They are short and to the point, so one chunk per summary is fine (just verify token count; if some summaries are >8191 tokens, then chunk those, but that’s rare).

Markdown docs – Use a larger chunk size (maybe 800-1000 tokens) since prose often requires more context to be meaningful. You could use the same base tokenizer but a higher chunk_size for docs than for code.

By tailoring chunking to content, you improve embedding quality. Many RAG frameworks allow this (e.g., RecursiveCharacterTextSplitter.from_language(Language.MARKDOWN, ...) can handle markdown differently than code). Real-world systems: Cursor AI indexes code by splitting into small pieces (and even generates summaries for each) before embedding
forum.cursor.com
forum.cursor.com
; Roo Code (open source) reportedly uses a chunk size of 100–1000 characters for code segments, suggesting dynamically sized chunks based on code structure (ensuring no chunk is too small or too large)
github.com
.

Impact on Search Performance (Precision & Recall)

Chunk size vs. Precision/Recall: There is an inherent trade-off:

Smaller chunks (more, finer-grained pieces):

Precision: Higher. Each chunk is tightly focused, so when a user’s query embedding matches a chunk, it’s likely a very relevant snippet. Fewer irrelevant sentences are carried along. A study showed ~30–50% higher retrieval precision when using intelligently chunked smaller segments vs. naive large chunks
medium.com
medium.com
. This is because the vector space representation is more targeted. In our context, a query like “password validation logic” will closely match the small chunk that specifically contains validate_password() rather than a big file chunk that also contains other logic.

Recall: Can suffer if too extreme. If a single logical answer is split across multiple tiny chunks, the user (or LLM) might need to gather multiple pieces. For example, if a function’s first half and second half are separate chunks, a query about the function might retrieve only one half if the other half didn’t contain enough keywords. That’s why some overlap or careful splitting is needed to keep each chunk self-contained. If chunks are too small, the system might miss some context and fail to retrieve a relevant piece (false negative). Chroma’s evaluation noted that “chunks which are too small fail to capture necessary context within a single unit,” hurting recall
research.trychroma.com
research.trychroma.com
.

Larger chunks (fewer, broader pieces):

Recall: Higher likelihood that something in the chunk will match the query (since the chunk covers more ground). You might retrieve that chunk for a variety of related queries. This is good for recall because fewer relevant details slip through the cracks. However, if the chunk is very large, the cosine similarity may be averaged out by a lot of unrelated content, so the relevant part’s impact is “diluted.” That can actually lower recall in vector search, as the query embedding might not be as close to the chunk embedding despite the chunk containing the answer. There is speculation that recall peaks at a certain chunk size, then declines if chunks get too big and semantically “noisy”
research.trychroma.com
research.trychroma.com
.

Precision: Tends to drop. A large chunk that gets retrieved might only be partially relevant to the query. The user or LLM then has to sift through extra text to find the answer. In an extreme case, if we embedded entire files, a query might retrieve a file that indeed contains the answer somewhere, but also a lot of unrelated code – making it harder to identify the answer. The NVIDIA summary pointed out that page-level chunks gave very consistent (low-variance) performance, but smaller chunks excelled on direct factoid queries
developer.nvidia.com
. The LinkedIn “Goldilocks” article succinctly says: too wide a chunk and the system “can’t focus on what matters.”
linkedin.com
.

Empirical trade-off example: In one evaluation (Chroma’s token-level retrieval test), a ~200-token chunk had recall ~0.88 and precision ~0.07 (they measured precision in a strict token-match sense)
research.trychroma.com
. Doubling chunk size to 400 tokens increased recall slightly (~0.91) but precision dropped (to ~0.045)
research.trychroma.com
research.trychroma.com
. This indicates more content per chunk made each retrieved chunk less pure. The highest recall (0.919) was achieved by a smart semantic chunking (LLM-based) at the cost of average precision
research.trychroma.com
research.trychroma.com
. These results highlight that the “sweet spot” depends on whether you favor finding all possible relevant info (recall) vs. getting highly relevant results at top ranks (precision). For code search, precision at top k is often more important – a developer wants the snippet that answers their question to show up in the top 3–5 results. Thus leaning toward smaller, precise chunks is wise, as long as recall stays acceptable (which overlap and good splitting help ensure).

Storage and performance: More chunks means more vectors to store and more comparisons per query:

If you halve the chunk size, roughly you’ll double the number of chunks (for a given amount of text, ignoring overlap). This doubles index size and likely doubles query latency (since cosine similarity will be computed against twice as many vectors). In an in-memory numpy search, this is linear scaling. For example, going from 512-token chunks to 256-token chunks yields finer granularity but about 2× vectors.

There is a balance: extremely small chunks (say every 50 tokens) would explode the vector count and slow down search considerably, for marginal gains in accuracy (and likely a loss of accuracy if context is broken too much). On the other hand, extremely large chunks (7500 tokens) minimize vector count but could miss details in similarity matching
research.trychroma.com
. We must find a sweet spot that balances quality and efficiency. Based on multiple sources above, that tends to be in the low hundreds of tokens per chunk for code/text. In practice, an average code file (say 3000 tokens) might yield ~6 chunks at 500 tokens each (with overlap) – that’s manageable. If we went with 7500-token chunks, that same file would be 1 chunk; fewer vectors, but likely a lower-quality embedding for search.

Many production systems settle around a few hundred tokens per chunk for these reasons. For instance, Sourcegraph (earlier version of Cody) used OpenAI’s text-embedding-ada-002 and initially chunked entire files, but found that unscalable and less effective, and moved toward smaller “context” snippets. Their team mentioned embeddings add complexity especially as codebase size grows (millions of vectors)
sourcegraph.com
sourcegraph.com
 – implying chunking too finely can be hard at very large scale, so a compromise is needed. They are even exploring replacing some embedding usage with more symbolic code graph search for efficiency
sourcegraph.com
.

Practical tip: Monitor recall@K – e.g. what fraction of known relevant code locations are retrieved in top 10 or top 5 – as you adjust chunk size. If recall@10 is low, maybe chunks are too small/disjoint (try increasing size or overlap). Monitor precision@K (or qualitatively, relevance of top results) – if many retrieved chunks contain mostly irrelevant text with maybe one line matching the query, chunks might be too large (try smaller). Also consider search latency: if queries slow down due to huge vector counts, you might slightly increase chunk size to reduce vector count, until latency is acceptable.

Recommended Chunking Parameters

Based on the above, our actionable recommendations for using OpenAI text-embedding-3-small in a code search context are:

Chunk size for code (CHUNK_SIZE_CODE): 400 tokens per chunk (approximate guideline). This is roughly a few hundred words or ~40 lines of code. It is large enough to contain a whole function or a meaningful code block, but small enough to not mix unrelated code. This value is well within the 8191 limit (for safety, leaving plenty of buffer) and aligns with the range that experts find effective (128–512 tokens)
linkedin.com
. You might adjust in the 300–600 range based on testing, but 400 is a solid starting point for Python/TypeScript given typical function sizes.

For code, also consider an alternative: chunk by function or class rather than a strict token count. If you implement a parser that splits code at definitions (using, e.g., the AST or regex for ^def and ^class in Python), you might let short functions be individual chunks even if <400 tokens, and split big functions into multiple ~400-token chunks. This ensures semantic coherence. (For our immediate implementation, using a fixed size is simpler, but keep this in mind as a potential improvement.)

Overlap for code (CHUNK_OVERLAP_CODE): 50 tokens (approximately 1–2 lines of code or a short comment). Rationale: if using structured splitting by function, you can set overlap to 0 because chunks naturally separate at boundaries. But with a fixed-size window, a small overlap guards against boundary issues (like a function cut in two). We choose 50 (which is 12.5% of 400) as a light overlap – enough to include perhaps a function signature or the end of a loop from the previous chunk. Code is fairly dense, so we don’t want to repeat too much. This overlaps recommendation falls in the 10–15% range which literature suggests
qdrant.tech
linkedin.com
 and should preserve context without excessive duplication.

Chunk size for documentation (CHUNK_SIZE_DOC): 800 tokens per chunk. This is closer to OpenAI’s 1000-token guidance
dev.to
 and allows paragraphs to stay together. For narrative text, we prefer larger chunks to maintain context. 800 tokens (~600–700 words) might equate to a few paragraphs or one subsection of a doc. This size also leaves a buffer under 8191 for any slight token count underestimation. It’s within the 512–1024 range that seems effective for more complex text and ensures enough context for answering higher-level questions from docs
linkedin.com
linkedin.com
.

Overlap for documentation (CHUNK_OVERLAP_DOC): 120 tokens (15% of 800). This is about 1–2 sentences overlap between doc chunks. Since text ideas can flow between paragraphs, a bit more overlap is justified compared to code. Microsoft’s example used 128 overlap on 512 chunks
learn.microsoft.com
, which is 25%; we opt for ~15% as a starting point and can increase if we notice the need. This choice is supported by experiments that found ~15% optimal in some cases
developer.nvidia.com
 and general advice of 10–20%
linkedin.com
.

Chunking approach: Use token-based splitting (with tiktoken for accuracy) combined with recursive splitting by separators. In code, separators could be \n\n (blank lines), \n (line breaks), space, etc., so that the splitter tries not to break in the middle of a line if possible. In LangChain, this is done via RecursiveCharacterTextSplitter with a list of separators. A pseudo-code setup:

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.text_splitter import Language

code_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=400,
    chunk_overlap=50
)
doc_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.MARKDOWN,
    chunk_size=800,
    chunk_overlap=120
)


These utilize language-specific heuristics (for Python, for example, it will prefer splitting at blank lines or indent decreases)
medium.com
medium.com
. Each splitter’s split_text() can then be applied to the content. By using from_language, we handle code vs. markdown appropriately with minimal custom code.

Validation: After implementing, we should verify the effectiveness of these parameters. We can do a trial on a subset of our codebase: embed some known files and run sample queries (e.g., “find authentication logic” or “where is logout function called”). Check if relevant chunks surface in top results. If we find that relevant pieces are being missed, we might increase chunk size or overlap. If irrelevant chunks often rank highly, perhaps our chunks are too large (embedding unrelated text) and we might decrease size. The goal is a balance where each chunk is just big enough to provide needed context, but not so big that it muddies the embedding.

Example of Code Chunking

To illustrate the difference between a naive chunking and a code-aware approach, consider a simplified example:

Suppose we have a Python file:

# file: example.py
def load_config(path):
    # ... code to load configuration ...
    return config

def init_db(conn_str):
    # ... code to initialize database ...
    return db_connection


Simple token-based chunking (chunk_size=1000, overlap=0): This might produce one single chunk containing both load_config and init_db (since together they are well under 1000 tokens). The resulting chunk embedding represents both functions together.

Code-aware chunking (using our recommended splitter): This will likely split at the blank line between the two function definitions. We’d get two chunks:

'def load_config(path): ... return config'

'def init_db(conn_str): ... return db_connection'
Each chunk corresponds to one function. In an embedding vector space, a query like “initialize database” will be much more similar to the second chunk’s embedding than the first. If they were one chunk, the query’s similarity might be slightly diluted by the presence of config-loading logic. By chunking per function, we preserve high precision.

This demonstrates how code chunking at logical boundaries yields more relevant search results. As another benefit, maintenance is easier: if only init_db function changes, we only need to re-embed that chunk, not the whole file (important for incremental indexing).

Pitfalls and How to Mitigate Them

When chunking for embeddings, beware of common pitfalls:

1. Chunks too small (over-segmentation):
If you make chunks very tiny (e.g. a few words or one line of code each), you lose context that could be important for understanding. For code, a single line by itself (say an if statement) might not convey the overall logic and thus its embedding may not match a query about the function’s purpose. Tiny chunks also increase the number of vectors massively, hurting performance. Mitigation: Choose a reasonable minimum chunk size (our recommendations above). Ensure each chunk is a complete thought – for code, usually an entire small block; for text, at least a full sentence or paragraph. If using recursive splitting, set a split length threshold so you don’t split below a certain unit (e.g., don’t split within a sentence or within a code statement). The Qdrant guide emphasizes preserving semantic units for this reason
qdrant.tech
qdrant.tech
.

2. Chunks too large (under-segmentation):
On the flip side, embedding extremely large chunks (close to the 8191-token limit) might include multiple concepts, leading to a “blurry” embedding. The model has to compress all that content into 1536 dimensions, potentially averaging out distinct topics. This can dilute the signal for any one topic
research.trychroma.com
. It also risks hitting token limits if any overhead is introduced (though for embeddings, it’s just input). Mitigation: Even if the model allows 8191 tokens, do not aim for that max unless absolutely necessary. Our plan to use ~400–800 token chunks is intentionally well below the max, as OpenAI notes staying under the limit improves performance and avoids errors
cookbook.openai.com
cookbook.openai.com
. Also, monitor if search results from large chunks tend to be off-target – that might indicate you need to break them down more.

3. Insufficient overlap (context lost at boundaries):
If chunks have no overlap, an important detail at the end of one chunk may not appear in the next chunk, and a query looking for it might miss both. For example, a code comment describing a function could be at the end of chunk1, and the function body in chunk2; a query for that comment text would retrieve chunk1, but chunk2 might be more relevant ultimately. With no overlap, chunk2 wouldn’t contain the comment. Mitigation: Use the overlaps as recommended (10–20%). In the code example, a small overlap could include the comment in both chunks, so either chunk retrieved would have useful info. Our overlap choices aim to include any “boundary words” in both chunks, smoothing this issue. Empirically, we saw that zero-overlap configurations had lower recall in tests
research.trychroma.com
, so we avoid zero except where chunks are naturally well-separated.

4. Overlap too large (excessive duplication):
While some overlap is good, too much can lead to many chunks containing very similar content. This wastes storage and can skew search results (the same passage might appear in multiple retrieved chunks). For instance, 50% overlap means you’re indexing every sentence roughly twice. Mitigation: Stick to moderate overlap. If you find your top-10 results include multiple overlapping chunks that are nearly the same, consider reducing the overlap. You want just enough to preserve context, no more. As our references noted, overlap beyond ~20% didn’t notably help and can hurt efficiency
qdrant.tech
research.trychroma.com
.

5. Breaking code or sentences in unnatural ways:
If a chunk breaks in the middle of a sentence or a code statement, the partial chunk may be hard to interpret. An embedding model will still produce a vector, but it might be less accurate. For example, a chunk that starts mid-function (missing the function name and parameters) might not clearly represent what that code does, making it harder to match with a query. Mitigation: Use smart splitting strategies. For code, ensure you don’t split in the middle of a function if possible – better to split before the def or at least include the def line with both halves (via overlap) if a function must span chunks. For text, prefer splitting at punctuation or paragraph boundaries. Many libraries (LangChain, etc.) do this by providing a list of separators (like ["\n\n", ". ", " "]) so they try a big split first, then smaller if needed
dev.to
dev.to
. Using such tools helps avoid mid-sentence splits. In our configuration, the RecursiveCharacterTextSplitter will first try to cut at double newlines (paragraph breaks) for docs, or for code at blank lines/indent boundaries, only resorting to breaking in the middle of text if absolutely necessary.

6. Embedding irrelevant content or secrets: (A tangential pitfall) While not directly about chunk size, when chunking code one must be careful about excluding sensitive or irrelevant parts. E.g. large JSON blobs, license headers, or secrets in code shouldn’t be embedded. Mitigation: Filter out files or sections (like .env secrets) from the embedding process. Some tools have heuristics (Cursor’s “scrubber” avoids sending secrets to embedding API
forum.cursor.com
). Ensure your chunking pipeline skips binary or non-text files and possibly big auto-generated docs that don’t need semantic search.

7. Assuming one size fits all:
Chunking strategy might need tweaking per project or content type. It’s a mistake to assume the initial parameters are optimal for every scenario. Mitigation: Treat our recommended values as a starting point, and be prepared to A/B test. For instance, if your codebase has very long functions, you might increase chunk_size_code to 600 to fit more of a function in one chunk. If your documentation is very reference-heavy with short Q&A pairs, you might actually shrink chunk_size_doc to ~300 for more precise matching. Always evaluate with real queries.

Validation metrics: To catch issues, use metrics:

Recall@K: Create a set of test queries with known relevant code sections (even 5-10 queries based on actual functions in the repo). Compute how many of those known relevant chunks appear in the top K results (K=5 or 10). Low recall indicates chunking may be too fine or missing context (increase chunk size or overlap).

Precision@K / MRR: Look at the rank of the correct snippet for each query. If it’s often lower than ideal (or incorrect chunks rank higher), that could mean chunks are too broad (embedding noise, so irrelevant stuff sometimes looks similar to the query). Smaller, more focused chunks can improve this by reducing noise.

Overlap impact: You can experiment by embedding with 0%, 10%, 20% overlap on a small subset and see if queries return more complete context with overlap. If a query result seems incomplete (e.g. chunk has half the answer), that’s a sign you needed either overlap or a larger chunk.

Qualitative check: Take a few adjacent chunks from your index and read them – do they each make sense alone? If you find chunks that are just “fragmented” (e.g. a chunk that is only a trailing half of a sentence or a code block with no context), that’s a chunking fail. Adjust parameters or splitting logic to avoid such fragments (likely by increasing overlap or using a smarter separator).

Integration Considerations

Lastly, how do these choices play out in our system’s integration and maintenance?

Different chunking for different content: We’ve already addressed using different chunk sizes for code vs. documentation. This will require keeping track of content type (which we can infer from file extension or metadata) and applying the appropriate splitter. This is straightforward – for example, maintain two splitter instances as shown in code above. The search procedure can be unified (the vectors all sit in one index), but you might also consider tagging vectors with their type (code or docs) in metadata, in case you want to filter results or boost one type based on query (this is an advanced consideration – e.g., if user query mentions “documentation” you might prioritize doc chunks).

Incremental re-indexing: In a codebase that updates, re-indexing efficiently is important. Our chunking strategy should facilitate that:

If you chunk by function (or at least by small blocks), when one function changes, ideally only that function’s chunk needs updating. This is good – it means we can hash each chunk’s content and only re-embed if it changed. If instead we had one huge chunk per file, a one-line change in a file would force re-embedding the entire file’s chunk. Smaller chunks = more targeted updates (but also more hashes to manage).

Using consistent chunk boundaries is key for stable indexing. If chunking is purely by fixed window and a change at the top of file shifts all subsequent chunks, then everything after changes. A logical chunking (by function/section) is more stable: adding a new function doesn’t affect embeddings of others except maybe shifting their order in storage, which is fine.

Our approach with RecursiveCharacterTextSplitter and specific chunk sizes is deterministic given the content, but content changes could shift chunk boundaries. One way to mitigate large shifts is to insert chunk breaks at logical places (which tend to remain logical even if code above changes). So, favor structure-based splitting where possible – it inherently localizes changes.

Tokenizer considerations (cl100k_base):

This tokenizer is used for both GPT-4/3.5 context and embeddings. It treats code and text tokens differently than older tokenizers (for example, it can encode common keywords or indentations efficiently). One subtle effect: indentation and punctuation in code will count as tokens. For instance, a line with 4-space indent may contribute a token. So token counts for code can be a bit unintuitive. Always use tiktoken to count tokens rather than assuming (we should in our implementation). The encoder.encode(content) in our chunk function is appropriate
cookbook.openai.com
.

The 8191 limit is plenty high, so our 400/800 token chunks are safely within limits even after adding a few overlap tokens. We don’t have to worry about exact byte size or such – just token count.

Make sure to leave a small buffer in chunk sizes so that if there are edge cases (like a very long word or multi-byte characters), we don’t accidentally hit 8191. Our recommendations already have a large buffer (400 << 8191).

Batching limits: Also note, OpenAI’s embedding API has a max of 8191 tokens per request (for one input). If you send multiple chunks in one request, each is counted separately but the total must not exceed some large number (the OpenAI documentation mentions a 16k limit for the sum in some cases). It’s safer to embed chunks one by one or in small batches to avoid hitting any request size caps
community.openai.com
community.openai.com
.

Final Summary of Choices: We will implement chunking as follows:

Code files – Use a Python (or TypeScript) code text splitter: target ~400 tokens, 50 overlap. Likely yields 1 chunk per function or so. This balances precision (function-level granularity) with enough context (each chunk contains the whole function logic). It also keeps vector count reasonable. Evidence from benchmarks suggests this size is effective for semantic search
research.trychroma.com
linkedin.com
.

AI Summaries – Since these are short, we treat each summary as one chunk (no splitting unless >8191 tokens, which is unlikely). This gives one embedding per summary which should capture its content.

Markdown docs – Use a markdown-aware splitter: target ~800 tokens, 120 overlap. This keeps sections together. Users querying docs (e.g. “installation instructions”) will get a chunk that contains the full relevant section (perhaps an entire FAQ answer or a couple paragraphs) without needing to assemble multiple chunks. Yet it’s not so large as to include unrelated sections. This approach is recommended for technical docs
linkedin.com
.

Rationale: These parameter choices are grounded in best practices and research:

Balanced chunk sizes (hundreds of tokens) are proven to improve retrieval outcomes
linkedin.com
research.trychroma.com
. They capture semantic units fully, which is crucial for both code and text.

Overlap ~15% ensures continuity. As one source put it, “smooths over hard boundaries” without “excessive duplication”
linkedin.com
.

Code vs Text differences: Our plan respects that code benefits from structure-based chunking, as used by tools like LangChain, LlamaIndex, and production systems
lancedb.com
studios.trychroma.com
. Meanwhile, our doc chunking is aligned with recommendations for technical content (256–512 or more tokens with recursive splitting)
linkedin.com
.

By implementing these chunking parameters, we anticipate improved search precision (relevant snippets ranking higher) and strong recall (important code not omitted due to chunking). These settings are a starting point – we will iteratively refine by measuring search results – but they are backed by evidence and practices from OpenAI, Microsoft, and others to be reasonable defaults for a code semantic search system.

Sources:

OpenAI & community guidance on chunking size/overlap
dev.to
dev.to
learn.microsoft.com
qdrant.tech

Research on chunking impact (Chroma report, NVIDIA blog)
research.trychroma.com
research.trychroma.com
developer.nvidia.com

RAG frameworks (LangChain, LlamaIndex) and code-specific strategies
medium.com
lancedb.com

Production insights (Sourcegraph Cody, etc.) on code chunking by symbol