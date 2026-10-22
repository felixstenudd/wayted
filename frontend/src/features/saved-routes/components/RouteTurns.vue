<script setup lang="ts">
import {
	ArrowDownLeft,
	ArrowDownRight,
	ArrowUpLeft,
	ArrowUpRight,
	ChevronDown,
	CornerUpLeft,
	CornerUpRight,
	RotateCcw,
	Undo2,
} from '@lucide/vue'
import { computed, ref, useId, type Component } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDistanceKm } from '../format'
import { instructionText, type Maneuver, type RouteInstruction } from '../turns'

const props = defineProps<{
	instructions: RouteInstruction[]
}>()

// Arrows bend as far as the turn does; roundabouts go anticlockwise, as they do driving right.
const ICONS: Record<Maneuver, Component> = {
	slight_left: ArrowUpLeft,
	left: CornerUpLeft,
	sharp_left: ArrowDownLeft,
	slight_right: ArrowUpRight,
	right: CornerUpRight,
	sharp_right: ArrowDownRight,
	u_turn: Undo2,
	roundabout: RotateCcw,
}

const i18n = useI18n()
const { t, locale } = i18n
// Collapsed: the list is long, and most only want it now and then.
const isOpen = ref(false)
const contentId = useId()

const rows = computed(() =>
	props.instructions.map((instruction) => ({
		seq: instruction.seq,
		icon: ICONS[instruction.maneuver],
		text: t('savedRoutes.turns.row', {
			km: formatDistanceKm(instruction.distance_m, locale.value),
			instruction: instructionText(instruction, t, (path) => i18n.te(path)),
		}),
	})),
)
</script>

<template>
	<section class="flex flex-col gap-2">
		<h2>
			<button
				type="button"
				class="flex w-full items-center justify-between gap-2 rounded-sm text-left text-title"
				:aria-expanded="isOpen"
				:aria-controls="contentId"
				@click="isOpen = !isOpen"
			>
				{{ t('savedRoutes.turns.title', { count: instructions.length }) }}
				<ChevronDown
					class="size-4 shrink-0 text-graphite motion-safe:transition-transform"
					:class="{ '-rotate-90': !isOpen }"
					aria-hidden="true"
				/>
			</button>
		</h2>
		<ol v-show="isOpen" :id="contentId" class="flex flex-col gap-2">
			<li v-for="row in rows" :key="row.seq" class="flex items-start gap-2 text-small">
				<component
					:is="row.icon"
					class="mt-0.5 size-4 shrink-0 text-graphite"
					aria-hidden="true"
				/>
				<span class="min-w-0 flex-1">{{ row.text }}</span>
			</li>
		</ol>
	</section>
</template>
