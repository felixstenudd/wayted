<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { MapMarker, type LonLat } from '@/features/map'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { CourseSymbol } from '@/shared/ui/course-symbol'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/ui/popover'

import { formatKm } from '../distance'
import { useThroughPointNumbers } from '../composables/useThroughPointNumbers'
import { usePlannerStore } from '../store'
import { soonOrder } from '../throughPoints'
import type { ThroughPoint } from '../types'
import ThroughPointSettings from './ThroughPointSettings.vue'

// A drag ends with a click on the marker; that click should not open its settings.
const CLICK_AFTER_DRAG_MS = 300

const i18n = useI18n()
const { t } = i18n
const planner = usePlannerStore()
const { numbers, nameOf } = useThroughPointNumbers()
// Tailwind's md breakpoint, as the page uses: below it the settings open in the sheet.
const hasRoomForPopover = useMediaQuery('(min-width: 48rem)')

const soon = computed(() => soonOrder(planner.throughPoints))
const ordinals = computed(() => new Intl.PluralRules(i18n.locale.value, { type: 'ordinal' }))
let movedAt = 0

/** What a point's placement says next to it on the map; nothing when it goes wherever it fits. */
function tag(point: ThroughPoint): string | null {
	if (point.placement.at === 'after') {
		return t('planner.points.through.afterTag', { km: formatKm(point.placement.afterKm) })
	}
	const turn = soon.value.get(point.id)
	if (turn === undefined) return null
	return t(`planner.points.through.soonTag.${ordinals.value.select(turn)}`, { n: turn })
}

function move(id: number, to: LonLat): void {
	movedAt = Date.now()
	planner.moveThroughPoint(id, to)
}

function setOpen(id: number, open: boolean): void {
	if (open && Date.now() - movedAt < CLICK_AFTER_DRAG_MS) return
	if (open) planner.editThroughPoint(id)
	else if (planner.editingThroughPointId === id) planner.editThroughPoint(null)
}
</script>

<template>
	<MapMarker
		v-for="(point, index) in planner.throughPoints"
		:key="point.id"
		:lon-lat="point.lonLat"
		control
		draggable
		@move="move(point.id, $event)"
	>
		<Popover
			:open="hasRoomForPopover && planner.editingThroughPointId === point.id"
			@update:open="setOpen(point.id, $event)"
		>
			<PopoverTrigger as-child>
				<button
					type="button"
					class="relative flex cursor-grab rounded-full"
					:aria-label="t('planner.points.through.change', { name: nameOf(point.id) })"
				>
					<CourseSymbol
						kind="control"
						:control-number="numbers[index]"
						class="size-6 sm:size-7"
					/>
					<span
						v-if="tag(point)"
						class="absolute top-1/2 left-full ml-1 -translate-y-1/2 rounded-full border border-line-strong bg-paper px-2 py-0.5 text-caption whitespace-nowrap text-ink"
						aria-hidden="true"
					>
						{{ tag(point) }}
					</span>
				</button>
			</PopoverTrigger>
			<PopoverContent
				aria-labelledby="through-point-popover-title"
				class="flex flex-col gap-3"
			>
				<h2 id="through-point-popover-title" class="text-title">{{ nameOf(point.id) }}</h2>
				<ThroughPointSettings
					:point="point"
					title-id="through-point-popover-title"
					id-prefix="through-point-popover"
				/>
			</PopoverContent>
		</Popover>
	</MapMarker>
</template>
