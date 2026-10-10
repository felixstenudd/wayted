<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { MapView, provideMap } from '@/features/map'

import ApiStatus from './components/ApiStatus.vue'
import CoveragePanel from './tools/fetched-tiles/CoveragePanel.vue'
import GraphPanel from './tools/graph/GraphPanel.vue'
import QueuePanel from './tools/queue/QueuePanel.vue'

// Central Stockholm, where the pipeline is tried out. The URL takes over once the map has moved.
const START = { center: { lon: 18.0686, lat: 59.3293 }, zoom: 13 }

const { t } = useI18n()

provideMap()
</script>

<template>
	<div class="grid h-dvh grid-cols-[auto_1fr]">
		<aside class="flex w-80 flex-col overflow-y-auto border-r border-line bg-paper">
			<header class="flex flex-col gap-1 px-4 py-4">
				<h1 class="text-heading">{{ t('panel.title') }}</h1>
				<ApiStatus />
			</header>
			<!-- The order is the drawing order: later tools are drawn above earlier ones. -->
			<CoveragePanel />
			<QueuePanel />
			<GraphPanel />
		</aside>
		<main>
			<MapView :center="START.center" :zoom="START.zoom" keep-view-in-url />
		</main>
	</div>
</template>
