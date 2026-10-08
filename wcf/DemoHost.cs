// Servicio de prueba propio. No representa el contrato real de MadgeTech.
using System;
using System.Runtime.Serialization;
using System.ServiceModel;
using System.ServiceModel.Description;

namespace HornoDemo {
    [DataContract(Namespace="urn:horno:demo:datos")]
    public class Lectura {
        [DataMember] public string Fecha;
        [DataMember] public string Canal;
        [DataMember] public double Temperatura;
    }
    [ServiceContract(Namespace="urn:horno:demo")]
    public interface ILecturas { [OperationContract] Lectura[] GetLecturas(); }
    public class Servicio : ILecturas {
        static DateTime inicio=DateTime.Now;
        public Lectura[] GetLecturas() {
            var now=DateTime.Now;var rounded=new DateTime(now.Year,now.Month,now.Day,now.Hour,now.Minute,now.Second);
            double temperature=25+Math.Max(0,(rounded-inicio).TotalHours)*150;
            return new [] {
                new Lectura {Fecha=rounded.ToString("yyyy-MM-ddTHH:mm:ss"),Canal="DEMO - Canal 1",Temperatura=temperature},
                new Lectura {Fecha=rounded.ToString("yyyy-MM-ddTHH:mm:ss"),Canal="DEMO - Canal 2",Temperatura=temperature+3}
            };
        }
    }
    class Program {
        public static void Main() {
            const string address="net.pipe://localhost/HornoDemo";
            using(var host=new ServiceHost(typeof(Servicio),new Uri(address))) {
                host.AddServiceEndpoint(typeof(ILecturas),new NetNamedPipeBinding(),"");
                host.Description.Behaviors.Add(new ServiceMetadataBehavior());
                host.AddServiceEndpoint(ServiceMetadataBehavior.MexContractName,MetadataExchangeBindings.CreateMexNamedPipeBinding(),"mex");
                host.Open();Console.WriteLine("DEMO WCF: datos artificiales. No hay conexion con MadgeTech.");
                Console.WriteLine("Direccion: "+address);Console.WriteLine("Descubrir -> GetLecturas -> Leer una respuesta.");
                Console.WriteLine("Campos: Lectura / Fecha / Temperatura / Canal. Unidad: grados C.");
                Console.WriteLine("Mantenga esta ventana abierta. ENTER para detener.");Console.ReadLine();host.Close();
            }
        }
    }
}
