// The heights are smoothed and approximate, so a route that climbs and drops less than this in
// all reads as flat rather than as a few metres.
const FLAT_BELOW_M = 10

/** Metres rounded no finer than the heights are known: to 5 m under 100 m, else to 10 m. */
export function roundClimbM(m: number): number {
	const stepM = m < 100 ? 5 : 10
	return Math.round(m / stepM) * stepM
}

export const isFlat = (ascentM: number, descentM: number) =>
	ascentM < FLAT_BELOW_M && descentM < FLAT_BELOW_M

/** Rounded metres as a number for the locale, without the unit. */
export function formatClimbM(m: number, locale: string): string {
	return new Intl.NumberFormat(locale).format(roundClimbM(m))
}
