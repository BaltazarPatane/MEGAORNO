"""Treatment recipe, statistics, raw measurements and acquisition notices."""
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QDateTime
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateTimeEdit, QDialog,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTableView, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from models import Perfil, Sesion, exportar_controladores, fecha_local, numero, perfil_desde_excel
from .table_models import MeasurementsModel, RowsModel, display_value


PROFILE_FIELDS = (
    ('inicio', 'Temperatura inicial', '°C'),
    ('objetivo', 'Temperatura objetivo', '°C'),
    ('final', 'Temperatura final', '°C'),
    ('subida', 'Gradiente de ascenso', '°C/h'),
    ('bajada', 'Gradiente de descenso', '°C/h'),
    ('mantenimiento', 'Mantenimiento', 'min'),
    ('inferior', 'Límite inferior de banda', '°C'),
    ('superior', 'Límite superior de banda', '°C'),
    ('desfase', 'Inicio desde primera muestra', 'min'),
    ('hueco_max', 'Hueco máximo entre muestras', 'min'),
)


def label(text, name='muted'):
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def card():
    widget = QFrame()
    widget.setObjectName('card')
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return widget, layout


def table(model):
    widget = QTableView()
    widget.setModel(model)
    widget.setAlternatingRowColors(True)
    widget.setShowGrid(False)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    widget.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    widget.verticalHeader().setVisible(False)
    widget.verticalHeader().setDefaultSectionSize(38)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    widget.horizontalHeader().setDefaultSectionSize(150)
    widget.horizontalHeader().setMinimumSectionSize(90)
    widget.horizontalHeader().setStretchLastSection(True)
    return widget


def profile_from_fields(values):
    """Parse editable decimal-comma fields and apply the shared recipe contract."""
    profile = Perfil(**{key: numero(values[key]) for key, _, _ in PROFILE_FIELDS})
    profile.validar()
    return profile


def build_manual_event(session, timestamp, zones, operator='', note=''):
    """Snapshot the last sample at/before an event, preserving invalid readings."""
    registro, profile = session.registro, session.perfil
    if not registro.muestras:
        raise ValueError('Se necesita al menos una muestra para registrar una incidencia.')
    timestamp = fecha_local(timestamp)
    if len(zones) != 6:
        raise ValueError('La bitácora utiliza seis zonas.')
    parsed = [None if value is None or str(value).strip() == '' else numero(value) for value in zones]
    if any(value is not None and not 0 <= value <= 100 for value in parsed):
        raise ValueError('Los porcentajes de las zonas deben estar entre 0 y 100.')
    # Only the latest explicit observation of each channel counts.  An explicit
    # None breaks validity; an absent channel does not overwrite its prior sample.
    latest = {}
    for observed, values in registro.muestras:
        if observed > timestamp:
            break
        for channel, value in values.items():
            latest[channel] = observed, value
    snapshot = {
        channel: latest[channel][1]
        for channel in registro.canales
        if channel in latest and 0 <= (timestamp - latest[channel][0]).total_seconds() / 60 <= profile.hueco_max
    }
    ideal, _ = profile.punto((timestamp - registro.muestras[0][0]).total_seconds() / 60)
    return dict(fecha=timestamp.isoformat(sep=' '), zonas=parsed, operador=operator.strip(),
                nota=note.strip(), ideal=round(ideal, 4), temperaturas=snapshot)


class ProfilePage(QWidget):
    profile_applied = Signal(object)

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session or Sesion()
        self.fields = {}
        self._loaded_profile = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(180)
        self._preview_timer.timeout.connect(self._update_preview)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)
        layout.addWidget(label('Perfil ideal', 'pageTitle'))
        layout.addWidget(label('Definí la referencia de temperatura y los límites del tratamiento.'))
        form_card, form_layout = card()
        form_layout.addWidget(label('Receta del tratamiento', 'sectionTitle'))
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)
        for index, (key, title, unit) in enumerate(PROFILE_FIELDS):
            group, row = index // 5, index % 5
            field = QLineEdit()
            field.setObjectName('profile_' + key)
            field.setMinimumWidth(95)
            field.setMaximumWidth(135)
            field.setAccessibleName(f'{title} ({unit})')
            field.textChanged.connect(lambda _text: self._preview_timer.start())
            field_box = QHBoxLayout()
            field_box.setSpacing(8)
            field_box.addWidget(field)
            field_box.addWidget(label(unit))
            grid.addWidget(QLabel(title), row, group * 2)
            grid.addLayout(field_box, row, group * 2 + 1)
            self.fields[key] = field
        form_layout.addLayout(grid)
        actions = QHBoxLayout()
        self.apply_button = QPushButton('Aplicar perfil')
        self.apply_button.setProperty('primary', True)
        self.apply_button.clicked.connect(self.apply_profile)
        import_button = QPushButton('Importar receta Excel')
        import_button.clicked.connect(self.import_profile)
        actions.addWidget(self.apply_button)
        actions.addWidget(import_button)
        actions.addStretch()
        form_layout.addLayout(actions)
        self.validation_label = label('')
        form_layout.addWidget(self.validation_label)
        layout.addWidget(form_card)
        preview_card, preview_layout = card()
        preview_layout.addWidget(label('Vista previa del programa', 'sectionTitle'))
        self.figure = Figure(figsize=(9, 2.7), dpi=100, layout='constrained', facecolor='white')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(255)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.canvas)
        self.timing_label = label('')
        preview_layout.addWidget(self.timing_label)
        layout.addWidget(preview_card)
        layout.addWidget(label('El mantenimiento programado comienza al alcanzar el objetivo ideal. La racha medida en banda se consulta en Estadísticas.'))
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._load_profile(self.session.perfil)

    def set_session(self, session):
        self.session = session
        self._load_profile(session.perfil)

    def refresh(self):
        if asdict(self.session.perfil) != self._loaded_profile:
            self._load_profile(self.session.perfil)

    def _load_profile(self, profile):
        self._loaded_profile = asdict(profile)
        for key, value in asdict(profile).items():
            self.fields[key].setText(str(value).removesuffix('.0'))
        self._preview_timer.stop()
        self._update_preview()

    def _read_profile(self):
        return profile_from_fields({key: field.text() for key, field in self.fields.items()})

    def _update_preview(self):
        try:
            profile = self._read_profile()
        except (ValueError, TypeError) as exc:
            self.validation_label.setText(str(exc))
            self.validation_label.setStyleSheet('color: #b05236;')
            self.apply_button.setEnabled(False)
            return
        self.apply_button.setEnabled(True)
        modified = asdict(profile) != asdict(self.session.perfil)
        self.validation_label.setText('Vista previa · cambios pendientes de aplicar.' if modified else 'Perfil aplicado a la sesión.')
        self.validation_label.setStyleSheet('color: #52748a;' if modified else 'color: #397e62;')
        up, hold, down = profile.tiempos
        start = profile.desfase
        times = [start, start + up, start + up + hold, start + up + hold + down]
        temps = [profile.inicio, profile.objetivo, profile.objetivo, profile.final]
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.axhspan(profile.inferior, profile.superior, color='#75b79b', alpha=.14, label='Banda de mantenimiento')
        axis.plot(times, temps, color='#216890', linewidth=2.1, marker='o', markersize=4, label='Temperatura ideal')
        for index, (duration, title) in enumerate(zip((up, hold, down), ('Ascenso', 'Mantenimiento', 'Descenso'))):
            if duration > 0:
                axis.axvspan(times[index], times[index + 1], color=('#e8f1f7', '#e9f4ee', '#f1f3f6')[index], alpha=.45, zorder=-1)
                axis.text((times[index] + times[index + 1]) / 2, 1.01, title, transform=axis.get_xaxis_transform(), ha='center', fontsize=8, color='#647787')
        axis.set_xlabel('Minutos desde la primera muestra', fontsize=9, color='#647787')
        axis.set_ylabel('Temperatura · °C', fontsize=9, color='#647787')
        axis.grid(True, color='#e4eaee', linewidth=.6)
        axis.tick_params(labelsize=8, colors='#647787')
        axis.spines[['top', 'right']].set_visible(False)
        for spine in ('left', 'bottom'):
            axis.spines[spine].set_color('#dce4e9')
        axis.legend(loc='lower right', fontsize=8, frameon=False)
        self.canvas.draw_idle()
        self.timing_label.setText(f'Ascenso {up:.2f} min  ·  Mantenimiento {hold:.2f} min  ·  Descenso {down:.2f} min  ·  Total {up + hold + down:.2f} min\nRampas: +{profile.subida / 60:g} y −{profile.bajada / 60:g} °C/min. Inicio: minuto {start:g}.')

    def apply_profile(self):
        try:
            profile = self._read_profile()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Revisá el perfil', str(exc))
            return
        self.profile_applied.emit(profile)
        self._update_preview()

    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Importar receta', '', 'Recetas Excel (*.xlsx *.xlsm)')
        if not path:
            return
        try:
            profile = perfil_desde_excel(path)
        except Exception as exc:
            QMessageBox.warning(self, 'No se pudo importar la receta', str(exc))
            return
        for key, value in asdict(profile).items():
            self.fields[key].setText(str(value).removesuffix('.0'))
        self._preview_timer.stop()
        self._update_preview()


class StatisticsPage(QWidget):
    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session or Sesion()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        heading.addWidget(label('Estadísticas', 'pageTitle'))
        heading.addStretch()
        heading.addWidget(label('Gradiente'))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(['°C/h', '°C/min'])
        self.unit_combo.currentTextChanged.connect(self.refresh)
        heading.addWidget(self.unit_combo)
        layout.addLayout(heading)
        self.summary_label = label('')
        layout.addWidget(self.summary_label)
        self.model = RowsModel(parent=self)
        self.table = table(self.model)
        layout.addWidget(self.table, 1)
        layout.addWidget(label('Última válida siempre indica la fecha de esa medición. Racha en banda: mayor intervalo continuo con ambos extremos válidos dentro de la banda, sin interpolación. Una lectura inválida o un hueco excesivo interrumpe la racha.'))
        self.refresh()

    def set_session(self, session):
        self.session = session
        self.refresh()

    def refresh(self, *_):
        summary, _alerts = self.session.analisis()
        unit = self.unit_combo.currentText()
        factor = 60 if unit == '°C/h' else 1
        headers = ['Canal', 'Última válida · °C', 'Fecha última válida', 'Mínima · °C', 'Fecha mínima', 'Máxima · °C', 'Fecha máxima', f'Gradiente máx. ascenso · {unit}', 'Fecha subida', f'Gradiente mín. descenso · {unit}', 'Fecha descenso', 'Racha en banda · min', 'Lecturas válidas']
        rows = []
        for stats in summary:
            gradiente = lambda key: stats.get(key) * factor if stats.get(key) is not None else None
            rows.append([self.session.nombre(stats['canal']), stats.get('ultima'), stats.get('tultima'), stats.get('minimo'), stats.get('tmin'), stats.get('maximo'), stats.get('tmax'), gradiente('subida'), stats.get('tsubida'), gradiente('bajada'), stats.get('tbajada'), stats.get('racha'), stats['n']])
        self.model.replace(headers, rows)
        self.table.setColumnWidth(0, 240)
        for col in (7, 9):self.table.setColumnWidth(col,250)
        for col in (2, 4, 6, 8, 10):
            self.table.setColumnWidth(col, 180)
        registro = self.session.registro
        self.summary_label.setText(f'{len(registro.canales)} canales  ·  {len(registro.muestras):,} muestras  ·  Registro completo  ·  Banda {self.session.perfil.inferior:g}–{self.session.perfil.superior:g} °C')


class LogbookDialog(QDialog):
    annotations_changed = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle('Bitácora del tratamiento')
        self.resize(1120, 750)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(label('Bitácora del tratamiento', 'pageTitle'))
        layout.addWidget(label('Registrá ajustes e incidencias del operador. Los porcentajes documentan los ajustes realizados en cada zona.'))
        entry_card, entry_layout = card()
        row = QHBoxLayout()
        row.addWidget(QLabel('Fecha y hora'))
        self.timestamp = QDateTimeEdit()
        self.timestamp.setCalendarPopup(True)
        self.timestamp.setDisplayFormat('dd/MM/yyyy HH:mm:ss')
        self.timestamp.setDateTime(QDateTime.currentDateTime())
        self.timestamp.setMinimumWidth(195)
        row.addWidget(self.timestamp)
        latest = QPushButton('Última muestra')
        latest.clicked.connect(self.use_latest_sample)
        row.addWidget(latest)
        row.addSpacing(16)
        row.addWidget(QLabel('Operador'))
        self.operator = QLineEdit()
        self.operator.setPlaceholderText('Nombre del operador')
        row.addWidget(self.operator, 1)
        entry_layout.addLayout(row)
        zones_row = QHBoxLayout()
        self.zones = []
        for index in range(6):
            group = QVBoxLayout()
            group.addWidget(label(f'Zona {index + 1} · %'))
            field = QLineEdit()
            field.setPlaceholderText('Sin registro')
            field.setAccessibleName(f'Porcentaje de zona {index + 1}')
            group.addWidget(field)
            zones_row.addLayout(group)
            self.zones.append(field)
        entry_layout.addLayout(zones_row)
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText('Incidencia o motivo del ajuste…')
        self.note.setMaximumHeight(78)
        entry_layout.addWidget(self.note)
        entry_actions = QHBoxLayout()
        entry_actions.addStretch()
        add = QPushButton('Registrar en bitácora')
        add.setProperty('primary', True)
        add.clicked.connect(self.add_event)
        entry_actions.addWidget(add)
        entry_layout.addLayout(entry_actions)
        layout.addWidget(entry_card)
        self.model = RowsModel(parent=self)
        self.table = table(self.model)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        delete = QPushButton('Eliminar seleccionado')
        delete.clicked.connect(self.delete_selected)
        export = QPushButton('Exportar bitácora CSV')
        export.clicked.connect(self.export_csv)
        actions.addWidget(delete)
        actions.addWidget(export)
        actions.addStretch()
        close = QPushButton('Cerrar')
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.use_latest_sample()
        self.refresh()

    def use_latest_sample(self):
        if self.session.registro.muestras:
            self.timestamp.setDateTime(QDateTime(self.session.registro.muestras[-1][0]))

    def add_event(self):
        try:
            event = build_manual_event(self.session, self.timestamp.dateTime().toPython(),
                                       [field.text() for field in self.zones], self.operator.text(), self.note.toPlainText())
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Revisá el registro', str(exc))
            return
        self.session.controladores.append(event)
        self.session.controladores.sort(key=lambda item: fecha_local(item['fecha']))
        self.note.clear()
        self.refresh()
        self.annotations_changed.emit()

    def delete_selected(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        answer = QMessageBox.question(self, 'Eliminar registro', f'¿Eliminar {len(selected)} registro(s) de la bitácora?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        for index in sorted((index.row() for index in selected), reverse=True):
            self.session.controladores.pop(index)
        self.refresh()
        self.annotations_changed.emit()

    def refresh(self):
        headers = ['Fecha y hora', 'Ideal · °C', 'Operador'] + [f'Zona {index} · %' for index in range(1, 7)] + ['Temperaturas medidas · °C', 'Incidencia']
        rows = []
        for event in self.session.controladores:
            temperatures = '; '.join(f'{self.session.nombre(channel)}: {display_value(value)}' for channel, value in event.get('temperaturas', {}).items())
            rows.append([fecha_local(event['fecha']), event.get('ideal'), event.get('operador', '')] + event['zonas'] + [temperatures or 'Sin datos vigentes', event.get('nota', '')])
        self.model.replace(headers, rows)
        self.table.setColumnWidth(0, 185)
        for col in range(3, 9):
            self.table.setColumnWidth(col, 100)
        self.table.setColumnWidth(9, 280)
        self.table.setColumnWidth(10, 280)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar bitácora', 'bitacora.csv', 'CSV (*.csv)')
        if path:
            try:
                exportar_controladores(self.session, path)
            except Exception as exc:
                QMessageBox.warning(self, 'No se pudo exportar', str(exc))


class DataPage(QWidget):
    save_requested = Signal()
    annotations_changed = Signal()
    replay_requested = Signal()

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session or Sesion()
        self.session_path = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        heading.addWidget(label('Datos', 'pageTitle'))
        heading.addStretch()
        self.replay_button=QPushButton('Reproducir ejemplo')
        self.replay_button.clicked.connect(self.replay_requested.emit)
        self.replay_button.hide()
        heading.addWidget(self.replay_button)
        heading.addWidget(label('Gradiente'))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(['°C/h', '°C/min'])
        heading.addWidget(self.unit_combo)
        logbook = QPushButton('Bitácora')
        logbook.clicked.connect(self.open_logbook)
        heading.addWidget(logbook)
        save = QPushButton('Guardar sesión')
        save.clicked.connect(lambda: self.save_requested.emit())
        heading.addWidget(save)
        layout.addLayout(heading)
        self.info_label = label('')
        layout.addWidget(self.info_label)
        self.model = MeasurementsModel(self.session, self)
        self.unit_combo.currentTextChanged.connect(self.model.set_unit)
        self.table = table(self.model)
        layout.addWidget(self.table, 1)
        self.path_label = label('')
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        layout.addWidget(label('El gradiente utiliza el intervalo real entre mediciones de ese canal. «—» indica un valor ausente o inválido, una primera lectura o una pausa o un intervalo que supera el hueco máximo.'))
        self.set_path(None)
        self.refresh()

    def set_session(self, session):
        self.session = session
        self.model.set_session(session)
        self.replay_button.setVisible('EJEMPLO' in session.modo or 'SIMULACIÓN' in session.modo)
        self.refresh()

    def set_path(self, path):
        self.session_path = Path(path) if path else None
        self.path_label.setText(f'Sesión: {self.session_path}' if self.session_path else 'Sesión en memoria · Guardar sesión conserva datos, perfil y bitácora.')

    def refresh(self):
        registro = self.session.registro
        if len(registro.gradientes) != len(registro.muestras):
            registro.recalcular(self.session.perfil.hueco_max)
        self.model.refresh()
        self.table.setColumnWidth(0, 190)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 180)
        for column in range(3, self.model.columnCount()):
            self.table.setColumnWidth(column, 215)
        self.info_label.setText(f'{len(registro.muestras):,} muestras  ·  {len(registro.canales)} canales  ·  {len(self.session.controladores)} registros en bitácora')

    def open_logbook(self):
        dialog = LogbookDialog(self.session, self)
        dialog.annotations_changed.connect(self._annotations_updated)
        dialog.exec()

    def _annotations_updated(self):
        self.refresh()
        self.annotations_changed.emit()


class AlertsPage(QWidget):
    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session or Sesion()
        self._logs = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(label('Avisos', 'pageTitle'))
        self.info_label = label('')
        layout.addWidget(self.info_label)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter = self.splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.model = RowsModel(parent=self)
        self.table = table(self.model)
        self.table.setMinimumHeight(130)
        splitter.addWidget(self.table)
        details = QWidget()
        details.setMinimumHeight(140)
        details_layout = QHBoxLayout(details)
        details_layout.setContentsMargins(0, 10, 0, 0)
        details_layout.setSpacing(14)
        notes_card, notes_layout = card()
        notes_layout.addWidget(label('Notas de importación y datos', 'sectionTitle'))
        self.notes_text = QPlainTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setPlaceholderText('Sin notas de importación.')
        notes_layout.addWidget(self.notes_text)
        details_layout.addWidget(notes_card)
        diagnostic_card, diagnostic_layout = card()
        diagnostic_layout.addWidget(label('Diagnóstico de conexión', 'sectionTitle'))
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(2000)
        self.log_text.setPlaceholderText('Las novedades de conexión aparecerán aquí.')
        diagnostic_layout.addWidget(self.log_text)
        details_layout.addWidget(diagnostic_card)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([420, 220])
        layout.addWidget(splitter, 1)
        layout.addWidget(label('Las rampas se comparan con el perfil; la banda se evalúa durante el mantenimiento previsto. Estos avisos ayudan al seguimiento del tratamiento y requieren interpretación del operador.'))
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        # A splitter constructed inside a hidden tab can initially have zero
        # pane sizes on Windows. Allocate both panes after the tab is shown.
        QTimer.singleShot(0, self._ensure_panes)

    def _ensure_panes(self):
        if self.isVisible() and any(size < 1 for size in self.splitter.sizes()):
            height=max(300,self.splitter.height())
            self.splitter.setSizes([height*3//5,height*2//5])

    def set_session(self, session):
        self.session = session
        self.refresh()

    def clear_log(self):
        self._logs.clear()
        self.log_text.clear()

    def add_log(self, text):
        text = str(text).strip()
        if not text or (self._logs and self._logs[-1] == text):
            return
        self._logs.append(text)
        if len(self._logs) > 2000:
            self._logs = self._logs[-1000:]
        self.log_text.appendPlainText(text)

    def refresh(self):
        _, alerts = self.session.analisis()
        self.model.replace(['Fecha y hora', 'Canal', 'Observación', 'Detalle'], [(dt, self.session.nombre(channel), kind, detail) for dt, channel, kind, detail in alerts])
        self.table.setColumnWidth(0, 185)
        self.table.setColumnWidth(1, 250)
        self.table.setColumnWidth(2, 235)
        notes = self.session.registro.notas
        self.notes_text.setPlainText('\n'.join(str(note) for note in notes))
        count = len(alerts)
        self.info_label.setText(f'{count:,} observaciones calculadas  ·  {len(notes):,} notas de datos' if count else f'Sin observaciones calculadas  ·  {len(notes):,} notas de datos')
