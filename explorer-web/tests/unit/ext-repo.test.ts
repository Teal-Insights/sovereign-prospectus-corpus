import { afterEach, expect, it, vi } from 'vitest';

import { applyExtensionRepository } from '../../src/lib/ext-repo';

afterEach(() => {
  vi.restoreAllMocks();
});

it('is a no-op when the base is unset (default CDN autoload path, unregressed)', async () => {
  const run = vi.fn(async () => undefined);
  await applyExtensionRepository(undefined, run);
  await applyExtensionRepository('', run);
  expect(run).not.toHaveBeenCalled();
});

it('installs and loads parquet from the base when set (primary path)', async () => {
  const run = vi.fn(async (_sql: string) => undefined);
  await applyExtensionRepository('https://data.example.org/ext', run);
  expect(run.mock.calls.map((c) => c[0])).toEqual([
    "INSTALL parquet FROM 'https://data.example.org/ext'",
    'LOAD parquet',
  ]);
});

it("escapes a single quote in the base so it cannot break out of the SQL string", async () => {
  const run = vi.fn(async (_sql: string) => undefined);
  await applyExtensionRepository("https://data.example.org/o'ops", run);
  expect(run.mock.calls[0][0]).toBe("INSTALL parquet FROM 'https://data.example.org/o''ops'");
});

it('falls back to custom_extension_repository (not the CDN) when INSTALL throws, and warns', async () => {
  const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  const run = vi.fn(async (sql: string) => {
    if (sql.startsWith('INSTALL')) throw new Error('INSTALL unsupported');
    return undefined;
  });
  await applyExtensionRepository('https://data.example.org/ext', run);
  const calls = run.mock.calls.map((c) => c[0]);
  expect(calls).toContain("SET custom_extension_repository='https://data.example.org/ext'");
  // The fallback still targets the mirror base, never extensions.duckdb.org.
  expect(calls.join('\n')).not.toContain('extensions.duckdb.org');
  expect(warn).toHaveBeenCalledOnce();
});

it('falls back when LOAD throws after a successful INSTALL', async () => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  const run = vi.fn(async (sql: string) => {
    if (sql === 'LOAD parquet') throw new Error('LOAD failed');
    return undefined;
  });
  await applyExtensionRepository('https://data.example.org/ext', run);
  expect(run.mock.calls.map((c) => c[0])).toContain(
    "SET custom_extension_repository='https://data.example.org/ext'"
  );
});
