# Contributing

Thanks for your interest in improving the Universal Android / ADB Diagnostic Toolkit.

## Development setup

```bash
git clone https://github.com/MrKhan025/Universal-Android-ADB-Diagnostic-Toolkit.git
cd Universal-Android-ADB-Diagnostic-Toolkit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"
```

## Running tests

```bash
pytest -v
# or without pytest:
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests mock ADB/Fastboot; no physical device is required.

## Code style

- Python 3.10+
- Prefer stdlib only (no runtime deps beyond the language)
- Keep package removal **safe by default** (`pm disable-user`, protected list, validation)
- Add unit tests for new parsers/helpers

## Adding OEM bloatware entries

Edit `src/universal_android_adb_toolkit/bloatware.py`:

1. Add the package name under the correct OEM key in `OEM_BLOATWARE`.
2. Never add anything that belongs in `PROTECTED_PACKAGES`.
3. Run tests and a dry-run against a real device when possible.

## Pull requests

1. Fork and branch from `main`.
2. Keep changes focused; update `CHANGELOG.md` and README when adding user-facing commands.
3. Ensure CI (Python 3.10–3.13) stays green.

## License

By contributing you agree that your contributions are licensed under the MIT License.
