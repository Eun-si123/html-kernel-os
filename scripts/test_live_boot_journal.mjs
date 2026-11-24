import test from 'node:test';
import assert from 'node:assert/strict';
import {BootTrace, JOURNAL_LIMIT, BOOT_VGA_TEXT,
        VGA_COLS, VGA_ROWS} from '../site/live/journal.mjs';

test('only actual completed CPU COM1 lines are recorded', () => {
  let now = 100;
  const trace = new BootTrace(() => now);
  trace.host('emulator-ready');
  now = 300;
  for (const byte of Buffer.from('M5_PROMPT> \r\n', 'ascii')) trace.uartByte(byte);
  assert.deepEqual(trace.events.map(e => e.kind), ['VM HOST', 'CPU COM1']);
  assert.equal(trace.events[1].text, 'M5_PROMPT>');
  assert.equal(trace.events[1].ms, 200);
  assert.ok(trace.formatted().includes('[+  0.200s] [CPU COM1] M5_PROMPT>'));
});

test('real VGA SeaBIOS/Booting-from cell changes become log entries', () => {
  let time = 0;
  const trace = new BootTrace(() => time);
  const send = (row, text) => {
    for (let i=0;i<text.length;i++) trace.vgaCell([row,i,text.charCodeAt(i)]);
  };
  send(0, 'SeaBIOS (version test-firmware)');
  time=13;
  send(1, 'Booting from CD-ROM...');
  trace.captureFrame();
  assert.ok(trace.events.some(e => e.kind==='BIOS VGA' &&
    e.text === 'SeaBIOS (version test-firmware)'));
  assert.ok(trace.events.some(e => e.kind==='BIOS VGA' &&
    e.text === 'Booting from CD-ROM...'));
  const n=trace.events.length;
  trace.captureFrame();
  assert.equal(trace.events.length,n,'duplicate unchanged VGA states must not inflate log');
  assert.ok(BOOT_VGA_TEXT.test('Limine bootloader'));
});

test('firmware row partial lines are replaced only by actually observed full text', () => {
  let clock = 0;
  const trace = new BootTrace(() => clock);
  const draw = (s) => { for (let i=0;i<s.length;i++) trace.vgaCell([0,i,s.charCodeAt(i)]); };
  draw('SeaBIOS (version rel-');
  trace.captureFrame();
  assert.equal(trace.events.length,1);
  clock=22;
  draw('SeaBIOS (version rel-1.16.2)');
  trace.captureFrame();
  assert.equal(trace.events.length,1,'partial and full line are the same BIOS message');
  assert.equal(trace.events[0].text,'SeaBIOS (version rel-1.16.2)');
  assert.equal(trace.events[0].ms,22);
});

test('out of range VGA cells and invalid UART bytes are rejected' , () => {
  const trace = new BootTrace(() => 0);
  for (const bad of ([VGA_ROWS,0,65], [0,VGA_COLS,65], [-1,1,65],
                     [0,-1,65], ['a',0,65], null, [])) trace.vgaCell(bad);
  for (const bad of (-1,256,1.5,'hello')) trace.uartByte(bad);
  assert.equal(trace.events.length,0);
  trace.vgaCell([0,0,'unprintable']);
  trace.captureFrame();
  assert.equal(trace.events.length,0);
});

test('bounded journal caps captured history; raw CPU lines do not execute HTML', () => {
  const trace = new BootTrace(() => 0);
  for (let i=0;i<JOURNAL_LIMIT+10;i++) trace.add('CPU COM1','<script>never execute</script>');
  assert.equal(trace.events.length,JOURNAL_LIMIT);
  assert.equal(trace.dropped,10);
  assert.equal(trace.formatted(1).split('\n').length,1);
  assert.ok(trace.formatted(1).includes('<script>never execute</script>'));
  trace.reset();
  assert.equal(trace.events.length,0);
  assert.equal(trace.dropped,0);
});
