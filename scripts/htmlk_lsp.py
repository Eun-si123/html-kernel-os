#!/usr/bin/env python3
"""Bounded HTML Kernel Language Server Protocol 3.x stdio adapter.

One authoritative compiler: this server performs NO parsing/code execution of
its own. Diagnostics and metadata delegate to compiler.diagnostics.check and
describe, which delegate to the real typed native compiler. Completion's
*lexical cursor detection* is not a language/semantic parser.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compiler.diagnostics import check, describe  # noqa: E402
from compiler.language import MAX_SOURCE_BYTES  # noqa: E402

MAX_MESSAGE_BYTES = 512 * 1024
MAX_HEADER_BYTES = 4096
MAX_DOCUMENTS = 16
MAX_URI_LENGTH = 2048
TARGETS = {"linux", "user", "kernel"}


class ProtocolError(ValueError):
    pass


def recv_message(stream):
    """Read one bounded Content-Length frame; never attempt to process HTTP."""
    headers = {}
    total = 0
    while True:
        line = stream.readline(MAX_HEADER_BYTES + 1)
        if not line:
            if not headers:
                return None
            raise ProtocolError("truncated LSP header")
        total += len(line)
        if total > MAX_HEADER_BYTES or not line.endswith(b"\n"):
            raise ProtocolError("LSP headers exceed 4096 bytes")
        if line in (b"\r\n", b"\n"):
            break
        key, sep, value = line.partition(b":")
        if not sep:
            raise ProtocolError("malformed LSP header")
        name = key.strip().lower()
        if name in headers:
            raise ProtocolError("duplicate LSP header")
        headers[name] = value.strip()
    raw_length = headers.get(b"content-length")
    if not raw_length or not re.fullmatch(rb"[0-9]{1,7}", raw_length):
        raise ProtocolError("missing/invalid Content-Length")
    length = int(raw_length)
    if not 0 < length <= MAX_MESSAGE_BYTES:
        raise ProtocolError("oversize/empty LSP request")
    body = stream.read(length)
    if len(body) != length:
        raise ProtocolError("truncated LSP body")
    try:
        message = json.loads(body.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise ProtocolError("invalid UTF-8 JSON LSP body") from exc
    if not isinstance(message, dict):
        raise ProtocolError("LSP body must be an object")
    return message


def send_message(stream, message):
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    stream.flush()


def utf16_index(text: str, character: int) -> int:
    """Convert LSP UTF-16 column to Python Unicode index, never splitting emoji."""
    if not isinstance(character, int) or character < 0:
        return 0
    length = 0
    for i, char in enumerate(text):
        units = 2 if ord(char) > 0xFFFF else 1
        if length + units > character:
            return i
        length += units
    return len(text)


def utf16_column(text: str, index: int) -> int:
    return len(text[:index].encode("utf-16-le")) // 2


def compiler_diagnostics(source: str, target: str, uri: str) -> list[dict]:
    result = check(source, target=target, file=uri)
    lines = source.splitlines()
    issues = []
    for problem in result["diagnostics"]:
        if problem["line"] is None or problem["column"] is None or not lines:
            row, col = 0, 0
            message = "Document-level error (precise source location unavailable): " + problem["message"]
        else:
            row = min(max(problem["line"] - 1, 0), len(lines) - 1)
            original_col = min(max(problem["column"] - 1, 0), len(lines[row]))
            col = utf16_column(lines[row], original_col)
            message = problem["message"]
        if problem["hint"]:
            message += "\nHint: " + problem["hint"]
        issues.append({
            "range": {"start": {"line": row, "character": col},
                      "end": {"line": row, "character": col + 1}},
            "severity": 1, "source": "htmlk", "code": problem["code"],
            "message": message,
        })
    return issues


class Server:
    def __init__(self, incoming, outgoing):
        self.incoming, self.outgoing = incoming, outgoing
        self.docs: dict[str, tuple[int, str | None]] = {}
        self.target = "linux"
        self.initialized = False
        self.shutdown_requested = False
        self.grammar = describe()["tags"]

    def send(self, msg):
        send_message(self.outgoing, msg)

    def publish(self, uri, version, diagnostics):
        self.send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                   "params": {"uri": uri, "version": version, "diagnostics": diagnostics}})

    def validate_doc(self, uri):
        version, content = self.docs[uri]
        if content is None:
            problems = [{"range": {"start": {"line": 0, "character": 0},
                                    "end": {"line": 0, "character": 1}},
                         "severity": 1, "source": "htmlk", "code": "HK301_BOUNDS",
                         "message": f"Document-level error: source exceeds {MAX_SOURCE_BYTES} UTF-8 bytes"}]
        else:
            problems = compiler_diagnostics(content, self.target, uri)
        self.publish(uri, version, problems)

    def upsert(self, uri, version, content):
        if not isinstance(uri, str) or not uri or len(uri) > MAX_URI_LENGTH:
            raise ValueError("document URI is missing or too long")
        if not isinstance(version, int) or not isinstance(content, str):
            raise ValueError("expected full-text content and integer document version")
        if uri in self.docs and version <= self.docs[uri][0]:
            return  # ignore stale edits, preserving the newest published state
        if uri not in self.docs and len(self.docs) >= MAX_DOCUMENTS:
            raise ValueError("open document limit reached (16)")
        value = content if len(content.encode("utf-8")) <= MAX_SOURCE_BYTES else None
        self.docs[uri] = (version, value)
        self.validate_doc(uri)

    def completion(self, params):
        doc = params.get("textDocument", {})
        uri = doc.get("uri")
        record = self.docs.get(uri)
        if record is None or record[1] is None:
            return []
        text = record[1]
        pos = params.get("position", {})
        row = pos.get("line", -1)
        if not isinstance(row, int) or row < 0:
            return []
        lines = text.splitlines()
        if row >= len(lines):
            return []
        col = pos.get("character", 0)
        line = lines[row]
        cursor = utf16_index(line, col)
        prefix = line[:cursor]
        lt = prefix.rfind("<")
        if lt < 0 or ">" in prefix[lt:]:
            return []
        tail = prefix[lt + 1:]
        if not tail or re.fullmatch(r"[a-z][a-z0-9_-]*", tail):
            start = utf16_column(line, lt + 1)
            replacement = {"start": {"line": row, "character": start},
                           "end": {"line": row, "character": utf16_column(line, cursor)}}
            return [{"label": tag, "kind": 14,
                     "detail": "Parent: " + ", ".join(self.grammar[tag]["parents"]),
                     "documentation": "Attributes: " + ", ".join(self.grammar[tag]["attributes"]),
                     "textEdit": {"range": replacement, "newText": tag}}
                    for tag in sorted(self.grammar) if tag.startswith(tail)]
        # Attribute name completions only; semantic values remain checked by
        # canonical compiler, never accepted by this lexical helper.
        match = re.match(r"^([a-z][a-z0-9_-]*)\s+", tail)
        if not match or tail.count('"') % 2 or tail.count("'") % 2:
            return []
        tag = match.group(1)
        if tag not in self.grammar:
            return []
        suffix = re.search(r"([a-z_-]*)$", tail)
        typed = suffix.group(1) if suffix else ""
        used = set(re.findall(r"([a-z][a-z0-9_-]*)\s*=", tail))
        start = utf16_column(line, cursor - len(typed))
        edit = {"start": {"line": row, "character": start},
                "end": {"line": row, "character": utf16_column(line, cursor)}}
        return [{"label": attribute, "kind": 10,
                 "detail": "<" + tag + "> attribute",
                 "textEdit": {"range": edit, "newText": attribute + '=\"\"'}}
                for attribute in self.grammar[tag]["attributes"]
                if attribute.startswith(typed) and attribute not in used]

    def hover(self, params):
        uri = params.get("textDocument", {}).get("uri")
        record = self.docs.get(uri)
        if record is None or record[1] is None:
            return None
        lines = record[1].splitlines()
        pos = params.get("position", {})
        row = pos.get("line", -1)
        if not isinstance(row, int) or not 0 <= row < len(lines):
            return None
        line = lines[row]
        col = utf16_index(line, pos.get("character", 0))
        for m in re.finditer(r"<(/?)([a-z][a-z0-9_-]*)\b", line):
            if m.start(2) <= col <= m.end(2) and m.group(2) in self.grammar:
                tag = m.group(2)
                fields = self.grammar[tag]
                return {"contents": {"kind": "markdown", "value": (
                    f"**HTML Kernel Language `<{tag}>`**  \n"
                    f"Allowed parents: {', '.join(fields['parents'])}  \n"
                    f"Required attributes: {', '.join(fields['required_attributes']) or '(none)'}  \n"
                    f"Allowed attributes: {', '.join(fields['attributes']) or '(none)'}  \n"
                    "Checked by the canonical compiler; not standard DOM HTML.")}}
        return None

    def on_message(self, message):
        method = message.get("method")
        request_id = message.get("id")
        is_request = "id" in message
        params = message.get("params") or {}
        try:
            if method == "initialize":
                opts = params.get("initializationOptions") or {}
                target = opts.get("target", "linux")
                if target not in TARGETS:
                    raise ValueError("initializationOptions.target must be linux/user/kernel")
                self.target = target
                self.initialized = True
                result = {"serverInfo": {"name": "htmlk-lsp", "version": "0.1.0"},
                          "capabilities": {"positionEncoding": "utf-16",
                                           "textDocumentSync": {"openClose": True, "change": 1},
                                           "completionProvider": {"triggerCharacters": ["<", " "]},
                                           "hoverProvider": True,
                                           "executeCommandProvider": {"commands": ["htmlk.describe"]}}}
            elif method == "shutdown":
                self.shutdown_requested = True
                result = None
            elif method == "exit":
                return False
            elif not self.initialized or self.shutdown_requested:
                if is_request:
                    self.send({"jsonrpc": "2.0", "id": request_id,
                               "error": {"code": -32002, "message": "server not initialized or shutting down"}})
                return True
            elif method == "textDocument/didOpen":
                doc = params["textDocument"]
                self.upsert(doc["uri"], doc["version"], doc["text"])
                result = None
            elif method == "textDocument/didChange":
                doc = params["textDocument"]
                changes = params["contentChanges"]
                if len(changes) != 1 or "range" in changes[0]:
                    raise ValueError("only one full-document text change is supported")
                self.upsert(doc["uri"], doc["version"], changes[0]["text"])
                result = None
            elif method == "textDocument/didSave":
                uri = params["textDocument"]["uri"]
                if uri in self.docs:
                    self.validate_doc(uri)
                result = None
            elif method == "textDocument/didClose":
                uri = params["textDocument"]["uri"]
                self.docs.pop(uri, None)
                self.publish(uri, None, [])
                result = None
            elif method == "workspace/didChangeConfiguration":
                settings = params.get("settings", {})
                candidate = settings.get("htmlk", {}).get("target", self.target)
                if candidate not in TARGETS:
                    raise ValueError("htmlk.target must be linux/user/kernel")
                self.target = candidate
                for uri in list(self.docs):
                    self.validate_doc(uri)
                result = None
            elif method == "textDocument/completion":
                result = self.completion(params)
            elif method == "textDocument/hover":
                result = self.hover(params)
            elif method == "workspace/executeCommand":
                if params.get("command") != "htmlk.describe":
                    raise ValueError("only htmlk.describe is supported")
                result = describe()
            elif method in ("initialized", "$/cancelRequest", "$/setTrace"):
                result = None
            else:
                if is_request:
                    self.send({"jsonrpc": "2.0", "id": request_id,
                               "error": {"code": -32601, "message": "method not found"}})
                return True
            if is_request:
                self.send({"jsonrpc": "2.0", "id": request_id, "result": result})
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            if is_request:
                self.send({"jsonrpc": "2.0", "id": request_id,
                           "error": {"code": -32602, "message": str(exc)[:400]}})
            elif method in ("textDocument/didOpen", "textDocument/didChange"):
                # LSP notifications have no response channel. Give the human
                # editor a bounded document-level diagnostic instead of
                # silently dropping a 17th document or unsupported edit.
                document = params.get("textDocument", {})
                uri = document.get("uri")
                if isinstance(uri, str) and 0 < len(uri) <= MAX_URI_LENGTH:
                    version = document.get("version")
                    self.publish(uri, version if isinstance(version, int) else None, [{
                        "range": {"start": {"line": 0, "character": 0},
                                  "end": {"line": 0, "character": 1}},
                        "severity": 1, "source": "htmlk-lsp", "code": "HK900_PROTOCOL",
                        "message": "Document-level editor protocol error: " + str(exc)[:250],
                    }])
        return True

    def serve(self):
        while True:
            try:
                message = recv_message(self.incoming)
            except ProtocolError:
                return 1  # invalid framing: fail closed, never misparse next bytes
            if message is None:
                return 0 if self.shutdown_requested else 1
            if not self.on_message(message):
                return 0 if self.shutdown_requested else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    return Server(sys.stdin.buffer, sys.stdout.buffer).serve()


if __name__ == "__main__":
    raise SystemExit(main())
