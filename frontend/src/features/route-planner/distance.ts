import type { Activity } from './types'

/** How far the − and + buttons move the target distance. */
export const STEP_KM: Record<Activity, number> = { running: 1, cycling: 5 }

/** A typed distance in km, or null when it is not one. Takes a decimal comma and a "km" unit. */
export function parseDistanceKm(text: string): number | null {
	const number = text
		.trim()
		.replace(/\s*km$/i, '')
		.replace(',', '.')
	if (!/^\d+(\.\d+)?$/.test(number)) return null
	const km = Number(number)
	return km > 0 ? km : null
}

export function formatKm(km: number): string {
	return String(Math.round(km * 10) / 10)
}

/** The next multiple of stepKm from km in a direction, so 10.5 steps to 11 or 10. */
export function steppedKm(km: number, stepKm: number, direction: 1 | -1): number {
	return direction === 1
		? Math.floor(km / stepKm) * stepKm + stepKm
		: Math.ceil(km / stepKm) * stepKm - stepKm
}
