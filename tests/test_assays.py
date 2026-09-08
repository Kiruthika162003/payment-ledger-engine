from __future__ import annotations

from mint.assays import broken, catalog
from mint.cli import main


class TestRegistry:
    def test_the_catalog_is_not_empty(self):
        assert len(catalog()) >= 1

    def test_every_assay_holds(self):
        failing = [item.name for item in broken()]
        assert failing == []

    def test_names_are_unique(self):
        names = [item.name for item in catalog()]
        assert len(names) == len(set(names))

    def test_every_assay_measures_something(self):
        for item in catalog():
            assert item.findings(), f"{item.name} produced no findings"


class TestCli:
    def test_check_exits_zero_when_all_hold(self):
        assert main(["check"]) == 0

    def test_summary_reports_zero_broken(self, capsys):
        code = main(["summary"])
        out = capsys.readouterr().out.strip()
        assert code == 0
        assert out.endswith("(0 broken)")
        assert out.startswith(f"{len(catalog())} assays")

    def test_list_names_every_assay(self, capsys):
        main(["list"])
        out = capsys.readouterr().out
        for item in catalog():
            assert item.name in out

    def test_an_unknown_command_is_reported(self, capsys):
        code = main(["frobnicate"])
        out = capsys.readouterr().out
        assert code == 2
        assert "unknown command" in out
