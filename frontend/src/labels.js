// On a phone each table row is shown as a block, so every cell needs the name of its column
export function watchTables(root) {
  const label = () => root.querySelectorAll('table.data').forEach((table) => {
    const names = [...table.querySelectorAll('thead th')].map((th) => th.textContent.replace(/[\u2191\u2193]/g, '').trim());
    table.querySelectorAll('tbody tr').forEach((row) => [...row.children].forEach((cell, i) => {
      if (names[i] && cell.dataset.label !== names[i]) cell.dataset.label = names[i];
    }));
  });
  label();
  const watcher = new MutationObserver(label);
  watcher.observe(root, { childList: true, subtree: true });
  return () => watcher.disconnect();
}
