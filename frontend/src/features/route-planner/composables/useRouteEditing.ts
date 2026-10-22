import { distanceToLineM, type LonLat } from '@/features/map'

import { useReroute, useRerouteRequest } from '../api'
import { editError } from '../editError'
import { usePlannerStore } from '../store'
import type { EditHandle, EditReach, RerouteAnswer, Route } from '../types'
import { useShownRoute } from './useShownRoute'

// A handle further than this from the route an edit made was routed away from by that edit.
const ON_ROUTE_M = 10

type NextHandles = (handles: EditHandle[], handle: EditHandle | null) => EditHandle[]

const addHandle: NextHandles = (handles, handle) => (handle ? [...handles, handle] : handles)

/** What a preview of a drag got, and the route it was asked for. */
export interface DragPreview {
	base: Route
	answer: RerouteAnswer
}

/**
 * Edits of the shown route: dragging its line to a road, moving a handle such a drag left, and
 * taking one back out. Each sends the route as it is now, so later edits build on earlier ones.
 */
export function useRouteEditing() {
	const planner = usePlannerStore()
	const { routes, shown } = useShownRoute()
	const reroute = useReroute()
	const request = useRerouteRequest()

	function apply(base: Route, answer: RerouteAnswer, nextHandles: NextHandles): void {
		const original = routes.value[planner.selectedOption]
		// After Undo or a switch of option the answer is for a route no longer shown.
		if (!original || shown.value !== base) return
		const handle = answer.handle
			? {
					at: { lon: answer.handle.coordinates[0], lat: answer.handle.coordinates[1] },
					beforeM: answer.before_m ?? 0,
					afterM: answer.after_m ?? 0,
				}
			: null
		const line = answer.route.geometry.coordinates
		const handles = nextHandles([...planner.editHandles], handle).filter(
			(kept) => distanceToLineM(kept.at, line) <= ON_ROUTE_M,
		)
		planner.applyEdit(original, answer.route, handles)
	}

	function run(
		grab: LonLat,
		drop: LonLat | null,
		reach: EditReach | null,
		nextHandles: NextHandles,
	): void {
		const route = shown.value
		// One edit at a time, so each starts from the route the last one made.
		if (!route || reroute.isPending.value) return
		planner.setEditError(null)
		reroute.mutate(
			{ route, grab, drop, reach },
			{
				onSuccess: (answer) => apply(route, answer, nextHandles),
				onError: (error) => {
					if (shown.value === route) planner.setEditError(editError(error))
				},
			},
		)
	}

	/**
	 * A drag of the line from grab to drop, which leaves a handle where it came onto the road.
	 * previewed is what a preview already got for that drop, which is taken as it is.
	 */
	function dragLine(grab: LonLat, drop: LonLat, previewed: DragPreview | null = null): void {
		if (previewed?.base === shown.value && !reroute.isPending.value) {
			planner.setEditError(null)
			apply(previewed.base, previewed.answer, addHandle)
		} else run(grab, drop, null, addHandle)
	}

	/** What a drag of the line to drop would make, without making it. */
	function previewDrag(grab: LonLat, drop: LonLat): Promise<DragPreview> {
		const base = shown.value
		if (!base) return Promise.reject(new Error('No route shown.'))
		return request({ route: base, grab, drop }).then((answer) => ({ base, answer }))
	}

	/** Moves a handle: its change is made again through the new spot, over the stretch it moved. */
	function moveHandle(index: number, to: LonLat): void {
		const handle = planner.editHandles[index]
		if (handle) {
			run(handle.at, to, handle, (handles, moved) =>
				moved ? handles.map((h, i) => (i === index ? moved : h)) : handles,
			)
		}
	}

	/**
	 * Takes a handle's change back out: the last one is undone exactly; an earlier one has the
	 * stretch it moved routed again without it, since the edits after it were made on top of it.
	 */
	function removeHandle(index: number): void {
		const handles = planner.editHandles
		const handle = handles[index]
		if (!handle) return
		if (index === handles.length - 1) planner.undoEdit()
		else run(handle.at, null, handle, (current) => current.filter((_, i) => i !== index))
	}

	return { dragLine, previewDrag, moveHandle, removeHandle, isPending: reroute.isPending }
}
