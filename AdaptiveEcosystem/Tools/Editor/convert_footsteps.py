"""Convert user-edited M4A files to importable mono PCM16 WAV. Never trim or normalize.

Run with Python and ffmpeg on PATH, or --ffmpeg PATH. An optional imageio_ffmpeg
installation in Saved/AudioImportTools is discovered for local editor tooling only.
"""
import argparse
import array
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg")
    args = parser.parse_args()
    ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        sys.path.insert(0, str(PROJECT / "Saved/AudioImportTools"))
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError as exc:
            raise RuntimeError("Install ffmpeg or pass --ffmpeg; no runtime dependency is required") from exc
    rows = []
    for surface in ("Grass", "Dry"):
        folder = PROJECT / "Content/Audio/Footsteps" / surface
        sources = sorted(folder.glob("*.m4a"))
        for source in sources:
            suffix = re.sub(r"[^A-Za-z0-9_]", "_", source.stem)
            name = "SW_" + surface + "_" + suffix
            destination = folder / (name + ".wav")
            subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                            "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(destination)], check=True)
            with wave.open(str(destination), "rb") as audio:
                frames, rate = audio.getnframes(), audio.getframerate()
                channels, width = audio.getnchannels(), audio.getsampwidth()
                samples = array.array("h", audio.readframes(frames))
            if sys.byteorder != "little":
                samples.byteswap()
            peak = max((abs(sample) for sample in samples), default=0) / 32768
            rms = (sum(sample * sample for sample in samples) / max(len(samples), 1)) ** 0.5 / 32768
            if frames == 0 or peak == 0 or channels != 1 or width != 2:
                raise RuntimeError("Empty/silent/malformed conversion: " + str(source))
            rows.append({"surface": surface, "source": source.relative_to(PROJECT).as_posix(),
                         "wav": destination.relative_to(PROJECT).as_posix(), "asset_name": name,
                         "duration": round(frames / rate, 4), "rate": rate, "channels": channels,
                         "peak": round(peak, 4), "rms": round(rms, 4)})
    if not rows:
        raise RuntimeError("No M4A sources under Content/Audio/Footsteps/{Grass,Dry}")
    manifest = PROJECT / "Saved/FootstepImportManifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"converted": len(rows), "manifest": str(manifest), "files": rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
