"""Explicit, deterministic source bundling; no implicit filesystem imports."""
from __future__ import annotations

from compiler.htmlk import compile_html
from compiler.language import CompileError, KernelParser, MAX_SOURCE_BYTES, parse

MAX_LIBRARIES = 8


class RootPosition(KernelParser):
    """The canonical HTMLK parser, recording only the root opening tag end."""
    root_end: int | None = None

    def __init__(self, source: str) -> None:
        super().__init__()
        self.source_lines = source.split("\n")
        # HTMLParser positions advance on LF, not arbitrary Unicode separators.

    def handle_starttag(self, tag, attrs):
        at_root = not self.stack
        super().handle_starttag(tag, attrs)
        if at_root:
            line, column = self.getpos()
            self.root_end = sum(len(part) + 1 for part in self.source_lines[:line-1])
            self.root_end += column + len(self.get_starttag_text())


def bundle(source: str, libraries: list[str], *, target: str) -> str:
    """Compose explicit function fragments into one checked HTMLK source."""
    if not 1 <= len(libraries) <= MAX_LIBRARIES:
        raise CompileError(f"bundle requires 1..{MAX_LIBRARIES} explicit libraries")
    if sum(len(part.encode("utf-8")) for part in [source, *libraries]) > MAX_SOURCE_BYTES:
        raise CompileError("combined source exceeds maximum source size")
    # Check app syntax before insertion. Missing library function references
    # are checked by the final compiler, after the complete source is formed.
    app = RootPosition(source)
    app.feed(source)
    app.close()
    app.finish()
    assert app.root_end is not None
    for index, library in enumerate(libraries, 1):
        # A synthetic entrypoint permits canonical parsing of pure function
        # fragments without adding a second grammar or accepting extra roots.
        try:
            parsed = parse("<kernel>\n" + library +
                           "\n<onboot><print>library check</print><halt/></onboot></kernel>")
            if not parsed.functions:
                raise CompileError("library must contain at least one function")
        except CompileError as exc:
            raise CompileError(f"library {index}: {exc}") from exc
    result = (source[:app.root_end] + "\n" + "\n".join(libraries) +
              "\n" + source[app.root_end:])
    # Exactly the resulting bytes are passed through the existing compiler.
    # This enforces aggregate node, array, function, cost and target limits.
    compile_html(result, target=target)
    return result
