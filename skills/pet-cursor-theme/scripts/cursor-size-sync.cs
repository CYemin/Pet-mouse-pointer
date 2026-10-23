// Build with the Windows .NET Framework C# compiler, /target:winexe.
// Usage: cursor-size-sync.exe config.xml | --stop config.xml | --self-test
// No service, administrator privileges, UI, network, or idle polling is used.
// Configuration: <cursorSizeSync enabled="true"><schemeName>Pet theme 48</schemeName>
// <installedDirectory>C:\...\installed</installedDirectory><initialSliderSize>1</initialSliderSize>
// <initialPixelSize>48</initialPixelSize><cursors><cursor role="Arrow" id="32512"
// file="normal.ani"/>...all 17 roles...</cursors></cursorSizeSync>
// The installer owns startup registration. --stop returns 3 on timeout: the
// caller must not restore settings until the helper has acknowledged its exit.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Xml;
using System.Xml.Linq;
using Microsoft.Win32;

internal static class PetCursorSizeSync
{
    private const string CursorKey = @"Control Panel\Cursors";
    private const string AccessibilityKey = @"Software\Microsoft\Accessibility";
    private static readonly string[] Roles = { "Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person" };
    private static readonly uint[] Ids = { 32512, 32651, 32650, 32514, 32515, 32513, 32631, 32648, 32645, 32644, 32642, 32643, 32646, 32516, 32649, 32671, 32672 };
    private static readonly string[] AccessibilityFiles = { "arrow_eoa.cur", "helpsel_eoa.cur", "busy_eoa.cur", "wait_eoa.cur", "cross_eoa.cur", "ibeam_eoa.cur", "pen_eoa.cur", "unavail_eoa.cur", "ns_eoa.cur", "ew_eoa.cur", "nwse_eoa.cur", "nesw_eoa.cur", "move_eoa.cur", "up_eoa.cur", "link_eoa.cur", "pin_eoa.cur", "person_eoa.cur" };
    private static string configPath;
    private static int lastPixelSize;
    private static int lastSliderSize;
    private static int applyCount;

    private sealed class Config
    {
        internal XDocument Document;
        internal string Scheme;
        internal string[] Files = new string[17];
        internal int InitialSlider;
        internal int InitialPixels;
        internal int SavedSlider;
        internal int SavedPixels;
        internal bool Enabled;
    }

    private sealed class Snapshot
    {
        internal int Slider;
        internal int Base;
        internal bool Owned;
        internal bool BuiltIn;
    }

    private sealed class RegistryWatch : IDisposable
    {
        internal RegistryKey Key;
        internal AutoResetEvent Changed = new AutoResetEvent(false);
        internal RegistryWatch(string path)
        {
            Key = Registry.CurrentUser.OpenSubKey(path, RegistryKeyPermissionCheck.ReadSubTree,
                RegistryRights.QueryValues | RegistryRights.Notify);
            if (Key == null) throw new IOException("Required Windows pointer settings key is missing.");
            Arm();
        }
        internal void Arm()
        {
            int error = RegNotifyChangeKeyValue(Key.Handle.DangerousGetHandle(), false, 4,
                Changed.SafeWaitHandle.DangerousGetHandle(), true);
            if (error != 0) throw new Win32Exception(error, "Cannot watch Windows pointer settings.");
        }
        public void Dispose() { if (Key != null) Key.Dispose(); Changed.Dispose(); }
    }

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern int RegNotifyChangeKeyValue(IntPtr key, bool subtree, uint filter, IntPtr changedEvent, bool asynchronous);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr LoadImageW(IntPtr instance, string path, uint type, int width, int height, uint flags);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetSystemCursor(IntPtr cursor, uint id);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool DestroyCursor(IntPtr cursor);

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length == 1 && args[0] == "--self-test") return SelfTest();
        bool stopping = args.Length == 2 && args[0] == "--stop";
        if ((!stopping && args.Length != 1) || (args.Length == 1 && args[0].StartsWith("--", StringComparison.Ordinal))) return 2;
        try
        {
            configPath = Path.GetFullPath(args[stopping ? 1 : 0]);
            string identity = Identity(configPath);
            if (stopping) return Stop(identity);
            using (Mutex singleton = new Mutex(false, identity + "-running"))
            {
                bool acquired;
                try { acquired = singleton.WaitOne(0); }
                catch (AbandonedMutexException) { acquired = true; }
                if (!acquired) return 0;
                try
                {
                    using (EventWaitHandle stop = new EventWaitHandle(false, EventResetMode.ManualReset, identity + "-stop"))
                    {
                        stop.Reset();
                        Config config = ReadConfig(configPath);
                        if (!config.Enabled) { Status("disabled", "Configuration is disabled."); return 0; }
                        return Run(config, stop);
                    }
                }
                finally { singleton.ReleaseMutex(); }
            }
        }
        catch (Exception error)
        {
            // Log only a bounded message. No paths or registry contents are recorded.
            Status("error", error.GetType().Name + ": " + SafeError(error));
            return 1;
        }
    }

    private static string SafeError(Exception error)
    {
        Win32Exception native = error as Win32Exception;
        if (native != null) return "Windows error " + native.NativeErrorCode.ToString(CultureInfo.InvariantCulture);
        return "Pointer size synchronization stopped; reinstall the theme to retry.";
    }

    private static string Identity(string path)
    {
        string sid = WindowsIdentity.GetCurrent().User.Value;
        string input = sid + "|" + Process.GetCurrentProcess().SessionId.ToString(CultureInfo.InvariantCulture)
            + "|" + path.ToUpperInvariant();
        using (SHA256 sha = SHA256.Create())
        {
            byte[] bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(input));
            StringBuilder hex = new StringBuilder();
            foreach (byte value in bytes) hex.Append(value.ToString("x2", CultureInfo.InvariantCulture));
            return @"Local\PetCursorSizeSync-" + hex.ToString();
        }
    }

    private static int Stop(string identity)
    {
        Mutex running;
        try { running = Mutex.OpenExisting(identity + "-running"); }
        catch (WaitHandleCannotBeOpenedException) { return 0; }
        using (running)
        {
            Stopwatch timeout = Stopwatch.StartNew();
            while (timeout.ElapsedMilliseconds < 5000)
            {
                bool acquired;
                try { acquired = running.WaitOne(0); }
                catch (AbandonedMutexException) { acquired = true; }
                if (acquired) { running.ReleaseMutex(); return 0; }
                try
                {
                    using (EventWaitHandle stop = EventWaitHandle.OpenExisting(identity + "-stop")) stop.Set();
                }
                catch (WaitHandleCannotBeOpenedException) { /* Starting: retry until its stop handle exists. */ }
                Thread.Sleep(25);
            }
            return 3; // Caller must not restore cursors until a later stop succeeds.
        }
    }

    private static Config ReadConfig(string path)
    {
        XmlReaderSettings settings = new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null };
        XDocument document;
        using (XmlReader reader = XmlReader.Create(path, settings)) document = XDocument.Load(reader);
        XElement root = document.Root;
        if (root == null || root.Name != "cursorSizeSync") throw new InvalidDataException("Invalid sync configuration root.");
        Config config = new Config();
        config.Document = document;
        config.Enabled = String.Equals((string)root.Attribute("enabled"), "true", StringComparison.OrdinalIgnoreCase);
        config.Scheme = Required(root, "schemeName");
        string directory = Required(root, "installedDirectory");
        if (!Path.IsPathRooted(directory)) throw new InvalidDataException("Installed directory must be absolute.");
        directory = Path.GetFullPath(directory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        config.InitialSlider = Number(root, "initialSliderSize", 1, 15, 1);
        config.InitialPixels = Number(root, "initialPixelSize", 16, 512, 48);
        config.SavedSlider = Number(root, "lastSliderSize", 1, 15, 0);
        config.SavedPixels = Number(root, "lastPixelSize", 16, 512, 0);
        XElement cursors = root.Element("cursors");
        if (cursors == null) throw new InvalidDataException("Cursor records are missing.");
        int count = 0;
        foreach (XElement cursor in cursors.Elements("cursor"))
        {
            string role = (string)cursor.Attribute("role");
            int index = Array.IndexOf(Roles, role);
            uint id;
            if (index < 0 || config.Files[index] != null || !UInt32.TryParse((string)cursor.Attribute("id"), out id) || id != Ids[index])
                throw new InvalidDataException("Invalid or duplicate cursor role.");
            string relative = (string)cursor.Attribute("file");
            if (String.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative)) throw new InvalidDataException("Cursor file must be relative.");
            string file = Path.GetFullPath(Path.Combine(directory, relative));
            if (!file.StartsWith(directory, StringComparison.OrdinalIgnoreCase)
                || (!file.EndsWith(".ani", StringComparison.OrdinalIgnoreCase) && !file.EndsWith(".cur", StringComparison.OrdinalIgnoreCase))
                || !File.Exists(file)) throw new InvalidDataException("Cursor file is unavailable.");
            config.Files[index] = file;
            count++;
        }
        if (count != Roles.Length) throw new InvalidDataException("All 17 cursor roles are required.");
        return config;
    }

    private static string Required(XElement root, string name)
    {
        string value = (string)root.Element(name);
        if (String.IsNullOrWhiteSpace(value)) throw new InvalidDataException("Required configuration value is missing.");
        return value;
    }

    private static int Number(XElement root, string name, int minimum, int maximum, int fallback)
    {
        XElement element = root.Element(name);
        if (element == null) return fallback;
        int value;
        if (!Int32.TryParse(element.Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out value) || value < minimum || value > maximum)
            throw new InvalidDataException("Invalid numeric configuration value.");
        return value;
    }

    private static int ReadNumber(RegistryKey key, string name, int minimum, int maximum)
    {
        object value = key.GetValue(name, null);
        int number;
        if (value == null || !Int32.TryParse(Convert.ToString(value, CultureInfo.InvariantCulture), out number)
            || number < minimum || number > maximum) return 0;
        return number;
    }

    private static Snapshot ReadSnapshot(Config config, RegistryKey accessibility, RegistryKey cursors)
    {
        Snapshot snapshot = new Snapshot();
        snapshot.Slider = ReadNumber(accessibility, "CursorSize", 1, 15);
        snapshot.Base = ReadNumber(cursors, "CursorBaseSize", 16, 512);
        snapshot.Owned = true;
        snapshot.BuiltIn = true;
        string windowsCursors = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Cursors")
            .TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string accessibilityCursors = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"Microsoft\Windows\Cursors");
        for (int i = 0; i < Roles.Length; i++)
        {
            string path = cursors.GetValue(Roles[i], "", RegistryValueOptions.DoNotExpandEnvironmentNames) as string;
            path = Environment.ExpandEnvironmentVariables(path ?? "");
            if (path.Length > 0)
            {
                try { path = Path.GetFullPath(path); }
                catch { path = "invalid"; }
            }
            bool owned = String.Equals(path, config.Files[i], StringComparison.OrdinalIgnoreCase);
            bool generated = String.Equals(path, Path.Combine(accessibilityCursors, AccessibilityFiles[i]), StringComparison.OrdinalIgnoreCase);
            snapshot.Owned &= owned;
            snapshot.BuiltIn &= owned || generated || path.Length == 0 || path.StartsWith(windowsCursors, StringComparison.OrdinalIgnoreCase);
        }
        return snapshot;
    }

    // CursorBaseSize is Windows' own pixel choice. Use the ordinal mapping only
    // when Windows has updated CursorSize but has not yet updated the base value.
    private static int PixelsFor(int slider, int currentBase, int previousBase, bool sliderChanged)
    {
        if (currentBase >= 16 && currentBase <= 512 && (!sliderChanged || currentBase != previousBase)) return currentBase;
        if (slider >= 1 && slider <= 15) return 32 + 16 * (slider - 1);
        return currentBase >= 16 && currentBase <= 512 ? currentBase : 48;
    }

    private static int Run(Config config, EventWaitHandle stop)
    {
        using (RegistryWatch accessibility = new RegistryWatch(AccessibilityKey))
        using (RegistryWatch cursors = new RegistryWatch(CursorKey))
        {
            Snapshot previous = ReadSnapshot(config, accessibility.Key, cursors.Key);
            if (!previous.Owned) return Suspend(config, "A different pointer theme is active.");
            lastSliderSize = previous.Slider == 0 ? config.InitialSlider : previous.Slider;
            lastPixelSize = config.SavedPixels > 0 ? config.SavedPixels : config.InitialPixels;
            if (config.SavedSlider > 0 && previous.Slider > 0 && config.SavedSlider != previous.Slider)
                lastPixelSize = PixelsFor(previous.Slider, previous.Base, 0, true);
            try
            {
                Apply(config, lastPixelSize, stop);
                Status("ready", "Watching the Windows pointer size slider.");
                Stopwatch clock = Stopwatch.StartNew();
                WaitHandle[] handles = { stop, accessibility.Changed, cursors.Changed };
                long firstChange = -1, lastChange = -1, externalSince = -1;
                long graceUntil = -1, settleAt = -1;
                int settlePasses = 0;
                while (true)
                {
                    long now = clock.ElapsedMilliseconds;
                    long due = Int64.MaxValue;
                    if (firstChange >= 0) due = Math.Min(lastChange + 180, firstChange + 1000);
                    if (externalSince >= 0) due = Math.Min(due, externalSince + 650);
                    if (settleAt >= 0) due = Math.Min(due, settleAt);
                    int timeout = due == Int64.MaxValue ? Timeout.Infinite : (int)Math.Max(0, Math.Min(Int32.MaxValue, due - now));
                    int signaled = WaitHandle.WaitAny(handles, timeout);
                    if (signaled == 0) break;
                    now = clock.ElapsedMilliseconds;
                    if (signaled == 1 || signaled == 2)
                    {
                        if (signaled == 1) accessibility.Arm(); else cursors.Arm();
                        if (firstChange < 0) firstChange = now;
                        lastChange = now;
                        long hardDue = firstChange + 1000;
                        if (externalSince >= 0) hardDue = Math.Min(hardDue, externalSince + 650);
                        if (settleAt >= 0) hardDue = Math.Min(hardDue, settleAt);
                        if (now < hardDue) continue;
                    }
                    firstChange = lastChange = -1;
                    Snapshot current = ReadSnapshot(config, accessibility.Key, cursors.Key);
                    bool sliderChanged = current.Slider > 0 && current.Slider != previous.Slider;
                    bool baseChanged = current.Base > 0 && current.Base != previous.Base;
                    // A built-in scheme can also change CursorBaseSize. Only
                    // reclaim its paths for a confirmed accessibility-slider
                    // change, or a trailing update of that same transaction.
                    bool resize = (sliderChanged && (current.Owned || current.BuiltIn))
                        || (baseChanged && (current.Owned || (current.BuiltIn && now <= graceUntil)));
                    bool settle = settleAt >= 0 && now >= settleAt;
                    if (resize)
                    {
                        lastPixelSize = PixelsFor(current.Slider, current.Base, previous.Base, sliderChanged);
                        if (current.Slider > 0) lastSliderSize = current.Slider;
                        graceUntil = now + 2000;
                        settleAt = now + 400;
                        settlePasses = 2;
                        Apply(config, lastPixelSize, stop);
                        SaveSize(config);
                        Status("resized", "Applied the Windows pointer size to the pet theme.");
                        externalSince = -1;
                    }
                    else if (!current.Owned)
                    {
                        if (now <= graceUntil && current.BuiltIn)
                        {
                            // Settings can replace the paths after writing the size.
                            Apply(config, lastPixelSize, stop);
                            externalSince = -1;
                        }
                        else if (externalSince < 0) externalSince = now;
                        else if (now >= externalSince + 650)
                            return Suspend(config, "Another pointer theme was selected; synchronization is disabled.");
                    }
                    else externalSince = -1;
                    if (settle && !resize)
                    {
                        // A finite follow-up also covers delayed native cursor reloads
                        // which do not write the registry a second time.
                        if (current.Owned && now <= graceUntil) Apply(config, lastPixelSize, stop);
                        settlePasses--;
                        settleAt = settlePasses > 0 ? now + 650 : -1;
                    }
                    previous = current;
                }
            }
            catch (OperationCanceledException) { }
            Status("stopped", "Synchronization stopped before restoring pointers.");
            return 0;
        }
    }

    private static void Apply(Config config, int pixels, EventWaitHandle stop)
    {
        IntPtr[] handles = new IntPtr[Roles.Length];
        try
        {
            for (int i = 0; i < handles.Length; i++)
            {
                if (stop.WaitOne(0)) throw new OperationCanceledException();
                handles[i] = LoadImageW(IntPtr.Zero, config.Files[i], 2, pixels, pixels, 0x10);
                if (handles[i] == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
            }
            if (stop.WaitOne(0)) throw new OperationCanceledException();
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(CursorKey, true))
            {
                if (key == null) throw new IOException("Cursor settings are unavailable.");
                for (int i = 0; i < Roles.Length; i++) SetValueIfChanged(key, Roles[i], config.Files[i], RegistryValueKind.ExpandString);
                SetValueIfChanged(key, "", config.Scheme, RegistryValueKind.String);
                SetValueIfChanged(key, "Scheme Source", 1, RegistryValueKind.DWord);
                // CursorSize and CursorBaseSize are controlled by Windows' slider.
                key.Flush();
            }
            for (int i = 0; i < handles.Length; i++)
            {
                if (stop.WaitOne(0)) throw new OperationCanceledException();
                if (!SetSystemCursor(handles[i], Ids[i])) throw new Win32Exception(Marshal.GetLastWin32Error());
                handles[i] = IntPtr.Zero; // SetSystemCursor consumes this non-shared handle.
            }
            applyCount++;
        }
        finally
        {
            foreach (IntPtr handle in handles) if (handle != IntPtr.Zero) DestroyCursor(handle);
        }
    }

    private static void SetValueIfChanged(RegistryKey key, string name, object value, RegistryValueKind kind)
    {
        object old = key.GetValue(name, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
        if (!Object.Equals(old, value)) key.SetValue(name, value, kind);
    }

    private static void SaveSize(Config config)
    {
        config.Document.Root.SetElementValue("lastSliderSize", lastSliderSize);
        config.Document.Root.SetElementValue("lastPixelSize", lastPixelSize);
        SaveXml(config.Document, configPath);
    }

    private static int Suspend(Config config, string reason)
    {
        config.Document.Root.SetAttributeValue("enabled", "false");
        SaveXml(config.Document, configPath);
        Status("suspended", reason);
        return 0;
    }

    private static void SaveXml(XDocument document, string path)
    {
        string temporary = path + "." + Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture) + ".tmp";
        try
        {
            using (XmlWriter writer = XmlWriter.Create(temporary, new XmlWriterSettings { Encoding = new UTF8Encoding(false), Indent = true }))
                document.Save(writer);
            if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    private static void Status(string state, string message)
    {
        if (String.IsNullOrEmpty(configPath)) return;
        try
        {
            string timestamp = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);
            XDocument document = new XDocument(new XElement("cursorSizeSyncStatus",
                new XAttribute("state", state), new XAttribute("utc", timestamp),
                new XElement("pid", Process.GetCurrentProcess().Id),
                new XElement("sliderSize", lastSliderSize), new XElement("pixelSize", lastPixelSize),
                new XElement("applyCount", applyCount), new XElement("message", message)));
            SaveXml(document, configPath + ".status.xml");
            string log = configPath + ".log";
            if (File.Exists(log) && new FileInfo(log).Length > 32768) File.WriteAllText(log, "", new UTF8Encoding(false));
            File.AppendAllText(log, timestamp + " " + state + " slider=" + lastSliderSize.ToString(CultureInfo.InvariantCulture)
                + " pixels=" + lastPixelSize.ToString(CultureInfo.InvariantCulture) + " " + message + Environment.NewLine,
                new UTF8Encoding(false));
        }
        catch { /* Diagnostics must not prevent restoring or stopping the helper. */ }
    }

    private static int SelfTest()
    {
        try
        {
            if (PixelsFor(1, 48, 48, true) != 32) throw new Exception("Minimum fallback.");
            if (PixelsFor(15, 48, 48, true) != 256) throw new Exception("Maximum fallback.");
            if (PixelsFor(4, 120, 48, true) != 120) throw new Exception("Windows pixel value takes priority.");
            if (PixelsFor(4, 96, 48, false) != 96) throw new Exception("Base-only resize.");
            if (PixelsFor(0, 0, 0, false) != 48) throw new Exception("Missing settings fallback.");
            if (Roles.Length != 17 || Ids.Length != 17 || new HashSet<uint>(Ids).Count != 17) throw new Exception("Role map.");
            if (AccessibilityFiles.Length != 17 || new HashSet<string>(AccessibilityFiles).Count != 17) throw new Exception("Accessibility role paths.");
            Console.WriteLine("Passed: size bounds, stale-base fallback, Windows pixel priority, base-only changes, missing settings, 17 cursor IDs. No system settings changed.");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
    }
}
