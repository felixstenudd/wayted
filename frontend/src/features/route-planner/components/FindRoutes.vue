<script setup lang="ts">
import { CircleAlert, Info } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'

import { useFoundRoute } from '../api'
import { usePlannerStore } from '../store'

const HINT_ID = 'find-routes-hint'

const { t } = useI18n()
const planner = usePlannerStore()
const state = useFoundRoute()

const isBusy = computed(() => ['finding', 'preparing'].includes(state.value.status))
// Not the user's mistake: said plainly, not in the error colour.
const isNotice = computed(
	() => state.value.status === 'failed' && state.value.error === 'stillPreparing',
)
</script>

<template>
	<div class="flex flex-col gap-2">
		<Button
			size="lg"
			class="w-full"
			:disabled="planner.routeRequest === null || isBusy"
			:aria-busy="isBusy"
			:aria-describedby="planner.missingPoint ? HINT_ID : undefined"
			@click="planner.findRoutes()"
		>
			{{
				state.status === 'finding'
					? t('planner.findRoutes.submitting')
					: state.status === 'preparing'
						? t('planner.findRoutes.preparing')
						: t('planner.findRoutes.submit')
			}}
		</Button>
		<p v-if="planner.missingPoint" :id="HINT_ID" class="text-small text-graphite">
			{{ t(`planner.findRoutes.missing.${planner.missingPoint}`) }}
		</p>
		<p v-else-if="state.status === 'preparing'" role="status" class="text-small text-graphite">
			{{ t('planner.findRoutes.preparingHint') }}
		</p>
		<p
			v-else-if="state.status === 'failed'"
			role="alert"
			class="flex gap-1.5 text-small"
			:class="isNotice ? 'text-graphite' : 'text-contour'"
		>
			<component
				:is="isNotice ? Info : CircleAlert"
				class="mt-0.5 size-3.5 shrink-0"
				aria-hidden="true"
			/>
			{{ t(`planner.findRoutes.errors.${state.error}`) }}
		</p>
	</div>
</template>
