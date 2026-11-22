(() => {
  const tabs = Array.from(document.querySelectorAll('[data-tab]'));
  const panels = { html: document.getElementById('panel-html'), c: document.getElementById('panel-c') };
  function selectTab(name, focus = false) {
    for (const tab of tabs) {
      const active = tab.dataset.tab === name;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    }
    for (const [key, panel] of Object.entries(panels)) panel.hidden = key !== name;
  }
  tabs.forEach((tab, idx) => {
    tab.addEventListener('click', () => selectTab(tab.dataset.tab));
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (idx + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      selectTab(tabs[next].dataset.tab, true);
    });
  });
  document.getElementById('copy-code').addEventListener('click', async () => {
    const selected = tabs.find(t => t.getAttribute('aria-selected') === 'true')?.dataset.tab || 'html';
    const source = panels[selected].querySelector('code').textContent;
    const button = document.getElementById('copy-code');
    try {
      await navigator.clipboard.writeText(source);
      button.textContent = '복사 완료 ✓';
    } catch {
      button.textContent = '복사 불가 (HTTPS 필요)';
    }
    setTimeout(() => { button.textContent = '코드 복사'; }, 1800);
  });
})();
