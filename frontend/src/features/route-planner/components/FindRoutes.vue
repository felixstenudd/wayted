<script setup lang="ts">
import { CircleAlert, Info } from '@lucide/vue'
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'

import { useFindRoutes } from '../api'
import { findRoutesError } from '../findRoutesError'
import { usePlannerStore } from '../store'

const HINT_ID = 'find-routes-hint'

const { t } = useI18n()
const planner = usePlannerStore()
const findRoutes = useFindRoutes()

const error = computed(() => findRoutesError(findRoutes.error.value))
// Not the user's mistake: said plainly, not in the error colour.
const isNotice = computed(() => error.value === 'notAvailable')

// A message about the last request is stale once the route changes.
watch(
	() => planner.routeRequest,
	() => findRoutes.reset(),
	{ deep: true },
)

function submit(): void {
	if (planner.routeRequest) findRoutes.mutate(planner.routeRequest)
}
</script>

<template>
	<div class="flex flex-col gap-2">
		<Button
			size="lg"
			class="w-full"
			:disabled="planner.routeRequest === null || findRoutes.isPending.value"
			:aria-busy="findRoutes.isPending.value"
			:aria-describedby="planner.missingPoint ? HINT_ID : undefined"
			@click="submit"
		>
			{{
				findRoutes.isPending.value
					? t('planner.findRoutes.submitting')
					: t('planner.findRoutes.submit')
			}}
		</Button>
		<p v-if="planner.missingPoint" :id="HINT_ID" class="text-small text-graphite">
			{{ t(`planner.findRoutes.missing.${planner.missingPoint}`) }}
		</p>
		<p
			v-else-if="error"
			role="alert"
			class="flex gap-1.5 text-small"
			:class="isNotice ? 'text-graphite' : 'text-contour'"
		>
			<component
				:is="isNotice ? Info : CircleAlert"
				class="mt-0.5 size-3.5 shrink-0"
				aria-hidden="true"
			/>
			{{ t(`planner.findRoutes.errors.${error}`) }}
		</p>
	</div>
</template>
