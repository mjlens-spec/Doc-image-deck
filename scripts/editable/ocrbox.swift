import Foundation
import Vision
import AppKit
// Usage:
//   ocrbox <image>                         -> JSON array of lines for one image
//   ocrbox --batch <list.txt> [--words <words.txt>] [--lc]
//        -> JSON object {path: [lines]} for every image path listed (one per line)
// Each line: text, conf, pixel box (origin top-left), per-character boxes, and up to 3 alternative readings.
var args = Array(CommandLine.arguments.dropFirst())
var batch: String? = nil, wordsFile: String? = nil, lc = false
var single: String? = nil
var i = 0
while i < args.count {
    switch args[i] {
    case "--batch": batch = args[i + 1]; i += 2
    case "--words": wordsFile = args[i + 1]; i += 2
    case "--lc": lc = true; i += 1
    default: single = args[i]; i += 1
    }
}
var words: [String] = []
if let wf = wordsFile, let t = try? String(contentsOfFile: wf, encoding: .utf8) {
    words = t.split(separator: "\n").map { String($0) }.filter { !$0.isEmpty }
}
func run(_ path: String) -> [[String: Any]] {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return [] }
    let W = Double(cg.width), H = Double(cg.height)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    req.usesLanguageCorrection = lc
    if !words.isEmpty { req.customWords = words }
    req.minimumTextHeight = 0.004
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    func px(_ b: CGRect) -> [Double] { return [b.minX * W, (1 - b.maxY) * H, b.maxX * W, (1 - b.minY) * H] }
    var out: [[String: Any]] = []
    for o in (req.results ?? []) {
        let cands = o.topCandidates(3)
        guard let t = cands.first else { continue }
        let s = t.string
        var chars: [[Double]] = []
        var k = s.startIndex
        while k < s.endIndex {
            let j = s.index(after: k)
            if let r = try? t.boundingBox(for: k..<j) { chars.append(px(r.boundingBox)) } else { chars.append([]) }
            k = j
        }
        let b = px(o.boundingBox)
        out.append(["text": s, "conf": t.confidence, "x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3], "chars": chars,
                    "alts": cands.dropFirst().map { ["text": $0.string, "conf": $0.confidence] }])
    }
    return out
}
if let b = batch, let list = try? String(contentsOfFile: b, encoding: .utf8) {
    var res: [String: Any] = [:]
    for p in list.split(separator: "\n").map({ String($0) }) where !p.isEmpty { res[p] = run(p) }
    print(String(data: try! JSONSerialization.data(withJSONObject: res, options: []), encoding: .utf8)!)
} else if let p = single {
    print(String(data: try! JSONSerialization.data(withJSONObject: run(p), options: []), encoding: .utf8)!)
}
