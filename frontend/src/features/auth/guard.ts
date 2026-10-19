import type { LocationQueryValue, RouteLocationNormalized, RouteLocationRaw } from 'vue-router'

declare module 'vue-router' {
	interface RouteMeta {
		/** Who may open the page. Pages without it are open to everyone. */
		access?: 'signed-in' | 'signed-out'
	}
}

interface AuthRoutes {
	signIn: string
	/** Where a signed-in user lands. */
	home: string
}

/** Where to send someone instead of `to`, or undefined to let them through. */
export function authRedirect(
	to: RouteLocationNormalized,
	isSignedIn: boolean,
	routes: AuthRoutes,
): RouteLocationRaw | undefined {
	if (to.meta.access === 'signed-in' && !isSignedIn) {
		return { name: routes.signIn, query: { redirect: to.fullPath } }
	}
	if (to.meta.access === 'signed-out' && isSignedIn) return { name: routes.home }
	return undefined
}

/** The redirect query as a path on this site. Anything else could send someone off-site. */
export function safeRedirect(
	redirect: LocationQueryValue | LocationQueryValue[] | undefined,
): string | undefined {
	if (typeof redirect !== 'string') return undefined
	return redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : undefined
}
