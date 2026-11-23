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
  const demos = Object.freeze({
    video: {
      iso: 'html-kernel-video.iso',
      expected: 'HTML KERNEL ON-SCREEN\nTHE DISPLAY IS DRAWN BY THE BOOTED CPU\n42\nVIDEO PASS\n'
    },
    basic: {
      iso: 'html-kernel.iso',
      expected: 'Hello from HTML Kernel!\nNative code, not a browser.\n'
    },
    math: {
      iso: 'html-kernel-math.iso',
      expected: 'Arithmetic in HTML Kernel!\n14\n16\n18\ncondition PASS\n18446744073709551615\n'
    },
    functions: {
      iso: 'html-kernel-functions.iso',
      expected: 'Functions in HTML Kernel!\n13\n17\nfunction PASS\n10\n12\n'
    },
    scoped: {
      iso: 'html-kernel-scoped.iso',
      expected: 'Scoped functions in HTML Kernel!\n25\n10\nscoped function PASS\n'
    },
    branches: {
      iso: 'html-kernel-else.iso',
      expected: 'HTML if/else native!\nelse branch PASS\n8\n17\n222\nnested PASS\nnested PASS\n'
    },
    u32: {
      iso: 'html-kernel-u32.iso',
      expected: 'Native u32 types in HTML Kernel!\n4294967295\n0\n1\n4294967295\n4294967296\ntyped PASS\n'
    },
    signed: {
      iso: 'html-kernel-signed.iso',
      expected: 'Typed signed integers and bitwise kernel!\n-2147483648\n2147483647\n1\n2\n-9223372036854775808\n9223372036854775807\n-1\n18446744073709551615\n43\n0\n4294967295\n1\n3\ntyped signed and loop PASS\n'
    }
  });

  let machine = null;
  let serial = '';
  let serialVerified = false;
  let playbackTimer = null;
  let playbackPosition = 0;
  const setStatus = message => { status.textContent = message; };

  const clearPlayback = () => {
    if (playbackTimer !== null) {
      clearTimeout(playbackTimer);
      playbackTimer = null;
    }
  };
  function replayTick() {
    if (!serialVerified) return;
    const length = Math.min(serial.length, playbackPosition + 1);
    output.textContent = serial.slice(0, length);
    playbackPosition = length;
    output.scrollTop = output.scrollHeight;
    if (playbackPosition < serial.length) {
      // Recorded COM1 bytes, NOT a slowed guest CPU or fabricated boot video.
      playbackTimer = setTimeout(replayTick, Number(replaySpeed.value));
    } else {
      playbackTimer = null;
      replay.disabled = false;
      setStatus('실제 커널 부팅 검증 성공 · 기록된 시리얼 재생 완료. 다시 보기도 가능해.');
    }
  }
  function playRecordedSerial() {
    if (!serialVerified) return;
    clearPlayback();
    playbackPosition = 0;
    replay.disabled = true;
    output.textContent = '';
    setStatus('실제 네이티브 부팅 검증 성공 · COM1 기록을 천천히 다시 보여 주는 중 (CPU 속도 조절 아님).');
    replayTick();
  }

  selection.addEventListener('change', () => {
    download.href = './' + demos[selection.value].iso;
  });
  download.href = './' + demos[selection.value].iso;
  replay.addEventListener('click', playRecordedSerial);
  fullscreen.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement === screen) {
        await document.exitFullscreen();
      } else {
        await screen.requestFullscreen();
      }
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
    serial = '';
    serialVerified = false;
    playbackPosition = 0;
    replay.disabled = true;
    start.disabled = true;
    selection.disabled = true;
    const demo = demos[selection.value];
    output.textContent = '';
    setStatus('x86-64 WebAssembly 가상머신과 실제 커널 ISO를 불러오는 중...');
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
      machine.add_listener('emulator-ready', () => setStatus('가상 PC 준비 완료. 실제 부트로더 실행 중...'));
      machine.add_listener('emulator-started', () => {
        setStatus('x86-64 가상 PC 실행 중. 실제 COM1 메시지를 수신하고 있어.');
        stop.disabled = false;
      });
      machine.add_listener('serial0-output-byte', byte => {
        if (serial.length >= 12000 || serialVerified) return;
        serial += String.fromCharCode(byte);
        if (serial === demo.expected) {
          serialVerified = true;
          replay.disabled = false;
          playRecordedSerial();
        } else if (!demo.expected.startsWith(serial)) {
          output.textContent = serial;
          replay.disabled = true;
          setStatus('실제 커널 출력이 기대값과 달라. 원본 COM1 기록을 확인해.');
        }
      });
      machine.add_listener('emulator-stopped', () => {
        stop.disabled = true;
        if (!serial) {
          setStatus('가상 PC가 정지했어. 커널 출력을 확인하지 못했어.');
        } else if (!serialVerified) {
          output.textContent = serial;
          setStatus('가상 PC 정지 · 커널 출력을 끝까지 검증하지 못했어.');
        }
      });
    } catch (error) {
      machine = null;
      start.disabled = false;
      selection.disabled = false;
      setStatus('가상 PC 시작 실패: ' + String(error?.message || error));
    }
  });

  stop.addEventListener('click', async () => {
    if (!machine) return;
    stop.disabled = true;
    try {
      await machine.stop();
      start.disabled = false;
      start.textContent = '다시 부팅 ↗';
      setStatus(serialVerified
        ? '가상 PC 정지 · 검증된 COM1 기록은 아래에서 다시 볼 수 있어.'
        : '가상 PC 정지됨. 시리얼 결과를 확인해.');
    } catch (error) {
      setStatus('정지 실패: ' + String(error?.message || error));
    }
  });
})();
