// Shared DOM helpers for the client scripts. Every data/wasm failure mode
// must end in a visible error state, never a blank region.

export function renderError(el: HTMLElement, message: string): void {
  el.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'ew-error';
  // WCAG 4.1.3: dynamically injected errors are status messages
  div.setAttribute('role', 'alert');
  div.textContent = message;
  el.appendChild(div);
}

export function renderNotice(el: HTMLElement, message: string): void {
  const div = document.createElement('div');
  div.className = 'ew-notice';
  div.setAttribute('role', 'status');
  div.textContent = message;
  el.appendChild(div);
}

export function userMessageOf(e: unknown, fallback: string): string {
  if (e && typeof e === 'object' && 'userMessage' in e) {
    return String((e as { userMessage: unknown }).userMessage);
  }
  return fallback;
}
