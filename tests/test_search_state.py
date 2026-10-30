import unittest

from search_state import PageStore, SlidingWindowRateLimiter


class PageStoreTests(unittest.TestCase):
    def test_returns_pages_and_expires_results(self) -> None:
        store = PageStore(ttl_seconds=600)
        store.set_results(42, list(range(1, 13)))

        self.assertEqual(store.next_page(42), [1, 2, 3, 4, 5])
        self.assertTrue(store.has_more(42))
        self.assertEqual(store.next_page(42), [6, 7, 8, 9, 10])
        self.assertEqual(store.next_page(42), [11, 12])
        self.assertFalse(store.has_more(42))
        self.assertEqual(store.next_page(42), [])

    def test_new_search_replaces_previous_results(self) -> None:
        store = PageStore()
        store.set_results(42, [1, 2, 3])
        store.set_results(42, [9, 10])

        self.assertEqual(store.next_page(42), [9, 10])
        self.assertFalse(store.has_more(42))


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_allows_limit_then_reopens_window(self) -> None:
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)

        self.assertTrue(limiter.allow(42, now=0))
        self.assertTrue(limiter.allow(42, now=1))
        self.assertFalse(limiter.allow(42, now=2))
        self.assertTrue(limiter.allow(42, now=60))

    def test_tracks_users_independently(self) -> None:
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)

        self.assertTrue(limiter.allow(42, now=0))
        self.assertTrue(limiter.allow(43, now=0))


if __name__ == "__main__":
    unittest.main()