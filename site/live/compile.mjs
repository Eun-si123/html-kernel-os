/* M2-UX7-A: real canonical Python→C via optional Pyodide WebWorker.
 * Shows diagnostics and download of actual C, NEVER simulated native output.
 * The real x86-64 HKEX/ISO still requires the existing local GCC toolchain.
 */
import {sourceState, SOURCE_LIMIT} from './editor.mjs';
export const COMPILER_TIMEOUT_MS = 90000;
export const C_FILENAME = 'htmlk-generated-user.c';
export const WORKER_URL = new URL('./compiler-worker.mjs', import.meta.url);

export function formatDiagnostics(issues) {
  if (!Array.isArray(issues) || !issues.length) return '알 수 없는 컴파일 오류';
  return issues.slice(0,8).map(item => {
    const location = Number.isInteger(item.line) && Number.isInteger(item.column) ?
      `줄 ${item.line}, 열 ${item.column}: ` : '문서 전체: ';
    return location + String(item.code || 'HK100') + ' · ' +
      String(item.message || '컴파일 오류').slice(0,260) +
      (item.hint ? '\n도움말: ' + String(item.hint).slice(0,200) : '');
  }).join('\n');
}

export function setupBrowserCompiler(doc = document) {
  const editor = doc.getElementById('html-editor');
  const compile = doc.getElementById('browser-compile');
  const saveC = doc.getElementById('browser-save-c');
  const status = doc.getElementById('browser-compile-status');
  const output = doc.getElementById('browser-compiler-output');
  if (!editor || !compile || !saveC || !status || !output) return;

  let worker = null;
  let timeout = null;
  let currentId = 0;
  let compiledC = null;
  let snapshot = null;

  const cleanup = () => {
    if (timeout !== null) clearTimeout(timeout);
    timeout = null;
    if (worker) worker.terminate();
    worker = null;
    compile.disabled = false;
  };
  const invalidate = () => {
    const active = !!worker;
    currentId++;
    cleanup();
    compiledC = null;
    snapshot = null;
    saveC.disabled = true;
    output.textContent = '';
    if (active) status.textContent = '소스가 변경되어 이전 컴파일을 취소했어.';
    else status.textContent = '현재 소스는 브라우저에서 아직 컴파일되지 않았어.';
  };
  editor.addEventListener('input',invalidate);

  compile.addEventListener('click', () => {
    invalidate();
    const state = sourceState(editor.value);
    if (!state.valid || state.bytes > SOURCE_LIMIT) {
      status.textContent = '1..4096바이트의 유효한 HTMLK 원본만 검사할 수 있어.';
      return;
    }
    if (!window.Worker || !window.crypto?.subtle) {
      status.textContent = '이 브라우저는 필요한 Web Worker 또는 SHA-256을 지원하지 않아.';
      return;
    }
    snapshot = editor.value;
    const id = ++currentId;
    compile.disabled = true;
    status.textContent = '실제 Python 컴파일러 다운로드 및 실행 준비 중…';
    try {
      worker = new Worker(WORKER_URL, {type:'module',name:'htmlk-typed-compiler'});
    } catch (error) {
      cleanup();
      status.textContent = '컴파일러 Worker 시작 실패: ' + String(error?.message || error).slice(0,180);
      return;
    }
    const fail = message => {
      if (id !== currentId) return;
      cleanup();
      status.textContent = message;
    };
    timeout = setTimeout(() => fail('90초 이내에 완료되지 않아 WebAssembly 컴파일러를 종료했어.'),
                         COMPILER_TIMEOUT_MS);
    worker.onerror = () => fail('WebAssembly Python 로딩 실패. 네트워크·브라우저 정책을 확인해.');
    worker.onmessageerror = () => fail('컴파일러 메시지 전송 실패.');
    worker.onmessage = event => {
      const message = event.data || {};
      if (id !== currentId || message.requestId !== id || editor.value !== snapshot) return;
      if (message.type === 'progress') {
        const known = {
          'pyodide-loading':'고정 버전 Pyodide WebAssembly 다운로드·시작 중…',
          'compiler-source-verifying':'GitHub Pages에서 실제 Python 컴파일러 소스 해시 검증 중…',
          'authoritative-compiler-loaded':'컴파일러 로딩 완료 · 같은 타깃의 C 코드 생성 중…',
        };
        if (known[message.stage]) status.textContent = known[message.stage];
      } else if (message.type === 'error') {
        fail('컴파일러 실패: ' + String(message.message || '알 수 없음').slice(0,350));
      } else if (message.type === 'result') {
        cleanup();
        if (!message.ok) {
          output.textContent = formatDiagnostics(message.diagnostics);
          status.textContent = '실제 Python 컴파일러가 HTMLK 소스를 거부했어. C/ISO는 생성되지 않았어.';
          return;
        }
        if (typeof message.c !== 'string' || message.c.length > 131072 ||
            !/^[a-f0-9]{64}$/.test(message.generated_c_sha256 || '')) {
          status.textContent = '컴파일러의 잘못된 결과를 거부했어.';
          return;
        }
        compiledC = message.c;
        output.textContent = compiledC;
        saveC.disabled = false;
        status.textContent = '실제 HTMLK → C 컴파일 성공 · SHA-256: ' +
          message.generated_c_sha256 + ' · x86-64 HKEX/ISO는 아직 생성되지 않았어.';
      }
    };
    worker.postMessage({requestId:id,source:snapshot});
  });

  saveC.addEventListener('click', () => {
    if (!compiledC || editor.value !== snapshot) return;
    const url = URL.createObjectURL(new Blob([new TextEncoder().encode(compiledC)],
      {type:'text/x-c;charset=utf-8'}));
    try {
      const a = doc.createElement('a');
      a.href=url;
      a.download=C_FILENAME;
      doc.body.appendChild(a);
      a.click();
      a.remove();
    } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
  });

  window.addEventListener('pagehide',cleanup,{once:true});
  status.textContent = '선택 기능 · 실제 컴파일러는 버튼을 누르기 전까지 내려받지 않아.';
}
if (typeof document !== 'undefined') setupBrowserCompiler(document);
