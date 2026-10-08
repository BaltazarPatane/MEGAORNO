"""Puente WCF y conversión explícita de respuestas XML a muestras."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import threading
import xml.etree.ElementTree as ET
from models import numero, fecha_local


_BUILD_LOCK=threading.Lock()


def carpeta_madgetech():
    candidates=[Path(os.environ.get(key,default))/'MadgeTech'/'MadgeTech 4'
                for key,default in [('ProgramFiles(x86)',r'C:\Program Files (x86)'),('ProgramFiles',r'C:\Program Files')]]
    return str(next((p for p in candidates if (p/'WCFInterop.dll').is_file()),candidates[0]))


def decodificar_madgetech(data,unit='Auto',valid_status='Auto',*,diagnostics=None):
    """Interpreta tipos reflejados; nunca considera 0 un estado válido por defecto."""
    if not isinstance(data,dict):raise ValueError('Respuesta MadgeTech inválida: se esperaba un objeto.')
    serial=data.get('serial','')
    if not isinstance(serial,str) or not serial.strip():raise ValueError('Lectura MadgeTech sin número de serie.')
    serial=serial.strip()
    dt=fecha_local(data.get('timestamp',''))
    if dt.year<1900:raise ValueError('Fecha de medición MadgeTech inválida.')
    channels=data.get('channels')
    if not isinstance(channels,list):raise ValueError('Falta la lista ChannelValues de MadgeTech.')
    normalize=lambda s:''.join(c for c in str(s).casefold() if c.isalnum())
    units={}
    for target,aliases in [('°C',['C','°C','Celsius','Centigrade','DegreeC','DegreesC','DegreeCelsius','DegreesCelsius','DegC','TemperatureCelsius']),
                           ('°F',['F','°F','Fahrenheit','DegreeF','DegreesF','DegreeFahrenheit','DegreesFahrenheit','DegF','TemperatureFahrenheit']),
                           ('K',['K','Kelvin','DegreeKelvin','DegreesKelvin','TemperatureKelvin'])]:
        units.update({normalize(alias):target for alias in aliases})
    good={'ok','success','valid','normal','good','noerror','validreading','readingok'}
    no_sensor={'nosensor','sensordisconnected','sensornotconnected','disconnected',
               'notconnected','opencircuit','opensensor','openinput','nodata','sindato',
               'empty','disabled','channeldisabled','sensorerror','overrange','underrange'}
    rows=[];errors=[];positions=set()
    for channel in channels:
        if not isinstance(channel,dict):raise ValueError('Canal MadgeTech inválido: se esperaba un objeto.')
        pos=channel.get('position')
        if isinstance(pos,bool) or not isinstance(pos,int) or pos<1 or pos in positions:raise ValueError('Posición WCF inválida o duplicada.')
        positions.add(pos);name=f'{serial} / Posición WCF {pos}';value=None
        status=str(channel.get('status',''));source_unit=str(channel.get('unit',''))
        raw_value=channel.get('value')
        missing=raw_value is None or (isinstance(raw_value,str) and not raw_value.strip())
        issue=None
        if missing:
            # Preserve the invalid sample (it breaks the derivative), but an
            # empty physical input is not a new diagnostic error each poll.
            issue=dict(channel=name,key=('missing',),quiet=True,message=f'{name}: sin lectura.')
            rows.append((dt,name,None))
            if diagnostics is not None:diagnostics.append(issue)
            continue
        category='status'
        try:
            if not (normalize(status) in good if valid_status=='Auto' else bool(valid_status) and status==valid_status):
                raise ValueError(f'estado {status!r}; lectura no utilizable con el estado válido seleccionado')
            category='unit'
            detected=units.get(normalize(source_unit)) if unit=='Auto' else unit
            if detected not in ('°C','°F','K'):raise ValueError(f'unidad {source_unit!r} no reconocida como temperatura; confirmar en MadgeTech')
            category='value'
            value=numero(channel.get('value'))
            if detected=='°F':value=(value-32)/9*5
            elif detected=='K':value-=273.15
            value=numero(value)
        except (ValueError,TypeError) as error:
            value=None;message=f'{name}: {error}. Se registra sin dato.';errors.append(message)
            detail=normalize(status) if category=='status' else normalize(source_unit) if category=='unit' else ''
            issue=dict(channel=name,key=(category,detail),quiet=category=='status' and detail in no_sensor,message=message)
        if issue is not None and diagnostics is not None:diagnostics.append(issue)
        rows.append((dt,name,value))
    return rows,errors


def local(tag):return tag.rsplit('}',1)[-1]


def campo(node,path):
    if path=='.':return (node.text or '').strip()
    current=node
    for name in path.strip('/').split('/'):
        if name.startswith('@'):return current.attrib.get(name[1:])
        current=next((c for c in current if local(c.tag)==name),None)
        if current is None:return None
    return (current.text or '').strip()


def describir_xml(xml):
    root=ET.fromstring(xml);groups={}
    for node in root.iter():
        if len(node) and any(not len(c) for c in node):
            groups.setdefault(local(node.tag),{local(c.tag):(c.text or '').strip()[:100] for c in node if not len(c)})
    return groups


def decodificar(xml,mapping,allow_empty=False):
    if len(xml)>16000000:raise ValueError('Respuesta XML demasiado grande.')
    root=ET.fromstring(xml);tag=mapping.get('record','').strip()
    if not tag:raise ValueError('Elegí el elemento XML que representa una lectura.')
    nodes=[n for n in root.iter() if local(n.tag)==tag]
    if not nodes:
        if allow_empty:return [],[]
        raise ValueError(f'No se encontró el elemento {tag!r} en la respuesta.')
    rows=[];errors=[]
    for i,node in enumerate(nodes,1):
        try:
            dt=fecha_local(campo(node,mapping['time']));value=numero(campo(node,mapping['value']))
            channel=campo(node,mapping['channel']) if mapping.get('channel') else mapping.get('constant','')
            if not channel:raise ValueError('Falta el identificador de canal.')
            device=campo(node,mapping['device']) if mapping.get('device') else ''
            if device:channel=str(device)+' / '+str(channel)
            unit=mapping.get('unit','°C')
            if unit=='°F':value=(value-32)/9*5
            elif unit=='K':value-=273.15
            elif unit!='°C':raise ValueError('Unidad no soportada.')
            rows.append((dt,str(channel),numero(value)))
        except (ValueError,TypeError,KeyError) as e:errors.append(f'Lectura {i}: {e}')
    if not rows:raise ValueError('Ninguna lectura válida: '+'; '.join(errors[:5]))
    return rows,errors


def redact_diagnostic(value,config):
    if isinstance(value,str):
        for key in ('password','username'):
            secret=config.get(key)
            if isinstance(secret,str) and secret:value=value.replace(secret,'[oculto]')
        return value
    if isinstance(value,dict):return {k:redact_diagnostic(v,config) for k,v in value.items()}
    if isinstance(value,list):return [redact_diagnostic(v,config) for v in value]
    return value


class WcfBridge:
    def __init__(self,events):
        self.events=events;self.process=None;self.stop_event=threading.Event();self.thread=None;self.request_id=0;self._lock=threading.RLock()

    @property
    def running(self):return self.thread is not None and self.thread.is_alive()

    def start(self,config,folder):
        with self._lock:
            if self.running:raise ValueError('Hay una operación WCF en curso.')
            self.request_id+=1;self.stop_event.clear();self.thread=threading.Thread(target=self._run,args=(dict(config),Path(folder),self.request_id),daemon=True);self.thread.start()

    def _run(self,config,folder,request_id):
        def emit(event):
            # Diagnostics may contain authentication error text from the vendor.
            # Keep raw measurement payloads untouched for metrological traceability.
            if event.get('type') in ('log','error','fault'):
                event=dict(event)
                event['data']=redact_diagnostic(event.get('data',''),config)
            self.events.put(dict(event,request_id=request_id))
        reported_error=False
        try:
            if os.name!='nt':raise RuntimeError('La tubería WCF requiere Windows y .NET Framework 4.x.')
            folder.mkdir(parents=True,exist_ok=True);base=Path(__file__).resolve().parent/'wcf';sources=[base/'Bridge.cs',base/'MadgeTechClient.cs'];exe=folder/'HornoWcfBridge.exe'
            windir=Path(os.environ.get('WINDIR',r'C:\Windows'))
            csc=next((p for p in [windir/'Microsoft.NET/Framework64/v4.0.30319/csc.exe',windir/'Microsoft.NET/Framework/v4.0.30319/csc.exe'] if p.exists()),None)
            if not csc:raise RuntimeError('No se encontró el compilador de .NET Framework. Se necesita .NET Framework 4.8 en Windows.')
            # A cancelled instance may still be finishing csc while a new
            # session connects. Share one build gate so its executable/stamp
            # cannot be replaced by two compiler processes simultaneously.
            with _BUILD_LOCK:
                if self.stop_event.is_set():return
                fingerprint=hashlib.sha256(b'v2.1-x86'+b''.join(source.read_bytes() for source in sources)).hexdigest();stamp=folder/'bridge_build.sha256'
                if not exe.exists() or not stamp.exists() or stamp.read_text(encoding='ascii')!=fingerprint:
                    emit({'type':'log','data':'Compilando el puente WCF local…'})
                    cmd=[str(csc),'/nologo','/target:exe','/platform:x86','/out:'+str(exe),'/r:System.ServiceModel.dll','/r:System.Runtime.Serialization.dll','/r:System.Web.Services.dll','/r:System.Web.Extensions.dll','/r:System.Xml.Linq.dll']+[str(source) for source in sources]
                    result=subprocess.run(cmd,capture_output=True,text=True,errors='replace',timeout=50,creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode:raise RuntimeError(result.stdout+'\n'+result.stderr)
                    stamp.write_text(fingerprint,encoding='ascii')
            if self.stop_event.is_set():return
            # Configuración por stdin: las credenciales no se escriben en disco ni en la línea de comandos.
            self.process=subprocess.Popen([str(exe),'-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
            self.process.stdin.write(json.dumps(config,ensure_ascii=False));self.process.stdin.close()
            if self.stop_event.is_set():self.process.terminate()
            for line in self.process.stdout:
                try:
                    event=json.loads(line.lstrip('\ufeff'))
                    if not isinstance(event,dict) or 'type' not in event:raise ValueError('Evento WCF inválido.')
                    if event['type'] in ('error','fault'):reported_error=True
                    emit(event)
                except json.JSONDecodeError:emit({'type':'log','data':line.strip()})
            code=self.process.wait()
            if code and not self.stop_event.is_set():emit({'type':'log' if reported_error else 'error','data':f'El puente terminó con código {code}. Revisá el diagnóstico.'})
        except Exception as e:
            if not self.stop_event.is_set():emit({'type':'error','data':str(e)})
        finally:
            if self.process:
                try:
                    if self.process.poll() is None:self.process.terminate()
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:self.process.kill();self.process.wait(timeout=2)
                    except (OSError,subprocess.TimeoutExpired):pass
                except OSError:pass
                finally:
                    for stream in (self.process.stdin,self.process.stdout):
                        if stream is not None:
                            try:stream.close()
                            except OSError:pass
            emit({'type':'finished','data':config.get('mode','')})

    def stop(self):
        with self._lock:
            self.request_id+=1;self.stop_event.set()
            if self.process and self.process.poll() is None:
                try:self.process.terminate()
                except OSError:pass  # Process may have exited between poll and terminate.
