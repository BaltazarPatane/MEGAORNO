"""Read-only Qt models: measurements are formatted only when visible."""
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


def display_value(value):
    if value is None:
        return '—'
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M:%S')
    if isinstance(value, float):
        return f'{value:.3f}'
    return str(value)


class RowsModel(QAbstractTableModel):
    """A small general model for summaries, alerts and manual annotations."""

    def __init__(self, headers=(), rows=(), parent=None):
        super().__init__(parent)
        self.headers = list(headers)
        self.rows = list(rows)

    def replace(self, headers, rows):
        self.beginResetModel()
        self.headers = list(headers)
        self.rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.rows):
            return None
        value = self.rows[index.row()][index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return display_value(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            horizontal = Qt.AlignmentFlag.AlignRight if isinstance(value, (int, float)) else Qt.AlignmentFlag.AlignLeft
            return horizontal | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and section < len(self.headers):
            return self.headers[section]
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None


class MeasurementsModel(QAbstractTableModel):
    """Expose every raw sample without constructing a second formatted table."""

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.unit = '°C/h'

    def set_session(self, session):
        self.beginResetModel()
        self.session = session
        self.endResetModel()

    def refresh(self):
        self.beginResetModel()
        self.endResetModel()

    def set_unit(self, unit):
        self.unit = unit
        self.refresh()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.session is None else len(self.session.registro.muestras)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.session is None else 3 + 2 * len(self.session.registro.canales)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.session is None or index.row() >= self.rowCount():
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return (Qt.AlignmentFlag.AlignLeft if index.column() in (0, 2) else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        registro, perfil = self.session.registro, self.session.perfil
        dt, values = registro.muestras[index.row()]
        col = index.column()
        if col == 0:
            return display_value(dt)
        if col in (1, 2):
            minutes = (dt - registro.muestras[0][0]).total_seconds() / 60
            ideal, stage = perfil.punto(minutes)
            return display_value(ideal) if col == 1 else stage
        channel = registro.canales[(col - 3) // 2]
        if (col - 3) % 2 == 0:
            value = values.get(channel)
        else:
            row = registro.gradientes[index.row()] if index.row() < len(registro.gradientes) else {}
            value = row.get(channel)
            if value is not None and self.unit == '°C/h':
                value *= 60
        return display_value(value)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or self.session is None:
            return None
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        if section < 3:
            return ('Fecha y hora de medición', 'Ideal · °C', 'Etapa prevista')[section]
        channel = self.session.registro.canales[(section - 3) // 2]
        suffix = '°C' if (section - 3) % 2 == 0 else 'Gradiente · '+self.unit
        return f'{self.session.nombre(channel)} · {suffix}'
