import type { ExpressionSpecification } from 'maplibre-gl'

import type { Graph } from '../../dev-api/types'

export interface ScoreRange {
	min: number
	max: number
}

export interface EdgeColors {
	plain: string
	low: string
	high: string
}

const scoreProperty = (name: string) => `score:${name}`
const isScore = (value: unknown): value is number =>
	typeof value === 'number' && Number.isFinite(value)

/** Flat features for the map: the id, and each numeric score as its own property. */
export function toMapEdges(graph: Graph) {
	return {
		type: 'FeatureCollection' as const,
		features: graph.edges.features.map(({ geometry, properties }) => {
			const flat: Record<string, number> = { id: properties.id }
			for (const [name, value] of Object.entries(properties.scores)) {
				if (isScore(value)) flat[scoreProperty(name)] = value
			}
			return { type: 'Feature' as const, geometry, properties: flat }
		}),
	}
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
