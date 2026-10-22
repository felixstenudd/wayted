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

type Translate = (key: string, named: Record<string, string>) => string

/**
 * The climb as a route's length is followed by it: "120 m up, 115 m down", or "Flat". Null while
 * the heights are not known, which is nothing the user can fix, so it is left out.
 */
export function climbText(
	ascentM: number | null | undefined,
	descentM: number | null | undefined,
	t: Translate,
	locale: string,
): string | null {
	if (ascentM == null || descentM == null) return null
	if (isFlat(ascentM, descentM)) return t('route.climb.flat', {})
	return t('route.climb.upDown', {
		up: formatClimbM(ascentM, locale),
		down: formatClimbM(descentM, locale),
	})
}
