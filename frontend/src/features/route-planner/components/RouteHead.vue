<script setup lang="ts">
import { TriangleAlert } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useShownRoute } from '../composables/useShownRoute'
import { formatKm } from '../distance'
import { optionLetter } from '../options'
import { usePlannerStore } from '../store'

const { t } = useI18n()
const planner = usePlannerStore()
const { routes, shown } = useShownRoute()

const targetKm = computed(() => formatKm((planner.search?.request.target_distance_m ?? 0) / 1000))
</script>

<template>
	<!-- The shown route's length, which option it is, and why it misses the target if it does. -->
	<div v-if="shown" role="status" class="flex flex-col gap-1">
		<div class="flex items-baseline justify-between gap-3">
			<p class="text-heading">
				{{ t('planner.route.length', { km: formatKm(shown.properties.length_m / 1000) }) }}
			</p>
			<p v-if="routes.length > 1" class="text-small text-graphite">
				{{ t('planner.options.name', { letter: optionLetter(planner.selectedOption) }) }}
			</p>
		</div>
		<p
			v-for="warning in shown.properties.warnings"
			:key="warning"
			class="flex gap-1.5 text-small text-graphite"
		>
			<TriangleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t(`planner.route.warnings.${warning}`, { km: targetKm }) }}
		</p>
	</div>
</template>
