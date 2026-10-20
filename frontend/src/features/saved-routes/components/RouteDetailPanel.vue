<script setup lang="ts">
import { ChevronLeft, CircleAlert, Ellipsis, PenLine, Trash2 } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { ApiError } from '@/shared/api'
import { Button } from '@/shared/ui/button'
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

import { useSavedRoute } from '../api'
import { formatDistanceKm, formatSavedOn } from '../format'
import DeleteRoute from './DeleteRoute.vue'
import RouteName from './RouteName.vue'
import ScoreProfile from './ScoreProfile.vue'

const props = defineProps<{
	/** panel: floating beside the map. sheet: inside a bottom sheet, which brings its own padding. */
	layout: 'panel' | 'sheet'
	routeId: number
}>()

const HEADING_ID = 'route-heading'

const { t, locale } = useI18n()
const saved = useSavedRoute(() => props.routeId)
const route = computed(() => saved.data.value)
const isMissing = computed(
	() => saved.error.value instanceof ApiError && saved.error.value.status === 404,
)
const isRenaming = ref(false)
const isDeleting = ref(false)
watch(
	() => props.routeId,
	() => {
		isRenaming.value = false
		isDeleting.value = false
	},
)

const details = computed(() => {
	if (!route.value) return ''
	return t('savedRoutes.detail.details', {
		activity: t(`savedRoutes.activity.${route.value.activity}`),
		shape: t(`savedRoutes.shape.${route.value.shape}`),
		km: formatDistanceKm(route.value.distance_m, locale.value),
		date: formatSavedOn(route.value.created_at, new Date(), locale.value),
	})
})
</script>

<template>
	<section
		:aria-labelledby="HEADING_ID"
		:aria-busy="saved.isPending.value"
		class="flex flex-col gap-5"
		:class="layout === 'panel' ? 'p-5' : 'border-t border-line pt-4'"
	>
		<div class="flex items-center justify-between">
			<RouterLink
				:to="{ name: 'routes' }"
				class="-ml-1 flex items-center gap-1 rounded-sm text-small font-semibold text-graphite transition-[color] duration-150 ease-out hover:text-ink"
			>
				<ChevronLeft class="size-4" aria-hidden="true" />
				{{ t('savedRoutes.title') }}
			</RouterLink>
			<DropdownMenu v-if="route">
				<DropdownMenuTrigger as-child>
					<Button
						variant="ghost"
						size="icon"
						class="-my-2"
						:aria-label="t('savedRoutes.detail.more')"
					>
						<Ellipsis />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" class="w-48">
					<DropdownMenuItem @select="isRenaming = true">
						<PenLine />
						{{ t('savedRoutes.rename.start') }}
					</DropdownMenuItem>
					<DropdownMenuItem @select="isDeleting = true">
						<Trash2 />
						{{ t('savedRoutes.delete.confirm') }}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>

		<div v-if="saved.isPending.value" class="flex flex-col gap-3" aria-hidden="true">
			<span class="h-7 w-48 rounded-sm bg-sunken" />
			<span class="h-4 w-56 rounded-sm bg-sunken" />
			<span v-for="row in 3" :key="row" class="h-4 rounded-sm bg-sunken" />
		</div>
		<h1 v-if="saved.isPending.value" :id="HEADING_ID" class="sr-only">
			{{ t('savedRoutes.detail.loading') }}
		</h1>

		<div v-else-if="isMissing" class="flex flex-col items-start gap-2">
			<h1 :id="HEADING_ID" class="text-title">{{ t('savedRoutes.detail.missingTitle') }}</h1>
			<p class="text-graphite">{{ t('savedRoutes.detail.missing') }}</p>
		</div>

		<div v-else-if="saved.isError.value" role="alert" class="flex flex-col items-start gap-2">
			<h1 :id="HEADING_ID" class="sr-only">{{ t('savedRoutes.detail.loading') }}</h1>
			<p class="flex gap-1.5 text-small text-contour">
				<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
				{{ t('savedRoutes.detail.loadFailed') }}
			</p>
			<Button variant="secondary" size="sm" @click="saved.refetch()">
				{{ t('savedRoutes.tryAgain') }}
			</Button>
		</div>

		<template v-else-if="route">
			<div class="flex flex-col gap-1">
				<RouteName v-model:editing="isRenaming" :route="route" :heading-id="HEADING_ID" />
				<p class="text-small text-graphite">{{ details }}</p>
			</div>
			<ScoreProfile :route="route" />
			<DeleteRoute v-if="isDeleting" :route="route" @keep="isDeleting = false" />
		</template>
	</section>
</template>
