import WidgetKit
import SwiftUI

// ЭКСПЕРИМЕНТАЛЬНЫЙ виджет «Pet Lab»: проверяет, оживает ли в виджете TimelineView (способ из найденного вами текста).
// Он ничего не ломает: основной виджет работает отдельно. Если персонаж здесь стоит на месте — этот способ у вас не работает.

struct LabEntry: TimelineEntry { let date: Date }

struct LabProvider: TimelineProvider {
    func placeholder(in context: Context) -> LabEntry { LabEntry(date: Date()) }
    func getSnapshot(in context: Context, completion: @escaping (LabEntry) -> Void) { completion(LabEntry(date: Date())) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<LabEntry>) -> Void) {
        completion(Timeline(entries: [LabEntry(date: Date())], policy: .after(Date().addingTimeInterval(15 * 60))))
    }
}

struct LabView: View {
    let entry: LabEntry
    private let frames = (0..<4).map { "calm_walk_\($0)" }

    var body: some View {
        VStack(spacing: 4) {
            // Способ из найденного текста: перерисовка по расписанию .animation
            TimelineView(.animation(minimumInterval: 0.1, paused: false)) { ctx in
                let i = Int(ctx.date.timeIntervalSince1970 * 8) % frames.count
                Image(frames[i]).resizable().scaledToFit()
            }
            // Контрольные часы: системный таймер, который iOS обновляет сама (раз в секунду).
            // Если цифры идут, а персонаж стоит — TimelineView в виджете не анимируется.
            Text(Date(), style: .timer)
                .font(.system(size: 12, weight: .bold, design: .monospaced))
                .foregroundStyle(.secondary)
        }
        .containerBackground(.clear, for: .widget)
    }
}

struct PetLabWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "PetLab", provider: LabProvider()) { entry in
            LabView(entry: entry)
        }
        .configurationDisplayName("Pet Lab (тест скорости)")
        .description("Эксперимент: анимируется ли TimelineView в виджете.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
