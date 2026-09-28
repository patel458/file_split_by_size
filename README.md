# file-split-by-size

Splits a binary file into chunks no larger than a given byte size, writing part files with zero-padded index suffixes.

```python
import tempfile
from pathlib import Path
from file_split_by_size import split_file, join_files

tmp = Path(tempfile.mkdtemp())
src = tmp / "large.bin"
src.write_bytes(b"some data to split")

parts = split_file(src, chunk_size=1_000_000, output_dir=tmp / "parts")
join_files(parts, tmp / "reconstructed.bin")
```

## Why

The problem is simple: move a large file through a channel that caps individual message size. You need deterministic splits you can reverse, without pulling in a compression or archive library that does a dozen other things.

The trade-off: part files are named with a fixed 6-digit zero-padded index (`prefix.000000`, `prefix.000001`, ...). This caps you at 999,999 parts. At a 1 MB chunk size that's roughly 1 TB, which covers the intended use. If you need more, use a bigger chunk size.

## Edge cases

An empty source file produces a single empty part file. This keeps the split reversible — `join_files` on that one empty part reproduces the empty original. If `split_file` wrote zero parts for an empty input, `join_files` would have nothing to read and would refuse the empty list.

`chunk_size` must be positive. Zero and negative values raise `ValueError` before any I/O happens.
