"""Shared local resources, independent of reference analysis profiles."""
import copy
from pathlib import Path
from gui.ui_styles import ask_unsaved_settings
from dorado_workflow.utils.reference_registry import (
    reference_library, apply_reference_library, new_reference_key, BUILTIN_REFERENCES,
)
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QScrollArea, QComboBox, QInputDialog,
)


class AppSettingsPage(QWidget):
    """Manage a general named-reference catalog without editing profile values."""
    saved = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        if parent is not None:
            self.setFont(parent.font())
        self.store, self.loading = store, True
        self.reference_options = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        header = QHBoxLayout()
        help_text = QLabel('Add named reference files here. Set their analysis defaults in Profile settings.')
        help_text.setWordWrap(True)
        header.addWidget(help_text, 1)
        self.restore_button = QPushButton('Restore defaults')
        self.restore_button.clicked.connect(self.restore_defaults)
        header.addWidget(self.restore_button)
        root.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setProperty('card', True)
        fields = QVBoxLayout(body)
        fields.setContentsMargins(18, 16, 18, 16)
        fields.setSpacing(10)
        reference_header = QHBoxLayout()
        reference_header.addWidget(QLabel('Reference genomes'), 1)
        self.add_reference_button = QPushButton('Add reference')
        self.add_reference_button.setToolTip('Add a new named reference to the full reference list.')
        self.add_reference_button.clicked.connect(self.add_reference)
        reference_header.addWidget(self.add_reference_button)
        fields.addLayout(reference_header)
        choices = QHBoxLayout()
        self.reference_selector = QComboBox()
        self.reference_selector.setAccessibleName('Named reference')
        self.reference_selector.setToolTip('Choose a reference to edit. Run selection is made in the Organism list.')
        choices.addWidget(self.reference_selector, 1)
        for title, action in [('Rename', self.rename_reference), ('Remove', self.remove_reference)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            choices.addWidget(button)
            if title == 'Remove':
                self.reference_remove_button = button
        fields.addLayout(choices)
        row = QHBoxLayout()
        self.reference_path = QLineEdit()
        self.reference_path.setAccessibleName('Reference FASTA file')
        row.addWidget(self.reference_path, 1)
        browse = QPushButton('Browse')
        browse.clicked.connect(lambda: self.browse(self.reference_path, False))
        row.addWidget(browse)
        fields.addLayout(row)
        self.reference_selector.currentIndexChanged.connect(self.select_reference)
        self.reference_path.textChanged.connect(self.reference_path_changed)
        self.edits = {}
        for key, title in [('dorado_model', 'Dorado model folder'),
                           ('default_input_base', 'Default input folder'),
                           ('default_output_base', 'Default output folder')]:
            fields.addWidget(QLabel(title))
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setAccessibleName(title)
            row.addWidget(edit, 1)
            button = QPushButton('Browse')
            button.clicked.connect(lambda checked=False, field=edit: self.browse(field, True))
            row.addWidget(button)
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
        self.discard_button = QPushButton('Discard app changes')
        self.discard_button.clicked.connect(self.reload)
        footer.addWidget(self.discard_button)
        self.save_button = QPushButton('Save app settings')
        self.save_button.setProperty('primary', True)
        self.save_button.clicked.connect(self.save)
        footer.addWidget(self.save_button)
        root.addLayout(footer)
        self.reload()

    def fill_reference_selector(self, selected=None):
        previous = selected or self.reference_selector.currentData()
        self.reference_selector.blockSignals(True)
        self.reference_selector.clear()
        for key, item in self.reference_options.items():
            self.reference_selector.addItem(item['name'], key)
        index = self.reference_selector.findData(previous)
        self.reference_selector.setCurrentIndex(index if index >= 0 else 0)
        self.reference_selector.blockSignals(False)
        self.select_reference()

    def select_reference(self, *_):
        key = self.reference_selector.currentData()
        self.reference_path.blockSignals(True)
        self.reference_path.setText(self.reference_options.get(key, {}).get('path', ''))
        self.reference_path.blockSignals(False)
        self.reference_remove_button.setEnabled(key not in BUILTIN_REFERENCES and key is not None)
        self.reference_remove_button.setToolTip('Remove this entry without deleting its FASTA file.' if key not in BUILTIN_REFERENCES else 'Bundled reference entries are retained for existing profiles.')
        self.update_status()

    def reference_path_changed(self, path):
        if self.loading:
            return
        key = self.reference_selector.currentData()
        if key in self.reference_options:
            self.reference_options[key]['path'] = path.strip()
        self.update_status()

    def add_reference(self):
        name, accepted = QInputDialog.getText(self, 'Add reference', 'Reference name:')
        if not accepted:
            return
        name = name.strip()
        if not name or name.casefold() in {item['name'].casefold() for item in self.reference_options.values()}:
            QMessageBox.warning(self, 'Reference not added', 'Enter a unique reference name.')
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Choose reference FASTA', '', 'FASTA (*.fa *.fasta *.fna *.gz);;All files (*)')
        if not path:
            return
        key = new_reference_key(name, self.reference_options)
        self.reference_options[key] = dict(name=name, path=str(Path(path).resolve()))
        self.fill_reference_selector(key)

    def rename_reference(self):
        key = self.reference_selector.currentData()
        old = self.reference_options[key]['name']
        name, accepted = QInputDialog.getText(self, 'Rename reference', 'Reference name:', text=old)
        if not accepted:
            return
        name = name.strip()
        if not name or any(other != key and item['name'].casefold() == name.casefold() for other, item in self.reference_options.items()):
            QMessageBox.warning(self, 'Reference not renamed', 'Enter a unique reference name.')
            return
        self.reference_options[key]['name'] = name
        self.fill_reference_selector(key)

    def remove_reference(self):
        key = self.reference_selector.currentData()
        if key not in BUILTIN_REFERENCES and key in self.reference_options:
            del self.reference_options[key]
            self.fill_reference_selector()

    def browse(self, edit, directory):
        if directory:
            path = QFileDialog.getExistingDirectory(self, 'Choose folder', edit.text())
        else:
            path, _ = QFileDialog.getOpenFileName(self, 'Choose reference', edit.text(), 'FASTA (*.fa *.fasta *.fna *.gz);;All files (*)')
        if path:
            edit.setText(path)

    def reload(self):
        self.loading = True
        self.reference_options = reference_library(self.store.app_paths)
        self.fill_reference_selector()
        for key, edit in self.edits.items():
            edit.setText(self.store.app_paths[key])
        self.refresh_legacy_note()
        self.loading = False
        self.update_status()

    def refresh_legacy_note(self):
        names = ', '.join(self.store.path_overrides)
        self.legacy_note.setText('Preserved custom profile paths: ' + names + '.' if names else '')
        self.legacy_note.setVisible(bool(names))

    def restore_defaults(self):
        self.loading = True
        defaults = self.store.defaults['paths']
        self.reference_options = reference_library(defaults)
        self.fill_reference_selector()
        for key, edit in self.edits.items():
            edit.setText(defaults[key])
        self.loading = False
        self.update_status()

    def collect(self):
        paths = apply_reference_library(self.store.app_paths, self.reference_options)
        for key, edit in self.edits.items():
            paths[key] = edit.text().strip()
        return paths

    def is_dirty(self):
        """True when current editor values differ from the saved state.

        Inputs:
            None; uses instance state.

        Returns:
            True when current editor values differ from the saved state.
        """
        return self.collect() != self.store.app_paths

    def update_status(self, *_):
        """Update status.

        Args:
            _: Event argument intentionally unused by this callback.

        Returns:
            None.
        """
        if self.loading:
            return
        dirty = self.is_dirty()
        self.status.setText("Unsaved app changes" if dirty else "App settings saved")
        self.save_button.setEnabled(dirty)
        self.discard_button.setEnabled(dirty)

    def save(self):
        """Persist shared paths and notify the owner only after a successful write.

        Inputs:
            None; uses instance state.

        Returns:
            True when saving succeeds; False when validation or persistence fails.
        """
        try:
            self.store.save_app_paths(self.collect())
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "App settings were not saved", str(exc))
            return False
        self.reload()
        self.saved.emit()
        return True

    def confirm_pending(self):
        """Protect app edits when navigating away from Settings or closing.

        Inputs:
            None; uses instance state.

        Returns:
            True to continue; False when the user cancels or saving fails.
        """
        if not self.is_dirty():
            return True
        answer = ask_unsaved_settings(self, "Unsaved app settings", "Save changes to shared app paths?")
        if answer == QMessageBox.Save:
            return self.save()
        if answer == QMessageBox.Discard:
            self.reload()
            return True
        return False
