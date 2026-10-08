// Adaptador del contrato observado en WCFInterop 1.1.0.2.
// Usa las bibliotecas de la instalación local; no redistribuye DLL del fabricante.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.ServiceModel;
using System.ServiceModel.Channels;
using System.ServiceModel.Description;
using System.Threading;

namespace HornoWcf {
public static class MadgeTechClient {
    static object Property(object value,string name) {
        if(value==null)return null;
        var property=value.GetType().GetProperty(name);
        if(property==null)throw new Exception("El contrato no contiene la propiedad "+name+" en "+value.GetType().FullName);
        return property.GetValue(value,null);
    }
    static Exception Unwrap(Exception error) {
        while(error is TargetInvocationException && error.InnerException!=null)error=error.InnerException;
        return error;
    }
    static string FaultName(Exception error) {
        error=Unwrap(error);var type=error.GetType();
        if(type.IsGenericType && type.GetGenericTypeDefinition()==typeof(FaultException<>))return type.GetGenericArguments()[0].Name;
        return type.Name;
    }
    static object Call(Type contract,object proxy,string name,params object[] arguments) {
        try{return contract.GetMethod(name).Invoke(proxy,arguments);}catch(TargetInvocationException ex){throw Unwrap(ex);}
    }
    static string Friendly(Exception error) {
        switch(FaultName(error)) {
            case "UnauthorizedAccessException":return "MadgeTech rechazó la autenticación. Revisá las credenciales configuradas para la salida WCF y activá Usar Authenticate si corresponde.";
            case "DeviceOfflineException":return "MadgeTech informa que el equipo está desconectado. Revisá el equipo en MadgeTech 4.";
            case "DeviceNotFoundException":return "MadgeTech no encuentra ese número de serie. Volvé a buscar los equipos.";
            case "CommunicationLostException":return "MadgeTech informa pérdida de comunicación con el adquisidor.";
            default:return Unwrap(error).Message;
        }
    }
    public static object Reading(object data,string requestedSerial) {
        if(data==null)return null;
        string serial=Convert.ToString(Property(data,"Serial"),CultureInfo.InvariantCulture);
        if(String.IsNullOrWhiteSpace(serial)||serial!=requestedSerial)throw new Exception("La respuesta no coincide con el número de serie solicitado.");
        object timestamp=Property(data,"TimeStamp");
        if(!(timestamp is DateTime)||(DateTime)timestamp==DateTime.MinValue)throw new Exception("MadgeTech devolvió una fecha de medición inválida.");
        var values=Property(data,"ChannelValues") as IEnumerable;
        if(values==null)return null;
        var channels=new List<object>();int position=0;
        foreach(var value in values) {
            position++;
            if(value==null){channels.Add(new {position=position,unit="",status="SinDato",value=(string)null});continue;}
            // El miembro serializado Unit es el campo privado _unit (UnitBase),
            // no la propiedad Unit, que construye un objeto y puede devolver null.
            var unitField=value.GetType().GetField("_unit",BindingFlags.Instance|BindingFlags.NonPublic);
            if(unitField==null)throw new Exception("El contrato cambió: no se encuentra el miembro serializado Unit (_unit).");
            var unitBase=unitField.GetValue(value);
            channels.Add(new {position=position,unit=Convert.ToString(unitBase,CultureInfo.InvariantCulture),
                status=Convert.ToString(Property(value,"Status"),CultureInfo.InvariantCulture),
                value=Convert.ToDouble(Property(value,"Value"),CultureInfo.InvariantCulture).ToString("R",CultureInfo.InvariantCulture)});
        }
        return new {serial=serial,timestamp=((DateTime)timestamp).ToString("o",CultureInfo.InvariantCulture),channels=channels};
    }
    public static void Run(Dictionary<string,object> cfg,Action<string,object> emit,Binding binding,PollGate gate=null) {
        Func<string,string,string> get=(key,fallback)=>cfg.ContainsKey(key)?Convert.ToString(cfg[key]):fallback;
        string directory=Path.GetFullPath(get("vendor_dir",""));
        foreach(string name in new[]{"WCFInterop.dll","DeviceComm.dll"})
            if(!File.Exists(Path.Combine(directory,name)))throw new Exception("Falta "+name+". Seleccioná la carpeta donde está instalado MadgeTech 4.");
        ResolveEventHandler resolve=(sender,args)=>{
            string name=new AssemblyName(args.Name).Name;
            string path=Path.Combine(directory,name+".dll");
            return File.Exists(path)?Assembly.LoadFrom(path):null;
        };
        AppDomain.CurrentDomain.AssemblyResolve+=resolve;
        ChannelFactory factory=null;IClientChannel channel=null;
        try {
            var assembly=Assembly.LoadFrom(Path.Combine(directory,"WCFInterop.dll"));
            var contract=assembly.GetType("WCFInterop.IMT4RealTimeNotifierService",true);
            var description=ContractDescription.GetContract(contract);
            foreach(string name in new[]{"Authenticate","GetConnectedSerialNumbers","RequestLatestReading"})
                if(contract.GetMethod(name)==null)throw new Exception("La biblioteca instalada no expone "+name+".");
            if(description.CallbackContractType!=null)throw new Exception("Esta versión del contrato requiere callbacks y necesita adaptación.");
            var device=Assembly.LoadFrom(Path.Combine(directory,"DeviceComm.dll"));
            var statusType=device.GetType("MadgeTech.Device+ReadingStatus",true);
            var unitType=device.GetType("MadgeTech.Units.UnitBase",true);
            emit("mt_contract",new {version=assembly.GetName().Version.ToString(),contract=description.Name,
                session=description.SessionMode.ToString(),statuses=Enum.GetNames(statusType),units=Enum.GetNames(unitType),
                operations=description.Operations.Select(op=>new {name=op.Name,action=op.Messages[0].Action}).ToArray()});
            var endpoint=new EndpointAddress(get("endpoint","net.pipe://localhost/MT4Data"));
            if(endpoint.Uri.Scheme!="net.pipe" || !endpoint.Uri.IsLoopback)throw new Exception("La conexión debe ser una tubería net.pipe de esta PC (localhost).");
            var factoryType=typeof(ChannelFactory<>).MakeGenericType(contract);
            factory=(ChannelFactory)Activator.CreateInstance(factoryType,new object[]{binding,endpoint});
            var proxy=factoryType.GetMethod("CreateChannel",Type.EmptyTypes).Invoke(factory,null);
            channel=(IClientChannel)proxy;channel.OperationTimeout=TimeSpan.FromSeconds(10);channel.Open();
            emit("transport_open",endpoint.Uri.ToString());
            if(get("authenticate","false")=="true") {
                // Se autentica y consulta sobre el mismo canal/sesión. No se registra la contraseña.
                try{Call(contract,proxy,"Authenticate",get("username",""),get("password",""));}
                catch(Exception){throw new Exception("Authenticate fue rechazado o no pudo completarse. Revisá las credenciales WCF y la conexión de MadgeTech.");}
                emit("log","Authenticate aceptado en esta sesión WCF.");
            }
            var serials=((IEnumerable)Call(contract,proxy,"GetConnectedSerialNumbers")??new string[0]).Cast<object>().Select(x=>Convert.ToString(x)).ToArray();
            emit("mt_devices",serials);
            string mode=get("mode","mt_list");
            if(mode!="mt_list") {
                string serial=get("serial","");
                // Enumerar y leer en la misma sesión autenticada. El caso habitual
                // de una notebook con un adquisidor no requiere pasos manuales.
                if(String.IsNullOrWhiteSpace(serial)) {
                    if(serials.Length==1)serial=serials[0];
                    else if(serials.Length>1) {
                        emit("mt_select",serials);
                        channel.Close();factory.Close();return;
                    }
                    else throw new Exception("MadgeTech no informa equipos conectados. Revisá el equipo en MadgeTech 4.");
                }
                if(!serials.Contains(serial))throw new Exception("El número de serie seleccionado no figura entre los equipos conectados. Usá Buscar equipos.");
                int interval=Int32.Parse(get("poll_seconds","5"));
                if(interval<1||interval>3600)throw new Exception("Sondeo debe estar entre 1 y 3600 segundos.");
                do {
                    int ticket=0;
                    if(gate!=null && !gate.Next(out ticket))break;
                    Action<string,object> publish=(kind,data)=>{
                        if(gate==null)emit(kind,data);else gate.Publish(ticket,kind,data,emit);
                    };
                    try {
                        var reading=Reading(Call(contract,proxy,"RequestLatestReading",serial),serial);
                        if(reading==null)publish("mt_waiting","MadgeTech todavía no devuelve una lectura. Esperando adquisición en tiempo real.");
                        else publish("mt_reading",reading);
                    }catch(Exception error) {
                        if(FaultName(error)=="RealTimeNotAvailableException")publish("mt_waiting","MadgeTech informa que no hay lectura en tiempo real disponible. Iniciá la adquisición en MadgeTech 4.");
                        else throw;
                    }
                    if(mode=="mt_poll") {
                        if(gate==null)Thread.Sleep(interval*1000);else gate.WaitInterval(interval*1000,ticket);
                    }
                }while(mode=="mt_poll");
            }
            channel.Close();factory.Close();
        }catch(Exception error){throw new Exception(FaultName(error)+": "+Friendly(error));}
        finally {
            if(channel!=null&&channel.State!=CommunicationState.Closed)channel.Abort();
            if(factory!=null&&factory.State!=CommunicationState.Closed)factory.Abort();
            AppDomain.CurrentDomain.AssemblyResolve-=resolve;
        }
    }
}}
