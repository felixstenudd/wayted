import { describe, expect, it } from 'vitest'

import { reasonsBySide, reviewSides, reviewTone, toggleReason, type ReviewReason } from './reasons'

const REASONS: ReviewReason[] = [
	{ code: 'green_good', topic: 'green', sentiment: 1, attribute: 'green' },
	{ code: 'green_bad', topic: 'green', sentiment: -1, attribute: 'green' },
	{ code: 'access_bad', topic: 'access', sentiment: -1, attribute: null },
]

describe('toggleReason', () => {
	it('adds a reason, and takes it away again', () => {
		expect(toggleReason([], 'access_bad', REASONS)).toEqual(['access_bad'])
		expect(toggleReason(['access_bad'], 'access_bad', REASONS)).toEqual([])
	})

	it('drops the other side of a topic when one side is chosen', () => {
		expect(toggleReason(['green_bad', 'access_bad'], 'green_good', REASONS)).toEqual([
			'access_bad',
			'green_good',
		])
	})
})

describe('reasonsBySide', () => {
	it('splits the reasons into good and bad, keeping their order', () => {
		const { good, bad } = reasonsBySide(REASONS)
		expect(good.map((r) => r.code)).toEqual(['green_good'])
		expect(bad.map((r) => r.code)).toEqual(['green_bad', 'access_bad'])
	})
})

describe('reviewSides', () => {
	it('splits a review into good and bad, in list order', () => {
		expect(reviewSides(['access_bad', 'green_good'], REASONS)).toEqual({
			good: ['green_good'],
			bad: ['access_bad'],
		})
	})
})

describe('reviewTone', () => {
	it('says good, bad, or mixed', () => {
		expect(reviewTone({ good: ['green_good'], bad: [] })).toBe('good')
		expect(reviewTone({ good: [], bad: ['access_bad'] })).toBe('bad')
		expect(reviewTone({ good: ['green_good'], bad: ['access_bad'] })).toBe('mixed')
	})
})
