// Pixel boxes of text on a page image, with macOS's built-in text recognition (Vision):
//
//     pdftoppm -f 5 -l 5 -r 200 -png doc.pdf /tmp/p        # the page at recortes.py's DPI
//     swift experiments/carrusel/documentos/boxes.swift /tmp/p-05.png                 # every line: L x y w h | text
//     swift experiments/carrusel/documentos/boxes.swift /tmp/p-05.png "frase" ...     # each phrase: N x y w h | frase
//
// Boxes are top-left origin, tight to the ink: pad about 8 px before cutting. Cut a wrapped sentence at a word
// boundary, so the cuts read in order.
import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count >= 2, let img = NSImage(contentsOfFile: args[1]),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("usage: boxes.swift page.png [phrase...]"); exit(1) }
let W = CGFloat(cg.width), H = CGFloat(cg.height)
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.recognitionLanguages = ["es-ES"]
req.usesLanguageCorrection = false
try VNImageRequestHandler(cgImage: cg).perform([req])
func px(_ r: CGRect) -> String {
    String(format: "%d %d %d %d", Int(r.minX * W), Int((1 - r.maxY) * H), Int(r.width * W), Int(r.height * H))
}
let needles = Array(args.dropFirst(2))
for o in req.results ?? [] {
    guard let c = o.topCandidates(1).first else { continue }
    if needles.isEmpty { print("L \(px(o.boundingBox)) | \(c.string)") }
    for n in needles {
        if let r = c.string.range(of: n), let b = try? c.boundingBox(for: r) {
            print("N \(px(b.boundingBox)) | \(n)")
        }
    }
}
