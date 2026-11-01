"""Live streaming microphone audio capture for continuous voice interaction."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from elvion.storage.traces import default_data_dir


def default_stream_helper_path() -> Path:
    return default_data_dir() / "voice-input" / "stream_capture"


def build_stream_helper(target_path: Path | None = None) -> Path:
    if sys.platform != "darwin":
        raise RuntimeError("Audio streaming is only supported on macOS")
    compiler = shutil.which("swiftc")
    if compiler is None:
        raise RuntimeError("Swift compiler (swiftc) not found")

    target = target_path or default_stream_helper_path()
    source = Path(__file__).with_name("stream_capture.swift")
    info = Path(__file__).parent.parent / "input" / "capture-info.plist"

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stream-build-", dir=target.parent) as tmp_dir:
        binary = Path(tmp_dir) / "stream_capture"
        cmd = [
            compiler,
            str(source),
            "-o", str(binary),
            "-Xlinker", "-sectcreate",
            "-Xlinker", "__TEXT",
            "-Xlinker", "__info_plist",
            "-Xlinker", str(info),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if res.returncode != 0 or not binary.is_file():
            raise RuntimeError(f"Failed to compile stream_capture helper (code {res.returncode})")
        binary.chmod(0o755)
        os.replace(binary, target)
        stamp = sha256(source.read_bytes() + info.read_bytes()).hexdigest()
        target.with_suffix(".sha256").write_text(stamp, encoding="ascii")
    return target


def is_stream_helper_ready(target_path: Path | None = None) -> bool:
    target = target_path or default_stream_helper_path()
    try:
        source = Path(__file__).with_name("stream_capture.swift")
        info = Path(__file__).parent.parent / "input" / "capture-info.plist"
        stamp = sha256(source.read_bytes() + info.read_bytes()).hexdigest()
        return (
            target.is_file()
            and os.access(target, os.X_OK)
            and target.with_suffix(".sha256").read_text(encoding="ascii") == stamp
        )
    except Exception:
        return False


@contextmanager
def open_live_audio_stream(helper_path: Path | None = None, chunk_size: int = 640):
    """Yield a generator reading raw 16kHz 16-bit mono PCM chunks from the live microphone."""
    path = helper_path or default_stream_helper_path()
    if not is_stream_helper_ready(path):
        build_stream_helper(path)

    process = subprocess.Popen(
        [str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    try:
        # Wait for stream ready
        ready_line = process.stderr.readline().decode("utf-8", errors="ignore").strip()
        if "stream_ready" not in ready_line:
            err = ready_line or "Unknown mic error"
            raise RuntimeError(f"Microphone stream failed to initialize: {err}")

        def stream_generator():
            while process.poll() is None:
                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        yield stream_generator()

    finally:
        if process.poll() is None:
            try:
                process.stdin.write(b"stop\n")
                process.stdin.flush()
                process.communicate(timeout=1.0)
            except Exception:
                process.kill()
                process.communicate()
