/* M2-UX7-A experimental, REAL canonical Python HTMLK -> C in WebAssembly.
 * The actual Python compiler sources are copied byte-for-byte by Pages CI.
 * No JS language parser, no fabricated output, no C->native ELF/HKEX/ISO.
 * Only start a new worker when the user explicitly asks to compile.
 * Pyodide comes from a PINNED versioned CDN (network/trust limitation).
 */
const CDN = 'https://cdn.jsdelivr.net/pyodide/v0.29.5/full/';
const MAX_EDITOR_BYTES = 4096;
const MAX_OUTPUT_BYTES = 131072;
const MAX_COMPILER_FILE_BYTES = 100000;
const FILES = ['__init__.py','numeric_types.py','language.py',
               'function_codegen.py','htmlk.py','diagnostics.py'];
const hex = bytes => Array.from(bytes, n => n.toString(16).padStart(2,'0')).join('');
async function digest(bytes) { return hex(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))); }
function report(requestId, stage) { self.postMessage({type:'progress',requestId,stage}); }

// Enforce bounded network downloads BEFORE a large response is held in memory.
// This matters especially on low-RAM phones and for malformed same-origin files.
export async function boundedResponseBytes(response, limit) {
  if (!Number.isInteger(limit) || limit < 0 || limit > MAX_COMPILER_FILE_BYTES)
    throw Error('잘못된 브라우저 컴파일러 다운로드 제한');
  const sizeHeader = response.headers?.get('content-length');
  if (sizeHeader !== null && sizeHeader !== undefined) {
    if (!/^[0-9]+$/.test(sizeHeader) || Number(sizeHeader) > limit)
      throw Error('컴파일러 네트워크 응답 크기 제한 초과');
  }
  if (!response.body?.getReader) throw Error('브라우저 응답 스트리밍 미지원');
  const reader = response.body.getReader();
  let total = 0;
  const parts = [];
  try {
    while (true) {
      const {done,value} = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) throw Error('잘못된 다운로드 바이트');
      total += value.byteLength;
      if (total > limit) {
        await reader.cancel();
        throw Error('컴파일러 네트워크 응답 크기 제한 초과');
      }
      parts.push(value);
    }
  } finally { reader.releaseLock(); }
  const all = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) { all.set(part, offset); offset += part.byteLength; }
  return all;
}

async function actualCompiler(py, requestId) {
  const manifestUrl = new URL('../compiler/manifest.json', import.meta.url);
  const response = await fetch(manifestUrl, {credentials:'omit', cache:'no-store'});
  if (!response.ok) throw Error('컴파일러 파일 명세를 불러올 수 없음 (HTTP '+response.status+')');
  const rawManifest = await boundedResponseBytes(response, 8192);
  const meta = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(rawManifest));
  if (meta.schema_version !== 1 || meta.target !== 'user' ||
      meta.pyodide_version !== '0.29.5' ||
      Object.keys(meta.files||{}).length !== FILES.length ||
      FILES.some(name => !meta.files[name])) {
    throw Error('지원하지 않는 네이티브 컴파일러 소스 명세');
  }
  py.FS.mkdirTree('/htmlk/compiler');
  for (const name of FILES) {
    const info = meta.files[name];
    if (!Number.isInteger(info.bytes) || info.bytes < 0 ||
        info.bytes > MAX_COMPILER_FILE_BYTES ||
        !/^[a-f0-9]{64}$/.test(info.sha256)) throw Error('부정확한 컴파일러 소스 명세: '+name);
    const url = new URL('../compiler/' + name, import.meta.url);
    const file = await fetch(url,{credentials:'omit',cache:'no-store'});
    if (!file.ok) throw Error('컴파일러 소스 누락: '+name);
    const bytes = await boundedResponseBytes(file, info.bytes);
    if (bytes.byteLength !== info.bytes || await digest(bytes) !== info.sha256)
      throw Error('컴파일러 소스 해시/길이가 일치하지 않음: '+name);
    py.FS.writeFile('/htmlk/compiler/' + name, bytes);
  }
  // This is fixed Python glue code; user-provided input is passed via globals
  // as a DATA STRING. Never interpolate visitor HTML into executed Python.
  py.runPython("import sys; sys.path.insert(0, '/htmlk')\n"
      + 'from compiler.diagnostics import check\n'
      + 'from compiler.htmlk import compile_html\n'
      + 'import json\n');
  report(requestId,'authoritative-compiler-loaded');
}

const PYTHON_COMPILE = `
checked = check(_htmlk_source, target='user', file='editor://htmlk-program.html')
result = {'schema_version': 1, 'target':'user', 'source_sha256': checked['source_sha256'],
          'generated_c_sha256': checked['generated_c_sha256'],
          'ok': checked['ok'], 'diagnostics': checked['diagnostics'], 'c': None}
if checked['ok']:
    result['c'] = compile_html(_htmlk_source, target='user')
json.dumps(result, ensure_ascii=False, separators=(',', ':'))
`;

self.onmessage = async event => {
  const {requestId,source} = event.data || {};
  if (!Number.isSafeInteger(requestId) || requestId < 1 || typeof source !== 'string') return;
  const bytes = new TextEncoder().encode(source);
  if (!bytes.length || bytes.length > MAX_EDITOR_BYTES) {
    self.postMessage({type:'error',requestId,message:'소스 크기가 1..4096 UTF-8 바이트 범위를 벗어남'});
    return;
  }
  try {
    report(requestId,'pyodide-loading');
    const {loadPyodide} = await import(CDN + 'pyodide.mjs');
    const py = await loadPyodide({indexURL:CDN});
    report(requestId,'compiler-source-verifying');
    await actualCompiler(py,requestId);
    py.globals.set('_htmlk_source',source);
    let text;
    try { text = py.runPython(PYTHON_COMPILE); }
    finally { py.runPython('_htmlk_source = None'); }
    const outcome = JSON.parse(text);
    if (outcome.ok) {
      if (typeof outcome.c !== 'string' ||
          new TextEncoder().encode(outcome.c).byteLength > MAX_OUTPUT_BYTES ||
          await digest(new TextEncoder().encode(outcome.c)) !== outcome.generated_c_sha256) {
        throw Error('컴파일러 결과 길이/해시 검증 실패');
      }
    } else if (!Array.isArray(outcome.diagnostics)) {
      throw Error('컴파일러 진단 형식 오류');
    }
    self.postMessage({type:'result',requestId,...outcome});
  } catch (error) {
    self.postMessage({type:'error',requestId,message:String(error?.message || error).slice(0,350)});
  }
};
