<script setup lang="ts">
import { ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { AccountMenu } from '@/features/auth'
import { MapView, provideMap, type MapCover } from '@/features/map'
import { PlannerEssentials, PlannerPanel, PointMarkers, RouteLine } from '@/features/route-planner'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { BottomSheet } from '@/shared/ui/bottom-sheet'

// Central Stockholm until the user places a start. The URL takes over once the map has moved.
const START = { center: { lon: 18.0686, lat: 59.3293 }, zoom: 13 }

const { t } = useI18n()
// Tailwind's md breakpoint: from here the panel floats beside the map instead of a sheet.
const hasRoomForPanel = useMediaQuery('(min-width: 48rem)')
const sheetStop = ref(0)
const sheetHeightPx = ref(0)
const panel = useTemplateRef<HTMLElement>('panel')

// A route is fitted beside the panel, or above the sheet.
function plannerCover(): MapCover {
	if (!hasRoomForPanel.value) return { bottom: sheetHeightPx.value }
	return { left: panel.value?.getBoundingClientRect().right ?? 0 }
}

provideMap()
</script>

<template>
	<!-- In tab order: account, then the planner, then the map. The map is drawn underneath. -->
	<main class="relative h-dvh overflow-hidden">
		<div class="absolute top-4 right-4 z-10">
			<AccountMenu />
		</div>
		<div
			v-if="hasRoomForPanel"
			class="pointer-events-none absolute inset-y-4 left-4 z-10 flex w-90 flex-col"
		>
			<aside
				ref="panel"
				:aria-label="t('planner.title')"
				class="pointer-events-auto max-h-full overflow-y-auto overscroll-contain rounded-lg bg-paper shadow-float"
			>
				<PlannerPanel layout="panel" />
			</aside>
		</div>
		<BottomSheet
			v-else
			v-model:stop="sheetStop"
			:label="t('planner.title')"
			:expand-label="t('planner.sheet.expand')"
			:collapse-label="t('planner.sheet.collapse')"
			:peek-rem="13"
			@height="sheetHeightPx = $event"
		>
			<template #header>
				<PlannerEssentials />
			</template>
			<PlannerPanel layout="sheet" />
		</BottomSheet>
		<MapView
			:center="START.center"
			:zoom="START.zoom"
			keep-view-in-url
			zoom-buttons-position="bottom-right"
			:controls-bottom-px="hasRoomForPanel ? 0 : sheetHeightPx"
		/>
		<RouteLine :cover="plannerCover" />
		<PointMarkers />
	</main>
</template>
