"""Build the complete offline Windows installer on a Windows x64 host.

Dependencies are installed into the payload at BUILD time, never on the user's
computer. The destination machine needs no system Python, pip or build tools.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build'/'windows'
SOURCE=ROOT/'installer'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def run(arguments,**kwargs):
    print('Ejecutando:',str(arguments[0]),flush=True)
    subprocess.run([str(a) for a in arguments],check=True,**kwargs)


def download(url,destination):
    print('Descargando',destination.name,flush=True)
    request=urllib.request.Request(url,headers={'User-Agent':'MEGAORNO-installer-build/1'})
    with urllib.request.urlopen(request,timeout=180) as response,destination.open('wb') as stream:
        shutil.copyfileobj(response,stream)
    if destination.stat().st_size<100000:
        raise RuntimeError('La descarga no tiene el tamaño esperado: '+destination.name)


def compiler():
    candidates=[Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET'/'Framework64'/'v4.0.30319'/'csc.exe',
                Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET'/'Framework'/'v4.0.30319'/'csc.exe']
    return next((p for p in candidates if p.is_file()),None)


def main():
    if os.name!='nt' or platform.machine().lower() not in ('amd64','x86_64'):
        raise RuntimeError('El instalador debe compilarse en Windows x64.')
    dependencies=json.loads((SOURCE/'dependencies.json').read_text(encoding='utf-8'))
    python=dependencies['python'];version=(ROOT/'VERSION').read_text().strip()
    if platform.python_version()!=python['version']:
        raise RuntimeError('Usá Python '+python['version']+' para compilar este paquete.')
    if BUILD.exists():shutil.rmtree(BUILD)
    payload=BUILD/'payload';prerequisites=BUILD/'prerequisites';dist=BUILD/'dist'
    for folder in [payload,prerequisites,dist]:folder.mkdir(parents=True)
    runtime=payload/'runtime';runtime.mkdir()
    archive=BUILD/'python-embedded.zip';download(python['url'],archive)
    if digest(archive)!=python['sha256']:raise RuntimeError('El SHA-256 del Python oficial no coincide.')
    with zipfile.ZipFile(archive) as package:package.extractall(runtime)
    pth=next(runtime.glob('python*._pth'))
    zip_name=next(runtime.glob('python*.zip')).name
    pth.write_text(zip_name+'\n.\nLib/site-packages\n..\nimport site\n',encoding='ascii')
    site=runtime/'Lib'/'site-packages'
    run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir',
         '--require-hashes','--only-binary=:all:','--no-compile','--target',site,'-r',ROOT/'requirements.lock'])
    for name in ['app.py','gui.py','acquisition.py','live.py','models.py','charts.py','reports.py','VERSION','requirements.lock']:
        shutil.copy2(ROOT/name,payload/name)
    for folder in ['ui','wcf']:
        shutil.copytree(ROOT/folder,payload/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.exe','*.build.json'))
    (payload/'ejemplos').mkdir();shutil.copy2(ROOT/'ejemplos'/'R59022 MultiChannel.xlsx',payload/'ejemplos')
    (payload/'tools').mkdir()
    for name in ['export_session.py','installed_smoke.py']:shutil.copy2(ROOT/'tools'/name,payload/'tools'/name)
    shutil.copy2(SOURCE/'LEEME_INSTALACION.txt',payload/'LEEME_INSTALACION.txt')
    csc=compiler()
    if csc is None:raise RuntimeError('La compilación requiere el compilador de .NET Framework 4.x.')
    bridge=payload/'wcf'/'HornoWcfBridge.exe'
    bridge_sources=[payload/'wcf'/name for name in ['Bridge.cs','MadgeTechClient.cs','PollGate.cs']]
    run([csc,'/nologo','/target:exe','/platform:x86','/out:'+str(bridge),
         '/r:System.ServiceModel.dll','/r:System.Runtime.Serialization.dll','/r:System.Web.Services.dll',
         '/r:System.Web.Extensions.dll','/r:System.Xml.Linq.dll',*bridge_sources])
    fingerprint=hashlib.sha256(b'v2.1-x86'+b''.join(p.read_bytes() for p in bridge_sources)).hexdigest()
    (payload/'wcf'/'HornoWcfBridge.build.json').write_text(json.dumps(dict(
        source_sha256=fingerprint,binary_sha256=digest(bridge)),indent=2),encoding='utf-8')
    run([csc,'/nologo','/utf8output','/target:winexe','/platform:anycpu',
         '/out:'+str(payload/'MEGAORNO.exe'),'/win32icon:'+str(ROOT/'ui'/'icons'/'megaorno.ico'),
         '/r:System.Windows.Forms.dll',SOURCE/'Launcher.cs'])
    shutil.copy2(SOURCE/'Launcher.exe.config',payload/'MEGAORNO.exe.config')
    vendor={}
    for key in ['dotnet48','vc_x64','vc_x86']:
        spec=dependencies[key];path=prerequisites/spec['filename'];download(spec['url'],path)
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
            '-File',str(SOURCE/'verify_microsoft.ps1'),'-Path',str(path)],capture_output=True,text=True,errors='replace')
        if result.returncode:
            raise RuntimeError('Falló la verificación de '+path.name+'\n'+result.stdout+'\n'+result.stderr)
        vendor[key]=json.loads(result.stdout.lstrip('\ufeff'))
        vendor[key]['url']=spec['url'];vendor[key]['filename']=path.name
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions(path=[str(site)])}
    manifest=dict(aplicacion='MEGAORNO',version=version,revision_instalador=1,arquitectura='x64',
                  source_commit=os.environ.get('GITHUB_SHA','compilacion-local'),
                  python=python,paquetes=packages,microsoft=vendor,
                  requirements_sha256=digest(ROOT/'requirements.lock'),icon_sha256=digest(ROOT/'ui'/'icons'/'megaorno.ico'),
                  madgetech_incluido=False,conexion_fisica_verificada=False)
    manifest_path=dist/'componentes.json';manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(manifest_path,payload/'componentes.json')
    test_env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
    run([runtime/'python.exe','-I','-B','-X','utf8',payload/'tools'/'installed_smoke.py','--output',BUILD/'verificacion-payload'],env=test_env)
    iscc=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Inno Setup 6'/'ISCC.exe'
    if not iscc.is_file():raise RuntimeError('Se necesita Inno Setup 6 para compilar el instalador.')
    def vc_version(key):
        match=re.search(r'\d+\.\d+\.\d+\.\d+',vendor[key]['version'])
        if not match:raise RuntimeError('No se reconoce la versión del redistribuible '+key)
        return match.group()
    run([iscc,'/Qp','/DAppVersion='+version,'/DBuildRoot='+str(BUILD),
         '/DVCX64Version='+vc_version('vc_x64'),'/DVCX86Version='+vc_version('vc_x86'),SOURCE/'MEGAORNO.iss'])
    installer=dist/'MEGAORNO-Setup-x64.exe'
    if not installer.is_file() or installer.stat().st_size<20_000_000:raise RuntimeError('No se generó el instalador completo.')
    print('Instalador compilado:',installer,installer.stat().st_size,'bytes',flush=True)


if __name__=='__main__':main()
