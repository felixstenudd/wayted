<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { AccountMenu } from '@/features/auth'
import { MapView, provideMap } from '@/features/map'
import {
	PlannerEssentials,
	PlannerMap,
	PlannerPanel,
	usePlannerStore,
} from '@/features/route-planner'
import {
	RouteCourse,
	RouteDetailPanel,
	RouteLines,
	RoutesPanel,
	useSavedRoutesStore,
} from '@/features/saved-routes'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { BottomSheet } from '@/shared/ui/bottom-sheet'
import { SegmentedNav } from '@/shared/ui/segmented-nav'

type Section = 'plan' | 'routes' | 'route'

interface SectionParts {
	titleKey: string
	/** Where the switch at the top stands. */
	nav: 'plan' | 'routes'
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
		nav: 'plan',
		panel: PlannerPanel,
		peek: PlannerEssentials,
		map: PlannerMap,
	},
	routes: { titleKey: 'savedRoutes.title', nav: 'routes', panel: RoutesPanel, map: RouteLines },
	route: {
		titleKey: 'savedRoutes.detail.title',
		nav: 'routes',
		panel: RouteDetailPanel,
		map: RouteCourse,
	},
}

// The floating panel: left-4 plus w-90, in rem.
const PANEL_REACH_REM = 23.5

// Central Stockholm until the user places a start. The URL takes over once the map has moved.
const START = { center: { lon: 18.0686, lat: 59.3293 }, zoom: 13 }

const { t } = useI18n()
const route = useRoute()
// Tailwind's md breakpoint: from here the panel floats beside the map instead of a sheet.
const hasRoomForPanel = useMediaQuery('(min-width: 48rem)')
const sheetStop = ref(0)
const sheetHeightPx = ref(0)

const section = computed<Section>(() =>
	route.name === 'routes' || route.name === 'route' ? route.name : 'plan',
)
const parts = computed(() => SECTIONS[section.value])
// What the section's parts need from the URL.
const sectionProps = computed(() =>
	section.value === 'route' ? { routeId: Number(route.params.id) } : {},
)
const panelReachPx = computed(() =>
	hasRoomForPanel.value
		? PANEL_REACH_REM * parseFloat(getComputedStyle(document.documentElement).fontSize)
		: 0,
)
const navItems = computed(() => [
	{ value: 'plan' as const, label: t('nav.plan'), to: { name: 'planner' } },
	{ value: 'routes' as const, label: t('nav.routes'), to: { name: 'routes' } },
])

// Picking a stretch needs the map, so the sheet steps down; saying what it was like needs the sheet.
const savedRoutes = useSavedRoutesStore()
const isPickingStretch = computed(
	() => savedRoutes.isPickingStretch && savedRoutes.stretchStage === 'pick',
)
// The lowest stop holds the picker's instruction and its way on while the map is tapped.
const peekRem = computed(() => (isPickingStretch.value ? 18 : 13))
watch(
	() => (savedRoutes.isPickingStretch ? savedRoutes.stretchStage : null),
	(stage) => {
		if (stage === 'pick') sheetStop.value = 0
		else if (stage === 'reasons') sheetStop.value = 1
	},
)

// A through point's settings open in the sheet, which rises far enough to show them.
const planner = usePlannerStore()
watch(
	() => planner.editingThroughPointId,
	(id) => {
		if (id !== null && !hasRoomForPanel.value) sheetStop.value = 1
	},
)

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
					<SegmentedNav :label="t('nav.label')" :items="navItems" :current="parts.nav" />
				</div>
				<component :is="parts.panel" layout="panel" v-bind="sectionProps" />
			</aside>
		</div>
		<BottomSheet
			v-else
			v-model:stop="sheetStop"
			:label="t(parts.titleKey)"
			:expand-label="t('planner.sheet.expand')"
			:collapse-label="t('planner.sheet.collapse')"
			:peek-rem="peekRem"
			@height="sheetHeightPx = $event"
		>
			<template #header>
				<div class="flex flex-col gap-4">
					<SegmentedNav :label="t('nav.label')" :items="navItems" :current="parts.nav" />
					<component :is="parts.peek" v-if="parts.peek" v-bind="sectionProps" />
				</div>
			</template>
			<component :is="parts.panel" layout="sheet" v-bind="sectionProps" />
		</BottomSheet>
		<MapView
			:center="START.center"
			:zoom="START.zoom"
			keep-view-in-url
			zoom-buttons-position="bottom-right"
			:controls-bottom-px="hasRoomForPanel ? 0 : sheetHeightPx"
			:covered-left-px="panelReachPx"
		/>
		<component :is="parts.map" v-bind="sectionProps" />
	</main>
</template>
