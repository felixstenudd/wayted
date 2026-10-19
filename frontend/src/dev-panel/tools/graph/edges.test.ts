import { describe, expect, it } from 'vitest'

import type { Graph } from '../../dev-api/types'
import {
	colorScale,
	edgeColor,
	isFixedScale,
	scoredCount,
	scoreNames,
	scoreRange,
	toMapEdges,
} from './edges'

const edge = (id: number, scores: Record<string, unknown>) => ({
	type: 'Feature' as const,
	geometry: {
		type: 'LineString' as const,
		coordinates: [
			[18, 59],
			[18.1, 59.1],
		],
	},
	properties: {
		id,
		way_id: 100 + id,
		source: 1,
		target: 2,
		length_m: 12.5,
		forward: ['cycling', 'running'],
		backward: ['running'],
		scores,
		tags: { highway: 'residential' },
	},
})

const graph = (...edges: ReturnType<typeof edge>[]): Graph => ({
	edges: { type: 'FeatureCollection', features: edges },
	vertices: { type: 'FeatureCollection', features: [] },
})

const scored = graph(
	edge(1, { green: 0.2, quiet: 1 }),
	edge(2, { green: 0.8, note: 'text', broken: Number.NaN }),
	edge(3, {}),
)
const colors = { plain: 'black', low: 'grey', high: 'green' }

describe('toMapEdges', () => {
	it('keeps the id and flattens the numeric scores', () => {
		const data = toMapEdges(scored)
		expect(data.features.map((f) => f.properties)).toEqual([
			{ id: 1, 'score:green': 0.2, 'score:quiet': 1 },
			{ id: 2, 'score:green': 0.8 },
			{ id: 3 },
		])
	})
})

describe('scoreNames', () => {
	it('lists the scores that hold a number, sorted', () => {
		expect(scoreNames(scored)).toEqual(['green', 'quiet'])
	})

	it('is empty before the enricher has scored anything', () => {
		expect(scoreNames(graph(edge(1, {}), edge(2, {})))).toEqual([])
	})
})

describe('scoreRange', () => {
	it('runs from the smallest to the largest value', () => {
		expect(scoreRange(scored, 'green')).toEqual({ min: 0.2, max: 0.8 })
	})

	it('is null for a score no edge has', () => {
		expect(scoreRange(scored, 'hilly')).toBeNull()
	})
})

describe('colorScale', () => {
	it('runs from 0 to 1 for green in every view', () => {
		expect(colorScale(scored, 'green')).toEqual({ min: 0, max: 1 })
		expect(isFixedScale('green')).toBe(true)
	})

	it('runs from 0 to 1 for nature too', () => {
		expect(isFixedScale('nature')).toBe(true)
	})

	it('runs over the values in view for other scores', () => {
		expect(colorScale(scored, 'quiet')).toEqual({ min: 1, max: 1 })
		expect(isFixedScale('quiet')).toBe(false)
	})

	it('is null for a score no edge has', () => {
		expect(colorScale(graph(edge(1, {})), 'green')).toBeNull()
	})
})

describe('scoredCount', () => {
	it('counts the edges that hold a number for the score', () => {
		expect(scoredCount(scored, 'green')).toBe(2)
		expect(scoredCount(scored, 'quiet')).toBe(1)
	})
})

describe('edgeColor', () => {
	it('is plain without a score to colour by', () => {
		expect(edgeColor(null, null, colors)).toBe('black')
		expect(edgeColor('hilly', null, colors)).toBe('black')
	})

	it('runs from low to high, and stays plain on edges without the score', () => {
		expect(edgeColor('green', { min: 0.2, max: 0.8 }, colors)).toEqual([
			'case',
			['has', 'score:green'],
			['interpolate', ['linear'], ['get', 'score:green'], 0.2, 'grey', 0.8, 'green'],
			'black',
		])
	})

	it('uses one colour when every edge has the same value', () => {
		expect(edgeColor('quiet', { min: 1, max: 1 }, colors)).toEqual([
			'case',
			['has', 'score:quiet'],
			'green',
			'black',
		])
	})
})
