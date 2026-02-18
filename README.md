# flexitac

`flexitac` is a Python package for interacting with FlexiTac tactile sensors and flashing firmware via `arduino-cli`.
CLI output uses colorized logging (via `colorlogging`) when available.

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

## Examples

The repo includes runnable examples in `/examples`.

Install visualization extras if needed:

```bash
pip install "flexitac[examples]"
```

### 1) Stream frames + print metrics

```bash
python examples/stream_frames.py --port /dev/ttyUSB0 --rows 16 --cols 32
```

### 2) Live heatmap visualization

```bash
python examples/visualize_heatmap.py --port /dev/ttyUSB0 --rows 16 --cols 32
```

Both scripts accept `--help` for full argument lists.

## Flashing Firmware

The flash command generates a configured `.ino` sketch from a template and uploads it with `arduino-cli`.
CLI implementation modules live in `/flexitac/scripts` (with backward-compatible shims at `flexitac.flash` and `flexitac.scan`).

### Prerequisite

Install `arduino-cli` and required board core(s). If a core is missing, `flexitac` prints the exact install command.

#### First-time `arduino-cli` setup

1. Install `arduino-cli` (official options: Homebrew or install script):  
   https://arduino.github.io/arduino-cli/latest/installation/

   Example via Homebrew (macOS/Linux):

   ```bash
   brew update
   brew install arduino-cli
   ```

2. Confirm it is installed:

   ```bash
   arduino-cli version
   ```

3. Initialize/update core index:

   ```bash
   arduino-cli core update-index
   ```

4. Install the default AVR core used by FlexiTac profiles:

   ```bash
   arduino-cli core install arduino:avr
   ```

5. Verify core installation and board visibility:

   ```bash
   arduino-cli core list
   arduino-cli board list
   uv run python -m flexitac.scan --verbose
   ```

If `arduino-cli board list` shows ports as `Unknown`, that usually means board cores are missing or board detection failed. You can still flash by passing explicit `--port` and `--fqbn`.

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
