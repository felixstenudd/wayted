<script setup lang="ts">
import { CircleAlert, PenLine } from '@lucide/vue'
import { nextTick, ref, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'

import { useRenameRoute } from '../api'
import type { SavedRoute } from '../types'

const props = defineProps<{ route: SavedRoute; headingId: string }>()
/** Open from outside too, such as the route's menu. */
const isEditing = defineModel<boolean>('editing', { default: false })

const MAX_LENGTH = 80
const INPUT_ID = 'route-name-input'
const ERROR_ID = 'route-name-error'

const { t } = useI18n()
const rename = useRenameRoute(() => props.route.id)
const draft = ref('')
const problem = ref<'empty' | 'failed' | null>(null)
const field = useTemplateRef<HTMLElement>('field')

watch(isEditing, async (editing) => {
	if (!editing) return
	draft.value = props.route.name
	problem.value = null
	await nextTick()
	field.value?.querySelector('input')?.select()
})

async function save(): Promise<void> {
	// A second press while the first is on its way would send it twice.
	if (rename.isPending.value) return
	const name = draft.value.trim()
	if (name === '') {
		problem.value = 'empty'
		return
	}
	if (name === props.route.name) {
		isEditing.value = false
		return
	}
	try {
		await rename.mutateAsync(name)
		isEditing.value = false
	} catch {
		problem.value = 'failed'
	}
}
</script>

<template>
	<div v-if="!isEditing" class="flex items-start gap-1">
		<h1 :id="headingId" tabindex="-1" class="min-w-0 text-heading wrap-break-word outline-none">
			{{ route.name }}
		</h1>
		<Button
			variant="ghost"
			size="icon"
			class="-my-1.5 shrink-0"
			:aria-label="t('savedRoutes.rename.start')"
			@click="isEditing = true"
		>
			<PenLine />
		</Button>
	</div>
	<form v-else class="flex flex-col gap-2" @submit.prevent="save">
		<h1 :id="headingId" class="sr-only">{{ route.name }}</h1>
		<label :for="INPUT_ID" class="text-small font-semibold">{{
			t('savedRoutes.rename.label')
		}}</label>
		<div ref="field">
			<Input
				:id="INPUT_ID"
				v-model="draft"
				:maxlength="MAX_LENGTH"
				:aria-invalid="problem !== null"
				:aria-describedby="problem ? ERROR_ID : undefined"
				@keydown.escape="isEditing = false"
			/>
		</div>
		<p v-if="problem" :id="ERROR_ID" class="flex gap-1.5 text-small text-contour" role="alert">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t(`savedRoutes.rename.${problem}`) }}
		</p>
		<div class="flex gap-2">
			<Button type="submit" size="sm" :aria-busy="rename.isPending.value">
				{{
					rename.isPending.value
						? t('savedRoutes.rename.saving')
						: t('savedRoutes.rename.save')
				}}
			</Button>
			<Button type="button" variant="ghost" size="sm" @click="isEditing = false">
				{{ t('savedRoutes.rename.cancel') }}
			</Button>
		</div>
	</form>
</template>
