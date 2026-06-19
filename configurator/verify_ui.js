const { chromium } = require('/usr/lib/node_modules/playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium',
    args: ['--allow-file-access-from-files'],
    headless: true
  });
  
  const page = await browser.newPage();
  
  // Track console errors
  const consoleErrors = [];
  page.on('pageerror', err => {
    console.error('Page error:', err);
    consoleErrors.push(err);
  });
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('Console error:', msg.text());
      consoleErrors.push(new Error(msg.text()));
    }
  });

  // Stub WebSocket to isolate UI tests and prevent external state contamination
  await page.addInitScript(() => {
    window.WebSocket = class MockWebSocket {
      constructor(url) {
        console.log('MockWebSocket created for:', url);
        this.url = url;
        this.readyState = 0; // CONNECTING
        setTimeout(() => {
          this.readyState = 1; // OPEN
          if (this.onopen) this.onopen();
        }, 10);
      }
      send(data) {
        console.log('MockWebSocket sent:', data);
      }
      close() {
        this.readyState = 3; // CLOSED
        if (this.onclose) this.onclose();
      }
    };
  });

  // Load the page
  const htmlPath = 'file://' + path.resolve(__dirname, 'index.html');
  console.log('Loading page:', htmlPath);
  await page.goto(htmlPath);
  
  // 1. Verify page has loaded and has no console errors
  if (consoleErrors.length > 0) {
    console.error('FAIL: Console errors detected on page load!');
    process.exit(1);
  }
  console.log('PASS: Page loaded with no console errors.');

  // Mock dialogs
  let dialogType = '';
  let dialogMessage = '';
  let promptValue = '';
  let confirmValue = true;
  let lastAlert = '';
  page.on('dialog', async dialog => {
    dialogType = dialog.type();
    dialogMessage = dialog.message();
    console.log(`Dialog triggered: [${dialogType}] "${dialogMessage}"`);
    if (dialogType === 'prompt') {
      await dialog.accept(promptValue);
    } else if (dialogType === 'confirm') {
      if (confirmValue) {
        await dialog.accept();
      } else {
        await dialog.dismiss();
      }
    } else if (dialogType === 'alert') {
      lastAlert = dialogMessage;
      await dialog.accept();
    }
  });

  // Helper to get active mode name from select element
  const getSelectedMode = async () => {
    return await page.$eval('#modeSelect', el => el.value);
  };

  // Helper to get modes list from select element
  const getModeOptions = async () => {
    return await page.$$eval('#modeSelect option', options => options.map(o => o.value));
  };

  // 2. Verify mode creation
  console.log('\n--- Testing Mode Creation ---');
  promptValue = 'GrugMode';
  const newModeBtn = await page.getByRole('button', { name: 'New Mode' });
  await newModeBtn.click();
  
  let selected = await getSelectedMode();
  let options = await getModeOptions();
  console.log('Selected mode after creation:', selected);
  console.log('Mode options after creation:', options);
  
  if (selected !== 'GrugMode' || !options.includes('GrugMode')) {
    console.error('FAIL: Mode "GrugMode" was not created/selected!');
    process.exit(1);
  }
  
  // Verify actions object on page contains GrugMode
  let hasGrugMode = await page.evaluate(() => typeof actions.modes['GrugMode'] !== 'undefined');
  if (!hasGrugMode) {
    console.error('FAIL: actions.modes["GrugMode"] not defined in page scope!');
    process.exit(1);
  }
  console.log('PASS: Mode creation verified.');

  // 3. Verify mode renaming
  console.log('\n--- Testing Mode Renaming ---');
  promptValue = 'SuperGrug';
  const renameBtn = await page.getByRole('button', { name: 'Rename' });
  await renameBtn.click();
  
  selected = await getSelectedMode();
  options = await getModeOptions();
  console.log('Selected mode after rename:', selected);
  console.log('Mode options after rename:', options);
  
  if (selected !== 'SuperGrug' || options.includes('GrugMode') || !options.includes('SuperGrug')) {
    console.error('FAIL: Mode rename failed!');
    process.exit(1);
  }
  
  let hasSuperGrug = await page.evaluate(() => typeof actions.modes['SuperGrug'] !== 'undefined');
  hasGrugMode = await page.evaluate(() => typeof actions.modes['GrugMode'] !== 'undefined');
  if (!hasSuperGrug || hasGrugMode) {
    console.error('FAIL: actions.modes mapping was not updated correctly after rename!');
    process.exit(1);
  }
  console.log('PASS: Mode renaming verified.');

  // 4. Verify mode deletion
  console.log('\n--- Testing Mode Deletion ---');
  confirmValue = true;
  const deleteBtn = await page.getByRole('button', { name: 'Delete' });
  await deleteBtn.click();
  
  selected = await getSelectedMode();
  options = await getModeOptions();
  console.log('Selected mode after delete:', selected);
  console.log('Mode options after delete:', options);
  
  if (selected !== 'Default' || options.includes('SuperGrug')) {
    console.error('FAIL: Mode deletion failed!');
    process.exit(1);
  }
  
  hasSuperGrug = await page.evaluate(() => typeof actions.modes['SuperGrug'] !== 'undefined');
  if (hasSuperGrug) {
    console.error('FAIL: actions.modes["SuperGrug"] still exists after delete!');
    process.exit(1);
  }
  console.log('PASS: Mode deletion verified.');

  // 5. Verify Default mode protections
  console.log('\n--- Testing Default Mode Protections ---');
  // Try to rename Default
  lastAlert = '';
  
  await renameBtn.click();
  if (lastAlert !== 'Cannot rename Default mode!') {
    console.error('FAIL: Default mode was allowed to be renamed or wrong alert shown:', lastAlert);
    process.exit(1);
  }
  console.log('PASS: Prevented renaming Default mode.');
  
  lastAlert = '';
  await deleteBtn.click();
  if (lastAlert !== 'Cannot delete Default mode!') {
    console.error('FAIL: Default mode was allowed to be deleted or wrong alert shown:', lastAlert);
    process.exit(1);
  }
  console.log('PASS: Prevented deleting Default mode.');

  // 6. Verify mode action dropdown logic in the UI
  console.log('\n--- Testing Mode Action Dropdown Logic ---');
  // First, create a new mode to target
  promptValue = 'DropdownTargetMode';
  await newModeBtn.click();
  
  // Go back to Default mode
  await page.selectOption('#modeSelect', 'Default');
  
  // Open callout for Left Button (co-left-btn)
  await page.click('#co-left-btn');
  
  // Find and click the 'Mode' action chip
  const modeChip = await page.locator('.action-chip', { hasText: 'Mode' });
  await modeChip.click();
  
  // Verify target mode dropdown is rendered and lists available modes
  const targetModeSelectExists = await page.locator('#sf-mode').count() > 0;
  if (!targetModeSelectExists) {
    console.error('FAIL: Target Mode select dropdown "#sf-mode" not found when "Mode" action selected!');
    process.exit(1);
  }
  
  const targetModes = await page.$$eval('#sf-mode option', options => options.map(o => o.value));
  console.log('Target modes listed in dropdown:', targetModes);
  if (!targetModes.includes('Default') || !targetModes.includes('DropdownTargetMode')) {
    console.error('FAIL: Target mode dropdown does not contain all modes!');
    process.exit(1);
  }
  
  // Select "DropdownTargetMode" and apply
  await page.selectOption('#sf-mode', 'DropdownTargetMode');
  const applyBtn = await page.locator('#sidePanel .btn-apply');
  await applyBtn.click();
  
  // Check if saved action in actions object is correct
  const savedAction = await page.evaluate(() => actions.modes['Default'].buttons['0:1'] || actions.modes['Default'].buttons['0']);
  console.log('Saved action on button 0 in Default mode:', savedAction);
  
  if (!savedAction || savedAction.action !== 'mode' || savedAction.value !== 'DropdownTargetMode') {
    console.error('FAIL: Saved action was not updated correctly!', savedAction);
    process.exit(1);
  }
  console.log('PASS: Mode action dropdown logic verified.');

  // 7. Validate saving/loading profiles functions correctly with the new nested structure
  console.log('\n--- Testing Save/Load Profiles ---');
  
  // Mock window.showOpenFilePicker
  await page.evaluate(() => {
    window.showOpenFilePicker = async () => {
      return [{
        getFile: async () => {
          return {
            name: 'test-nested-profile.json',
            text: async () => JSON.stringify({
              button_override: true,
              current_mode: "LoadedMode",
              modes: {
                "Default": {
                  buttons: { "0": {"action": "mouse_scroll", "direction": "down", "amount": 1} },
                  taps: {},
                  led: { effect: "breathing", color: "FF0000", brightness: 100 }
                },
                "LoadedMode": {
                  buttons: { "0": {"action": "key", "value": "ctrl+c"} },
                  taps: {
                    "top:1": {"action": "mode", "value": "Default"}
                  },
                  led: { effect: "solid", color: "00FF00", brightness: 255 }
                }
              },
              sensitivity: { "x_pos": 2.5 },
              inversion: { "x": true }
            })
          };
        }
      }];
    };
  });

  // Mock window.showSaveFilePicker
  await page.evaluate(() => {
    window.showSaveFilePicker = async () => {
      return {
        name: 'saved-nested-profile.json',
        createWritable: async () => {
          let content = '';
          return {
            write: async (data) => { content = data; },
            close: async () => { window.__saved_profile_content = JSON.parse(content); }
          };
        }
      };
    };
  });

  // Trigger Load Profile
  const loadBtn = await page.getByRole('button', { name: 'Load Profile' });
  await loadBtn.click();
  
  // Wait a small moment
  await page.waitForTimeout(100);
  
  // Verify that current_mode is LoadedMode and it is selected
  selected = await getSelectedMode();
  options = await getModeOptions();
  console.log('Selected mode after Profile Load:', selected);
  console.log('Mode options after Profile Load:', options);
  
  if (selected !== 'LoadedMode' || !options.includes('LoadedMode') || !options.includes('Default')) {
    console.error('FAIL: Profile loading did not populate modes and select active mode correctly!');
    process.exit(1);
  }
  
  // Verify that sensitivity and inversion from profile are applied to actions variable
  const localActions = await page.evaluate(() => actions);
  console.log('Loaded actions.sensitivity.x_pos:', localActions.sensitivity?.x_pos);
  console.log('Loaded actions.inversion.x:', localActions.inversion?.x);
  
  if (localActions.sensitivity?.x_pos !== 2.5 || localActions.inversion?.x !== true) {
    console.error('FAIL: Profile properties (sensitivity/inversion) were not loaded correctly!');
    process.exit(1);
  }
  
  // Modify something to test saving
  await page.evaluate(() => {
    actions.sensitivity.x_pos = 3.5;
  });
  
  // Trigger Save Profile
  const saveBtn = await page.getByRole('button', { name: 'Save Profile' });
  await saveBtn.click();
  await page.waitForTimeout(100);
  
  const savedProfile = await page.evaluate(() => window.__saved_profile_content);
  console.log('Saved profile contents:', JSON.stringify(savedProfile, null, 2));
  
  if (!savedProfile || savedProfile.sensitivity.x_pos !== 3.5 || !savedProfile.modes['LoadedMode']) {
    console.error('FAIL: Profile saving did not serialize the modified nested structure correctly!');
    process.exit(1);
  }
  console.log('PASS: Save/Load Profile with nested structure verified.');

  // Clean up
  await browser.close();
  
  if (consoleErrors.length > 0) {
    console.error('FAIL: Page encountered console errors during run!');
    process.exit(1);
  }
  
  console.log('\nALL UI TESTS PASSED SUCCESSFULLY!');
  process.exit(0);
})();
