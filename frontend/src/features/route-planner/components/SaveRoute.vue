<script setup lang="ts">
import { Check } from '@lucide/vue'
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { suggestRouteName } from '@/features/route'
import { useSaveRoute } from '@/features/saved-routes'
import { Button } from '@/shared/ui/button'
import { FormField } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'

import { useShownRoute } from '../composables/useShownRoute'
import { usePlannerStore } from '../store'

const ID = 'save-route-name'

const { t } = useI18n()
const planner = usePlannerStore()
const { shown } = useShownRoute()
const save = useSaveRoute()

const isNaming = ref(false)
const name = ref('')
const isNameMissing = ref(false)

// Saved, and not changed since: editing it again offers to save the new version.
const isSaved = computed(
	() =>
		shown.value !== null &&
		planner.saved !== null &&
		planner.saved.edges === JSON.stringify(shown.value.properties.edges),
)

async function startNaming(): Promise<void> {
	const route = shown.value
	const request = planner.search?.request
	if (!route || !request) return
	const suggested = suggestRouteName({
		shape: request.shape,
		targetM: request.target_distance_m ?? null,
		lengthM: route.properties.length_m,
	})
	name.value = t(suggested.key, suggested.values)
	isNameMissing.value = false
	save.reset()
	isNaming.value = true
	// Selected, so typing replaces the suggestion and Enter keeps it.
	await nextTick()
	const field = document.getElementById(ID)
	if (field instanceof HTMLInputElement) field.select()
}

function submit(): void {
	const route = shown.value
	const request = planner.search?.request
	const trimmed = name.value.trim()
	isNameMissing.value = trimmed === ''
	if (!route || !request || isNameMissing.value) return
	save.mutate(
		{
			name: trimmed,
			activity: request.activity,
			shape: request.shape,
			...(request.target_distance_m ? { target_distance_m: request.target_distance_m } : {}),
			preferences: { ...request.preferences },
			// Where the user dragged the route is kept as through points, for planning it again.
			waypoints: [
				...request.waypoints.map((waypoint) => ({ ...waypoint })),
				...planner.editHandles.map((handle) => ({ ...handle, at: 'any' as const })),
			],
			edges: route.properties.edges.map((step) => ({ ...step })),
		},
		{
			onSuccess: (saved) => {
				planner.markSaved(saved.id, route)
				isNaming.value = false
			},
		},
	)
}

const error = computed(() => {
	if (isNameMissing.value) return t('planner.save.nameMissing')
	return save.isError.value ? t('planner.save.failed') : undefined
})
</script>

<template>
	<p v-if="isSaved && planner.saved" role="status" class="flex items-start gap-1.5">
		<Check class="mt-0.5 size-4 shrink-0 text-vegetation" aria-hidden="true" />
		<span>
			<span class="font-semibold">{{ t('planner.save.saved') }}</span>
			{{ ' ' }}
			<RouterLink
				:to="{ name: 'route', params: { id: planner.saved.id } }"
				class="rounded-sm underline decoration-line-strong underline-offset-3 transition-[text-decoration-color] duration-150 ease-out hover:decoration-ink"
			>
				{{ t('planner.save.view') }}
			</RouterLink>
		</span>
	</p>
	<form v-else-if="isNaming" class="flex flex-col gap-3" novalidate @submit.prevent="submit">
		<FormField
			:id="ID"
			v-slot="{ describedBy, invalid }"
			:label="t('planner.save.name')"
			:error="error"
		>
			<Input
				:id="ID"
				v-model="name"
				maxlength="80"
				autocomplete="off"
				:disabled="save.isPending.value"
				:aria-describedby="describedBy"
				:aria-invalid="invalid || undefined"
			/>
		</FormField>
		<div class="flex gap-2">
			<Button
				type="submit"
				class="flex-1"
				:disabled="save.isPending.value"
				:aria-busy="save.isPending.value"
			>
				{{ save.isPending.value ? t('planner.save.saving') : t('planner.save.submit') }}
			</Button>
			<Button
				type="button"
				variant="ghost"
				:disabled="save.isPending.value"
				@click="isNaming = false"
			>
				{{ t('planner.save.cancel') }}
			</Button>
		</div>
	</form>
	<Button v-else size="lg" class="w-full" @click="startNaming">
		{{ t('planner.save.submit') }}
	</Button>
</template>
