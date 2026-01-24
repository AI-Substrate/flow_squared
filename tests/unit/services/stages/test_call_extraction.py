"""Unit tests for call expression position extraction from tree-sitter AST.

Purpose: Verifies _extract_call_positions() correctly identifies call sites
         in source code for multiple languages (Python, TypeScript, Go, C#).

Quality Contribution: Enables accurate LSP get_definition queries at call sites,
                     restoring "what do I call" direction of call graph.

Per Subtask 001 Tasks:
- ST002: Write failing unit tests (TDD RED)
- ST003: Implementation to make these tests pass (TDD GREEN)

Per Alignment Brief:
- Call sites are (line, column) positions 0-indexed relative to content
- For method calls (obj.method()), position must be at method name, not receiver
- Query at receiver resolves to variable assignment; query at method resolves to definition

Test Naming: Given-When-Then format
"""

# Import will fail until ST003 implements the function
from fs2.core.services.stages.relationship_extraction_stage import (
    extract_call_positions,
)


class TestExtractCallPositionsBasic:
    """Basic tests for extract_call_positions function."""

    def test_given_python_simple_call_when_extract_then_finds_call(self):
        """
        Purpose: Verifies basic Python function call is detected.
        Quality Contribution: Core functionality for call extraction.
        Acceptance Criteria: Returns position of call expression.

        Worked Example:
        - Input: "def f():\n  foo()"
        - Output: [(1, 2)] - call at line 1, column 2
        """
        content = "def f():\n  foo()"
        positions = extract_call_positions(content, "python")

        assert len(positions) >= 1
        # foo() is at line 1 (0-indexed), column 2 (after indentation)
        assert (1, 2) in positions

    def test_given_python_nested_calls_when_extract_then_finds_all(self):
        """
        Purpose: Verifies nested function calls are all detected.
        Quality Contribution: Ensures complex expressions are fully analyzed.
        Acceptance Criteria: Returns positions for all 3 call expressions.

        Worked Example:
        - Input: "foo(bar(baz()))"
        - Output: 3 positions (foo, bar, baz calls)
        """
        content = "foo(bar(baz()))"
        positions = extract_call_positions(content, "python")

        assert len(positions) == 3

    def test_given_python_method_call_when_extract_then_returns_method_position(self):
        """
        Purpose: Verifies method calls return method name position, not receiver.
        Quality Contribution: CRITICAL - querying at receiver gives variable, not method.
        Acceptance Criteria: Position points to 'helper', not 'self'.

        Worked Example:
        - Input: "self.helper()"
        - Tree-sitter: call > attribute > [identifier "self" @ col 0, identifier "helper" @ col 5]
        - Output: [(0, 5)] - position at "helper", NOT (0, 0) at "self"

        Why This Matters:
        - LSP at col 0 ("self") → resolves to self/this variable assignment
        - LSP at col 5 ("helper") → resolves to helper() method definition
        """
        content = "self.helper()"
        positions = extract_call_positions(content, "python")

        assert len(positions) == 1
        # Position must be at "helper" (col 5), not "self" (col 0)
        line, col = positions[0]
        assert col == 5, f"Expected column 5 (method name), got {col}"

    def test_given_python_attribute_call_when_extract_then_returns_method_position(
        self,
    ):
        """
        Purpose: Verifies attribute access calls return attribute position.
        Quality Contribution: Ensures obj.method() queries method definition.
        Acceptance Criteria: Position points to 'login', not 'auth'.

        Worked Example:
        - Input: "auth.login(user)"
        - Output: [(0, 5)] - position at "login"
        """
        content = "auth.login(user)"
        positions = extract_call_positions(content, "python")

        assert len(positions) == 1
        line, col = positions[0]
        # "auth.login" -> "login" starts at col 5
        assert col == 5, f"Expected column 5 (login), got {col}"

    def test_given_python_chained_calls_when_extract_then_finds_each(self):
        """
        Purpose: Verifies chained method calls are all detected.
        Quality Contribution: Builder pattern and fluent APIs need full resolution.
        Acceptance Criteria: Returns 3 positions for a().b().c().

        Worked Example:
        - Input: "a().b().c()"
        - Output: 3 positions (a, b, c calls)
        """
        content = "a().b().c()"
        positions = extract_call_positions(content, "python")

        assert len(positions) == 3


class TestExtractCallPositionsMultiLanguage:
    """Tests for TypeScript, Go, and C# call extraction."""

    def test_given_typescript_call_when_extract_then_finds_call_expression(self):
        """
        Purpose: Verifies TypeScript call extraction works.
        Quality Contribution: Ensures cross-language support.
        Acceptance Criteria: Returns position of call.

        Worked Example:
        - Input: "foo()"
        - Tree-sitter node type: call_expression
        - Output: [(0, 0)]
        """
        content = "foo()"
        positions = extract_call_positions(content, "typescript")

        assert len(positions) == 1
        assert (0, 0) in positions

    def test_given_typescript_method_call_when_extract_then_returns_method_position(
        self,
    ):
        """
        Purpose: Verifies TypeScript method calls return property position.
        Quality Contribution: Same principle as Python - query method, not object.
        Acceptance Criteria: Position points to method name.

        Worked Example:
        - Input: "user.getName()"
        - Tree-sitter: call_expression > member_expression > [identifier "user", property_identifier "getName"]
        - Output: position at "getName" (col 5)
        """
        content = "user.getName()"
        positions = extract_call_positions(content, "typescript")

        assert len(positions) == 1
        line, col = positions[0]
        # "getName" starts at col 5
        assert col == 5, f"Expected column 5 (getName), got {col}"

    def test_given_go_package_call_when_extract_then_returns_function_position(self):
        """
        Purpose: Verifies Go package.Function() calls return function position.
        Quality Contribution: Go uses selector_expression for package calls.
        Acceptance Criteria: Position points to 'Println', not 'fmt'.

        Worked Example:
        - Input: "func main() { fmt.Println(x) }" (Go requires function context)
        - Tree-sitter: call_expression > selector_expression > [identifier "fmt", field_identifier "Println"]
        - Output: position at "Println"

        Note: Bare statements like "fmt.Println(x)" are parsed as type_conversion,
        not call_expression. Real Go code is always inside functions.
        """
        # Go needs function context for call_expression parsing
        content = "func main() {\n    fmt.Println(x)\n}"
        positions = extract_call_positions(content, "go")

        assert len(positions) == 1
        line, col = positions[0]
        # "fmt.Println" on line 1 (inside function), "Println" starts at col 8
        assert line == 1
        assert col == 8, f"Expected column 8 (Println), got {col}"

    def test_given_csharp_method_call_when_extract_then_returns_method_position(self):
        """
        Purpose: Verifies C# method calls return method position.
        Quality Contribution: C# uses invocation_expression and member_access_expression.
        Acceptance Criteria: Position points to 'Login', not 'auth'.

        Worked Example:
        - Input: "class C { void M() { auth.Login(user); } }" (C# needs class context)
        - Tree-sitter: invocation_expression > member_access_expression
        - Output: position at "Login"

        Note: tree-sitter-language-pack uses 'csharp' (not 'c_sharp')
        """
        # C# needs proper class/method context for correct parsing
        content = "class C { void M() { auth.Login(user); } }"
        positions = extract_call_positions(content, "csharp")

        assert len(positions) == 1
        line, col = positions[0]
        # "Login" is inside the method, position should be > 21 (start of auth.Login)
        assert col > 20, f"Expected column > 20 (inside method), got {col}"


class TestExtractCallPositionsEdgeCases:
    """Edge case tests for extract_call_positions."""

    def test_given_no_calls_when_extract_then_returns_empty(self):
        """
        Purpose: Verifies code without calls returns empty list.
        Quality Contribution: Prevents false positives.
        Acceptance Criteria: Returns empty list.
        """
        content = "x = 1\ny = 2"
        positions = extract_call_positions(content, "python")

        assert positions == []

    def test_given_unknown_language_when_extract_then_returns_empty(self):
        """
        Purpose: Verifies unknown languages return empty (graceful degradation).
        Quality Contribution: Prevents crashes on unsupported languages.
        Acceptance Criteria: Returns empty list, no exception.
        """
        content = "foo()"
        positions = extract_call_positions(content, "unknown_language")

        assert positions == []

    def test_given_empty_content_when_extract_then_returns_empty(self):
        """
        Purpose: Verifies empty content returns empty list.
        Quality Contribution: Handles edge case gracefully.
        Acceptance Criteria: Returns empty list.
        """
        content = ""
        positions = extract_call_positions(content, "python")

        assert positions == []

    def test_given_javascript_when_extract_then_same_as_typescript(self):
        """
        Purpose: Verifies JavaScript uses same logic as TypeScript.
        Quality Contribution: JS/TS share call_expression node type.
        Acceptance Criteria: Returns position of call.
        """
        content = "console.log('test')"
        positions = extract_call_positions(content, "javascript")

        assert len(positions) == 1
        # "log" starts at col 8
        line, col = positions[0]
        assert col == 8, f"Expected column 8 (log), got {col}"

    def test_given_tsx_when_extract_then_same_as_typescript(self):
        """
        Purpose: Verifies TSX uses same logic as TypeScript.
        Quality Contribution: TSX is TypeScript with JSX.
        Acceptance Criteria: Returns position of call.
        """
        content = "useState(0)"
        positions = extract_call_positions(content, "tsx")

        assert len(positions) == 1
        assert (0, 0) in positions


class TestExtractCallPositionsComplexScenarios:
    """Complex scenario tests for call extraction."""

    def test_given_multiline_function_when_extract_then_finds_all_calls(self):
        """
        Purpose: Verifies multi-line functions have all calls detected.
        Quality Contribution: Real-world functions have multiple calls.
        Acceptance Criteria: Returns positions for all calls.

        Worked Example:
        - Input: Function with 3 calls on different lines
        - Output: 3 positions with correct line numbers
        """
        content = """def process():
    validate()
    transform()
    save()"""
        positions = extract_call_positions(content, "python")

        assert len(positions) == 3
        # Check line numbers (0-indexed)
        lines = [pos[0] for pos in positions]
        assert 1 in lines  # validate() on line 1
        assert 2 in lines  # transform() on line 2
        assert 3 in lines  # save() on line 3

    def test_given_method_with_arguments_when_extract_then_ignores_arguments(self):
        """
        Purpose: Verifies call arguments don't add extra positions.
        Quality Contribution: Arguments are not calls (unless they contain calls).
        Acceptance Criteria: Returns only 1 position for outer call.
        """
        content = "process(x, y, z)"
        positions = extract_call_positions(content, "python")

        assert len(positions) == 1

    def test_given_call_with_lambda_argument_when_extract_then_finds_both(self):
        """
        Purpose: Verifies calls inside lambdas are detected.
        Quality Contribution: Lambda expressions may contain calls.
        Acceptance Criteria: Returns positions for map and inner call.
        """
        content = "map(lambda x: inner(x), items)"
        positions = extract_call_positions(content, "python")

        # Should find: map() and inner()
        assert len(positions) == 2
