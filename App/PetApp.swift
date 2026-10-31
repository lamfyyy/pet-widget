import SwiftUI
import WidgetKit

@main
struct PetApp: App {
    var body: some Scene { WindowGroup { ContentView() } }
}

/// Проверка без виджета: можно посмотреть любой набор кадров и запустить событие с эффектами.
/// Здесь частота не ограничена iOS, поэтому это «как должно выглядеть», а не «как будет в виджете».
struct ContentView: View {
    @State private var clip = "calm_idle"
    @State private var event: PetEvent? = nil
    @State private var eventStart = Date()
    @State private var step: Double = {
        let v = UserDefaults(suiteName: PetConfig.group)?.double(forKey: "entryStep") ?? 0
        return v >= 0.1 ? v : 0.25
    }()
    private let stage = CGSize(width: 340, height: 170)

    private var names: [String] { FrameManifest.counts.keys.sorted() }

    var body: some View {
        VStack(spacing: 14) {
            TimelineView(.periodic(from: .now, by: PetConfig.frameInterval)) { ctx in
                let el = ctx.date.timeIntervalSince(eventStart)
                let evFrame: String? = event?.frame(at: el)
                let fx: FXState = event.map { PetFX.state(event: $0, elapsed: el, seed: 42) } ?? FXState()
                let n = max(FrameManifest.counts[clip] ?? 1, 1)
                let i = Int(ctx.date.timeIntervalSinceReferenceDate / PetConfig.frameInterval) % n
                let name = evFrame ?? "\(clip)_\(i)"
                ZStack {
                    RoundedRectangle(cornerRadius: 22).fill(Color(white: 0.86))
                    Image(PetFrames.safe(name)).resizable().scaledToFit().frame(height: stage.height - 10)
                    FXOverlay(fx: fx, size: stage)
                }
                .frame(width: stage.width, height: stage.height)
                .clipShape(RoundedRectangle(cornerRadius: 22))
                .offset(x: CGFloat(fx.shakeX), y: CGFloat(fx.shakeY))
            }
            Picker("Набор кадров", selection: $clip) {
                ForEach(names, id: \.self) { Text($0).tag($0) }
            }
            .pickerStyle(.menu)
            HStack {
                ForEach(PetEvent.allCases, id: \.self) { ev in
                    Button(ev.rawValue) { event = ev; eventStart = Date() }
                        .buttonStyle(.borderedProminent)
                }
            }
            VStack(spacing: 4) {
                Text("Шаг записей таймлайна виджета (секунды)").font(.footnote.bold())
                Picker("Шаг", selection: $step) {
                    Text("0.25").tag(0.25); Text("0.5").tag(0.5); Text("1").tag(1.0); Text("2").tag(2.0)
                }
                .pickerStyle(.segmented)
                .onChange(of: step) { _, v in
                    UserDefaults(suiteName: PetConfig.group)?.set(v, forKey: "entryStep")
                    WidgetCenter.shared.reloadAllTimelines()
                }
                Text("Меньше шаг — больше записей, но iOS сама решает, как часто их показывать. Меняйте и смотрите на виджет.")
                    .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            Text("Кнопки запускают событие гнева (пистолет, граната, РПГ) вместе с трещинами и пылью. Затем добавьте виджет Pet на домашний экран.")
                .font(.footnote).multilineTextAlignment(.center).foregroundStyle(.secondary)
        }
        .padding()
    }
}
