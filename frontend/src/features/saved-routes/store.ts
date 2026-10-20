import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** Junction indexes of a stretch being picked; null until that end is placed. */
export interface StretchEnds {
	start: number | null
	end: number | null
}

/** What the panel and the map share while looking at saved routes. */
export const useSavedRoutesStore = defineStore('saved-routes', () => {
	// which saved route the list points at, so the map can lift it out of the others
	const highlightedId = ref<number | null>(null)
	const stretchEnds = ref<StretchEnds | null>(null)
	const isPickingStretch = computed(() => stretchEnds.value !== null)

	function startPickingStretch(): void {
		stretchEnds.value = { start: null, end: null }
	}

	function stopPickingStretch(): void {
		stretchEnds.value = null
	}

	function setStretchEnds(ends: StretchEnds): void {
		if (stretchEnds.value) stretchEnds.value = ends
	}

	return {
		highlightedId,
		stretchEnds,
		isPickingStretch,
		startPickingStretch,
		stopPickingStretch,
		setStretchEnds,
	}
})
