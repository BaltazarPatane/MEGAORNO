"""MEGAORNO 3 · Interfaz modular. El transporte y los cálculos viven separados."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
import os
import sys
import uuid
from PySide6.QtCore import Qt,QTimer,QProcess,QStandardPaths
from PySide6.QtGui import QFont,QCloseEvent
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QStackedWidget,QTabWidget,QFrame,QMenu,QFileDialog,QMessageBox
from acquisition import AcquisitionController
from models import Sesion,Perfil,Registro,cargar_xlsx
from ui.theme import STYLE,label,button,icon
from ui.login import LoginPage
from ui.curves import CurvesPage
from ui.detail_pages import ProfilePage,StatisticsPage,DataPage,AlertsPage

ROOT=Path(__file__).resolve().parent

class App(QMainWindow):
    def __init__(self,state_dir=None,controller=None):
        super().__init__();self.setWindowTitle('MEGAORNO · Tratamientos térmicos');self.resize(1366,820);self.setMinimumSize(1080,700)
        location=state_dir or os.environ.get('MEGAORNO_STATE_DIR') or str(Path(os.environ['LOCALAPPDATA'])/'HornoMadgeTech' if os.environ.get('LOCALAPPDATA') else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)))
        self.state_dir=Path(location);self.state_dir.mkdir(parents=True,exist_ok=True)
        self.controller=controller or AcquisitionController(self.state_dir)
        self.replay_timer=QTimer(self);self.replay_timer.setInterval(250);self.replay_timer.timeout.connect(self.replay_step);self.replay_rows=[];self.replay_paused=False
        self.session=Sesion();self.session_path=None;self.pending_path=None;self.active=False;self.refresh_pending=False;self.export_process=None;self.export_snapshot=None;self.last_export=None
        self.setStyleSheet(STYLE);self.stack=QStackedWidget();self.stack.setObjectName('root');self.setCentralWidget(self.stack)
        scroll_widget=QWidget();login_layout=QVBoxLayout(scroll_widget);login_layout.setContentsMargins(0,0,0,0)
        from PySide6.QtWidgets import QScrollArea
        login_scroll=QScrollArea();login_scroll.setWidgetResizable(True);self.login=LoginPage(self.state_dir);login_scroll.setWidget(self.login);login_layout.addWidget(login_scroll);self.stack.addWidget(scroll_widget)
        self.workspace=QWidget();self.stack.addWidget(self.workspace);self.build_workspace()
        self.login.connect_requested.connect(lambda:self.run(self.connect_device));self.login.search_requested.connect(lambda:self.run(self.search_devices));self.login.demo_requested.connect(lambda:self.run(self.open_example));self.login.open_requested.connect(lambda:self.run(self.open_file));self.login.cancel_requested.connect(self.cancel_connection)
        self.timer=QTimer(self);self.timer.timeout.connect(self.consume);self.timer.start(100)
        self.refresh_timer=QTimer(self);self.refresh_timer.timeout.connect(self.flush_refresh);self.refresh_timer.start(750)
        self.stack.setCurrentIndex(0)
    def run(self,fn):
        try:return fn()
        except Exception as exc:self.show_error(str(exc))
    def show_error(self,message):
        if not self.active:self.login.set_busy(False);self.login.set_message(message,True)
        else:
            self.notice.clear()
            self.alerts.add_log(message)
    def build_workspace(self):
        layout=QVBoxLayout(self.workspace);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        header=QFrame();header.setObjectName('header');hl=QHBoxLayout(header);hl.setContentsMargins(26,18,26,17);hl.setSpacing(15)
        mark=label();mark.setPixmap(icon('mark','#286ca4',34).pixmap(34,34));hl.addWidget(mark)
        brand=QVBoxLayout();brand.setSpacing(2);brand.addWidget(label('MEGAORNO','brand'));brand.addWidget(label('TRATAMIENTOS TÉRMICOS','eyebrow'));hl.addLayout(brand);hl.addStretch()
        self.connection_badge=label('EJEMPLO','badge');hl.addWidget(self.connection_badge)
        self.pause_button=button('Pausa',lambda:self.run(self.toggle_pause));self.pause_button.setEnabled(False);hl.addWidget(self.pause_button)
        self.export_button=button('Exportar');self.export_button.setObjectName('dark');self.export_button.setIcon(icon('export','#ffffff'))
        menu=QMenu(self.export_button)
        for kind in ['PDF','EXCEL','CSV']:menu.addAction(kind,lambda checked=False,k=kind:self.run(lambda:self.choose_export(k)))
        self.export_button.setMenu(menu);hl.addWidget(self.export_button)
        self.power=button('',lambda:self.run(self.logout));self.power.setObjectName('power');self.power.setIcon(icon('power'));self.power.setFixedSize(39,39);self.power.setToolTip('Cerrar sesión y volver al inicio');self.power.setAccessibleName('Cerrar sesión');hl.addWidget(self.power);layout.addWidget(header)
        body=QWidget();bl=QVBoxLayout(body);bl.setContentsMargins(26,0,26,10);bl.setSpacing(6)
        self.tabs=QTabWidget();self.tabs.setDocumentMode(True);self.curves=CurvesPage();self.profile=ProfilePage();self.statistics=StatisticsPage();self.data=DataPage();self.alerts=AlertsPage()
        for page,name in [(self.curves,'Curvas'),(self.profile,'Perfil ideal'),(self.statistics,'Estadísticas'),(self.data,'Datos'),(self.alerts,'Avisos')]:self.tabs.addTab(page,name)
        bl.addWidget(self.tabs,1)
        bottom=QHBoxLayout();self.notice=label('Sesión guardada automáticamente','muted');self.notice.setWordWrap(True);self.notice.setMaximumHeight(38);bottom.addWidget(self.notice,1);self.source=label('','muted');bottom.addWidget(self.source);bl.addLayout(bottom);layout.addWidget(body,1)
        self.profile.profile_applied.connect(self.apply_profile);self.curves.aliases_changed.connect(self.persist_changes);self.data.annotations_changed.connect(self.persist_changes);self.data.save_requested.connect(lambda:self.run(self.save_copy));self.tabs.currentChanged.connect(self.refresh_visible)
        self.data.replay_requested.connect(lambda:self.run(self.toggle_replay))
    def new_capture_path(self,prefix='captura'):
        directory=Path(self.login.capture_dir.text().strip() or self.state_dir/'capturas');directory.mkdir(parents=True,exist_ok=True)
        return directory/(prefix+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.horno.json')
    def connect_device(self):
        if self.controller.running:raise ValueError('Hay una conexión en curso.')
        if os.name!='nt' and type(self.controller) is AcquisitionController:raise ValueError('La conexión WCF requiere Windows, .NET Framework 4.8 y MadgeTech 4. En este equipo podés usar Cargar ejemplo o Abrir archivo.')
        settings=self.login.settings();self.login.save_settings();self.pending_path=self.new_capture_path();self.alerts.clear_log()
        self.controller.connect(settings,self.pending_path,self.session.perfil);self.login.set_busy(True);self.login.set_message('Conectando, buscando el equipo y esperando una lectura válida…')
    def search_devices(self):
        settings=self.login.settings();self.pending_path=None;self.controller.search(settings);self.login.set_busy(True);self.login.set_message('Buscando equipos conectados a MadgeTech…')
    def cancel_connection(self):
        self.consume()
        if self.active:self.logout();return
        self.controller.disconnect();self.login.set_busy(False);self.login.password.clear();self.login.set_message('Conexión cancelada. Podés volver a intentar.');self.pending_path=None
    def open_example(self):
        r=cargar_xlsx(ROOT/'ejemplos'/'R59022 MultiChannel.xlsx');session=Sesion(registro=r,modo='EJEMPLO · histórico',titulo='Tratamiento de ejemplo · R59022')
        path=self.new_capture_path('ejemplo');session.guardar(path);self.alerts.clear_log();self.activate_session(session,path)
    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Abrir registro o sesión','','Registros y sesiones (*.xlsx *.xlsm *.horno.json);;Sesión de tratamiento (*.json)')
        if path:self.load_file(path)
    def load_file(self,path):
        path=Path(path)
        if path.suffix.lower()=='.json':session=Sesion.abrir(path);destination=path
        else:session=Sesion(registro=cargar_xlsx(path));destination=self.new_capture_path('historico');session.guardar(destination)
        self.alerts.clear_log();self.activate_session(session,destination)
    def activate_session(self,session,path):
        self.session=session;self.session_path=Path(path);self.active=True;self.login.set_busy(False);self.login.password.clear()
        for page in (self.curves,self.profile,self.statistics,self.data,self.alerts):page.set_session(session)
        self.data.set_path(str(self.session_path));self.tabs.setCurrentIndex(0);self.stack.setCurrentIndex(1)
        self.connection_badge.setText('●  RECEPCIÓN ACTIVA' if self.controller.running else 'EJEMPLO' if 'EJEMPLO' in session.modo or 'SIMULACIÓN' in session.modo else 'HISTÓRICO')
        self.notice.setText('Guardado automático · '+str(self.session_path));self.notice.setStyleSheet('color:#74818a;');self.update_source();self.export_button.setEnabled(self.export_process is None and bool(session.registro.muestras))
        self.update_pause_ui()
    def update_pause_ui(self):
        enabled=self.active and (self.controller.can_pause or self.replay_timer.isActive() or self.replay_paused)
        paused=self.controller.paused or self.replay_paused
        self.pause_button.setEnabled(enabled);self.pause_button.setText('Reanudar' if paused else 'Pausa')
        self.pause_button.setToolTip('Continuar en la misma sesión, conservando el historial.' if paused else 'Pausar la adquisición sin cerrar la sesión ni borrar muestras.' if enabled else 'Disponible durante la adquisición o la reproducción del ejemplo.')
        if self.replay_paused:self.data.replay_button.setText('Reanudar ejemplo')
        elif self.replay_timer.isActive():self.data.replay_button.setText('Pausar ejemplo')
        else:self.data.replay_button.setText('Reproducir ejemplo')
    def toggle_pause(self):
        self.consume()
        if self.controller.can_pause:
            if self.controller.paused:self.controller.resume()
            else:self.controller.pause()
            self.consume()
        elif self.replay_timer.isActive():
            self.replay_timer.stop();self.replay_paused=True;self.connection_badge.setText('SIMULACIÓN · PAUSADA')
        elif self.replay_paused:
            self.replay_paused=False;self.replay_timer.start();self.connection_badge.setText('SIMULACIÓN · EN CURSO')
        self.update_pause_ui()
    def update_source(self):
        r=self.session.registro;self.source.setText((r.serie+'  ·  ' if r.serie else '')+f'{len(r.muestras):,} muestras'.replace(',','.'))
    def apply_profile(self,profile):
        try:
            profile.validar();self.session.perfil=profile;self.persist_changes();self.curves.options_changed()
        except Exception as e:self.show_error(str(e))
    def persist_changes(self):
        try:
            self.session.guardar(self.session_path);self.session.analisis();self.refresh_pending=True;self.flush_refresh();self.notice.setText('Cambios guardados · '+str(self.session_path));self.notice.setStyleSheet('color:#74818a;')
        except Exception as e:
            if self.controller.running:self.controller.disconnect()
            self.replay_timer.stop()
            self.replay_paused=False;self.update_pause_ui()
            self.connection_badge.setText('●  RECEPCIÓN DETENIDA');self.show_error('No se pudo guardar. Los datos siguen en memoria. Usá Datos → Guardar sesión en otra ubicación. '+str(e))
    def save_copy(self):
        path,_=QFileDialog.getSaveFileName(self,'Guardar sesión',str(self.session_path or self.state_dir/'tratamiento.horno.json'),'Sesión de tratamiento (*.horno.json)')
        if not path:return
        if not path.endswith('.horno.json'):path+='.horno.json'
        self.session.guardar(path)
        if self.controller.running:
            self.notice.setText('Copia guardada. La captura continúa en '+str(self.session_path))
        else:self.session_path=Path(path);self.data.set_path(path);self.notice.setText('Sesión guardada · '+path)
    def consume(self):
        try:
            for event in self.controller.drain():
                kind,data=event.get('type'),event.get('data')
                if kind=='devices':self.login.set_devices(data)
                elif kind=='selection_required':
                    self.login.set_devices(data);self.login.advanced.show();self.login.set_busy(False);self.login.set_message('Hay más de un equipo. Elegí su número de serie y conectá nuevamente.')
                elif kind=='ready':self.activate_session(self.controller.session,self.controller.session_path)
                elif kind=='sample':
                    if data.get('changed'):self.refresh_pending=True
                elif kind=='state':
                    state=data if isinstance(data,str) else self.controller.state
                    if state in ('disconnected','error','selection_required'):self.login.set_busy(False)
                    if state=='waiting':
                        if self.active:self.connection_badge.setText('●  ESPERANDO MUESTRA');self.notice.setText('Esperando lectura nueva. Se conserva la hora de medición de cada canal.')
                        else:self.login.set_message('MadgeTech todavía no entrega temperaturas válidas. Verificá la adquisición en tiempo real.')
                    elif state=='receiving' and self.active:
                        self.connection_badge.setText('●  RECEPCIÓN ACTIVA');self.notice.setText('Guardado automático · '+str(self.session_path));self.notice.setStyleSheet('color:#74818a;')
                    elif state=='paused' and self.active:
                        self.connection_badge.setText('Ⅱ  ADQUISICIÓN PAUSADA');self.notice.setText('Historial conservado · La adquisición continuará al pulsar Reanudar.')
                elif kind in ('warning','log','error'):
                    self.alerts.add_log(str(data))
                    if kind=='error':
                        if (not self.active and self.pending_path is not None
                                and self.controller.session_path == self.pending_path
                                and self.controller.session and self.controller.session.registro.muestras):
                            self.activate_session(self.controller.session,self.controller.session_path)
                        self.show_error(str(data));self.connection_badge.setText('●  RECEPCIÓN DETENIDA');self.login.password.clear()
                    elif kind=='warning':
                        if not self.active:self.login.set_message('Esperando temperaturas válidas de MadgeTech…')
                elif kind=='contract':self.alerts.add_log('Contrato MadgeTech: '+json.dumps(data,ensure_ascii=False))
            if not self.controller.running and self.controller.state=='disconnected':self.login.set_busy(False)
        except Exception as e:
            self.controller.disconnect();self.show_error(str(e))
        self.update_pause_ui()
    def flush_refresh(self):
        if not self.refresh_pending or not self.active:return
        self.refresh_pending=False;self.refresh_visible();self.update_source();self.export_button.setEnabled(self.export_process is None and bool(self.session.registro.muestras))
    def refresh_visible(self,*args):
        if self.active:self.tabs.currentWidget().refresh()
    def logout(self):
        self.consume();self.replay_timer.stop();self.replay_paused=False
        self.controller.disconnect()
        self.update_pause_ui()
        self.connection_badge.setText('●  RECEPCIÓN DETENIDA')
        if self.active:
            try:self.session.guardar(self.session_path)
            except Exception as e:
                self.show_error('No se pudo guardar; la sesión sigue abierta. Guardala desde Datos antes de cerrar. '+str(e));return
        self.active=False;self.refresh_pending=False;self.pending_path=None;self.login.password.clear();self.login.username.clear();self.login.set_busy(False);self.login.set_message('Sesión cerrada. La captura quedó guardada.');self.stack.setCurrentIndex(0);self.session=Sesion();self.session_path=None
    def toggle_replay(self):
        if self.replay_timer.isActive() or self.replay_paused:
            self.toggle_pause();return
        if self.controller.running:raise ValueError('La recepción real está activa.')
        if 'EJEMPLO' not in self.session.modo and 'SIMULACIÓN' not in self.session.modo:raise ValueError('La reproducción está disponible en el ejemplo.')
        self.session.guardar(self.session_path)
        source=cargar_xlsx(ROOT/'ejemplos'/'R59022 MultiChannel.xlsx')
        session=Sesion(registro=Registro(origen='Reproducción del ejemplo R59022',serie=source.serie,canales=list(source.canales)),perfil=Perfil(**asdict(self.session.perfil)),modo='SIMULACIÓN histórica',titulo='Ejemplo · reproducción acelerada')
        path=self.new_capture_path('simulacion');session.guardar(path);self.activate_session(session,path);self.replay_rows=list(source.muestras);self.replay_paused=False;self.connection_badge.setText('SIMULACIÓN · EN CURSO');self.replay_timer.start();self.replay_step();self.update_pause_ui()
    def replay_step(self):
        if self.replay_paused:return
        if not self.replay_rows:
            self.replay_timer.stop();self.update_pause_ui();self.connection_badge.setText('EJEMPLO · COMPLETO');self.notice.setText('Reproducción finalizada. Se conservaron las fechas originales del registro.');return
        dt,values=self.replay_rows.pop(0);self.session.registro.agregar([(dt,c,v) for c,v in values.items()],self.session.perfil.hueco_max)
        try:self.session.guardar(self.session_path)
        except Exception as e:
            self.replay_timer.stop();self.replay_paused=False;self.update_pause_ui();self.connection_badge.setText('EJEMPLO · DETENIDO');self.show_error('No se pudo guardar la simulación. Los datos siguen en memoria. '+str(e));return
        self.refresh_pending=True
    def choose_export(self,kind):
        ext={'PDF':'pdf','EXCEL':'xlsx','CSV':'csv'}[kind]
        path,_=QFileDialog.getSaveFileName(self,'Exportar '+kind,str(Path(self.session_path).parent/('tratamiento.'+ext)),kind+' (*.'+ext+')')
        if path:
            if not path.lower().endswith('.'+ext):path+='.'+ext
            self.export_to(path,kind)
    def export_to(self,path,kind):
        if not self.session.registro.muestras:raise ValueError('Todavía no hay muestras para exportar.')
        if self.export_process is not None:raise ValueError('Esperá a que termine la exportación actual.')
        selected=self.curves.selected_channels() if kind=='PDF' else None
        if selected==[]:raise ValueError('Seleccioná al menos un canal en Curvas para exportar la gráfica en PDF.')
        scratch=self.state_dir/'exportaciones';scratch.mkdir(exist_ok=True);snapshot=scratch/(uuid.uuid4().hex+'.horno.json');self.session.guardar(snapshot)
        process=QProcess(self);self.export_process=process;self.export_snapshot=snapshot;self.last_export=None;self.export_button.setEnabled(False)
        arguments=[str(ROOT/'tools'/'export_session.py'),str(snapshot),str(Path(path).absolute()),kind]
        if selected is not None:arguments.append(json.dumps(selected,ensure_ascii=False))
        process.setProgram(sys.executable);process.setArguments(arguments);process.setWorkingDirectory(str(ROOT));process.finished.connect(lambda code,status:self.export_finished(code,path));process.errorOccurred.connect(lambda error:self.export_failed(process.errorString()))
        self.notice.setText('Exportando '+kind+' · Historial conservado.');process.start()
    def export_failed(self,message):
        if self.export_process is None:return
        self.show_error('No se pudo exportar: '+message);self.cleanup_export()
    def export_finished(self,code,path):
        if self.export_process is None:return
        errors=bytes(self.export_process.readAllStandardError()).decode('utf8',errors='replace')
        if code==0:self.last_export=Path(path);self.notice.setText('Exportación guardada · '+str(path));self.notice.setStyleSheet('color:#287f65;')
        else:self.show_error('No se pudo exportar: '+(errors or f'código {code}'))
        self.cleanup_export()
    def cleanup_export(self):
        process=self.export_process;self.export_process=None
        if process:process.deleteLater()
        if self.export_snapshot:self.export_snapshot.unlink(missing_ok=True);self.export_snapshot=None
        self.export_button.setEnabled(self.active and bool(self.session.registro.muestras))
    def closeEvent(self,event:QCloseEvent):
        if self.export_process is not None:
            self.notice.setText('Esperá a que termine la exportación antes de cerrar.');event.ignore();return
        self.consume();self.replay_timer.stop();self.replay_paused=False;self.controller.disconnect();self.update_pause_ui();self.connection_badge.setText('●  RECEPCIÓN DETENIDA')
        if self.active:
            try:self.session.guardar(self.session_path)
            except Exception as exc:self.show_error('Guardá la sesión desde Datos antes de cerrar. '+str(exc));event.ignore();return
        self.timer.stop();self.refresh_timer.stop();event.accept()

def main():
    app=QApplication.instance() or QApplication(sys.argv);app.setApplicationName('MEGAORNO');app.setOrganizationName('MEGAORNO');app.setFont(QFont('Segoe UI',10));window=App();window.show();return app.exec()

if __name__=='__main__':sys.exit(main())
