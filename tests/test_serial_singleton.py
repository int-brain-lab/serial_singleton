import unittest

from serial_singleton import SerialSingleton, SerialSingletonException


class Child1(SerialSingleton):
    pass


class Child2(SerialSingleton):
    pass


class TestSingleton(unittest.TestCase):
    def test_unconnected(self):
        # creation of an instance without opening the connection
        ser = Child1(port='FakePort', connect=False)
        assert ser.is_open is False

    def test_singleton(self):
        # create a few instances of Child1
        ser1 = Child1(port='FakePort1', connect=False)
        ser2 = Child1(port='FakePort1', connect=False)
        ser3 = Child1(port='FakePort2', connect=False)

        # assert singleton behavior
        assert ser1 is ser2
        assert ser1 is not ser3

        # assert that a port blocked by Child1 can't be used by Child2
        with self.assertRaises(SerialSingletonException):
            Child2(port=ser1.port)

        # assert that port cannot be changed after initialization
        with self.assertRaises(SerialSingletonException):
            ser3.port = 'FakePort3'

        # assert that port cannot be changed after instantiation
        self.assertRaises(Exception, ser1.setPort)
