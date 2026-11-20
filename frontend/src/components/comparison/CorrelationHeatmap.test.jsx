import { describe, it, expect } from 'vitest'
import { getCorrelationColor } from './CorrelationHeatmap'

describe('getCorrelationColor', () => {
  it('-1~1 전 구간을 구분해 칠한다(음수와 0이 같은 색이 아님)', () => {
    for (const isDark of [true, false]) {
      expect(getCorrelationColor(-0.41, isDark)).not.toBe(getCorrelationColor(0, isDark))
      expect(getCorrelationColor(-1, isDark)).not.toBe(getCorrelationColor(1, isDark))
    }
  })

  it('범위를 벗어난 값은 -1·1로 자른다', () => {
    expect(getCorrelationColor(1.5, true)).toBe(getCorrelationColor(1, true))
    expect(getCorrelationColor(-2, false)).toBe(getCorrelationColor(-1, false))
  })
})
