import V86 from '../vendor/libv86.mjs';

// Every visible COM1 byte must originate from the actual emulated UART.
// Never display example output as if the guest generated it.
const $ = id => document.getElementById(id);
const ui = Object.fromEntries(
  ['start','stop','fullscreen','state','message','terminal','command','send',
   'command-form','source','source-hash','iso-hash','boot-event','screen_container']
    .map(id => [id, $(id)]));
const buttons = [...document.querySelectorAll('button[data-command]')];
let machine = null;
let serial = '';
let running = false;
let stopped = false;
let sending = false;
let promptReady = false;
let userFinished = false;
let sourceVerified = false;
let metadata = null;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function status(label, message) {
  ui.state.textContent = label;
  ui.message.textContent = message;
}
function allowCommands(value) {
  const available = Boolean(value && running && !stopped && !sending && !userFinished);
  ui.command.disabled = !available;
  ui.send.disabled = !available;
  for (const button of buttons) button.disabled = !available;
}
async function digest(bytes) {
  const result = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(result)].map(b => b.toString(16).padStart(2, '0')).join('');
}
async function fetchBytes(url) {
  const response = await fetch(url, { cache: 'no-store', credentials: 'omit' });
  if (!response.ok) throw Error(url + ': HTTP ' + response.status);
  return response.arrayBuffer();
}
async function loadEvidence() {
  const response = await fetch('../html-kernel-live.json',
                               {cache:'no-store', credentials:'omit'});
  if (!response.ok) throw Error('빌드 명세를 받지 못했어 (' + response.status + ')');
  const manifest = await response.json();
  if (manifest.kind !== 'html-kernel-os-native-boot' ||
      manifest.image !== 'html-kernel-live.iso' ||
      manifest.user_source !== 'examples/user-programs/html-u64-report.html' ||
      !/^[0-9a-f]{64}$/.test(manifest.image_sha256) ||
      !/^[0-9a-f]{64}$/.test(manifest.user_source_sha256) ||
      manifest.user_timer !== false) {
    throw Error('예상하지 못한 빌드 명세. 실제 부팅을 중단했어.');
  }
  const bytes = await fetchBytes('../examples/user-programs/html-u64-report.html');
  if (await digest(bytes) !== manifest.user_source_sha256)
    throw Error('HTML 소스 해시 불일치: 부팅 소스 증거가 일치하지 않아.');
  ui.source.textContent = new TextDecoder('utf-8', {fatal:true}).decode(bytes);
  ui['source-hash'].textContent = 'HTML SHA-256: ' + manifest.user_source_sha256;
  sourceVerified = true;
  metadata = manifest;
  return manifest;
}

const vga = Array.from({length:50}, () => Array(120).fill(' '));
let vgaReported = new Set();
let vgaFlush = null;
function recordVga(cell) {
  if (!Array.isArray(cell) || cell.length < 3) return;
  const [row, col, char] = cell;
  if (!Number.isInteger(row) || !Number.isInteger(col) ||
      row < 0 || row >= 50 || col < 0 || col >= 120) return;
  vga[row][col] = Number.isInteger(char) && char >= 32 && char < 127 ?
    String.fromCharCode(char) : ' ';
  if (vgaFlush !== null) return;
  vgaFlush = setTimeout(() => {
    vgaFlush = null;
    for (const line of vga.map(r => r.join('').trim()).filter(Boolean)) {
      if ((line.startsWith('SeaBIOS') || line.startsWith('Booting from')) &&
          !vgaReported.has(line)) {
        vgaReported.add(line);
        ui['boot-event'].textContent = 'VGA: ' + line.slice(0,100);
      }
    }
  }, 120);
}

function onSerial(byte) {
  if (!Number.isInteger(byte) || byte < 0 || byte > 255) return;
  if (serial.length >= 60000) {
    allowCommands(false);
    status('OVERFLOW', 'COM1 로그 상한 초과. 더 이상 결과를 검증하지 않아.');
    return;
  }
  serial += String.fromCharCode(byte);
  ui.terminal.textContent = serial;
  ui.terminal.scrollTop = ui.terminal.scrollHeight;
  if (serial.endsWith('M5_PROMPT> ')) {
    promptReady = true;
    if (!sending) {
      allowCommands(true);
      status('GUEST READY', '실제 커널 COM1 프롬프트를 받았어. 명령을 실행할 수 있어.');
    }
  }
  if (serial.includes('M5_C_USER_FRAMES_RECLAIMED\n') &&
      serial.includes('M5_C_RING3_EXIT_OK\n') &&
      serial.includes('M5_RUN_EXIT_CODE=7\n') &&
      ui.state.textContent !== 'RING3 EXECUTED') {
    status('RING3 EXECUTED', '실제 CPU가 HTML 사용자 프로그램을 실행하고, 종료 코드 7과 메모리 회수 기록을 보냈어.');
  }
  if (serial.endsWith('Native code, not a browser.\n')) {
    userFinished = true;
    allowCommands(false);
    status('GUEST EXIT', '네이티브 커널의 마지막 HTML 출력까지 실제 COM1으로 수신했어.');
  }
}

async function start() {
  if (machine) { window.location.reload(); return; }
  ui.start.disabled = true;
  status('VERIFYING', '배포된 ISO와 HTML 소스의 SHA-256을 검사하고 있어…');
  try {
    if (!sourceVerified) await loadEvidence();
    const data = await fetchBytes('../html-kernel-live.iso');
    if (data.byteLength !== metadata.image_bytes ||
        await digest(data) !== metadata.image_sha256) {
      throw Error('ISO SHA-256 또는 길이가 배포 명세와 일치하지 않아.');
    }
    ui['iso-hash'].textContent = 'ISO SHA-256: ' + metadata.image_sha256;
    serial = '';
    ui.terminal.textContent = '';
    promptReady = false;
    stopped = false;
    running = false;
    userFinished = false;
    status('LOADING BIOS', '검증한 ISO를 실제 64비트 가상머신에 넣는 중…');
    machine = new V86({
      cpu_type:'x86_64', graphics_adapter:'bochs_vga',
      wasm_path:'../vendor/v86.wasm',
      bios:{url:'../vendor/seabios.bin'}, vga_bios:{url:'../vendor/vgabios.bin'},
      cdrom:{buffer:data},
      screen_container:ui.screen_container, memory_size:128*1024*1024,
      vram_size:4*1024*1024, acpi:true,
      net_device:{type:'none'}, audio_device:'none', autostart:true
    });
    machine.add_listener('screen-put-char', recordVga);
    machine.add_listener('serial0-output-byte', onSerial);
    machine.add_listener('emulator-ready', () => {
      if (!stopped) status('BIOS READY', '실제 SeaBIOS·Limine 부팅 단계. COM1 출력을 기다리는 중…');
    });
    machine.add_listener('emulator-started', () => {
      running = true;
      ui.stop.disabled = false;
      if (!promptReady) status('CPU RUNNING', '실제 x86-64 가상 CPU가 실행 중. BIOS→커널 부팅을 기다리는 중…');
    });
    machine.add_listener('emulator-stopped', () => {
      running = false;
      allowCommands(false);
      if (!stopped) status('CPU STOPPED', '가상 CPU가 멈췄어. 현재 COM1 기록은 실제 수신한 내용이야.');
    });
  } catch (error) {
    status('BOOT BLOCKED', String(error?.message || error));
    ui.start.disabled = false;
    if (machine) { try { await machine.stop(); } catch {} }
    machine = null;
  }
}
async function sendCommand(value) {
  const command = value.trim();
  if (!machine || stopped || !running || !promptReady || sending || userFinished) return;
  // Keep input to one printable ASCII guest command; never inject controls.
  if (!command || command.length > 88 || !/^[\x20-\x7e]+$/.test(command)) {
    ui.message.textContent = '명령은 1~88자 ASCII 한 줄로 입력해 줘.';
    return;
  }
  sending = true;
  promptReady = false;
  allowCommands(false);
  ui.command.value = '';
  status('UART INPUT', '명령을 실제 가상 COM1 RX에 전송 중: ' + command);
  try {
    // The emulated 16550 receive FIFO is small. Pacing prevents dropped chars.
    for (const char of command + '\r') {
      if (!machine || stopped) break;
      machine.serial0_send(char);
      await sleep(10);
    }
  } catch (error) {
    status('UART ERROR', String(error?.message || error));
  } finally {
    sending = false;
    allowCommands(promptReady);
    if (promptReady && !userFinished && ui.state.textContent === 'UART INPUT') {
      status('GUEST READY', '게스트가 응답을 마치고 다음 명령을 기다리고 있어.');
    }
  }
}
ui.start.addEventListener('click', () => void start());
ui.stop.addEventListener('click', async () => {
  if (!machine || stopped) return;
  stopped = true;
  allowCommands(false);
  ui.stop.disabled = true;
  try { await machine.stop(); } catch (error) {
    status('STOP ERROR', String(error?.message || error));
  }
  ui.start.disabled = false;
  ui.start.textContent = '새로 부팅';
  status('STOPPED', '가상 CPU를 중단했어. 수신한 COM1 기록은 그대로 남아 있어.');
});
ui.fullscreen.addEventListener('click', () => {
  if (document.fullscreenElement === ui.screen_container) {
    void document.exitFullscreen();
  } else {
    void ui.screen_container.requestFullscreen().catch(error =>
      status('DISPLAY ERROR', String(error?.message || error)));
  }
});
ui['command-form'].addEventListener('submit', event => {
  event.preventDefault();
  void sendCommand(ui.command.value);
});
for (const button of buttons) {
  button.addEventListener('click', () => void sendCommand(button.dataset.command));
}
void loadEvidence().catch(error => {
  ui.source.textContent = '소스 무결성 검사를 통과하지 못했어.';
  status('SOURCE ERROR', String(error?.message || error));
});
