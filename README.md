# Windows Notifier Suite

Two companion PySide6 desktop applications for managing notification modules on Windows.

## Projects
- `windows_notifier_core`: Runtime that surfaces notification modules to end users.
- `windows_notifier_builder`: Authoring tool to create and preview modules.

Both applications share schema and data definitions under `shared/`.

## Repository Layout
- `windows_notifier_core/`: Core runtime package and `main.py` entry point.
- `windows_notifier_builder/`: Builder package and `builder_main.py` entry point.
- `core/`: Shared runtime helpers (module IDs, registry store, loader, idle monitor, etc.).
- `shared/`: Manifest schema + module definition shared between apps.
- `Modules/`: Example modules, including `sample_module/manifest.json`.
- `packaging/`: PyInstaller spec files for distribution builds.
- `tests/`: Pytest coverage for shared/core components.
- `assets/`: Place supporting assets such as PDF.js (optional).

## Requirements
```powershell
python -m venv .venv
.venv\Scripts\Activate
pip install -r requirements.txt
```

## Running the Applications
```powershell
# Core runtime (displays notifications)
python -m windows_notifier_core.main

# Module builder GUI
python -m windows_notifier_builder.builder_main
```

## Packaging with PyInstaller
```powershell
# Build the core runtime (one-folder, auto-prunes Qt bloat)
.\scripts\build_core.ps1

# Build the builder application (one-folder, auto-prunes Qt bloat)
.\scripts\build_builder.ps1
```

Output folders appear under `dist/windows_notifier_core/` and `dist/windows_notifier_builder/`. Copy the `Modules/` directory (or deploy via management tooling) alongside the core runtime distribution.

## Module Authoring Workflow
1. Launch the builder via `python -m windows_notifier_builder.builder_main`.
2. Enter Title, Message (max 240 characters), Category (optional), and optional expiry date.
3. Choose media type:
   - File: select PDF/image/video to bundle with the module.
   - URL: provide an HTTPS URL that the core app opens in the default browser.
   - None: leave empty for text-only notifications.
4. Optionally enable *Schedule first display* to delay the initial notification until a specific UTC date/time.
5. Optionally enable *Play Windows notification sound* to use the built-in sound cue when the module appears.
6. Review the live preview card at the bottom of the form to confirm title, message, and action icons match your expectations.
7. Click **Save Module** to persist under `Modules/<timestamp-title>/`. The builder displays the generated module ID on save.
8. Need a script-driven notification? Select **Save Conditional…** to attach a PowerShell condition script (details below).
9. Want to deploy via Intune? Click **Create Intune Package**, choose one or more saved modules, and the builder will wrap them (plus `install_module_intune.ps1`) into an `.intunewin` package using Microsoft’s `IntuneWinAppUtil.exe`. When configuring the Win32 app in Intune, use an install command like `powershell.exe -ExecutionPolicy Bypass -File install_module_intune.ps1`.

Modules are ready to copy into the core runtime's `Modules/` directory (local or deployed via Intune).

### Conditional Notifications

Some campaigns should only display once a device meets a prerequisite. Conditional modules let you bundle an admin-provided PowerShell script that returns `1` when the notification should fire or `0` when it should wait:

1. Fill out the primary builder form (title, message, media, icon, etc.).
2. Click **Save Conditional…** to open the condition dialog.
3. Browse for the `.ps1` script and choose the recheck interval (defaults to 60 minutes if omitted).
4. Use **Test Script** to run it immediately and review stdout/stderr plus the exit code.
5. Click **Use Script** to finalize the module.

The builder copies the script into the module folder and writes `type: "conditional"` plus the interval into the manifest. The core runtime executes the script at the chosen interval (with a timeout just under the 5-minute scan cadence). Exit code `1` moves the module into the normal lifecycle (popup, actions, reminders). Exit code `0` keeps it pending for the next run. Any execution error is logged, written to the registry, and the module folder is removed so it won't break subsequent scans.

### Deploying Modules with Intune

The PowerShell helper `packaging/install_module.ps1` copies a module folder to the runtime directory and prepares the corresponding registry entry. Example usage when packaging with Intune:

```powershell
.\packaging\install_module.ps1 -ModuleSource .\Modules\20250101235959-security-tip
```

By default the script copies into `%LOCALAPPDATA%\Windows Notifier\Modules`. Override the destination with the `-ModulesRoot` parameter if needed.

### Example Module
- Located at `Modules/sample_module/manifest.json`.
- Demonstrates required fields and bundled media (`poster.png`) for a simple notification.

## Core Runtime Lifecycle
1. On startup the core app scans `Modules/` and loads each manifest.
   - The tray process refreshes the module list every 5 minutes (300 seconds) so newly deployed content is picked up automatically without thrashing the disk. Use the tray icon’s **Refresh Now** command any time you want to force a scan outside that cycle.
2. Modules already marked `Completed` or `Expired` in the registry are skipped and their folders removed.
3. Scheduled modules wait until their `schedule` time before appearing (if the time has already passed, they surface immediately while the status remains Pending).
4. Notifications appear in the bottom-right corner. Clicking the popup reveals three actions rendered directly on the toast:
   - **Show me how**: Opens the associated media (PDF/video/image/etc.).
   - **I understand**: Marks the module as completed, removes the folder, and moves on.
   - **Remind me later**: Defers the reminder until the system has been idle for 10 minutes.
5. Activity is logged for operational visibility via the app-wide logger.
6. Conditional modules execute their bundled PowerShell scripts at the configured interval. Exit code `1` promotes the module into the queue, `0` keeps it pending for the next cycle, and any other result logs an error, records it in the registry, and removes the module to keep scans healthy.

The runtime exposes a tray icon with **Refresh Now** (manual scan) and **Exit** options. Deploy the executable via Intune and register a logon task or run key so the application launches when users sign in.

## Core Management & Telemetry

### Registry-based settings
Device administrators can steer the runtime at `HKCU\Software\WindowsNotifier\Core` (created by the installer). Settings are polled every ~15 seconds so changes apply without restarting:

| Value name | Type | Default | Effect |
|------------|------|---------|--------|
| `IsEnabled` | `REG_DWORD` (0/1) | `1` | Turns the core on/off. When `0`, scans stop, notifications hide, and the process waits silently until re-enabled. |
| `PollingIntervalSeconds` | `REG_DWORD` | `300` | Controls how often the module directory is scanned (clamped to 60–3600 seconds). |
| `ShowTrayIcon` | `REG_DWORD` (0/1) | `1` | Toggles the tray icon visibility without stopping the background worker. |
| `SoundEnabled` | `REG_DWORD` (0/1) | `1` | Enables/disables playback of the Windows notification sound even if the module requests it. |
| `AutoDeleteModules` | `REG_DWORD` (0/1) | `1` | When `0`, module folders remain on disk after users click **I understand**. |

Add more keys of the same pattern as new controls become available—the core will fall back to defaults if values are missing or invalid.

### Persistent logging
All runtime diagnostics now flow into `%LOCALAPPDATA%\Windows Notifier\Core\core.log` with automatic rotation (five 10‑MB files retained). Use these logs to trace module ingestion, registry changes, or crash-recovery events without requiring extra tooling.

## Intune Deployment Workflow
1. Package the core runtime using `pyinstaller packaging/core.spec` and deploy the resulting folder to target devices via Intune.
2. Provide new or updated module folders (e.g., through additional Intune deployments or file sync) into the runtime's `Modules/` directory.
3. The core app automatically ingests, displays, and manages module lifecycles—tracking completion in the user registry.
4. Updated modules can be redistributed; completed modules are removed automatically once acknowledged.

Need to re-create the scheduled task later? Run `{app}\register_core_task.ps1` (installed beside the executable) to register or remove the logon task outside the installer. When executing as SYSTEM (e.g., via Intune), the script automatically targets the currently signed-in user; pass `-TargetUser DOMAIN\User` if you need to override the detection.

## Contributing & Testing
Run the existing test suite with:
```powershell
$env:PYTHONPATH='.'
pytest
```

Add new tests under `tests/` when expanding functionality.
