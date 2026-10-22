import type { SavedRoute } from './types'

export type RouteInstruction = SavedRoute['instructions'][number]
export type Maneuver = RouteInstruction['maneuver']

type Translate = (path: string, params: Record<string, unknown>) => string

/**
 * The message naming a road by its highway class, for one without a name or ref: the class's
 * own, or the generic word for any other. null when the road has no class to go by.
 */
export function wayClassMessage(
	wayClass: string | null,
	hasMessage: (path: string) => boolean,
): string | null {
	if (wayClass === null) return null
	const own = `savedRoutes.turns.ways.${wayClass}`
	return hasMessage(own) ? own : 'savedRoutes.turns.ways.other'
}

/** The message for what to do, onto the road when there is one to name. A u-turn names none. */
export function maneuverMessage(maneuver: Maneuver, hasRoad: boolean): string {
	return hasRoad && maneuver !== 'u_turn'
		? `savedRoutes.turns.onto.${maneuver}`
		: `savedRoutes.turns.maneuvers.${maneuver}`
}

/** An instruction as a sentence: "Left onto Storgatan", "Roundabout, exit 2 onto path". */
export function instructionText(
	instruction: RouteInstruction,
	t: Translate,
	hasMessage: (path: string) => boolean,
): string {
	const wayClass = wayClassMessage(instruction.way_class, hasMessage)
	const road = instruction.name ?? (wayClass === null ? null : t(wayClass, {}))
	return t(maneuverMessage(instruction.maneuver, road !== null), {
		road,
		exit: instruction.exit,
	})
}
