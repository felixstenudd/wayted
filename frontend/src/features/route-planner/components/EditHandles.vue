<script setup lang="ts">
import { Undo2 } from '@lucide/vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { MapMarker, type LonLat } from '@/features/map'
import { Button } from '@/shared/ui/button'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '@/shared/ui/popover'

defineProps<{
	/** Where earlier drags of the line came onto a road. */
	handles: readonly LonLat[]
	/** On a touch screen, the spot of the line last tapped, ready to be dragged. */
	tapped: LonLat | null
}>()
const emit = defineEmits<{
	move: [index: number, to: LonLat]
	remove: [index: number]
	dragTapped: [to: LonLat]
}>()

// A drag ends with a click on the handle; that click should not open its menu.
const CLICK_AFTER_DRAG_MS = 300

const { t } = useI18n()
const openIndex = ref<number | null>(null)
let movedAt = 0

function move(index: number, to: LonLat): void {
	movedAt = Date.now()
	emit('move', index, to)
}

function setOpen(index: number, open: boolean): void {
	if (open && Date.now() - movedAt < CLICK_AFTER_DRAG_MS) return
	openIndex.value = open ? index : null
}
</script>

<template>
	<MapMarker
		v-for="(handle, index) in handles"
		:key="`${handle.lon},${handle.lat}`"
		:lon-lat="handle"
		control
		draggable
		@move="move(index, $event)"
	>
		<Popover :open="openIndex === index" @update:open="setOpen(index, $event)">
			<PopoverTrigger as-child>
				<button
					type="button"
					class="grid size-11 cursor-grab place-items-center rounded-full"
					:aria-label="t('planner.edit.handle', { n: index + 1 })"
				>
					<span
						class="size-4 rounded-full border-2 border-overprint-contrast bg-overprint"
					/>
				</button>
			</PopoverTrigger>
			<PopoverContent class="w-auto p-1">
				<PopoverClose as-child>
					<Button variant="ghost" size="sm" @click="emit('remove', index)">
						<Undo2 />
						{{ t('planner.edit.removeChange') }}
					</Button>
				</PopoverClose>
			</PopoverContent>
		</Popover>
	</MapMarker>
	<MapMarker
		v-if="tapped"
		:key="`tapped-${tapped.lon},${tapped.lat}`"
		:lon-lat="tapped"
		:label="t('planner.edit.tapped')"
		draggable
		@move="emit('dragTapped', $event)"
	>
		<span class="grid size-11 place-items-center">
			<span class="size-5 rounded-full border-2 border-overprint-contrast bg-overprint" />
		</span>
	</MapMarker>
</template>
