<script setup lang="ts">
import { Undo2 } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'

import { useShownRoute } from '../composables/useShownRoute'
import { optionLetter } from '../options'
import { usePlannerStore } from '../store'

const { t } = useI18n()
const planner = usePlannerStore()
const { routes } = useShownRoute()

const changes = computed(() => (planner.edit ? planner.edit.steps.length - 1 : 0))
const isEdited = computed(() => planner.edit?.option === planner.selectedOption)
const from = computed(() => optionLetter(planner.edit?.option ?? 0))
// With options shown, the selected card already says it is edited.
const hasCards = computed(() => routes.value.length > 1 && !planner.isChosen)
</script>

<template>
	<!-- Another option was asked for: the edits go if it is shown, so the user says first. -->
	<div
		v-if="planner.pendingOption !== null"
		role="alert"
		class="flex flex-col gap-2 rounded-md bg-sunken p-3"
	>
		<p class="text-small">{{ t('planner.edit.lose', { from }) }}</p>
		<div class="flex flex-wrap gap-2">
			<Button size="sm" @click="planner.confirmOption()">
				{{ t('planner.edit.show', { to: optionLetter(planner.pendingOption) }) }}
			</Button>
			<Button variant="ghost" size="sm" @click="planner.cancelOption()">
				{{ t('planner.edit.keep') }}
			</Button>
		</div>
	</div>
	<div v-else-if="isEdited" class="flex items-center gap-1">
		<div class="flex min-w-0 flex-1 flex-col">
			<span v-if="!hasCards" class="text-title">{{ t('planner.edit.title') }}</span>
			<span class="text-small text-graphite">{{ t('planner.edit.changes', changes) }}</span>
		</div>
		<Button variant="ghost" size="sm" @click="planner.undoEdit()">
			<Undo2 />
			{{ t('planner.edit.undo') }}
		</Button>
		<Button variant="ghost" size="sm" @click="planner.discardEdit()">
			{{ t('planner.edit.discard') }}
		</Button>
	</div>
</template>
