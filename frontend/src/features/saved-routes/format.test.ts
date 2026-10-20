import { describe, expect, it } from 'vitest'

import { formatDistanceKm, formatSavedOn } from './format'

const NOW = new Date('2026-10-20T12:00:00Z')

describe('formatSavedOn', () => {
	it('leaves out the year when the route was saved this year', () => {
		expect(formatSavedOn('2026-10-18T07:30:00Z', NOW, 'en-GB')).toBe('18 Oct')
	})

	it('adds the year for an older route', () => {
		expect(formatSavedOn('2025-12-31T07:30:00Z', NOW, 'en-GB')).toBe('31 Dec 2025')
	})
})

describe('formatDistanceKm', () => {
	it('shows kilometres with one decimal in the reader’s number format', () => {
		expect(formatDistanceKm(6420, 'en')).toBe('6.4')
		expect(formatDistanceKm(11800, 'sv')).toBe('11,8')
		expect(formatDistanceKm(5000, 'en')).toBe('5.0')
	})
})
