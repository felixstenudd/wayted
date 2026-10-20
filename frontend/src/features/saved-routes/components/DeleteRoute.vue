<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { onMounted, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { Button } from '@/shared/ui/button'

import { useDeleteRoute } from '../api'
import type { SavedRoute } from '../types'

const props = defineProps<{ route: SavedRoute }>()
const emit = defineEmits<{ keep: [] }>()

const { t } = useI18n()
const router = useRouter()
const remove = useDeleteRoute(() => props.route.id)
const hasFailed = ref(false)
const question = useTemplateRef<HTMLElement>('question')

// The question replaces the menu that opened it, so focus moves to it.
onMounted(() => question.value?.focus())

async function confirm(): Promise<void> {
	if (remove.isPending.value) return
	hasFailed.value = false
	try {
		await remove.mutateAsync()
		await router.push({ name: 'routes' })
	} catch {
		hasFailed.value = true
	}
}
</script>

<template>
	<div class="flex flex-col gap-3 border-t border-line pt-4">
		<p ref="question" tabindex="-1" class="outline-none">
			{{ t('savedRoutes.delete.question', { name: route.name }) }}
		</p>
		<p v-if="hasFailed" class="flex gap-1.5 text-small text-contour" role="alert">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t('savedRoutes.delete.failed') }}
		</p>
		<div class="flex gap-2">
			<Button :aria-busy="remove.isPending.value" @click="confirm">
				{{
					remove.isPending.value
						? t('savedRoutes.delete.deleting')
						: t('savedRoutes.delete.confirm')
				}}
			</Button>
			<Button variant="ghost" @click="emit('keep')">{{
				t('savedRoutes.delete.keep')
			}}</Button>
		</div>
	</div>
</template>
