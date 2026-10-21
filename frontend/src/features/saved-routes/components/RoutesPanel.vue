<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { Button } from '@/shared/ui/button'

import { useSavedRoutes } from '../api'
import { useSavedRoutesStore } from '../store'
import RouteRow from './RouteRow.vue'

defineProps<{
	/** panel: floating beside the map. sheet: inside a bottom sheet, which brings its own padding. */
	layout: 'panel' | 'sheet'
}>()

const HEADING_ID = 'saved-routes-heading'
const PLACEHOLDER_ROWS = 3

const { t } = useI18n()
const routes = useSavedRoutes()
const store = useSavedRoutesStore()

// A route left highlighted would stay lifted on the map after leaving the list.
onBeforeUnmount(() => {
	store.highlightedId = null
})
</script>

<template>
	<section
		:aria-labelledby="HEADING_ID"
		:aria-busy="routes.isPending.value"
		class="flex flex-col gap-4"
		:class="layout === 'panel' ? 'p-5' : 'border-t border-line pt-4'"
	>
		<h1 :id="HEADING_ID" :class="layout === 'panel' ? 'text-heading' : 'sr-only'">
			{{ t('savedRoutes.title') }}
		</h1>

		<div v-if="routes.isPending.value">
			<span class="sr-only">{{ t('savedRoutes.loading') }}</span>
			<div
				v-for="row in PLACEHOLDER_ROWS"
				:key="row"
				class="flex items-center gap-3 py-2.5"
				aria-hidden="true"
			>
				<span class="h-8 w-11 rounded-sm bg-sunken" />
				<span class="flex flex-1 flex-col gap-1.5">
					<span class="h-3.5 w-36 rounded-sm bg-sunken" />
					<span class="h-3 w-20 rounded-sm bg-sunken" />
				</span>
			</div>
		</div>

		<div v-else-if="routes.isError.value" role="alert" class="flex flex-col items-start gap-2">
			<p class="flex gap-1.5 text-small text-contour">
				<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
				{{ t('savedRoutes.loadFailed') }}
			</p>
			<Button variant="secondary" size="sm" @click="routes.refetch()">
				{{ t('savedRoutes.tryAgain') }}
			</Button>
		</div>

		<div v-else-if="routes.data.value?.length === 0" class="flex flex-col items-start gap-2">
			<p class="text-graphite">{{ t('savedRoutes.empty') }}</p>
			<Button variant="link" as-child>
				<RouterLink :to="{ name: 'planner' }">{{ t('savedRoutes.planRoute') }}</RouterLink>
			</Button>
		</div>

		<ul v-else class="flex flex-col divide-y divide-line">
			<RouteRow v-for="route in routes.data.value" :key="route.id" :route="route" />
		</ul>
	</section>
</template>
