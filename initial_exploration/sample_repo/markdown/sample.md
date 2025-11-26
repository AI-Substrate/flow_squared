# Sample Markdown Document

This is a sample Markdown file for **tree-sitter** exploration.
It includes various *Markdown* constructs to test AST generation.

## Section 1: Text Formatting

Regular paragraph with **bold**, *italic*, and ***bold italic*** text.
Also `inline code` and ~~strikethrough~~.

### Subsection 1.1: Links and Images

Here's a [link to example](https://example.com "Example Title").
And an auto-link: <https://example.com>

![Alt text for image](image.png "Image Title")

Reference-style link: [example][ref1]

[ref1]: https://example.com

### Subsection 1.2: Lists

Unordered list:
- Item 1
- Item 2
  - Nested item 2.1
  - Nested item 2.2
    - Deep nested
- Item 3

Ordered list:
1. First item
2. Second item
   1. Nested ordered
   2. Another nested
3. Third item

Task list:
- [x] Completed task
- [ ] Incomplete task
- [ ] Another task

## Section 2: Code

Inline code: `const x = 42;`

Fenced code block with language:

```python
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
```

Another code block:

```javascript
const greet = (name) => {
    console.log(`Hello, ${name}!`);
};
```

Indented code block:

    function indented() {
        return "This is indented code";
    }

## Section 3: Blockquotes

> This is a blockquote.
> It can span multiple lines.
>
> > Nested blockquote.
> > With multiple lines.
>
> Back to first level.

## Section 4: Tables

| Column 1 | Column 2 | Column 3 |
|----------|:--------:|---------:|
| Left     | Center   | Right    |
| Data 1   | Data 2   | Data 3   |
| More     | Data     | Here     |

## Section 5: Horizontal Rules

---

***

___

## Section 6: HTML Elements

<div class="custom">
  <p>HTML paragraph inside div</p>
</div>

<details>
<summary>Click to expand</summary>

Hidden content here.

</details>

## Section 7: Footnotes

Here's a sentence with a footnote[^1].

Another footnote reference[^note].

[^1]: This is the footnote content.
[^note]: This is another footnote with a label.

## Section 8: Definition Lists

Term 1
: Definition for term 1

Term 2
: Definition for term 2
: Another definition for term 2

## Section 9: Math (if supported)

Inline math: $E = mc^2$

Block math:

$$
\sum_{i=1}^{n} x_i = x_1 + x_2 + \cdots + x_n
$$

## Section 10: Escaping

Special characters: \* \_ \` \[ \] \{ \} \# \+ \- \. \!

## Conclusion

This document demonstrates various Markdown features for AST analysis.

---

*Document end*
