"""Where a line's comment starts

A comment runs from the first `#` that is not inside a closed quoted string.
Quotes follow the tokenizer's atoms (`syntax._ATOM`): `"` always opens a
string, `'` only where a word cannot continue (`@layer='a#b'` is a string,
the apostrophe in `Joe's` is not). A string that is not closed on its line
protects nothing, so `"abc # note` is the text `"abc ` and a comment.

The parser, `syntax.tokenize()` / `complete()` and the GtkSourceView
definition must all agree with this.
"""

# After one of these (or at the start of the line) `'` opens a string: the
# characters a word never contains (see syntax._ATOM)
_QUOTE_OPENERS = frozenset(" \t[](){},:=\"@$<>&")


def comment_start(line: str) -> int:
    """Index of the `#` that starts the comment, or -1 when there is none"""
    i, n = 0, len(line)
    while i < n:
        char = line[i]
        if char == "#":
            return i
        if char == '"' or (char == "'" and (i == 0 or line[i - 1] in _QUOTE_OPENERS)):
            close = line.find(char, i + 1)
            if close >= 0:
                i = close + 1
                continue
        i += 1
    return -1


def strip_comment(line: str) -> str:
    """The line without its comment"""
    at = comment_start(line)
    return line if at < 0 else line[:at]
