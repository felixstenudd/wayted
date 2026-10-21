<script setup lang="ts">
import { Check, CircleAlert } from '@lucide/vue'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'

import { useSaveDefaults } from '../api'
import { usePlannerDefaults } from '../composables/usePlannerDefaults'
import { usePlannerStore } from '../store'

const { t } = useI18n()
const planner = usePlannerStore()
const stored = usePlannerDefaults()
const save = useSaveDefaults()
const isJustSaved = ref(false)
const hasSaveFailed = ref(false)

// The confirmation holds until the sliders move again.
watch(
	() => planner.preferenceWeights,
	() => {
		isJustSaved.value = false
		hasSaveFailed.value = false
	},
)

async function saveDefaults(): Promise<void> {
	hasSaveFailed.value = false
	try {
		await save.mutateAsync({ ...planner.preferenceWeights })
		isJustSaved.value = true
	} catch {
		hasSaveFailed.value = true
	}
}
</script>

<template>
	<div
		v-if="stored.isError.value"
		role="alert"
		class="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-small"
	>
		<p class="flex gap-1.5 text-contour">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t('planner.defaults.loadFailed') }}
		</p>
		<Button variant="link" class="text-small" @click="stored.refetch()">
			{{ t('planner.preferences.tryAgain') }}
		</Button>
	</div>
	<p
		v-else-if="isJustSaved"
		role="status"
		class="flex items-center gap-1.5 text-small text-graphite"
	>
		<Check class="size-3.5 shrink-0" aria-hidden="true" />
		{{ t('planner.defaults.saved') }}
	</p>
	<div v-else-if="planner.differsFromDefaults" class="flex flex-col gap-1">
		<div class="flex flex-wrap gap-x-4 gap-y-1">
			<Button
				variant="link"
				class="text-small"
				:aria-busy="save.isPending.value"
				@click="saveDefaults"
			>
				{{
					save.isPending.value ? t('planner.defaults.saving') : t('planner.defaults.save')
				}}
			</Button>
			<Button variant="link" class="text-small" @click="planner.backToDefaults()">
				{{ t('planner.defaults.back') }}
			</Button>
		</div>
		<p v-if="hasSaveFailed" role="alert" class="flex gap-1.5 text-small text-contour">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t('planner.defaults.saveFailed') }}
		</p>
	</div>
</template>
