from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("lakemind.asr.prefetch")

MODEL_DIR = Path(os.environ.get("ASR_MODEL_DIR", "/models/asr/faster-whisper-small"))
MODEL_ID = os.environ.get("ASR_MODEL_ID", "Systran/faster-whisper-small")
MODEL_REVISION = os.environ.get("ASR_MODEL_REVISION", "536b0662742c02347bc0e980a01041f333bce120")
MODEL_BIN_SHA256 = os.environ.get(
    "ASR_MODEL_BIN_SHA256",
    "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
)

REQUIRED_FILES = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "vocabulary.txt",
)

ALLOW_PATTERNS = [
    "model.bin",
    "config.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "vocabulary.*",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_model(path: Path, verify_hash: bool = True) -> None:
    missing = [f for f in REQUIRED_FILES if not (path / f).is_file()]
    if missing:
        raise RuntimeError(f"Missing ASR model files: {missing}")

    model_bin = path / "model.bin"
    if model_bin.stat().st_size < 400 * 1024 * 1024:
        raise RuntimeError(f"model.bin is unexpectedly small: {model_bin.stat().st_size} bytes")

    if verify_hash:
        actual = sha256_file(model_bin)
        if actual != MODEL_BIN_SHA256:
            raise RuntimeError(f"model.bin checksum mismatch: expected {MODEL_BIN_SHA256}, got {actual}")


def main() -> None:
    manifest_path = MODEL_DIR / "model-manifest.json"

    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                manifest.get("model_id") == MODEL_ID
                and manifest.get("revision") == MODEL_REVISION
                and manifest.get("verified") is True
            ):
                validate_model(MODEL_DIR, verify_hash=False)
                logger.info("Model already verified at %s", MODEL_DIR)
                return
        except Exception as e:
            logger.warning("Manifest check failed, will re-download: %s", e)

    staging_dir = MODEL_DIR.parent / f".{MODEL_DIR.name}.downloading"

    shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading %s@%s to staging %s", MODEL_ID, MODEL_REVISION, staging_dir)

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(staging_dir),
        allow_patterns=ALLOW_PATTERNS,
        max_workers=2,
    )

    logger.info("Download complete, validating...")
    validate_model(staging_dir, verify_hash=True)

    logger.info("SHA-256 verified, testing model load...")
    from faster_whisper import WhisperModel

    test_model = WhisperModel(
        str(staging_dir),
        device="cpu",
        compute_type="int8",
        cpu_threads=1,
        num_workers=1,
    )
    del test_model
    logger.info("Model load test passed")

    manifest = {
        "schema_version": 1,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "runtime": "faster-whisper",
        "runtime_version": "1.2.1",
        "model_bin_sha256": MODEL_BIN_SHA256,
        "verified": True,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    (staging_dir / "model-manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)

    staging_dir.rename(MODEL_DIR)
    logger.info("ASR model installed at %s", MODEL_DIR)


if __name__ == "__main__":
    main()
