# flexitac

Python interface for [FlexiTac](https://flexitac.github.io/) tactile sensors:
flash Arduino firmware, then read framed sensor data over serial.

Defaults target the standard FlexiTac 12x32 sensor (12 rows wired to mux
channels 4-15). Override `--rows`, `--cols`, and `--mux-offset` for variants.

## Install

```bash
# recommended
uv sync            # core deps only
uv sync --extra examples  # include matplotlib for the heatmap CLI
uv sync --extra dev       # dev tooling (ruff, mypy, pytest)

# or with pip
pip install flexitac
pip install 'flexitac[examples]'  # include matplotlib
```

## Reading frames

```python
from flexitac import FlexiTacSensor

with FlexiTacSensor("/dev/ttyUSB0") as sensor:  # rows=12, cols=32 by default
    for frame in sensor:
        print(frame.normalized.shape, frame.normalized.max())
```

`sensor.read()` returns a `FlexiTacFrame(seq, timestamp_s, raw, normalized)`.
The first read auto-calibrates by collecting `init_frames` (default 30) and
storing the per-pixel median as the baseline. Call `sensor.calibrate()` to
recalibrate.

## CLI tools

All CLI commands are installed as entry points:

```bash
flexitac-stream  --port /dev/ttyUSB0               # stream frames & print stats
flexitac-heatmap --port /dev/ttyUSB0               # live matplotlib heatmap
flexitac-flash                                      # flash firmware (auto-detects board)
flexitac-find-port                                  # identify sensor port by unplug

# with uv (no install needed)
uv run flexitac-stream  --port /dev/ttyUSB0
uv run flexitac-heatmap --port /dev/ttyUSB0
```

### `flexitac-stream`

Stream frames and print FPS / signal stats:

```bash
flexitac-stream --port /dev/ttyUSB0 --frames 30
```

```
frame=    10 fps=  85.3 raw_max=104 norm_max=0.000
frame=    20 fps=  87.1 raw_max=109 norm_max=0.123
```

What to check:

- **`fps`** stabilizes near your expected rate (~100+ fps for a 12x32 sensor
  at 2 Mbps). If it's 0 or you get `TimeoutError`, the firmware isn't sending
  framed data -- confirm `--rows`/`--cols`/`--baud` match what you flashed.
- **`raw_max`** is in `[0, 255]` and changes when you press the sensor.
  A flat 0 or flat 255 indicates a wiring issue, not a flashing issue.
- **`norm_max`** rises toward 1.0 under contact and stays near 0 at rest.

### `flexitac-heatmap`

Live heatmap visualization (requires `matplotlib` -- install with the `examples` extra):

```bash
flexitac-heatmap --port /dev/ttyUSB0
```

Press the sensor pad -- bright spots should track your touch.

### `flexitac-find-port`

Not sure which `/dev/tty*` your sensor is on? Run:

```bash
flexitac-find-port
```

It snapshots ports, asks you to unplug the sensor, then reports whichever port
disappeared.

### `flexitac-flash`

Requires [`arduino-cli`](https://arduino.github.io/arduino-cli/latest/installation/).
First-time setup:

```bash
brew install arduino-cli
# or use the upstream install script:
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# then install the Arduino AVR core
arduino-cli core update-index
arduino-cli core install arduino:avr  # AVR core for Uno/Nano/Mega/etc.
```

```bash
# auto-detects the port + FQBN if exactly one Arduino is plugged in
flexitac-flash

# override geometry / wiring for non-standard sensors
flexitac-flash --rows 16 --cols 32 --mux-offset 0

# if unable to autodetect, pass --port and --fqbn explicitly:
flexitac-flash --port /dev/ttyUSB0 --fqbn arduino:avr:uno
```

Defaults: `rows=12`, `cols=32`, `baud=2000000`, `mux-offset=4` (standard
FlexiTac 12x32 sensor wired to mux channels 4-15). The firmware is generated
from `flexitac/firmware/template.ino` by substituting `ROW_COUNT`,
`COLUMN_COUNT`, `BAUD_RATE`, and `MUX_CHANNEL_OFFSET`. To customize pin
assignments, edit the template directly.

## Wire protocol

Each frame: marker `0xAA 0x55` followed by `rows * cols` uint8 ADC samples,
streamed continuously at the configured baud rate.

## Development

```bash
uv sync --extra dev

make format         # ruff format + autofix
make static-checks  # ruff + mypy
make test           # pytest
```
