import AppKit
import Foundation

let launchStart = ProcessInfo.processInfo.systemUptime

final class DownloaderApp: NSObject, NSApplicationDelegate, NSWindowDelegate, NSTextFieldDelegate {
    var window: NSWindow!
    let urlField = NSTextField(string: "")
    let folderField = NSTextField(string: "")
    let format = NSPopUpButton(frame: .zero, pullsDown: false)
    let playlist = NSButton(checkboxWithTitle: "Entire YouTube playlist", target: nil, action: nil)
    let startButton = NSButton(title: "Download", target: nil, action: nil)
    let cancelButton = NSButton(title: "Cancel", target: nil, action: nil)
    let pauseButton = NSButton(title: "Pause", target: nil, action: nil)
    let detailButton = NSButton(title: "Show details", target: nil, action: nil)
    let status = NSTextField(wrappingLabelWithString: "Ready. Paste a YouTube or Spotify link.")
    let count = NSTextField(labelWithString: "Songs save directly to the folder you choose, one at a time.")
    let progress = NSProgressIndicator()
    let logText = NSTextView()
    let logScroll = NSScrollView()
    let chooseButton = NSButton(title: "Choose…", target: nil, action: nil)
    var process: Process?
    var isPaused = false
    var receivedDone = false
    var cancelRequested = false
    var detailsVisible = false
    var buffer = Data()
    let parsing = DispatchQueue(label: "com.alaamari.mediaflow.events")
    var dataFolder: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("YouTube & Spotify Downloader", isDirectory: true)
    }
    var preferences: URL { dataFolder.appendingPathComponent("settings.json") }

    func label(_ title: String) -> NSTextField {
        let view = NSTextField(labelWithString: title)
        view.font = .systemFont(ofSize: 12, weight: .semibold)
        view.textColor = .secondaryLabelColor
        return view
    }
    func row(_ views: [NSView]) -> NSStackView {
        let stack = NSStackView(views: views)
        stack.orientation = .horizontal
        stack.alignment = .centerY
        stack.spacing = 10
        return stack
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        try? FileManager.default.createDirectory(at: dataFolder, withIntermediateDirectories: true)
        let settings = (try? Data(contentsOf: preferences)).flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: String] } ?? [:]
        folderField.stringValue = settings["destination"] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Downloads").path
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 610, height: 470), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "YouTube & Spotify Downloader"
        window.delegate = self
        window.center()
        window.isReleasedWhenClosed = false
        let title = NSTextField(labelWithString: "YouTube & Spotify Downloader")
        title.font = .systemFont(ofSize: 23, weight: .bold)
        let subtitle = NSTextField(labelWithString: "Paste a link. Pick your folder. Download.")
        subtitle.textColor = .secondaryLabelColor
        subtitle.font = .systemFont(ofSize: 13)
        urlField.placeholderString = "YouTube video, or Spotify track / album / playlist link"
        urlField.delegate = self
        urlField.font = .systemFont(ofSize: 13)
        urlField.cell?.isScrollable = true
        format.addItems(withTitles: ["MP3 audio", "M4A audio", "FLAC audio", "MP4 video"])
        if let previous = settings["format"] { format.selectItem(withTitle: previous) }
        playlist.state = .on
        folderField.font = .systemFont(ofSize: 12)
        folderField.cell?.isScrollable = true
        chooseButton.target = self; chooseButton.action = #selector(chooseFolder)
        let openButton = NSButton(title: "Open folder", target: self, action: #selector(openFolder))
        let folderRow = row([folderField, chooseButton, openButton])
        folderField.setContentHuggingPriority(.defaultLow, for: .horizontal)
        folderField.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        chooseButton.setContentHuggingPriority(.required, for: .horizontal)
        openButton.setContentHuggingPriority(.required, for: .horizontal)
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let options = row([label("Format"), format, spacer, playlist])
        startButton.target = self; startButton.action = #selector(startDownload); startButton.keyEquivalent = "\r"
        startButton.bezelStyle = .rounded
        startButton.controlSize = .large
        cancelButton.target = self; cancelButton.action = #selector(cancelDownload)
        pauseButton.target = self; pauseButton.action = #selector(togglePause)
        pauseButton.isHidden = true; cancelButton.isHidden = true
        detailButton.target = self; detailButton.action = #selector(toggleDetails)
        detailButton.bezelStyle = .inline
        let buttonSpacer = NSView()
        let actions = row([startButton, pauseButton, cancelButton, buttonSpacer, detailButton])
        buttonSpacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        progress.style = .bar
        progress.isIndeterminate = true
        progress.isDisplayedWhenStopped = false
        status.font = .systemFont(ofSize: 13)
        status.maximumNumberOfLines = 3
        count.font = .systemFont(ofSize: 11)
        count.textColor = .secondaryLabelColor
        logText.isEditable = false
        logText.isSelectable = true
        logText.font = .monospacedSystemFont(ofSize: 10, weight: .regular)
        logText.textColor = .secondaryLabelColor
        logText.autoresizingMask = [.width]
        logText.textContainer?.widthTracksTextView = true
        logText.isHorizontallyResizable = false
        logText.isVerticallyResizable = true
        logScroll.documentView = logText
        logScroll.hasVerticalScroller = true
        logScroll.borderType = .bezelBorder
        logScroll.heightAnchor.constraint(equalToConstant: 150).isActive = true
        logScroll.isHidden = true
        let root = NSStackView(views: [title, subtitle, label("YouTube or Spotify link"), urlField, options, label("Save to"), folderRow, progress, status, count, actions, logScroll])
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = 13
        root.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(root)
        NSLayoutConstraint.activate([
            root.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 24),
            root.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -24),
            root.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 24),
            root.bottomAnchor.constraint(lessThanOrEqualTo: window.contentView!.bottomAnchor, constant: -20)
        ])
        for view in [urlField, options, folderRow, progress, status, count, actions, logScroll] {
            view.widthAnchor.constraint(equalTo: root.widthAnchor).isActive = true
        }
        urlField.heightAnchor.constraint(equalToConstant: 28).isActive = true
        status.heightAnchor.constraint(greaterThanOrEqualToConstant: 34).isActive = true
        makeMenu()
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(urlField)
        NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.main.async {
            let timing: [String: Any] = ["nativeUIReadyMs": (ProcessInfo.processInfo.systemUptime - launchStart) * 1000, "date": ISO8601DateFormatter().string(from: Date())]
            if let bytes = try? JSONSerialization.data(withJSONObject: timing) { try? bytes.write(to: self.dataFolder.appendingPathComponent("startup.json"), options: .atomic) }
        }
    }
    func makeMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu(); appItem.submenu = appMenu
        appMenu.addItem(withTitle: "Quit Downloader", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let edit = NSMenuItem(); main.addItem(edit)
        let editMenu = NSMenu(title: "Edit"); edit.submenu = editMenu
        for (title, selector, key) in [("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            editMenu.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
        }
        NSApp.mainMenu = main
    }
    func controlTextDidChange(_ notification: Notification) {
        guard process == nil else { return }
        let spotify = URL(string: urlField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines))?.host == "open.spotify.com"
        format.lastItem?.isEnabled = !spotify
        if spotify && format.indexOfSelectedItem == 3 { format.selectItem(at: 0) }
        playlist.isEnabled = !spotify
    }
    @objc func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true; panel.canChooseFiles = false; panel.allowsMultipleSelection = false; panel.canCreateDirectories = true
        panel.prompt = "Save here"
        panel.directoryURL = URL(fileURLWithPath: NSString(string: folderField.stringValue).expandingTildeInPath)
        panel.beginSheetModal(for: window) { response in
            if response == .OK, let folder = panel.url { self.folderField.stringValue = folder.path; self.saveSettings() }
        }
    }
    @objc func openFolder() {
        let folder = URL(fileURLWithPath: NSString(string: folderField.stringValue).expandingTildeInPath)
        NSWorkspace.shared.open(folder)
    }
    func saveSettings() {
        let values = ["destination": folderField.stringValue, "format": format.titleOfSelectedItem ?? "MP3 audio"]
        if let bytes = try? JSONSerialization.data(withJSONObject: values) { try? bytes.write(to: preferences, options: .atomic) }
    }
    func enginePath() -> String? {
        let path = Bundle.main.resourceURL!.appendingPathComponent("engine/mediaflow-engine").path
        return FileManager.default.isExecutableFile(atPath: path) ? path : nil
    }
    @objc func startDownload() {
        guard process == nil else { return }
        let link = urlField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !link.isEmpty else { status.stringValue = "Paste a YouTube or Spotify link first."; window.makeFirstResponder(urlField); return }
        guard let engine = enginePath() else { status.stringValue = "The download engine is missing. Download a fresh copy of the app."; return }
        let formats = ["mp3", "m4a", "flac", "mp4"]
        let config: [String: Any] = ["url": link, "format": formats[max(0, format.indexOfSelectedItem)], "destination": folderField.stringValue, "playlist": playlist.state == .on, "data": dataFolder.path]
        guard var input = try? JSONSerialization.data(withJSONObject: config) else { return }
        input.append(10)
        let worker = Process()
        worker.executableURL = URL(fileURLWithPath: engine)
        worker.arguments = []
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = Bundle.main.resourceURL!.appendingPathComponent("bin").path + ":/usr/bin:/bin"
        env["PYTHONUNBUFFERED"] = "1"
        worker.environment = env
        let output = Pipe(), errors = Pipe(), incoming = Pipe()
        worker.standardOutput = output; worker.standardError = errors; worker.standardInput = incoming
        receivedDone = false; cancelRequested = false; isPaused = false; buffer = Data(); logText.string = ""
        output.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let bytes = handle.availableData
            if bytes.isEmpty { handle.readabilityHandler = nil; return }
            self?.parsing.async { [weak self] in self?.consume(bytes) }
        }
        errors.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let bytes = handle.availableData
            if bytes.isEmpty { handle.readabilityHandler = nil; return }
            if let text = String(data: bytes, encoding: .utf8) { DispatchQueue.main.async { self?.appendLog(text) } }
        }
        worker.terminationHandler = { [weak self] finished in
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                guard let self = self else { return }
                if self.cancelRequested { self.status.stringValue = "Download cancelled. Files already saved remain in your folder." }
                else if !self.receivedDone { self.status.stringValue = finished.terminationStatus == 0 ? "Download finished." : "Download stopped. Open details for more information." }
                self.process = nil
                self.setRunning(false)
            }
        }
        do {
            try worker.run()
            process = worker
            try incoming.fileHandleForWriting.write(contentsOf: input)
            try incoming.fileHandleForWriting.close()
            setRunning(true)
            status.stringValue = "Starting local download engine…"
            count.stringValue = "Files save straight to your selected folder."
            saveSettings()
        } catch { status.stringValue = "Could not start the download: \(error.localizedDescription)"; process = nil; setRunning(false) }
    }
    func consume(_ bytes: Data) {
        buffer.append(bytes)
        while let newline = buffer.firstIndex(of: 10) {
            let line = buffer.prefix(upTo: newline); buffer.removeSubrange(...newline)
            guard let values = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { continue }
            DispatchQueue.main.async { self.receive(values) }
        }
    }
    func receive(_ event: [String: Any]) {
        let type = event["type"] as? String ?? ""
        if let message = event["message"] as? String {
            appendLog(message)
            if type != "progress" { status.stringValue = String(message.prefix(240)) }
            else if message.contains("Processing query:") { status.stringValue = "Reading your Spotify link…" }
            else if message.contains("Found ") && message.contains("songs") { status.stringValue = String(message.prefix(180)) }
            else if message.contains("Searching for song") { status.stringValue = "Finding matching audio…" }
            else if message.contains("returned no usable results") { status.stringValue = "Trying another audio match…" }
            else if message.contains("Getting audio meta") { status.stringValue = "Preparing audio…" }
            else if message.contains("Embedding metadata") { status.stringValue = "Finishing the song…" }
            else if message.contains("Downloading") || message.contains("[download]") { status.stringValue = "Downloading…" }
            else if message.contains("ERROR:") || message.contains("AudioProviderError") { status.stringValue = "This item encountered a problem. See details." }
        }
        if type == "progress", let value = event["percent"] as? Double {
            progress.isIndeterminate = false; progress.maxValue = 100; progress.doubleValue = value
        }
        if type == "saved" {
            count.stringValue = "\(event["count"] as? Int ?? 0) song(s) saved"
            if let name = event["name"] as? String { appendLog("Saved: \(name)") }
        }
        if type == "done" {
            receivedDone = true
            if let number = event["count"] as? Int { count.stringValue = "\(number) file(s) saved in \(folderField.stringValue)" }
            if event["state"] as? String == "error" { status.textColor = .systemRed } else { status.textColor = .labelColor }
        }
    }
    func appendLog(_ line: String) {
        let previous = logText.string.components(separatedBy: "\n").suffix(120)
        logText.string = (Array(previous) + [line]).joined(separator: "\n")
        logText.scrollToEndOfDocument(nil)
    }
    func setRunning(_ running: Bool) {
        startButton.isEnabled = !running; urlField.isEnabled = !running; folderField.isEnabled = !running
        format.isEnabled = !running; playlist.isEnabled = !running; chooseButton.isEnabled = !running
        pauseButton.isHidden = !running; cancelButton.isHidden = !running
        pauseButton.title = "Pause"; cancelButton.isEnabled = true
        if running { status.textColor = .labelColor }
        if running { progress.isIndeterminate = true; progress.startAnimation(nil) } else { progress.stopAnimation(nil); controlTextDidChange(Notification(name: NSText.didChangeNotification)) }
    }
    @objc func togglePause() {
        guard let worker = process, worker.isRunning else { return }
        isPaused.toggle()
        kill(-worker.processIdentifier, isPaused ? SIGSTOP : SIGCONT)
        pauseButton.title = isPaused ? "Resume" : "Pause"
        status.stringValue = isPaused ? "Paused." : "Resuming download…"
    }
    @objc func cancelDownload() {
        guard let worker = process, worker.isRunning else { return }
        cancelRequested = true
        kill(-worker.processIdentifier, SIGCONT)
        if kill(-worker.processIdentifier, SIGTERM) != 0 { worker.terminate() }
        status.stringValue = "Cancelling…"
        cancelButton.isEnabled = false
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { if worker.isRunning { kill(-worker.processIdentifier, SIGKILL) }; self.cancelButton.isEnabled = true }
    }
    @objc func toggleDetails() {
        detailsVisible.toggle(); logScroll.isHidden = !detailsVisible; detailButton.title = detailsVisible ? "Hide details" : "Show details"
        var frame = window.frame
        let adjustment: CGFloat = detailsVisible ? 163 : -163
        frame.origin.y -= adjustment; frame.size.height += adjustment
        window.setFrame(frame, display: true, animate: false)
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if let worker = process, worker.isRunning { kill(-worker.processIdentifier, SIGCONT); kill(-worker.processIdentifier, SIGTERM) }
        return .terminateNow
    }
}

let application = NSApplication.shared
application.setActivationPolicy(.regular)
let delegate = DownloaderApp()
application.delegate = delegate
application.run()
