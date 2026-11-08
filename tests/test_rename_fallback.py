"""rename 的 online 回退经路(序列号真实解析 + redump 查询打桩,不触网)。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from batoroms import rename
from tests import synthetic


class RenameFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.out_psx = self.base / "out" / "psx"
        self.origin_psx = self.base / "origin-roms" / "psx"
        self.out_psx.mkdir(parents=True)
        self.origin_psx.mkdir(parents=True)

        # 文件名很脏,离线库按名字查不到;但原始镜像内含 SLUS-00594。
        (self.out_psx / "mystery_dump_v3.chd").write_bytes(b"fake chd")
        (self.origin_psx / "mystery_dump_v3.iso").write_bytes(
            synthetic.make_iso9660("SLUS_005.94")
        )

        # 打桩离线库:只认 "metal gear solid" → id 102。
        self._orig_load = rename.load_index
        rename.load_index = lambda: {  # type: ignore[assignment]
            "platforms": {"psx": {"metal gear solid": "102"}},
            "names": {},
        }
        self._orig_lookup = rename.lookup_title

    def tearDown(self) -> None:
        rename.load_index = self._orig_load  # type: ignore[assignment]
        rename.lookup_title = self._orig_lookup  # type: ignore[assignment]
        self._tmp.cleanup()

    def _stub_lookup(self, title: str | None) -> None:
        rename.lookup_title = lambda system, serial, timeout=15.0: title  # type: ignore[assignment]

    def test_online_recovers_and_renames(self) -> None:
        self._stub_lookup("Metal Gear Solid (Disc 1)")
        report = rename.run_rename(self.base, system="psx", online=True)

        self.assertTrue((self.out_psx / "102.chd").is_file())
        self.assertFalse((self.out_psx / "mystery_dump_v3.chd").exists())
        self.assertEqual(len(report.renamed), 1)
        self.assertEqual(len(report.recovered), 1)
        self.assertEqual(report.not_found, [])

    def test_no_online_skips_as_not_found(self) -> None:
        self._stub_lookup("Metal Gear Solid (Disc 1)")
        report = rename.run_rename(self.base, system="psx", online=False)

        self.assertTrue((self.out_psx / "mystery_dump_v3.chd").is_file())
        self.assertEqual(report.renamed, [])
        self.assertEqual(len(report.not_found), 1)

    def test_online_miss_reports_not_found(self) -> None:
        self._stub_lookup(None)  # redump 无命中
        report = rename.run_rename(self.base, system="psx", online=True)

        self.assertTrue((self.out_psx / "mystery_dump_v3.chd").is_file())
        self.assertEqual(report.renamed, [])
        self.assertEqual(len(report.not_found), 1)
        self.assertIn("redump", report.not_found[0])

    def test_online_title_still_unknown_in_db(self) -> None:
        self._stub_lookup("Totally Unknown Game")  # 离线库里没有
        report = rename.run_rename(self.base, system="psx", online=True)

        self.assertEqual(report.renamed, [])
        self.assertEqual(len(report.not_found), 1)
        self.assertIn("离线库仍查不到", report.not_found[0])


if __name__ == "__main__":
    unittest.main()
