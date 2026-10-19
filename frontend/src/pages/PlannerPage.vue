<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { AccountMenu } from '@/features/auth'
import { MapView, provideMap } from '@/features/map'

// Central Stockholm until the user places a start. The URL takes over once the map has moved.
const START = { center: { lon: 18.0686, lat: 59.3293 }, zoom: 13 }

const { t } = useI18n()

provideMap()
</script>

<template>
	<main class="relative h-dvh overflow-hidden">
		<h1 class="sr-only">{{ t('planner.title') }}</h1>
		<MapView
			:center="START.center"
			:zoom="START.zoom"
			keep-view-in-url
			zoom-buttons-position="bottom-right"
		/>
		<div class="absolute top-4 right-4">
			<AccountMenu />
		</div>
	</main>
</template>
