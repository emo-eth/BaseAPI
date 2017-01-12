import unittest
from multiprocessing.pool import ThreadPool
from BaseAPI import BaseAPI
from timeit import timeit
from time import sleep
from TOKEN import TOKEN, LIFX


class HypeMLite(BaseAPI):
    memo = {}

    def __init__(self):
        (super(HypeMLite, self)
            .__init__('https://api.hypem.com/v2',
                      payload_auth={'key': 'swagger'}))
        self.hm_token = TOKEN

    def get_artist_tracks(self, artist, page=1, count=1, hm_token=None):
        params = self._parse_params(locals().copy(),
                                    exclude_endpoints=['artist'])
        query_string = '/artists/' + str(artist) + '/tracks?' + params
        return self._get(query_string)

    def toggle_favorite(self, type, val, hm_token=None):
        """Add to favorites
        Returns 1 or 0, reflecting the final state of the item (1 is favorite,
        0 is not)
        POST method

        Args:
            REQUIRED:
            - string type: type of resource to favorite
                allowable values: item, site, user
            - string val: id of resource to favorite, generally numerical
            - string hm_token: user token from /signup or /get_token
            Optional:


        Returns JSON of response.
        """
        assert str(type) in ['item', 'site', 'user'], ('"type" must be item or'
                                                       'site or user')
        payload = self._parse_payload(locals().copy(), [])
        endpoint = '/me/favorites?' + self._param('hm_token', self.hm_token)

        return self._post(endpoint, payload)

    def get_token(self, username=None, password=None, fb_oauth_token=None,
                  tw_oauth_token=None, tw_oauth_token_secret=None):
        """Obtain an auth token
        Returns an hm_token like /signup. You must use this token to
        authenticate all requests for a logged-in user. Requires username and
        password OR fb token OR twitter token and secret (accounts must be
        connected via website first)
        POST method

        Args:
            REQUIRED:
            - string username: username
            - string password: password
            - string fb_oauth_token: a facebook API auth token (must be
            currently valid)
            - string tw_oauth_token: a twitter API token secret
            - string tw_oauth_token_secret: a twitter API token
            Optional:

        Returns JSON of response.
        """
        assert (username and password) or fb_oauth_token or (
            tw_oauth_token and tw_oauth_token_secret)
        device_id = self.device_id
        payload = self._parse_payload(locals().copy(), [])
        endpoint = '/get_token'
        self.hm_token = self._post(endpoint, payload)
        return self.hm_token

    def add_playlist(self, playlist_id, itemid, hm_token=None):
        """Add item to playlist
        Returns 1 or 0, reflecting success and failure, respectively. Will
        also add item to favorites, if not already present there
        POST method

        Args:
            REQUIRED:
            - int playlist_id: id of playlist
                allowable values: 0, 1, 2
            - string itemid: itemid of item to add
            - string hm_token: user token from /signup or /get_token
            Optional:


        Returns JSON of response.
        """
        assert str(playlist_id) in ['0', '1', '2'], ('"playlist_id" must be 0 '
                                                     'or 1 or 2')
        payload = self._parse_payload(locals().copy(), ['playlist_id'])
        endpoint = ('/me/playlists/' + str(playlist_id) + '?' +
                    self._param('hm_token', self.hm_token))
        return self._post(endpoint, payload)

    def favorites_me(self, hm_token=None, page=None, count=None):
        """Get my favorites

        GET method

        Args:
            REQUIRED:
            - string hm_token: user token from /signup or /get_token
            Optional:
            - int page: the page of the collection
            - int count: items per page

        Returns JSON of response.
        """
        params = self._parse_params(locals().copy(), [])
        query_string = '/me/favorites?' + params
        return self._get(query_string)

    def remove_playlist(self, playlist_id, itemid, hm_token=None):
        """Remove item from playlist
        Returns 1 or 0, reflecting success and failure, respectively. Will NOT
        remove item from favorites
        DELETE method

        Args:
            REQUIRED:
            - int playlist_id: id of playlist
                allowable values: 0, 1, 2
            - string itemid: itemid of item to remove
            - string hm_token: user token from /signup or /get_token
            Optional:


        Returns JSON of response.
        """
        assert str(playlist_id) in ['0', '1', '2'], ('"playlist_id" must be 0 '
                                                     'or 1 or 2')
        hm_token = self.hm_token
        params = self._parse_params(locals().copy(), ['playlist_id'])
        endpoint = ('/me/playlists/' + str(playlist_id) + '/items/' + params)
        payload = {}
        # defined after payload bc of locals() call

        return self._delete(endpoint, payload)


class LIFXLite(BaseAPI):

    def __init__(self):
        (super(LIFXLite, self)
            .__init__('https://api.lifx.com/v1/',
                      rate_limit_status_code=429,
                      headers={'Authorization': 'Bearer %s' % LIFX},
                      cache_life=-1))

    def set_state(self, selector=None, power=None, color=None, brightness=None,
                  duration=None, infrared=None):
        payload = self._parse_payload(locals().copy(), ['selector'])
        endpoint = '/lights/' + str(selector) + '/state'
        return self._put(endpoint, payload)


class ThrottleTest(BaseAPI):
    last_time_called = [0.0]

    def __init__(self):
        super(ThrottleTest, self).__init__('test')

    @BaseAPI._throttle(.5)
    def test_throttle(self):
        return 5

    @BaseAPI._throttle(.5)
    def test_throttle2(self):
        return 6


class TestBaseAPI(unittest.TestCase):

    def test_assert_memo(self):
        "Memoizing in a subclass without a memo attr raises an assertion error"

        class Test(BaseAPI):

            def __init__(self):
                super(Test, self).__init__('test')

            @BaseAPI._memoize
            def test(self):
                pass
        try:
            Test().test()
            self.assertTrue(False)
        except AssertionError:
            self.assertTrue(True)

    def test_memo_static(self):
        "A call is memoized for all instances with a static memo dict"

        class Fib(BaseAPI):

            memo = {}

            def __init__(self):
                super(Fib, self).__init__('test')

            @BaseAPI._memoize
            def fib(self, n):
                if n == 0 or n == 1:
                    return n
                return self.fib(n - 1) + self.fib(n - 2)

        test = Fib()
        val1 = test.fib(10)
        val2 = test.fib(10)
        # check that the previous instance's call is cached
        test2 = Fib()
        # we access the function's debug attribute to get to the underlying
        # method (since @BaseAPI._memoize returns a *wrapper* around the
        # original method)
        self.assertTrue((test2.fib.debug, 10, tuple()) in Fib.memo)
        # and test that the memoizing works, I suppose
        self.assertEqual(val1, val2)

    def test_memo_instance(self):
        "Instances with their own memo dicts do not leak cached calls"

        class Fib(BaseAPI):

            def __init__(self):
                self.memo = {}
                super(Fib, self).__init__('test')

            @BaseAPI._memoize
            def fib(self, n):
                if n == 0 or n == 1:
                    return n
                return self.fib(n - 1) + self.fib(n - 2)

        test = Fib()
        test.fib(10)
        test2 = Fib()
        # check that the new instance's memo dict is empty
        self.assertEqual(test2.memo, {})

    def test_expire(self):
        "An expired cache value will be re-requested"

        class Wait(BaseAPI):
            memo = {}

            def __init__(self):
                super(Wait, self).__init__('test', cache_life=1)

            @BaseAPI._memoize
            def wait(self):
                sleep(1)
                return 5

        w = Wait()
        w.wait()
        wait1 = timeit(w.wait, number=1)
        self.assertTrue(wait1 < 0.5)
        self.assertEqual(w.wait(), 5)
        sleep(1)
        wait2 = timeit(w.wait, number=1)
        self.assertTrue(wait2 > 0.5)

    def test_hashkey(self):
        "Non-hashable args are made hashable by _hashkey function"
        class Fib(BaseAPI):
            memo = {}

            def __init__(self):
                super(Fib, self).__init__('test')

            @BaseAPI._memoize
            def fib(self, n):
                if n[0] == 0 or n[0] == 1:
                    return n[0]
                return self.fib([n[0] - 1]) + self.fib([n[0] - 2])

        test = Fib()
        val1 = test.fib([10])
        val2 = test.fib([10])
        # check that the previous instance's call is cached
        test2 = Fib()
        # we access the function's debug attribute to get to the underlying
        # method (since @BaseAPI._memoize returns a *wrapper* around the
        # original method)
        self.assertTrue((test2.fib.debug, (10,), tuple()) in Fib.memo)
        # and test that the memoizing works, I suppose
        self.assertEqual(val1, val2)

    def test_throttle(self):
        "Throttling works"
        throttled = ThrottleTest()
        wait1 = timeit(throttled.test_throttle, number=3)
        self.assertTrue(wait1 > 1)

    def test_throttle_multiple_instances(self):
        "Throttling works across instances with a static timer"
        throttle1 = ThrottleTest()
        throttle2 = ThrottleTest()
        throttle1.test_throttle()
        throttle1.test_throttle()
        wait = timeit(throttle2.test_throttle, number=1)
        self.assertTrue(wait > 1)

    def test_throttle_multiple_threads(self):
        "Throttling works across threads"
        throttle = ThrottleTest()

        def test():
            with ThreadPool(4) as pool:
                objs = (pool.apply_async(throttle.test_throttle)
                        for x in range(4))
                return [obj.get() for obj in objs]

        wait = timeit(test, number=1)
        self.assertTrue(wait > 5)

    def test_throttle_multiple_instances_threads(self):
        "Throttling works across threads across instances"
        throttle1 = ThrottleTest()
        throttle2 = ThrottleTest()

        def test():
            with ThreadPool(4) as pool:
                obj1 = pool.apply_async(throttle1.test_throttle)
                obj2 = pool.apply_async(throttle2.test_throttle)
                obj3 = pool.apply_async(throttle1.test_throttle)
                obj4 = pool.apply_async(throttle2.test_throttle)
                return [obj.get() for obj in [obj1, obj2, obj3, obj4]]

        wait = timeit(test, number=1)
        self.assertTrue(wait > 5)

    def test_throttle_non_global(self):
        "Throttling is not global across methods by default"
        throttle = ThrottleTest()
        throttle.test_throttle()
        wait = timeit(throttle.test_throttle2, number=1)
        self.assertTrue(wait < 1)

    def test_oauth_flow(self):
        raise NotImplementedError()

    def test_get(self):
        "GET methods work with params, excludes endpoints"
        lite = HypeMLite()
        result = lite.get_artist_tracks('ratherbright')
        self.assertTrue(len(result) == 1)
        self.assertTrue('artist' in result[0])
        result = lite.favorites_me(lite.hm_token)
        self.assertTrue(result)

    def test_put(self):
        "PUT methods"
        # TODO: Find a public API with a PUT method
        LIFX = LIFXLite()
        result = LIFX.set_state(selector='all', power='on')
        self.assertTrue(result)

    def test_post(self):
        "POST methods"
        lite = HypeMLite()
        result = lite.toggle_favorite('item', '2fv7a')
        self.assertTrue(result in (0, 1))
        result = lite.add_playlist(1, '2fv7a')
        self.assertTrue(result in (0, 1))

    def test_delete(self):
        "DELETE method"
        # TODO: Find a public API with a DELETE method
        raise NotImplementedError()
