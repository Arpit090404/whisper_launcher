# VoiceLaunch

VoiceLaunch is a local, privacy-first Windows voice launcher. Press a hotkey, speak a short command, and it opens an app or file, runs a macro, or searches the web.

It uses local speech recognition (`faster-whisper`); audio stays in memory and is never uploaded or saved.

## Features

- Global configurable hotkey (default: `Ctrl+Alt+Space`)
- Small, always-on-top dot-matrix status orb
- Local Start menu app matching and Everything-powered file search
- Chrome/site searches, YAML macros, and command history
- PySide6 UI with no focus stealing

## Requirements

- Windows 10 22H2 or Windows 11, x64
- Python 3.11–3.13 recommended (3.12 is the primary target)
- A microphone
- [Everything](https://www.voidtools.com/) and its `es.exe` CLI for fast file search (optional; a bounded fallback scan is included)

## Development setup

```powershell
git clone https://github.com/YOUR-USERNAME/voicelaunch.git
cd voicelaunch
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m voicelaunch
```

On first launch, VoiceLaunch creates editable runtime files in `%APPDATA%\VoiceLaunch\` and downloads the local Whisper model into `%LOCALAPPDATA%\VoiceLaunch\models\`.

## Configuration

Edit `%APPDATA%\VoiceLaunch\config.yaml`, then choose **Reload config** from the tray menu (or restart). Macros live in `%APPDATA%\VoiceLaunch\macros.yaml`.

## Build a distributable Windows app

```powershell
.\scripts\build.ps1
```

The packaged application is written to `release\VoiceLaunch\VoiceLaunch.exe`. The build embeds the supplied VoiceLaunch mark as the Windows executable and tray icon.

## Project layout

```text
assets/                 Product icon source and Windows icon
config/                 First-run config templates
scripts/build.ps1       Reproducible Windows packaging script
src/voicelaunch/        Application source
tests/                  Unit tests for pure parsing/matching logic
```

## Privacy

VoiceLaunch transcribes locally. It does not save audio, send telemetry, create accounts, or call cloud APIs. The only network use is the one-time local-model download and URLs you explicitly request it to open.

## License

[MIT](LICENSE)
