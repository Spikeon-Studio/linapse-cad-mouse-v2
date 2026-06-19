const { app, BrowserWindow, dialog } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');

// Configure console logging for auto-updater
autoUpdater.logger = console;

function createWindow() {
  const win = new BrowserWindow({
    width: 1020,
    height: 820,
    title: "Linapse Configurator",
    icon: path.join(__dirname, 'linapse-square-logo.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  win.loadFile(path.join(__dirname, 'index.html'));
  win.setMenuBarVisibility(false);
}

app.whenReady().then(() => {
  createWindow();

  // Check for updates and notify
  autoUpdater.checkForUpdatesAndNotify();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Update event handlers
autoUpdater.on('checking-for-update', () => {
  console.log('[updater] Checking for update...');
});

autoUpdater.on('update-available', (info) => {
  console.log('[updater] Update available:', info.version);
});

autoUpdater.on('update-not-available', (info) => {
  console.log('[updater] Update not available.');
});

autoUpdater.on('error', (err) => {
  console.error('[updater] Error in auto-updater:', err);
});

autoUpdater.on('download-progress', (progressObj) => {
  console.log(`[updater] Download progress: ${progressObj.percent}%`);
});

autoUpdater.on('update-downloaded', (info) => {
  console.log('[updater] Update downloaded.');
  dialog.showMessageBox({
    type: 'info',
    title: 'Update Ready',
    message: `Version ${info.version} has been downloaded. Restart the application to apply the update.`,
    buttons: ['Restart Now', 'Later']
  }).then((result) => {
    if (result.response === 0) {
      autoUpdater.quitAndInstall();
    }
  });
});
