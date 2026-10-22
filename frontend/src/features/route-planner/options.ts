import { scoreWord, type AttributeScore } from '@/features/route'

// The planner's plan.tolerance: within it a route has kept to its target.
const TOLERANCE = 0.07

/** A route option's name: a letter, since a number on the map means a through point. */
export function optionLetter(index: number): string {
	return String.fromCharCode('A'.charCodeAt(0) + index)
}

export type RouteFit = { kind: 'close' } | { kind: 'long' | 'short'; km: number }

/** How a route's length fits the target it was planned for; null without one. */
export function routeFit(lengthM: number, targetM: number | null | undefined): RouteFit | null {
	if (targetM === null || targetM === undefined) return null
	const offM = lengthM - targetM
	if (Math.abs(offM) <= TOLERANCE * targetM) return { kind: 'close' }
	return { kind: offM > 0 ? 'long' : 'short', km: Math.round(Math.abs(offM) / 100) / 10 }
}

/**
 * For each option, the attribute it is told apart by: one it has in other words than every other
 * option, such as "Some nature" against "No nature". One the user weighted comes first, then the
 * biggest difference. Only keys, which have words, and that every option was scored for, count.
 * Null where an option shares every word with another.
 */
export function standOut(
	options: readonly Record<string, AttributeScore>[],
	preferences: Record<string, number>,
	keys: readonly string[],
): (string | null)[] {
	const meanOf = (index: number, key: string) => options[index]?.[key]?.mean ?? 0
	const shared = keys.filter((key) => options.every((scores) => key in scores))
	return options.map((_, index) => {
		const others = options.map((_, other) => other).filter((other) => other !== index)
		const difference = (key: string) =>
			Math.abs(
				meanOf(index, key) -
					others.reduce((sum, other) => sum + meanOf(other, key), 0) / others.length,
			)
		const apart = shared.filter((key) =>
			others.every(
				(other) => scoreWord(meanOf(other, key)) !== scoreWord(meanOf(index, key)),
			),
		)
		const isWeighted = (key: string) => Number((preferences[key] ?? 0) !== 0)
		apart.sort((a, b) => isWeighted(b) - isWeighted(a) || difference(b) - difference(a))
		return apart[0] ?? null
	})
}
