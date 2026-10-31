"""Run deterministic JavaScript receiver regressions on Node (included in Windows CI)."""
from pathlib import Path
import shutil
import subprocess


def test_native_audio_receiver_behaviors():
    node = shutil.which('node')
    assert node, 'Node is required for the browser receiver regression suite'
    result = subprocess.run(
        [node, '--test', str(Path(__file__).with_name('receiver.test.cjs'))],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
