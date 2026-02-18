# flexitac

`flexitac` is a Python package for interacting with FlexiTac tactile sensors and flashing firmware via `arduino-cli`.
CLI output uses colorized logging (via `colorlog`) when available.

## Install

```bash
pip install flexitac
```

For development in this repo:

```bash
pip install -e '.[dev]'
```

## Runtime API

The runtime expects the binary framed protocol:
- frame marker: `0xAA 0x55`
- payload: `rows * cols` bytes

Example:

```python
from flexitac import FlexiTacSensor

with FlexiTacSensor(port="/dev/ttyUSB0", rows=16, cols=32) as sensor:
    frame = sensor.read_frame()
    print(frame.raw.shape)          # (16, 32)
    print(frame.normalized.max())
```

Streaming:

```python
from flexitac import FlexiTacSensor

sensor = FlexiTacSensor(port="/dev/ttyUSB0")
for frame in sensor.iter_frames(limit=10):
    print(frame.seq, frame.timestamp_s)
sensor.close()
```

## Flashing Firmware

The flash command generates a configured `.ino` sketch from a template and uploads it with `arduino-cli`.

### Prerequisite

Install `arduino-cli` and required board core(s). If a core is missing, `flexitac` prints the exact install command.

### Quick Start

```bash
python -m flexitac.flash --profile 16x32
```

The command attempts to auto-detect board + port, restricted to supported AVR targets by default.

### Helpful Flags

```bash
python -m flexitac.flash --list-profiles
python -m flexitac.flash --list-boards
python -m flexitac.flash --profile 16x16 --dry-run --verbose
python -m flexitac.flash --profile 16x32 --print-config
```

### Scan and Diagnose Board Detection

Use the dedicated scanner when auto-detection fails:

```bash
uv run python -m flexitac.scan --verbose
```

Or with the installed console script:

```bash
flexitac-scan --verbose
```

### Explicit Board/Port

```bash
python -m flexitac.flash --profile 16x32 --fqbn arduino:avr:uno --port /dev/ttyUSB0
```

### Programmatic Firmware Variable Overrides

Layering order:
1. profile defaults
2. first-class flags (`--rows`, `--cols`, `--baud`, pin flags)
3. repeated `--set NAME=VALUE`

Examples:

```bash
python -m flexitac.flash --profile 16x32 --rows 16 --cols 24 --baud 1000000
python -m flexitac.flash --profile 16x32 --set ROWS_PER_MUX=8 --set MUX_COUNT=2
```

By default, `--set` is allowlisted for safety. Use `--expert` to bypass restrictions.

### Emit Generated Sketch

```bash
python -m flexitac.flash --profile 16x32 --emit-sketch /tmp/flexitac_generated.ino --dry-run
```

This writes the exact rendered `.ino` used for compile/upload.

## Supported Defaults

Default flashing target allowlist:
- `arduino:avr:uno`
- `arduino:avr:nano`
- `arduino:avr:mega`
- `arduino:avr:leonardo`
- `arduino:avr:micro`

Use `--expert` to target non-default boards.
