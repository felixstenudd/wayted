import { defineStore } from 'pinia'
import { ref } from 'vue'

/** Which saved route the list points at, so the map can lift it out of the others. */
export const useSavedRoutesStore = defineStore('saved-routes', () => {
	const highlightedId = ref<number | null>(null)
	return { highlightedId }
})
