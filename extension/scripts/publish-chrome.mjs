#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import chromeWebstoreUpload from 'chrome-webstore-upload';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXT_DIR = resolve(__dirname, '..');
const ROOT = resolve(EXT_DIR, '..');
const VERSION = readFileSync(join(ROOT, 'VERSION'), 'utf8').trim();
const meta = JSON.parse(readFileSync(join(EXT_DIR, 'extension-id.json'), 'utf8'));

const clientId = process.env.CHROME_CLIENT_ID;
const clientSecret = process.env.CHROME_CLIENT_SECRET;
const refreshToken = process.env.CHROME_REFRESH_TOKEN;
const extensionId = process.env.CHROME_EXTENSION_ID || meta.chrome_extension_id;

for (const [name, value] of Object.entries({
  CHROME_CLIENT_ID: clientId,
  CHROME_CLIENT_SECRET: clientSecret,
  CHROME_REFRESH_TOKEN: refreshToken,
})) {
  if (!value) {
    console.error(`Missing required secret/env: ${name}`);
    process.exit(1);
  }
}

const zipPath = join(EXT_DIR, 'dist', `linapse-browser-connector-chrome-${VERSION}.zip`);
const zipBuffer = readFileSync(zipPath);

const store = chromeWebstoreUpload({
  extensionId,
  clientId,
  clientSecret,
  refreshToken,
});

console.log(`Uploading ${zipPath} to Chrome Web Store (${extensionId})...`);
await store.uploadExisting(zipBuffer);
console.log('Upload complete. Publishing to trusted testers/default channel...');
await store.publish();
console.log('Chrome Web Store publish complete.');
