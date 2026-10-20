export type ScoreWord = 'none' | 'aLittle' | 'some' | 'aLot' | 'mostly'

export interface AttributeScore {
	mean: number
	coverage: number
}

export interface ProfileRow extends AttributeScore {
	key: string
	/** The weight the route was planned with; 0 when the attribute did not matter. */
	weight: number
}

// Below this share of the route with a known score, the profile says how much is known.
const COVERAGE_NOTE_BELOW = 0.9

/** A score in words, so it reads without a number to interpret. */
export function scoreWord(mean: number): ScoreWord {
	if (mean < 0.05) return 'none'
	if (mean < 0.25) return 'aLittle'
	if (mean < 0.5) return 'some'
	if (mean < 0.75) return 'aLot'
	return 'mostly'
}

export const needsCoverageNote = (coverage: number) => coverage < COVERAGE_NOTE_BELOW

/**
 * One row per scored attribute. What the route was planned for comes first, so it reads against
 * the weights that produced it; within each part, attributes keep the planner's order.
 */
export function profileRows(
	scores: Record<string, AttributeScore>,
	preferences: Record<string, number>,
	order: readonly string[],
): ProfileRow[] {
	const position = (key: string) => {
		const index = order.indexOf(key)
		return index === -1 ? order.length : index
	}
	return Object.entries(scores)
		.map(([key, score]) => ({ key, ...score, weight: preferences[key] ?? 0 }))
		.sort(
			(a, b) =>
				Number(b.weight !== 0) - Number(a.weight !== 0) ||
				position(a.key) - position(b.key) ||
				a.key.localeCompare(b.key),
		)
}
