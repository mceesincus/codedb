from __future__ import annotations

from tree_sitter import Node


def child_text(node: Node | None, source_text: str) -> str:
    if node is None:
        return ""
    return source_text[node.start_byte : node.end_byte]


def compact_signature(node: Node, source_text: str) -> str:
    text = child_text(node, source_text).strip()
    first_line = text.splitlines()[0].strip()
    return first_line[:240]


def line_span(node: Node) -> tuple[int, int]:
    return node.start_point.row + 1, node.end_point.row + 1


def walk(node: Node):
    yield node
    for child in node.children:
        yield from walk(child)

