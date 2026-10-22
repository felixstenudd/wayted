import { describe, expect, it } from 'vitest'

import { slug } from './slug'

// The same cases as backend/tests/logbook/test_export_slug.py: both sides name files alike.
const CASES: [string, string][] = [
	['Morning loop', 'morning-loop'],
	['Södermalm', 'sodermalm'],
	['Crème brûlée à Ærø', 'creme-brulee-a-aero'],
	['Øresund runda', 'oresund-runda'],
	['Strandstraße', 'strandstrasse'],
	['Łódź', 'lodz'],
	['Œuvre Æbeltoft', 'oeuvre-aebeltoft'],
	['Đakovo Þórsmörk Ðorđe', 'dakovo-thorsmork-dorde'],
	['Kırkpınar', 'kirkpinar'],
	['  Runt Årstaviken, 2 varv!! ', 'runt-arstaviken-2-varv'],
	['Hill #3 / (fast)', 'hill-3-fast'],
	['a'.repeat(70), 'a'.repeat(60)],
	// The cut lands on a dash, which is trimmed.
	['word '.repeat(20), Array(12).fill('word').join('-')],
	['!!!', 'route-7'],
	['東京の道', 'route-7'],
]

describe('slug', () => {
	it.each(CASES)('names %j %j', (name, expected) => {
		expect(slug(name, 7)).toBe(expected)
	})
})
