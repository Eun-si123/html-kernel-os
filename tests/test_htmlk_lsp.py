"""LSP 3.x true stdio protocol tests, not an in-process mock of the server."""
from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from compiler.diagnostics import check, describe
from scripts.htmlk_lsp import recv_message, send_message, utf16_column, utf16_index

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT/'scripts/htmlk_lsp.py'
GOOD = (ROOT/'examples/human-agent-program.html').read_text(encoding='utf-8')
URI = 'file:///demo/my-hello.html'


def request(method, params=None, identifier=None):
    data = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        data['params'] = params
    if identifier is not None:
        data['id'] = identifier
    return data


def run_server(messages, *, timeout=9):
    input_stream = io.BytesIO()
    for message in messages:
        send_message(input_stream, message)
    done = subprocess.run([sys.executable, str(SERVER)], input=input_stream.getvalue(),
                          capture_output=True, timeout=timeout, cwd=ROOT)
    frames, output = [], io.BytesIO(done.stdout)
    while True:
        frame = recv_message(output)
        if frame is None:
            break
        frames.append(frame)
    return done, frames


class HtmlkLspTests(unittest.TestCase):
    def test_initialize_open_valid_completion_hover_change_diagnostics_and_shutdown(self):
        bad = GOOD.replace('<print value="4294967296"/>', '<prnit value="4294967296"/>')
        assert bad != GOOD
        messages = [
            request('initialize', {'initializationOptions': {'target': 'user'}}, 1),
            request('initialized'),
            request('textDocument/didOpen', {'textDocument': {
                'uri': URI, 'version': 1, 'languageId': 'htmlk', 'text': GOOD}}),
            request('workspace/executeCommand', {'command': 'htmlk.describe'}, 2),
            request('textDocument/didChange', {'textDocument': {'uri': URI, 'version': 2},
                                             'contentChanges': [{'text': bad}]}),
            request('textDocument/didChange', {'textDocument': {'uri': URI, 'version': 1},
                                             'contentChanges': [{'text': GOOD}]}),
            request('textDocument/didChange', {'textDocument': {'uri': URI, 'version': 3},
                                             'contentChanges': [{'text': GOOD}]}),
            request('textDocument/didClose', {'textDocument': {'uri': URI}}),
            request('shutdown', identifier=3),
            request('exit'),
        ]
        done, frames = run_server(messages)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, b'')
        self.assertEqual([f['id'] for f in frames if 'id' in f], [1, 2, 3])
        init = frames[0]['result']
        self.assertEqual(init['capabilities']['positionEncoding'], 'utf-16')
        self.assertEqual(init['capabilities']['textDocumentSync']['change'], 1)
        self.assertEqual(frames[2]['result'], describe())
        published = [f['params'] for f in frames if f.get('method') == 'textDocument/publishDiagnostics']
        self.assertEqual([p['version'] for p in published], [1, 2, 3, None])
        self.assertEqual(published[0]['diagnostics'], [])
        error, = published[1]['diagnostics']
        self.assertEqual(error['code'], 'HK101_TAG')
        self.assertIn('Did you mean <print>?', error['message'])
        self.assertEqual(error['range']['start']['line'], bad.splitlines().index(
            next(line for line in bad.splitlines() if '<prnit ' in line)))
        self.assertEqual(published[2]['diagnostics'], [])
        self.assertEqual(published[3]['diagnostics'], [])
        self.assertIsNone(frames[-1]['result'])

    def test_real_completion_is_derived_from_canonical_tags_and_attributes(self):
        content = '<program>\n  <main>\n    <pr\n    <let n\n  </main>\n</program>'
        done, frames = run_server([
            request('initialize', identifier=1),
            request('textDocument/didOpen', {'textDocument': {
                'uri': URI, 'version': 1, 'text': content}}),
            request('textDocument/completion', {'textDocument': {'uri': URI},
                                                'position': {'line': 2, 'character': 7}}, 2),
            request('textDocument/completion', {'textDocument': {'uri': URI},
                                                'position': {'line': 3, 'character': 10}}, 3),
            request('shutdown', identifier=4),
            request('exit')])
        self.assertEqual(done.returncode, 0, done.stderr)
        tags = next(f['result'] for f in frames if f.get('id') == 2)
        self.assertEqual([f['label'] for f in tags], ['print', 'program'])
        self.assertEqual(tags[0]['textEdit']['newText'], 'print')
        self.assertEqual(tags[0]['textEdit']['range']['start']['character'], 5)
        attributes = next(f['result'] for f in frames if f.get('id') == 3)
        self.assertEqual([a['label'] for a in attributes], ['name'])
        self.assertEqual(attributes[0]['textEdit']['newText'], 'name=""')
        self.assertEqual(set(a['label'] for a in attributes), {'name'})

    def test_root_alias_hover_diagnostics_and_target_switch_are_canonical(self):
        source = '<program><main><print value="1"/><halt/></main></program>'
        done, frames = run_server([
            request('initialize', {'initializationOptions': {'target': 'user'}}, 1),
            request('textDocument/didOpen', {'textDocument': {'uri': URI, 'version': 1, 'text': source}}),
            request('textDocument/hover', {'textDocument': {'uri': URI},
                                           'position': {'line': 0, 'character': 3}}, 2),
            request('workspace/didChangeConfiguration', {'settings': {'htmlk': {'target': 'kernel'}}}),
            request('textDocument/didClose', {'textDocument': {'uri': URI}}),
            request('shutdown', identifier=3), request('exit')])
        self.assertEqual(done.returncode, 0, done.stderr)
        hover = next(f['result'] for f in frames if f.get('id') == 2)
        self.assertIn('<program>', hover['contents']['value'])
        publications = [f['params'] for f in frames if f.get('method')=='textDocument/publishDiagnostics']
        self.assertEqual([len(p['diagnostics']) for p in publications], [0, 1, 0])
        self.assertIn('for Linux or Ring3 user apps', publications[1]['diagnostics'][0]['message'])

    def test_utf16_column_is_correct_after_astral_unicode(self):
        text = '<program><main><!-- 😀 --><prnit/><halt/></main></program>'
        problem, = check(text, target='linux', file=URI)['diagnostics']
        self.assertGreater(problem['column'], 1)
        unicode_offset = problem['column'] - 1
        expected_utf16 = utf16_column(text, unicode_offset)
        self.assertEqual(expected_utf16, unicode_offset + 1)
        self.assertEqual(utf16_index(text, expected_utf16), unicode_offset)
        done, frames = run_server([
            request('initialize', identifier=1),
            request('textDocument/didOpen', {'textDocument': {'uri': URI, 'version': 1, 'text': text}}),
            request('shutdown', identifier=2), request('exit')])
        self.assertEqual(done.returncode, 0)
        got, = next(f['params']['diagnostics'] for f in frames
                    if f.get('method') == 'textDocument/publishDiagnostics')
        self.assertEqual(got['range']['start']['character'], expected_utf16)

    def test_document_wide_errors_are_labeled_not_falsely_positioned(self):
        source = '<program><main><halt/></main></program>'
        done, frames = run_server([
            request('initialize', {'initializationOptions': {'target': 'user'}}, 1),
            request('textDocument/didOpen', {'textDocument': {'uri': URI, 'version': 1, 'text': source}}),
            request('shutdown', identifier=2), request('exit')])
        self.assertEqual(done.returncode, 0)
        got, = next(f['params']['diagnostics'] for f in frames
                    if f.get('method') == 'textDocument/publishDiagnostics')
        self.assertIn('precise source location unavailable', got['message'])
        self.assertEqual(got['range']['start'], {'line': 0, 'character': 0})

    def test_bounded_source_is_denied_before_retention_and_no_host_execution(self):
        text = 'a' * 131073
        done, frames = run_server([
            request('initialize', identifier=1),
            request('textDocument/didOpen', {'textDocument': {'uri': URI, 'version': 1, 'text': text}}),
            request('shutdown', identifier=2), request('exit')])
        self.assertEqual(done.returncode, 0, done.stderr)
        got, = next(f['params']['diagnostics'] for f in frames
                    if f.get('method')=='textDocument/publishDiagnostics')
        self.assertEqual(got['code'], 'HK301_BOUNDS')
        self.assertIn('131072 UTF-8 bytes', got['message'])

    def test_attribute_completion_refuses_quoted_values_and_duplicate_names(self):
        content = '<program><main><let name="Hello world" ty'
        done, frames = run_server([
            request('initialize', identifier=1),
            request('textDocument/didOpen', {'textDocument': {
                'uri': URI, 'version': 1, 'text': content}}),
            request('textDocument/completion', {'textDocument': {'uri': URI},
                'position': {'line': 0, 'character': len(content)}}, 2),
            request('shutdown', identifier=3), request('exit')])
        self.assertEqual(done.returncode, 0)
        result = next(f['result'] for f in frames if f.get('id') == 2)
        self.assertEqual([f['label'] for f in result], ['type'])
        content2 = '<program><main><let name="Hi ty'
        done, frames = run_server([
            request('initialize', identifier=1),
            request('textDocument/didOpen', {'textDocument': {
                'uri': URI, 'version': 1, 'text': content2}}),
            request('textDocument/completion', {'textDocument': {'uri': URI},
                'position': {'line': 0, 'character': len(content2)}}, 2),
            request('shutdown', identifier=3), request('exit')])
        self.assertEqual(done.returncode, 0)
        self.assertEqual(next(f['result'] for f in frames if f.get('id') == 2), [])

    def test_invalid_initialize_target_is_rejected_before_compilation(self):
        done, frames = run_server([
            request('initialize', {'initializationOptions': {'target': 'administrative'}}, 1),
            request('exit')])
        self.assertEqual(done.returncode, 1)
        self.assertEqual(frames[0]['error']['code'], -32602)

    def test_full_lsp_content_type_header_and_live_parser_roundtrip(self):
        body = json.dumps(request('initialize', identifier=1)).encode('utf-8')
        payload = (b'Content-Length: ' + str(len(body)).encode() + b'\r\n'
                   b'Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n' + body)
        payload += b'Content-Length: 48\r\n\r\n'
        # The malformed final message must not cause fabricated output or
        # bypass the length bound; the first valid initialization is preserved.
        done = subprocess.run([sys.executable, str(SERVER)], input=payload,
                              capture_output=True, timeout=6, cwd=ROOT)
        self.assertEqual(done.returncode, 1)
        responses = io.BytesIO(done.stdout)
        self.assertEqual(recv_message(responses)['id'], 1)
        self.assertIsNone(recv_message(responses))

    def test_more_than_sixteen_docs_returns_explicit_bounded_diagnostic(self):
        msgs = [request('initialize', identifier=1)]
        for i in range(17):
            msgs.append(request('textDocument/didOpen', {'textDocument': {
                'uri': f'file:///demo/file-{i}.html', 'version': 1,
                'text': '<program><main><print>hello</print><halt/></main></program>'}}))
        msgs.extend([request('shutdown', identifier=2), request('exit')])
        done, frames = run_server(msgs)
        self.assertEqual(done.returncode, 0)
        published = [f['params'] for f in frames if f.get('method') == 'textDocument/publishDiagnostics']
        self.assertEqual(len(published), 17)
        last, = published[-1]['diagnostics']
        self.assertEqual(last['code'], 'HK900_PROTOCOL')
        self.assertIn('document limit reached', last['message'])
        self.assertEqual(last['source'], 'htmlk-lsp')

    def test_incremental_edit_mismatch_reports_error_but_valid_sync_recovers(self):
        msgs = [request('initialize', identifier=1),
                request('textDocument/didOpen', {'textDocument': {
                    'uri': URI, 'version': 1, 'text': GOOD}}),
                request('textDocument/didChange', {'textDocument': {
                    'uri': URI, 'version': 2},
                    'contentChanges': [{'range': {'start': {}}, 'text': 'no'}]}),
                request('textDocument/didChange', {'textDocument': {
                    'uri': URI, 'version': 3},
                    'contentChanges': [{'text': GOOD}]}),
                request('shutdown', identifier=2), request('exit')]
        done, frames = run_server(msgs)
        self.assertEqual(done.returncode, 0)
        publications = [f['params'] for f in frames if f.get('method')=='textDocument/publishDiagnostics']
        self.assertEqual([p['version'] for p in publications], [1, 2, 3])
        self.assertEqual(publications[0]['diagnostics'], [])
        self.assertEqual(publications[1]['diagnostics'][0]['code'], 'HK900_PROTOCOL')
        self.assertEqual(publications[2]['diagnostics'], [])

    def test_invalid_protocol_bodies_or_framing_fail_closed(self):
        for raw in (b'Content-Length: 0\r\n\r\n',
                    b'Content-Length: 524289\r\n\r\n',
                    b'Content-Length: 2\r\n\r\n\xff\xfe',
                    b'Content-Length: 12\r\n\r\nshort'):
            with self.subTest(raw=raw[:35]):
                done = subprocess.run([sys.executable, str(SERVER)], input=raw,
                                      capture_output=True, timeout=5, cwd=ROOT)
                self.assertEqual(done.returncode, 1)
                self.assertFalse(done.stdout)

    def test_exit_requires_shutdown_and_unknown_methods_have_lsp_errors(self):
        done, frames = run_server([
            request('initialize', identifier=1),
            request('my/unsupportedMethod', identifier=2),
            request('textDocument/didChange', {'textDocument': {'uri': URI, 'version': 1},
                                               'contentChanges': [{'range': {}, 'text': ''}]}, 3),
            request('exit')])
        self.assertEqual(done.returncode, 1)
        self.assertEqual(frames[1]['error']['code'], -32601)
        self.assertEqual(frames[2]['error']['code'], -32602)


if __name__=='__main__':
    unittest.main()
