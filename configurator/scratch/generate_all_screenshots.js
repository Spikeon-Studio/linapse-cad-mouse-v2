const { chromium } = require('/usr/lib/node_modules/playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium',
    args: ['--allow-file-access-from-files'],
    headless: true
  });
  
  const context = await browser.newContext({
    deviceScaleFactor: 2
  });
  
  const page = await context.newPage();
  
  // Stub WebSocket to prevent connections and mock connection
  await page.addInitScript(() => {
    window.WebSocket = class MockWebSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 1; // OPEN
      }
      send(data) {}
      close() {}
    };
  });

  const htmlPath = 'file://' + path.resolve(__dirname, '../index.html');
  console.log('Loading page:', htmlPath);
  await page.goto(htmlPath);

  // Set connected status to show green/connected dot
  await page.evaluate(() => {
    setConnected(true);
  });
  
  // Helper to wait
  const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));
  await wait(500);

  const imagesDir = path.resolve(__dirname, '../../docs/images');

  // Let's first capture wide layouts (Viewport 1920x1014 -> 3840x2028 image at scale 2)
  console.log('Capturing wide layout screenshots...');
  await page.setViewportSize({ width: 1920, height: 1014 });

  // 1. Wide Customize Tab (configurator-customize.png)
  await page.evaluate(() => {
    // Switch to Customize tab
    switchTab('customize', document.querySelectorAll('.tab')[0]);
    // Close side panel just in case
    document.getElementById('sidePanel').classList.remove('open');
  });
  await wait(500);
  await page.screenshot({ path: path.join(imagesDir, 'configurator-customize.png') });
  console.log('Captured configurator-customize.png');

  // 2. Wide Lighting Tab (configurator-lighting.png)
  await page.evaluate(() => {
    switchTab('lighting', document.querySelectorAll('.tab')[1]);
  });
  await wait(500);
  await page.screenshot({ path: path.join(imagesDir, 'configurator-lighting.png') });
  console.log('Captured configurator-lighting.png');

  // 3. Wide Sensitivity Tab (configurator-sensitivity.png)
  await page.evaluate(() => {
    switchTab('sensitivity', document.querySelectorAll('.tab')[2]);
    switchSensTab('general', document.querySelectorAll('.sens-tab')[0]);
  });
  await wait(500);
  await page.screenshot({ path: path.join(imagesDir, 'configurator-sensitivity.png') });
  console.log('Captured configurator-sensitivity.png');

  // 4. Wide Sensitivity Axes Tab (configurator-sensitivity-axes.png)
  await page.evaluate(() => {
    switchSensTab('axes', document.querySelectorAll('.sens-tab')[1]);
  });
  await wait(500);
  await page.screenshot({ path: path.join(imagesDir, 'configurator-sensitivity-axes.png') });
  console.log('Captured configurator-sensitivity-axes.png');

  // 5. Wide Sensitivity Wizard Overlay (configurator-sensitivity-wizard.png)
  await page.evaluate(() => {
    startCalibrationWizard();
  });
  await wait(500);
  await page.screenshot({ path: path.join(imagesDir, 'configurator-sensitivity-wizard.png') });
  console.log('Captured configurator-sensitivity-wizard.png');

  // Cancel wizard
  await page.evaluate(() => {
    cancelCalibrationWizard();
  });
  await wait(100);

  // Now capture narrow layouts (Viewport 1046x1014 -> 2092x2028 image at scale 2)
  console.log('Capturing narrow layout screenshots...');
  await page.setViewportSize({ width: 1046, height: 1014 });

  // 6. Active Mode Selector Header (configurator-modes.png)
  // Let's capture the whole window with customize tab active and side panel closed
  await page.evaluate(() => {
    switchTab('customize', document.querySelectorAll('.tab')[0]);
    document.getElementById('sidePanel').classList.remove('open');
  });
  await wait(500);
  await page.screenshot({ path: path.join(imagesDir, 'configurator-modes.png') });
  console.log('Captured configurator-modes.png');

  // Helper to open side panel with specific callout and action chip
  const setupSidePanel = async (calloutId, actionChipLabel) => {
    await page.evaluate((cid) => {
      // Close side panel first to reset
      document.getElementById('sidePanel').classList.remove('open');
      // Click callout
      document.getElementById(cid).click();
    }, calloutId);
    await wait(300);
    // Click action chip by label
    await page.locator(`.action-chip`, { hasText: actionChipLabel }).first().click();
    await wait(300);
  };

  // 7. Key Combo Configuration (configurator-customize-key.png)
  await setupSidePanel('co-left-btn', 'Key Combo');
  await page.screenshot({ path: path.join(imagesDir, 'configurator-customize-key.png') });
  console.log('Captured configurator-customize-key.png');

  // 8. Scroll Configuration (configurator-customize-scroll.png)
  await setupSidePanel('co-left-btn', 'Scroll');
  await page.screenshot({ path: path.join(imagesDir, 'configurator-customize-scroll.png') });
  console.log('Captured configurator-customize-scroll.png');

  // 9. Tap & Mouse Configuration (configurator-customize-tap.png)
  await setupSidePanel('co-top', 'Mouse Click');
  await page.screenshot({ path: path.join(imagesDir, 'configurator-customize-tap.png') });
  console.log('Captured configurator-customize-tap.png');

  // 10. Macro Configuration (configurator-customize-macro.png)
  await setupSidePanel('co-left-btn', 'Macro');
  await page.screenshot({ path: path.join(imagesDir, 'configurator-customize-macro.png') });
  console.log('Captured configurator-customize-macro.png');

  await browser.close();
  console.log('Done generating all screenshots!');
})();
