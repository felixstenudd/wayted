import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** Junction indexes of a stretch; null until that end is placed. */
export interface StretchEnds {
	start: number | null
	end: number | null
}

/** What the panel and the map share while looking at saved routes. */
export const useSavedRoutesStore = defineStore('saved-routes', () => {
	// which saved route the list points at, so the map can lift it out of the others
	const highlightedId = ref<number | null>(null)
	// which of the route's stretch reviews the list points at
	const highlightedReviewId = ref<number | null>(null)

	// A stretch review in progress: first its ends are picked, then what it was like is said.
	const stretchEnds = ref<StretchEnds | null>(null)
	const stretchStage = ref<'pick' | 'reasons'>('pick')
	// set when an existing review is changed; its stretch stays as it was
	const editingReviewId = ref<number | null>(null)
	const isPickingStretch = computed(() => stretchEnds.value !== null)

	function startPickingStretch(): void {
		stretchEnds.value = { start: null, end: null }
		stretchStage.value = 'pick'
		editingReviewId.value = null
	}

	function stopPickingStretch(): void {
		stretchEnds.value = null
		stretchStage.value = 'pick'
		editingReviewId.value = null
	}

	function setStretchEnds(ends: StretchEnds): void {
		if (stretchEnds.value) stretchEnds.value = ends
	}

	function toStretchReasons(): void {
		if (stretchEnds.value?.end != null) stretchStage.value = 'reasons'
	}

	function backToStretchPick(): void {
		if (editingReviewId.value === null) stretchStage.value = 'pick'
	}

	/** Opens an existing review, its stretch fixed, at what it was like. */
	function editStretchReview(reviewId: number, from: number, to: number): void {
		stretchEnds.value = { start: from, end: to }
		stretchStage.value = 'reasons'
		editingReviewId.value = reviewId
	}

	return {
		highlightedId,
		highlightedReviewId,
		stretchEnds,
		stretchStage,
		editingReviewId,
		isPickingStretch,
		startPickingStretch,
		stopPickingStretch,
		setStretchEnds,
		toStretchReasons,
		backToStretchPick,
		editStretchReview,
	}
})
