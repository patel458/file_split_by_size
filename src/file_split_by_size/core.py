from __future__ import annotations

import os
from pathlib import Path


def _format_index(index: int, total: int) -> str:
    """Zero-pad the part index so lexical sort matches numeric sort.

    Without padding, part_10 sorts before part_2 in most tools. We derive the
    width from the total count so the padding is exactly wide enough and no
    wider — a small thing, but it means a 3-file split doesn't get padded to
    part_000 just because some other split had a thousand parts.
    """
    width = max(1, len(str(total)))
    return str(index).zfill(width)


def split_bytes(data: bytes, chunk_size: int) -> list[bytes]:
    """Split a bytes object into chunks no larger than chunk_size.

    Returns a list of chunks. The concatenation of the chunks equals data.
    If data is empty, returns an empty list — there is nothing to write.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"data must be bytes-like, got {type(data).__name__}")
    data = bytes(data)
    if not data:
        return []
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]


def split_file(source: str | os.PathLike, chunk_size: int, output_dir: str | os.PathLike = ".", prefix: str | None = None) -> list[Path]:
    """Split a file into part files no larger than chunk_size bytes.

    Reads source in chunk_size increments so memory use stays bounded regardless
    of file size — the whole point of this library. Writes part files named
    {prefix}.{index} into output_dir, where index is zero-padded so lexical
    ordering matches numeric ordering.

    Args:
        source: Path to the file to split.
        chunk_size: Maximum size in bytes of each part file.
        output_dir: Directory to write part files into. Created if missing.
        prefix: Base name for part files. Defaults to the source file's name.

    Returns:
        List of Path objects for the part files written, in order.

    Raises:
        ValueError: If chunk_size is not positive.
        FileNotFoundError: If source does not exist.
        IsADirectoryError: If source is a directory.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")

    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"source file not found: {source_path}")
    if source_path.is_dir():
        raise IsADirectoryError(f"source is a directory, not a file: {source_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if prefix is None:
        prefix = source_path.name

    written: list[Path] = []
    index = 0
    with open(source_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            # We don't know the total count up front, so we can't zero-pad to
            # the right width in a single pass. We use a generous width of 6
            # digits (up to 999999 parts) which covers files up to ~1 TB at a
            # 1 MB chunk size. If someone exceeds that, we raise rather than
            # silently producing mis-sorted names.
            if index >= 1_000_000:
                raise ValueError(
                    f"refusing to write more than 999999 parts; "
                    f"use a larger chunk_size for {source_path}"
                )
            part_path = out_dir / f"{prefix}.{index:06d}"
            with open(part_path, "wb") as out:
                out.write(chunk)
            written.append(part_path)
            index += 1

    if not written:
        # Empty source file: write a single empty part so the split is
        # reversible. join_files on that single empty part reproduces the
        # empty original.
        part_path = out_dir / f"{prefix}.000000"
        part_path.touch()
        written.append(part_path)

    return written


def join_files(part_paths: list[str | os.PathLike], destination: str | os.PathLike) -> Path:
    """Concatenate part files into a single file.

    Args:
        part_paths: List of part file paths, in the order they should be
            concatenated.
        destination: Path to write the joined file to.

    Returns:
        Path object for the destination file.

    Raises:
        ValueError: If part_paths is empty.
        FileNotFoundError: If any part file does not exist.
    """
    if not part_paths:
        raise ValueError("part_paths must not be empty")

    dest_path = Path(destination)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "wb") as out:
        for p in part_paths:
            part = Path(p)
            if not part.exists():
                raise FileNotFoundError(f"part file not found: {part}")
            with open(part, "rb") as f:
                while True:
                    block = f.read(1 << 20)  # 1 MB blocks to bound memory
                    if not block:
                        break
                    out.write(block)

    return dest_path
