__author__ = "Nicholas Logan"
__copyright__ = "Copyright 2018, Nicholas Logan"
__credits__ = ["Nicholas Logan"]
__license__ = "GNU GPL3"
__version__ = "1.0.0"
__maintainer__ = "Nicholas Logan"
__email__ = "nicholasklogan@gmail.com"
__status__ = "Production"

import functools


def merge_two_dicts(x, y):
    return {**x, **y}
    # python 2 solution
    # z = x.copy()
    # z.update(y)
    # return z


def handle_error(error_type, error_response):
    def __handler__(func):
        def __curried__(*args, **kwargs):
            try:
                ret_val = func(*args, **kwargs)
                if hasattr(ret_val, '__name__') and ret_val.__name__ == '__curried__':
                    ret_val = handle_error(error_type, error_response)(ret_val)
                return ret_val
            except error_type:
                return error_response
        return __curried__
    return __handler__


def curry(func, stored_kws=dict(), arg_count=None):
    arg_count = func.__code__.co_argcount if not arg_count else arg_count

    def __curried__(*_, **kwargs):
        current_kws = merge_two_dicts(stored_kws, kwargs)
        if len(current_kws) == arg_count:
            return func(**current_kws)
        else:
            return curry(func, current_kws, arg_count)
    return __curried__


def to(func, kw):
    def __curried__(*args, **kwargs):
        if kw in kwargs:
            return func(**kwargs)
        elif kwargs:
            return to(func(**kwargs), kw)
        return func(**{kw: args[0]})
    return __curried__


def split_to(func, kws):
    def __to_wrapper__(*args, **kwargs):
        return func(**merge_two_dicts({kw: arg for kw, arg in zip(kws, args[0])}, kwargs))
    return __to_wrapper__


@curry
def map(func, iterable, kw):
    return [func(**{kw: iter1}) for iter1 in iterable]


@curry
def reduce(func, primer, iterable):
    return functools.reduce(func, iterable, primer)


def concurrently(*functions):
    def wrapper(*args, **kwargs):
        return [func(*args, **kwargs) for func in functions]
    return wrapper


@curry
def filterer(func, iterable, kw):
    return tuple(filter(to(func, kw), iterable))


def compose(func1, func2):
    def func(*args, **kwargs):
        return func2(func1(*args, **kwargs))
    return func


def chain(*function_list):
    return functools.reduce(compose, function_list[1:], function_list[0])


@curry
def conditional_branch(conditional_test, if_true, if_false):
    def wrapper(*args, **kwargs):
        boolean_result, _ = conditional_test(*args, **kwargs)
        if boolean_result:
            return if_true(_)
        else:
            return if_false(_)
    return wrapper


def wait(func):
    def wrapper(*args, **kwargs):
        def wrapper2():
            return func(*args, **kwargs)
        return wrapper2
    return wrapper


@curry
def zipper(iter1, iter2):
    return zip(iter1, iter2)
