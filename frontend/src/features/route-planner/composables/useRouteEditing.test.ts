import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, ref } from 'vue'

import type { RerouteInput } from '../api'
import { usePlannerStore } from '../store'
import type { RerouteAnswer, Route } from '../types'
import { useRouteEditing } from './useRouteEditing'

interface Sent {
	input: RerouteInput
	onSuccess: (answer: RerouteAnswer) => void
}

const found = ref<Route[]>([])
const sent: Sent[] = []
const isPending = ref(false)

vi.mock('../api', () => ({
	useReroute: () => ({
		isPending,
		mutate: (input: RerouteInput, callbacks: Pick<Sent, 'onSuccess'>) => {
			isPending.value = true
			sent.push({ input, ...callbacks })
		},
	}),
	useRerouteRequest: () => (input: RerouteInput) =>
		Promise.resolve(answer(line(input.drop ?? input.grab))),
}))
vi.mock('./useShownRoute', () => ({
	useShownRoute: () => {
		const planner = usePlannerStore()
		const routes = computed(() => found.value)
		const shown = computed(() =>
			planner.edit?.option === planner.selectedOption
				? planner.editedRoute
				: (found.value[planner.selectedOption] ?? null),
		)
		return { routes, shown }
	},
}))

// Streets in Umeå running east, each about 100 m apart.
const row = (lat: number): [number, number][] => [
	[20.25, lat],
	[20.27, lat],
]
const line = (through: { lat: number }) => row(through.lat)
const route = (coordinates: [number, number][]): Route => ({
	type: 'Feature',
	geometry: { type: 'LineString', coordinates },
	properties: {
		length_m: 1_000,
		scores: {},
		reused_m: 0,
		ascent_m: null,
		descent_m: null,
		warnings: [],
		edges: [],
		waypoint_order: [],
	},
})
function answer(coordinates: [number, number][], handleLat?: number): RerouteAnswer {
	return {
		route: route(coordinates),
		handle: handleLat === undefined ? null : { type: 'Point', coordinates: [20.26, handleLat] },
		before_m: handleLat === undefined ? null : 400,
		after_m: handleLat === undefined ? null : 600,
	}
}

function answerLast(next: RerouteAnswer): void {
	isPending.value = false
	sent.at(-1)?.onSuccess(next)
}

const GRAB = { lon: 20.26, lat: 63.82 }

beforeEach(() => {
	setActivePinia(createPinia())
	found.value = [route(row(63.82)), route(row(63.83))]
	sent.length = 0
	isPending.value = false
	const planner = usePlannerStore()
	planner.start = { lon: 20.25, lat: 63.82 }
	planner.findRoutes()
})

describe('useRouteEditing', () => {
	it('lets an answer go once the route it was asked for is no longer shown', () => {
		const planner = usePlannerStore()
		const editing = useRouteEditing()

		editing.dragLine(GRAB, { lon: 20.26, lat: 63.821 })
		planner.selectOption(1)
		answerLast(answer(row(63.821), 63.821))

		expect(planner.edit).toBeNull()
	})

	it('takes a preview only when it was made from the route shown', async () => {
		const planner = usePlannerStore()
		const editing = useRouteEditing()
		const preview = await editing.previewDrag(GRAB, { lon: 20.26, lat: 63.821 })

		planner.selectOption(1)
		editing.dragLine(GRAB, { lon: 20.26, lat: 63.831 }, preview)

		expect(planner.edit).toBeNull()
		expect(sent).toHaveLength(1)
	})

	it('drops the handles an edit routed away from', () => {
		const planner = usePlannerStore()
		const editing = useRouteEditing()
		editing.dragLine(GRAB, { lon: 20.26, lat: 63.821 })
		answerLast(
			answer(
				[
					[20.25, 63.82],
					[20.26, 63.821],
					[20.27, 63.82],
				],
				63.821,
			),
		)

		editing.dragLine(GRAB, { lon: 20.26, lat: 63.819 })
		answerLast(
			answer(
				[
					[20.25, 63.82],
					[20.26, 63.819],
					[20.27, 63.82],
				],
				63.819,
			),
		)

		expect(planner.editHandles.map((handle) => handle.at.lat)).toEqual([63.819])
	})

	it('takes a change out over the whole stretch it moved', () => {
		const planner = usePlannerStore()
		const editing = useRouteEditing()
		// North a block, and then a block more, on one street running north.
		const detour: [number, number][] = [
			[20.25, 63.82],
			[20.26, 63.821],
			[20.26, 63.822],
			[20.27, 63.82],
		]
		editing.dragLine(GRAB, { lon: 20.26, lat: 63.821 })
		answerLast(answer(detour, 63.821))
		editing.dragLine({ lon: 20.262, lat: 63.82 }, { lon: 20.26, lat: 63.822 })
		answerLast(answer(detour, 63.822))
		expect(planner.editHandles).toHaveLength(2)

		editing.removeHandle(0)

		expect(sent.at(-1)?.input).toMatchObject({
			grab: { lon: 20.26, lat: 63.821 },
			drop: null,
			reach: { beforeM: 400, afterM: 600 },
		})
	})
})
