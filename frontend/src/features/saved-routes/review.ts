import type { components } from '@/shared/api'

export type Answer = components['schemas']['Answer']
export type PreferenceChange = components['schemas']['PreferenceChangeOut']

/** The three answers in the order they are shown: less, about right, more. */
export const ANSWERS = [
	{ value: -1, key: 'less' },
	{ value: 0, key: 'aboutRight' },
	{ value: 1, key: 'more' },
] as const satisfies readonly { value: Answer; key: string }[]

export function changeKind({ before, after }: PreferenceChange): 'raised' | 'lowered' | 'atEnd' {
	if (after > before) return 'raised'
	if (after < before) return 'lowered'
	return 'atEnd'
}

/** The answers to send: rows left unanswered are left out. */
export function answeredOnly(answers: Record<string, Answer | null>): Record<string, Answer> {
	return Object.fromEntries(
		Object.entries(answers).filter((entry): entry is [string, Answer] => entry[1] !== null),
	)
}

/** Where a weight sits on the planner's slider, from avoid (0) to prefer (100). */
export const sliderPercent = (weight: number) => Math.round(((weight + 1) / 2) * 100)
