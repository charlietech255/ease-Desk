import textwrap
from pathlib import Path

from shared.utilities.apps import discover_applications


def test_discover_applications_filters_and_expands_exec(tmp_path: Path):
    (tmp_path / "visible.desktop").write_text(textwrap.dedent("""
        [Desktop Entry]
        Type=Application
        Name=Visible Editor
        Comment=Edit text files
        Exec=editor --new-window %F
        Icon=accessories-text-editor
    """), encoding="utf-8")
    (tmp_path / "hidden.desktop").write_text("[Desktop Entry]\nType=Application\nName=Hidden\nHidden=true\nExec=hidden\n", encoding="utf-8")
    (tmp_path / "invalid.desktop").write_text("not an entry", encoding="utf-8")

    apps = discover_applications([tmp_path])

    assert len(apps) == 1
    assert apps[0].name == "Visible Editor"
    assert apps[0].exec_command == ("editor", "--new-window")
    assert apps[0].matches("text files")
