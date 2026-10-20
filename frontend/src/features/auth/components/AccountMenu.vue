<script setup lang="ts">
import { Bookmark, LogOut, MessageSquare, PenLine, Route, UsersRound } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'

import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

import { useAuthStore } from '../store'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

// Array.from splits by code point, so a name starting with an emoji or an
// accented letter written as two code units still gives one whole character.
const initial = computed(() => Array.from(auth.user?.name.trim() ?? '')[0]?.toLocaleUpperCase())

// Listed so people can see what is coming. They become links once their pages exist.
const comingLater = [
	{ key: 'myReviews', icon: MessageSquare },
	{ key: 'publicReviews', icon: UsersRound },
	{ key: 'writeReview', icon: PenLine },
] as const

async function signOut(): Promise<void> {
	try {
		await auth.signOut()
	} catch (error) {
		// Signed out here already; the server forgets the session when the cookie expires.
		console.error('Sign out failed', error)
	}
	await router.push({ name: 'landing' })
}
</script>

<template>
	<DropdownMenu v-if="auth.user">
		<DropdownMenuTrigger
			:aria-label="t('account.menu', { name: auth.user.name })"
			class="grid size-10 place-items-center rounded-full bg-paper text-title text-ink shadow-float transition-[background-color] duration-150 ease-out hover:bg-sunken"
		>
			{{ initial }}
		</DropdownMenuTrigger>
		<DropdownMenuContent align="end" class="w-64">
			<div class="px-2.5 py-2">
				<p class="truncate text-small font-semibold">{{ auth.user.name }}</p>
				<p class="truncate text-small text-graphite">{{ auth.user.email }}</p>
			</div>
			<DropdownMenuSeparator />
			<DropdownMenuItem as-child>
				<RouterLink :to="{ name: 'planner' }">
					<Route />
					{{ t('account.planRoute') }}
				</RouterLink>
			</DropdownMenuItem>
			<DropdownMenuItem as-child>
				<RouterLink :to="{ name: 'routes' }">
					<Bookmark />
					{{ t('account.savedRoutes') }}
				</RouterLink>
			</DropdownMenuItem>
			<DropdownMenuSeparator />
			<DropdownMenuGroup>
				<DropdownMenuLabel>{{ t('account.notAvailableYet') }}</DropdownMenuLabel>
				<DropdownMenuItem v-for="item in comingLater" :key="item.key" disabled>
					<component :is="item.icon" />
					{{ t(`account.${item.key}`) }}
				</DropdownMenuItem>
			</DropdownMenuGroup>
			<DropdownMenuSeparator />
			<DropdownMenuItem @select="signOut">
				<LogOut />
				{{ t('account.signOut') }}
			</DropdownMenuItem>
		</DropdownMenuContent>
	</DropdownMenu>
</template>
