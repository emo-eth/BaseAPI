import requests
import json
import time
import multiprocessing
from functools import wraps


class RateLimitError(Exception):
    '''A rate-limit-specific error'''

    def __init__(self, value):
        '''
        Args:
            value: Rate Limit error code for the API'''
        self.value = str(value) + ' Error/Rate Limit Encountered'


class APIError(Exception):
    '''A generic API Error that must be passed a value'''

    def __init__(self, value):
        '''
        Args:
            value: error message to display'''
        self.value = value


def _hashkey(obj):
    '''Converts a list, dict, or set to a hashable pseudo-equivalent'''
    # TODO: timeit to check sorted tuple vs frozenset speed (& memory?)
    if isinstance(obj, list):
        return tuple(sorted(obj))
    if isinstance(obj, dict):
        return tuple(sorted(obj.items()))
    if isinstance(obj, set):
        return tuple(sorted(obj))
    return obj


class BaseAPI(object):
    '''A base class to implement the methods of a RESTful HTTP API'''
    # TODO: Handle OAuth2 Flow

    lock = multiprocessing.Lock()

    def __init__(self, api, rate_limit_status_code=403,
                 cache_life=float('inf'), payload_auth={}, headers={}):
        '''
        Args:
            string api: base link to api (https://spotify.com/v1/)
            int rate_limit_status_code: status code to pass to RateLimitError
                constructor
            int cache_life: length in seconds a request should be read from
                in-memory cache before requesting from the server again
            dict payload_auth: dictionary of authorization information, passed
                in as part of payload or query params
                eg {'token': val, 'secret': val}
            dict headers: headers (including auth) to be passed with each
                request
        '''
        self._api = api
        self._rate_limit_status_code = rate_limit_status_code
        self._payload_auth = payload_auth
        self._headers = headers
        self._cache_life = cache_life
        self._session = requests.Session()

    @staticmethod
    def _memoize(f):
        '''Wraps a function to read from a static memo dictionary. The subclass
        must include its own instance or static memo dictionary The args of
        a function must be hashable'''

        @wraps(f)
        def memoized(*args, **kwargs):
            now = int(time.time())
            instance = args[0]
            assert hasattr(instance, 'memo'), ("Subclass or instance needs " +
                                               "a 'memo' dict attribute to " +
                                               "be memoized.")
            hashable_args = [_hashkey(x) for x in args[1:]]
            hashable_kwargs = [_hashkey({k: _hashkey(v) for k, v in
                                         kwargs.items()})]
            # create a hashable key out of the function, args (excluding
            # instance) and kwargs
            key = tuple([f] + hashable_args + hashable_kwargs)
            # store new key or update if our key has outlived cache-life
            if (key not in instance.memo) or (now - instance.memo[key][1] >
                                              instance._cache_life):
                instance.memo[key] = (f(*args, **kwargs), now)
            # return our cached request
            return instance.memo[key][0]

        memoized.debug = f
        return memoized

    @staticmethod
    def _throttle(max_per_second, global_rate_limit=False):
        '''Rate-limits a method call either globally or on a per-method basis

        Args:
            float max_per_second: max number of times this method may be called
                per second
            boolean global_rate_limit: if true, all other methods with this
                flag will reference the same last_time_called. if false,
                rate-limits will be applied on a per-method basis.
                eg: set to true if the *entire API* allows 20 calls per
                second
        '''
        interval = 1.0 / max_per_second

        def decorator(f):
            last_time = [0.0]

            @wraps(f)
            def throttled(*args, **kwargs):
                instance = args[0]
                if global_rate_limit:
                    last_time_called = instance.last_time_called
                else:
                    last_time_called = last_time
                instance.lock.acquire()
                elapsed = time.clock() - last_time_called[0]
                time_to_wait = interval - elapsed
                if time_to_wait > 0 and last_time_called[0]:
                    time.sleep(time_to_wait)
                return_val = f(*args, **kwargs)
                last_time_called[0] = time.clock()
                instance.lock.release()
                return return_val

            return throttled

        return decorator

    @property
    def _key(self):
        '''Converts auth dict into query string format'''
        auth_string = ''
        for k, v in self._payload_auth.items():
            auth_string += str(k) + '=' + str(v) + '&'
        return auth_string

    def _check_status(self, response):
        '''Checks response status and raises errors accordingly

        Args:
            requests.Response response: the response of a request
        '''
        sc = response.status_code
        # 2xx statuses are all success
        if sc // 100 == 2:
            assert response.text, 'Invalid response from server'
            return
        elif sc == self._rate_limit_status_code:
            raise RateLimitError(self._rate_limit_status_code)
        elif sc == 401:
            response = json.loads(response.text)
            raise APIError(response)
        else:
            raise ValueError('Status code unhandled: ' +
                             str(sc) + ' for URL ' + response.url)

    def _get(self, qstring):
        '''Handles auth, API query, status checking, and json conversion.
        May raise an exception depending on response status code.
        Returns response as JSON

        Args:
            string qstring: string for API query without auth key
        '''
        qstring += self._key
        response = self._session.get(self._api + qstring,
                                     headers=self._headers)
        self._check_status(response)
        return json.loads(response.text)

    def _put_post_delete(self, endpoint, payload, http_method):
        '''Calls the passed put/post/delete method with the specified payload
        and returns the response as JSON if it is valid

        Args:
            string endpoint: URL of API endpoint
            dict payload: dict of payload data
            requests.method http_method: requests' put/post/delete method
        '''
        payload.update(self._payload_auth)
        response = http_method(self._api + endpoint, data=payload,
                               headers=self._headers)
        self._check_status(response)
        return json.loads(response.text)

    def _put(self, endpoint, payload):
        return self._put_post_delete(endpoint, payload, self._session.put)

    def _post(self, endpoint, payload):
        return self._put_post_delete(endpoint, payload, self._session.post)

    def _delete(self, endpoint, payload):
        return self._put_post_delete(endpoint, payload, self._session.delete)

    def _param(self, param, value):
        '''Formats a parameter/value pair for html
        Args:
            string param: parameter name
            value value: value for parameter

        Returns correctly formatted parameter=value&
        '''
        if value:
            return str(param) + '=' + str(value) + '&'
        else:
            return ''

    def _parse_params(self, locals_copy, exclude_endpoints=[]):
        '''Format all params for a GET request into a query string

        Args:
            dict locals_copy: a copy() of the locals() value in an API method
            list exclude_endpoints: a list of names of variables that refer to
                endpoint-specific arguments in the method's local variables,
                ie arguments that do not need to be parsed into a query string
                    eg: http://spotify.com/v1/{artists}/xxx

        Returns a formatted query string of param=value& pairs'''
        query_string = ''
        # remove self and endpoint-specific args
        del locals_copy['self']
        for val in exclude_endpoints:
            del locals_copy[val]
        for param, val in locals_copy.items():
            query_string += self._param(param, val)
        return query_string

    def _parse_payload(self, locals_copy, exclude_endpoints=[]):
        '''Remove self and endpoint args from PUT/POST/DELETE payload

        Args:
            dict locals_copy: a copy() of the locals() value in an API method
            list exclude_endpoints: a list of names of variables that refer to
                endpoint-specific arguments in the method's local variables,
                ie arguments that do not need to be parsed in the payload
                    eg: http://spotify.com/v1/{artists}/xxx'''
        del locals_copy['self']
        for val in exclude_endpoints:
            del locals_copy[val]
        return locals_copy
