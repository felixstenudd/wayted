export type ScoreWord = 'none' | 'aLittle' | 'some' | 'aLot' | 'mostly'

import type { AttributeScore } from './types'

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

/**
 * The message for a score of one attribute: its own words, such as "Mostly prepared", when it has
 * them, else the plain word.
 */
export function scoreMessage(
	attributeKey: string,
	mean: number,
	hasMessage: (path: string) => boolean,
): string {
	const word = scoreWord(mean)
	const own = `route.profile.attributeWords.${attributeKey}.${word}`
	return hasMessage(own) ? own : `route.profile.words.${word}`
}

export const needsCoverageNote = (coverage: number) => coverage < COVERAGE_NOTE_BELOW

/**
 * Attribute keys with what the route was planned for first, so a route reads against the weights
 * that produced it; within each part, keys keep the planner's order.
 */
export function plannedFirst(
	keys: readonly string[],
	preferences: Record<string, number>,
	order: readonly string[],
): string[] {
	const isWanted = (key: string) => Number((preferences[key] ?? 0) !== 0)
	const position = (key: string) => {
		const index = order.indexOf(key)
		return index === -1 ? order.length : index
	}
	return [...keys].sort(
		(a, b) => isWanted(b) - isWanted(a) || position(a) - position(b) || a.localeCompare(b),
	)
}

/** One row per scored attribute, in plannedFirst order. */
export function profileRows(
	scores: Record<string, AttributeScore>,
	preferences: Record<string, number>,
	order: readonly string[],
): ProfileRow[] {
	return plannedFirst(Object.keys(scores), preferences, order).map((key) => ({
		key,
		mean: scores[key]?.mean ?? 0,
		coverage: scores[key]?.coverage ?? 0,
		weight: preferences[key] ?? 0,
	}))
}
