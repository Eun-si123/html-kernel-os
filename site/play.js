import V86 from './vendor/libv86.mjs';

(() => {
  'use strict';
  const start = document.getElementById('boot-start');
  const stop = document.getElementById('boot-stop');
  const status = document.getElementById('boot-status');
  const output = document.getElementById('boot-output');
  let machine = null;
  let bytesReceived = 0;
  const setStatus = message => { status.textContent = message; };

  start.addEventListener('click', () => {
    if (machine) { window.location.reload(); return; }
    start.disabled = true;
    output.textContent = '';
    setStatus('x86-64 WebAssembly 가상머신과 실제 커널 ISO를 불러오는 중...');
    try {
      machine = new V86({
        cpu_type: 'x86_64',
        graphics_adapter: 'bochs_vga',
        wasm_path: './vendor/v86.wasm',
        memory_size: 128 * 1024 * 1024,
        vram_size: 2 * 1024 * 1024,
        screen_container: document.getElementById('screen_container'),
        bios: { url: './vendor/seabios.bin' },
        vga_bios: { url: './vendor/vgabios.bin' },
        cdrom: { url: './html-kernel.iso' },
        acpi: true,
        net_device: { type: 'none' },
        audio_device: 'none',
        autostart: true
      });
      machine.add_listener('emulator-ready', () => setStatus('가상 PC 준비 완료. 부트로더를 시작하는 중...'));
      machine.add_listener('emulator-started', () => {
        setStatus('가상 PC 실행 중. 커널 부팅 메시지를 확인하는 중...');
        stop.disabled = false;
      });
      machine.add_listener('serial0-output-byte', byte => {
        if (bytesReceived++ > 12000) return;
        output.textContent += String.fromCharCode(byte);
        if (output.textContent.includes('Native code, not a browser.')) {
          setStatus('실제 HTML 파생 커널의 시리얼 출력 수신 성공!');
        }
      });
      machine.add_listener('emulator-stopped', () => {
        stop.disabled = true;
        if (!bytesReceived) setStatus('가상 PC가 정지했어. 커널 출력을 확인하지 못했어.');
      });
    } catch (error) {
      machine = null;
      start.disabled = false;
      setStatus('가상 PC 시작 실패: ' + String(error?.message || error));
    }
  });

  stop.addEventListener('click', async () => {
    if (!machine) return;
    stop.disabled = true;
    try {
      await machine.stop();
      setStatus('가상 PC 정지됨. 다시 체험하려면 페이지를 새로고침해.');
    } catch (error) {
      setStatus('정지 실패: ' + String(error?.message || error));
    }
  });
})();
