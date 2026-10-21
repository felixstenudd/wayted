<script setup lang="ts">
import { ChevronLeft, CircleAlert, Ellipsis, PenLine, Trash2 } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { ScoreProfile } from '@/features/route'

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
import type { PreferenceChange } from '../review'
import { useSavedRoutesStore } from '../store'
import DeleteRoute from './DeleteRoute.vue'
import ReviewSavedNotice from './ReviewSavedNotice.vue'
import RouteName from './RouteName.vue'
import RouteReviewForm from './RouteReviewForm.vue'
import RouteReviewSummary from './RouteReviewSummary.vue'
import StretchPicker from './StretchPicker.vue'
import StretchReasons from './StretchReasons.vue'
import StretchReviewList from './StretchReviewList.vue'

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
const isReviewing = ref(false)
const store = useSavedRoutesStore()
// What the last saved review did to the user's weights, until they move on.
const savedChanges = ref<PreferenceChange[] | null>(null)
const isStretchJustSaved = ref(false)
watch(
	() => props.routeId,
	() => {
		isRenaming.value = false
		isDeleting.value = false
		isReviewing.value = false
		savedChanges.value = null
		isStretchJustSaved.value = false
		store.stopPickingStretch()
	},
)
// Picking belongs to this route's page; leaving it ends the picking.
onBeforeUnmount(() => store.stopPickingStretch())
// Each view replaces the one whose button had focus. Focus moves to the new view's heading, so
// keyboard and screen reader users carry on from there rather than from the top of the page.
const view = computed(() => {
	if (store.isPickingStretch) return store.stretchStage
	return isReviewing.value ? 'review' : 'route'
})
watch(view, async () => {
	await nextTick()
	document.getElementById(HEADING_ID)?.focus()
})
// A review answers attributes the route has scores for; without any there is nothing to ask.
const canReview = computed(() => Object.keys(route.value?.scores ?? {}).length > 0)

function startReview(): void {
	savedChanges.value = null
	isDeleting.value = false
	isReviewing.value = true
}

function startStretch(): void {
	savedChanges.value = null
	isStretchJustSaved.value = false
	isDeleting.value = false
	store.startPickingStretch()
}

function reviewSaved(changes: PreferenceChange[]): void {
	isReviewing.value = false
	savedChanges.value = changes
}

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
		<!-- Hidden while a review is written: the review has its own way back. -->
		<div
			v-if="!isReviewing && !store.isPickingStretch"
			class="flex items-center justify-between"
		>
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

		<StretchPicker
			v-else-if="route && store.isPickingStretch && store.stretchStage === 'pick'"
			:route="route"
			:heading-id="HEADING_ID"
		/>
		<StretchReasons
			v-else-if="route && store.isPickingStretch"
			:route="route"
			:heading-id="HEADING_ID"
			@saved="isStretchJustSaved = true"
		/>

		<RouteReviewForm
			v-else-if="route && isReviewing"
			:route="route"
			:heading-id="HEADING_ID"
			@saved="reviewSaved"
			@cancel="isReviewing = false"
		/>

		<template v-else-if="route">
			<div class="flex flex-col gap-1">
				<RouteName v-model:editing="isRenaming" :route="route" :heading-id="HEADING_ID" />
				<p class="text-small text-graphite">{{ details }}</p>
			</div>
			<ReviewSavedNotice v-if="savedChanges" :changes="savedChanges" />
			<ScoreProfile :scores="route.scores" :preferences="route.preferences" />
			<RouteReviewSummary v-if="route.review" :route="route" @edit="startReview" />
			<p v-else-if="!canReview" class="text-small text-graphite">
				{{ t('savedRoutes.review.nothingToReview') }}
			</p>
			<div class="flex gap-2">
				<Button v-if="!route.review && canReview" class="flex-1" @click="startReview">
					{{ t('savedRoutes.review.start') }}
				</Button>
				<Button variant="secondary" class="flex-1" @click="startStretch">
					{{ t('savedRoutes.stretch.start') }}
				</Button>
			</div>
			<StretchReviewList :route="route" :just-saved="isStretchJustSaved" />
			<DeleteRoute v-if="isDeleting" :route="route" @keep="isDeleting = false" />
		</template>
	</section>
</template>
