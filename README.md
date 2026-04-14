# flexitac

Python interface for [FlexiTac](https://flexitac.github.io/) tactile sensors:
flash Arduino firmware, then read framed sensor data over serial.

Defaults target the standard FlexiTac 12×32 sensor (12 rows wired to mux
channels 4-15). Override `--rows`, `--cols`, and `--mux-offset` for variants.

## Install

```bash
uv sync --extra dev
# or: pip install -e '.[dev]'
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

Examples:

```bash
python examples/stream_frames.py --port /dev/ttyUSB0
python examples/visualize_heatmap.py --port /dev/ttyUSB0   # needs matplotlib
```

## Finding the port

Not sure which `/dev/tty*` your sensor is on? Run:

```bash
flexitac-find-port
```

It snapshots ports, asks you to unplug the sensor, then reports whichever port
disappeared.

## Flashing firmware

Requires [`arduino-cli`](https://arduino.github.io/arduino-cli/latest/installation/).
First-time setup:

```bash
brew install arduino-cli              # or use the upstream install script
arduino-cli core update-index
arduino-cli core install arduino:avr  # AVR core for Uno/Nano/Mega/etc.
```

```bash
# auto-detects the port + FQBN if exactly one Arduino is plugged in
flexitac-flash

# override geometry / wiring for non-standard sensors
flexitac-flash --rows 16 --cols 32 --mux-offset 0
```

Defaults: `rows=12`, `cols=32`, `baud=2000000`, `mux-offset=4` (standard
FlexiTac 12×32 sensor wired to mux channels 4-15). The firmware is generated
from `flexitac/firmware/template.ino` by substituting `ROW_COUNT`,
`COLUMN_COUNT`, `BAUD_RATE`, and `MUX_CHANNEL_OFFSET`. To customize pin
assignments, edit the template directly.

## Verify the flash worked

After flashing, stream a few frames and confirm sane values:

```bash
python examples/stream_frames.py --port /dev/ttyUSB0 --frames 30
```

You should see steady output like:

```
frame=    10 fps=  85.3 raw_max=104 norm_max=0.000
frame=    20 fps=  87.1 raw_max=109 norm_max=0.123
```

What to check:

- **`fps`** stabilizes near your expected rate (~100+ fps for a 12×32 sensor
  at 2 Mbps). If it's 0 or you get `TimeoutError`, the firmware isn't sending
  framed data — confirm `--rows`/`--cols`/`--baud` match what you flashed.
- **`raw_max`** is in `[0, 255]` and changes when you press the sensor.
  A flat 0 or flat 255 indicates a wiring issue, not a flashing issue.
- **`norm_max`** rises toward 1.0 under contact and stays near 0 at rest.

For a visual check:

```bash
python examples/visualize_heatmap.py --port /dev/ttyUSB0
```

Press the sensor pad — bright spots should track your touch.

## Wire protocol

Each frame: marker `0xAA 0x55` followed by `rows * cols` uint8 ADC samples,
streamed continuously at the configured baud rate.

## Development

```bash
make format         # ruff format + autofix
make static-checks  # ruff + mypy
make test           # pytest
```
