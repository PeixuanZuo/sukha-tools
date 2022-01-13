try:
    import ctypes
    roctx = ctypes.cdll.LoadLibrary('/opt/rocm/lib/libroctx64.so')
    # roctx.roctxRangePushA(label.encode('utf-8'))
    # roctx.roctxRangePop()    
    roctr = ctypes.cdll.LoadLibrary('/opt/rocm/lib/libroctracer64.so')
    # roctr.roctracer_start()
    # roctr.roctracer_stop()
except:
    pass


# annotate code segment with NVTX or ROCTX using context manager, e.g.
# with roctx_range('forward-pass'):
#     do_forward_pass(sample)
from contextlib import contextmanager
@contextmanager
def roctx_range(label):
    roctx.roctxRangePushA(label.encode('utf-8'))
    try:
        yield
    finally:
        roctx.roctxRangePop()