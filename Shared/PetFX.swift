import SwiftUI

// MARK: - Состояние эффектов поверх виджета (трещины, пыль, взрыв, летящая граната/ракета)
struct FXState: Equatable {
    var dust: Double = 0        // 0…1 — «пыльная завеса» после взрыва
    var flash: Double = 0       // 0…1 — белая вспышка
    var crack: Int = 0          // 0 нет, 1…3 — стадия трещин
    var holeX: Double = 0.5     // где пробоина (доля ширины/высоты)
    var holeY: Double = 0.45
    var crackSeed: Int = 1
    var boom: Double = 0        // 0 — нет, 0…1 — прогресс вспышки-взрыва
    var boomBig: Bool = false
    var fly: Int = 0            // 0 нет, 1 граната, 2 ракета
    var flyP: Double = 0        // 0…1 — полёт к зрителю
    var shakeX: Double = 0      // тряска всего содержимого, пт
    var shakeY: Double = 0
}

enum PetFX {
    private static func dustLevel(_ e: Double, peak: Double, total: Double) -> Double {
        let v = e < 0.25 ? peak * e / 0.25 : peak * max(0, 1 - (e - 0.25) / total)
        return (v * 100).rounded() / 100
    }

    /// Эффекты в момент `elapsed` секунд после начала события.
    static func state(event: PetEvent, elapsed t: Double, seed: Int) -> FXState {
        var fx = FXState()
        guard t >= 0, t < PetConfig.fxLifetime else { return fx }
        var rng = SplitMix(UInt64(truncatingIfNeeded: seed) &* 0x9E3779B97F4A7C15 &+ 7)
        fx.holeX = ((0.3 + rng.unit() * 0.4) * 100).rounded() / 100
        fx.holeY = ((0.3 + rng.unit() * 0.35) * 100).rounded() / 100
        fx.crackSeed = seed
        let tick = Int(t / PetConfig.frameInterval + 1e-6)
        let sgn: Double = tick % 2 == 0 ? 1 : -1

        switch event {
        case .pistol:
            let fire = 1.0
            if t >= fire && t < fire + 10 {
                fx.crack = t < fire + 0.25 ? 1 : (t < fire + 0.5 ? 2 : 3)
                if t < fire + 0.25 { fx.flash = 0.45 }
                if t < fire + 0.5 { fx.shakeX = 4 * sgn; fx.shakeY = -2.5 * sgn }
            }
        case .grenade:
            let throwT = 1.0, boomT = 2.0
            if t >= throwT && t < boomT { fx.fly = 1; fx.flyP = (t - throwT) / (boomT - throwT) }
            if t >= boomT {
                let e = t - boomT
                if e < 1.0 { fx.boom = max(e, 0.05) }
                fx.flash = e < 0.25 ? 0.9 : (e < 0.5 ? 0.45 : 0)
                fx.dust = dustLevel(e, peak: 0.88, total: 9)
                if e < 1.0 { fx.shakeX = 9 * (1 - e) * sgn; fx.shakeY = -6 * (1 - e) * sgn }
            }
        case .rpg:
            let fire = 1.25, boomT = 1.75
            if t >= fire && t < boomT { fx.fly = 2; fx.flyP = (t - fire) / (boomT - fire) }
            if t >= boomT {
                let e = t - boomT
                fx.boomBig = true
                if e < 1.25 { fx.boom = max(e / 1.25, 0.05) }
                fx.flash = e < 0.25 ? 0.95 : (e < 0.75 ? 0.5 : 0)
                fx.dust = dustLevel(e, peak: 0.95, total: 9.5)
                if e < 1.5 { fx.shakeX = 13 * (1 - e / 1.5) * sgn; fx.shakeY = -9 * (1 - e / 1.5) * sgn }
            }
        }
        return fx
    }
}

// MARK: - Фигуры
struct StarShape: Shape {
    var points: Int
    var inner: Double
    func path(in rect: CGRect) -> Path {
        var p = Path()
        let c = CGPoint(x: rect.midX, y: rect.midY)
        let r = Double(min(rect.width, rect.height)) / 2
        let n = points * 2
        for i in 0..<n {
            let rr = (i % 2 == 0) ? r : r * inner
            let a = Double.pi * 2 * Double(i) / Double(n) - Double.pi / 2
            let pt = CGPoint(x: c.x + CGFloat(cos(a) * rr), y: c.y + CGFloat(sin(a) * rr))
            if i == 0 { p.move(to: pt) } else { p.addLine(to: pt) }
        }
        p.closeSubpath()
        return p
    }
}

struct CrackShape: Shape {
    var stage: Int
    var seed: Int
    var hx: Double
    var hy: Double

    func path(in rect: CGRect) -> Path {
        var p = Path()
        let c = CGPoint(x: rect.width * CGFloat(hx), y: rect.height * CGFloat(hy))
        var rng = SplitMix(UInt64(truncatingIfNeeded: seed) &* 0x2545F4914F6CDD1D &+ 99)
        let rays = 9
        let reach = Double(max(rect.width, rect.height)) * (stage == 1 ? 0.28 : (stage == 2 ? 0.55 : 0.95))
        var all: [[CGPoint]] = []
        for r in 0..<rays {
            var ang = 2 * Double.pi * Double(r) / Double(rays) + (rng.unit() - 0.5) * 0.5
            let len = reach * (0.65 + rng.unit() * 0.5)
            var pts: [CGPoint] = [c]
            var cur = c
            var d = 0.0
            while d < len {
                let step = 10.0 + rng.unit() * 12.0
                ang += (rng.unit() - 0.5) * 0.45
                cur = CGPoint(x: cur.x + CGFloat(cos(ang) * step), y: cur.y + CGFloat(sin(ang) * step))
                pts.append(cur)
                d += step
            }
            all.append(pts)
            p.move(to: c)
            for q in pts.dropFirst() { p.addLine(to: q) }
        }
        if stage >= 2 {
            let rings = stage == 2 ? [3, 6] : [3, 6, 10]
            for ring in rings {
                for r in 0..<rays {
                    let a = all[r], b = all[(r + 1) % rays]
                    if rng.unit() < 0.8 && ring < a.count && ring < b.count {
                        p.move(to: a[ring]); p.addLine(to: b[ring])
                    }
                }
            }
        }
        return p
    }
}

// MARK: - Слои эффектов
private struct CrackLayer: View {
    let fx: FXState
    let size: CGSize
    var body: some View {
        ZStack {
            Rectangle().fill(Color.white.opacity(0.06))
            CrackShape(stage: fx.crack, seed: fx.crackSeed, hx: fx.holeX, hy: fx.holeY)
                .stroke(Color.black.opacity(0.55), style: StrokeStyle(lineWidth: 3.4, lineCap: .round, lineJoin: .round))
            CrackShape(stage: fx.crack, seed: fx.crackSeed, hx: fx.holeX, hy: fx.holeY)
                .stroke(Color.white.opacity(0.95), style: StrokeStyle(lineWidth: 1.4, lineCap: .round, lineJoin: .round))
            Circle().fill(Color.black).frame(width: 9, height: 9)
                .position(x: size.width * CGFloat(fx.holeX), y: size.height * CGFloat(fx.holeY))
            Circle().stroke(Color.white.opacity(0.9), lineWidth: 1.5).frame(width: 13, height: 13)
                .position(x: size.width * CGFloat(fx.holeX), y: size.height * CGFloat(fx.holeY))
        }
    }
}

private struct BoomView: View {
    let p: Double
    let big: Bool
    let size: CGSize
    var body: some View {
        let base = Double(min(size.width, size.height)) * (big ? 1.5 : 1.0)
        let d = base * (0.35 + 1.1 * p.squareRoot())
        ZStack {
            StarShape(points: 13, inner: 0.55).fill(Color(red: 0.95, green: 0.35, blue: 0.08))
                .frame(width: CGFloat(d), height: CGFloat(d))
            StarShape(points: 13, inner: 0.5).fill(Color(red: 1.0, green: 0.78, blue: 0.15))
                .frame(width: CGFloat(d * 0.72), height: CGFloat(d * 0.72)).rotationEffect(.degrees(14))
            StarShape(points: 11, inner: 0.5).fill(Color(red: 1.0, green: 0.97, blue: 0.8))
                .frame(width: CGFloat(d * 0.4), height: CGFloat(d * 0.4))
        }
        .opacity(1.0 - 0.75 * p)
        .position(x: size.width / 2, y: size.height * 0.45)
    }
}

private struct GrenadeIcon: View {
    var body: some View {
        ZStack {
            Ellipse().fill(Color(red: 0.34, green: 0.42, blue: 0.2)).frame(width: 26, height: 32)
            Rectangle().fill(Color.gray).frame(width: 10, height: 6).offset(y: -18)
            Capsule().fill(Color(white: 0.75)).frame(width: 14, height: 4).offset(x: 6, y: -22)
        }
    }
}

private struct RocketIcon: View {
    var body: some View {
        ZStack {
            Capsule().fill(Color(red: 0.34, green: 0.4, blue: 0.24)).frame(width: 44, height: 14)
            Circle().fill(Color(red: 0.85, green: 0.28, blue: 0.15)).frame(width: 14, height: 14).offset(x: 24)
            Circle().fill(Color.orange).frame(width: 12, height: 12).offset(x: -26)
        }
    }
}

private struct FlyingView: View {
    let kind: Int
    let p: Double
    let size: CGSize
    var body: some View {
        let e = p * p
        let sc = 0.25 + 2.9 * e
        let x = Double(size.width) * (0.70 - 0.20 * p)
        let y = Double(size.height) * (0.62 - 0.14 * p) - 30 * sin(p * Double.pi)
        Group {
            if kind == 1 { GrenadeIcon() } else { RocketIcon() }
        }
        .scaleEffect(CGFloat(sc))
        .rotationEffect(.degrees(kind == 1 ? p * 540 : -25))
        .position(x: CGFloat(x), y: CGFloat(y))
    }
}

private struct DustLayer: View {
    let dust: Double
    let size: CGSize
    var body: some View {
        ZStack {
            Rectangle().fill(Color(red: 0.36, green: 0.31, blue: 0.26).opacity(dust * 0.85))
            Ellipse().fill(Color(red: 0.70, green: 0.62, blue: 0.50).opacity(dust * 0.45))
                .frame(width: size.width * 0.7, height: size.height * 0.8).offset(x: -size.width * 0.18, y: size.height * 0.05)
            Ellipse().fill(Color(red: 0.62, green: 0.55, blue: 0.45).opacity(dust * 0.4))
                .frame(width: size.width * 0.6, height: size.height * 0.7).offset(x: size.width * 0.22, y: -size.height * 0.08)
        }
    }
}

/// Все эффекты событий одним слоем. Рисуется поверх персонажа.
struct FXOverlay: View {
    let fx: FXState
    let size: CGSize
    var body: some View {
        ZStack {
            if fx.crack > 0 { CrackLayer(fx: fx, size: size) }
            if fx.boom > 0 { BoomView(p: fx.boom, big: fx.boomBig, size: size) }
            if fx.fly > 0 { FlyingView(kind: fx.fly, p: fx.flyP, size: size) }
            if fx.dust > 0.01 { DustLayer(dust: fx.dust, size: size) }
            if fx.flash > 0.01 { Rectangle().fill(Color.white.opacity(fx.flash)) }
        }
        .frame(width: size.width, height: size.height)
        .allowsHitTesting(false)
    }
}
