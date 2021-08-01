

import ctypes
roctx = ctypes.cdll.LoadLibrary('/opt/rocm/lib/libroctx64.so')
roctr = ctypes.cdll.LoadLibrary('/opt/rocm/lib/libroctracer64.so')

# annotate code segment with NVTX or ROCTX using context manager, e.g.
# with gputx_range('forward-pass'):
#     do_forward_pass(sample)
from contextlib import contextmanager
@contextmanager
def gputx_range(label):
    roctx.roctxRangePushA(label.encode('utf-8'))
    try:
        yield
    finally:
        roctx.roctxRangePop()

# decorate function with GPUTX ranges, e.g.
# @gputx_wrap
# prepare_sample(sample):
#     return sample + 1
import functools
def gputx_wrap(func):
    @functools.wraps(func)
    def gputx_ranged_func(*args, **kwargs):
        with gputx_range('{}.{}'.format(func.__module__, func.__qualname__)):
            value = func(*args, **kwargs)
        return value
    return gputx_ranged_func

def for_all_methods(decorator):
    def decorate(cls):
        for attr in cls.__dict__:
            if callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate

def for_all_functions(module, decorator):
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, types.FunctionType):
            setattr(module, name, decorator(obj))

# add ranges to iterator, e.g.
# dataloader = GputxIterator(dataloader, 'load-samples')
# for i, sample in enumerate(dataloader):
#     do_inference(sample)
class GputxWrappedIterator:
    def __init__(self, iterable, label, counter=False):
        self.iterable = iterable
        self.iterator = None
        self.label = label
        self.counter = counter
    def __iter__(self):
        self.count = 0
        self.iterator = iter(self.iterable)
        return self
    def __next__(self):
        self.count += 1
        label = self.label if not counter else '{}-{}'.format(self.label, self.count)
        with gputx_range(label):
            return next(self.iterator)
    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)
        return getattr(self.iterable, attr)

# add ranges to PyT model, e.g.
# model = GputxWrappedModel(model)
def GputxWrappedModel(model, max_level=10, name=None):
    if max_level == 0:
        return

    if name is None:
        name = name = type(model).__name__
    else:
        name = name + ': ' + type(model).__name__

    def push(*args, _name=name, **kwargs):
        roctx.roctxRangePushA(_name.encode('utf-8'))

    def pop(*args, _name=name, **kwargs):
        roctx.roctxRangePop()

    model.register_forward_pre_hook(push)
    model.register_forward_hook(pop)

    for name, child in model.named_children():
        GputxWrappedModel(child, max_level-1, name)

    return model
