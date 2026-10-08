"""Pantalla de entrada: valores seguros por defecto y configuración progresiva."""
from pathlib import Path
import json
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QSpinBox, QCheckBox, QComboBox, QFileDialog, QScrollArea
from live import carpeta_madgetech
from ui.theme import label, button, card, icon

class ProcessArt(QWidget):
    """Trazo ilustrativo del perfil; no representa una adquisición."""
    def __init__(self):
        super().__init__(); self.setMinimumHeight(160)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height();p.setPen(QPen(QColor('#304c5d'),1))
        for n in range(5): p.drawLine(0,int(h*.15+n*h*.17),w,int(h*.15+n*h*.17))
        points=[(0,.85),(.1,.85),(.42,.22),(.66,.22),(.92,.62),(1,.62)]
        path=QPainterPath()
        for i,(x,y) in enumerate(points):
            if i==0:path.moveTo(x*w,y*h)
            else:path.lineTo(x*w,y*h)
        p.setPen(QPen(QColor('#6ec39e'),2.5));p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#6ec39e'));p.drawEllipse(QRectF(w*.66-4,h*.22-4,8,8))

class LoginPage(QWidget):
    connect_requested=Signal(); search_requested=Signal(); demo_requested=Signal(); open_requested=Signal(); cancel_requested=Signal()
    def __init__(self,state_dir,parent=None):
        super().__init__(parent); self.state_dir=Path(state_dir)
        outer=QVBoxLayout(self);outer.setContentsMargins(40,25,40,25)
        branding=QHBoxLayout(); branding.addWidget(label('MEGAORNO','brand'));branding.addStretch();branding.addWidget(label('ADQUISICIÓN · ANÁLISIS · TRAZABILIDAD','eyebrow'));outer.addLayout(branding)
        outer.addStretch(1)
        middle=QHBoxLayout();middle.addStretch()
        shell,shell_layout=card(0);shell.setMaximumWidth(1080)
        columns=QHBoxLayout(); columns.setContentsMargins(0,0,0,0);columns.setSpacing(0);shell_layout.addLayout(columns)
        hero=QWidget();hero.setMinimumWidth(340);hero.setMaximumWidth(405)
        hero.setStyleSheet('QWidget#hero { background: #223c4c; border-top-left-radius: 14px; border-bottom-left-radius: 14px; } QLabel {color:#ecf2f5;}')
        hero.setObjectName('hero');hl=QVBoxLayout(hero);hl.setContentsMargins(34,40,34,34);hl.setSpacing(18)
        k=label('CONTROL DE TRATAMIENTO','eyebrow');k.setStyleSheet('color:#90b8c8;');hl.addWidget(k)
        hl.addStretch();hl.addWidget(ProcessArt());hl.addWidget(label('MADGETECH 4  /  INTEROPERABILIDAD','eyebrow'))
        hl.addStretch()
        authors=label('Baltazar Patané\nJuan Marcos Macagno',wrap=True);authors.setStyleSheet('color:#c9dce6;font-size:15px;');hl.addWidget(authors)
        columns.addWidget(hero)
        form=QWidget();fl=QVBoxLayout(form);fl.setContentsMargins(36,28,36,28);fl.setSpacing(12)
        fl.addWidget(label('Iniciar sesión','pageTitle'));fl.addWidget(label('Conectá el equipo o explorá un tratamiento de ejemplo.','muted',True))
        g=QGridLayout();g.setHorizontalSpacing(12);g.setVerticalSpacing(6)
        self.endpoint=QLineEdit('net.pipe://localhost/MT4Data');self.endpoint.setAccessibleName('Dirección WCF')
        self.poll=QSpinBox();self.poll.setRange(1,3600);self.poll.setValue(5);self.poll.setSuffix(' s');self.poll.setToolTip('Consulta la última lectura. No modifica el muestreo del equipo.')
        g.addWidget(label('Dirección WCF'),0,0);g.addWidget(label('Sondeo'),0,1);g.addWidget(self.endpoint,1,0);g.addWidget(self.poll,1,1);g.setColumnStretch(0,1);fl.addLayout(g)
        self.auth=QCheckBox('Autenticar en MadgeTech');self.auth.setToolTip('Activá esta opción si la salida WCF usa usuario y contraseña.');fl.addWidget(self.auth)
        credentials=QHBoxLayout();self.username=QLineEdit();self.username.setPlaceholderText('Usuario WCF');self.username.setAccessibleName('Usuario WCF')
        self.password=QLineEdit();self.password.setPlaceholderText('Contraseña');self.password.setEchoMode(QLineEdit.EchoMode.Password);self.password.setAccessibleName('Contraseña WCF')
        credentials.addWidget(self.username);credentials.addWidget(self.password);fl.addLayout(credentials)
        self.auth.toggled.connect(self._auth_changed);self._auth_changed(False)
        self.advanced_button=button('Configuración del equipo  ▾',self.toggle_advanced);self.advanced_button.setObjectName('link');fl.addWidget(self.advanced_button)
        self.advanced=QWidget();al=QVBoxLayout(self.advanced);al.setContentsMargins(0,0,0,0);al.setSpacing(6)
        al.addWidget(label('Carpeta de instalación de MadgeTech 4','muted'));row=QHBoxLayout();self.vendor_dir=QLineEdit(carpeta_madgetech());row.addWidget(self.vendor_dir)
        choose=button('…',self.choose_vendor);choose.setToolTip('Elegir carpeta MadgeTech');row.addWidget(choose);al.addLayout(row)
        al.addWidget(label('Carpeta de capturas','muted'));row=QHBoxLayout();self.capture_dir=QLineEdit(str(self.state_dir/'capturas'));row.addWidget(self.capture_dir);row.addWidget(button('…',self.choose_captures));al.addLayout(row)
        row=QHBoxLayout();self.search_button=button('Buscar equipos',self.search_requested.emit);row.addWidget(self.search_button);self.devices=QComboBox();self.devices.addItem('Selección automática','');row.addWidget(self.devices,1);al.addLayout(row)
        al.addWidget(label('El único equipo se selecciona automáticamente.','muted',True));self.advanced.hide();fl.addWidget(self.advanced)
        self.message=label('MadgeTech debe estar abierto y adquiriendo en esta notebook.','muted',True);self.message.setMinimumHeight(34);fl.addWidget(self.message)
        self.connect_button=button('Conectar con MadgeTech',self.connect_requested.emit,True);self.connect_button.setMinimumHeight(43);self.connect_button.setIcon(icon('arrow','#ffffff'));fl.addWidget(self.connect_button)
        self.cancel_button=button('Cancelar conexión',self.cancel_requested.emit);self.cancel_button.hide();fl.addWidget(self.cancel_button)
        bottom=QHBoxLayout();self.demo_button=button('Cargar ejemplo',self.demo_requested.emit);self.open_button=button('Abrir archivo',self.open_requested.emit);bottom.addWidget(self.demo_button);bottom.addWidget(self.open_button);fl.addLayout(bottom)
        fl.addWidget(label('Ejemplo y archivos históricos funcionan sin conectar equipos.','muted',True));columns.addWidget(form,1)
        middle.addWidget(shell,1);middle.addStretch();outer.addLayout(middle);outer.addStretch(1)
        footer=label('MEGAORNO 3.2   ·   MONITOREO DE TRATAMIENTOS TÉRMICOS','eyebrow');footer.setAlignment(Qt.AlignmentFlag.AlignCenter);outer.addWidget(footer)
        self.load_settings()
    def _auth_changed(self,enabled):
        self.username.setEnabled(enabled);self.password.setEnabled(enabled)
    def toggle_advanced(self):
        self.advanced.setVisible(not self.advanced.isVisible())
        self.advanced_button.setText('Configuración del equipo  '+('▴' if self.advanced.isVisible() else '▾'))
    def choose_vendor(self):
        path=QFileDialog.getExistingDirectory(self,'Carpeta de MadgeTech 4',self.vendor_dir.text())
        if path:self.vendor_dir.setText(path)
    def choose_captures(self):
        path=QFileDialog.getExistingDirectory(self,'Carpeta de capturas',self.capture_dir.text())
        if path:self.capture_dir.setText(path)
    def set_busy(self,busy):
        for widget in (self.connect_button,self.demo_button,self.open_button,self.search_button,self.endpoint,self.poll,self.auth,self.vendor_dir,self.devices,self.capture_dir):widget.setEnabled(not busy)
        self.username.setEnabled(not busy and self.auth.isChecked());self.password.setEnabled(not busy and self.auth.isChecked())
        self.cancel_button.setVisible(busy)
    def set_message(self,text,error=False):
        self.message.setText(str(text));self.message.setStyleSheet('color: '+('#b04442' if error else '#647985')+';')
    def set_devices(self,serials):
        current=self.devices.currentData();self.devices.clear();self.devices.addItem('Selección automática','')
        for serial in serials:self.devices.addItem(str(serial),str(serial))
        if current in serials:self.devices.setCurrentIndex(serials.index(current)+1)
    def settings(self):
        from acquisition import ConnectionSettings
        return ConnectionSettings(endpoint=self.endpoint.text().strip(),poll_seconds=self.poll.value(),vendor_dir=self.vendor_dir.text().strip(),authenticate=self.auth.isChecked(),username=self.username.text(),password=self.password.text(),serial=self.devices.currentData() or '')
    def save_settings(self):
        data=dict(endpoint=self.endpoint.text().strip(),poll_seconds=self.poll.value(),vendor_dir=self.vendor_dir.text().strip(),authenticate=self.auth.isChecked(),capture_dir=self.capture_dir.text().strip())
        dest=self.state_dir/'madgetech.json';temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(dest)
    def load_settings(self):
        path=self.state_dir/'madgetech.json'
        if not path.exists():return
        try:
            data=json.loads(path.read_text(encoding='utf8'))
            for key,widget in [('endpoint',self.endpoint),('vendor_dir',self.vendor_dir),('capture_dir',self.capture_dir)]:
                if isinstance(data.get(key),str):widget.setText(data[key])
            self.poll.setValue(int(data.get('poll_seconds',5)));self.auth.setChecked(data.get('authenticate') is True)
        except (ValueError,TypeError,OSError):self.set_message('No se pudo leer la configuración anterior. Revisá los valores de conexión.',True)
