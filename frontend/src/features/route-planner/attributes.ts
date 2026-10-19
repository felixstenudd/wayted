import { nearestDetent } from '@/shared/utils/detents'

import type { AttributeGroup, RouteAttribute } from './types'

export type WeightWord = 'avoid' | 'ratherNot' | 'dontMind' | 'niceToHave' | 'prefer'

const WORDS = new Map<number, WeightWord>([
	[-1, 'avoid'],
	[-0.5, 'ratherNot'],
	[0, 'dontMind'],
	[0.5, 'niceToHave'],
	[1, 'prefer'],
])
export const WEIGHT_DETENTS = [...WORDS.keys()]

/** The word for a weight: the name of the nearest detent. */
export function weightWord(weight: number): WeightWord {
	return WORDS.get(nearestDetent(weight, WEIGHT_DETENTS)) ?? 'dontMind'
}

/** Attributes by group, groups in the order they first appear. */
export function groupAttributes(
	attributes: readonly RouteAttribute[],
): { group: AttributeGroup; attributes: RouteAttribute[] }[] {
	const groups = new Map<AttributeGroup, RouteAttribute[]>()
	for (const attribute of attributes) {
		groups.set(attribute.group, [...(groups.get(attribute.group) ?? []), attribute])
	}
	return [...groups].map(([group, members]) => ({ group, attributes: members }))
}

/** A readable name for a key the app has no translation for yet, so a new attribute still shows. */
export function humanizeKey(key: string): string {
	const words = key.replaceAll('_', ' ')
	return words.charAt(0).toUpperCase() + words.slice(1)
}
