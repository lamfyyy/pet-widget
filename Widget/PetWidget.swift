import WidgetKit
import SwiftUI
import AppIntents

struct PetEntry: TimelineEntry {
    let date: Date
    let snap: PetSnapshot
}

struct PetProvider: TimelineProvider {
    func placeholder(in context: Context) -> PetEntry { PetEntry(date: Date(), snap: PetSnapshot.placeholder) }

    func getSnapshot(in context: Context, completion: @escaping (PetEntry) -> Void) {
        completion(PetProvider.entries(Date()).first ?? placeholder(in: context))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<PetEntry>) -> Void) {
        let now = Date()
        // После окна анимации iOS обновит виджет сама (не чаще, чем позволяет бюджет).
        completion(Timeline(entries: PetProvider.entries(now), policy: .after(now.addingTimeInterval(PetConfig.nextReload))))
    }

    static func entries(_ now: Date) -> [PetEntry] {
        let planner = PetPlanner(state: PetStore.load(), now: now)
        return planner.timeline().map { PetEntry(date: $0.date, snap: $0.snap) }
    }
}

struct PetWidgetView: View {
    let entry: PetEntry
    @Environment(\.widgetFamily) private var family

    /// Картинка кадра. На iOS 18+ просим НЕ обесцвечивать её в режиме «прозрачные/тонированные иконки».
    @ViewBuilder
    private func frameImage(_ name: String) -> some View {
        let img = Image(PetFrames.safe(name)).resizable().interpolation(.high)
        if #available(iOS 18.0, *) {
            img.widgetAccentedRenderingMode(.fullColor).scaledToFit()
        } else {
            img.scaledToFit()
        }
    }

    var body: some View {
        let snap = entry.snap
        Button(intent: TapIntent()) {
            GeometryReader { geo in
                let charH = geo.size.height * (family == .systemSmall ? 0.84 : 0.96)
                let charW = charH                       // кадры квадратные 180x180
                let room = max(0, (geo.size.width - charH * 0.72) / 2)   // сам персонаж занимает около 72% ширины кадра
                ZStack {
                    frameImage(snap.frame)
                        .frame(width: charW, height: charH)
                        .scaleEffect(x: snap.flip ? -1 : 1, y: 1)
                        .offset(x: CGFloat(snap.x) * room)
                        // Попытка убрать «перетекание» кадров: каждый кадр — новая вьюха без анимации появления.
                        .id(snap.frame)
                        .transition(.identity)
                    FXOverlay(fx: snap.fx, size: geo.size)
                }
                .frame(width: geo.size.width, height: geo.size.height)
                .offset(x: CGFloat(snap.fx.shakeX), y: CGFloat(snap.fx.shakeY))
            }
            .animation(nil, value: snap.frame)
        }
        .buttonStyle(.plain)
        .contentTransition(.identity)
        .containerBackground(.clear, for: .widget)
    }
}

struct PetWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: PetConfig.widgetKind, provider: PetProvider()) { entry in
            PetWidgetView(entry: entry)
        }
        .configurationDisplayName("Pet")
        .description("Персонаж ходит и реагирует на нажатия.")
        .supportedFamilies([.systemSmall, .systemMedium])
        .contentMarginsDisabled()
    }
}

@main
struct PetWidgetBundle: WidgetBundle {
    var body: some Widget {
        PetWidget()
        PetLabWidget()
    }
}
