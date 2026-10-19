<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'

import { useDetentPointer } from '@/shared/composables/useDetentPointer'
import { nextDetent, roundToHundredth } from '@/shared/utils/detents'

// A slider from -1 to 1 with "neither" in the middle. It fills outward from the
// middle, so a slider left at its default does not look partly switched on.
const props = withDefaults(
	defineProps<{
		/** Names the slider for screen readers. */
		label: string
		/** The value in words, read out instead of the number. */
		valueText: string
		disabled?: boolean
		detents?: readonly number[]
	}>(),
	{ disabled: false, detents: () => [-1, -0.5, 0, 0.5, 1] },
)
const value = defineModel<number>({ required: true })

const FINE_STEP = 0.01
// Ruler marks shown while fine-tuning, every 0.1.
const RULER = Array.from({ length: 21 }, (_, index) => roundToHundredth(index / 10 - 1))

const track = useTemplateRef<HTMLElement>('track')
const pointer = useDetentPointer(
	props.detents,
	value,
	() => track.value?.getBoundingClientRect() ?? null,
)

const percent = (at: number) => `${((at + 1) / 2) * 100}%`
const fill = computed(() => ({
	left: percent(Math.min(value.value, 0)),
	width: `${(Math.abs(value.value) / 2) * 100}%`,
}))

function set(next: number): void {
	value.value = roundToHundredth(Math.min(Math.max(next, -1), 1))
}

function onKeydown(event: KeyboardEvent): void {
	if (props.disabled) return
	const direction = {
		ArrowRight: 1,
		ArrowUp: 1,
		PageUp: 1,
		ArrowLeft: -1,
		ArrowDown: -1,
		PageDown: -1,
	}[event.key] as 1 | -1 | undefined
	if (direction !== undefined) {
		set(
			event.altKey
				? value.value + direction * FINE_STEP
				: nextDetent(value.value, props.detents, direction),
		)
	} else if (event.key === 'Home') set(-1)
	else if (event.key === 'End') set(1)
	else return
	event.preventDefault()
}

function reset(): void {
	if (!props.disabled) value.value = 0
}
</script>

<template>
	<div
		data-slot="bipolar-slider"
		class="group relative h-8 touch-none px-2.5 select-none"
		:class="disabled ? 'opacity-40' : 'cursor-pointer'"
		:data-fine="pointer.isFine.value || undefined"
		@pointerdown="!disabled && pointer.onPointerDown($event)"
		@pointermove="pointer.onPointerMove"
		@pointerup="pointer.onPointerUp"
		@pointercancel="pointer.onPointerUp"
		@lostpointercapture="pointer.onLostPointerCapture"
	>
		<div ref="track" class="relative h-full">
			<div class="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line-strong" />
			<span
				v-for="detent in detents"
				:key="detent"
				class="absolute top-1/2 w-px -translate-x-1/2 -translate-y-1/2"
				:class="detent === 0 ? 'h-3 bg-ink' : 'h-1.5 bg-graphite'"
				:style="{ left: percent(detent) }"
			/>
			<span
				v-for="mark in RULER"
				:key="`ruler-${mark}`"
				class="absolute top-full h-1 w-px -translate-x-1/2 -translate-y-1.5 bg-graphite opacity-0 transition-opacity duration-150 ease-out group-data-fine:opacity-100"
				:style="{ left: percent(mark) }"
			/>
			<div
				class="absolute top-1/2 h-0.75 -translate-y-1/2 bg-ink"
				:class="{ 'transition-[left,width] duration-150 ease-out': !pointer.isFine.value }"
				:style="fill"
			/>
			<div
				role="slider"
				:tabindex="disabled ? -1 : 0"
				:aria-label="label"
				aria-valuemin="-1"
				aria-valuemax="1"
				:aria-valuenow="value"
				:aria-valuetext="valueText"
				:aria-disabled="disabled || undefined"
				aria-orientation="horizontal"
				class="group/thumb absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-paper bg-ink ring-1 ring-ink group-data-fine:scale-125"
				:class="
					pointer.isFine.value
						? 'transition-[scale] duration-150 ease-out'
						: 'transition-[left,scale] duration-150 ease-out'
				"
				:style="{ left: percent(value) }"
				@keydown="onKeydown"
				@dblclick="reset"
			>
				<!-- The value in words while the slider is in use; at rest the shared scale says it. -->
				<span
					v-if="!disabled"
					aria-hidden="true"
					class="pointer-events-none absolute bottom-full left-1/2 mb-1.5 -translate-x-1/2 rounded-sm bg-ink px-1.5 text-caption whitespace-nowrap text-paper opacity-0 transition-opacity duration-150 ease-out group-hover:opacity-100 group-focus-visible/thumb:opacity-100 group-active:opacity-100 group-data-fine:opacity-100"
				>
					{{ valueText }}
				</span>
			</div>
		</div>
	</div>
</template>
