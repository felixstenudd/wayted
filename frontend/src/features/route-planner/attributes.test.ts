import { describe, expect, it } from 'vitest'

import { groupAttributes, humanizeKey, weightWord } from './attributes'
import type { RouteAttribute } from './types'

const attribute = (key: string, group: string, scored = true) =>
	({ key, group, scored }) as RouteAttribute

describe('groupAttributes', () => {
	it('groups attributes in the order the groups first appear, keeping their order', () => {
		const groups = groupAttributes([
			attribute('green', 'surroundings'),
			attribute('gravel', 'surface'),
			attribute('water', 'surroundings', false),
		])

		expect(
			groups.map(({ group, attributes }) => [group, attributes.map((a) => a.key)]),
		).toEqual([
			['surroundings', ['green', 'water']],
			['surface', ['gravel']],
		])
	})
})

describe('weightWord', () => {
	it.each([
		[-1, 'avoid'],
		[-0.6, 'ratherNot'],
		[0, 'dontMind'],
		[0.2, 'dontMind'],
		[0.37, 'niceToHave'],
		[0.9, 'prefer'],
	])('calls %d "%s"', (weight, word) => {
		expect(weightWord(weight)).toBe(word)
	})
})

describe('humanizeKey', () => {
	it('turns a key the app has no name for yet into words', () => {
		expect(humanizeKey('quiet_streets')).toBe('Quiet streets')
		expect(humanizeKey('hills')).toBe('Hills')
	})
})
