import { expect, test } from 'claude-code/testing'

type Look = { level: number; overlay: string; agents: number }

test('idle is dust; work and subagents organise the field; events set the overlay', async ($, on) => {
  // The engine's state store and clock, played here.
  let stored: unknown = undefined
  let version = 0
  let clock = 1_000_000
  on('clock.now', () => ({ value: (clock += 100) }))
  on('state.get', () => ({ value: stored === undefined ? {} : { value: stored, version } }))
  on('state.set', (_, e) => {
    stored = (e as { value: unknown }).value
    version += 1
    return { value: { isSet: true, version } }
  })
  const look = () => stored as Look | undefined

  on('tool.call', (_, e) => (e.tool === 'Bash' && e.command === 'false' ? { result: {}, isError: true } : { result: {} }))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))

  await $.turn.start({ text: 'go', turnId: 't1' })
  expect(look()?.level).toBe(1)

  await $.tool.call({ tool: 'Read', file_path: '/x' })
  expect(look()?.overlay).toBe('scan')

  await $.tool.call({ tool: 'Edit', file_path: '/x', old_string: 'a', new_string: 'b' })
  expect(look()?.overlay).toBe('write')

  await $.tool.call({ tool: 'Bash', command: 'false' })
  expect(look()?.overlay).toBe('error')

  // two subagents: two rings, and the field organises further
  await $.turn.start({ text: 'a', turnId: 'a1', agentId: 'agent-1' })
  await $.turn.start({ text: 'b', turnId: 'b1', agentId: 'agent-2' })
  expect(look()?.agents).toBe(2)
  expect(look()?.level).toBeGreaterThanOrEqual(2)

  await $.turn.complete({ turnId: 'a1', agentId: 'agent-1', reason: 'answer' } as never)
  await $.turn.complete({ turnId: 'b1', agentId: 'agent-2', reason: 'answer' } as never)
  expect(look()?.agents).toBe(0)

  await $.turn.complete({ turnId: 't1', reason: 'answer' } as never)
  expect(look()?.level).toBe(0)
  expect(look()?.overlay).toBe('done')
})

for (const [env, where, phosphor] of [
  [{}, 'local', 'paper'],
  [{ SSH_CONNECTION: '10.0.0.2 52000 10.0.0.9 22' }, 'ssh', 'mint'],
  [{ CLAUDE_CODE_REMOTE: 'true' }, 'cloud', 'cobalt'],
] as const) {
  test(`a session ${where} takes ${phosphor}`, { options: { thisComputer: 'paper' } }, async ($, on) => {
    let stored: Record<string, unknown> = {}
    on('env.get', (_, e) => ({ value: (env as Record<string, string>)[(e as { name: string }).name] }))
    on('state.get', (_, e) => {
      const key = (e as { key: string }).key
      return { value: key in stored ? { value: stored[key], version: 1 } : {} }
    })
    on('state.set', (_, e) => {
      const { key, value } = e as { key: string; value: unknown }
      stored = { ...stored, [key]: value }
      return { value: { isSet: true, version: 1 } }
    })
    on('session.start', (_, e) => ({ cwd: e.cwd }))

    await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
    expect(stored.place).toEqual({ where, phosphor })
  })
}
