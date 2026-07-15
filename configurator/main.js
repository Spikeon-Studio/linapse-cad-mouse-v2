const { app, BrowserWindow, Tray, Menu, nativeImage, dialog } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');

// Configure console logging for auto-updater
autoUpdater.logger = console;

let mainWindow = null;
let tray = null;
let isQuitting = false;
let updaterQuitPending = false;

// Single instance: focus the existing window instead of launching a duplicate.
// exit() (not quit()) so the losing instance never reaches whenReady and
// flashes a duplicate window/tray before dying.
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.exit(0);
} else {
  app.on('second-instance', () => {
    showWindow();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1020,
    height: 820,
    title: "Linapse Configurator",
    icon: path.join(__dirname, 'linapse-square-logo.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.setMenuBarVisibility(false);

  // Close-to-tray: hide instead of closing unless the app is really quitting
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Windows: shutdown/logout does not emit before-quit, only session-end
  mainWindow.on('session-end', () => {
    isQuitting = true;
  });
}

function showWindow() {
  if (mainWindow === null || mainWindow.isDestroyed()) {
    createWindow();
    return;
  }
  mainWindow.show();
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();
}

function createTray() {
  // Native tray sizes: 16px on Windows, 22pt on macOS menu bar, 24px appindicator
  const size = process.platform === 'win32' ? 16 : process.platform === 'darwin' ? 22 : 24;
  const trayIcon = nativeImage
    .createFromPath(path.join(__dirname, 'linapse-square-logo-128.png'))
    .resize({ width: size, height: size });

  tray = new Tray(trayIcon);
  tray.setToolTip('Linapse Configurator');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open Configurator', click: () => showWindow() },
    { type: 'separator' },
    {
      label: 'Quit Linapse Configurator',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]));

  // Windows/macOS: clicking the tray icon shows the window.
  // Linux appindicator only shows the menu on click; this is a no-op there.
  tray.on('click', () => showWindow());
}

app.whenReady().then(() => {
  createWindow();
  createTray();

  // Check for updates and notify
  autoUpdater.checkForUpdatesAndNotify();
});

// macOS: clicking the dock icon restores the hidden window
app.on('activate', () => {
  showWindow();
});

// Mark OS-initiated quits (logout, Cmd+Q) so the close interception doesn't block them
app.on('before-quit', () => {
  isQuitting = true;
});

app.on('window-all-closed', () => {
  // The tray keeps the app alive; only quit when a real quit is in progress
  if (isQuitting && process.platform !== 'darwin') app.quit();
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
  // A failed quitAndInstall leaves the app running; don't let the stuck
  // flag silently disable close-to-tray for the rest of the session
  if (updaterQuitPending) {
    updaterQuitPending = false;
    isQuitting = false;
  }
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
      isQuitting = true;
      updaterQuitPending = true;
      autoUpdater.quitAndInstall();
    }
  });
});
