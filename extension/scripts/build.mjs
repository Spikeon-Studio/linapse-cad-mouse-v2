#!/usr/bin/env node
import { cpSync, createWriteStream, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import archiver from 'archiver';
import sharp from 'sharp';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXT_DIR = resolve(__dirname, '..');
const ROOT = resolve(EXT_DIR, '..');
const VERSION = readFileSync(join(ROOT, 'VERSION'), 'utf8').trim();
const LOGO = join(ROOT, 'configurator', 'linapse-square-logo.png');

async function zipDirectory(sourceDir, zipPath) {
  await new Promise((resolvePromise, reject) => {
    const output = createWriteStream(zipPath);
    const archive = archiver('zip', { zlib: { level: 9 } });
    output.on('close', resolvePromise);
    archive.on('error', reject);
    archive.pipe(output);
    archive.directory(sourceDir, false);
    archive.finalize();
  });
}

async function buildVariant(name, manifestTemplatePath) {
  const outDir = join(EXT_DIR, 'dist', name);
  rmSync(outDir, { recursive: true, force: true });
  mkdirSync(join(outDir, 'icons'), { recursive: true });

  const manifest = JSON.parse(readFileSync(manifestTemplatePath, 'utf8'));
  manifest.version = VERSION;
  writeFileSync(join(outDir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  cpSync(join(EXT_DIR, 'src', 'content.js'), join(outDir, 'content.js'));

  for (const size of [16, 48, 128]) {
    await sharp(LOGO)
      .resize(size, size)
      .png()
      .toFile(join(outDir, 'icons', `icon${size}.png`));
  }

  const zipPath = join(EXT_DIR, 'dist', `linapse-browser-connector-${name}-${VERSION}.zip`);
  rmSync(zipPath, { force: true });
  await zipDirectory(outDir, zipPath);
  console.log(`built ${zipPath}`);
  return { outDir, zipPath };
}

mkdirSync(join(EXT_DIR, 'dist'), { recursive: true });
await buildVariant('chrome', join(EXT_DIR, 'manifest.chrome.json'));
await buildVariant('firefox', join(EXT_DIR, 'manifest.firefox.json'));

console.log(`extension build complete (${VERSION})`);
