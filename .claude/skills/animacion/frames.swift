import AVFoundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

// usage: frames <video> <outdir> <cellWidth> <cols> <rows> [t0 t1 [step]]
// Pass 1 (no t0): prints nominal fps, duration, and a per-frame motion value (mean abs luma diff vs previous frame) to motion.csv
// CROP=x,y,w,h (fractions of the frame, origin top left) limits both the motion value and the sheets to one region.
// Sheets: frames sampled every `step` seconds between t0..t1, laid out cols x rows per sheet, timestamp burned in.
let a = CommandLine.arguments
let url = URL(fileURLWithPath: a[1]); let out = a[2]
let cellW = Int(a[3])!, cols = Int(a[4])!, rows = Int(a[5])!
let asset = AVURLAsset(url: url)
let track = asset.tracks(withMediaType: .video)[0]
let dur = CMTimeGetSeconds(asset.duration)
let full = track.naturalSize
let crop = (ProcessInfo.processInfo.environment["CROP"] ?? "0,0,1,1").split(separator: ",").map { Double($0)! }
let size = CGSize(width: full.width * crop[2], height: full.height * crop[3])
print("duration \(dur) fps \(track.nominalFrameRate) size \(Int(full.width))x\(Int(full.height)) crop \(crop)")
let t0 = a.count > 6 ? Double(a[6])! : 0, t1 = a.count > 7 ? Double(a[7])! : dur
let step = a.count > 8 ? Double(a[8])! : (t1 - t0) / Double(cols * rows)

if a.count <= 6 {
  let reader = try! AVAssetReader(asset: asset)
  let w = 192, h = max(2, Int(192 * full.height / full.width) / 2 * 2)
  let o = AVAssetReaderTrackOutput(track: track, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
    kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h])
  reader.add(o); reader.startReading()
  var prev: [UInt8] = []; var csv = "frame,t,motion\n"; var n = 0
  while let sb = o.copyNextSampleBuffer() {
    let t = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sb))
    let pb = CMSampleBufferGetImageBuffer(sb)!
    CVPixelBufferLockBaseAddress(pb, .readOnly)
    let bpr = CVPixelBufferGetBytesPerRow(pb), hh = CVPixelBufferGetHeight(pb), ww = CVPixelBufferGetWidth(pb)
    let p = CVPixelBufferGetBaseAddress(pb)!.assumingMemoryBound(to: UInt8.self)
    let x0 = Int(crop[0] * Double(ww)), y0 = Int(crop[1] * Double(hh)), cw = max(1, Int(crop[2] * Double(ww))), ch = max(1, Int(crop[3] * Double(hh)))
    var cur = [UInt8](repeating: 0, count: cw * ch)
    for y in 0..<ch { for x in 0..<cw { cur[y*cw+x] = p[(y0+y)*bpr + (x0+x)*4 + 1] } }
    CVPixelBufferUnlockBaseAddress(pb, .readOnly)
    var d = 0.0
    if prev.count == cur.count { var s = 0; for i in 0..<cur.count { s += abs(Int(cur[i]) - Int(prev[i])) }; d = Double(s) / Double(cur.count) }
    csv += "\(n),\(String(format: "%.3f", t)),\(String(format: "%.2f", d))\n"
    prev = cur; n += 1
  }
  try! csv.write(toFile: out + "/motion.csv", atomically: true, encoding: .utf8)
  print("frames \(n)")
}

let gen = AVAssetImageGenerator(asset: asset)
gen.requestedTimeToleranceBefore = .zero; gen.requestedTimeToleranceAfter = .zero
gen.appliesPreferredTrackTransform = true
let cellH = Int(Double(cellW) * Double(size.height) / Double(size.width))
gen.maximumSize = CGSize(width: Double(cellW) / crop[2], height: Double(cellH) / crop[3])
var times: [Double] = []; var t = t0
while t < t1 - 1e-6 { times.append(t); t += step }
let per = cols * rows; var sheet = 0
let cs = CGColorSpaceCreateDeviceRGB()
for start in stride(from: 0, to: times.count, by: per) {
  let chunk = Array(times[start..<min(start + per, times.count)])
  let r = Int(ceil(Double(chunk.count) / Double(cols)))
  let ctx = CGContext(data: nil, width: cols * cellW, height: r * cellH, bitsPerComponent: 8, bytesPerRow: 0, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  ctx.setFillColor(CGColor(red: 0.2, green: 0.2, blue: 0.2, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: cols * cellW, height: r * cellH))
  for (i, tt) in chunk.enumerated() {
    guard let whole = try? gen.copyCGImage(at: CMTime(seconds: tt, preferredTimescale: 600), actualTime: nil),
          let img = whole.cropping(to: CGRect(x: crop[0] * Double(whole.width), y: crop[1] * Double(whole.height), width: crop[2] * Double(whole.width), height: crop[3] * Double(whole.height))) else { continue }
    let cx = (i % cols) * cellW, cy = (r - 1 - i / cols) * cellH
    ctx.draw(img, in: CGRect(x: cx, y: cy, width: cellW, height: cellH))
    ctx.setStrokeColor(CGColor(red: 1, green: 0, blue: 1, alpha: 1)); ctx.stroke(CGRect(x: cx, y: cy, width: cellW, height: cellH), width: 1)
    let label = String(format: "%.2f", tt) as CFString
    let font = CTFontCreateWithName("Menlo-Bold" as CFString, 13, nil)
    let attr = [kCTFontAttributeName: font, kCTForegroundColorAttributeName: CGColor(red: 1, green: 0, blue: 1, alpha: 1)] as CFDictionary
    let line = CTLineCreateWithAttributedString(CFAttributedStringCreate(nil, label, attr)!)
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 0.85)); ctx.fill(CGRect(x: cx + 2, y: cy + 2, width: 46, height: 16))
    ctx.textPosition = CGPoint(x: cx + 4, y: cy + 5); CTLineDraw(line, ctx)
  }
  let path = String(format: "%@/sheet-%.2f-%02d.jpg", out, t0, sheet)
  let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: path) as CFURL, UTType.jpeg.identifier as CFString, 1, nil)!
  CGImageDestinationAddImage(dest, ctx.makeImage()!, [kCGImageDestinationLossyCompressionQuality: 0.8] as CFDictionary)
  CGImageDestinationFinalize(dest); print(path); sheet += 1
}
