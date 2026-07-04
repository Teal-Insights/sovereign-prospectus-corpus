// Client script for document pages: MANIFEST-first text fetch with the
// version token, a click-gate for documents over 5 MB, drift notice, and
// visible error states. Zero SQL, zero raw fetch, zero URL assembly (the
// lib modules own all of it).

import { PUBLIC_DATA_BASE_URL } from '../lib/config';
import { DRIFT_NOTICE, formatBytes, loadGateLabel } from '../lib/format';
import { fetchDocText, loadManifest, type Manifest, type TocEntry } from '../lib/snapshot-client';
import { renderError, renderNotice, userMessageOf } from './dom';

const GATE_BYTES = 5_000_000;

let rawText: string | null = null;
window.__ewDoc = { getRawText: () => rawText };

// One manifest read per page view, shared by the drift check and text load.
let manifestPromise: Promise<Manifest> | null = null;
function getManifest(): Promise<Manifest> {
  manifestPromise ??= loadManifest(PUBLIC_DATA_BASE_URL);
  return manifestPromise;
}

async function driftCheck(): Promise<void> {
  try {
    const manifest = await getManifest();
    const stamped = document.body.dataset.buildGeneratedAt;
    if (stamped && manifest.generated_at !== stamped) {
      const notices = document.getElementById('ew-doc-notices');
      if (notices) renderNotice(notices, DRIFT_NOTICE);
    }
  } catch {
    // The drift check is advisory; text loading reports manifest errors.
  }
}

function renderToc(entries: TocEntry[]): void {
  const ol = document.getElementById('ew-doc-toc');
  if (!ol) return;
  if (!entries.length) {
    ol.textContent = ol.dataset.emptyLabel ?? '';
    return;
  }
  for (const entry of entries) {
    const li = document.createElement('li');
    li.textContent = entry.title;
    li.style.marginLeft = `${Math.max(0, entry.level - 2)}rem`;
    ol.appendChild(li);
  }
}

function renderGateButton(container: HTMLElement, slug: string, bytes: number): void {
  container.textContent = '';
  const button = document.createElement('button');
  button.textContent = loadGateLabel(bytes);
  button.addEventListener('click', () => {
    button.remove();
    void loadText(container, slug, bytes);
  });
  container.appendChild(button);
}

async function loadText(container: HTMLElement, slug: string, bytes: number): Promise<void> {
  container.textContent = `Loading ${formatBytes(bytes)}...`;
  try {
    const manifest = await getManifest();
    const result = await fetchDocText(PUBLIC_DATA_BASE_URL, slug, manifest.generated_at);

    rawText = result.doc.text;
    // Single container render, re-renderable in offset-addressed slices (S3).
    const t0 = performance.now();
    container.textContent = result.doc.text;
    const renderMs = performance.now() - t0;
    renderToc(result.doc.toc ?? []);

    window.__ewDocMetrics = {
      fetchMs: result.fetchMs,
      parseMs: result.parseMs,
      renderMs,
      stringLength: result.stringLength,
    };
  } catch (e) {
    renderError(container, userMessageOf(e, 'Could not load the document text from the data host.'));
    if (bytes > GATE_BYTES) {
      // Leave a retry affordance; a transient failure on a 29 MB document
      // must not require a full page reload.
      const retry = document.createElement('p');
      container.appendChild(retry);
      renderGateButton(retry, slug, bytes);
    }
  }
}

function main(): void {
  void driftCheck();
  const container = document.getElementById('ew-doc-text');
  if (!container) return; // has_text=false pages: drift check only
  const slug = container.dataset.slug ?? '';
  const bytes = Number(container.dataset.textBytes ?? 0);

  if (bytes > GATE_BYTES) {
    renderGateButton(container, slug, bytes);
  } else {
    void loadText(container, slug, bytes);
  }
}

main();
