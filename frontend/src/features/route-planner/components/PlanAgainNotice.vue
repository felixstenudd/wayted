<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'

import { usePlanAgain } from '../composables/usePlanAgain'

const { t } = useI18n()
const { stage, name, load, forget } = usePlanAgain()
</script>

<template>
	<p v-if="stage === 'loading'" role="status" class="text-small text-graphite">
		{{ t('planner.planAgain.loading') }}
	</p>
	<!-- Inline, not a dialog: the user has already come to the planner, so nothing is left to guard. -->
	<div
		v-else-if="stage === 'confirm'"
		role="alertdialog"
		aria-labelledby="plan-again-title"
		aria-describedby="plan-again-body"
		class="flex flex-col gap-2 rounded-md bg-sunken p-3"
	>
		<p id="plan-again-title" class="text-body font-semibold">
			{{ t('planner.planAgain.title') }}
		</p>
		<p id="plan-again-body" class="text-small text-graphite">
			{{ t('planner.planAgain.body', { name }) }}
		</p>
		<div class="flex flex-wrap gap-2">
			<Button size="sm" @click="load">{{ t('planner.planAgain.confirm') }}</Button>
			<Button variant="ghost" size="sm" @click="forget">{{
				t('planner.planAgain.keep')
			}}</Button>
		</div>
	</div>
	<div
		v-else-if="stage === 'missing' || stage === 'failed'"
		role="alert"
		class="flex items-start gap-2 text-small"
		:class="stage === 'failed' ? 'text-contour' : 'text-graphite'"
	>
		<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
		<p class="flex-1">{{ t(`planner.planAgain.${stage}`) }}</p>
		<Button variant="link" class="h-auto text-small" @click="forget">
			{{ t('planner.planAgain.dismiss') }}
		</Button>
	</div>
</template>
