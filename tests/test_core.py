import os
import tempfile
import unittest
from pathlib import Path

from file_split_by_size import split_file, split_bytes, join_files


class TestSplitBytes(unittest.TestCase):
    def test_basic_split(self):
        data = b"abcdefghij"
        chunks = split_bytes(data, 4)
        self.assertEqual(chunks, [b"abcd", b"efgh", b"ij"])

    def test_exact_multiple(self):
        data = b"abcdefgh"
        chunks = split_bytes(data, 4)
        self.assertEqual(chunks, [b"abcd", b"efgh"])

    def test_chunk_larger_than_data(self):
        data = b"abc"
        chunks = split_bytes(data, 100)
        self.assertEqual(chunks, [b"abc"])

    def test_empty_data(self):
        self.assertEqual(split_bytes(b"", 10), [])

    def test_chunk_size_one(self):
        data = b"abc"
        self.assertEqual(split_bytes(data, 1), [b"a", b"b", b"c"])

    def test_invalid_chunk_size(self):
        with self.assertRaises(ValueError):
            split_bytes(b"abc", 0)
        with self.assertRaises(ValueError):
            split_bytes(b"abc", -1)

    def test_bytearray_input(self):
        chunks = split_bytes(bytearray(b"abcdef"), 3)
        self.assertEqual(chunks, [b"abc", b"def"])

    def test_memoryview_input(self):
        chunks = split_bytes(memoryview(b"abcdef"), 3)
        self.assertEqual(chunks, [b"abc", b"def"])


class TestSplitFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_file(self, name, content):
        p = Path(self.tmpdir) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return p

    def test_basic_split_and_rejoin(self):
        data = bytes(range(256)) * 10  # 2560 bytes
        src = self._make_file("input.bin", data)
        out_dir = Path(self.tmpdir) / "out"
        parts = split_file(src, 1000, out_dir)
        self.assertEqual(len(parts), 3)
        # Each part file should be <= chunk_size
        for p in parts:
            self.assertLessEqual(p.stat().st_size, 1000)
        # Names should sort lexically in order
        names = [p.name for p in parts]
        self.assertEqual(names, sorted(names))
        # Rejoin
        joined = join_files(parts, Path(self.tmpdir) / "joined.bin")
        self.assertEqual(joined.read_bytes(), data)

    def test_empty_source_file(self):
        src = self._make_file("empty.bin", b"")
        out_dir = Path(self.tmpdir) / "out"
        parts = split_file(src, 100, out_dir)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].stat().st_size, 0)
        joined = join_files(parts, Path(self.tmpdir) / "joined.bin")
        self.assertEqual(joined.read_bytes(), b"")

    def test_exact_multiple_chunk_size(self):
        data = b"a" * 500
        src = self._make_file("exact.bin", data)
        out_dir = Path(self.tmpdir) / "out"
        parts = split_file(src, 250, out_dir)
        self.assertEqual(len(parts), 2)
        for p in parts:
            self.assertEqual(p.stat().st_size, 250)
        joined = join_files(parts, Path(self.tmpdir) / "joined.bin")
        self.assertEqual(joined.read_bytes(), data)

    def test_chunk_larger_than_file(self):
        data = b"small"
        src = self._make_file("small.bin", data)
        out_dir = Path(self.tmpdir) / "out"
        parts = split_file(src, 10000, out_dir)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].read_bytes(), data)

    def test_custom_prefix(self):
        data = b"hello world"
        src = self._make_file("input.txt", data)
        out_dir = Path(self.tmpdir) / "out"
        parts = split_file(src, 5, out_dir, prefix="myparts")
        for p in parts:
            self.assertTrue(p.name.startswith("myparts."))

    def test_output_dir_created(self):
        data = b"test"
        src = self._make_file("input.bin", data)
        out_dir = Path(self.tmpdir) / "deep" / "nested" / "out"
        parts = split_file(src, 2, out_dir)
        self.assertTrue(out_dir.is_dir())
        self.assertEqual(len(parts), 2)

    def test_invalid_chunk_size(self):
        src = self._make_file("input.bin", b"abc")
        with self.assertRaises(ValueError):
            split_file(src, 0)
        with self.assertRaises(ValueError):
            split_file(src, -5)

    def test_source_not_found(self):
        with self.assertRaises(FileNotFoundError):
            split_file(Path(self.tmpdir) / "nonexistent.bin", 100)

    def test_source_is_directory(self):
        d = Path(self.tmpdir) / "somedir"
        d.mkdir()
        with self.assertRaises(IsADirectoryError):
            split_file(d, 100)

    def test_default_prefix_uses_source_name(self):
        data = b"test data here"
        src = self._make_file("myinput.bin", data)
        out_dir = Path(self.tmpdir) / "out"
        parts = split_file(src, 5, out_dir)
        for p in parts:
            self.assertTrue(p.name.startswith("myinput.bin."))

    def test_large_file_streaming(self):
        # Verify streaming behavior: file larger than chunk_size, multiple parts
        data = bytes(range(256)) * 100  # 25600 bytes
        src = self._make_file("large.bin", data)
        out_dir = Path(self.tmpdir) / "out"
        parts = split_file(src, 4096, out_dir)
        # 25600 / 4096 = 6.25 -> 7 parts
        self.assertEqual(len(parts), 7)
        self.assertEqual(parts[-1].stat().st_size, 25600 - 6 * 4096)
        joined = join_files(parts, Path(self.tmpdir) / "joined.bin")
        self.assertEqual(joined.read_bytes(), data)


class TestJoinFiles(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_join_empty_list(self):
        with self.assertRaises(ValueError):
            join_files([], Path(self.tmpdir) / "out.bin")

    def test_join_missing_part(self):
        p1 = Path(self.tmpdir) / "p.000000"
        p1.write_bytes(b"abc")
        with self.assertRaises(FileNotFoundError):
            join_files([p1, Path(self.tmpdir) / "missing.000001"], Path(self.tmpdir) / "out.bin")

    def test_join_creates_parent_dirs(self):
        p1 = Path(self.tmpdir) / "p.000000"
        p1.write_bytes(b"abc")
        dest = Path(self.tmpdir) / "deep" / "nested" / "out.bin"
        result = join_files([p1], dest)
        self.assertEqual(result.read_bytes(), b"abc")

    def test_join_order_preserved(self):
        p0 = Path(self.tmpdir) / "p.000000"
        p1 = Path(self.tmpdir) / "p.000001"
        p0.write_bytes(b"AAA")
        p1.write_bytes(b"BBB")
        dest = Path(self.tmpdir) / "out.bin"
        join_files([p0, p1], dest)
        self.assertEqual(dest.read_bytes(), b"AAABBB")
        # Reverse order
        dest2 = Path(self.tmpdir) / "out2.bin"
        join_files([p1, p0], dest2)
        self.assertEqual(dest2.read_bytes(), b"BBBAAA")


if __name__ == "__main__":
    unittest.main()
