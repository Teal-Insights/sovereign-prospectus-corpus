// The only module that touches astro:env. Everything else takes the base URL
// as a parameter (keeps the virtual module out of the vitest import graph).
// Presence/https validation happens at build time in astro.config.mjs.

export {
  PUBLIC_DATA_BASE_URL,
  PUBLIC_EXTENSION_BASE_URL,
  PUBLIC_WASM_BASE_URL,
} from 'astro:env/client';
