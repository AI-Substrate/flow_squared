"""ParsingStage - Pipeline stage for AST parsing.

Wraps ASTParser adapter to extract CodeNodes from discovered files.
Iterates context.scan_results, parses each file, accumulates nodes.

Per Alignment Brief:
- Validates ast_parser not None (raises ValueError)
- Catches ASTParserError per file, appends to context.errors, continues
- Records metrics: parsing_nodes count, parsing_errors count
"""

from typing import TYPE_CHECKING

from fs2.core.adapters.exceptions import ASTParserError

if TYPE_CHECKING:
    from fs2.core.services.pipeline_context import PipelineContext


class ParsingStage:
    """Pipeline stage that parses files using ASTParser.

    This stage:
    - Validates ast_parser is present in context
    - Iterates context.scan_results
    - Calls ast_parser.parse() for each file
    - Accumulates nodes in context.nodes
    - Catches ASTParserError per file and appends to context.errors
    - Records parsing_nodes and parsing_errors in context.metrics
    """

    @property
    def name(self) -> str:
        """Human-readable stage name for logging and metrics."""
        return "parsing"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Parse files from scan_results using the AST parser.

        Args:
            context: Pipeline context with ast_parser adapter and scan_results.

        Returns:
            Context with nodes populated.

        Raises:
            ValueError: If context.ast_parser is None.
        """
        # Validate precondition
        if context.ast_parser is None:
            raise ValueError(
                "ParsingStage requires ast_parser to be set in context. "
                "Ensure ScanPipeline injects the ASTParser adapter."
            )

        error_count = 0

        for scan_result in context.scan_results:
            try:
                nodes = context.ast_parser.parse(scan_result.path)
                context.nodes.extend(nodes)
            except ASTParserError as e:
                # Collect error, don't raise - continue with other files
                context.errors.append(str(e))
                error_count += 1

        # Record metrics
        context.metrics["parsing_nodes"] = len(context.nodes)
        context.metrics["parsing_errors"] = error_count

        return context
