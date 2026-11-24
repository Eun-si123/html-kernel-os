/* M5 Web: real BIOS/VGA and kernel COM1 capture, with clearly labeled replay.
 * Neither host timestamps nor replay change guest CPU speed.
 * No invented guest lines, no HTML evaluation, no external network. */
export const JOURNAL_LIMIT = 240;
export const VGA_ROWS = 50;
export const VGA_COLS = 120;
export const BOOT_VGA_TEXT = /SeaBIOS|Booting from|Limine|iPXE|Boot failed|Booting CD|CD-ROM/i;

export class BootTrace {
  constructor(now = () => performance.now()) {
    this.now = now;
    this.reset();
  }
  reset() {
    this.started = this.now();
    this.events = [];
    this.revision = 0;
    this.seenVgaRow = new Map();
    this.screen = Array.from({length: VGA_ROWS}, () => Array(VGA_COLS).fill(' '));
    this.lastRow = null;
    this.lastFrame = new Set();
    this.serialLine = '';
    this.dropped = 0;
  }
  add(kind, text) {
    if (!text) return;
    if (this.events.length >= JOURNAL_LIMIT) {
      this.dropped++;
      return;
    }
    this.revision++;
    this.events.push({
      ms: Math.max(0, Math.round(this.now() - this.started)),
      kind, text: String(text).slice(0, 240),
    });
  }
  host(text) { this.add('VM HOST', text); }
  uartByte(byte) {
    if (!Number.isInteger(byte) || byte < 0 || byte > 255) return;
    if (byte === 10) {
      const line = this.serialLine.trim();
      if (line) this.add('CPU COM1', line);
      this.serialLine = '';
    } else if (byte === 13) {
      // Guest emits CR/LF; a single actual completed line is enough.
    } else if (this.serialLine.length < 240) {
      this.serialLine += byte >= 32 && byte < 127 ?
        String.fromCharCode(byte) : '\\x' + byte.toString(16).padStart(2, '0');
    }
  }
  vgaCell(cell) {
    if (!Array.isArray(cell) || cell.length < 3) return;
    const [row, col, char] = cell;
    if (!Number.isInteger(row) || !Number.isInteger(col) ||
        row < 0 || row >= VGA_ROWS || col < 0 || col >= VGA_COLS) return;
    if (this.lastRow !== null && this.lastRow !== row) this.captureRow(this.lastRow);
    this.lastRow = row;
    this.screen[row][col] = Number.isInteger(char) && char >= 32 && char < 127 ?
      String.fromCharCode(char) : ' ';
  }
  captureRow(row) {
    const line = this.screen[row].join('').trim().slice(0, 200);
    if (!BOOT_VGA_TEXT.test(line) || this.lastFrame.has(line)) return;
    const previous = this.seenVgaRow.get(row);
    // VGA may paint the same firmware line in several bursts. Replace the
    // short partial text with the completed actual line instead of claiming
    // two distinct BIOS messages; never add bytes not seen from VGA events.
    if (previous && line.startsWith(previous.text) &&
        previous.index < this.events.length) {
      const event = this.events[previous.index];
      event.text = line;
      event.ms = Math.max(0, Math.round(this.now() - this.started));
      this.seenVgaRow.set(row, { text: line, index: previous.index });
      this.lastFrame.add(line);
      this.revision++;
      return;
    }
    if (this.events.length >= JOURNAL_LIMIT) {
      this.dropped++;
      return;
    }
    this.add('BIOS VGA', line);
    this.lastFrame.add(line);
    this.seenVgaRow.set(row, { text: line, index: this.events.length - 1 });
  }
  captureFrame() {
    for (let row = 0; row < VGA_ROWS; row++) this.captureRow(row);
  }
  formatted(maxEntries = this.events.length) {
    return this.events.slice(0, maxEntries).map((item) => {
      const seconds = (item.ms / 1000).toFixed(3).padStart(7, ' ');
      return `[+${seconds}s] [${item.kind}] ${item.text}`;
    }).join('\n');
  }
}

export function createBootJournal(doc = document) {
  const output = doc.getElementById('journal-output');
  const position = doc.getElementById('journal-position');
  const play = doc.getElementById('journal-play');
  const pause = doc.getElementById('journal-pause');
  const step = doc.getElementById('journal-step');
  const speed = doc.getElementById('journal-speed');
  const status = doc.getElementById('journal-status');
  const trace = new BootTrace();
  let cursor = 0, timer = null, playing = false, following = true;
  function cancel() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    playing = false;
  }
  function display() {
    if (!output) return;
    const previousScroll = output.scrollTop;
    output.textContent = trace.formatted(cursor) ||
      '실제 가상 PC의 첫 BIOS/VGA·COM1 이벤트를 기다리고 있어.';
    position.max = String(trace.events.length);
    position.value = String(cursor);
    const label = following ? '실시간' : playing ? '기록 재생 중' : '기록 일시 정지';
    status.textContent = `${label} · ${cursor}/${trace.events.length}건 · 브라우저 수신 시각 기준` +
      (trace.dropped ? ` · 기록 상한 도달 (${trace.dropped}건 제외)` : '');
    output.scrollTop = following || playing ? output.scrollHeight : previousScroll;
    pause.disabled = !playing;
    step.disabled = !trace.events.length;
  }
  function updated() {
    if (following && !playing) cursor = trace.events.length;
    display();
  }
  function reset() {
    cancel();
    trace.reset();
    cursor = 0;
    following = true;
    display();
  }
  function next() {
    if (!playing) return;
    if (cursor >= trace.events.length) {
      cancel();
      following = false;
      display();
      return;
    }
    const prev = cursor ? trace.events[cursor - 1].ms : 0;
    const curr = trace.events[cursor].ms;
    cursor++;
    display();
    const rate = Number(speed.value) || 1;
    const delay = Math.max(80, Math.min(1800, (curr - prev) / rate));
    timer = setTimeout(next, delay);
  }
  if (output && position && play && pause && step && speed && status) {
    play.addEventListener('click', () => {
      cancel();
      cursor = 0;  // button explicitly says "replay from the beginning"
      following = false;
      playing = true;
      next();
    });
    pause.addEventListener('click', () => {
      cancel();
      following = false;
      display();
    });
    step.addEventListener('click', () => {
      cancel();
      following = false;
      cursor = Math.min(cursor + 1, trace.events.length);
      display();
    });
    position.addEventListener('input', () => {
      cancel();
      following = false;
      cursor = Math.min(Math.max(0, Number(position.value) || 0), trace.events.length);
      display();
    });
    display();
  }
  return {
    trace, reset,
    host(text) { trace.host(text); updated(); },
    vgaCell(cell) { const rev = trace.revision; trace.vgaCell(cell);
      if (trace.revision !== rev) updated(); },
    captureFrame() { const rev = trace.revision; trace.captureFrame();
      if (trace.revision !== rev) updated(); },
    uartByte(byte) { const prev = trace.events.length; trace.uartByte(byte);
      if (trace.events.length !== prev) updated(); },
  };
}
