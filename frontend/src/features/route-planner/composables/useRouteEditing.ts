import type { LonLat } from '@/features/map'

import { useReroute, useRerouteRequest } from '../api'
import { editError } from '../editError'
import { usePlannerStore } from '../store'
import type { RerouteAnswer } from '../types'
import { useShownRoute } from './useShownRoute'

type NextHandles = (handles: LonLat[], handle: LonLat | null) => LonLat[]

const addHandle: NextHandles = (handles, handle) => (handle ? [...handles, handle] : handles)

/**
 * Edits of the shown route: dragging its line to a road, moving a handle such a drag left, and
 * taking one back out. Each sends the route as it is now, so later edits build on earlier ones.
 */
export function useRouteEditing() {
	const planner = usePlannerStore()
	const { routes, shown } = useShownRoute()
	const reroute = useReroute()
	const request = useRerouteRequest()

	function apply(answer: RerouteAnswer, nextHandles: NextHandles): void {
		const original = routes.value[planner.selectedOption]
		if (!original) return
		const handle = answer.handle
			? { lon: answer.handle.coordinates[0], lat: answer.handle.coordinates[1] }
			: null
		planner.applyEdit(original, answer.route, nextHandles([...planner.editHandles], handle))
	}

	function run(grab: LonLat, drop: LonLat | null, nextHandles: NextHandles): void {
		const route = shown.value
		// One edit at a time, so each starts from the route the last one made.
		if (!route || reroute.isPending.value) return
		planner.setEditError(null)
		reroute.mutate(
			{ route, grab, drop },
			{
				onSuccess: (answer) => apply(answer, nextHandles),
				onError: (error) => planner.setEditError(editError(error)),
			},
		)
	}

	/**
	 * A drag of the line from grab to drop, which leaves a handle where it came onto the road.
	 * previewed is what a preview already got for that drop, which is taken as it is.
	 */
	function dragLine(grab: LonLat, drop: LonLat, previewed: RerouteAnswer | null = null): void {
		if (previewed && !reroute.isPending.value) {
			planner.setEditError(null)
			apply(previewed, addHandle)
		} else run(grab, drop, addHandle)
	}

	/** What a drag of the line to drop would make, without making it. */
	function previewDrag(grab: LonLat, drop: LonLat): Promise<RerouteAnswer> {
		const route = shown.value
		return route ? request({ route, grab, drop }) : Promise.reject(new Error('No route shown.'))
	}

	function moveHandle(index: number, to: LonLat): void {
		const handle = planner.editHandles[index]
		if (handle) {
			run(handle, to, (handles, moved) =>
				moved ? handles.map((h, i) => (i === index ? moved : h)) : handles,
			)
		}
	}

	/**
	 * Takes a handle's change back out: the last one is undone exactly; an earlier one has its
	 * stretch routed again without it, since the edits after it were made on top of it.
	 */
	function removeHandle(index: number): void {
		const handles = planner.editHandles
		const handle = handles[index]
		if (!handle) return
		if (index === handles.length - 1) planner.undoEdit()
		else run(handle, null, (current) => current.filter((_, i) => i !== index))
	}

	return { dragLine, previewDrag, moveHandle, removeHandle, isPending: reroute.isPending }
}
