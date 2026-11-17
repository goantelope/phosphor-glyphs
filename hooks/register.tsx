import type { EngineInterface, Register, ThemeSetArgs } from 'claude-code'

import type { Look, Overlay } from '../types'
import { makeColors } from './make-colors.js'
import { AGENTS, BASE, BASE_CSS, CYCLE, DEFS, GATHER, H, OVERLAY, W } from './scenes'

// Phosphor Glyphs: the turntable display's look (home_automation, firmware/turntable-display).
// The roles are the display's phosphor palette (dial_core.h PALETTES): amber P3 is the main colour,
// ember P12 the "hot" accent, mint P1, cobalt P7. Dark is the CRT at night: warm black glass with
// amber-white text. Light is P4 "paper" phosphor: the same glyphs on a pale warm screen.
const { theme, problems } = makeColors({
  label: 'Phosphor Glyphs',
  roles: {
    accent: '#ffa82c', // amber
    danger: '#ff5a3c', // ember, pushed a little redder so it still reads as danger
    success: '#5fd68a', // mint, deepened so it reads as green
    warning: '#ffcc33', // a yellower amber, apart from the accent
    pro: '#80b0ff', // cobalt
  },
  light: {
    gray: {
      anchors: {
        'surface-0': '#ece8dd',
        'surface-1': '#f2efe6',
        'surface-2': '#f8f6f0',
        'text-primary': '#1c160d',
        'text-secondary': '#463b2b',
        'text-muted': '#5f5240',
      },
    },
  },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#0e0b07',
        'surface-1': '#16120c',
        'surface-2': '#1d1810',
        'surface-3': '#241e15',
        'text-primary': '#ffe6c2',
        'text-secondary': '#e8c48e',
        'text-muted': '#b99a6a',
      },
    },
  },
})

const LOOK: ThemeSetArgs = {
  colors: theme,
  backdrop: { scene: 'phosphor-glyphs', glass: { blur: 18, opacity: 0.72 } },
}

const ALT = [
  'Amber glyphs drifting like dust in space',
  'Dust gathering into slowly turning spiral arms of glyphs',
  'A grid of glyph blocks with spiral and ring waves running through it',
  'A turning pinwheel of glyph spokes, waves popping outward',
] as const

// ---------- what the session is doing ----------

const LOOK_REF = { plugin: 'phosphor-glyphs', key: 'look' } as const
const IDLE: Look = { level: 0, from: 0, levelAt: 0, overlay: 'none', overlayAt: 0, agents: 0 }

const READING = new Set(['Read', 'Grep', 'Glob', 'LS', 'WebFetch', 'WebSearch', 'NotebookRead', 'ToolSearch'])
const WRITING = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit'])

function overlayFor(tool: string): Overlay {
  if (READING.has(tool)) return 'scan'
  if (WRITING.has(tool)) return 'write'
  return 'run'
}

// Work in the last 90 s, in tokens: each model response's output, and a flat amount per tool call.
// Kept in the module: a reload starts the count over, which only costs a few seconds of accuracy.
const WINDOW_MS = 90_000
const TOOL_WEIGHT = 300
let work: { at: number; tokens: number }[] = []
let mainActive = false
const running = new Set<string>()

function levelNow(now: number): Look['level'] {
  work = work.filter(w => now - w.at < WINDOW_MS)
  if (!mainActive && running.size === 0) return 0
  const tokens = work.reduce((sum, w) => sum + w.tokens, 0)
  // a subagent counts as a good deal of work in itself
  const score = tokens / 1000 + running.size * 2
  return score < 2 ? 1 : score < 7 ? 2 : 3
}

async function current($: EngineInterface): Promise<Look> {
  const { value } = await $.state.get(LOOK_REF)
  return value ?? IDLE
}

/** Recomputes the level and writes the look when something a viewer would see changed. */
async function refresh($: EngineInterface, overlay?: Overlay, replay = false) {
  const now = await $.clock.now()
  const was = await current($)
  const level = levelNow(now)
  const next: Look = { ...was, agents: Math.min(running.size, AGENTS.length) }
  if (level !== was.level) {
    next.from = was.level
    next.level = level
    next.levelAt = now
  }
  if (overlay !== undefined && (overlay !== was.overlay || replay)) {
    next.overlay = overlay
    next.overlayAt = now
  }
  const isSame =
    next.level === was.level && next.agents === was.agents && next.overlay === was.overlay && next.overlayAt === was.overlayAt
  if (!isSame) {
    await $.state.set(LOOK_REF, next)
  }
}

// ---------- drawing ----------

const GATHER_MS = 2600
const ONE_SHOT_MS = 3200

function compose(look: Look, now: number): string {
  const s = (ms: number) => `${(-ms / 1000).toFixed(2)}s`
  const o = s(now % (CYCLE * 1000))
  const sinceLevel = now - look.levelAt
  const sinceOverlay = now - look.overlayAt

  const base = BASE[look.level] ?? BASE[0]!
  const isChanging = sinceLevel < GATHER_MS && look.from !== look.level
  // gathering: a swarm flies into the new pattern; scattering: out of the old one
  const isGathering = look.level > look.from
  const swarm = isChanging ? GATHER[isGathering ? look.level : look.from] : undefined
  // a finished one-shot overlay draws nothing more, so leave it out
  const isOneShot = look.overlay === 'error' || look.overlay === 'done'
  const overlay = isOneShot && sinceOverlay > ONE_SHOT_MS ? OVERLAY.none : OVERLAY[look.overlay]
  const agents = AGENTS.slice(0, look.agents)

  const css = [BASE_CSS, base.css, swarm?.css ?? '', ...agents.map(a => a.css), overlay.css].join('')
  const body = [
    `<g class="${isChanging ? 'fi' : ''}" style="--e:${s(sinceLevel)}">${base.body}</g>`,
    swarm ? `<g class="${isGathering ? '' : 'gs'}" style="--e:${s(sinceLevel)}">${swarm.body}</g>` : '',
    agents.map(a => a.body).join(''),
    `<g style="--e:${s(sinceOverlay)}">${overlay.body}</g>`,
  ].join('')

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice" style="--o:${o};--e:0s">` +
    `<style>${css}</style>${DEFS}${body}</svg>`
  )
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const unpainted = problems.find(line => line.startsWith("Desktop won't paint"))
    if (unpainted !== undefined) {
      $.ui.toast(unpainted)
    }
    const set = await $.theme.set(LOOK)
    if (!set.isDrawn) {
      $.ui.status(set.reason)
    }
    // the level falls as work stops arriving, so look again now and then
    $.clock.every(10_000, () => refresh($))
    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    mainActive = true
    await refresh($, 'none')
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId !== undefined) {
      running.add(e.agentId)
    } else {
      mainActive = true
    }
    await refresh($)
    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    const result = yield* next(e)
    const tokens = result.usage?.output_tokens ?? 0
    work.push({ at: await $.clock.now(), tokens })
    await refresh($)
    return result
  })

  on('tool.call', async ($, e, next) => {
    work.push({ at: await $.clock.now(), tokens: TOOL_WEIGHT })
    // some connected tools' calls carry no `tool` name in their type; those count as running
    await refresh($, overlayFor('tool' in e ? String(e.tool) : ''))
    const result = await next(e)
    if (result.isError === true) {
      await refresh($, 'error', true)
    }
    return result
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId !== undefined) {
      running.delete(e.agentId)
      await refresh($)
    } else {
      mainActive = false
      await refresh($, e.reason === 'answer' ? 'done' : 'error', true)
    }
    return next(e)
  })

  on('ui.render', { component: 'Backdrop' }, async ($, e, next) => {
    if ((e.surface !== 'desktop' && e.surface !== 'mobile') || e.props.scene !== 'phosphor-glyphs') {
      return next(e)
    }
    const { Svg } = $.ui.resolve(e)
    const look = await current($)
    const now = await $.clock.now()
    const agents = look.agents > 0 ? `, ${look.agents} subagent ring${look.agents === 1 ? '' : 's'} circling` : ''

    return <Svg source={compose(look, now)} alt={ALT[look.level] + agents} isInteractive />
  })
}
