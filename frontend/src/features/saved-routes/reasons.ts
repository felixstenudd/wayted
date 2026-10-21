import type { components } from '@/shared/api'

export type ReviewReason = components['schemas']['ReasonOut']

/** Chooses or unchooses a reason. Choosing one side of a topic drops the other side. */
export function toggleReason(
	selected: readonly string[],
	code: string,
	reasons: readonly ReviewReason[],
): string[] {
	if (selected.includes(code)) return selected.filter((c) => c !== code)
	const topic = reasons.find((r) => r.code === code)?.topic
	const sameTopic = new Set(reasons.filter((r) => r.topic === topic).map((r) => r.code))
	return [...selected.filter((c) => !sameTopic.has(c)), code]
}

export function reasonsBySide(reasons: readonly ReviewReason[]) {
	return {
		good: reasons.filter((r) => r.sentiment === 1),
		bad: reasons.filter((r) => r.sentiment === -1),
	}
}

/** What a review says was good and what was bad, each in the order the reasons are listed. */
export function reviewSides(codes: readonly string[], reasons: readonly ReviewReason[]) {
	const said = (sentiment: number) =>
		reasons
			.filter((r) => r.sentiment === sentiment && codes.includes(r.code))
			.map((r) => r.code)
	return { good: said(1), bad: said(-1) }
}

/** One word for a review on the map: it was good, bad, or some of each. */
export function reviewTone({ good, bad }: { good: readonly string[]; bad: readonly string[] }) {
	if (good.length > 0 && bad.length > 0) return 'mixed'
	return bad.length > 0 ? 'bad' : 'good'
}
