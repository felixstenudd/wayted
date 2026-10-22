<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { ScoreProfile } from '@/features/route'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'

import { useShownRoute } from '../composables/useShownRoute'
import { usePlannerStore } from '../store'
import EditedBar from './EditedBar.vue'
import RouteHead from './RouteHead.vue'
import RouteOptions from './RouteOptions.vue'
import SettingsLine from './SettingsLine.vue'

defineProps<{
	/** In the sheet the options and length sit in its header, which a phone always shows. */
	layout: 'panel' | 'sheet'
}>()

const { t } = useI18n()
const planner = usePlannerStore()
const { shown } = useShownRoute()

const request = computed(() => planner.search?.request ?? null)
// Until the route is first edited, or chosen, it says that it can be.
const isTouch = useMediaQuery('(pointer: coarse)')
const isEditHintShown = computed(() => planner.edit === null && !planner.isChosen)
</script>

<template>
	<div v-if="shown && request" class="flex flex-col gap-5">
		<SettingsLine
			:request="request"
			:action="t('planner.settingsLine.change')"
			@action="planner.changeSettings(true)"
		/>
		<template v-if="layout === 'panel'">
			<RouteOptions />
			<EditedBar />
			<RouteHead />
		</template>
		<ScoreProfile :scores="shown.properties.scores" :preferences="request.preferences" />
		<p v-if="isEditHintShown" class="text-small text-graphite">
			{{ t(isTouch ? 'planner.edit.hintTouch' : 'planner.edit.hint') }}
		</p>
	</div>
</template>
