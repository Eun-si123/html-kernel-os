import test from 'node:test';
import assert from 'node:assert/strict';
import { SOURCE_LIMIT, EXPORT_FILENAME, TEMPLATE,
         BUILD_COMMAND, sourceBytes, sourceState } from '../site/live/editor.mjs';

test('browser source editor uses the actual static ROMFS byte budget', () => {
  assert.equal(SOURCE_LIMIT, 4096);
  assert.deepEqual(sourceState(''), { bytes: 0, valid: false });
  assert.deepEqual(sourceState('A'.repeat(4096)), { bytes: 4096, valid: true });
  assert.deepEqual(sourceState('A'.repeat(4097)), { bytes: 4097, valid: false });
  assert.deepEqual(sourceState('한'.repeat(1365)), {bytes: 4095, valid: true});
  assert.deepEqual(sourceState('한'.repeat(1366)), {bytes: 4098, valid: false});
  assert.deepEqual(sourceState('😊'.repeat(1024)), {bytes: 4096, valid: true});
  assert.deepEqual(sourceState('😊'.repeat(1025)), {bytes: 4100, valid: false});
});

test('native editor fixture is valid bounded HTMLK user source', () => {
  assert.equal(sourceState(TEMPLATE).valid, true);
  assert.ok(TEMPLATE.includes('<program>') && TEMPLATE.includes('<main>'));
  assert.ok(TEMPLATE.includes('<print value="value"/>'));
  assert.ok(TEMPLATE.includes('<halt/>'));
  assert.equal(Buffer.from(sourceBytes(TEMPLATE)).toString('utf8'), TEMPLATE);
  assert.equal(EXPORT_FILENAME, 'htmlk-program.html');
  assert.equal(BUILD_COMMAND,
    'python3 scripts/build_live_site.py --source htmlk-program.html --out-dir build/my-html-os');
});

test('changed source changes exported bytes with no fake program output', () => {
  const changed = TEMPLATE.replace('value="2026"', 'value="2031"');
  assert.notEqual(changed, TEMPLATE);
  assert.notDeepEqual(sourceBytes(changed), sourceBytes(TEMPLATE));
  assert.ok(sourceState(changed).valid);
  assert.ok(!BUILD_COMMAND.includes('eval('));
});
