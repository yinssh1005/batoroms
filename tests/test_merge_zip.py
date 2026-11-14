"""merge:dreamcast 的 zip 打包镜像解压后交给 chdman(chdman 打桩,不依赖真实 ROM)。"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from batoroms import merge

GDI = b"3\n1 0 4 2352 track01.bin 0\n2 600 0 2352 track02.raw 0\n3 45000 4 2352 track03.iso 0\n"
TRACKS = {"track01.bin": b"d1", "track02.raw": b"a2", "track03.iso": b"d3"}


class MergeZipTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.origin = self.base / "origin-roms" / "dreamcast"
        self.origin.mkdir(parents=True)
        self.out = self.base / "out" / "dreamcast"
        self.calls: list[tuple[Path, Path]] = []

        def fake_chdman(mode, primary, output, force):
            # 调用时解压出的 gdi 与其引用的 track 必须都在。
            seen = {p.name for p in primary.parent.iterdir()}
            self.calls.append((primary, output))
            self.assertTrue({"disc.gdi", *TRACKS} <= seen)
            output.write_bytes(b"chd")
            return True, ""

        self._orig = merge._run_chdman
        merge._run_chdman = fake_chdman  # type: ignore[assignment]

    def tearDown(self) -> None:
        merge._run_chdman = self._orig  # type: ignore[assignment]
        self._tmp.cleanup()

    def _zip(self, name: str, members: dict[str, bytes]) -> Path:
        p = self.origin / name
        with zipfile.ZipFile(p, "w") as zf:
            for member, data in members.items():
                zf.writestr(member, data)
        return p

    def _game_zip(self, name: str, folder: str = "") -> Path:
        members = {f"{folder}disc.gdi": GDI}
        members.update({f"{folder}{k}": v for k, v in TRACKS.items()})
        return self._zip(name, members)

    def test_zip_merged_under_zip_name_and_tmp_cleaned(self) -> None:
        self._game_zip("Sonic Adventure (USA).zip", folder="SA/")
        report = merge.run_merge(self.base, system="dreamcast")

        self.assertEqual(report.merged, ["dreamcast/Sonic Adventure (USA).zip"])
        (primary, output), = self.calls
        self.assertEqual(primary.name, "disc.gdi")
        self.assertEqual(output, self.out / "Sonic Adventure (USA).chd")
        self.assertFalse((self.out / merge.ZIP_TMP_DIRNAME).exists())

    def test_multi_disc_zips_get_m3u(self) -> None:
        self._game_zip("Shenmue (Disc 1).zip")
        self._game_zip("Shenmue (Disc 2).zip")
        report = merge.run_merge(self.base, system="dreamcast")

        self.assertEqual(report.m3u_written, ["dreamcast/Shenmue.m3u"])
        self.assertEqual(
            (self.out / "Shenmue.m3u").read_text(encoding="utf-8"),
            "Shenmue (Disc 1).chd\nShenmue (Disc 2).chd\n",
        )

    def test_existing_output_skips_without_extracting(self) -> None:
        self._game_zip("Game.zip")
        self.out.mkdir(parents=True)
        (self.out / "Game.chd").write_bytes(b"old")
        report = merge.run_merge(self.base, system="dreamcast")

        self.assertEqual(report.skipped_existing, ["dreamcast/Game.zip"])
        self.assertEqual(self.calls, [])

    def test_bad_zips_reported_as_failed(self) -> None:
        self._zip("Empty.zip", {"readme.txt": b"x"})
        self._zip("Two.zip", {"a.gdi": GDI, "b.gdi": GDI})
        (self.origin / "Broken.zip").write_bytes(b"not a zip")
        report = merge.run_merge(self.base, system="dreamcast")

        failed = dict(report.failed)
        self.assertEqual(
            set(failed),
            {"dreamcast/Empty.zip", "dreamcast/Two.zip", "dreamcast/Broken.zip"},
        )
        self.assertEqual(self.calls, [])
        self.assertFalse((self.out / merge.ZIP_TMP_DIRNAME).exists())

    def test_zip_ignored_on_other_disc_systems(self) -> None:
        saturn = self.base / "origin-roms" / "saturn"
        saturn.mkdir(parents=True)
        with zipfile.ZipFile(saturn / "Game.zip", "w") as zf:
            zf.writestr("disc.cue", b'FILE "t.bin" BINARY\n')
        report = merge.run_merge(self.base, system="saturn")

        self.assertEqual(report.merged + report.failed, [])


if __name__ == "__main__":
    unittest.main()
