import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {C_FILENAME,COMPILER_TIMEOUT_MS,WORKER_URL,formatDiagnostics} from '../site/live/compile.mjs';
import {sourceState,TEMPLATE} from '../site/live/editor.mjs';

test('HTMLK worker CLI is opt-in real Python WebAssembly compiler with clear limits',()=>{
  const worker=fs.readFileSync('site/live/compiler-worker.mjs','utf8');
  const controller=fs.readFileSync('site/live/compile.mjs','utf8');
  assert.equal(C_FILENAME,'htmlk-generated-user.c');
  assert.equal(COMPILER_TIMEOUT_MS,90000);
  assert.equal(WORKER_URL.pathname.endsWith('/site/live/compiler-worker.mjs'),true);
  assert.ok(worker.includes("const CDN = 'https://cdn.jsdelivr.net/pyodide/v0.29.5/full/'"));
  assert.ok(worker.includes("py.globals.set('_htmlk_source',source)"));
  assert.ok(worker.includes("compile_html(_htmlk_source, target='user')"));
  assert.ok(worker.includes('await digest(bytes) !== info.sha256'));
  assert.ok(worker.includes('outcome.generated_c_sha256'));
  assert.ok(controller.includes("new Worker(WORKER_URL, {type:'module'"));
  assert.ok(controller.includes('worker.terminate()'));
  assert.ok(controller.includes('compiledC = message.c'));
  assert.ok(!worker.includes('M5_C_USER_VALUE='),'never invent native UART output');
  assert.ok(!worker.includes('eval(source)'),'do not evaluate user HTML as JS');
  assert.ok(!controller.includes('innerHTML'));
});

test('proper UTF-8 source bounds, no fake output and correct human diagnostics',()=>{
  assert.equal(sourceState(TEMPLATE).valid,true);
  assert.equal(sourceState('한'.repeat(1366)).valid,false);
  assert.equal(sourceState('A'.repeat(4097)).valid,false);
  assert.equal(formatDiagnostics([{
    code:'HK101_TAG',line:5,column:5,message:'<prnit> is not allowed under <main>',
    hint:'Did you mean <print>?'
  }]),'줄 5, 열 5: HK101_TAG · <prnit> is not allowed under <main>\n도움말: Did you mean <print>?');
  assert.equal(formatDiagnostics([{code:'HK100',message:'document error'}]),
    '문서 전체: HK100 · document error');
  assert.equal(formatDiagnostics([]),'알 수 없는 컴파일 오류');
});

test('HTML editor reset notifies compiler controller to revoke stale C',()=>{
  const editor=fs.readFileSync('site/live/editor.mjs','utf8');
  assert.ok(editor.includes("editor.dispatchEvent(new Event('input', {bubbles:true}))"));
  assert.ok(fs.readFileSync('site/live/index.html','utf8').includes('id="browser-compiler"'));
  assert.ok(fs.readFileSync('site/live/index.html','utf8').includes('ISO 생성 아님'));
});


test('real Worker reader stops oversized network responses before allocation',async()=>{
  const oldSelf = globalThis.self;
  globalThis.self = {postMessage:()=>{}};
  try {
    const {boundedResponseBytes} = await import('../site/live/compiler-worker.mjs');
    const okay=new Response(new Uint8Array([1,2,3]));
    assert.deepEqual([...await boundedResponseBytes(okay,3)],[1,2,3]);
    await assert.rejects(boundedResponseBytes(new Response(new Uint8Array([1,2,3])),2),
                         /응답 크기 제한 초과/);
    const overflow = new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array([1,2]));
        controller.enqueue(new Uint8Array([3,4]));
        controller.close();
      }
    });
    await assert.rejects(boundedResponseBytes(new Response(overflow),3),
                         /응답 크기 제한 초과/);
    await assert.rejects(boundedResponseBytes(new Response('nope'),-1),
                         /잘못된 브라우저 컴파일러 다운로드 제한/);
  } finally { globalThis.self = oldSelf; }
});
