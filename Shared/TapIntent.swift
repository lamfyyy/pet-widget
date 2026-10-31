import AppIntents
import WidgetKit

struct TapIntent: AppIntent {
    static var title: LocalizedStringResource = "Poke"
    static var openAppWhenRun = false

    func perform() async throws -> some IntentResult {
        PetStore.registerTap()
        // iOS обычно сама обновляет виджет после интента; явный вызов — страховка.
        WidgetCenter.shared.reloadTimelines(ofKind: PetConfig.widgetKind)
        return .result()
    }
}
