// Cliente WCF .NET Framework: las operaciones se obtienen del contrato real.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.ServiceModel;
using System.ServiceModel.Channels;
using System.ServiceModel.Description;
using System.Threading;
using System.Web.Script.Serialization;
using System.Xml;
using System.Xml.Linq;

namespace HornoWcf {
[ServiceContract]
public interface IRawRequestReply {
    // WCF correlaciona las respuestas sobre el transporte duplex de net.pipe.
    [OperationContract(Action="*",ReplyAction="*")]
    Message Invoke(Message request);
}
public class Bridge {
    static JavaScriptSerializer json=new JavaScriptSerializer { MaxJsonLength=20000000 };
    static Dictionary<string,object> cfg;
    static string Get(string key,string fallback) { return cfg.ContainsKey(key)?Convert.ToString(cfg[key]):fallback; }
    static void Emit(string kind,object data) { Console.WriteLine(json.Serialize(new {type=kind,data=data}));Console.Out.Flush(); }
    static string Error(Exception e) { return e.GetType().Name+": "+e.Message+(e.InnerException==null?"":" | "+Error(e.InnerException)); }
    static XmlReader Reader(string xml) { return XmlReader.Create(new StringReader(xml),new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=16000000}); }
    static NetNamedPipeBinding Pipe(string security) {
        var b=new NetNamedPipeBinding(security=="none"?NetNamedPipeSecurityMode.None:NetNamedPipeSecurityMode.Transport);
        b.OpenTimeout=TimeSpan.FromSeconds(8);b.SendTimeout=TimeSpan.FromSeconds(10);b.CloseTimeout=TimeSpan.FromSeconds(2);
        b.ReceiveTimeout=TimeSpan.FromMinutes(10);b.MaxReceivedMessageSize=8388608;b.MaxBufferSize=8388608;
        b.ReaderQuotas.MaxArrayLength=1000000;b.ReaderQuotas.MaxStringContentLength=8388608;return b;
    }
    static List<ServiceEndpoint> Import(MetadataSet set) {
        var imp=new WsdlImporter(set);var eps=imp.ImportAllEndpoints().Where(e=>e.Address.Uri.Scheme=="net.pipe").ToList();
        foreach(var err in imp.Errors)Emit("log",err.Message);
        if(eps.Count==0)throw new Exception("Los metadatos no contienen endpoints net.pipe importables.");return eps;
    }
    static List<ServiceEndpoint> LoadEndpoints(string path) {
        using(var reader=XmlReader.Create(path,new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null}))return Import(MetadataSet.ReadFrom(reader));
    }
    static bool Readable(OperationDescription op) {return !op.IsOneWay&&op.Messages.Count>=2&&op.Messages[0].Direction==MessageDirection.Input;}
    static string Body(MessageDescription msg) {
        XElement body=String.IsNullOrEmpty(msg.Body.WrapperName)?null:new XElement(XName.Get(msg.Body.WrapperName,msg.Body.WrapperNamespace??""));
        var parts=msg.Body.Parts.Select(p=>new XElement(XName.Get(p.Name,p.Namespace??""),"COMPLETAR_PARAMETRO")).ToArray();
        if(body!=null){body.Add(parts);return body.ToString(SaveOptions.DisableFormatting);}
        return String.Join("",parts.Select(p=>p.ToString(SaveOptions.DisableFormatting)).ToArray());
    }
    static void Describe(MetadataSet set,string path) {
        var eps=Import(set);var ops=new List<object>();
        for(int ei=0;ei<eps.Count;ei++) {
            var ep=eps[ei];foreach(var op in ep.Contract.Operations) {
                if(!Readable(op))continue;var input=op.Messages[0];
                ops.Add(new {endpoint_index=ei,endpoint=ep.Address.Uri.ToString(),contract=ep.Contract.Name,name=op.Name,action=input.Action,body=Body(input),parameters=input.Body.Parts.Count,headers=input.Headers.Count,duplex=ep.Contract.CallbackContractType!=null});
            }
        }
        Emit("metadata",new {path=path,operations=ops,endpoint_count=eps.Count});
    }
    static void Discover() {
        var baseUri=Get("endpoint","net.pipe://localhost/MT4Data").TrimEnd('/');
        if(!baseUri.StartsWith("net.pipe://",StringComparison.OrdinalIgnoreCase))throw new Exception("Se necesita una dirección net.pipe.");
        var addresses=new List<string>{baseUri};if(!baseUri.EndsWith("/mex",StringComparison.OrdinalIgnoreCase))addresses.Add(baseUri+"/mex");
        var errors=new List<string>();
        foreach(string address in addresses)foreach(string security in new[]{"transport","none"}) {
            Emit("log","Buscando metadatos: "+address+" ("+security+")");
            try {
                var client=new MetadataExchangeClient(Pipe(security));client.ResolveMetadataReferences=true;client.MaximumResolvedReferences=30;client.OperationTimeout=TimeSpan.FromSeconds(8);
                var meta=client.GetMetadata(new EndpointAddress(address));string path=Get("metadata_path","metadata.xml");
                using(var writer=XmlWriter.Create(path,new XmlWriterSettings {Indent=true}))meta.WriteTo(writer);
                Describe(meta,path);return;
            }catch(Exception ex){errors.Add(address+" ["+security+"] "+Error(ex));Emit("log",errors.Last());}
        }
        Emit("error","No fue posible obtener el contrato WCF. El servicio puede funcionar sin publicar metadatos. Se necesita el contrato del fabricante (Action, cuerpo XML y binding), o habilitar su endpoint MEX. "+String.Join("\n",errors));
    }
    static Binding BindingForConfig(out EndpointAddress address) {
        string metadata=Get("metadata_path","");
        if(!String.IsNullOrEmpty(metadata)&&File.Exists(metadata)&&Get("manual","false")!="true") {
            var eps=LoadEndpoints(metadata);int ix=Int32.Parse(Get("endpoint_index","0"));
            if(ix<0||ix>=eps.Count)throw new Exception("Índice de endpoint inválido.");
            var ep=eps[ix];address=ep.Address;var b=ep.Binding;b.OpenTimeout=TimeSpan.FromSeconds(8);b.SendTimeout=TimeSpan.FromSeconds(10);b.CloseTimeout=TimeSpan.FromSeconds(2);return b;
        }
        address=new EndpointAddress(Get("endpoint","net.pipe://localhost/MT4Data"));return Pipe(Get("security","transport"));
    }
    static void Query(bool repeat) {
        string action=Get("action","");string body=Get("body","");
        if(String.IsNullOrEmpty(action)||String.IsNullOrEmpty(body)||body.Contains("COMPLETAR_PARAMETRO"))throw new Exception("Seleccioná una operación de lectura y completá sus parámetros XML.");
        using(var reader=Reader(body)){XElement.Load(reader);}
        EndpointAddress endpoint;Binding binding=BindingForConfig(out endpoint);
        if(endpoint.Uri.Scheme!="net.pipe")throw new Exception("Solo se admite net.pipe en este puente.");
        ChannelFactory<IRawRequestReply> factory=null;IClientChannel channel=null;
        try {
            factory=new ChannelFactory<IRawRequestReply>(binding,endpoint);
            var proxy=factory.CreateChannel();channel=(IClientChannel)proxy;channel.OperationTimeout=TimeSpan.FromSeconds(10);
            channel.Open();Emit("transport_open",endpoint.Uri.ToString());
            int interval=Int32.Parse(Get("poll_seconds","5"));if(interval<1||interval>3600)throw new Exception("Sondeo debe estar entre 1 y 3600 segundos.");
            do {
                using(var reader=Reader(body))using(var request=Message.CreateMessage(binding.MessageVersion,action,reader)) {
                    endpoint.ApplyTo(request);
                    using(var response=proxy.Invoke(request)) {
                        bool fault=response.IsFault;string xml;
                        using(var sw=new StringWriter()){using(var xw=XmlWriter.Create(sw,new XmlWriterSettings {OmitXmlDeclaration=true}))response.WriteMessage(xw);xml=sw.ToString();}
                        Emit(fault?"fault":"response",xml);
                        if(fault)throw new Exception("El servicio respondió un SOAP Fault. Revisá el diagnóstico y la operación elegida.");
                    }
                }
                if(repeat)Thread.Sleep(interval*1000);
            }while(repeat);
            channel.Close();factory.Close();
        }finally {
            if(channel!=null&&channel.State!=CommunicationState.Closed)channel.Abort();
            if(factory!=null&&factory.State!=CommunicationState.Closed)factory.Abort();
        }
    }
    public static int Main(string[] args) {
        Console.OutputEncoding=new System.Text.UTF8Encoding(false);
        Console.InputEncoding=new System.Text.UTF8Encoding(false);
        try {
            if(args.Length!=1)throw new Exception("Uso: Bridge.exe configuracion.json");
            cfg=json.Deserialize<Dictionary<string,object>>(args[0]=="-"?Console.In.ReadToEnd():File.ReadAllText(args[0]));
            switch(Get("mode","discover")) {
                case "mt_list":case "mt_probe":case "mt_poll":MadgeTechClient.Run(cfg,Emit,Pipe(Get("security","transport")));break;
                case "discover":Discover();break;
                case "probe":Query(false);break;
                case "poll":Query(true);break;
                default:throw new Exception("Modo desconocido.");
            }
            return 0;
        }catch(Exception e){Emit("error",Error(e));return 1;}
    }
}}
