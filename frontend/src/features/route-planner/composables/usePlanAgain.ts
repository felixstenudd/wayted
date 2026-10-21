import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSavedRoute } from '@/features/saved-routes'
import { ApiError } from '@/shared/api'

import { planOf } from '../planAgain'
import { usePlannerStore } from '../store'
import { useShownRoute } from './useShownRoute'

export type PlanAgainStage = 'loading' | 'confirm' | 'missing' | 'failed'

/**
 * Planning a saved route again, asked for with ?from=<route id>: loads it into the planner and
 * finds routes, but asks first if that would throw away a route the user has not saved.
 */
export function usePlanAgain() {
	const route = useRoute()
	const router = useRouter()
	const planner = usePlannerStore()
	const { shown } = useShownRoute()

	const fromId = computed(() => {
		const id = Number(route.query.from)
		return Number.isInteger(id) && id > 0 ? id : null
	})
	const saved = useSavedRoute(
		() => fromId.value ?? 0,
		() => fromId.value !== null,
	)
	// Judged when the saved route arrives, before it replaces anything.
	const hasUnsaved = ref(false)

	const isShownSaved = () =>
		planner.saved !== null &&
		shown.value !== null &&
		planner.saved.edges === JSON.stringify(shown.value.properties.edges)

	function forget(): void {
		void router.replace({ query: {} })
	}

	function load(): void {
		const plan = saved.data.value ? planOf(saved.data.value) : null
		if (plan) planner.loadPlan(plan)
		forget()
	}

	watch(
		() => saved.data.value,
		(data) => {
			if (!data || fromId.value === null) return
			hasUnsaved.value = shown.value !== null && !isShownSaved()
			if (!hasUnsaved.value) load()
		},
		{ immediate: true },
	)

	const stage = computed<PlanAgainStage | null>(() => {
		if (fromId.value === null) return null
		if (saved.isError.value) {
			return saved.error.value instanceof ApiError && saved.error.value.status === 404
				? 'missing'
				: 'failed'
		}
		if (!saved.data.value) return 'loading'
		return hasUnsaved.value ? 'confirm' : null
	})

	return { stage, name: computed(() => saved.data.value?.name ?? ''), load, forget }
}
