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
