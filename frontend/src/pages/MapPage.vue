<script setup lang="ts">
import { computed, ref, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { AccountMenu } from '@/features/auth'
import { MapView, provideMap } from '@/features/map'
import { PlannerEssentials, PlannerPanel, PointMarkers } from '@/features/route-planner'
import { RouteLines, RoutesPanel } from '@/features/saved-routes'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { BottomSheet } from '@/shared/ui/bottom-sheet'
import { SegmentedNav } from '@/shared/ui/segmented-nav'

type Section = 'plan' | 'routes'

interface SectionParts {
	titleKey: string
	/** Takes layout: 'panel' beside the map, 'sheet' in the bottom sheet. */
	panel: Component
	/** What a phone shows at the sheet's lowest stop, under the navigation. */
	peek?: Component
	/** Drawn on the map. */
	map: Component
}

// Every section shares this page, so moving between them keeps the map as it is.
const SECTIONS: Record<Section, SectionParts> = {
	plan: {
		titleKey: 'planner.title',
		panel: PlannerPanel,
		peek: PlannerEssentials,
		map: PointMarkers,
	},
	routes: { titleKey: 'savedRoutes.title', panel: RoutesPanel, map: RouteLines },
}

// Central Stockholm until the user places a start. The URL takes over once the map has moved.
const START = { center: { lon: 18.0686, lat: 59.3293 }, zoom: 13 }

const { t } = useI18n()
const route = useRoute()
// Tailwind's md breakpoint: from here the panel floats beside the map instead of a sheet.
const hasRoomForPanel = useMediaQuery('(min-width: 48rem)')
const sheetStop = ref(0)
const sheetHeightPx = ref(0)

const section = computed<Section>(() => (route.name === 'routes' ? 'routes' : 'plan'))
const parts = computed(() => SECTIONS[section.value])
const navItems = computed(() => [
	{ value: 'plan' as const, label: t('nav.plan'), to: { name: 'planner' } },
	{ value: 'routes' as const, label: t('nav.routes'), to: { name: 'routes' } },
])

provideMap()
</script>

<template>
	<!-- In tab order: account, then the panel, then the map. The map is drawn underneath. -->
	<main class="relative h-dvh overflow-hidden">
		<div class="absolute top-4 right-4 z-10">
			<AccountMenu />
		</div>
		<div
			v-if="hasRoomForPanel"
			class="pointer-events-none absolute inset-y-4 left-4 z-10 flex w-90 flex-col"
		>
			<aside
				:aria-label="t(parts.titleKey)"
				class="pointer-events-auto max-h-full overflow-y-auto overscroll-contain rounded-lg bg-paper shadow-float"
			>
				<div class="px-5 pt-5">
					<SegmentedNav :label="t('nav.label')" :items="navItems" :current="section" />
				</div>
				<component :is="parts.panel" layout="panel" />
			</aside>
		</div>
		<BottomSheet
			v-else
			v-model:stop="sheetStop"
			:label="t(parts.titleKey)"
			:expand-label="t('planner.sheet.expand')"
			:collapse-label="t('planner.sheet.collapse')"
			:peek-rem="13"
			@height="sheetHeightPx = $event"
		>
			<template #header>
				<div class="flex flex-col gap-4">
					<SegmentedNav :label="t('nav.label')" :items="navItems" :current="section" />
					<component :is="parts.peek" v-if="parts.peek" />
				</div>
			</template>
			<component :is="parts.panel" layout="sheet" />
		</BottomSheet>
		<MapView
			:center="START.center"
			:zoom="START.zoom"
			keep-view-in-url
			zoom-buttons-position="bottom-right"
			:controls-bottom-px="hasRoomForPanel ? 0 : sheetHeightPx"
		/>
		<component :is="parts.map" />
	</main>
</template>
