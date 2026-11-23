import V86 from './vendor/libv86.mjs';

(() => {
  'use strict';
  const start = document.getElementById('boot-start');
  const stop = document.getElementById('boot-stop');
  const replay = document.getElementById('boot-replay');
  const replaySpeed = document.getElementById('replay-speed');
  const fullscreen = document.getElementById('display-fullscreen');
  const status = document.getElementById('boot-status');
  const output = document.getElementById('boot-output');
  const selection = document.getElementById('kernel-demo');
  const download = document.getElementById('iso-download');
  const screen = document.getElementById('screen_container');
  const paceChoice = document.getElementById('vm-pace');
  const pauseButton = document.getElementById('vm-pause');
  const events = document.getElementById('boot-events');
  const sourceView = document.getElementById('boot-source');
  const sourcePath = document.getElementById('boot-source-path');
  const sourceNote = document.getElementById('boot-source-note');
  const liveTag = document.getElementById('live-tag');
  const latestEvent = document.getElementById('boot-latest');
  const demos = Object.freeze({
    video: {
      iso: 'html-kernel-video.iso',
      source: 'framebuffer-kernel.html',
      expected: 'HTML KERNEL ON-SCREEN\nTHE DISPLAY IS DRAWN BY THE BOOTED CPU\n42\nVIDEO PASS\n'
    },
    basic: {
      iso: 'html-kernel.iso',
      source: 'kernel.html',
      expected: 'Hello from HTML Kernel!\nNative code, not a browser.\n'
    },
    math: {
      iso: 'html-kernel-math.iso',
      source: 'math-kernel.html',
      expected: 'Arithmetic in HTML Kernel!\n14\n16\n18\ncondition PASS\n18446744073709551615\n'
    },
    functions: {
      iso: 'html-kernel-functions.iso',
      source: 'functions-kernel.html',
      expected: 'Functions in HTML Kernel!\n13\n17\nfunction PASS\n10\n12\n'
    },
    scoped: {
      iso: 'html-kernel-scoped.iso',
      source: 'scoped-functions-kernel.html',
      expected: 'Scoped functions in HTML Kernel!\n25\n10\nscoped function PASS\n'
    },
    branches: {
      iso: 'html-kernel-else.iso',
      source: 'else-kernel.html',
      expected: 'HTML if/else native!\nelse branch PASS\n8\n17\n222\nnested PASS\nnested PASS\n'
    },
    u32: {
      iso: 'html-kernel-u32.iso',
      source: 'u32-kernel.html',
      expected: 'Native u32 types in HTML Kernel!\n4294967295\n0\n1\n4294967295\n4294967296\ntyped PASS\n'
    },
    signed: {
      iso: 'html-kernel-signed.iso',
      source: 'signed-bits-kernel.html',
      expected: 'Typed signed integers and bitwise kernel!\n-2147483648\n2147483647\n1\n2\n-9223372036854775808\n9223372036854775807\n-1\n18446744073709551615\n43\n0\n4294967295\n1\n3\ntyped signed and loop PASS\n'
    }
  });

  let machine = null;
  let bootStartedAt = 0;
  let serial = '';
  let serialVerified = false;
  let serialMismatch = false;
  let playbackTimer = null;
  let playbackPosition = 0;
  let sourceLines = [];
  let sourceNodes = [];
  let currentDemo = null;
  let lastSourceLine = -1;
  let firstByteSeen = false;
  let replaying = false;
  let userPaused = false;
  let userStopped = false;
  let paceStopPending = false;
  let paceTimer = null;
  let vgaTimer = null;
  const vgaRows = Array.from({ length: 50 }, () => Array(120).fill(' '));
  const vgaSeen = new Set();
  let firstEmulatorStart = false;
  const setStatus = message => { status.textContent = message; };

  function stamp() {
    return (Math.max(0, performance.now() - bootStartedAt) / 1000).toFixed(2) + 's';
  }

  function logEvent(kind, detail) {
    const li = document.createElement('li');
    const time = document.createElement('time');
    time.textContent = stamp();
    const topic = document.createElement('strong');
    topic.textContent = kind;
    const message = document.createElement('span');
    message.textContent = detail;
    li.append(time, topic, message);
    if (events.children.length >= 60) events.firstElementChild.remove();
    events.append(li);
    latestEvent.textContent = kind + ' · ' + detail;
    events.scrollTop = events.scrollHeight;
  }

  function resetVga() {
    vgaSeen.clear();
    for (const row of vgaRows) row.fill(' ');
    if (vgaTimer !== null) clearTimeout(vgaTimer);
    vgaTimer = null;
  }

  function flushVga() {
    vgaTimer = null;
    const lines = vgaRows.map(row => row.join('').trim()).filter(Boolean);
    for (const line of lines) {
      // Actual VGA text-cell writes from SeaBIOS. These are NOT COM1 bytes.
      const complete = (line.startsWith('SeaBIOS') && line.includes(')')) ||
        (line.startsWith('Booting from') && line.includes('...'));
      if (complete && !vgaSeen.has(line)) {
        vgaSeen.add(line);
        logEvent('BIOS VGA', line.slice(0, 110));
      }
    }
  }

  function recordVgaCell(cell) {
    if (!Array.isArray(cell) || cell.length < 3) return;
    const [row, col, ch] = cell;
    if (!Number.isInteger(row) || !Number.isInteger(col) ||
        row < 0 || row >= vgaRows.length || col < 0 || col >= 120) return;
    vgaRows[row][col] = Number.isInteger(ch) && ch >= 32 && ch <= 126 ?
      String.fromCharCode(ch) : ' ';
    if (vgaTimer === null && vgaSeen.size < 12) {
      vgaTimer = setTimeout(flushVga, 90);
    }
  }

  function clearPlayback() {
    if (playbackTimer !== null) clearTimeout(playbackTimer);
    playbackTimer = null;
    replaying = false;
  }

  function clearPaceTimer() {
    if (paceTimer !== null) clearTimeout(paceTimer);
    paceTimer = null;
  }

  function sourceLineForLiteral(text) {
    for (let i = 0; i < sourceLines.length; i++) {
      const literal = sourceLines[i].match(/<print>(.*?)<\/print>/);
      if (literal && literal[1] === text) return i;
    }
    return -1;
  }

  function highlightLiteral(line) {
    const found = sourceLineForLiteral(line);
    if (found === -1) {
      sourceNote.textContent = '계산값·분기 출력은 원본 소스를 참고해. 실행 줄 번호를 추측해서 표시하지 않아.';
      return;
    }
    if (lastSourceLine >= 0 && sourceNodes[lastSourceLine]) {
      sourceNodes[lastSourceLine].classList.remove('source-active');
      sourceNodes[lastSourceLine].removeAttribute('aria-current');
    }
    lastSourceLine = found;
    const row = sourceNodes[found];
    row.classList.add('source-active');
    row.setAttribute('aria-current', 'true');
    // Keep the VGA screen in view; only scroll the source subpanel.
    sourceView.scrollTop = Math.max(0, row.offsetTop - sourceView.clientHeight / 2);
    sourceNote.textContent = '실제 COM1 출력과 일치한 <print> 텍스트를 강조했어. 이는 명령어별 디버깅이 아니야.';
  }

  function drawSource(sourceText) {
    sourceLines = sourceText.replace(/\r\n/g, '\n').split('\n');
    sourceNodes = [];
    lastSourceLine = -1;
    sourceView.replaceChildren();
    for (let i = 0; i < sourceLines.length; i++) {
      if (i === sourceLines.length - 1 && !sourceLines[i]) continue;
      const row = document.createElement('div');
      row.className = 'source-row';
      const number = document.createElement('span');
      number.className = 'source-line-number';
      number.textContent = String(i + 1);
      const code = document.createElement('span');
      code.className = 'source-code';
      code.textContent = sourceLines[i];
      row.append(number, code);
      sourceView.append(row);
      sourceNodes.push(row);
    }
  }

  async function loadSource(demo) {
    sourceView.textContent = 'HTML 원본 소스를 불러오는 중...';
    sourcePath.textContent = 'examples/' + demo.source;
    sourceNote.textContent = '이 HTML은 커널 코드의 입력 소스야. BIOS와 Limine의 실행 코드는 HTML이 아니야.';
    sourceLines = [];
    sourceNodes = [];
    try {
      const response = await fetch('./examples/' + demo.source, {
        cache: 'no-store',
        credentials: 'omit'
      });
      if (!response.ok) throw Error('HTTP ' + response.status);
      const text = await response.text();
      if (currentDemo !== demo) return;
      drawSource(text);
      // The guest can finish before the source fetch; reconcile only with
      // already received real COM1 lines, not a guessed instruction pointer.
      const lines = serial.trimEnd().split('\n');
      for (let i = lines.length - 1; i >= 0; i--) {
        if (sourceLineForLiteral(lines[i]) !== -1) {
          highlightLiteral(lines[i]);
          break;
        }
      }
    } catch (error) {
      if (currentDemo !== demo) return;
      sourceView.textContent = '원본 HTML을 불러올 수 없어: ' + String(error?.message || error);
      sourceNote.textContent = '소스 로드 실패. 실행 중인 ISO와 코드가 일치한다고 표시하지 않아.';
    }
  }

  function useDemo() {
    if (!Object.prototype.hasOwnProperty.call(demos, selection.value)) return;
    currentDemo = demos[selection.value];
    download.href = './' + currentDemo.iso;
    void loadSource(currentDemo);
  }

  function onSerialByte(byte) {
    if (serial.length >= 12000) {
      if (!serialMismatch) {
        serialMismatch = true;
        setStatus('COM1 출력이 표시 한도를 넘었어. 결과 검증 불가.');
        logEvent('COM1 제한', '12,000바이트 수신 한도 도달');
      }
      return;
    }
    if (!firstByteSeen) {
      firstByteSeen = true;
      liveTag.textContent = 'LIVE / COM1';
      sourceNote.textContent = '첫 COM1 바이트 수신: HTML에서 컴파일한 커널의 출력이 시작됐어.';
      logEvent('KERNEL COM1', '실제 네이티브 커널에서 첫 시리얼 바이트 수신');
      setStatus('커널 실행 중 · 실제 COM1 바이트를 실시간으로 표시 중...');
    }
    if (replaying) clearPlayback();
    serial += String.fromCharCode(byte);
    output.textContent = serial;
    output.scrollTop = output.scrollHeight;
    if (serial.endsWith('\n')) {
      const lines = serial.trimEnd().split('\n');
      highlightLiteral(lines[lines.length - 1]);
    }
    if (serial !== currentDemo.expected && !currentDemo.expected.startsWith(serial)) {
      if (!serialMismatch) logEvent('출력 불일치', '기대 출력과 실제 COM1이 달라졌어. 원본을 그대로 표시해.');
      serialMismatch = true;
      replay.disabled = true;
      setStatus('실제 COM1과 기대 출력이 달라. 원본 바이트를 그대로 보여주는 중.');
    } else if (!serialMismatch && serial === currentDemo.expected) {
      serialVerified = true;
      clearPaceTimer();
      liveTag.textContent = 'VERIFIED / COM1';
      replay.disabled = false;
      logEvent('KERNEL PASS', '실제 COM1 바이트가 선택한 커널의 기대 출력과 정확히 일치');
      setStatus('실제 커널 부팅 검증 성공 · COM1 전체 기록을 볼 수 있고 다시 재생할 수도 있어.');
    }
  }

  function replayTick() {
    if (!replaying || !serialVerified) return;
    playbackPosition = Math.min(serial.length, playbackPosition + 1);
    output.textContent = serial.slice(0, playbackPosition);
    output.scrollTop = output.scrollHeight;
    if (playbackPosition < serial.length) {
      playbackTimer = setTimeout(replayTick, Number(replaySpeed.value));
    } else {
      clearPlayback();
      replay.disabled = false;
      liveTag.textContent = 'VERIFIED / COM1';
      setStatus('기록 재생 완료 · 원본 COM1을 모두 표시했어.');
    }
  }

  function playRecordedSerial() {
    if (!serialVerified) return;
    clearPlayback();
    replaying = true;
    playbackPosition = 0;
    output.textContent = '';
    liveTag.textContent = 'REPLAY / COM1';
    replay.disabled = true;
    setStatus('검증된 시리얼 출력만 다시 재생 중 · 가상 CPU 부팅 속도를 조작하는 기능은 아니야.');
    replayTick();
  }

  function schedulePacedStop() {
    if (paceChoice.value !== 'slow' || !machine || userPaused || userStopped ||
        serialVerified || paceStopPending || paceTimer !== null) return;
    paceTimer = setTimeout(async () => {
      paceTimer = null;
      if (!machine || userPaused || userStopped || serialVerified) return;
      paceStopPending = true;
      try {
        await machine.stop();
      } catch (error) {
        paceStopPending = false;
        setStatus('관찰 속도 모드 실패: ' + String(error?.message || error));
      }
    }, 65);
  }

  selection.addEventListener('change', useDemo);
  useDemo();
  replay.addEventListener('click', playRecordedSerial);
  fullscreen.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement === screen) await document.exitFullscreen();
      else await screen.requestFullscreen();
    } catch (error) {
      setStatus('전체 화면 전환 불가: ' + String(error?.message || error));
    }
  });
  document.addEventListener('fullscreenchange', () => {
    fullscreen.textContent = document.fullscreenElement === screen ? '전체 화면 닫기' : '화면 크게 보기';
  });

  start.addEventListener('click', () => {
    if (machine) { window.location.reload(); return; }
    clearPlayback();
    clearPaceTimer();
    resetVga();
    events.replaceChildren();
    latestEvent.textContent = '실제 가상머신 이벤트 기록을 준비 중...';
    bootStartedAt = performance.now();
    serial = '';
    serialVerified = false;
    serialMismatch = false;
    firstByteSeen = false;
    firstEmulatorStart = false;
    userStopped = false;
    userPaused = false;
    paceStopPending = false;
    playbackPosition = 0;
    replay.disabled = true;
    start.disabled = true;
    selection.disabled = true;
    paceChoice.disabled = true;
    pauseButton.disabled = true;
    pauseButton.textContent = '일시 정지';
    output.textContent = '';
    liveTag.textContent = 'WAITING / COM1';
    const demo = currentDemo;
    logEvent('브라우저', '선택한 HTML 소스에서 미리 빌드한 ISO와 BIOS 리소스 다운로드 요청');
    setStatus('가상 PC를 생성하고 실제 SeaBIOS·부트로더 실행을 준비 중...');
    try {
      machine = new V86({
        cpu_type: 'x86_64',
        graphics_adapter: 'bochs_vga',
        wasm_path: './vendor/v86.wasm',
        memory_size: 128 * 1024 * 1024,
        vram_size: 4 * 1024 * 1024,
        screen_container: screen,
        bios: { url: './vendor/seabios.bin' },
        vga_bios: { url: './vendor/vgabios.bin' },
        cdrom: { url: './' + demo.iso },
        acpi: true,
        net_device: { type: 'none' },
        audio_device: 'none',
        autostart: true
      });
      machine.add_listener('emulator-ready', () => {
        logEvent('V86 준비', '가상머신 초기화 완료 이벤트 수신 (아직 커널 실행 증거는 아님)');
        if (!firstByteSeen) setStatus('가상 PC 준비 완료 · BIOS VGA 문자 이벤트를 실시간 기록 중...');
      });
      machine.add_listener('screen-put-char', recordVgaCell);
      machine.add_listener('emulator-started', () => {
        if (!firstEmulatorStart) {
          firstEmulatorStart = true;
          logEvent('CPU 실행', paceChoice.value === 'slow' ?
            '실제 CPU 실행 시작 · 65ms 실행/450ms 정지 반복 관찰 모드' :
            '실제 에뮬레이터 CPU 시작');
        }
        stop.disabled = false;
        pauseButton.disabled = false;
        pauseButton.textContent = '일시 정지';
        if (!firstByteSeen) setStatus('SeaBIOS/부트로더 단계 · VGA 기록 확인 중 (아직 COM1 없음)');
        schedulePacedStop();
      });
      machine.add_listener('serial0-output-byte', onSerialByte);
      machine.add_listener('emulator-stopped', () => {
        if (userStopped) {
          pauseButton.disabled = true;
          stop.disabled = true;
          return;
        }
        if (userPaused) {
          pauseButton.textContent = '계속 실행';
          setStatus('실제 가상 CPU가 일시 정지됐어. 계속 실행할 수 있어.');
          return;
        }
        if (paceStopPending) {
          paceStopPending = false;
          if (!userStopped) {
            // After validation, resume without further pacing. During boot,
            // genuine v86 CPU pauses separate brief execution windows.
            paceTimer = setTimeout(async () => {
              paceTimer = null;
              if (!machine || userPaused || userStopped) return;
              try { await machine.run(); }
              catch (error) { setStatus('관찰 속도 재개 실패: ' + String(error?.message || error)); }
            }, serialVerified ? 0 : 450);
          }
          return;
        }
        pauseButton.disabled = true;
        if (!serialVerified) setStatus('가상 CPU 중지됨 · 실시간 COM1 출력과 부팅 이벤트를 확인해.');
      });
    } catch (error) {
      machine = null;
      start.disabled = false;
      selection.disabled = false;
      paceChoice.disabled = false;
      setStatus('가상 PC 생성 실패: ' + String(error?.message || error));
      logEvent('시작 실패', String(error?.message || error));
    }
  });

  pauseButton.addEventListener('click', async () => {
    if (!machine || userStopped) return;
    clearPaceTimer();
    if (!userPaused) {
      userPaused = true;
      pauseButton.disabled = true;
      try {
        await machine.stop();
        paceStopPending = false;
        logEvent('CPU 일시정지', 'v86.stop() 완료 · 실제 CPU 진행 정지');
        pauseButton.textContent = '계속 실행';
      } catch (error) {
        userPaused = false;
        setStatus('일시 정지 실패: ' + String(error?.message || error));
      } finally { pauseButton.disabled = false; }
    } else {
      userPaused = false;
      pauseButton.disabled = true;
      try {
        await machine.run();
        logEvent('CPU 재개', 'v86.run() · 가상 CPU 실제 실행 재개');
        pauseButton.textContent = '일시 정지';
      } catch (error) {
        userPaused = true;
        setStatus('CPU 실행 재개 실패: ' + String(error?.message || error));
      } finally { pauseButton.disabled = false; }
    }
  });

  stop.addEventListener('click', async () => {
    if (!machine || userStopped) return;
    userStopped = true;
    clearPaceTimer();
    clearPlayback();
    stop.disabled = true;
    pauseButton.disabled = true;
    try {
      await machine.stop();
      logEvent('VM 종료', '사용자가 실제 가상 CPU를 정지함');
      start.disabled = false;
      start.textContent = '다시 부팅 ↗';
      setStatus(serialVerified ?
        'VM 정지 · COM1 검증 성공. 다시 보기 또는 새로 부팅을 선택할 수 있어.' :
        'VM 정지 · 지금까지 받은 BIOS·COM1 기록은 유지돼.');
      replay.disabled = !serialVerified;
    } catch (error) {
      userStopped = false;
      setStatus('가상 PC 정지 실패: ' + String(error?.message || error));
      stop.disabled = false;
      pauseButton.disabled = false;
    }
  });
})();
