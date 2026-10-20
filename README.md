# Cassette

Cassette is a local, privacy-first Windows voice launcher. Press a hotkey, speak a short command, and it opens an app or file, runs a macro, or searches the web.

It uses local speech recognition (`faster-whisper`); audio stays in memory and is never uploaded or saved.

## Features

- Global configurable hotkey (default: `Ctrl+Alt+Space`)
- Small, always-on-top dot-matrix status orb
- Local Start menu app matching and Everything-powered file search
- Chrome/site searches, YAML macros, and local dictation history with weekly word counts
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

On first launch, Cassette creates editable runtime files in `%APPDATA%\Cassette\` and downloads the local Whisper model into `%LOCALAPPDATA%\Cassette\models\`.

## Configuration

Edit `%APPDATA%\Cassette\config.yaml`, then choose **Reload config** from the tray menu (or restart). Macros live in `%APPDATA%\Cassette\macros.yaml`.

## Build a distributable Windows app

```powershell
.\scripts\build.ps1
```

The packaged application is written to `release\Cassette\Cassette.exe`. The build embeds the supplied app mark as the Windows executable and tray icon.

## Project layout

```text
assets/                 Product icon source and Windows icon
config/                 First-run config templates
scripts/build.ps1       Reproducible Windows packaging script
src/voicelaunch/        Application source
tests/                  Unit tests for pure parsing/matching logic
```

## Privacy

Cassette transcribes locally. It does not save audio, send telemetry, create accounts, or call cloud APIs. The only network use is the one-time local-model download and URLs you explicitly request it to open. Transcriptions are saved locally only so the history panel and weekly statistics can work.

## License

[MIT](LICENSE)
