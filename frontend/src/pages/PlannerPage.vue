<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { AccountMenu } from '@/features/auth'
import { MapView, provideMap } from '@/features/map'
import { PlannerPanel } from '@/features/route-planner'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { BottomSheet } from '@/shared/ui/bottom-sheet'

// Central Stockholm until the user places a start. The URL takes over once the map has moved.
const START = { center: { lon: 18.0686, lat: 59.3293 }, zoom: 13 }

const { t } = useI18n()
// Tailwind's md breakpoint: from here the panel floats beside the map instead of a sheet.
const hasRoomForPanel = useMediaQuery('(min-width: 48rem)')
const sheetStop = ref(0)
const sheetHeightPx = ref(0)

provideMap()
</script>

<template>
	<main class="relative h-dvh overflow-hidden">
		<MapView
			:center="START.center"
			:zoom="START.zoom"
			keep-view-in-url
			zoom-buttons-position="bottom-right"
			:controls-bottom-px="hasRoomForPanel ? 0 : sheetHeightPx"
		/>
		<div class="absolute top-4 right-4">
			<AccountMenu />
		</div>
		<div
			v-if="hasRoomForPanel"
			class="pointer-events-none absolute inset-y-4 left-4 flex w-90 flex-col"
		>
			<aside
				:aria-label="t('planner.title')"
				class="pointer-events-auto max-h-full overflow-y-auto overscroll-contain rounded-lg bg-paper p-5 shadow-float"
			>
				<PlannerPanel />
			</aside>
		</div>
		<BottomSheet
			v-else
			v-model:stop="sheetStop"
			:label="t('planner.title')"
			:expand-label="t('planner.sheet.expand')"
			:collapse-label="t('planner.sheet.collapse')"
			@height="sheetHeightPx = $event"
		>
			<PlannerPanel />
		</BottomSheet>
	</main>
</template>
