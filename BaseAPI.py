import requests
import json
import time


class RateLimitError(Exception):
    '''A rate-limit-specific error'''

    def __init__(self, value):
        '''
        Params:
            value: Rate Limit error code for the API'''
        self.value = str(value) + ' Error/Rate Limit Encountered'


class APIError(Exception):
    '''A generic API Error that must be passed a value'''

    def __init__(self, value):
        '''
        Params:
            value: error message to display'''
        self.value = value


class BaseAPI(object):
    '''An base class to implement the methods of a RESTful HTTP API'''

    def __init__(self, api, rate_limit_status_code=403,
                 cache_life=float('inf'), auth_dict={}):
        '''
        Params:
            string api: base link to api (https://spotify.com/v1/)
            int rate_limit_status_code: status code to pass to RateLimitError
                constructor
            int cache_life: length in seconds a request should be read from
                in-memory cache before requesting from the server again
            dict auth_dict: dictionary of authorization information,
                eg {'token': val, 'secret': val}
        '''
        self._api = api
        self._rate_limit_status_code = rate_limit_status_code
        self._auth_dict = auth_dict
        self._cache_life = cache_life

    @staticmethod
    def _memoize(f):
        '''Wraps a function to read from a memo dictionary. The args of a
        function must be hashable'''

        memo = {}

        def memoized(*args, **kwargs):
            now = int(time.time())
            instance = args[0]
            # create a hashable key out of the function, args (excluding
            # instance) and kwargs
            key = tuple([f, frozenset(kwargs)] + list(args[1:]))
            # store new key / update if our key has outlived cache-life
            if key not in memo or now - memo[key][1] > instance._cache_life:
                memo[key] = (f(*args, **kwargs), now)
            # return our cached request
            return memo[key][0]

        return memoized

    @property
    def _key(self):
        '''Converts auth dict into query string format'''
        auth_string = ''
        for k, v in self._auth_dict.items():
            auth_string += str(k) + '=' + str(v) + '&'
        return auth_string

    def _check_status(self, response):
        '''Checks response status and raises errors accordingly

        Params:
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
            raise APIError(response['error_msg'])
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
        response = requests.get(self._api + qstring)
        self._check_status(response)
        return json.loads(response.text)

    def _put_post_delete(self, endpoint, payload, http_method):
        '''Calls the passed put/post/delete method with the specified payload
        and returns the response as JSON if it is valid

        Params:
            string endpoint: URL of API endpoint
            dict payload: dict of payload data
            requests.method http_method: requests' put/post/delete method
        '''
        payload.update(self._auth_dict)
        response = http_method(self._api + endpoint, data=payload)
        self._check_status(response)
        return json.loads(response.text)

    def _put(self, endpoint, payload):
        return self._put_post_delete(endpoint, payload, requests.put)

    def _post(self, endpoint, payload):
        return self._put_post_delete(endpoint, payload, requests.post)

    def _delete(self, endpoint, payload):
        return self._put_post_delete(endpoint, payload, requests.delete)

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

    def _parse_params(self, locals_copy, endpoint_args):
        '''Format all params for a GET request into a query string

        Params:
            dict locals_copy: a copy() of the locals() value in an API method
            list endpoint_args: a list of names of variables that refer to
                endpoint-specific arguments in the method's local variables,
                ie arguments that do not need to be parsed into a query string
                    eg: http://spotify.com/v1/{artists}/xxx

        Returns a formatted query string of param=value& pairs'''
        query_string = ''
        # remove self and endpoint-specific args
        locals_copy.pop('self')
        for val in endpoint_args:
            locals_copy.pop(val)
        for param, val in locals_copy.items():
            query_string += self._param(param, val)
        return query_string

    def _parse_payload(self, locals_copy, endpoint_args):
        '''Remove self and endpoint args from POST/PUT/DELETE payload

        Params:
            dict locals_copy: a copy() of the locals() value in an API method
            list endpoint_args: a list of names of variables that refer to
                endpoint-specific arguments in the method's local variables,
                ie arguments that do not need to be parsed in the payload
                    eg: http://spotify.com/v1/{artists}/xxx'''
        locals_copy.pop('self')
        for val in endpoint_args:
            locals_copy.pop(val)
        return locals_copy

    def set_auth(self, auth):
        '''Change to user-supplied auth token
        Params:
            dict auth: dictionary of new authentication information
        '''
        self._auth_dict = auth
