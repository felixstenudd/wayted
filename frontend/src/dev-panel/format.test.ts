import { describe, expect, it } from 'vitest'

import { formatLayerCounts } from './format'

describe('formatLayerCounts', () => {
	it('lists each layer with its count, by layer name', () => {
		expect(formatLayerCounts({ roads: 9, parks: 9 })).toBe('9 parks, 9 roads')
	})

	it('keeps a layer that got nothing', () => {
		expect(formatLayerCounts({ parks: 2, roads: 0 })).toBe('2 parks, 0 roads')
	})
})
