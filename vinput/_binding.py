from ctypes import *
from typing import Callable

import ctypes.util as cutil
import os 
import sys

class VInputException(Exception): pass

vinput = None

dir_path = os.path.dirname(os.path.realpath(__file__))

os_name = "notwin"
if sys.platform.startswith("win"):
    os_name = "win"
elif sys.platform.startswith("darwin"):
    os_name = "darwin"

try:
    dll = ''
    if os_name == 'notwin':
        dll = 'libvinput.so.dat'
    elif os_name == 'win':
        dll = 'libvinput.dll.dat'
    else:
        dll = 'libvinput.dylib.dat'

    path = os.path.join(dir_path, 'lib', dll)
    vinput = CDLL(path)
except: pass

if vinput == None:
    vinput = cutil.find_library('vinput')
    if vinput == None:
        # Try and find it manually
        files = [
            './libvinput.so',
            './libvinput.dll',
            './libvinput.dylib',
            'libvinput.so',
            'libvinput.dll',
            'libvinput.dylib',
            '/usr/local/lib/libvinput.so',
            '/usr/lib/libvinput.so',
            '/usr/local/lib64/libvinput.so',
            '/usr/lib64/libvinput.so',
            '/usr/local/lib/libvinput.dylib',
            '/usr/local/lib64/libvinput.dylib',
        ]
        for file in files:
            try:
                vinput = CDLL(file)
                if vinput != None:
                    break
            except: pass
    if isinstance(vinput, str):
        vinput = CDLL(vinput)

if vinput == None:
    raise VInputException("Failed to find libvinput library")

def version() -> (int, int, int):
    v = vinput.VInput_version()
    v = int(v)
    return (v & 0xff, (v & 0xff00) >> 8, (v & 0xff0000) >> 16)

class _EventListener(Structure):
    _fields_ = [
        ('listen_keyboard', c_bool),
        ('initialized', c_bool),
        ('data', c_void_p),
        ('listen_mouse_button', c_bool),
        ('listen_mouse_move', c_bool),
    ]

    def __str__(self):
        return f"EventListener(listen_keyboard={self.listen_keyboard}, initialized={self.initialized}, data={self.data}, listen_mouse_button={self.listen_mouse_button}, listen_mouse_move={self.listen_mouse_move})"

class KeyboardModifiers(Structure):
    _fields_ = [
        ('left_control', c_ubyte, 1),
        ('right_control', c_ubyte, 1),
        ('left_shift', c_ubyte, 1),
        ('right_shift', c_ubyte, 1),
        ('left_alt', c_ubyte, 1),    # On Mac, this is the Option key
        ('right_alt', c_ubyte, 1),   # On Mac, this is the Option key
        ('left_meta', c_ubyte, 1),   # On Mac, this is the Command key
        ('right_meta', c_ubyte, 1),  # On Mac, this is the Command key
        ('left_super', c_ubyte, 1),  # On Mac, this is the Fn key
        ('right_super', c_ubyte, 1), # On Mac, this is the Fn key
        ('left_hyper', c_ubyte, 1),
        ('right_hyper', c_ubyte, 1),
    ]

    def __str__(self):
        return f"KeyboardModifiers(left_control={self.left_control}, right_control={self.right_control}, left_shift={self.left_shift}, right_shift={self.right_shift}, left_alt={self.left_alt}, right_alt={self.right_alt}, left_meta={self.left_meta}, right_meta={self.right_meta}, left_super={self.left_super}, right_super={self.right_super}, left_hyper={self.left_hyper}, right_hyper={self.right_hyper})"

    def modifier_pressed_except_shift(self) -> bool:
        res = vinput.KeyboardModifiers_modifier_pressed_except_shift(pointer(self))
        return res

class KeyboardEvent(Structure):
    _fields_ = [
        ('pressed', c_bool),
        ('keychar', c_char),
        ('keycode', c_uint16),
        ('keysym', c_uint16),
        ('modifiers', KeyboardModifiers),
        ('timestamp', c_size_t)
    ]

    def __str__(self):
        return f"KeyboardEvent(pressed={self.pressed}, keychar={self.keychar}, keycode={self.keycode}, keysym={self.keysym}, modifiers={self.modifiers}, timestamp={self.timestamp})"

class MouseButtonEvent(Structure):
    _fields_ = [
        ('button', c_int),
        ('kind', c_int),
    ]

    def __str__(self):
        return f"MouseButtonEvent(button={self.button}, kind={self.kind})"

class MouseMoveEvent(Structure):
    _fields_ = [
        ('x', c_uint),
        ('y', c_uint),
        ('velocity_x', c_float),
        ('velocity_y', c_float),
        ('velocity', c_float),
    ]

    def __str__(self):
        return f"MouseMoveEvent(x={self.x}, y={self.y}, velocity_x={self.velocity_x}, velocity_y={self.velocity_y}, velocity={self.velocity})"

class EventListener:
    def __init__(self, listen_keyboard: bool, listen_mouse_button: bool = False, listen_mouse_move: bool = False):
        self._listener = _EventListener()
        err = vinput.EventListener2_create(pointer(self._listener), c_bool(listen_keyboard), c_bool(listen_mouse_button), c_bool(listen_mouse_move))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def __del__(self):
        err = vinput.EventListener_free(self._listener)
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def start(
        self,
        keyboard_callback: Callable[[KeyboardEvent], None],
        mouse_button_callback: Callable[[MouseButtonEvent], None] | None = None,
        mouse_move_callback: Callable[[MouseMoveEvent], None] | None = None
    ):
        KEYBOARD_FUNC = CFUNCTYPE(None, KeyboardEvent)
        MOUSE_BUTTON_FUNC = CFUNCTYPE(None, MouseButtonEvent)
        MOUSE_MOVE_FUNC = CFUNCTYPE(None, MouseMoveEvent)
        
        keyboard_func = KEYBOARD_FUNC(keyboard_callback)
        
        mouse_button_func = None if mouse_button_callback is None else MOUSE_BUTTON_FUNC(mouse_button_callback)
        mouse_move_func = None if mouse_move_callback is None else MOUSE_MOVE_FUNC(mouse_move_callback)
        
        vinput.EventListener2_start(
            pointer(self._listener),
            keyboard_func,
            c_void_p(None) if mouse_button_func is None else mouse_button_func,
            c_void_p(None) if mouse_move_func is None else mouse_move_func
        )

    def stop(self):
        """Stop a running listener, causing the blocking start() call to return.

        Safe to call from a different thread than the one that called start().
        No-op if the listener is not currently running.
        """
        err = vinput.EventListener_stop(pointer(self._listener))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

class _EventEmulator(Structure):
    _fields_ = [
        ('initialized', c_bool),
        ('data', c_void_p)
    ]

class EventEmulator:
    def __init__(self):
        self._emulator = _EventEmulator()
        err = vinput.EventEmulator_create(pointer(self._emulator))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))
        __import__('time').sleep(0.1)

    def __del__(self):
        err = vinput.EventEmulator_free(pointer(self._emulator))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def keyboard_state_clear(self):
        err = vinput.EventEmulator_keyboard_state_clear(pointer(self._emulator))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def keyboard_state_set(self, state: list[int]):
        array_type = c_int * len(state)
        err = vinput.EventEmulator_keyboard_state_set(pointer(self._emulator), array_type(*state), len(state))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def keyboard_press(self, keysym: int):
        err = vinput.EventEmulator_press(pointer(self._emulator), c_uint16(keysym))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def keyboard_release(self, keysym: int):
        err = vinput.EventEmulator_release(pointer(self._emulator), c_uint16(keysym))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def keyboard_typec(self, keychar: str):
        err = vinput.EventEmulator_typec(pointer(self._emulator), c_char(keychar[0].encode('utf-8')))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

    def keyboard_types(self, text: str):
        err = vinput.EventEmulator_types(pointer(self._emulator), c_char_p(text.encode('utf-8')), c_size_t(len(text)))
        if err != 0:
            raise VInputException(vinput.VInput_error_get_message(err))

