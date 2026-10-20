import { watch } from 'vue'

import { useStoredPreferences } from '../api'
import { usePlannerStore } from '../store'

/** Loads the user's stored weights into the planner, now and whenever they change. */
export function usePlannerDefaults() {
	const planner = usePlannerStore()
	const stored = useStoredPreferences()
	watch(
		() => stored.data.value,
		(preferences) => {
			if (preferences) planner.receiveDefaults(preferences.weights)
		},
		{ immediate: true },
	)
	return stored
}
