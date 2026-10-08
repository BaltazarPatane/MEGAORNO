"""Vista de curvas: controles contextuales y selección de canales trazable."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox, QListWidget, QListWidgetItem, QInputDialog
from ui.theme import label,button,card,icon
from ui.chart_widget import ChartWidget, CHANNEL_COLORS

class CurvesPage(QWidget):
    aliases_changed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.session=None;self.channel_keys=[]
        outer=QVBoxLayout(self);outer.setContentsMargins(0,18,0,0);outer.setSpacing(14)
        row=QHBoxLayout();title=QVBoxLayout();title.addWidget(label('Curvas del tratamiento','pageTitle'));title.addWidget(label('Temperatura y velocidad de cambio en el tiempo.','muted'));row.addLayout(title);row.addStretch()
        self.follow=QCheckBox('Seguir últimas muestras');self.follow.setChecked(True);row.addWidget(self.follow);outer.addLayout(row)
        self.metric_values=[];self.metric_notes=[];metrics=QHBoxLayout();metrics.setSpacing(12)
        for name in ['ÚLTIMA MUESTRA','ETAPA PREVISTA']:
            panel,layout=card(15);layout.setSpacing(5);layout.addWidget(label(name,'eyebrow'));value=label('—','metric');note=label('Esperando datos','muted');layout.addWidget(value);layout.addWidget(note);self.metric_values.append(value);self.metric_notes.append(note);metrics.addWidget(panel,1)
        outer.addLayout(metrics)
        content=QHBoxLayout();content.setSpacing(14);outer.addLayout(content,1)
        side,sl=card(16);sl.setSpacing(8);side.setFixedWidth(244);sl.addWidget(label('Canales','sectionTitle'));sl.addWidget(label('Doble clic: nombre / ubicación.','muted',True))
        self.channels=QListWidget();self.channels.setMinimumHeight(130);self.channels.setStyleSheet('QListWidget {border: none; background: white; outline: none;} QListWidget::item {border-bottom:1px solid #edf1f4;padding:12px 2px;} QListWidget::item:selected {background:#edf4f8;color:#263c49;}');self.channels.setWordWrap(True);sl.addWidget(self.channels,1)
        self.channels.itemChanged.connect(self.select_channels);self.channels.itemDoubleClicked.connect(self.rename_channel)
        toggles=QHBoxLayout();toggles.addWidget(button('Todos',lambda:self.check_all(True)));toggles.addWidget(button('Ninguno',lambda:self.check_all(False)));sl.addLayout(toggles)
        sl.addSpacing(8);sl.addWidget(label('REFERENCIAS','eyebrow'));self.ideal=QCheckBox('Perfil ideal');self.band=QCheckBox('Banda de mantenimiento');self.full=QCheckBox('Programa completo')
        for w in (self.ideal,self.band,self.full):sl.addWidget(w);w.toggled.connect(self.options_changed)
        content.addWidget(side)
        main,ml=card(17);ml.setSpacing(10);controls=QHBoxLayout();self.mode=QComboBox();self.mode.addItems(['Temperatura','Velocidad','Ambas']);self.mode.setMinimumWidth(142)
        self.unit=QComboBox();self.unit.addItems(['°C/h','°C/min']);self.unit.setToolTip('Unidad de velocidad de cambio')
        self.window=QComboBox()
        for name,minutes in [('Todo el registro',0),('Últimos 5 min',5),('Últimos 15 min',15),('Últimos 30 min',30),('Últimos 60 min',60)]:self.window.addItem(name,minutes)
        controls.addWidget(self.mode);controls.addWidget(self.unit);controls.addStretch();controls.addWidget(self.window)
        fit=button('Ajustar vista',lambda:self.chart.fit_view());fit.setIcon(icon('fit'));controls.addWidget(fit);ml.addLayout(controls)
        self.chart=ChartWidget();ml.addWidget(self.chart,1)
        self.cursor=label('Rueda: zoom  ·  Arrastrar: desplazar  ·  Doble clic: ajustar','muted');self.cursor.setMinimumHeight(22);ml.addWidget(self.cursor)
        content.addWidget(main,1)
        self.chart.cursor_text.connect(self._cursor_text);self.chart.view_changed.connect(self._view_changed);self.follow.toggled.connect(self.chart.set_follow)
        self.mode.currentIndexChanged.connect(self.options_changed);self.unit.currentIndexChanged.connect(self.options_changed);self.window.currentIndexChanged.connect(self.window_changed)
    def _cursor_text(self,text):self.cursor.setText(text or 'Rueda: zoom temporal  ·  Arrastrar: desplazar  ·  Ctrl + rueda: sólo eje Y')
    def _view_changed(self,following):
        self.follow.blockSignals(True);self.follow.setChecked(following);self.follow.blockSignals(False)
    def window_changed(self):
        if self.window.currentData():self.full.setChecked(False)
        self.options_changed()
    def options_changed(self):
        if self.full.isChecked() and self.window.currentData():
            self.window.blockSignals(True);self.window.setCurrentIndex(0);self.window.blockSignals(False)
        self.chart.set_options(mode=self.mode.currentText(),unit=self.unit.currentText(),window_minutes=self.window.currentData(),show_ideal=self.ideal.isChecked(),show_band=self.band.isChecked(),full_program=self.full.isChecked())
    def check_all(self,checked):
        self.channels.blockSignals(True)
        for i in range(self.channels.count()):self.channels.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.channels.blockSignals(False);self.select_channels()
    def select_channels(self,*args):
        self.chart.set_channels([i for i in range(self.channels.count()) if self.channels.item(i).checkState()==Qt.CheckState.Checked])
    def selected_channels(self):
        return [self.channel_keys[i] for i in range(self.channels.count()) if self.channels.item(i).checkState()==Qt.CheckState.Checked]
    def rename_channel(self,item):
        channel=self.channel_keys[self.channels.row(item)]
        name,ok=QInputDialog.getText(self,'Nombre del canal',channel+'\nNombre o ubicación:',text=self.session.nombre(channel))
        if ok and name.strip():self.session.alias[channel]=name.strip();self.aliases_changed.emit();self.refresh()
    def set_session(self,session):
        self.session=session;self.channel_keys=[];self.chart.set_session(session);self.refresh()
    def refresh(self,summary=None,alerts=None):
        if self.session is None:return
        r=self.session.registro
        r.recalcular(self.session.perfil.hueco_max)
        self.channels.blockSignals(True)
        if self.channel_keys!=r.canales:
            selected={self.channel_keys[i] for i in range(len(self.channel_keys)) if self.channels.item(i).checkState()==Qt.CheckState.Checked}
            new=not self.channel_keys;self.channels.clear();self.channel_keys=list(r.canales)
            for i,c in enumerate(r.canales):
                item=QListWidgetItem();item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if new or c in selected else Qt.CheckState.Unchecked);item.setForeground(QColor(CHANNEL_COLORS[i%len(CHANNEL_COLORS)]));self.channels.addItem(item)
        for i,c in enumerate(r.canales):
            latest=next(((dt,vals[c]) for dt,vals in reversed(r.muestras) if c in vals),None)
            text='Sin muestras'
            if latest:
                dt,value=latest;text=('Sin dato' if value is None else f'{value:.2f} °C')+f'  ·  {dt:%H:%M:%S}'
            item=self.channels.item(i);item.setText(self.session.nombre(c)+'\n'+text);item.setToolTip(c+(f'\nMedición: {latest[0]:%d/%m/%Y %H:%M:%S}' if latest else ''))
        self.channels.blockSignals(False)
        values=['—','—'];notes=['Esperando datos','Según el perfil ideal']
        if r.muestras:
            a,b=r.muestras[0][0],r.muestras[-1][0];values[0]=b.strftime('%H:%M:%S');notes[0]=b.strftime('%d/%m/%Y')+' · hora de medición';values[1]=self.session.perfil.punto((b-a).total_seconds()/60)[1].replace('Programa finalizado','Finalizado')
        for i,(v,n) in enumerate(zip(values,notes)):
            self.metric_values[i].setText(v);self.metric_notes[i].setText(n)
        selected=[i for i in range(self.channels.count()) if self.channels.item(i).checkState()==Qt.CheckState.Checked]
        if selected!=self.chart.channels:self.chart.set_channels(selected)
        else:self.chart.refresh(preserve_view=True)
