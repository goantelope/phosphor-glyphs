/** The event of the moment, drawn over the field. */
export type Overlay = 'none' | 'scan' | 'write' | 'run' | 'error' | 'done'

/** What the backdrop shows: how organised the field is, what just happened, how many subagents run. */
export type Look = {
  /** 0 dust, 1 gathering, 2 Weather Map, 3 Glyph Ring */
  level: 0 | 1 | 2 | 3
  /** the level before the last change, and when it changed (`$.clock.now()` ms) */
  from: 0 | 1 | 2 | 3
  levelAt: number
  overlay: Overlay
  /** when the overlay began, for its one-shot animations */
  overlayAt: number
  agents: number
}

declare module 'claude-code' {
  interface PluginState {
    'phosphor-glyphs': { look: Look }
  }
}
