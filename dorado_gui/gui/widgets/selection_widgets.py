
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QGridLayout,
    QLayout,
)

try:
    from core.workflow_constants import ICON_SIZE
except ImportError:
    from dorado_api.core.workflow_constants import ICON_SIZE

from core.workflow_constants import BASE_DIR


class SelectCard(QFrame):
    """Selectable card widget used for choosing inputs or workflow steps."""

    def __init__(self, key, title, description, theme="blue", title_size=13):
        """
        Initialize the selectable card widget.

        Args:
            key: Identifier for this card.
            title: Display title text.
            description: Supporting description text.
            theme: Visual theme name used for selected state color.
            title_size: Title font size in pixels.

        Returns:
            None
        """
        super().__init__()

        self.setCursor(Qt.PointingHandCursor)
        self.key = key
        self.theme = theme
        self.setObjectName("card")
        self.setProperty("selected", False)
        self.setFixedHeight(83)

        active_border = "#3b82f6" if theme == "blue" else "#22c55e"
        active_bg = "#ffffff"

        self.setStyleSheet(f"""
            QFrame#card {{
                border: 1.5px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px;
                background-color: #ffffff;
            }}

            QFrame#card[selected="true"] {{
                border: 2px solid {active_border};
                background-color: {active_bg};
            }}
        """)

        container = QWidget()
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setStyleSheet("background: transparent;")

        main = QHBoxLayout(container)
        main.setContentsMargins(6, 4, 6, 4)
        main.setSpacing(6)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(10)
        outer.addWidget(container)

        self.radio = QLabel("○")
        self.radio.setFixedWidth(18)
        self.radio.setAlignment(Qt.AlignCenter)
        self.radio.setStyleSheet("font-size: 16px; color: #9ca3af;")

        icon = QLabel()
        pixmap = QPixmap(self._get_icon_path(key))
        icon.setPixmap(
            pixmap.scaled(
                ICON_SIZE,
                ICON_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        icon.setFixedSize(ICON_SIZE, ICON_SIZE)

        text_layout = QVBoxLayout()
        text_layout.setAlignment(Qt.AlignTop)
        text_layout.setSpacing(3)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-weight: bold; font-size: {title_size}px;"
        )
        
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("color: #6b7280; font-size: 13px;")
        desc_lbl.setWordWrap(True)

        text_layout.addWidget(title_lbl)
        text_layout.addWidget(desc_lbl)

        main.addWidget(self.radio)
        main.addWidget(icon)
        main.addLayout(text_layout, 1)
        icon.setAlignment(Qt.AlignCenter)

    def set_selected(self, selected: bool):
        """
        Update the card selection state.

        Args:
            selected: True if this card is selected, False otherwise.

        Returns:
            None
        """
        self.setProperty("selected", selected)

        active_color = "#3b82f6" if self.theme == "blue" else "#22c55e"

        self.radio.setText("●" if selected else "○")
        self.radio.setStyleSheet(f"""
            font-size: 16px;
            color: {active_color if selected else "#9ca3af"};
        """)

        self.style().polish(self)

    def _get_icon_path(self, key):
        """
        Resolve the icon path for a card key.

        Args:
            key: Card identifier key.

        Returns:
            Path to the corresponding icon file as a string.
        """
        return str(
            BASE_DIR / "icons" / {
                "pod5": "pod5.png",
                "bam": "bam.png",
                "fastq": "fastq.png",
                "basecalling": "basecalling.png",
                "nanotel": "nanotel.png",
                "project": "folder.png",
                "post_analysis": "recalculate.svg",
            }.get(key, "")
        )


class SelectOption(QFrame):
    """A compact option row used in advanced settings."""

    def __init__(self, text):
        """
        Initialize a standalone selectable option row.

        Args:
            text: Option label text.

        Returns:
            None
        """
        super().__init__()
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("""
            background: transparent;
            border: none;
        """)

        self.selected = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.radio = QLabel("○")
        self.radio.setStyleSheet("""
            font-size: 16px;
            color: #9CA3AF;
        """)

        self.label = QLabel(text)
        self.label.setStyleSheet("""
            font-size: 13px;
            font-weight: 400;
            color: #6b7280;
        """)

        layout.addWidget(self.radio)
        layout.addWidget(self.label)

    def set_selected(self, selected):
        """
        Set the option selected state.

        Args:
            selected: True if the option is selected, False otherwise.

        Returns:
            None
        """
        self.selected = selected
        self.radio.setText("●" if selected else "○")
        self.radio.setStyleSheet(f"""
            font-size: 16px;
            color: {"#2563EB" if selected else "#9CA3AF"};
        """)


class SelectionGrid(QWidget):
    """Keep selection cards in-place, wrapping rows before captions are squeezed."""
    def __init__(self, maximum_columns, spacing=16, minimum_card_width=300):
        """Initialize the instance and its dependencies.

        Args:
            maximum_columns: Maximum number of cards in one row.
            spacing: Gap between cards in pixels. Default: 16.
            minimum_card_width: Minimum readable card width in pixels. Default: 300.

        Returns:
            None; initializes the instance.
        """
        super().__init__()
        self.maximum_columns = maximum_columns
        self.minimum_card_width = minimum_card_width
        self.cards = []
        self.columns = 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self.grid.setSizeConstraint(QLayout.SetNoConstraint)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def minimumSizeHint(self):
        """Minimum suggested widget size as QSize.

        Inputs:
            None; uses instance state.

        Returns:
            Minimum suggested widget size as QSize.
        """
        return QSize(0, max((card.minimumHeight() for card in self.cards), default=83))

    def add_card(self, card):
        """Add card.

        Args:
            card: Option card to enable, disable or insert.

        Returns:
            None.
        """
        card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.cards.append(card)
        self._reflow()

    def resizeEvent(self, event):
        """Resizeevent.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        """Wrap cards at their readable width and reserve the resulting height.

        Inputs:
            None; uses instance state.

        Returns:
            None.
        """
        card_width = max(self.minimum_card_width, max((card.minimumSizeHint().width() for card in self.cards), default=0))
        columns = min(self.maximum_columns, max(1, (self.width()+self.grid.spacing()) // (card_width+self.grid.spacing())))
        # Four input cards should wrap into two balanced rows, not a 3+1 layout.
        if self.maximum_columns == 4 and columns == 3: columns = 2
        height = max((card.minimumHeight() for card in self.cards), default=83)
        rows = (len(self.cards)+columns-1)//columns
        self.setFixedHeight(rows*height+max(0, rows-1)*self.grid.spacing())
        if columns == self.columns and self.grid.count() == len(self.cards): return
        self.columns = columns
        while self.grid.count(): self.grid.takeAt(0)
        for column in range(self.maximum_columns): self.grid.setColumnStretch(column, 0)
        for index, card in enumerate(self.cards): self.grid.addWidget(card, index // columns, index % columns)
        for column in range(columns): self.grid.setColumnStretch(column, 1)
