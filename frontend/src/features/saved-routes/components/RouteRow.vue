<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { formatDistanceKm, formatSavedOn } from '../format'
import { useSavedRoutesStore } from '../store'
import type { RouteSummary } from '../types'
import RouteSilhouette from './RouteSilhouette.vue'

const props = defineProps<{ route: RouteSummary }>()

const { t, locale } = useI18n()
const store = useSavedRoutesStore()

const isHighlighted = computed(() => store.highlightedId === props.route.id)
const details = computed(() =>
	t('savedRoutes.row.details', {
		activity: t(`savedRoutes.activity.${props.route.activity}`),
		date: formatSavedOn(props.route.created_at, new Date(), locale.value),
	}),
)
const distance = computed(() =>
	t('savedRoutes.row.distanceKm', { km: formatDistanceKm(props.route.distance_m, locale.value) }),
)

function highlight(): void {
	store.highlightedId = props.route.id
}

function unhighlight(): void {
	if (isHighlighted.value) store.highlightedId = null
}
</script>

<template>
	<li>
		<RouterLink
			:to="{ name: 'route', params: { id: route.id } }"
			class="-mx-2 flex items-center gap-3 rounded-md px-2 py-2.5 transition-[background-color] duration-150 ease-out"
			:class="{ 'bg-sunken': isHighlighted }"
			@pointerenter="highlight"
			@pointerleave="unhighlight"
			@focus="highlight"
			@blur="unhighlight"
		>
			<RouteSilhouette :coordinates="route.geometry.coordinates" />
			<span class="min-w-0 flex-1">
				<span class="block truncate font-semibold">{{ route.name }}</span>
				<span class="block text-small text-graphite">{{ details }}</span>
			</span>
			<span class="shrink-0 font-semibold">{{ distance }}</span>
		</RouterLink>
	</li>
</template>
