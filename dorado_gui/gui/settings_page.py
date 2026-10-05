"""Qt editor for saved workflow profiles and organism-specific TVR presets.

SettingsStore owns persisted profiles; this page edits a separate draft. TVR
lists live in that draft, while most other values stay in widgets until collect
combines them. Saving activates a profile and emits saved so AppWindow can refresh
its selector and pipeline defaults. Running workers already own their snapshots.
"""
import copy
import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QScrollArea, QFileDialog, QInputDialog,
    QMessageBox, QSizePolicy, QSpinBox, QDoubleSpinBox, QTabWidget,
)

from gui.app_settings_page import AppSettingsPage
from core.sequencing_kits import DORADO_KITS
from core.settings_store import merge_config, parse_patterns, validate_config, write_json
from dorado_workflow.managers.config_manager import organism_nanotel_settings


class SettingsPage(QWidget):
    """Manage profile editing, TVR history, validation feedback and persistence UI.

    State:
        store: Saved profiles and active-profile name.
        draft: Independent configuration carrying staged organism TVR edits.
        profile_name: Profile currently being edited, possibly not yet saved.
        current_org: Configuration key for TVR and numeric analysis controls.
        loading: Guard against change handlers during programmatic updates.
        undo_patterns: Previous TVR lists for the current organism only.

    Signals:
        saved: Emitted after a successful save or deletion; listeners should read
            the updated store rather than retaining a reference to the old draft.
    """

    saved = Signal()

    def __init__(self, store, parent=None):
        """Build the editor and load an independent draft of the active profile.

        Args:
            store: SettingsStore holding validated profiles and handling persistence.
            parent: Optional Qt parent that owns this page.

        The header, organism selector and save actions remain outside the scroll
        area. The central cards switch between two columns and a vertical stack.
        Signal handlers ignore programmatic field updates while loading is true."""
        super().__init__(parent)
        # Share compact body typography across both settings tabs.
        font = self.font()
        font.setPixelSize(13)
        self.setFont(font)
        self.store = store
        # Draft edits must never mutate the saved profile or a running workflow.
        self.loading = True
        self.draft = store.snapshot()
        self.profile_name = store.active
        self.current_org = self.draft["lab_info"]["default_organism"]
        self.undo_patterns = []
        # Scope these styles to this page; dynamic properties select card/button variants.
        self.setObjectName("settingsPage")
        self.setStyleSheet("""
            QWidget#settingsPage { background: #f0f2f5; color: #162238; }
            QWidget#settingsPage QLabel { background: transparent; color: #162238; }
            QWidget#settingsPage QLabel[muted="true"] { color: #748198; }
            QWidget#settingsPage QWidget[card="true"] { background: white; border-radius: 14px; }
            QWidget#settingsPage QPushButton { background: white; color: #2563eb; border: 1px solid #cbd5e1;
                border-radius: 7px; padding: 9px 13px; font-size: 13px; }
            QWidget#settingsPage QPushButton:hover { background: #eff6ff; border-color: #2563eb; }
            QWidget#settingsPage QPushButton[primary="true"] { background: #2563eb; color: white; border-color: #2563eb; }
            QWidget#settingsPage QPushButton:disabled { color: #94a3b8; background: #e8edf5; border-color: #e2e8f0; }
            QWidget#settingsPage QPushButton[link="true"] { border: none; background: transparent; padding: 5px; }
            QWidget#settingsPage QLineEdit, QWidget#settingsPage QComboBox,
            QWidget#settingsPage QSpinBox, QWidget#settingsPage QDoubleSpinBox {
                background: white; color: #162238; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; min-height: 18px; }
            QWidget#settingsPage QLineEdit:focus, QWidget#settingsPage QComboBox:focus { border-color: #2563eb; }
            QWidget#settingsPage QScrollArea { border: none; background: transparent; }
            QWidget#settingsPage QTabWidget::pane { border: none; }
            QWidget#settingsPage QTabBar::tab {
                background: #e8edf5; color: #52627a; padding: 8px 18px;
                border-top-left-radius: 7px; border-top-right-radius: 7px; margin-right: 6px;
            }
            QWidget#settingsPage QTabBar::tab:selected { background: #2563eb; color: white; }
            QWidget#settingsPage QWidget[chip="true"] { background: #f5f7fb; border: 1px solid #dce3ed; border-radius: 6px; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 14)
        root.setSpacing(14)
        root.addWidget(self.label("Settings & Configuration", size=22, bold=True))
        root.addWidget(self.label("Manage profile analysis settings and shared app resources.", muted=True))
        # Profile actions remain visible while the settings cards scroll.
        # Separate persistence scopes: switching tabs never commits either draft.
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.profile_tab = QWidget()
        root = QVBoxLayout(self.profile_tab)
        root.setContentsMargins(0, 12, 0, 0)
        root.setSpacing(12)
        self.tabs.addTab(self.profile_tab, "Profile settings")
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.label("Profile", bold=True))
        self.profile = QComboBox()
        self.profile.setStyleSheet("""
            QComboBox { background: white; color: #2563eb; }
            QComboBox QAbstractItemView {
                background: white; color: #2563eb;
                selection-background-color: white; selection-color: #2563eb;
            }
            QComboBox QAbstractItemView::item:selected { background: white; color: #2563eb; }
        """)
        self.profile.setMinimumWidth(140)
        toolbar.addWidget(self.profile, 1)
        toolbar.addWidget(self.button("Create new profile", self.save_as))
        self.delete_button = self.button("Delete profile", self.profile_action)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.button("Import", self.import_profile))
        toolbar.addWidget(self.button("Export", self.export_profile))
        # Give the selector and every profile action equal space and height.
        for index in range(1, toolbar.count()):
            action = toolbar.itemAt(index).widget()
            action.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            action.setMinimumWidth(64)
            action.setFixedHeight(36)
            toolbar.setStretch(index, 1)
        root.addLayout(toolbar)

        # Keep organism context above the scroll area to avoid editing the wrong preset.
        organism_card, organism_layout = self.card()
        organism_layout.setContentsMargins(14, 8, 14, 8)
        organism_layout.setSpacing(0)
        organism_row = QHBoxLayout()
        organism_row.setSpacing(10)
        organism_row.addWidget(self.label("Organism", bold=True, size=15))
        self.organism = QComboBox()
        for text, key in (("Mouse", "mouse"), ("Human", "human"), ("Zebrafish", "zebrafish")):
            self.organism.addItem(text, key)
        self.organism.setMinimumWidth(180)
        self.organism.setFixedHeight(30)
        self.organism.setStyleSheet("QComboBox { padding: 3px 8px; min-height: 0; }")
        self.organism.setAccessibleName("Organism")
        organism_row.addWidget(self.organism)
        self.scope = self.label("", muted=True)
        organism_row.addWidget(self.scope, 1)
        self.organism.setToolTip("Also sets the default organism for new runs with this profile.")
        organism_layout.addLayout(organism_row)
        root.addWidget(organism_card)

        # Only the central editor scrolls; the footer remains accessible at any height.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)
        self.columns = QGridLayout()
        self.columns.setSpacing(14)
        self.left = QWidget()
        left_layout = QVBoxLayout(self.left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(14)
        # Official Dorado choices; reload also retains IDs from existing profiles.
        kit_card, kit_layout = self.card()
        kit_layout.setContentsMargins(18, 16, 18, 8)
        kit_row = QVBoxLayout()
        kit_row.setSpacing(6)
        kit_title = self.label("Sequencing kit", size=17, bold=True)
        kit_title.setFixedHeight(30)
        kit_row.addWidget(kit_title)
        kit_row.addSpacing(8)
        self.kit = QComboBox()
        self.kit.setEditable(False)
        self.kit.setMaxVisibleItems(12)
        self.kit.setInsertPolicy(QComboBox.NoInsert)
        self.kit.addItems(DORADO_KITS)
        self.kit.setAccessibleName("Sequencing kit")
        self.kit.setFixedHeight(30)
        self.kit.setStyleSheet("QComboBox { padding: 3px 8px; min-height: 0; }")
        self.kit.setToolTip("Barcode demultiplexing kit for all organisms in this profile. Choose a kit supported by your installed Dorado version.")
        kit_row.addWidget(self.kit, 1)
        kit_layout.addLayout(kit_row)
        kit_layout.setSpacing(6)
        kit_layout.addWidget(self.label(
            "Barcode demultiplexing kit for all organisms in this profile.\n"
            "Choose a Dorado barcoding kit supported by your installed version.", muted=True))
        left_layout.addWidget(kit_card)

        # Legacy/imported custom paths remain visible until explicitly replaced.
        self.custom_paths_card, custom_layout = self.card("Custom profile paths")
        self.custom_paths_label = self.label("", muted=True)
        custom_layout.addWidget(self.custom_paths_label)
        custom_layout.addWidget(self.button("Use app paths", self.use_app_paths))
        left_layout.addWidget(self.custom_paths_card)

        # TVR chips edit the organism list directly in the draft, with full-list Undo.
        self.tvr_card, tvr_layout = self.card()
        tvr_layout.setSpacing(8)
        tvr_header = QHBoxLayout()
        tvr_header.setSpacing(10)
        tvr_title = self.label("TVR patterns", size=17, bold=True)
        tvr_title.setFixedHeight(30)
        tvr_title.setToolTip("Edit the preset used in NanoTel Preset mode.")
        tvr_header.addWidget(tvr_title)
        self.org_badge = self.label("", bold=True)
        self.org_badge.setStyleSheet("background: #edf3ff; color: #2563eb; padding: 3px 8px; border-radius: 5px;")
        tvr_header.addWidget(self.org_badge)
        tvr_header.addStretch()
        restore = self.button("Restore organism defaults", self.restore_patterns, link=True)
        tvr_header.addWidget(restore)
        tvr_layout.addLayout(tvr_header)
        tvr_layout.addWidget(self.label("Used when Preset mode is selected on Pipeline Setup.", muted=True))
        add_row = QHBoxLayout()
        self.sequence = QLineEdit()
        self.sequence.setPlaceholderText("Enter sequence, e.g. TCAGGG")
        add_row.addWidget(self.sequence, 1)
        add_row.addWidget(self.button("+ Add", self.add_patterns, primary=True))
        self.sequence.returnPressed.connect(self.add_patterns)
        tvr_layout.addLayout(add_row)
        tvr_layout.addWidget(self.label("A, C, G, T · duplicates prevented · minimum 5 bases", muted=True))
        self.error = self.label("")
        self.error.setStyleSheet("color: #b91c1c; background: transparent;")
        self.error.hide()
        tvr_layout.addWidget(self.error)
        self.pattern_grid = QGridLayout()
        self.pattern_grid.setSpacing(8)
        tvr_layout.addLayout(self.pattern_grid)
        actions = QHBoxLayout()
        self.count = self.label("", muted=True)
        actions.addWidget(self.count, 1)
        self.undo_button = self.button("Undo", self.undo_remove, link=True)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.button("Paste multiple", self.paste_multiple, link=True))
        tvr_layout.addLayout(actions)
        tvr_layout.addStretch()
        self.columns.addWidget(self.left, 0, 0)
        self.columns.addWidget(self.tvr_card, 0, 1)
        self.columns.setColumnStretch(0, 4)
        self.columns.setColumnStretch(1, 6)
        body_layout.addLayout(self.columns)

        # Keys match NanoTel settings; edits are stored under the selected organism.
        analysis_card, analysis_layout = self.card("Analysis defaults")
        analysis_layout.setSpacing(8)
        self.analysis_scope = self.label("", muted=True)
        analysis_layout.addWidget(self.analysis_scope)
        fields = QGridLayout()
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(6)
        self.analysis_fields = {}
        # -1 is a UI-only sentinel for optional minimum-length filtering (JSON null).
        specs = (
            ("min_read_length", "Minimum total read length (bp)", -1),
            ("short_telomere_threshold_bp", "Short telomere threshold (bp)", 1),
            ("display_max_edge_distance", "Minimum read-length margin (bp)", 0),
            ("max_telomere_start", "Latest allowed telomere start (bp)", 0),
            ("min_density", "Minimum telomeric repeat density (%)", 0),
        )
        for row, (key, title, minimum) in enumerate(specs):
            if key == "min_density":
                control = QDoubleSpinBox()
                control.setDecimals(4)
                control.setRange(0, 100)
                control.setSingleStep(1)
            else:
                control = QSpinBox()
                control.setRange(minimum, 2_147_483_647)
                if key == "min_read_length":
                    control.setSpecialValueText("Disabled")
            control.setAccessibleName(title)
            control.setFixedWidth(140)
            control.setFixedHeight(30)
            control.setStyleSheet("QSpinBox, QDoubleSpinBox { padding: 3px 8px; min-height: 0; }")
            control.valueChanged.connect(self.mark_dirty)
            fields.addWidget(self.label(title), row, 0)
            fields.addWidget(control, row, 1)
            self.analysis_fields[key] = control
        self.analysis_fields["display_max_edge_distance"].setToolTip(
            "Read length must exceed the running median telomere length by more than this value. The existing untrimmed-read adjustment still applies.")
        analysis_layout.addLayout(fields)
        # Absorb spare column height inside this card so both columns end together.
        analysis_layout.addStretch()
        left_layout.addWidget(analysis_card, 1)

        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Persistent save/discard actions reflect both field edits and pending activation.
        footer, footer_layout = self.card()
        footer_row = QHBoxLayout()
        self.status = self.label("Profile saved", muted=True)
        footer_row.addWidget(self.status, 1)
        self.discard_button = self.button("Discard changes", self.discard)
        self.save_button = self.button("Save profile", self.save, primary=True)
        footer_row.addWidget(self.discard_button)
        footer_row.addWidget(self.save_button)
        footer_layout.addLayout(footer_row)
        root.addWidget(footer)

        # Reload uses loading to suppress change handlers during field updates.
        self.kit.currentTextChanged.connect(self.mark_dirty)
        self.organism.currentIndexChanged.connect(self.change_organism)
        self.profile.currentTextChanged.connect(self.change_profile)
        self.sequence.textChanged.connect(self.mark_dirty)
        self.app_settings = AppSettingsPage(store, self)
        self.tabs.addTab(self.app_settings, "App settings")
        self.app_settings.saved.connect(self.app_paths_saved)
        self.reload()

    @staticmethod
    def label(text, muted=False, bold=False, size=13):
        """Return a wrapping label with optional muted color, bold weight and pixel size."""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setProperty("muted", muted)
        font = label.font()
        font.setPixelSize(size)
        font.setBold(bold)
        label.setFont(font)
        return label

    @staticmethod
    def button(text, callback, primary=False, link=False):
        """Return a styled action button connected to callback; flags select its appearance."""
        button = QPushButton(text)
        button.setProperty("primary", primary)
        button.setProperty("link", link)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def card(self, title="", subtitle=""):
        """Return a white card widget and its vertical layout, optionally with headings."""
        widget = QWidget()
        widget.setProperty("card", True)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        if title:
            layout.addWidget(self.label(title, size=17, bold=True))
        if subtitle:
            layout.addWidget(self.label(subtitle, muted=True))
        return widget, layout

    def field(self, layout, title, widget):
        """Append a label and horizontally expanding, fixed-height control to layout."""
        layout.addWidget(self.label(title, bold=True))
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(widget)

    def reload(self):
        """Populate controls from the current draft without triggering user-edit handlers.

        Rebuild saved profile/kit choices, reset transient TVR entry and undo state,
        then recompute whether the displayed draft differs from the saved state.
        This does not read the settings file or replace the draft itself."""
        self.loading = True
        is_default = self.profile_name == "Lab default"
        self.delete_button.setText("Restore profile defaults" if is_default else "Delete profile")
        self.delete_button.setEnabled(is_default or self.profile_name in self.store.profiles)
        self.delete_button.setToolTip("Stage the original profile settings. Save profile to apply." if is_default else "Delete this saved profile.")
        self.profile.clear()
        self.profile.addItems(self.store.profiles)
        self.profile.setCurrentText(self.profile_name)
        c = self.draft
        self._using_app_paths = c["paths"] == self.store.app_paths
        self.refresh_path_scope()
        self.kit.clear()
        # Preserve saved/imported IDs while offering the official catalog as closed choices.
        saved_kits = {profile["demuxing"]["kit_name"] for profile in self.store.profiles.values()
                      if profile["demuxing"].get("kit_name")}
        if c["demuxing"].get("kit_name"):
            saved_kits.add(c["demuxing"]["kit_name"])
        self.kit.addItems(sorted(set(DORADO_KITS) | saved_kits))
        self.kit.setCurrentText(c["demuxing"].get("kit_name") or "")
        self.current_org = c["lab_info"]["default_organism"]
        self.organism.setCurrentIndex(self.organism.findData(self.current_org))
        self.load_analysis_defaults()
        self.undo_patterns.clear()
        self.sequence.clear()
        self.error.hide()
        self.render_patterns()
        self.loading = False
        self.mark_dirty()

    def collect(self):
        """Return a deep copy of the draft overlaid with the current form values.

        Preserve configuration keys that have no visible editor, including motifs.
        Translate the minimum-length Disabled sentinel to None.
        This method neither validates the entire configuration nor persists it."""
        c = copy.deepcopy(self.draft)
        c["demuxing"]["kit_name"] = self.kit.currentText().strip() or None
        c["lab_info"]["default_organism"] = self.current_org
        # Write only changed values into this organism's override dictionary.
        # Legacy profiles keep their profile-wide fallback without becoming dirty.
        effective = organism_nanotel_settings(self.draft, self.current_org)
        for key, control in self.analysis_fields.items():
            value = control.value()
            # Merely opening a rounded spin box must not alter imported precision.
            if value == self._loaded_analysis_values[key]:
                continue
            if key == "min_density":
                value = round(value / 100, 6)
            value = None if key == "min_read_length" and value == -1 else value
            if value != effective[key]:
                overrides = c["organism_specific"][self.current_org].setdefault("nanotel", {})
                overrides[key] = value
                if key == "min_density":
                    overrides["density_threshold"] = value
        return c

    def refresh_path_scope(self):
        """Show preserved resource exceptions without mixing shared fields into profiles."""
        custom = self.draft["paths"] != self.store.app_paths
        self.custom_paths_card.setVisible(custom)
        paths = self.draft["paths"]
        self.custom_paths_label.setText(
            "Preserved from an existing or imported profile. App path changes do not affect these paths.\n"
            + "\n".join(f"{name.title()}: {path}" for name, path in paths["references"].items())
            + f'\nModel: {paths["dorado_model"]}\nOutput: {paths["default_output_base"]}')
        self.app_settings.refresh_legacy_note()

    def use_app_paths(self):
        """Stage removal of this profile's custom paths; Save profile applies it."""
        self.draft["paths"] = copy.deepcopy(self.store.app_paths)
        self._using_app_paths = True
        self.refresh_path_scope()
        self.mark_dirty()

    def app_paths_saved(self):
        """Refresh shared paths in the profile draft without saving its analysis edits."""
        if self._using_app_paths:
            self.draft["paths"] = copy.deepcopy(self.store.app_paths)
        self.refresh_path_scope()
        self.mark_dirty()
        self.saved.emit()

    def load_analysis_defaults(self):
        """Display the current organism's defaults; caller suppresses dirty signals."""
        defaults = organism_nanotel_settings(self.draft, self.current_org)
        for key, control in self.analysis_fields.items():
            value = defaults[key]
            control.setValue(-1 if value is None else value * 100 if key == "min_density" else value)
        self._loaded_analysis_values = {key: control.value() for key, control in self.analysis_fields.items()}
        self.analysis_scope.setText(f"{self.organism.currentText()} defaults in this profile; adjustable for each run.")

    def is_dirty(self):
        """Return whether edits, pending sequence input or profile activation need saving.

        Merely choosing a different saved profile in this editor is a pending
        activation until Save profile commits it to the store."""
        return bool(self.sequence.text().strip()) or self.profile_name != self.store.active or self.collect() != self.store.profiles.get(self.profile_name)

    def mark_dirty(self, *_):
        """Refresh the save/discard state; ignore loading updates and Qt signal arguments."""
        if self.loading:
            return
        dirty = self.is_dirty()
        self.status.setText("●  Unsaved profile changes" if dirty else "Profile saved")
        self.save_button.setEnabled(dirty)
        self.discard_button.setEnabled(dirty)

    def patterns(self):
        """Return the mutable TVR list for the currently edited organism.

        Initialize a missing organism list from the profile-wide fallback using
        a copy. An explicitly empty organism list remains empty."""
        organism = self.draft["organism_specific"][self.current_org]
        return organism.setdefault("tvr_patterns", list(self.draft["nanotel"]["tvr_patterns"]))

    def render_patterns(self):
        """Rebuild sequence chips, organism labels, count and Undo availability.

        Each chip captures its own sequence for removal. Existing widgets are
        hidden immediately and scheduled for deletion through the Qt event loop."""
        while self.pattern_grid.count():
            widget = self.pattern_grid.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        for index, pattern in enumerate(self.patterns()):
            chip = QWidget()
            chip.setProperty("chip", True)
            row = QHBoxLayout(chip)
            row.setContentsMargins(10, 1, 3, 1)
            sequence = self.label(pattern)
            sequence.setStyleSheet("font-family: Consolas, monospace; background: transparent;")
            row.addWidget(sequence, 1)
            # Capture pattern now, rather than using the loop variable at click time.
            remove = self.button("×", lambda checked=False, p=pattern: self.remove_pattern(p), link=True)
            remove.setAccessibleName(f"Remove {pattern}")
            remove.setToolTip(f"Remove {pattern}")
            row.addWidget(remove)
            self.pattern_grid.addWidget(chip, index // 2, index % 2)
        self.pattern_grid.setColumnStretch(0, 1)
        self.pattern_grid.setColumnStretch(1, 1)
        self.count.setText(f"{len(self.patterns())} patterns")
        self.org_badge.setText(self.organism.currentText())
        self.scope.setText(f"TVR patterns and analysis defaults apply only to {self.organism.currentText()} in this profile.")
        self.undo_button.setEnabled(bool(self.undo_patterns))

    def add_patterns(self, *_ , text=None):
        """Validate and stage unique sequences from text or the inline entry field.

        text is used by bulk paste; omitted text uses the inline entry. Positional
        arguments from Qt signals are ignored. Invalid or entirely duplicate input
        displays an inline error without changing the preset. Successful additions
        save an undo snapshot. Only an inline addition clears the inline entry;
        bulk paste preserves any separate unfinished input."""
        try:
            patterns = parse_patterns(self.sequence.text() if text is None else text)
            if not patterns:
                raise ValueError("Enter at least one sequence.")
            fresh = [p for p in patterns if p not in self.patterns()]
            if not fresh:
                raise ValueError("These sequences are already in this preset.")
            self.undo_patterns.append(list(self.patterns()))
            self.patterns().extend(fresh)
            if text is None:
                self.sequence.clear()
            self.error.hide()
            self.render_patterns()
            self.mark_dirty()
        except ValueError as exc:
            self.error.setText(str(exc))
            self.error.show()

    def remove_pattern(self, pattern):
        """Remove an existing sequence from this organism, preserving an undo snapshot."""
        self.undo_patterns.append(list(self.patterns()))
        self.patterns().remove(pattern)
        self.render_patterns()
        self.mark_dirty()

    def undo_remove(self):
        """Restore the previous TVR-list snapshot for the current organism.

        Despite the historical method name, Undo also reverses additions and
        restoring defaults. History is cleared when the organism or draft reloads."""
        if self.undo_patterns:
            self.draft["organism_specific"][self.current_org]["tvr_patterns"] = self.undo_patterns.pop()
            self.render_patterns()
            self.mark_dirty()

    def paste_multiple(self):
        """Collect multiline sequence input and pass it through the shared add validation."""
        text, ok = QInputDialog.getMultiLineText(self, "Add TVR patterns", "Paste sequences separated by lines, spaces, commas or semicolons:")
        if ok:
            self.add_patterns(text=text)

    def restore_patterns(self):
        """Stage the bundled defaults for this organism, preserving the previous list for Undo."""
        self.undo_patterns.append(list(self.patterns()))
        self.draft["organism_specific"][self.current_org]["tvr_patterns"] = list(self.store.defaults["organism_specific"][self.current_org]["tvr_patterns"])
        self.render_patterns()
        self.mark_dirty()

    def change_organism(self, *_):
        """Preserve current form edits before displaying another organism preset.

        current_org still identifies the previous organism when the combo signal
        fires, so collect stores its analysis defaults before
        switching keys. Load the new organism's numeric defaults, keep profile-wide
        controls intact, and reset sequence undo history."""
        if self.loading:
            return
        # Resolve inline input against its original organism before switching.
        # Invalid input stays visible, and the selector returns to that organism.
        if self.sequence.text().strip():
            self.add_patterns()
            if self.sequence.text().strip():
                self.organism.blockSignals(True)
                self.organism.setCurrentIndex(self.organism.findData(self.current_org))
                self.organism.blockSignals(False)
                return
        self.draft = self.collect()
        self.current_org = self.organism.currentData()
        self.loading = True
        self.load_analysis_defaults()
        self.loading = False
        self.undo_patterns.clear()
        self.error.hide()
        self.render_patterns()
        self.mark_dirty()

    def confirm_pending(self):
        """Resolve both independent drafts before leaving the settings screen."""
        return self.confirm_profile_pending() and self.app_settings.confirm_pending()

    def confirm_profile_pending(self):
        """Resolve pending changes and return whether navigation may continue.

        Save returns the persistence result, Discard restores the active saved
        profile, and Cancel returns False. Called before navigation, import,
        profile switching and application close by this page or its owner."""
        if not self.is_dirty():
            return True
        answer = QMessageBox.question(self, "Unsaved settings", "Save profile changes before continuing?",
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Save:
            return self.save()
        if answer == QMessageBox.Discard:
            self.discard()
            return True
        return False

    def change_profile(self, name):
        """Stage the named saved profile after resolving edits to the current draft.

        Cancel restores the previous combo selection without emitting another
        selection signal. Choosing a profile here does not immediately activate it."""
        if self.loading or not name:
            return
        if not self.confirm_profile_pending():
            self.profile.blockSignals(True)
            self.profile.setCurrentText(self.profile_name)
            self.profile.blockSignals(False)
            return
        self.profile_name = name
        self.draft = copy.deepcopy(self.store.profiles[name])
        self.reload()

    def save(self):
        """Validate, persist and activate the edited profile; return True on success.

        Process pending inline sequence input first. The store performs complete
        validation and atomic persistence. On failure the draft remains editable;
        on success reload and notify the main window through saved."""
        try:
            if self.sequence.text().strip():
                self.add_patterns()
                if self.sequence.text().strip():
                    return False
            self.store.commit(self.profile_name, self.collect())
            self.draft = self.store.snapshot()
            self.reload()
            self.saved.emit()
            return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Settings were not saved", str(exc))
            return False

    def discard(self):
        """Restore the active saved profile and clear staged edits and transient TVR state."""
        self.profile_name = self.store.active
        self.draft = self.store.snapshot()
        self.reload()

    def profile_action(self):
        """Restore the protected default profile, or delete a selected custom profile."""
        if self.profile_name == "Lab default":
            self.restore_profile_defaults()
        else:
            self.delete_profile()

    def restore_profile_defaults(self):
        """Stage bundled Lab default values for all organisms while preserving paths.

        Save profile applies the reset; Discard restores the saved profile.
        Shared app settings and custom resource paths are outside this action.
        """
        if self.profile_name != "Lab default":
            return
        paths = copy.deepcopy(self.draft["paths"])
        self.draft = copy.deepcopy(self.store.defaults)
        self.draft["paths"] = paths
        self.reload()

    def delete_profile(self):
        """Confirm and delete the selected saved profile, except Lab default.

        The confirmation includes pending-edit loss and active-profile fallback.
        Persistence failure leaves the editor intact. After success, reload the
        active profile and notify the main window to refresh its profile choices."""
        name = self.profile_name
        if name == "Lab default" or name not in self.store.profiles:
            return
        message = f'Delete profile "{name}"? This cannot be undone.'
        if self.collect() != self.store.profiles[name] or self.sequence.text().strip():
            message += "\nUnsaved changes to this profile will also be discarded."
        if name == self.store.active:
            message += '\nThe active profile will switch to "Lab default".'
        answer = QMessageBox.question(self, "Delete profile", message,
                                      QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if answer != QMessageBox.Yes:
            return
        try:
            self.store.delete(name)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Profile was not deleted", str(exc))
            return
        self.discard()
        self.saved.emit()

    def save_as(self):
        """Create and activate a uniquely named profile from the current form values.

        Reuse save for validation and persistence. If saving fails, restore the
        previous editor name so further edits still refer to the original draft."""
        name, ok = QInputDialog.getText(self, "Create new profile", "New profile name:")
        if not ok:
            return
        name = name.strip()
        if name in self.store.profiles:
            QMessageBox.warning(self, "Profile exists", "Choose a different name to preserve the existing profile.")
            return
        previous = self.profile_name
        self.profile_name = name
        if not self.save():
            self.profile_name = previous

    def import_profile(self):
        """Validate a JSON configuration and stage it under a new profile name.

        Missing configuration fields inherit bundled defaults. Existing names
        cannot be overwritten by import. The imported draft is added to the combo
        temporarily and requires Save profile before it becomes persistent."""
        if not self.confirm_profile_pending():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import configuration", "", "JSON configuration (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            defaults = copy.deepcopy(self.store.defaults)
            defaults["paths"] = copy.deepcopy(self.store.app_paths)
            config = merge_config(defaults, data)
            validate_config(config)
            name, ok = QInputDialog.getText(self, "Import profile", "New profile name:", text=Path(path).stem)
            if not ok:
                return
            name = name.strip()
            self.store.validate_name(name)
            if name in self.store.profiles:
                raise ValueError("That profile name already exists. Choose another name.")
            # Import is staged: the store and active run profile remain unchanged.
            self.profile_name, self.draft = name, config
            self.reload()
            self.profile.blockSignals(True)
            self.profile.addItem(name)
            self.profile.setCurrentText(name)
            self.profile.blockSignals(False)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Could not import configuration", str(exc))

    def export_profile(self):
        """Validate and write the collected configuration to a chosen JSON file.

        Export includes staged form edits and TVR patterns already added to the
        list, but not unsubmitted sequence text. It does not activate or save the
        profile in the profile store."""
        try:
            config = self.collect()
            validate_config(config)
            path, _ = QFileDialog.getSaveFileName(self, "Export current configuration", "configuration.json", "JSON configuration (*.json)")
            if path:
                write_json(path, config)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Could not export configuration", str(exc))

    def resizeEvent(self, event):
        """Reposition existing cards only when crossing the 1000-pixel page-width breakpoint."""
        super().resizeEvent(event)
        stacked = self.width() < 1000
        if getattr(self, "_stacked", None) != stacked:
            self._stacked = stacked
            self.columns.removeWidget(self.left)
            self.columns.removeWidget(self.tvr_card)
            self.columns.addWidget(self.left, 0, 0)
            self.columns.addWidget(self.tvr_card, 1 if stacked else 0, 0 if stacked else 1)
            self.columns.setColumnStretch(1, 0 if stacked else 6)
