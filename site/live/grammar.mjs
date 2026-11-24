/* M2-UX6: show exact static grammar emitted by the real typed compiler.
 * Metadata only; no browser parser, compiler or eval of user-supplied source.
 */
export const SCHEMA_URL = '../htmlk-language.json';
export const MAX_SCHEMA_BYTES = 16384;
const NAME = /^[a-z][a-z0-9_-]{0,40}$/;

export function verifyGrammar(schema) {
  if (!schema || schema.schema_version !== 1 ||
      schema.dialect !== 'HTML Kernel Language' ||
      !schema.tags || typeof schema.tags !== 'object' ||
      Array.isArray(schema.tags)) return false;
  const entries = Object.entries(schema.tags);
  if (entries.length < 2 || entries.length > 64 ||
      !Object.hasOwn(schema.tags,'program') ||
      !Object.hasOwn(schema.tags,'main')) return false;
  for (const [tag, spec] of entries) {
    if (!NAME.test(tag) || !spec || typeof spec !== 'object') return false;
    for (const key of ['attributes','required_attributes','parents']) {
      const items = spec[key];
      if (!Array.isArray(items) || items.length > 32 ||
          items.some(item => typeof item !== 'string' || item.length > 50)) return false;
    }
  }
  return Array.isArray(schema.types) && schema.types.length < 32 &&
    typeof schema.limits === 'object';
}

export function matchingTags(schema, query) {
  if (!verifyGrammar(schema)) return [];
  const q = String(query).trim().toLowerCase().slice(0,64);
  return Object.entries(schema.tags).filter(([tag, spec]) =>
    !q || tag.includes(q) || spec.attributes.some(name => name.includes(q)) ||
    spec.parents.some(name => name.includes(q))
  ).sort(([a],[b]) => a.localeCompare(b));
}

export async function loadGrammar(fetchFn = fetch) {
  const response = await fetchFn(SCHEMA_URL, {cache:'no-store',credentials:'omit'});
  if (!response.ok) throw Error(`문법 자료를 불러오지 못했어 (HTTP ${response.status}).`);
  const source = await response.text();
  if (new TextEncoder().encode(source).byteLength > MAX_SCHEMA_BYTES)
    throw Error('문법 자료가 허용 크기(16KiB)를 초과했어.');
  const grammar = JSON.parse(source);
  if (!verifyGrammar(grammar)) throw Error('지원하지 않는 HTMLK 문법 자료 형식이야.');
  return grammar;
}

export function setupGrammar(doc = document, fetchFn = fetch) {
  const list = doc.getElementById('grammar-list');
  const input = doc.getElementById('grammar-search');
  const status = doc.getElementById('grammar-status');
  const details = doc.getElementById('grammar-guide');
  if (!list || !input || !status || !details) return;
  let schema = null;
  function render() {
    if (!schema) return;
    const tags = matchingTags(schema, input.value);
    const nodes = doc.createDocumentFragment();
    for (const [tag, metadata] of tags) {
      const entry = doc.createElement('li');
      const heading = doc.createElement('strong');
      heading.textContent = `<${tag}>`;
      const parents = doc.createElement('span');
      parents.textContent = '허용 위치: ' + metadata.parents.join(', ');
      const attributes = doc.createElement('span');
      attributes.textContent = '속성: ' + (metadata.attributes.join(', ') || '(없음)');
      const required = doc.createElement('span');
      required.textContent = '필수: ' + (metadata.required_attributes.join(', ') || '(없음)');
      entry.append(heading, parents, attributes, required);
      nodes.append(entry);
    }
    list.replaceChildren(nodes);
    status.textContent = `${tags.length} / ${Object.keys(schema.tags).length} 태그 · ` +
      '실제 Python 컴파일러에서 생성한 읽기 전용 문법표';
  }
  input.addEventListener('input', render);
  // Defer first fetch until a visitor deliberately opens this reference.
  // Native code execution, ROMFS and the editor never depend on metadata.
  details.addEventListener('toggle', async () => {
    if (!details.open || schema) return;
    status.textContent = '기존 컴파일러 문법 자료를 불러오는 중…';
    try {
      schema = await loadGrammar(fetchFn);
      render();
    } catch (error) {
      status.textContent = String(error?.message || error);
    }
  });
  status.textContent = '문법표를 펼치면 실제 컴파일러의 지원 태그를 불러와.';
}
if (typeof document !== 'undefined') setupGrammar(document);
