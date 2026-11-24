/* M2-UX4: locally edit and download source. NEVER claim HTML was compiled here.
 * The real native ISO toolchain must run separately before importing an ISO.
 * Pure exports are tested in Node without DOM/emulation mocks. */
export const SOURCE_LIMIT = 4096;
export const EXPORT_FILENAME = 'htmlk-program.html';
export const TEMPLATE = `<!-- HTML Kernel Language: edit, save, then build a native ISO locally. -->
<program>
  <main>
    <let name="value" type="u64" value="2026"/>
    <print value="value"/>
    <halt/>
  </main>
</program>
`;
export const BUILD_COMMAND = 'python3 scripts/build_live_site.py --source ' +
  EXPORT_FILENAME + ' --out-dir build/my-html-os';
export function sourceBytes(text) {
  return new TextEncoder().encode(text);
}
export function sourceState(text) {
  const bytes = sourceBytes(text);
  return { bytes: bytes.length, valid: bytes.length > 0 && bytes.length <= SOURCE_LIMIT };
}
export function setupEditor(doc = document) {
  const editor = doc.getElementById('html-editor');
  const count = doc.getElementById('editor-bytes');
  const status = doc.getElementById('editor-status');
  const save = doc.getElementById('editor-save');
  const reset = doc.getElementById('editor-reset');
  const copy = doc.getElementById('editor-copy');
  const command = doc.getElementById('editor-command');
  if (!editor || !count || !status || !save || !reset || !copy || !command) return;
  editor.value = TEMPLATE;
  command.textContent = BUILD_COMMAND;
  function refresh() {
    const state = sourceState(editor.value);
    count.textContent = `${state.bytes} / ${SOURCE_LIMIT} bytes (UTF-8)`;
    save.disabled = !state.valid;
    if (!state.valid) {
      status.textContent = `이 파일은 ${SOURCE_LIMIT}바이트 ROMFS 제한을 초과했거나 비어 있어. 저장 불가.`;
    } else {
      status.textContent = '편집한 HTML은 아직 컴파일되지 않았어. 먼저 파일로 저장해.';
    }
  }
  editor.addEventListener('input', refresh);
  reset.addEventListener('click', () => {
    if (editor.value !== TEMPLATE && !window.confirm('현재 편집 내용을 버리고 예제를 다시 불러올까?')) return;
    editor.value = TEMPLATE;
    // Programmatic reset must invalidate any previously compiled C snapshot.
    editor.dispatchEvent(new Event('input', {bubbles:true}));
  });
  save.addEventListener('click', () => {
    if (!sourceState(editor.value).valid) return;
    const blob = new Blob([sourceBytes(editor.value)], {type:'text/html;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    try {
      const anchor = doc.createElement('a');
      anchor.href = url;
      anchor.download = EXPORT_FILENAME;
      doc.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      status.textContent = 'HTML 원본 저장 요청 완료. 아직 ISO로 컴파일하지 않았어.';
    } finally {
      // Defer revocation until the browser has initiated the download.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  });
  copy.addEventListener('click', async () => {
    try {
      if (!navigator.clipboard || !window.isSecureContext)
        throw Error('보안 컨텍스트의 클립보드 기능이 없어. 아래 명령을 직접 복사해.');
      await navigator.clipboard.writeText(BUILD_COMMAND);
      status.textContent = 'PC에서 실행할 네이티브 ISO 빌드 명령을 복사했어. 웹에서 실행한 건 아니야.';
    } catch (error) {
      status.textContent = String(error?.message || error);
    }
  });
  refresh();
}
if (typeof document !== 'undefined') setupEditor(document);
