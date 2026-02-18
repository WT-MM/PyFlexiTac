"""CLI and helpers for rendering and flashing FlexiTac Arduino firmware."""

from __future__ import annotations

import argparse
import json
import logging
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from flexitac.firmware.profiles import SUPPORTED_AVR_FQBNS, get_profile, profile_names
from flexitac.firmware.render import FirmwareRenderError, parse_set_overrides, render_template_to_file, resolve_macros
from flexitac.logging_utils import configure_logging

FQBN_RE = re.compile(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+")
LOGGER = logging.getLogger("flexitac")


class FlashError(RuntimeError):
    """Raised when flashing setup or upload steps fail."""


@dataclass(frozen=True)
class BoardCandidate:
    """Detected board candidate for upload."""

    port: str
    fqbn: str
    name: str


@dataclass(frozen=True)
class FlashResult:
    """Result metadata from a flash run."""

    port: str
    fqbn: str
    rows: int
    cols: int
    baud: int
    sketch_path: str
    compile_command: str
    upload_command: str
    dry_run: bool


def build_parser() -> argparse.ArgumentParser:
    """Build the flash CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m flexitac.flash",
        description="Generate and flash FlexiTac Arduino firmware using arduino-cli.",
    )

    parser.add_argument("--profile", default="16x32", help="Firmware profile to use (default: 16x32)")
    parser.add_argument("--port", help="Serial port to upload to, e.g. /dev/ttyUSB0")
    parser.add_argument("--fqbn", help="Arduino FQBN, e.g. arduino:avr:uno")
    parser.add_argument(
        "--board-options",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional board options forwarded to arduino-cli (repeatable).",
    )

    parser.add_argument("--rows", type=int, help="Override ROW_COUNT")
    parser.add_argument("--cols", type=int, help="Override COLUMN_COUNT")
    parser.add_argument("--baud", type=int, help="Override BAUD_RATE")

    parser.add_argument("--pin-adc-input", help="Override PIN_ADC_INPUT")
    parser.add_argument("--pin-shift-register-data", help="Override PIN_SHIFT_REGISTER_DATA")
    parser.add_argument("--pin-shift-register-clock", help="Override PIN_SHIFT_REGISTER_CLOCK")
    parser.add_argument("--pin-mux-channel-0", help="Override PIN_MUX_CHANNEL_0")
    parser.add_argument("--pin-mux-channel-1", help="Override PIN_MUX_CHANNEL_1")
    parser.add_argument("--pin-mux-channel-2", help="Override PIN_MUX_CHANNEL_2")
    parser.add_argument("--pin-mux-channel-3", help="Override PIN_MUX_CHANNEL_3")
    parser.add_argument("--pin-mux-inhibit-0", help="Override PIN_MUX_INHIBIT_0")
    parser.add_argument("--pin-mux-inhibit-1", help="Override PIN_MUX_INHIBIT_1")

    parser.add_argument(
        "--set",
        dest="set_overrides",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Override a macro directly. Allowlisted unless --expert is set.",
    )

    parser.add_argument("--list-profiles", action="store_true", help="List available firmware profiles and exit")
    parser.add_argument("--list-boards", action="store_true", help="List connected boards and exit")
    parser.add_argument("--dry-run", action="store_true", help="Render and print commands without flashing")
    parser.add_argument("--verbose", action="store_true", help="Print detailed command output")
    parser.add_argument("--print-config", action="store_true", help="Print resolved firmware macro configuration")
    parser.add_argument("--emit-sketch", help="Write the rendered sketch to this file path")
    parser.add_argument("--expert", action="store_true", help="Allow unsupported boards and unrestricted --set")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the flash CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = configure_logging(verbose=args.verbose)

    try:
        if args.list_profiles:
            _print_profiles()
            return 0

        ensure_arduino_cli_available(verbose=args.verbose)

        if args.list_boards:
            _print_boards(verbose=args.verbose)
            return 0

        result = flash_firmware(
            profile_name=args.profile,
            port=args.port,
            fqbn=args.fqbn,
            board_options=args.board_options,
            rows=args.rows,
            cols=args.cols,
            baud=args.baud,
            pin_adc_input=args.pin_adc_input,
            pin_shift_register_data=args.pin_shift_register_data,
            pin_shift_register_clock=args.pin_shift_register_clock,
            pin_mux_channel_0=args.pin_mux_channel_0,
            pin_mux_channel_1=args.pin_mux_channel_1,
            pin_mux_channel_2=args.pin_mux_channel_2,
            pin_mux_channel_3=args.pin_mux_channel_3,
            pin_mux_inhibit_0=args.pin_mux_inhibit_0,
            pin_mux_inhibit_1=args.pin_mux_inhibit_1,
            set_overrides=args.set_overrides,
            print_config=args.print_config,
            emit_sketch=args.emit_sketch,
            dry_run=args.dry_run,
            expert=args.expert,
            verbose=args.verbose,
        )

        mode = "Dry run complete" if result.dry_run else "Flash complete"
        logger.info(
            "%s: port=%s fqbn=%s rows=%s cols=%s baud=%s",
            mode,
            result.port,
            result.fqbn,
            result.rows,
            result.cols,
            result.baud,
        )
        logger.info("compile: %s", result.compile_command)
        logger.info("upload:  %s", result.upload_command)
        logger.info("sketch:  %s", result.sketch_path)
        return 0
    except (FlashError, FirmwareRenderError, ValueError) as exc:
        logger.error("%s", exc)
        return 2


def flash_firmware(
    *,
    profile_name: str,
    port: str | None,
    fqbn: str | None,
    board_options: list[str],
    rows: int | None,
    cols: int | None,
    baud: int | None,
    pin_adc_input: str | None,
    pin_shift_register_data: str | None,
    pin_shift_register_clock: str | None,
    pin_mux_channel_0: str | None,
    pin_mux_channel_1: str | None,
    pin_mux_channel_2: str | None,
    pin_mux_channel_3: str | None,
    pin_mux_inhibit_0: str | None,
    pin_mux_inhibit_1: str | None,
    set_overrides: list[str],
    print_config: bool,
    emit_sketch: str | None,
    dry_run: bool,
    expert: bool,
    verbose: bool,
) -> FlashResult:
    """Render firmware and compile/upload it with arduino-cli."""
    profile = get_profile(profile_name)
    common_overrides = _build_common_overrides(
        rows=rows,
        cols=cols,
        baud=baud,
        pin_adc_input=pin_adc_input,
        pin_shift_register_data=pin_shift_register_data,
        pin_shift_register_clock=pin_shift_register_clock,
        pin_mux_channel_0=pin_mux_channel_0,
        pin_mux_channel_1=pin_mux_channel_1,
        pin_mux_channel_2=pin_mux_channel_2,
        pin_mux_channel_3=pin_mux_channel_3,
        pin_mux_inhibit_0=pin_mux_inhibit_0,
        pin_mux_inhibit_1=pin_mux_inhibit_1,
    )

    direct_overrides = parse_set_overrides(set_overrides)
    macros = resolve_macros(
        profile=profile,
        common_overrides=common_overrides,
        set_overrides=direct_overrides,
        expert=expert,
    )

    if print_config:
        LOGGER.info("resolved firmware macros:\n%s", json.dumps(macros, indent=2, sort_keys=True))

    board_opts = _normalize_board_options(board_options)
    selected_port, selected_fqbn = select_board(port=port, fqbn=fqbn, expert=expert, verbose=verbose)

    if not expert and selected_fqbn not in SUPPORTED_AVR_FQBNS:
        supported = ", ".join(SUPPORTED_AVR_FQBNS)
        msg = (
            f"Detected board '{selected_fqbn}' is not in supported AVR targets. "
            f"Supported defaults: {supported}. Use --expert to override."
        )
        raise FlashError(msg)

    ensure_core_installed(selected_fqbn)

    template_path = Path(__file__).resolve().parent / "firmware" / "template.ino"
    with tempfile.TemporaryDirectory(prefix="flexitac-sketch-") as temp_dir:
        sketch_dir = Path(temp_dir) / "flexitac_generated"
        sketch_path = sketch_dir / "flexitac_generated.ino"
        rendered = render_template_to_file(template_path=template_path, output_path=sketch_path, macros=macros)

        if emit_sketch is not None:
            emit_path = Path(emit_sketch).expanduser().resolve()
            emit_path.parent.mkdir(parents=True, exist_ok=True)
            emit_path.write_text(rendered, encoding="utf-8")

        compile_cmd = _build_compile_command(
            fqbn=selected_fqbn,
            sketch_dir=sketch_dir,
            board_options=board_opts,
        )
        upload_cmd = _build_upload_command(
            port=selected_port,
            fqbn=selected_fqbn,
            sketch_dir=sketch_dir,
            board_options=board_opts,
        )

        if verbose or dry_run:
            LOGGER.info("compile cmd: %s", _shell_join(compile_cmd))
            LOGGER.info("upload cmd: %s", _shell_join(upload_cmd))

        if not dry_run:
            _run_command(compile_cmd, verbose=verbose)
            _run_command(upload_cmd, verbose=verbose)

        return FlashResult(
            port=selected_port,
            fqbn=selected_fqbn,
            rows=int(macros["ROW_COUNT"], 0),
            cols=int(macros["COLUMN_COUNT"], 0),
            baud=int(macros["BAUD_RATE"], 0),
            sketch_path=str(Path(emit_sketch).expanduser().resolve()) if emit_sketch else str(sketch_path),
            compile_command=_shell_join(compile_cmd),
            upload_command=_shell_join(upload_cmd),
            dry_run=dry_run,
        )


def ensure_arduino_cli_available(*, verbose: bool) -> str:
    """Ensure arduino-cli exists and return its version string."""
    result = _run_command(["arduino-cli", "version"], verbose=verbose, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        msg = f"arduino-cli is installed but unusable: {stderr}"
        raise FlashError(msg)

    output = (result.stdout or "").strip()
    if not output:
        msg = "arduino-cli version output was empty"
        raise FlashError(msg)
    return output


def select_board(*, port: str | None, fqbn: str | None, expert: bool, verbose: bool) -> tuple[str, str]:
    """Select a single board target using explicit args and autodetection."""
    if fqbn is not None and not expert and fqbn not in SUPPORTED_AVR_FQBNS:
        supported = ", ".join(SUPPORTED_AVR_FQBNS)
        msg = f"fqbn '{fqbn}' is unsupported by default. Supported: {supported}. Use --expert to override."
        raise FlashError(msg)

    if port is not None and fqbn is not None:
        return port, fqbn

    candidates = list_boards(verbose=verbose)
    filtered = list(candidates)

    if not expert:
        filtered = [candidate for candidate in filtered if candidate.fqbn in SUPPORTED_AVR_FQBNS]

    if port is not None:
        filtered = [candidate for candidate in filtered if candidate.port == port]

    if fqbn is not None:
        filtered = [candidate for candidate in filtered if candidate.fqbn == fqbn]

    if len(filtered) == 1:
        candidate = filtered[0]
        return candidate.port, candidate.fqbn

    if not filtered:
        if candidates:
            available = "\n".join(f"  - {item.port} ({item.fqbn})" for item in candidates)
            msg = (
                "no matching board found after applying filters. "
                "Specify --port and --fqbn explicitly. Available detected boards:\n"
                f"{available}\n{_board_scan_hint()}"
            )
            raise FlashError(msg)
        msg = (
            "no boards detected. Connect the board and retry, or pass --port and --fqbn explicitly.\n"
            f"{_board_scan_hint()}"
        )
        raise FlashError(msg)

    options = "\n".join(f"  - {item.port} ({item.fqbn})" for item in filtered)
    msg = (
        "multiple matching boards detected. Specify --port and --fqbn explicitly. Candidates:\n"
        f"{options}\n{_board_scan_hint()}"
    )
    raise FlashError(msg)


def list_boards(*, verbose: bool) -> list[BoardCandidate]:
    """Detect connected boards, preferring JSON output when available."""
    if _supports_board_list_json(verbose=verbose):
        result = _run_command(
            ["arduino-cli", "board", "list", "--format", "json"],
            verbose=verbose,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            try:
                payload = json.loads(result.stdout)
                candidates = _parse_board_list_json(payload)
                return _dedupe_candidates(candidates)
            except json.JSONDecodeError:
                if verbose:
                    LOGGER.warning("failed to parse JSON board list; falling back to text mode")

    text_result = _run_command(["arduino-cli", "board", "list"], verbose=verbose, capture_output=True, check=False)
    if text_result.returncode != 0:
        stderr = text_result.stderr.strip()
        msg = f"failed to list boards: {stderr}"
        raise FlashError(msg)

    return _dedupe_candidates(_parse_board_list_text(text_result.stdout))


def ensure_core_installed(fqbn: str) -> None:
    """Ensure the required board core for an FQBN is already installed."""
    required_core = ":".join(fqbn.split(":")[:2])
    if required_core.count(":") != 1:
        msg = f"invalid fqbn '{fqbn}'"
        raise FlashError(msg)

    installed = list_installed_cores()
    if required_core not in installed:
        msg = f"missing Arduino core '{required_core}'. Install it with:\n  arduino-cli core install {required_core}"
        raise FlashError(msg)


def list_installed_cores() -> set[str]:
    """Return installed arduino-cli core IDs."""
    result = _run_command(
        ["arduino-cli", "core", "list", "--format", "json"], verbose=False, capture_output=True, check=False
    )
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout)
            cores = _extract_cores_json(payload)
            if cores:
                return cores
        except json.JSONDecodeError:
            pass

    fallback = _run_command(["arduino-cli", "core", "list"], verbose=False, capture_output=True, check=False)
    if fallback.returncode != 0:
        stderr = fallback.stderr.strip()
        msg = f"failed to inspect installed cores: {stderr}"
        raise FlashError(msg)

    fallback_cores: set[str] = set()
    for line in fallback.stdout.splitlines():
        matches = re.findall(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", line)
        for match in matches:
            fallback_cores.add(match)
    return fallback_cores


def _print_profiles() -> None:
    for name in profile_names():
        profile = get_profile(name)
        LOGGER.info("%s: %s", name, profile.description)


def _print_boards(*, verbose: bool) -> None:
    boards = list_boards(verbose=verbose)
    if not boards:
        LOGGER.info("No boards detected.")
        return
    for candidate in boards:
        LOGGER.info("%s | %s | %s", candidate.port, candidate.fqbn, candidate.name)


def _build_common_overrides(
    *,
    rows: int | None,
    cols: int | None,
    baud: int | None,
    pin_adc_input: str | None,
    pin_shift_register_data: str | None,
    pin_shift_register_clock: str | None,
    pin_mux_channel_0: str | None,
    pin_mux_channel_1: str | None,
    pin_mux_channel_2: str | None,
    pin_mux_channel_3: str | None,
    pin_mux_inhibit_0: str | None,
    pin_mux_inhibit_1: str | None,
) -> dict[str, str]:
    overrides: dict[str, str] = {}

    if rows is not None:
        overrides["rows"] = str(rows)
    if cols is not None:
        overrides["cols"] = str(cols)
    if baud is not None:
        overrides["baud"] = str(baud)

    if pin_adc_input is not None:
        overrides["pin_adc_input"] = pin_adc_input
    if pin_shift_register_data is not None:
        overrides["pin_shift_register_data"] = pin_shift_register_data
    if pin_shift_register_clock is not None:
        overrides["pin_shift_register_clock"] = pin_shift_register_clock
    if pin_mux_channel_0 is not None:
        overrides["pin_mux_channel_0"] = pin_mux_channel_0
    if pin_mux_channel_1 is not None:
        overrides["pin_mux_channel_1"] = pin_mux_channel_1
    if pin_mux_channel_2 is not None:
        overrides["pin_mux_channel_2"] = pin_mux_channel_2
    if pin_mux_channel_3 is not None:
        overrides["pin_mux_channel_3"] = pin_mux_channel_3
    if pin_mux_inhibit_0 is not None:
        overrides["pin_mux_inhibit_0"] = pin_mux_inhibit_0
    if pin_mux_inhibit_1 is not None:
        overrides["pin_mux_inhibit_1"] = pin_mux_inhibit_1

    return overrides


def _normalize_board_options(options: list[str]) -> list[str]:
    normalized: list[str] = []
    for option in options:
        if "=" not in option:
            msg = f"invalid --board-options '{option}'. Expected KEY=VALUE"
            raise FlashError(msg)
        key, value = option.split("=", 1)
        if not key.strip() or not value.strip():
            msg = f"invalid --board-options '{option}'. Expected KEY=VALUE"
            raise FlashError(msg)
        normalized.append(f"{key.strip()}={value.strip()}")
    return normalized


def _build_compile_command(*, fqbn: str, sketch_dir: Path, board_options: list[str]) -> list[str]:
    cmd = ["arduino-cli", "compile", "--fqbn", fqbn]
    for option in board_options:
        cmd.extend(["--board-options", option])
    cmd.append(str(sketch_dir))
    return cmd


def _build_upload_command(*, port: str, fqbn: str, sketch_dir: Path, board_options: list[str]) -> list[str]:
    cmd = ["arduino-cli", "upload", "-p", port, "--fqbn", fqbn]
    for option in board_options:
        cmd.extend(["--board-options", option])
    cmd.append(str(sketch_dir))
    return cmd


def _run_command(
    cmd: list[str],
    *,
    verbose: bool,
    capture_output: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=capture_output,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = (
            "arduino-cli was not found on PATH. Install it from "
            "https://arduino.github.io/arduino-cli/latest/installation/"
        )
        raise FlashError(msg) from exc

    if verbose and capture_output:
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if stdout:
            LOGGER.debug(stdout)
        if stderr:
            LOGGER.debug(stderr)

    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        payload = stderr if stderr else stdout
        msg = f"command failed ({_shell_join(cmd)}): {payload}"
        raise FlashError(msg)

    return result


def _supports_board_list_json(*, verbose: bool) -> bool:
    help_result = _run_command(
        ["arduino-cli", "board", "list", "--help"],
        verbose=verbose,
        capture_output=True,
        check=False,
    )
    text = f"{help_result.stdout}\n{help_result.stderr}"
    return "--format" in text


def _parse_board_list_json(payload: object) -> list[BoardCandidate]:
    candidates: list[BoardCandidate] = []

    entries: list[dict[str, object]] = []
    if isinstance(payload, dict):
        raw_entries = payload.get("detected_ports")
        if isinstance(raw_entries, list):
            entries = [entry for entry in raw_entries if isinstance(entry, dict)]
    elif isinstance(payload, list):
        entries = [entry for entry in payload if isinstance(entry, dict)]

    for entry in entries:
        port_info = entry.get("port")
        address = ""
        if isinstance(port_info, dict):
            address_obj = port_info.get("address")
            if isinstance(address_obj, str):
                address = address_obj

        if not address:
            direct_address = entry.get("address")
            if isinstance(direct_address, str):
                address = direct_address

        if not address:
            continue

        boards_obj = entry.get("matching_boards")
        if not isinstance(boards_obj, list):
            boards_obj = []

        if boards_obj:
            for board_item in boards_obj:
                if not isinstance(board_item, dict):
                    continue
                fqbn_obj = board_item.get("fqbn")
                if not isinstance(fqbn_obj, str) or not fqbn_obj:
                    continue
                name_obj = board_item.get("name")
                name = name_obj if isinstance(name_obj, str) and name_obj else "Unknown"
                candidates.append(BoardCandidate(port=address, fqbn=fqbn_obj, name=name))
        else:
            fallback_fqbn = entry.get("fqbn")
            if isinstance(fallback_fqbn, str) and fallback_fqbn:
                candidates.append(BoardCandidate(port=address, fqbn=fallback_fqbn, name="Unknown"))

    return candidates


def _parse_board_list_text(payload: str) -> list[BoardCandidate]:
    candidates: list[BoardCandidate] = []

    for line in payload.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Port") or stripped.startswith("Protocol"):
            continue

        port = stripped.split()[0]
        if not (port.startswith("/") or port.upper().startswith("COM")):
            continue

        fqbn_match = FQBN_RE.search(stripped)
        if fqbn_match is None:
            continue

        fqbn = fqbn_match.group(0)
        suffix = stripped[fqbn_match.end() :].strip()
        name = suffix if suffix else "Unknown"
        candidates.append(BoardCandidate(port=port, fqbn=fqbn, name=name))

    return candidates


def _extract_cores_json(payload: object) -> set[str]:
    cores: set[str] = set()

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries_obj = payload.get("installed_platforms")
        if isinstance(entries_obj, list):
            entries = entries_obj
        else:
            entries = []
    else:
        entries = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        for key in ("ID", "id"):
            value = entry.get(key)
            if isinstance(value, str) and ":" in value:
                cores.add(value)

    return cores


def _dedupe_candidates(candidates: list[BoardCandidate]) -> list[BoardCandidate]:
    seen: set[tuple[str, str]] = set()
    deduped: list[BoardCandidate] = []

    for candidate in candidates:
        key = (candidate.port, candidate.fqbn)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    return deduped


def _board_scan_hint() -> str:
    return "Run diagnostics with: uv run python -m flexitac.scan --verbose"


def _shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


if __name__ == "__main__":
    raise SystemExit(main())
