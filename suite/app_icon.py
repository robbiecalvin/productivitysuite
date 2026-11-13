"""Load the bundled desktop icon, including the running macOS Dock icon."""
import ctypes
from pathlib import Path
import sys
import tkinter as tk
import warnings

ICON_PATH = Path(__file__).resolve().parent / 'assets' / 'app-icon.png'


def set_macos_dock_icon(path):
    """Use AppKit without adding a PyObjC dependency to the desktop runtime."""
    ctypes.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')
    objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    selector = lambda name: objc.sel_registerName(name.encode('ascii'))
    address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
    send_string = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(address)
    send_object = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
    send_void = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
    release = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(address)
    filename = send_string(objc.objc_getClass(b'NSString'), selector('stringWithUTF8String:'), str(path).encode('utf-8'))
    image = send_object(send(objc.objc_getClass(b'NSImage'), selector('alloc')),
                        selector('initWithContentsOfFile:'), filename)
    if not image:
        raise RuntimeError('AppKit could not load the app icon.')
    try:
        application = send(objc.objc_getClass(b'NSApplication'), selector('sharedApplication'))
        if not application:
            raise RuntimeError('AppKit application is unavailable.')
        send_void(application, selector('setApplicationIconImage:'), image)
    finally:
        release(image, selector('release'))


def apply_app_icon(window, path=None):
    path = Path(path) if path is not None else ICON_PATH
    if not path.is_file():
        return False
    try:
        image = tk.PhotoImage(master=window, file=str(path))
        window.iconphoto(True, image)
        # Tk stores the image name; Python must keep the image object alive.
        window._suite_app_icon = image
        if sys.platform == 'darwin':
            set_macos_dock_icon(path.resolve())
        return True
    except (tk.TclError, OSError, RuntimeError) as error:
        warnings.warn(f'Could not load application icon: {error}', RuntimeWarning, stacklevel=2)
        return False
