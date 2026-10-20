import { describe, expect, it } from 'vitest'

import type { Graph } from '../../dev-api/types'
import {
	colorScale,
	edgeColor,
	feedbackActivities,
	feedbackColor,
	feedbackOption,
	feedbackOptionActivity,
	isFixedScale,
	netVotes,
	scoredCount,
	scoreNames,
	scoreToken,
	scoreRange,
	toMapEdges,
	votedCount,
} from './edges'

type Feedback = Record<string, Record<string, { up: number; down: number }>>

const edge = (id: number, scores: Record<string, unknown>, feedback: Feedback = {}) => ({
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
		feedback,
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

	it('runs from 0 to 1 for nature, water and prepared too', () => {
		expect(isFixedScale('nature')).toBe(true)
		expect(isFixedScale('water')).toBe(true)
		expect(isFixedScale('prepared')).toBe(true)
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

const reviewed = graph(
	edge(1, {}, { running: { green: { up: 3, down: 1 }, safety: { up: 0, down: 2 } } }),
	edge(2, {}, { cycling: { access: { up: 0, down: 1 } }, running: {} }),
	edge(3, {}),
)

describe('netVotes', () => {
	it('is up minus down over every topic, as a share of all votes', () => {
		expect(netVotes({ green: { up: 3, down: 1 }, safety: { up: 0, down: 2 } })).toBe(0)
		expect(netVotes({ access: { up: 0, down: 1 } })).toBe(-1)
	})

	it('is null without votes', () => {
		expect(netVotes({})).toBeNull()
	})
})

describe('review votes on the map', () => {
	it('flattens net votes per activity next to the scores', () => {
		expect(toMapEdges(reviewed).features.map((f) => f.properties)).toEqual([
			{ id: 1, 'feedback:running': 0 },
			{ id: 2, 'feedback:cycling': -1 },
			{ id: 3 },
		])
	})

	it('lists the activities with votes and counts their edges', () => {
		expect(feedbackActivities(reviewed)).toEqual(['cycling', 'running'])
		expect(votedCount(reviewed, 'running')).toBe(1)
		expect(votedCount(reviewed, 'cycling')).toBe(1)
	})

	it('runs from all down through mixed to all up, and stays plain without votes', () => {
		const colors = { plain: 'black', bad: 'brown', mixed: 'grey', good: 'green' }
		expect(feedbackColor('running', colors)).toEqual([
			'case',
			['has', 'feedback:running'],
			[
				'interpolate',
				['linear'],
				['get', 'feedback:running'],
				-1,
				'brown',
				0,
				'grey',
				1,
				'green',
			],
			'black',
		])
	})

	it('shares the colour-by choice with the scores', () => {
		expect(feedbackOptionActivity(feedbackOption('cycling'))).toBe('cycling')
		expect(feedbackOptionActivity('green')).toBeNull()
		expect(feedbackOptionActivity(null)).toBeNull()
	})
})

describe('scoreToken', () => {
	it('ends a share in the colour of the layer it measures', () => {
		expect(scoreToken('green')).toBe('--map-park')
		expect(scoreToken('nature')).toBe('--map-nature')
		expect(scoreToken('water')).toBe('--map-water')
		expect(scoreToken('prepared')).toBe('--map-score-high')
		expect(scoreToken('quiet')).toBe('--map-score-high')
	})
})
