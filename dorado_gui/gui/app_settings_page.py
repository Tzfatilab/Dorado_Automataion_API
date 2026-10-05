"""Shared resource paths, edited and saved independently of analysis profiles."""
import copy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QScrollArea,
)


class AppSettingsPage(QWidget):
    """Stage global paths; saving does not commit any profile edits."""

    saved = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        # Inherit the same body font used by the Profile settings tab.
        if parent is not None:
            self.setFont(parent.font())
        self.store = store
        self.loading = True
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        help_text = QLabel("Shared paths for all profiles. Analysis values are edited in Profile settings.")
        help_text.setWordWrap(True)
        header = QHBoxLayout()
        header.addWidget(help_text, 1)
        self.restore_button = QPushButton("Restore defaults")
        self.restore_button.setProperty("link", True)
        self.restore_button.setToolTip("Restore the displayed paths to bundled defaults. Save app settings to apply.")
        self.restore_button.clicked.connect(self.restore_defaults)
        header.addWidget(self.restore_button)
        root.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setProperty("card", True)
        fields = QVBoxLayout(body)
        fields.setContentsMargins(18, 16, 18, 16)
        fields.setSpacing(10)
        self.edits = {}
        for key, title, directory in (
            ("dorado_model", "Dorado model folder", True),
            ("mouse", "Mouse reference genome", False),
            ("human", "Human reference genome", False),
            ("zebrafish", "Zebrafish reference genome", False),
            ("default_output_base", "Default output folder", True),
        ):
            fields.addWidget(QLabel(title))
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setAccessibleName(title)
            row.addWidget(edit, 1)
            browse = QPushButton("Browse")
            browse.clicked.connect(lambda checked=False, e=edit, d=directory: self.browse(e, d))
            row.addWidget(browse)
            fields.addLayout(row)
            edit.textChanged.connect(self.update_status)
            self.edits[key] = edit
        self.legacy_note = QLabel()
        self.legacy_note.setWordWrap(True)
        fields.addWidget(self.legacy_note)
        fields.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        footer = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.discard_button = QPushButton("Discard app changes")
        self.discard_button.clicked.connect(self.reload)
        footer.addWidget(self.discard_button)
        self.save_button = QPushButton("Save app settings")
        self.save_button.setProperty("primary", True)
        self.save_button.clicked.connect(self.save)
        footer.addWidget(self.save_button)
        root.addLayout(footer)
        self.reload()

    def browse(self, edit, directory):
        """Stage a selected directory or reference file without saving."""
        if directory:
            path = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text())
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Choose reference", edit.text(), "FASTA (*.fa *.fasta *.fna *.gz);;All files (*)")
        if path:
            edit.setText(path)

    def reload(self):
        """Discard app edits and display the saved shared paths."""
        self.loading = True
        for key, edit in self.edits.items():
            value = self.store.app_paths["references"][key] if key in {"mouse", "human", "zebrafish"} else self.store.app_paths[key]
            edit.setText(value)
        self.refresh_legacy_note()
        self.loading = False
        self.update_status()

    def refresh_legacy_note(self):
        """Identify preserved custom profiles so the scope of an app save is clear."""
        names = ", ".join(self.store.path_overrides)
        self.legacy_note.setText("Preserved custom paths: " + names + ". These profiles keep their own paths until you choose Use app paths in Profile settings." if names else "")
        self.legacy_note.setVisible(bool(names))

    def restore_defaults(self):
        """Stage bundled defaults for visible app fields; keep saved settings intact.

        Discard app changes restores the saved paths. Save app settings applies
        the restored values to profiles using shared paths, preserving custom
        profile paths and any unrelated configuration keys.
        """
        self.loading = True
        defaults = self.store.defaults["paths"]
        for key, edit in self.edits.items():
            value = defaults["references"][key] if key in {"mouse", "human", "zebrafish"} else defaults[key]
            edit.setText(value)
        self.loading = False
        self.update_status()

    def collect(self):
        """Return shared paths with current field edits, preserving hidden path keys."""
        paths = copy.deepcopy(self.store.app_paths)
        for key, edit in self.edits.items():
            if key in {"mouse", "human", "zebrafish"}:
                paths["references"][key] = edit.text().strip()
            else:
                paths[key] = edit.text().strip()
        return paths

    def is_dirty(self):
        return self.collect() != self.store.app_paths

    def update_status(self, *_):
        if self.loading:
            return
        dirty = self.is_dirty()
        self.status.setText("Unsaved app changes" if dirty else "App settings saved")
        self.save_button.setEnabled(dirty)
        self.discard_button.setEnabled(dirty)

    def save(self):
        """Persist shared paths and notify the owner only after a successful write."""
        try:
            self.store.save_app_paths(self.collect())
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "App settings were not saved", str(exc))
            return False
        self.reload()
        self.saved.emit()
        return True

    def confirm_pending(self):
        """Protect app edits when navigating away from Settings or closing."""
        if not self.is_dirty():
            return True
        answer = QMessageBox.question(self, "Unsaved app settings", "Save changes to shared app paths?",
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Save:
            return self.save()
        if answer == QMessageBox.Discard:
            self.reload()
            return True
        return False
