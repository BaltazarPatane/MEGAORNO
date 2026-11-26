// Native desktop entry point. Python is private to this installation.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

[assembly: AssemblyTitle("MEGAORNO")]
[assembly: AssemblyDescription("Supervisión de tratamientos térmicos")]
[assembly: AssemblyProduct("MEGAORNO")]
[assembly: AssemblyCompany("MEGAORNO - Astillero Río Santiago")]
[assembly: AssemblyVersion("3.2.0.0")]
[assembly: AssemblyFileVersion("3.2.0.1")]

internal static class Launcher {
    // CommandLineToArgvW quoting, including a trailing backslash in an argument.
    private static string Quote(string value) {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char ch in value) {
            if (ch == '\\') { slashes++; continue; }
            if (ch == '"') {
                result.Append('\\', slashes * 2 + 1); result.Append(ch);
            } else {
                result.Append('\\', slashes); result.Append(ch);
            }
            slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }

    [STAThread]
    private static int Main(string[] args) {
        bool selfTest = args.Length == 2 && args[0] == "--self-test";
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string logFolder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HornoMadgeTech", "logs");
        string log = Path.Combine(logFolder, "inicio_" + DateTime.Now.ToString("yyyyMMdd_HHmmss_fff") + "_" + Process.GetCurrentProcess().Id + ".log");
        try {
            Directory.CreateDirectory(logFolder);
            string python = Path.Combine(root, "runtime", "python.exe");
            string entry = Path.Combine(root, selfTest ? "tools\\installed_smoke.py" : "app.py");
            if (!File.Exists(python) || !File.Exists(entry))
                throw new FileNotFoundException("La instalación está incompleta. Ejecutá nuevamente el instalador de MEGAORNO.");
            using (var writer = new StreamWriter(log, true, new UTF8Encoding(false))) {
                writer.AutoFlush = true;
                writer.WriteLine("MEGAORNO - " + DateTime.Now.ToString("o"));
                writer.WriteLine("Instalación: " + root);
                var start = new ProcessStartInfo(python) {
                    Arguments = "-I -B -u -X utf8 " + Quote(entry) + (selfTest ? " --output " + Quote(Path.GetFullPath(args[1])) : ""),
                    WorkingDirectory = root,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding = Encoding.UTF8
                };
                if (selfTest) start.EnvironmentVariables["QT_QPA_PLATFORM"] = "offscreen";
                object gate = new object();
                using (var process = new Process { StartInfo = start }) {
                    DataReceivedEventHandler receive = (sender, e) => {
                        if (e.Data != null) lock (gate) writer.WriteLine(e.Data);
                    };
                    process.OutputDataReceived += receive; process.ErrorDataReceived += receive;
                    process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine();
                    process.WaitForExit();
                    int exitCode = process.ExitCode;
                    writer.WriteLine("Código de salida: " + exitCode);
                    if (exitCode != 0 && !selfTest)
                        MessageBox.Show("MEGAORNO no pudo completar el inicio.\n\nDetalle del error:\n" + log,
                            "MEGAORNO", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return exitCode;
                }
            }
        } catch (Exception error) {
            try { File.AppendAllText(log, error.ToString() + Environment.NewLine, Encoding.UTF8); } catch { }
            if (!selfTest) MessageBox.Show(error.Message + "\n\nRegistro:\n" + log, "MEGAORNO", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
