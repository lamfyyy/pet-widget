import Foundation

// MARK: - Настройки анимации (всё, что можно крутить, — здесь)
enum PetConfig {
    /// App Group. SideStore/AltStore переименовывают группу — берём реальное имя из Info.plist.
    static let group: String = {
        if let g = Bundle.main.object(forInfoDictionaryKey: "ALTAppGroups") as? [String], let f = g.first { return f }
        return "group.com.example.pet"
    }()
    static let widgetKind = "PetWidget"

    static let resetInterval: TimeInterval = 5        // сброс счётчика без нажатий
    static let maxCount = 10
    static let frameInterval: TimeInterval = 0.25     // длительность одного кадра в сценарии (события, реакции, ходьба)

    /// Шаг записей таймлайна для WidgetKit. Меняется в приложении (экран «Скорость») без пересборки.
    /// 0.25 = просим 4 записи в секунду; iOS может показывать их реже. Если анимация «прыгает» — поставьте 0.5 или 1.
    static var entryStep: TimeInterval {
        let v = UserDefaults(suiteName: group)?.double(forKey: "entryStep") ?? 0
        return v >= 0.1 ? v : 0.25
    }
    static let timelineSeconds: TimeInterval = 20     // сколько секунд анимации закладываем за один раз
    static let nextReload: TimeInterval = 10 * 60     // когда просить iOS обновить виджет после окна анимации
    static let reactionSeconds: TimeInterval = 0.5    // длина реакции/перехода (2 кадра)
    static let maxX = 0.9                             // предел блуждания (-1…1 по ширине свободного места)
    static let nightStartHour = 23
    static let nightEndHour = 7
    static let fxLifetime: TimeInterval = 12          // сколько живут трещины/пыль после события
}

// MARK: - Эмоции (по счётчику нажатий)
enum Mood: String {
    case sleep, calm, sad, annoyed, angry

    /// Таблица порогов: 0 — сон, 1 — спокоен, 2–4 — расстроен, 5–9 — недоволен, 10 — гнев.
    static func from(count: Int) -> Mood {
        switch count {
        case ..<1: return .sleep
        case 1: return .calm
        case 2...4: return .sad
        case 5...9: return .annoyed
        default: return .angry
        }
    }

    /// Скорость ходьбы (доля диапазона в секунду).
    var walkSpeed: Double {
        switch self {
        case .sleep: return 0
        case .calm: return 0.20
        case .sad: return 0.11
        case .annoyed: return 0.30
        case .angry: return 0.42
        }
    }
    var hasPoke: Bool { self == .sad || self == .annoyed || self == .angry }
}

// MARK: - Время суток
enum PetClock {
    static func isNight(_ t: Double) -> Bool {
        let h = Calendar.current.component(.hour, from: Date(timeIntervalSince1970: t))
        return h >= PetConfig.nightStartHour || h < PetConfig.nightEndHour
    }

    /// Последняя граница день/ночь (7:00 или 23:00), не позже t.
    static func lastBoundary(_ t: Double) -> Double {
        let cal = Calendar.current
        let start = cal.startOfDay(for: Date(timeIntervalSince1970: t))
        var best = -1.0
        for offset in [-1, 0] {
            guard let day = cal.date(byAdding: .day, value: offset, to: start) else { continue }
            for h in [PetConfig.nightEndHour, PetConfig.nightStartHour] {
                if let d = cal.date(bySettingHour: h, minute: 0, second: 0, of: day) {
                    let b = d.timeIntervalSince1970
                    if b <= t && b > best { best = b }
                }
            }
        }
        return best < 0 ? 0 : best
    }

    /// Сколько секунд между a и b приходится на «дневное» время (7:00–23:00). Ночью персонаж спит и не ходит.
    static func awakeSeconds(from a: Double, to b: Double) -> Double {
        if b <= a { return 0 }
        let cal = Calendar.current
        var dayStart = cal.startOfDay(for: Date(timeIntervalSince1970: a))
        var total = 0.0
        var guardN = 0
        while dayStart.timeIntervalSince1970 < b && guardN < 5000 {
            guardN += 1
            let ws = cal.date(bySettingHour: PetConfig.nightEndHour, minute: 0, second: 0, of: dayStart)?.timeIntervalSince1970 ?? 0
            let we = cal.date(bySettingHour: PetConfig.nightStartHour, minute: 0, second: 0, of: dayStart)?.timeIntervalSince1970 ?? 0
            let lo = max(a, ws), hi = min(b, we)
            if hi > lo { total += hi - lo }
            dayStart = cal.date(byAdding: .day, value: 1, to: dayStart) ?? dayStart.addingTimeInterval(86400)
        }
        return total
    }
}

// MARK: - Детерминированное блуждание (позиция — функция времени, поэтому без скачков при перезагрузке таймлайна)
struct SplitMix {
    var s: UInt64
    init(_ seed: UInt64) { s = seed }
    mutating func next() -> UInt64 {
        s &+= 0x9E3779B97F4A7C15
        var z = s
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
    mutating func unit() -> Double { Double(next() >> 11) / 9007199254740992.0 }
}

struct WanderSample {
    var x: Double        // -1…1
    var dir: Int         // -1 влево, 0 стоит, 1 вправо
    var segT: Double     // секунд с начала текущего отрезка (ходьбы или паузы)
    var pauseLen: Double // длина текущей паузы (0, если идёт)
    var fidget: Int      // 0 — нет, 1…4 — какую «вставку» играть в паузе
}

enum Wander {
    static func sample(seed: UInt64, x0: Double, elapsed: Double, speed: Double) -> WanderSample {
        let still = WanderSample(x: x0, dir: 0, segT: 0, pauseLen: 0, fidget: 0)
        guard elapsed > 0, speed > 0 else { return still }
        var rng = SplitMix(seed &* 0x9E3779B97F4A7C15 &+ 1)
        var x = x0
        var left = elapsed
        var iter = 0
        while iter < 2_000_000 {
            iter += 1
            let pause = 1.2 + rng.unit() * 3.8
            let r2 = rng.unit()
            let r3 = rng.unit()
            let fid = (r2 < 0.7 && pause >= 2.2) ? 1 + min(3, Int(r3 * 4)) : 0
            if left < pause { return WanderSample(x: x, dir: 0, segT: left, pauseLen: pause, fidget: fid) }
            left -= pause
            var target = (rng.unit() * 2 - 1) * PetConfig.maxX
            if abs(target - x) < 0.3 { target = x > 0 ? x - 0.6 : x + 0.6 }
            target = min(max(target, -PetConfig.maxX), PetConfig.maxX)
            let dur = abs(target - x) / speed
            if left < dur {
                let dir = target > x ? 1 : -1
                return WanderSample(x: x + Double(dir) * speed * left, dir: dir, segT: left, pauseLen: 0, fidget: 0)
            }
            left -= dur
            x = target
        }
        return WanderSample(x: x, dir: 0, segT: 0, pauseLen: 0, fidget: 0)
    }
}

// MARK: - События в гневе
enum PetEvent: String, CaseIterable {
    case pistol, grenade, rpg

    private static func f(_ base: String, _ i: Int) -> String { "\(base)_\(i)" }

    /// Последовательность кадров (по одному на frameInterval).
    var sequence: [String] {
        let f = PetEvent.f
        switch self {
        case .pistol:   // выстрел на 1.0 с
            return [f("pistol_aim", 0), f("pistol_aim", 1), f("pistol_aim", 0), f("pistol_aim", 1),
                    f("pistol_fire", 0), f("pistol_fire", 1), f("pistol_smoke", 0), f("pistol_smoke", 0),
                    f("laugh", 0), f("laugh", 1), f("laugh", 2), f("laugh", 3)]
        case .grenade:  // бросок на 1.0 с, взрыв на 2.0 с
            return [f("grenade_pin", 0), f("grenade_pin", 1), f("grenade_pin", 1), f("grenade_throw", 0),
                    f("grenade_throw", 1), f("grenade_cover", 0), f("grenade_cover", 1), f("grenade_cover", 0),
                    f("grenade_cover", 1), f("grenade_cover", 0), f("grenade_cover", 1),
                    f("laugh", 0), f("laugh", 1), f("laugh", 2), f("laugh", 3)]
        case .rpg:      // выстрел на 1.25 с, взрыв на 1.75 с
            return [f("rpg_aim", 0), f("rpg_aim", 1), f("rpg_aim", 0), f("rpg_aim", 1), f("rpg_aim", 0),
                    f("rpg_fire", 0), f("rpg_fire", 1), f("rpg_smoke", 0), f("rpg_smoke", 1),
                    f("dizzy", 0), f("dizzy", 1), f("dizzy", 2), f("dizzy", 3),
                    f("dizzy", 0), f("dizzy", 1), f("dizzy", 2), f("dizzy", 3)]
        }
    }

    var duration: TimeInterval { Double(sequence.count) * PetConfig.frameInterval }

    func frame(at elapsed: Double) -> String? {
        guard elapsed >= 0 else { return nil }
        let i = Int(elapsed / PetConfig.frameInterval + 1e-6)
        return i < sequence.count ? sequence[i] : nil
    }
}

// MARK: - Проверка имён кадров (на случай опечатки — вместо пустого виджета покажем спокойный кадр)
enum PetFrames {
    static func isValid(_ name: String) -> Bool {
        guard let u = name.lastIndex(of: "_"), let i = Int(name[name.index(after: u)...]) else { return false }
        guard let n = FrameManifest.counts[String(name[..<u])] else { return false }
        return i >= 0 && i < n
    }
    static func safe(_ name: String) -> String { isValid(name) ? name : "calm_idle_0" }
}

// MARK: - Сохранённое состояние (App Group)
struct PetState: Codable {
    var count = 0
    var lastTap: Double = 0          // 0 — нажатий ещё не было
    var prevMood: String = Mood.calm.rawValue
    var anchorX: Double = 0
    var seed: Int = 1
    var eventKind: String = ""
    var eventStart: Double = 0
    var eventSeed: Int = 1
}

enum PetStore {
    static var defaults: UserDefaults { UserDefaults(suiteName: PetConfig.group) ?? .standard }
    static let key = "pet.state.v2"

    static func load() -> PetState {
        guard let data = defaults.data(forKey: key),
              let s = try? JSONDecoder().decode(PetState.self, from: data) else { return PetState() }
        return s
    }

    static func save(_ s: PetState) {
        if let data = try? JSONEncoder().encode(s) { defaults.set(data, forKey: key) }
    }

    /// Нажатие: фиксируем, где стоял персонаж и какая эмоция была до нажатия. В гневе повторное нажатие запускает случайное событие.
    static func registerTap(now: Date = Date()) {
        var s = load()
        let planner = PetPlanner(state: s, now: now)
        let t = planner.now
        let before = planner.effectiveCount(at: t)
        let snap = planner.snapshot(at: t)
        let prev = planner.moodInfo(at: t).mood

        var busy = false
        if let ev = PetEvent(rawValue: s.eventKind) { busy = t < s.eventStart + ev.duration }

        s.prevMood = prev.rawValue
        s.anchorX = snap.x
        s.count = min(before + 1, PetConfig.maxCount)
        s.lastTap = t
        s.seed = Int.random(in: 1..<1_000_000)
        if before >= PetConfig.maxCount && !busy {
            s.eventKind = (PetEvent.allCases.randomElement() ?? .pistol).rawValue
            s.eventStart = t
            s.eventSeed = Int.random(in: 1..<1_000_000)
        }
        save(s)
    }
}

// MARK: - Что показать в момент времени
struct PetSnapshot: Equatable {
    var frame: String
    var x: Double
    var flip: Bool
    var fx: FXState
    var mood: Mood

    static let placeholder = PetSnapshot(frame: "calm_idle_0", x: 0, flip: false, fx: FXState(), mood: .calm)
}

struct PetTimelineItem {
    let date: Date
    let snap: PetSnapshot
}

struct PetPlanner {
    let s: PetState
    let now: Double
    private let resetT: Double
    private let refT: Double
    private let xAtReset: Double
    private let awakeAtRef: Double
    private let baseSeed: UInt64

    init(state: PetState, now date: Date = Date()) {
        let n = date.timeIntervalSince1970
        let hasTap = state.lastTap > 0
        let r = hasTap ? state.lastTap + PetConfig.resetInterval : Calendar.current.startOfDay(for: date).timeIntervalSince1970
        let ref = max(n, r)
        s = state
        now = n
        resetT = r
        refT = ref
        xAtReset = hasTap ? PetPlanner.activeSample(state, r).x : 0
        awakeAtRef = PetClock.awakeSeconds(from: r, to: ref)
        baseSeed = hasTap ? UInt64(truncatingIfNeeded: state.seed) &* 1_000_003 &+ UInt64(truncatingIfNeeded: Int(r)) : 7
    }

    /// Позиция, пока идёт «серия нажатий» (до сброса). Во время события и первой реакции стоит на месте.
    static func activeSample(_ s: PetState, _ t: Double) -> WanderSample {
        let mood = Mood.from(count: s.count)
        var moveStart = s.lastTap + PetConfig.reactionSeconds
        if let ev = PetEvent(rawValue: s.eventKind) {
            let end = s.eventStart + ev.duration
            if end > s.lastTap { moveStart = max(moveStart, end) }
        }
        return Wander.sample(seed: UInt64(truncatingIfNeeded: s.seed), x0: s.anchorX, elapsed: t - moveStart, speed: mood.walkSpeed)
    }

    /// Позиция после сброса: блуждание продолжается с того места, где персонаж остановился; ночью время «не идёт».
    private func baseSample(at t: Double) -> WanderSample {
        let awake = awakeAtRef + PetClock.awakeSeconds(from: refT, to: t)
        return Wander.sample(seed: baseSeed, x0: xAtReset, elapsed: awake, speed: Mood.calm.walkSpeed)
    }

    func effectiveCount(at t: Double) -> Int {
        if s.lastTap > 0 && t < s.lastTap + PetConfig.resetInterval { return s.count }
        return PetClock.isNight(t) ? 0 : 1
    }

    /// Текущая эмоция, момент её начала и предыдущая эмоция (для кадров перехода).
    func moodInfo(at t: Double) -> (mood: Mood, changeT: Double, prev: Mood, fromTap: Bool) {
        if s.lastTap > 0 && t < s.lastTap + PetConfig.resetInterval {
            return (Mood.from(count: s.count), s.lastTap, Mood(rawValue: s.prevMood) ?? .calm, true)
        }
        let base: Mood = PetClock.isNight(t) ? .sleep : .calm
        let b = PetClock.lastBoundary(t)
        if b > resetT {
            return (base, b, base == .sleep ? .calm : .sleep, false)
        }
        let before: Mood = s.lastTap > 0 ? Mood.from(count: s.count) : base
        return (base, resetT, before, false)
    }

    private func reactionFrame(prev: Mood, cur: Mood, fromTap: Bool, since: Double) -> String? {
        let i = min(Int(since / PetConfig.frameInterval + 1e-6), 1)
        if prev != cur {
            if prev == .sleep && cur == .calm { return "wake_\(i)" }
            return "to_\(cur.rawValue)_\(i)"
        }
        if fromTap && cur.hasPoke { return "poke_\(cur.rawValue)_\(i)" }
        return nil
    }

    private static let fidgets = ["happy", "love", "curious", "yawn"]

    func snapshot(at t: Double, rest: Bool = false) -> PetSnapshot {
        let info = moodInfo(at: t)
        let mood = info.mood
        let tapActive = s.lastTap > 0 && t < s.lastTap + PetConfig.resetInterval
        let w = tapActive ? PetPlanner.activeSample(s, t) : baseSample(at: t)
        let x = (w.x * 100).rounded() / 100
        var dir = w.dir
        if mood == .sleep || rest { dir = 0 }

        // 1) событие (оно же задаёт эффекты поверх виджета)
        var fx = FXState()
        if let ev = PetEvent(rawValue: s.eventKind) {
            let el = t - s.eventStart
            fx = PetFX.state(event: ev, elapsed: el, seed: s.eventSeed)
            if tapActive, let name = ev.frame(at: el) {
                return PetSnapshot(frame: name, x: x, flip: false, fx: fx, mood: mood)
            }
        }

        // 2) реакция на нажатие / переход между эмоциями
        let since = t - info.changeT
        if since >= 0 && since < PetConfig.reactionSeconds,
           let name = reactionFrame(prev: info.prev, cur: info.mood, fromTap: info.fromTap, since: since) {
            return PetSnapshot(frame: name, x: x, flip: false, fx: fx, mood: mood)
        }

        // 3) ходьба
        if dir != 0 {
            let idx = Int(w.segT / PetConfig.frameInterval + 1e-6) % 4
            return PetSnapshot(frame: "\(mood.rawValue)_walk_\(idx)", x: x, flip: dir < 0, fx: fx, mood: mood)
        }

        // 4) случайные «вставки» эмоций в паузах (только в спокойном состоянии)
        if mood == .calm && !rest && w.fidget > 0 && w.segT >= 0.5 && w.segT < 1.5 {
            let idx = Int((w.segT - 0.5) / PetConfig.frameInterval + 1e-6) % 4
            return PetSnapshot(frame: "fid_\(PetPlanner.fidgets[w.fidget - 1])_\(idx)", x: x, flip: false, fx: fx, mood: mood)
        }

        // 5) покой
        let period = mood == .sleep ? PetConfig.frameInterval * 2 : PetConfig.frameInterval
        let idx = Int((t / period + 1e-6).rounded(.down)) % 4
        return PetSnapshot(frame: "\(mood.rawValue)_idle_\(idx)", x: x, flip: false, fx: fx, mood: mood)
    }

    /// Кадры на ближайшие timelineSeconds секунд. Одинаковые подряд кадры склеиваются (меньше записей — меньше нагрузка).
    func timeline() -> [PetTimelineItem] {
        let dt = PetConfig.entryStep
        let n = Int(PetConfig.timelineSeconds / dt)
        var out: [PetTimelineItem] = []
        for k in 0...n {
            let t = now + Double(k) * dt
            let snap = snapshot(at: t, rest: k == n)   // последний кадр — стоя, чтобы не «замёрзнуть» посреди шага
            if let last = out.last, last.snap == snap { continue }
            out.append(PetTimelineItem(date: Date(timeIntervalSince1970: t), snap: snap))
        }
        return out
    }
}
