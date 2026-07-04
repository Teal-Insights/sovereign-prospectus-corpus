// Client script for document pages: MANIFEST-first text fetch with the
// version token, a click-gate for documents over 5 MB, drift notice, and
// visible error states. Zero SQL, zero URL assembly (lib modules own both).

import { PUBLIC_DATA_BASE_URL } from '../lib/config';
import { DRIFT_NOTICE, formatBytes, loadGateLabel } from '../lib/format';
import { loadManifest } from '../lib/snapshot-client';
import { textUrl } from '../lib/urls';
import { renderError, renderNotice, userMessageOf } from './dom';

const GATE_BYTES = 5_000_000;

interface TocEntry {
  level: number;
  title: string;
  offset: number;
  offset_utf16: number;
}

interface TextDoc {
  text: string;
  toc: TocEntry[];
}

let rawText: string | null = null;
window.__ewDoc = { getRawText: () => rawText };

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

async function loadText(container: HTMLElement, slug: string, bytes: number): Promise<void> {
  container.textContent = `Loading ${formatBytes(bytes)}...`;
  try {
    const manifest = await loadManifest(PUBLIC_DATA_BASE_URL);
    const stamped = document.body.dataset.buildGeneratedAt;
    if (stamped && manifest.generated_at !== stamped) {
      const notices = document.getElementById('ew-doc-notices');
      if (notices) renderNotice(notices, DRIFT_NOTICE);
    }

    const t0 = performance.now();
    const res = await fetch(textUrl(PUBLIC_DATA_BASE_URL, slug, manifest.generated_at));
    if (!res.ok) throw new Error(`text fetch HTTP ${res.status}`);
    const body = await res.text();
    const t1 = performance.now();
    const doc = JSON.parse(body) as TextDoc;
    const t2 = performance.now();

    rawText = doc.text;
    // Single container render, re-renderable in offset-addressed slices (S3).
    container.textContent = doc.text;
    const t3 = performance.now();
    renderToc(doc.toc ?? []);

    window.__ewDocMetrics = {
      fetchMs: t1 - t0,
      parseMs: t2 - t1,
      renderMs: t3 - t2,
      bytes: body.length,
    };
  } catch (e) {
    renderError(container, userMessageOf(e, 'Could not load the document text from the data host.'));
  }
}

function main(): void {
  const container = document.getElementById('ew-doc-text');
  if (!container) return;
  const slug = container.dataset.slug ?? '';
  const bytes = Number(container.dataset.textBytes ?? 0);

  if (bytes > GATE_BYTES) {
    container.textContent = '';
    const button = document.createElement('button');
    button.textContent = loadGateLabel(bytes);
    button.addEventListener('click', () => {
      button.remove();
      void loadText(container, slug, bytes);
    });
    container.appendChild(button);
  } else {
    void loadText(container, slug, bytes);
  }
}

main();
