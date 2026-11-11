"""rename 的常规经路:离线库直接命中改成规范游戏名(含多盘 m3u),以及卡带平台改名。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from batoroms import rename


class RenameNamesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self._orig_load = rename.load_index

    def tearDown(self) -> None:
        rename.load_index = self._orig_load  # type: ignore[assignment]
        self._tmp.cleanup()

    def _stub_index(self, platforms: dict, names: dict) -> None:
        rename.load_index = lambda: {  # type: ignore[assignment]
            "platforms": platforms,
            "names": names,
        }

    def test_disc_hit_multi_disc_uses_name_and_rewrites_m3u(self) -> None:
        out_psx = self.base / "out" / "psx"
        out_psx.mkdir(parents=True)
        for n in (1, 2, 3):
            (out_psx / f"Final Fantasy VII (USA) (Disc {n}).chd").write_bytes(b"x")
        (out_psx / "Final Fantasy VII (USA).m3u").write_text("old\n", encoding="utf-8")

        self._stub_index(
            {"psx": {"final fantasy vii": "140"}},
            {"140": "Final Fantasy VII"},
        )
        report = rename.run_rename(self.base, system="psx", online=False)

        for n in (1, 2, 3):
            self.assertTrue((out_psx / f"Final Fantasy VII (Disc {n}).chd").is_file())
        m3u = out_psx / "Final Fantasy VII.m3u"
        self.assertTrue(m3u.is_file())
        self.assertEqual(
            m3u.read_text(encoding="utf-8").splitlines(),
            [
                "Final Fantasy VII (Disc 1).chd",
                "Final Fantasy VII (Disc 2).chd",
                "Final Fantasy VII (Disc 3).chd",
            ],
        )
        self.assertFalse((out_psx / "Final Fantasy VII (USA).m3u").exists())
        self.assertEqual(len(report.renamed), 1)

    def test_cart_rom_renamed_preserving_extension(self) -> None:
        out_nes = self.base / "out" / "nes"
        out_nes.mkdir(parents=True)
        (out_nes / "Super Mario Bros (USA).nes").write_bytes(b"x")

        self._stub_index(
            {"nes": {"super mario bros": "7"}},
            {"7": "Super Mario Bros."},
        )
        report = rename.run_rename(self.base, system="nes", online=True)

        # 冒号/非法字符会被清掉;句点结尾被 safe_filename 去掉;扩展名保留。
        self.assertTrue((out_nes / "Super Mario Bros.nes").is_file())
        self.assertFalse((out_nes / "Super Mario Bros (USA).nes").exists())
        self.assertEqual(len(report.renamed), 1)

    def test_already_named_is_idempotent(self) -> None:
        out_psx = self.base / "out" / "psx"
        out_psx.mkdir(parents=True)
        (out_psx / "Metal Gear Solid.chd").write_bytes(b"x")

        self._stub_index(
            {"psx": {"metal gear solid": "102"}},
            {"102": "Metal Gear Solid"},
        )
        report = rename.run_rename(self.base, system="psx", online=False)

        self.assertTrue((out_psx / "Metal Gear Solid.chd").is_file())
        self.assertEqual(report.renamed, [])
        self.assertEqual(len(report.skipped_already), 1)


if __name__ == "__main__":
    unittest.main()
