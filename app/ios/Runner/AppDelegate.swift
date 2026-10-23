import Darwin
import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  private var offlineStorageChannel: FlutterMethodChannel?
  private let offlineStorageQueue = DispatchQueue(label: "smartplan.offline-storage", qos: .utility)

  override init() {
    // Set private creation modes before UIKit/Flutter can initialize plugins or
    // create temporary source/media files. Existing paths are checked separately.
    umask(mode_t(0o077))
    super.init()
  }

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
    let channel = FlutterMethodChannel(
      name: "smartplan/offline-storage",
      binaryMessenger: engineBridge.applicationRegistrar.messenger()
    )
    offlineStorageChannel = channel
    channel.setMethodCallHandler { [weak self] call, result in
      guard call.method == "protectDirectory" else {
        result(FlutterMethodNotImplemented)
        return
      }
      guard let path = call.arguments as? String,
        (path as NSString).isAbsolutePath, !path.utf8.contains(0), let self = self
      else {
        result(FlutterError(
          code: "invalid_directory", message: "Ein absoluter Offline-Verzeichnispfad ist erforderlich.",
          details: nil))
        return
      }
      self.offlineStorageQueue.async {
        do {
          try Self.protectOfflineDirectory(path)
          DispatchQueue.main.async { result(nil) }
        } catch {
          DispatchQueue.main.async {
            result(FlutterError(
              code: "offline_protection_failed",
              message: "Der lokale Offline-Speicher konnte nicht geschützt werden.", details: nil))
          }
        }
      }
    }
  }

  private enum OfflineStorageError: Error {
    case invalidDirectory
    case protectionNotApplied
  }

  nonisolated private static func protectOfflineDirectory(_ path: String) throws {
    let manager = FileManager.default
    let support = try manager.url(
      for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: false
    ).standardizedFileURL.resolvingSymlinksInPath()
    // Resolve the trusted parent, then append the fixed directory name. Resolving
    // the allowed root itself could accidentally authorize a symlink outside it.
    let allowed = support.appendingPathComponent("smartplan-offline", isDirectory: true)
    let directory = URL(fileURLWithPath: path, isDirectory: true)
      .standardizedFileURL.resolvingSymlinksInPath()
    guard directory.path == allowed.path || directory.path.hasPrefix(allowed.path + "/") else {
      throw OfflineStorageError.invalidDirectory
    }
    var isDirectory: ObjCBool = false
    guard manager.fileExists(atPath: directory.path, isDirectory: &isDirectory),
      isDirectory.boolValue
    else {
      throw OfflineStorageError.invalidDirectory
    }

    // Validate every existing child before changing attributes. No symbolic
    // links or special files may move the operation outside this directory.
    var targets = [directory]
    var enumerationError: Error?
    guard let children = manager.enumerator(
      at: directory,
      includingPropertiesForKeys: [.isDirectoryKey, .isRegularFileKey, .isSymbolicLinkKey],
      options: [],
      errorHandler: { _, error in
        enumerationError = error
        return false
      }
    ) else {
      throw OfflineStorageError.invalidDirectory
    }
    for case let child as URL in children {
      let values = try child.resourceValues(
        forKeys: [.isDirectoryKey, .isRegularFileKey, .isSymbolicLinkKey])
      let resolved = child.standardizedFileURL.resolvingSymlinksInPath()
      guard values.isSymbolicLink != true,
        values.isDirectory == true || values.isRegularFile == true,
        resolved.path.hasPrefix(directory.path + "/")
      else {
        throw OfflineStorageError.invalidDirectory
      }
      targets.append(resolved)
    }
    if let error = enumerationError { throw error }

    // The directory protects future children; explicitly cover existing files.
    // Complete protection intentionally requires an unlocked device for access.
    for var target in targets {
      try manager.setAttributes([.protectionKey: FileProtectionType.complete], atPath: target.path)
      var values = URLResourceValues()
      values.isExcludedFromBackup = true
      try target.setResourceValues(values)
      target.removeAllCachedResourceValues()
      let excluded = try target.resourceValues(forKeys: [.isExcludedFromBackupKey])
      let attributes = try manager.attributesOfItem(atPath: target.path)
      let protection = attributes[.protectionKey]
      let protectionName = (protection as? FileProtectionType)?.rawValue ?? (protection as? String)
      guard excluded.isExcludedFromBackup == true,
        protectionName == FileProtectionType.complete.rawValue
      else {
        throw OfflineStorageError.protectionNotApplied
      }
    }
  }
}
