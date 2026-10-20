import type { ExpressionSpecification } from 'maplibre-gl'

import type { Edge, Graph } from '../../dev-api/types'

export interface ScoreRange {
	min: number
	max: number
}

export interface EdgeColors {
	plain: string
	low: string
	high: string
}

export interface FeedbackColors {
	plain: string
	bad: string
	mixed: string
	good: string
}

type Votes = Edge['feedback'][string][string]

const scoreProperty = (name: string) => `score:${name}`
const feedbackProperty = (activity: string) => `feedback:${activity}`
const isScore = (value: unknown): value is number =>
	typeof value === 'number' && Number.isFinite(value)

/** Up votes minus down votes over all topics, as a share of all votes: -1 to 1. Null without votes. */
export function netVotes(topics: Record<string, Votes>): number | null {
	let up = 0
	let down = 0
	for (const votes of Object.values(topics)) {
		up += votes.up
		down += votes.down
	}
	return up + down === 0 ? null : (up - down) / (up + down)
}

/** Flat features for the map: the id, each numeric score, and net votes per activity. */
export function toMapEdges(graph: Graph) {
	return {
		type: 'FeatureCollection' as const,
		features: graph.edges.features.map(({ geometry, properties }) => {
			const flat: Record<string, number> = { id: properties.id }
			for (const [name, value] of Object.entries(properties.scores)) {
				if (isScore(value)) flat[scoreProperty(name)] = value
			}
			for (const [activity, topics] of Object.entries(properties.feedback)) {
				const net = netVotes(topics)
				if (net !== null) flat[feedbackProperty(activity)] = net
			}
			return { type: 'Feature' as const, geometry, properties: flat }
		}),
	}
}

// The colour-by choice holds a score name or one of these, so one select offers both.
const FEEDBACK_OPTION = 'feedback:'
export const feedbackOption = (activity: string) => `${FEEDBACK_OPTION}${activity}`
export const feedbackOptionActivity = (option: string | null): string | null =>
	option?.startsWith(FEEDBACK_OPTION) ? option.slice(FEEDBACK_OPTION.length) : null

/** The activities with a vote on at least one edge, sorted. */
export function feedbackActivities(graph: Graph): string[] {
	const activities = new Set<string>()
	for (const edge of graph.edges.features) {
		for (const [activity, topics] of Object.entries(edge.properties.feedback)) {
			if (netVotes(topics) !== null) activities.add(activity)
		}
	}
	return [...activities].sort()
}

export function votedCount(graph: Graph, activity: string): number {
	return graph.edges.features.filter((edge) => {
		const topics = edge.properties.feedback[activity]
		return topics !== undefined && netVotes(topics) !== null
	}).length
}

/** A line colour from all down votes through mixed to all up votes; plain without votes. */
export function feedbackColor(activity: string, colors: FeedbackColors): ExpressionSpecification {
	const net: ExpressionSpecification = ['get', feedbackProperty(activity)]
	return [
		'case',
		['has', feedbackProperty(activity)],
		['interpolate', ['linear'], net, -1, colors.bad, 0, colors.mixed, 1, colors.good],
		colors.plain,
	]
}

/** The names of the scores that hold a number on at least one edge, sorted. */
export function scoreNames(graph: Graph): string[] {
	const names = new Set<string>()
	for (const edge of graph.edges.features) {
		for (const [name, value] of Object.entries(edge.properties.scores)) {
			if (isScore(value)) names.add(name)
		}
	}
	return [...names].sort()
}

export function scoreRange(graph: Graph, name: string): ScoreRange | null {
	const values = graph.edges.features.map((edge) => edge.properties.scores[name]).filter(isScore)
	if (values.length === 0) return null
	return { min: Math.min(...values), max: Math.max(...values) }
}

// Shares of the corridor around an edge, so a colour means the same share in every view.
const FIXED_SCALES: Record<string, ScoreRange> = {
	green: { min: 0, max: 1 },
	nature: { min: 0, max: 1 },
	water: { min: 0, max: 1 },
	prepared: { min: 0, max: 1 },
}

export const isFixedScale = (name: string) => Object.hasOwn(FIXED_SCALES, name)

// A share ends in the colour of the layer it measures, so edges match the areas around them.
const SCORE_TOKENS: Record<string, string> = {
	green: '--map-park',
	nature: '--map-nature',
	water: '--map-water',
}

export const scoreToken = (name: string) =>
	(Object.hasOwn(SCORE_TOKENS, name) ? SCORE_TOKENS[name] : undefined) ?? '--map-score-high'

/** The range to colour a score over: fixed for shares, else the values in view. */
export function colorScale(graph: Graph, name: string): ScoreRange | null {
	const range = scoreRange(graph, name)
	return range && (FIXED_SCALES[name] ?? range)
}

export function scoredCount(graph: Graph, name: string): number {
	return graph.edges.features.filter((edge) => isScore(edge.properties.scores[name])).length
}

/** A line colour: plain, or from low to high over the range of one score. */
export function edgeColor(
	name: string | null,
	range: ScoreRange | null,
	colors: EdgeColors,
): ExpressionSpecification | string {
	if (name === null || range === null) return colors.plain
	const score: ExpressionSpecification = ['get', scoreProperty(name)]
	// interpolate needs rising stops, so one value for every edge gets one colour
	const scored: ExpressionSpecification | string =
		range.min === range.max
			? colors.high
			: ['interpolate', ['linear'], score, range.min, colors.low, range.max, colors.high]
	return ['case', ['has', scoreProperty(name)], scored, colors.plain]
}
