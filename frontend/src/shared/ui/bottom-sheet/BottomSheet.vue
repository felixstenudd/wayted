<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useTemplateRef, watch } from 'vue'

import { sheetStops, useSheetDrag } from '@/shared/composables/useSheetDrag'

const props = withDefaults(
	defineProps<{
		/** Names the sheet for screen readers. */
		label: string
		expandLabel: string
		collapseLabel: string
		/** Height of the lowest stop: enough for what the sheet should always show. */
		peekRem?: number
		/** The lowest stop shows the whole header instead, however tall it grows. */
		fitHeader?: boolean
	}>(),
	{ peekRem: 9, fitHeader: false },
)
const emit = defineEmits<{ height: [px: number] }>()
/** 0 is the lowest stop, 2 the highest. */
const stop = defineModel<number>('stop', { default: 0 })

// Lowest shows a peek of the content, the middle half the screen, the highest
// leaves a strip of the screen above it so the page behind stays in sight.
const TOP_GAP_REM = 4.5
// The handle above the header.
const HANDLE_REM = 2

const viewportPx = ref(window.innerHeight)
const updateViewport = () => {
	viewportPx.value = window.innerHeight
}
window.addEventListener('resize', updateViewport)
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

const header = useTemplateRef<HTMLElement>('header')
const headerPx = ref(0)
const headerObserver = new ResizeObserver(([entry]) => {
	headerPx.value = entry?.borderBoxSize[0]?.blockSize ?? 0
})
watch(header, (element, previous) => {
	if (previous) headerObserver.unobserve(previous)
	if (element) headerObserver.observe(element)
})
onBeforeUnmount(() => headerObserver.disconnect())

const stops = computed(() => {
	const remPx = parseFloat(getComputedStyle(document.documentElement).fontSize)
	const peekPx =
		props.fitHeader && header.value
			? headerPx.value + HANDLE_REM * remPx
			: props.peekRem * remPx
	return sheetStops(peekPx, viewportPx.value, TOP_GAP_REM * remPx)
})

const { heightPx, isDragging, onPointerDown, onPointerMove, onPointerUp } = useSheetDrag(
	stops,
	stop,
)
watch(heightPx, (px) => emit('height', px), { immediate: true })

const isHighest = computed(() => stop.value === stops.value.length - 1)

let wasDrag = false
function release(event: PointerEvent): void {
	wasDrag = onPointerUp(event)
}

/** A tap, or the keyboard, steps up one stop, and from the highest back to the lowest. */
function step(): void {
	if (wasDrag) {
		wasDrag = false
		return
	}
	stop.value = isHighest.value ? 0 : stop.value + 1
}
</script>

<template>
	<section
		:aria-label="props.label"
		class="fixed inset-x-0 bottom-0 z-10 flex flex-col overflow-hidden rounded-t-lg bg-paper shadow-float"
		:class="{ 'transition-[height] duration-250 ease-out': !isDragging }"
		:style="{ height: `${heightPx}px` }"
	>
		<button
			type="button"
			:aria-label="isHighest ? props.collapseLabel : props.expandLabel"
			class="flex h-8 w-full shrink-0 cursor-grab touch-none items-center justify-center rounded-t-lg active:cursor-grabbing"
			@pointerdown="onPointerDown"
			@pointermove="onPointerMove"
			@pointerup="release"
			@pointercancel="release"
			@click="step"
		>
			<span class="h-1 w-9 rounded-full bg-line-strong" />
		</button>
		<!-- Stays in place while the content below scrolls. -->
		<div v-if="$slots.header" ref="header" class="shrink-0 px-4 pb-4">
			<slot name="header" />
		</div>
		<div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-4">
			<slot />
		</div>
	</section>
</template>
