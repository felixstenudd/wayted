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

/** How many good and bad things a review says. */
export function voteCounts(codes: readonly string[], reasons: readonly ReviewReason[]) {
	const sentiments = codes.map((code) => reasons.find((r) => r.code === code)?.sentiment)
	return {
		up: sentiments.filter((s) => s === 1).length,
		down: sentiments.filter((s) => s === -1).length,
	}
}
