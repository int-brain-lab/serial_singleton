import ctypes
import logging
import re
import struct
import threading
from collections.abc import Sequence
from typing import Any, overload

import numpy as np
import serial
from serial.serialutil import to_bytes  # type: ignore[attr-defined]
from serial.tools import list_ports


class SerialSingletonException(serial.SerialException):
    pass


class SerialSingleton(serial.Serial):
    _instances: dict[str | None, serial.Serial] = dict()
    _initialized = False
    _lock = threading.Lock()

    def __new__(
        cls,
        port: str | None = None,
        serial_number: str | None = None,
        *args,
        **kwargs,
    ):
        # identify the device by its serial number
        if port is None and serial_number is not None:
            port = get_port_from_serial_number(serial_number) or port

        # implement singleton
        with cls._lock:
            instance = SerialSingleton._instances.get(port, None)
            if instance is None:
                logging.debug(f'Creating new {cls.__name__} instance on {port}')
                instance = super().__new__(cls)
                SerialSingleton._instances[port] = instance
            else:
                instance_name = type(instance).__name__
                if instance_name != cls.__name__:
                    raise SerialSingletonException(
                        f'{port} is already in use by an instance of {instance_name}'
                    )
                logging.debug(f'Using existing {instance_name} instance on {port}')
            return instance

    def __init__(self, port: str | None = None, connect: bool = True, **kwargs) -> None:
        if self._initialized:
            return

        super().__init__(**kwargs)

        serial.Serial.port.fset(self, port)  # type: ignore[attr-defined]
        if port is not None and connect is True:
            self.open()

        self.port_info = next(
            (p for p in list_ports.comports() if p.device == self.port), None
        )

        self._initialized = True

    def __del__(self) -> None:
        self.close()
        with self._lock:
            if self.port in SerialSingleton._instances:
                logging.debug(f'Deleting {type(self).__name__} instance on {self.port}')
                SerialSingleton._instances.pop(self.port)

    def open(self) -> None:
        super().open()
        logging.debug(f'Serial connection to {self.port} opened')

    def close(self) -> None:
        super().close()
        logging.debug(f'Serial connection to {self.port} closed')

    @property
    def port(self) -> str | None:
        """
        Get the serial device's communication port.

        Returns
        -------
        str
            The serial port (e.g., 'COM3', '/dev/ttyUSB0') used by the serial device.
        """
        return super().port

    @port.setter
    def port(self, port: str | None):
        """
        Set the serial device's communication port.

        This setter allows changing the communication port before the object is
        instantiated. Once the object is instantiated, attempting to change the port
        will raise a SerialSingletonException.

        Parameters
        ----------
        port : str
            The new communication port to be set (e.g., 'COM3', '/dev/ttyUSB0').

        Raises
        ------
        SerialSingletonException
            If an attempt is made to change the port after the object has been
            instantiated.
        """
        if self._initialized:
            raise SerialSingletonException(
                'Port cannot be changed after instantiation.'
            )
        if port is not None:
            serial.Serial.port.fset(self, port)  # type: ignore[attr-defined]

    def write(self, data: tuple[Sequence[Any], str] | Any) -> int | None:
        """
        Write data to the serial device.

        Parameters
        ----------
        data : any
            Data to be written to the serial device.
            See https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        int or None
            Number of bytes written to the serial device.
        """
        if isinstance(data, tuple()):
            size = struct.calcsize(data[1])
            buff = ctypes.create_string_buffer(size)
            struct.pack_into(data[1], buff, 0, *data[0])
            return super().write(buff)
        else:
            return super().write(self.to_bytes(data))

    @overload
    def read(self, data_specifier: int = 1) -> bytes:
        ...

    @overload
    def read(self, data_specifier: str) -> tuple[Any, ...]:
        ...

    def read(self, data_specifier=1):
        r"""
        Read data from the serial device.

        Parameters
        ----------
        data_specifier : int or str, default: 1
            The number of bytes to receive from the serial device, or a format string
            for unpacking.

            When providing an integer, the specified number of bytes will be returned
            as a bytestring. When providing a `format string`_, the data will be
            unpacked into a tuple accordingly. Format strings follow the conventions of
            the :mod:`struct` module.

            .. _format string:
                https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        bytes or tuple[Any]
            Data returned by the serial device. By default, data is formatted as a
            bytestring. Alternatively, when provided with a format string, data will
            be unpacked into a tuple according to the specified format string.
        """
        if isinstance(data_specifier, str):
            n_bytes = struct.calcsize(data_specifier)
            return struct.unpack(data_specifier, super().read(n_bytes))
        else:
            return super().read(data_specifier)

    @overload
    def query(self, query: bytes | Sequence[Any], data_specifier: int = 1) -> bytes:
        ...

    @overload
    def query(
        self, query: bytes | Sequence[Any], data_specifier: str
    ) -> tuple[Any, ...]:
        ...

    def query(self, query, data_specifier=1):
        r"""
        Query data from the serial device.

        This method is a combination of :py:meth:`write` and :py:meth:`read`.

        Parameters
        ----------
        query : any
            Query to be sent to the serial device.
        data_specifier : int or str, default: 1
            The number of bytes to receive from the serial device, or a format string
            for unpacking.

            When providing an integer, the specified number of bytes will be returned
            as a bytestring. When providing a `format string`_, the data will be
            unpacked into a tuple accordingly. Format strings follow the conventions of
            the :py:mod:`struct` module.

            .. _format string:
                https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        bytes or tuple[Any]
            Data returned by the serial device. By default, data is formatted as a
            bytestring. Alternatively, when provided with a format string, data will be
            unpacked into a tuple according to the specified format string.
        """
        self.write(query)
        return self.read(data_specifier)

    @staticmethod
    def to_bytes(data: Any) -> bytes:
        """
        Convert data to bytestring.

        This method extends :meth:`serial.to_bytes` with support for NumPy types,
        strings (interpreted as utf-8) and lists.

        Parameters
        ----------
        data : any
            Data to be converted to bytestring.

        Returns
        -------
        bytes
            Data converted to bytestring.
        """
        match data:
            case np.ndarray() | np.generic():
                return data.tobytes()
            case int():
                return data.to_bytes(1, 'little')
            case str():
                return data.encode('utf-8')
            case list():
                return b''.join([SerialSingleton.to_bytes(item) for item in data])
            case _:
                return to_bytes(data)  # type: ignore[no-any-return]


def filter_ports(**kwargs) -> list[str]:
    for port in list_ports.comports():
        yield_port = True
        for key, expected_value in kwargs.items():
            if not hasattr(port, key):
                pass
            elif isinstance(actual_value := getattr(port, key), str) and isinstance(expected_value, str):
                if bool(re.search(expected_value, actual_value)):
                    continue
            elif actual_value == expected_value:
                continue
            yield_port = False
            break
        if yield_port:
            yield port.device


def get_port_from_serial_number(serial_number: str) -> str | None:
    """
    Retrieve the com port of a USB serial device identified by its serial number.

    Parameters
    ----------
    serial_number : str
       The serial number of the USB device that you want to obtain the communication
       port of.

    Returns
    -------
    str or None
       The communication port of the USB serial device that matches the serial number
       provided by the user. The function will return None if no such device was found.
    """
    port_info = list_ports.comports()
    port_match = next((p for p in port_info if p.serial_number == serial_number), None)
    return port_match.name if port_match else None


def get_serial_number_from_port(port: str | None) -> str | None:
    """
    Retrieve the serial number of a USB serial device identified by its com port.

    Parameters
    ----------
    port : str
        The communication port of the USB serial device for which you want to retrieve
        the serial number.

    Returns
    -------
    str or None
        The serial number of the USB serial device corresponding to the provided
        communication port. Returns None if no device matches the port.
    """
    port_info = list_ports.comports()
    port_match = next((p for p in port_info if p.name == port), None)
    return port_match.serial_number if port_match else None
