import { fileURLToPath } from 'url'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Regression test for the ClarifyPrompt number-key "Other" path.
 *
 * The prompt renders `[...choices, 'Other (type your answer)']` — so the
 * visible rows are `choices.length + 1`, and the displayed number on the
 * "Other" row is `choices.length + 1`. The numeric-key handler used to
 * accept only `1..choices.length` and silently dropped `choices.length + 1`
 * even though the user could see the labeled row. After the fix, that key
 * flips the prompt into the custom-answer (typing) view.
 *
 * We assert the source shape instead of mounting Ink — the handler is an
 * inline `useInput` closure over component state, so a behavioral test would
 * need React + ink-testing-library setup we don't carry here. The three
 * assertions below cover the load-bearing pieces: the "Other" row exists in
 * the rendered list, the number-key handler routes `choices.length + 1` into
 * `setTyping(true)`, and `1..choices.length` still picks a choice.
 */
const here = dirname(fileURLToPath(import.meta.url))

describe('ClarifyPrompt — number key handling for the "Other" row', () => {
  const source = readFileSync(resolve(here, '../components/prompts.tsx'), 'utf8')

  it('renders the "Other (type your answer)" row alongside choices', () => {
    expect(source).toContain("'Other (type your answer)'")
  })

  it('routes numeric key choices.length + 1 into setTyping(true)', () => {
    const numberKeyBlock = source.match(
      /const n = parseInt\(ch\)[\s\S]{0,200}?if \(n === choices\.length \+ 1\)[\s\S]{0,80}?setTyping\(true\)/
    )
    expect(numberKeyBlock, 'expected number-key branch to set typing').not.toBeNull()
  })

  it('keeps numeric keys 1..choices.length mapped to their choice', () => {
    const earlyReturn = source.match(
      /if \(n >= 1 && n <= choices\.length\)[\s\S]{0,80}?onAnswer\(choices\[n - 1\]!\)/
    )
    expect(earlyReturn, 'expected 1..choices.length to still pick a choice').not.toBeNull()
  })
})
