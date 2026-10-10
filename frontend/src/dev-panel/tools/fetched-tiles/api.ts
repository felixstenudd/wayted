import { useQuery } from '@tanstack/vue-query'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'

export const fetchedTilesKey = ['tiles', 'fetched']

export function useFetchedTiles() {
	return useQuery({
		queryKey: fetchedTilesKey,
		queryFn: () => unwrap(api.GET('/tiles/fetched')),
		// shallow: thousands of features must not become reactive proxies
		shallow: true,
	})
}
